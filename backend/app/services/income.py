"""
Income service.

Categories:
  job_business   — salary / payroll / freelance (NEFT/RTGS from employers/clients)
  stcg           — realized short-term capital gains (NSE/BSE clearing settlements)
  interest       — bond coupon / FD interest / NBFC payouts
  unrealized_ltcg — unrealized gain across broker holdings (derived, not a bank deposit)
  misc           — manual income entries

UPI deposits from individuals are excluded entirely — friend splits, reimbursements,
etc. are not income. Only institutional NEFT/RTGS/IMPS credits qualify.
"""
import re
from datetime import date

from sqlalchemy.orm import Session

from app.models import BankTransaction, BrokerHolding, IncomeEntry

# ── Category detection ────────────────────────────────────────────────────────

_SALARY_KEYWORDS  = ["SALARY", " SAL ", "PAYROLL", "STIPEND", "WAGES", "CTCPAY"]

# NSE/BSE clearing is intentionally NOT auto-classified: the same description
# covers equity settlement (STCG), bond maturity (principal return), bond coupons,
# and MF redemptions. Principal returns are NOT income. Add realized gains manually
# as Miscellaneous entries.
_EXCHANGE_KEYWORDS = ["NSE CLEARING", "BSE CLEARING", "NSCCL", "NSE CLEAR", "BSE CLEAR"]

_INTEREST_KEYWORDS = [
    "INTEREST", "DIVIDEND", "COUPON", "BOND INT", "DEBENTURE",
    "INDIABULLS", "BAJAJ FINANCE", "HDFC LTD", "LICHSGFIN", "RECLTD",
    "NAVI FINSERV", "NAVI TECH",
]


def _category(description: str) -> str | None:
    """
    Returns the income category or None if the deposit should be excluded.
    Excluded: UPI from individuals, exchange settlements (ambiguous).
    """
    upper = description.upper()

    # UPI deposits — personal transfers, not income
    if upper.startswith("UPI-"):
        return None

    # Exchange settlements (NSE/BSE) are excluded — could be principal return,
    # not just capital gains. User should add STCG manually if applicable.
    if any(k in upper for k in _EXCHANGE_KEYWORDS):
        return None

    if any(k in upper for k in _SALARY_KEYWORDS):
        return "job_business"

    if any(k in upper for k in _INTEREST_KEYWORDS):
        return "interest"

    # Remaining NEFT/IMPS/RTGS from unrecognised institutions
    if any(k in upper for k in ["RTGS", "NEFT", "IMPS"]):
        return "interest"

    return None


# ── Entity name extraction ────────────────────────────────────────────────────

def _entity_name(description: str) -> str:
    """Return a short, clean entity name from a raw bank NEFT/RTGS description."""
    name = description.strip()
    # 1. Remove RTGS/NEFT/IMPS prefix + the reference blob that follows
    name = re.sub(r'^(RTGS|NEFT|IMPS)\s+\S+\s*', '', name)
    # 2. Remove trailing RTGSINW/NEFTINW ref codes
    name = re.sub(r'\s+(RTGSINW|NEFTINW|IMPSINW)[-\s]\S+$', '', name, flags=re.IGNORECASE)
    # 3. Remove bank IFSC codes (4 letters + digits, e.g. "ICIC00")
    name = re.sub(r'\s+[A-Z]{4}\d+\s*$', '', name)
    # 4. Remove LIMITED / LTD / LIMITE suffix
    name = re.sub(r'\s+(LIMITED|LIMITE|LTD)\.?\s*$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s{2,}', ' ', name).strip()
    return name.title() if name else description[:40]


# ── Main service ──────────────────────────────────────────────────────────────

CATEGORY_LABELS = {
    "job_business":     "Job / Business",
    "stcg":             "Realized STCG",
    "interest":         "Bond / Interest",
    "unrealized_ltcg":  "Unrealized LTCG",
    "misc":             "Miscellaneous",
}

CATEGORY_COLORS = {
    "job_business":     "#2ECC8E",
    "stcg":             "#7C6AF7",
    "interest":         "#C8A96E",
    "unrealized_ltcg":  "#387ED1",
    "misc":             "#E05C5C",
}


def get_income_summary(db: Session, months: int = 12) -> dict:
    today = date.today()

    # ── Bank deposits ─────────────────────────────────────────────────────────
    deposits = (
        db.query(BankTransaction)
        .filter(BankTransaction.deposit > 0)
        .order_by(BankTransaction.transaction_date.desc())
        .all()
    )

    bank_entries = []
    for t in deposits:
        cat = _category(t.description)
        if cat is None:
            continue
        bank_entries.append({
            "id": t.id,
            "date": str(t.transaction_date),
            "amount": t.deposit,
            "entity": _entity_name(t.description),
            "category": cat,
            "source": "bank_auto",
        })

    # ── Manual income entries ─────────────────────────────────────────────────
    manual_entries = [
        {
            "id": e.id,
            "date": str(e.date),
            "amount": e.amount,
            "entity": e.source_name,
            "category": "misc",
            "source": "manual",
        }
        for e in db.query(IncomeEntry).order_by(IncomeEntry.date.desc()).all()
    ]

    all_entries = bank_entries + manual_entries

    # ── Unrealized LTCG from broker holdings ─────────────────────────────────
    unrealized_ltcg = round(
        sum(h.unrealized_pnl for h in db.query(BrokerHolding).all()), 2
    )

    # ── Totals by category — always include all categories (even if zero) ────
    by_category: dict[str, float] = {k: 0.0 for k in CATEGORY_LABELS}
    for e in all_entries:
        by_category[e["category"]] = round(
            by_category.get(e["category"], 0.0) + e["amount"], 2
        )
    by_category["unrealized_ltcg"] = unrealized_ltcg

    # ── Monthly trend (bank + manual only — not unrealized) ───────────────────
    monthly: dict[str, float] = {}
    tmp = today
    for _ in range(months):
        monthly[f"{tmp.year}-{tmp.month:02d}"] = 0.0
        tmp = tmp.replace(month=tmp.month - 1) if tmp.month > 1 else tmp.replace(year=tmp.year - 1, month=12)

    for e in all_entries:
        mk = e["date"][:7]
        if mk in monthly:
            monthly[mk] += e["amount"]

    trend = [{"month": k, "total": round(v, 2)} for k, v in sorted(monthly.items())]

    return {
        "total_realized": round(sum(e["amount"] for e in all_entries), 2),
        "unrealized_ltcg": unrealized_ltcg,
        "by_category": by_category,
        "trend": trend,
        "entries": sorted(all_entries, key=lambda x: x["date"], reverse=True),
        "category_labels": CATEGORY_LABELS,
        "category_colors": CATEGORY_COLORS,
    }
