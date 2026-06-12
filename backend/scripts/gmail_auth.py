"""
One-time Gmail OAuth authorisation.

Run this once locally:
    python backend/scripts/gmail_auth.py

It will open a browser tab asking you to approve Gmail read access.
After approval it saves backend/credentials/gmail_token.json which
contains the refresh token used by email_sync.py.

The refresh token never expires unless you revoke access, so you only
need to run this once.
"""
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDS_FILE  = Path(__file__).parents[1] / "credentials" / "gmail_oauth.json"
TOKEN_FILE  = Path(__file__).parents[1] / "credentials" / "gmail_token.json"

def main():
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)

    TOKEN_FILE.write_text(creds.to_json())
    print(f"\n✓ Authorised. Token saved to {TOKEN_FILE}")
    print(f"\nRefresh token (save this as GMAIL_REFRESH_TOKEN on Railway):")
    print(f"  {creds.refresh_token}")

if __name__ == "__main__":
    main()
