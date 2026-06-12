"""
Expenses service.

- Card debits (non-payment) + bank UPI withdrawals that are not card payments.
- Transactions < RANDOM_THRESHOLD are grouped as "Random" per card.
- Response is structured per account so the UI can render per-card expandables.
"""
import re
from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from app.models import Account, BankTransaction, CardTransaction

RANDOM_THRESHOLD = 1500.0

_CARD_PAYMENT_KEYWORDS = [
    "CRED CLUB", "CRED.CLUB", "CC PAYMENT", "CREDIT CARD PAYMENT", "AUTOPAY", "BPPY CC",
]


def _is_card_payment(desc: str) -> bool:
    upper = desc.upper()
    return any(kw in upper for kw in _CARD_PAYMENT_KEYWORDS)


def _clean_description(desc: str) -> str:
    """Strip transaction routing noise, return a readable merchant / payee name."""
    d = desc.strip()

    # Card prefixes: RAZ*, PYU*, etc.
    for prefix in ("RAZ*", "PYU*"):
        if d.upper().startswith(prefix.upper()):
            d = d[len(prefix):]
            break

    # UPI format: "UPI-<PAYEE>-<vpa>@<bank>-<IFSC>-<ref>-..."
    # Take only the payee segment — stop at the first "-" that's followed by
    # a lowercase VPA handle or a "@"-containing segment.
    if d.upper().startswith("UPI-"):
        d = d[4:]
        # Chop at "@" (VPA separator)
        at_idx = d.find("@")
        if at_idx != -1:
            d = d[:at_idx]
        # Walk dash-separated segments; stop at the first one containing lowercase
        # (those are VPA handles, not payee name parts)
        parts = d.split("-")
        name_parts = []
        for part in parts:
            if re.search(r'[a-z]', part):
                break
            name_parts.append(part)
        d = " ".join(name_parts) if name_parts else parts[0]

    # Card descriptions: remove trailing country/city codes and reference noise
    d = re.sub(r"\s+[A-Z]{2}\*?$", "", d)            # e.g. " IN", " CZ"
    d = re.sub(r"\s+\(Pay in EMI.*\)$", "", d, flags=re.IGNORECASE)
    d = re.sub(r"\s+\(Ref#?\s*\S+\).*$", "", d, flags=re.IGNORECASE)
    # Remove trailing reference blobs: "Value Dt ..." or long alphanumeric
    d = re.sub(r"\s+Value Dt\s+.*$", "", d, flags=re.IGNORECASE)
    d = re.sub(r"\s{2,}", " ", d).strip()
    return d.title() if d else desc[:40]


def get_expenses_summary(db: Session, months: int = 6) -> dict:
    today = date.today()

    # ── All credit card accounts ──────────────────────────────────────────────
    card_accounts: dict[str, Account] = {
        a.id: a
        for a in db.query(Account).filter(Account.account_type == "credit_card").all()
    }

    # ── Card debit transactions ───────────────────────────────────────────────
    card_txns = (
        db.query(CardTransaction)
        .filter(CardTransaction.entry_type == "debit", CardTransaction.is_payment == 0)
        .order_by(CardTransaction.transaction_date.desc())
        .all()
    )

    # ── All bank accounts ──────────────────────────────────────────────────────
    bank_accounts: dict[str, Account] = {
        a.id: a
        for a in db.query(Account).filter(Account.account_type == "bank").all()
    }

    # ── Bank withdrawals (not card payments) — all bank accounts ──────────────
    bank_txns = [
        t for t in db.query(BankTransaction).filter(BankTransaction.withdrawal > 0).all()
        if not _is_card_payment(t.description)
    ]

    # ── Build per-account buckets ─────────────────────────────────────────────
    account_entries: dict[str, list] = defaultdict(list)

    for t in card_txns:
        acct = card_accounts.get(t.account_id)
        if not acct:
            continue
        account_entries[t.account_id].append({
            "id": t.id,
            "date": str(t.transaction_date),
            "amount": t.amount,
            "description": _clean_description(t.description),
            "raw_description": t.description,
            "account_id": t.account_id,
            "account_name": acct.name,
            "institution": acct.institution,
        })

    for t in bank_txns:
        acct = bank_accounts.get(t.account_id)
        name = acct.name if acct else "Bank"
        institution = acct.institution if acct else "Bank"
        account_entries[t.account_id].append({
            "id": t.id,
            "date": str(t.transaction_date),
            "amount": t.withdrawal,
            "description": _clean_description(t.description),
            "raw_description": t.description,
            "account_id": t.account_id,
            "account_name": name,
            "institution": institution,
        })

    # ── Build per-account summary with Random grouping ────────────────────────
    accounts_out = []
    grand_total = 0.0

    for account_id, entries in account_entries.items():
        # Sort by date desc
        entries.sort(key=lambda x: x["date"], reverse=True)

        named_entries = [e for e in entries if e["amount"] >= RANDOM_THRESHOLD]
        random_entries = [e for e in entries if e["amount"] < RANDOM_THRESHOLD]

        account_total = sum(e["amount"] for e in entries)
        named_total = sum(e["amount"] for e in named_entries)
        random_total = sum(e["amount"] for e in random_entries)

        grand_total += account_total

        accounts_out.append({
            "account_id": account_id,
            "account_name": entries[0]["account_name"] if entries else account_id,
            "institution": entries[0]["institution"] if entries else "",
            "total": round(account_total, 2),
            "transactions": named_entries,
            "random_total": round(random_total, 2),
            "random_count": len(random_entries),
            "random_transactions": random_entries,
        })

    # Include accounts with zero spend so the UI always shows all accounts
    present_ids = {a["account_id"] for a in accounts_out}
    for acct_id, acct in {**card_accounts, **bank_accounts}.items():
        if acct_id not in present_ids:
            accounts_out.append({
                "account_id": acct_id,
                "account_name": acct.name,
                "institution": acct.institution,
                "total": 0.0,
                "transactions": [],
                "random_total": 0.0,
                "random_count": 0,
                "random_transactions": [],
            })

    # Sort accounts by total spend descending
    accounts_out.sort(key=lambda x: x["total"], reverse=True)

    # ── Monthly trend ─────────────────────────────────────────────────────────
    monthly: dict[str, float] = {}
    tmp = today
    for _ in range(months):
        monthly[f"{tmp.year}-{tmp.month:02d}"] = 0.0
        tmp = tmp.replace(month=tmp.month - 1) if tmp.month > 1 else tmp.replace(year=tmp.year - 1, month=12)

    all_entries = [e for acct in accounts_out for e in acct["transactions"] + acct["random_transactions"]]
    for e in all_entries:
        mk = e["date"][:7]
        if mk in monthly:
            monthly[mk] += e["amount"]

    trend = [{"month": k, "total": round(v, 2)} for k, v in sorted(monthly.items())]

    return {
        "total_spend": round(grand_total, 2),
        "accounts": accounts_out,
        "trend": trend,
        "random_threshold": RANDOM_THRESHOLD,
    }
