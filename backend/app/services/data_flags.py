from datetime import date
from sqlalchemy.orm import Session
from app.models import Account, BankTransaction, BrokerHolding, CardTransaction

STALE_DAYS = 45


def get_data_flags(db: Session) -> list[dict]:
    """Return accounts whose most-recent data is older than STALE_DAYS days."""
    today = date.today()
    flags = []

    for acct in db.query(Account).order_by(Account.institution, Account.name).all():
        if acct.account_type == "bank":
            row = (
                db.query(BankTransaction.transaction_date)
                .filter(BankTransaction.account_id == acct.id)
                .order_by(BankTransaction.transaction_date.desc())
                .first()
            )
            last_date = row[0] if row else None
        elif acct.account_type == "credit_card":
            row = (
                db.query(CardTransaction.transaction_date)
                .filter(CardTransaction.account_id == acct.id)
                .order_by(CardTransaction.transaction_date.desc())
                .first()
            )
            last_date = row[0] if row else None
        elif acct.account_type == "broker":
            row = (
                db.query(BrokerHolding.as_of_date)
                .filter(BrokerHolding.account_id == acct.id)
                .order_by(BrokerHolding.as_of_date.desc())
                .first()
            )
            last_date = row[0] if row else None
        else:
            continue

        days_since = (today - last_date).days if last_date else None
        if days_since is None or days_since > STALE_DAYS:
            flags.append(
                {
                    "account_id": acct.id,
                    "account_name": acct.name,
                    "institution": acct.institution,
                    "account_type": acct.account_type,
                    "last_date": str(last_date) if last_date else None,
                    "days_since": days_since,
                }
            )

    return flags
