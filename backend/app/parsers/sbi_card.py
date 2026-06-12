"""
SBI credit card statement parser.
Row format: DD Mon YY  DESCRIPTION [COUNTRY] [FOREIGN_AMT FOREIGN_CURR] INR_AMT C/D
Continuation rows (charges without date) reuse the previous transaction date.
"""
import re
from datetime import date, datetime
from pathlib import Path

from app.parsers.base import CardTransactionRow, ParsedStatement, SourceKind
from app.parsers.pdf import extract_pdf_text

# DD Mon YY at start of line (e.g. "18 Apr 26")
SBI_DATE_RE = re.compile(r"^(\d{1,2}\s+[A-Z][a-z]{2}\s+\d{2})\s+(.*)")

# Amount tail: [FOREIGN_AMT FOREIGN_CURR] INR_AMT C/D
# Foreign currency must be exactly 3 uppercase letters to avoid matching country code like "IN"
AMOUNT_TAIL_RE = re.compile(
    r"(?:([\d,]+(?:\.\d+)?)\s+([A-Z]{3})\s+)?"
    r"([\d,]+\.\d{2})\s+"
    r"([CD])$"
)

PERIOD_RE = re.compile(
    r"(\d{2}\s+[A-Z][a-z]{2}\s+\d{2})\s+to\s+(\d{2}\s+[A-Z][a-z]{2}\s+\d{2})",
    re.IGNORECASE,
)
CARD_NO_RE = re.compile(r"XXXX[\s\-]XXXX[\s\-]XXXX[\s\-]XX(\d{2})", re.IGNORECASE)


def parse_sbi_card_pdf(path: Path, password: str) -> ParsedStatement:
    pages = extract_pdf_text(path, password)
    lines = [ln for page in pages for ln in page.splitlines()]
    full_text = " ".join(ln.strip() for ln in lines if ln.strip())

    masked_identifier = _extract_card_number(full_text)
    statement_start, statement_end = _extract_period(full_text)
    # Restrict card name detection to the first 2 pages — later pages contain
    # schedule-of-charges tables that list other card products by name.
    header_text = " ".join(pages[i] for i in range(min(2, len(pages))))
    account_name = _detect_card_name(header_text)

    rows: list[CardTransactionRow] = []
    warnings: list[str] = []
    current_date: date | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        dated = SBI_DATE_RE.match(line)
        if dated:
            d = _parse_sbi_date(dated.group(1))
            if d:
                current_date = d
            rest = dated.group(2)
        else:
            rest = line

        tail = AMOUNT_TAIL_RE.search(rest)
        if not tail:
            continue

        txn_date = current_date
        if not txn_date:
            continue

        foreign_amount: float | None = None
        foreign_currency: str | None = None
        if tail.group(1) and tail.group(2):
            foreign_amount = _parse_amount(tail.group(1))
            foreign_currency = tail.group(2)

        inr_amount = _parse_amount(tail.group(3))
        entry_type: str = "credit" if tail.group(4) == "C" else "debit"

        description = rest[: tail.start()].strip()
        if not description:
            continue

        is_payment = entry_type == "credit" and any(
            kw in description.upper() for kw in ["PAYMENT RECEIVED", "CREDIT", "CASHBACK"]
        )
        is_refund = entry_type == "credit" and not is_payment

        rows.append(CardTransactionRow(
            transaction_date=txn_date,
            description=description,
            amount=inr_amount,
            entry_type=entry_type,
            is_payment=is_payment,
            is_refund=is_refund,
            foreign_amount=foreign_amount,
            foreign_currency=foreign_currency,
        ))

    if rows and not statement_start:
        statement_start = min(r.transaction_date for r in rows)
    if rows and not statement_end:
        statement_end = max(r.transaction_date for r in rows)

    total_debits = sum(r.amount for r in rows if r.entry_type == "debit")
    total_credits = sum(r.amount for r in rows if r.entry_type == "credit")

    return ParsedStatement(
        source_kind=SourceKind.CREDIT_CARD,
        institution="SBI",
        account_name=account_name,
        masked_identifier=masked_identifier,
        statement_start=statement_start,
        statement_end=statement_end,
        statement_date=statement_end,
        summary={
            "total_debits": round(total_debits, 2),
            "total_credits": round(total_credits, 2),
        },
        rows=rows,
        warnings=warnings,
    )


def _detect_card_name(text: str) -> str:
    upper = text.upper()
    # Check most-specific card types first; generic "CASHBACK" must come before
    # Tata Neu because the Cashback card's fine print mentions Tata Neu products.
    if "CASHBACK" in upper:
        return "SBI Cashback Credit Card"
    if "TATA NEU" in upper and "INFINITY" in upper:
        return "Tata Neu Infinity SBI Credit Card"
    if "TATA NEU" in upper:
        return "Tata Neu SBI Credit Card"
    if "SIMPLY" in upper:
        return "SBI SimplyCLICK Credit Card"
    return "SBI Credit Card"


def _extract_card_number(text: str) -> str | None:
    m = CARD_NO_RE.search(text)
    return f"XXXX XXXX XXXX XX{m.group(1)}" if m else None


def _extract_period(text: str) -> tuple[date | None, date | None]:
    m = PERIOD_RE.search(text)
    if m:
        return _parse_sbi_date(m.group(1)), _parse_sbi_date(m.group(2))
    return None, None


def _parse_sbi_date(s: str) -> date | None:
    s = s.strip()
    try:
        return datetime.strptime(s, "%d %b %y").date()
    except ValueError:
        return None


def _parse_amount(s: str) -> float:
    return float(s.replace(",", ""))
