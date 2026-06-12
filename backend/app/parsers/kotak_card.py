"""
Kotak White Credit Card PDF parser.

Transaction lines appear as:
    DD/MM/YYYY  description  amount  [Cr]

Credits (payments / refunds) end with "Cr".
Debits (purchases) have no suffix.
"""
import re
from datetime import date, datetime
from pathlib import Path

from app.parsers.base import CardTransactionRow, ParsedStatement, SourceKind
from app.parsers.pdf import extract_pdf_text

# DD/MM/YYYY  <description>  <amount>  [Cr]
TXN_RE = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([\d,]+\.\d{2})\s*(Cr)?$"
)

# "Statement Date 15-Dec-2025"
STMT_DATE_RE = re.compile(
    r"Statement\s+Date\s+(\d{1,2}-[A-Za-z]{3}-\d{4})", re.IGNORECASE
)

# "from 16-Nov-2025 to 15-Dec-2025" (inside the table header)
PERIOD_RE = re.compile(
    r"from\s+(\d{1,2}-[A-Za-z]{3}-\d{4})\s+to\s+(\d{1,2}-[A-Za-z]{3}-\d{4})",
    re.IGNORECASE,
)

# "Primary Card Number 4147 XXXX XXXX 5243"
CARD_RE = re.compile(
    r"Primary\s+Card\s+Number\s+([\d]{4}(?:[\s]+[X\d]{4}){3})", re.IGNORECASE
)


def parse_kotak_card_pdf(path: Path, password: str | None) -> ParsedStatement:
    pages = extract_pdf_text(path, password)
    lines = [ln.strip() for page in pages for ln in page.splitlines() if ln.strip()]
    full_text = "\n".join(lines)

    masked_identifier = _extract_card_number(full_text)
    statement_start, statement_end = _extract_billing_period(full_text)
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
        institution="Kotak",
        account_name="Kotak White Credit Card",
        masked_identifier=masked_identifier,
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


def _extract_card_number(text: str) -> str | None:
    m = CARD_RE.search(text)
    if m:
        raw = m.group(1).replace(" ", "")
        return raw
    return None


def _extract_statement_date(text: str) -> date | None:
    m = STMT_DATE_RE.search(text)
    return _parse_date(m.group(1)) if m else None


def _extract_billing_period(text: str) -> tuple[date | None, date | None]:
    m = PERIOD_RE.search(text)
    if m:
        return _parse_date(m.group(1)), _parse_date(m.group(2))
    return None, None


def _parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(s.strip(), "%d-%b-%Y").date()
    except ValueError:
        return None


def _parse_transaction_line(line: str) -> CardTransactionRow | None:
    m = TXN_RE.match(line)
    if not m:
        return None

    txn_date = datetime.strptime(m.group(1), "%d/%m/%Y").date()
    description = m.group(2).strip()
    amount = float(m.group(3).replace(",", ""))
    is_cr = bool(m.group(4))

    if amount == 0.0:
        return None

    entry_type = "credit" if is_cr else "debit"

    # "DP0..." prefix = direct payment reference from Kotak
    is_payment = is_cr and any(
        kw in description.upper()
        for kw in ["DP0", "PAYMENT", "BPPY", "NACH", "AUTO DEBIT", "ONLINE PAYMENT"]
    )
    is_refund = is_cr and not is_payment

    return CardTransactionRow(
        transaction_date=txn_date,
        description=description,
        amount=amount,
        entry_type=entry_type,
        is_payment=is_payment,
        is_refund=is_refund,
    )
