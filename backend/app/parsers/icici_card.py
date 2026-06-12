"""
ICICI credit card statement parser (Sapphiro, MMT, etc.).
Row format: DD/MM/YYYY  SerNo  Description  RewardPoints  [ForeignAmt ForeignCurr]  Amount  [CR]
Card numbers appear as section headers; transactions are attributed to the most recent card.
"""
import re
from datetime import date, datetime
from pathlib import Path

from app.parsers.base import CardTransactionRow, ParsedStatement, SourceKind
from app.parsers.pdf import extract_pdf_text

# DD/MM/YYYY  7+-digit serial  description  reward_pts  [foreign] amount  [CR]
TXN_RE = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+"
    r"(\d{7,})\s+"
    r"(.+?)\s+"
    r"(\d+)\s+"
    r"(?:([\d,]+(?:\.\d+)?)\s+([A-Z]{3})\s+)?"
    r"([\d,]+\.\d{2})"
    r"(?:\s+(CR))?$"
)

# Card number line: 16-char with digits and X's (e.g. 5241XXXXXXXX4005)
CARD_LINE_RE = re.compile(r"^[\dX]{4}[\dX]{4,8}[\dX]{4}$")

# Statement period
PERIOD_RE = re.compile(
    r"(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
STMT_DATE_RE = re.compile(r"Statement Date\s*:?\s*(\d{2}/\d{2}/\d{4})", re.IGNORECASE)


def parse_icici_card_pdf(path: Path, password: str) -> ParsedStatement:
    pages = extract_pdf_text(path, password)
    lines = [ln.strip() for page in pages for ln in page.splitlines() if ln.strip()]
    full_text = " ".join(lines)

    account_name = _detect_card_name(full_text)
    primary_card = _extract_primary_card(lines)
    statement_start, statement_end = _extract_period(full_text)
    statement_date = _extract_statement_date(full_text) or statement_end

    rows: list[CardTransactionRow] = []
    warnings: list[str] = []

    for line in lines:
        row = _parse_transaction_line(line)
        if row:
            rows.append(row)

    if rows and not statement_start:
        statement_start = min(r.transaction_date for r in rows)
    if rows and not statement_end:
        statement_end = max(r.transaction_date for r in rows)

    total_debits = sum(r.amount for r in rows if r.entry_type == "debit")
    total_credits = sum(r.amount for r in rows if r.entry_type == "credit")

    return ParsedStatement(
        source_kind=SourceKind.CREDIT_CARD,
        institution="ICICI",
        account_name=account_name,
        masked_identifier=primary_card,
        statement_start=statement_start,
        statement_end=statement_end,
        statement_date=statement_date,
        summary={
            "total_debits": round(total_debits, 2),
            "total_credits": round(total_credits, 2),
        },
        rows=rows,
        warnings=warnings,
    )


def _detect_card_name(text: str) -> str:
    upper = text.upper()
    if "SAPPHIRO" in upper:
        return "ICICI Sapphiro Credit Card"
    if "MMT" in upper or "MAKEMYTRIP" in upper:
        return "ICICI MMT Credit Card"
    if "AMAZON" in upper:
        return "ICICI Amazon Pay Credit Card"
    if "CORAL" in upper:
        return "ICICI Coral Credit Card"
    return "ICICI Credit Card"


def _extract_primary_card(lines: list[str]) -> str | None:
    for line in lines:
        if CARD_LINE_RE.match(line):
            return line
    return None


def _extract_period(text: str) -> tuple[date | None, date | None]:
    m = PERIOD_RE.search(text)
    if m:
        return _parse_date(m.group(1)), _parse_date(m.group(2))
    return None, None


def _extract_statement_date(text: str) -> date | None:
    m = STMT_DATE_RE.search(text)
    return _parse_date(m.group(1)) if m else None


def _parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(s.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None


def _parse_transaction_line(line: str) -> CardTransactionRow | None:
    m = TXN_RE.match(line)
    if not m:
        return None

    txn_date = _parse_date(m.group(1))
    if not txn_date:
        return None

    description = m.group(3).strip()
    foreign_amount: float | None = None
    foreign_currency: str | None = None
    if m.group(5) and m.group(6):
        foreign_amount = float(m.group(5).replace(",", ""))
        foreign_currency = m.group(6)

    inr_amount = float(m.group(7).replace(",", ""))
    is_credit = m.group(8) == "CR"
    entry_type: str = "credit" if is_credit else "debit"

    is_payment = is_credit and any(
        kw in description.upper() for kw in ["BBPS", "PAYMENT", "PAYMENT RECEIVED"]
    )
    is_refund = is_credit and not is_payment

    return CardTransactionRow(
        transaction_date=txn_date,
        description=description,
        amount=inr_amount,
        entry_type=entry_type,
        is_payment=is_payment,
        is_refund=is_refund,
        foreign_amount=foreign_amount,
        foreign_currency=foreign_currency,
    )
