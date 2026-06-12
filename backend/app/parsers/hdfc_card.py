import re
from datetime import date, datetime
from pathlib import Path

from app.parsers.base import CardTransactionRow, ParsedStatement, SourceKind
from app.parsers.pdf import extract_pdf_text

# Transaction line: DD/MM/YYYY| HH:MM description [+ [N ]]C amount [l]
TXN_RE = re.compile(r"^(\d{2}/\d{2}/\d{4})\|\s*(\d{2}:\d{2})\s+(.+)")

# Tail of a transaction line: [+ [N ]]C amount [l]
# group 1 = "+" if present; group 2 = NeuCoins digit(s) if present; group 3 = amount
TAIL_RE = re.compile(
    r"(?:(\+)\s+(?:(\d+)\s+)?)?C\s+([\d,]+\.\d{2})(?:\s+l)?$"
)

BILLING_RE = re.compile(
    r"(\d{1,2}\s+[A-Z][a-z]{2},?\s+\d{4})\s*[-–to]+\s*(\d{1,2}\s+[A-Z][a-z]{2},?\s+\d{4})",
    re.IGNORECASE,
)
STMT_DATE_RE = re.compile(
    r"Statement Date\s*[:\-]?\s*(\d{1,2}\s+[A-Z][a-z]{2},?\s+\d{4})",
    re.IGNORECASE,
)
CARD_NO_RE = re.compile(r"(\d{4}[\sX\d]+\d{4})")


def parse_hdfc_card_pdf(path: Path, password: str) -> ParsedStatement:
    pages = extract_pdf_text(path, password)
    lines = [ln.strip() for page in pages for ln in page.splitlines() if ln.strip()]
    full_text = " ".join(lines)

    # Card name appears in the page-header line at the top of each page
    # (e.g. "Tata Neu Plus HDFC Bank Credit Card Statement"). Check the first
    # 3 lines of every page — never the body, which contains merchant names.
    header_text = " ".join(
        line
        for page in pages
        for line in page.splitlines()[:3]
    )
    account_name = _detect_card_name(header_text)
    masked_identifier = _extract_card_number(lines)
    statement_start, statement_end = _extract_billing_period(full_text)
    statement_date = _extract_statement_date(full_text) or statement_end

    rows: list[CardTransactionRow] = []
    warnings: list[str] = []

    for line in lines:
        row = _parse_transaction_line(line)
        if row:
            rows.append(row)

    # Derive period from rows if header parsing missed it
    if rows and not statement_start:
        statement_start = min(r.transaction_date for r in rows)
    if rows and not statement_end:
        statement_end = max(r.transaction_date for r in rows)

    total_debits = sum(r.amount for r in rows if r.entry_type == "debit")
    total_credits = sum(r.amount for r in rows if r.entry_type == "credit")

    return ParsedStatement(
        source_kind=SourceKind.CREDIT_CARD,
        institution="HDFC",
        account_name=account_name,
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


def _detect_card_name(text: str) -> str:
    upper = text.upper()
    if "TATA NEU PLUS" in upper:
        return "Tata Neu Plus HDFC Credit Card"
    if "TATA NEU" in upper:
        return "Tata Neu HDFC Credit Card"
    if "SWIGGY" in upper:
        return "Swiggy HDFC Credit Card"
    if "MILLENNIA" in upper:
        return "HDFC Millennia Credit Card"
    if "MONEYBACK" in upper:
        return "HDFC MoneyBack Credit Card"
    return "HDFC Credit Card"


def _extract_card_number(lines: list[str]) -> str | None:
    for i, line in enumerate(lines):
        if "credit card no" in line.lower():
            m = CARD_NO_RE.search(line)
            if m:
                return m.group(1).replace(" ", "")
            if i + 1 < len(lines):
                candidate = lines[i + 1].replace(" ", "")
                if re.fullmatch(r"[\dX]{12,19}", candidate):
                    return candidate
    return None


def _extract_billing_period(text: str) -> tuple[date | None, date | None]:
    m = BILLING_RE.search(text)
    if m:
        return _parse_date(m.group(1)), _parse_date(m.group(2))
    return None, None


def _extract_statement_date(text: str) -> date | None:
    m = STMT_DATE_RE.search(text)
    return _parse_date(m.group(1)) if m else None


def _parse_date(s: str) -> date | None:
    s = s.replace(",", "").strip()
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_transaction_line(line: str) -> CardTransactionRow | None:
    m = TXN_RE.match(line)
    if not m:
        return None

    txn_date = datetime.strptime(m.group(1), "%d/%m/%Y").date()
    rest = m.group(3)

    tail = TAIL_RE.search(rest)
    if not tail:
        return None

    plus_marker = tail.group(1)   # "+" or None
    neucoins = tail.group(2)      # digit string (NeuCoins) or None
    amount_str = tail.group(3)

    # Credit = "+" present AND no NeuCoins number after it
    is_credit = (plus_marker == "+") and (neucoins is None)
    entry_type: str = "credit" if is_credit else "debit"

    description = rest[: tail.start()].strip()

    is_payment = is_credit and any(
        kw in description.upper() for kw in ["CC PAYMENT", "BPPY", "PAYMENT"]
    )
    is_refund = is_credit and not is_payment

    return CardTransactionRow(
        transaction_date=txn_date,
        description=description,
        amount=float(amount_str.replace(",", "")),
        entry_type=entry_type,
        is_payment=is_payment,
        is_refund=is_refund,
    )
