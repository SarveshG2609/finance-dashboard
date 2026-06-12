from calendar import monthrange
from datetime import date

from sqlalchemy.orm import Session

from app.models import Account, BankTransaction, ManualAsset, PortfolioSnapshot


def get_networth_summary(db: Session, months: int = 12) -> dict:
    today = date.today()
    current = _current_breakdown(db, today)
    trend = _monthly_trend(db, today, months)
    return {"current": current, "trend": trend}


# ── Bank ─────────────────────────────────────────────────────────────────────

def _bank_breakdown(db: Session, as_of: date) -> tuple[float, list[dict]]:
    """Sum latest closing balance per bank account up to as_of. Returns (total, per_account_list)."""
    accounts = db.query(Account).filter(Account.account_type == "bank").all()
    items = []
    total = 0.0
    for acct in accounts:
        row = (
            db.query(BankTransaction)
            .filter(
                BankTransaction.account_id == acct.id,
                BankTransaction.closing_balance.isnot(None),
                BankTransaction.transaction_date <= as_of,
            )
            .order_by(BankTransaction.transaction_date.desc(), BankTransaction.id.desc())
            .first()
        )
        if row:
            total += row.closing_balance
            items.append({
                "name": acct.name,
                "balance": round(row.closing_balance, 2),
                "as_of": str(row.transaction_date),
            })
    return round(total, 2), items


# ── Investments ───────────────────────────────────────────────────────────────

def _investments_breakdown(db: Session, month_str: str) -> dict:
    """Return equity + mf values from the nearest PortfolioSnapshot on or before month_str."""
    snap = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.month <= month_str)
        .order_by(PortfolioSnapshot.month.desc())
        .first()
    )
    if not snap:
        return {"equity": 0.0, "mutual_funds": 0.0, "is_imputed": False}
    return {
        "equity": round(snap.equity_value, 2),
        "mutual_funds": round(snap.mf_value, 2),
        "is_imputed": snap.is_imputed,
    }


# ── Manual assets ─────────────────────────────────────────────────────────────

def _manual_totals(db: Session, as_of: date) -> tuple[float, float]:
    rows = db.query(ManualAsset).filter(ManualAsset.date <= as_of).all()
    latest: dict[str, ManualAsset] = {}
    for r in rows:
        if r.name not in latest or r.date > latest[r.name].date:
            latest[r.name] = r
    assets = sum(r.value for r in latest.values() if r.kind == "asset")
    liabilities = sum(r.value for r in latest.values() if r.kind == "liability")
    return assets, liabilities


# ── Aggregates ────────────────────────────────────────────────────────────────

def _current_breakdown(db: Session, today: date) -> dict:
    month_str = today.strftime("%Y-%m")
    bank_balance, bank_accounts = _bank_breakdown(db, today)
    inv = _investments_breakdown(db, month_str)
    manual_assets, liabilities = _manual_totals(db, today)

    total = bank_balance + inv["equity"] + inv["mutual_funds"] + manual_assets - liabilities

    return {
        "bank_balance": bank_balance,
        "bank_accounts": bank_accounts,
        "equity": inv["equity"],
        "mutual_funds": inv["mutual_funds"],
        "is_imputed": inv["is_imputed"],
        "manual_assets": round(manual_assets, 2),
        "liabilities": round(liabilities, 2),
        "total": round(total, 2),
    }


def _monthly_trend(db: Session, today: date, months: int) -> list[dict]:
    trend = []
    year, month = today.year, today.month

    for _ in range(months):
        month_str = f"{year}-{month:02d}"
        month_end = date(year, month, monthrange(year, month)[1])
        bank, bank_accounts = _bank_breakdown(db, month_end)
        inv = _investments_breakdown(db, month_str)
        manual_assets, liabilities = _manual_totals(db, month_end)
        investments = inv["equity"] + inv["mutual_funds"]
        total = bank + investments + manual_assets - liabilities

        trend.append({
            "month": month_str,
            "total": round(total, 2),
            "bank": round(bank, 2),
            "bank_accounts": bank_accounts,
            "investments": round(investments, 2),
            "equity": inv["equity"],
            "mutual_funds": inv["mutual_funds"],
            "is_imputed": inv["is_imputed"],
            "manual": round(manual_assets - liabilities, 2),
        })
        month -= 1
        if month == 0:
            month = 12
            year -= 1

    trend.reverse()
    return trend
