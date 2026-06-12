from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Account, BankTransaction, BrokerHolding, CardTransaction, ManualAsset


def get_accounts_overview(db: Session) -> dict:
    banks = _bank_accounts(db)
    credit_cards = _credit_card_accounts(db)
    brokers = _broker_accounts(db)
    manual = _manual_assets(db)
    return {
        "banks": banks,
        "credit_cards": credit_cards,
        "brokers": brokers,
        "manual_assets": manual,
    }


def _bank_accounts(db: Session) -> list[dict]:
    accounts = db.query(Account).filter_by(account_type="bank").all()
    result = []
    for acc in accounts:
        latest = (
            db.query(BankTransaction)
            .filter_by(account_id=acc.id)
            .order_by(BankTransaction.transaction_date.desc())
            .first()
        )
        earliest = (
            db.query(BankTransaction)
            .filter_by(account_id=acc.id)
            .order_by(BankTransaction.transaction_date.asc())
            .first()
        )
        txn_count = db.query(func.count(BankTransaction.id)).filter_by(account_id=acc.id).scalar() or 0
        result.append({
            "id": acc.id,
            "name": acc.name,
            "institution": acc.institution,
            "masked_identifier": acc.masked_identifier,
            "latest_balance": latest.closing_balance if latest else None,
            "last_txn_date": str(latest.transaction_date) if latest else None,
            "statement_start": str(earliest.transaction_date) if earliest else None,
            "txn_count": txn_count,
        })
    return result


def _credit_card_accounts(db: Session) -> list[dict]:
    accounts = db.query(Account).filter_by(account_type="credit_card").all()
    result = []
    for acc in accounts:
        latest_txn = (
            db.query(CardTransaction)
            .filter_by(account_id=acc.id)
            .order_by(CardTransaction.transaction_date.desc())
            .first()
        )
        billing_start = latest_txn.billing_start if latest_txn else None
        billing_end = latest_txn.billing_end if latest_txn else None

        # Total spend in the latest billing period
        total_spend = 0.0
        if billing_start and billing_end:
            total_spend = (
                db.query(func.sum(CardTransaction.amount))
                .filter(
                    CardTransaction.account_id == acc.id,
                    CardTransaction.entry_type == "debit",
                    CardTransaction.billing_start == billing_start,
                )
                .scalar()
            ) or 0.0

        txn_count = db.query(func.count(CardTransaction.id)).filter_by(account_id=acc.id).scalar() or 0
        result.append({
            "id": acc.id,
            "name": acc.name,
            "institution": acc.institution,
            "masked_identifier": acc.masked_identifier,
            "statement_date": str(latest_txn.statement_date) if latest_txn and latest_txn.statement_date else None,
            "billing_start": str(billing_start) if billing_start else None,
            "billing_end": str(billing_end) if billing_end else None,
            "last_spend": round(total_spend, 2),
            "txn_count": txn_count,
        })
    return result


def _broker_accounts(db: Session) -> list[dict]:
    accounts = db.query(Account).filter_by(account_type="broker").all()
    result = []
    for acc in accounts:
        # Latest as_of_date for this account
        latest_date = (
            db.query(func.max(BrokerHolding.as_of_date))
            .filter_by(account_id=acc.id)
            .scalar()
        )
        if latest_date:
            holdings = (
                db.query(BrokerHolding)
                .filter_by(account_id=acc.id, as_of_date=latest_date)
                .all()
            )
            portfolio_value = sum(h.current_or_sell_value for h in holdings)
            unrealized_pnl = sum(h.unrealized_pnl for h in holdings)
            holdings_count = len(holdings)
        else:
            portfolio_value = 0.0
            unrealized_pnl = 0.0
            holdings_count = 0

        result.append({
            "id": acc.id,
            "name": acc.name,
            "institution": acc.institution,
            "masked_identifier": acc.masked_identifier,
            "portfolio_value": round(portfolio_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "as_of_date": str(latest_date) if latest_date else None,
            "holdings_count": holdings_count,
        })
    return result


def _manual_assets(db: Session) -> list[dict]:
    all_entries = db.query(ManualAsset).order_by(ManualAsset.date.desc()).all()
    # Latest entry per name
    seen: set[str] = set()
    result = []
    for m in all_entries:
        if m.name not in seen:
            seen.add(m.name)
            result.append({
                "id": m.id,
                "name": m.name,
                "kind": m.kind,
                "value": m.value,
                "date": str(m.date),
                "notes": m.notes,
            })
    return result
