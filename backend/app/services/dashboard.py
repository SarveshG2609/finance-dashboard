from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Account, BankTransaction


def get_summary(db: Session, today: date | None = None) -> dict:
    today = today or date.today()

    accounts = db.query(Account).filter_by(account_type="bank").all()

    account_balances = []
    bank_total = 0.0
    for account in accounts:
        latest_txn = (
            db.query(BankTransaction)
            .filter_by(account_id=account.id)
            .filter(BankTransaction.closing_balance.isnot(None))
            .order_by(BankTransaction.transaction_date.desc(), BankTransaction.id.desc())
            .first()
        )
        balance = latest_txn.closing_balance if latest_txn else 0.0
        as_of = latest_txn.transaction_date if latest_txn else None
        bank_total += balance or 0.0
        account_balances.append({
            "id": account.id,
            "name": account.name,
            "institution": account.institution,
            "latest_balance": balance,
            "as_of_date": as_of,
        })

    upi_spend = (
        db.query(func.sum(BankTransaction.withdrawal))
        .filter(
            BankTransaction.payment_channel == "UPI",
            BankTransaction.classification == "expense",
            func.strftime("%Y-%m", BankTransaction.transaction_date) == today.strftime("%Y-%m"),
        )
        .scalar()
    ) or 0.0

    total_expense = (
        db.query(func.sum(BankTransaction.withdrawal))
        .filter(
            BankTransaction.classification == "expense",
            func.strftime("%Y-%m", BankTransaction.transaction_date) == today.strftime("%Y-%m"),
        )
        .scalar()
    ) or 0.0

    return {
        "accounts": account_balances,
        "monthly_spend": {
            "month": today.strftime("%Y-%m"),
            "upi_spend": round(upi_spend, 2),
            "total_expense": round(total_expense, 2),
        },
        "net_worth": {
            "bank_total": round(bank_total, 2),
            "total": round(bank_total, 2),
        },
    }
