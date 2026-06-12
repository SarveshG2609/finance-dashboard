"""
Weekly Gmail sync — fetches bank/card statement PDFs from email and imports them.

Run manually:
    PYTHONPATH=backend python backend/scripts/email_sync.py

On Railway (cron service), set these env vars:
    DATABASE_URL          — injected automatically from Postgres service
    GMAIL_CLIENT_ID       — from gmail_oauth.json
    GMAIL_CLIENT_SECRET   — from gmail_oauth.json
    GMAIL_REFRESH_TOKEN   — printed after running gmail_auth.py once
"""
import base64
import os
import sys
import tempfile
from pathlib import Path

# ── Env / path setup ─────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if DATABASE_URL:
    os.environ["DATABASE_URL"] = DATABASE_URL

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.database import SessionLocal, init_db
from app.services.import_confirm import confirm_import
from app.services.import_preview import preview_import

# ── Sender → (source_id, password) mapping ───────────────────────────────────
# Keys are the actual sender addresses (case-insensitive match at runtime).
# source_id must match a registered source in import_preview.py.
# If a source_id has no parser yet, the email is skipped with a log message.
SENDER_MAP: dict[str, tuple[str, str | None]] = {
    # HDFC Bank savings account
    "hdfcbanksmartstatement@hdfcbank.bank.in":      ("hdfc_bank",  "138536162"),
    # Kotak Bank savings account
    "bankstatements@kotak.bank.in":                 ("kotak_bank", "sarv2609"),
    # SBI Credit Card
    "statements@sbicard.com":                       ("sbi_card",   "260920023025"),
    # Kotak White Credit Card
    "cardstatement@kotak.com":                      ("kotak_card", "sarv2609"),
    # ICICI Sapphiro Credit Cards
    "credit_cards@icicibank.com":                   ("icici_card", "sarv2609"),
    # HDFC Swiggy + Tata Neu Credit Cards
    "emailstatements.cards@hdfcbank.bank.in":       ("hdfc_card",  "SARV2609"),
    "emailstatements.cards@hdfcbank.net":           ("hdfc_card",  "SARV2609"),
}

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _gmail_service():
    """Build an authenticated Gmail API service using env var credentials."""
    token_file = Path(__file__).parents[1] / "credentials" / "gmail_token.json"

    if token_file.exists():
        # Local dev — use saved token file
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    else:
        # Production (Railway) — build from env vars
        client_id     = os.environ["GMAIL_CLIENT_ID"]
        client_secret = os.environ["GMAIL_CLIENT_SECRET"]
        refresh_token = os.environ["GMAIL_REFRESH_TOKEN"]
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )

    if not creds.valid:
        creds.refresh(Request())

    return build("gmail", "v1", credentials=creds)


def _list_statement_emails(service, days_back: int = 10) -> list[dict]:
    """Search Gmail for emails from known bank senders with PDF attachments."""
    sender_query = " OR ".join(f"from:{s}" for s in SENDER_MAP)
    query = f"({sender_query}) has:attachment filename:pdf newer_than:{days_back}d"
    result = service.users().messages().list(userId="me", q=query, maxResults=50).execute()
    return result.get("messages", [])


def _get_sender(service, msg_id: str) -> str:
    msg = service.users().messages().get(userId="me", id=msg_id, format="metadata",
                                         metadataHeaders=["From"]).execute()
    for h in msg["payload"]["headers"]:
        if h["name"] == "From":
            raw = h["value"].lower()
            for sender in SENDER_MAP:
                if sender.lower() in raw:
                    return sender
    return ""


def _download_pdf_attachments(service, msg_id: str) -> list[bytes]:
    """Return raw bytes for every PDF attachment in a message."""
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    pdfs = []

    def _walk(parts):
        for part in parts:
            if part.get("parts"):
                _walk(part["parts"])
            mime = part.get("mimeType", "")
            filename = part.get("filename", "")
            if "pdf" in mime.lower() or filename.lower().endswith(".pdf"):
                att_id = part.get("body", {}).get("attachmentId")
                if att_id:
                    att = service.users().messages().attachments().get(
                        userId="me", messageId=msg_id, id=att_id
                    ).execute()
                    pdfs.append(base64.urlsafe_b64decode(att["data"]))

    _walk(msg["payload"].get("parts", [msg["payload"]]))
    return pdfs


def run_sync(days_back: int = 10):
    print(f"Starting email sync (last {days_back} days)…")
    init_db()
    db = SessionLocal()
    service = _gmail_service()

    messages = _list_statement_emails(service, days_back)
    print(f"Found {len(messages)} candidate email(s).")

    imported = skipped = errors = 0

    for msg in messages:
        msg_id = msg["id"]
        sender = _get_sender(service, msg_id)
        if not sender:
            continue

        source_id, password = SENDER_MAP[sender]
        pdfs = _download_pdf_attachments(service, msg_id)

        for pdf_bytes in pdfs:
            try:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                    f.write(pdf_bytes)
                    tmp_path = Path(f.name)

                try:
                    parsed = preview_import(tmp_path, source_id, password)
                except ValueError as e:
                    tmp_path.unlink(missing_ok=True)
                    if "Unknown source" in str(e):
                        print(f"  ⚠ {source_id}: no parser available yet — skipping")
                        skipped += 1
                        continue
                    raise

                result = confirm_import(
                    db=db,
                    file_sha256=__import__("hashlib").sha256(pdf_bytes).hexdigest(),
                    original_filename=f"email_{msg_id}.pdf",
                    parsed=parsed,
                )
                tmp_path.unlink(missing_ok=True)

                if result["new_rows"] > 0:
                    print(f"  ✓ {parsed.account_name}: {result['new_rows']} new rows")
                    imported += 1
                else:
                    print(f"  – {parsed.account_name}: already up to date")
                    skipped += 1

            except ValueError as e:
                if "already imported" in str(e):
                    skipped += 1
                else:
                    print(f"  ✗ {source_id} from {sender}: {e}")
                    errors += 1
            except Exception as e:
                print(f"  ✗ {source_id} from {sender}: {e}")
                errors += 1

    db.close()
    print(f"\nDone — {imported} imported, {skipped} skipped, {errors} errors.")


if __name__ == "__main__":
    run_sync()
