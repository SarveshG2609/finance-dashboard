"""
Kotak Bank savings account PDF parser.
Row format (multi-line blocks):
  Line 1: N  DD Mon YYYY  description_start
  Lines 2+: continuation of description
  Last line: RefNo [Amount] Balance   (2 numeric values at end)
Direction is inferred from balance change.
"""
import re
from datetime import date, datetime
from pathlib import Path

from app.parsers.base import BankTransactionRow, ParsedStatement, SourceKind
from app.parsers.pdf import extract_pdf_text

# Starts a new transaction block: row_number  DD Mon YYYY  ...
BLOCK_START_RE = re.compile(r"^(\d+)\s+(\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4})\s+(.*)")

# Last line of a block: anything  Amount  Balance  (2 comma-formatted numbers at end)
AMOUNTS_RE = re.compile(r"^(.*?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$")

# Opening balance line
OPENING_RE = re.compile(r"Opening Balance.*?([\d,]+\.\d{2})$")

ACCOUNT_NO_RE = re.compile(r"Account\s+(?:Number|No\.?)\s*[:\-]?\s*([\d]+)", re.IGNORECASE)
PERIOD_RE = re.compile(
    r"(\d{2}\s+[A-Z][a-z]{2}\s+\d{4})\s+to\s+(\d{2}\s+[A-Z][a-z]{2}\s+\d{4})",
    re.IGNORECASE,
)


def parse_kotak_bank_pdf(path: Path, password: str) -> ParsedStatement:
    pages = extract_pdf_text(path, password)
    lines = [ln.strip() for page in pages for ln in page.splitlines() if ln.strip()]
    full_text = " ".join(lines)

    masked_identifier = _extract_account_number(lines)
    statement_start, statement_end = _extract_period(full_text)

    opening_balance = _extract_opening_balance(lines)
    prev_balance = opening_balance

    rows: list[BankTransactionRow] = []
    warnings: list[str] = []

    # Collect multi-line blocks
    blocks: list[list[str]] = []
    current: list[str] | None = None

    for line in lines:
        if BLOCK_START_RE.match(line):
            if current is not None:
                blocks.append(current)
            current = [line]
        elif current is not None:
            # Stop collecting if we hit known non-transaction footer lines
            if any(kw in line for kw in ["Closing Balance", "Statement Summary", "Opening Balance"]):
                blocks.append(current)
                current = None
            else:
                current.append(line)

    if current:
        blocks.append(current)

    for block in blocks:
        row, new_balance = _parse_block(block, prev_balance)
        if row:
            rows.append(row)
            prev_balance = new_balance if new_balance is not None else prev_balance
        else:
            warnings.append(f"Skipped block: {' '.join(block)[:120]}")

    if rows and not statement_start:
        statement_start = min(r.transaction_date for r in rows)
    if rows and not statement_end:
        statement_end = max(r.transaction_date for r in rows)

    closing_balance = rows[-1].closing_balance if rows else opening_balance
    total_deposits = sum(r.deposit for r in rows)
    total_withdrawals = sum(r.withdrawal for r in rows)

    return ParsedStatement(
        source_kind=SourceKind.BANK,
        institution="Kotak",
        account_name="Kotak Savings",
        masked_identifier=masked_identifier,
        statement_start=statement_start,
        statement_end=statement_end,
        statement_date=statement_end,
        summary={
            "total_withdrawals": round(total_withdrawals, 2),
            "total_deposits": round(total_deposits, 2),
            "closing_balance": closing_balance,
            "opening_balance": opening_balance,
        },
        rows=rows,
        warnings=warnings,
    )


def _parse_block(
    block: list[str], prev_balance: float | None
) -> tuple[BankTransactionRow | None, float | None]:
    if not block:
        return None, None

    first_m = BLOCK_START_RE.match(block[0])
    if not first_m:
        return None, None

    txn_date = _parse_kotak_date(first_m.group(2))
    if not txn_date:
        return None, None

    # Scan from bottom up to find the amounts line
    for i in range(len(block) - 1, -1, -1):
        m = AMOUNTS_RE.match(block[i])
        if m:
            ref_and_prefix = m.group(1)
            amount1 = _parse_amount(m.group(2))
            new_balance = _parse_amount(m.group(3))

            # Build description from block lines before amounts line
            desc_parts = [first_m.group(3)] + block[1:i]
            if ref_and_prefix.strip():
                # ref_and_prefix is the reference number; append it
                desc_parts.append(ref_and_prefix.strip())
            description = " ".join(p for p in desc_parts if p).strip()

            # Determine direction from balance change
            if prev_balance is not None:
                diff = round(new_balance - prev_balance, 2)
                if abs(diff - amount1) < 1.0:
                    deposit, withdrawal = amount1, 0.0
                elif abs(diff + amount1) < 1.0:
                    deposit, withdrawal = 0.0, amount1
                else:
                    # Fallback: treat as deposit
                    deposit, withdrawal = amount1, 0.0
            else:
                deposit, withdrawal = amount1, 0.0

            return BankTransactionRow(
                transaction_date=txn_date,
                description=description,
                withdrawal=withdrawal,
                deposit=deposit,
                closing_balance=new_balance,
                payment_channel=_infer_channel(description),
                classification=_infer_classification(description, withdrawal, deposit),
                reference=_extract_ref(ref_and_prefix),
            ), new_balance

    return None, None


def _extract_account_number(lines: list[str]) -> str | None:
    full = " ".join(lines[:40])
    m = ACCOUNT_NO_RE.search(full)
    if m:
        num = m.group(1)
        if len(num) >= 8:
            return f"{num[:4]}XXXX{num[-4:]}"
    return None


def _extract_opening_balance(lines: list[str]) -> float | None:
    for line in lines:
        m = OPENING_RE.search(line)
        if m:
            return _parse_amount(m.group(1))
    return None


def _extract_period(text: str) -> tuple[date | None, date | None]:
    m = PERIOD_RE.search(text)
    if m:
        return _parse_kotak_date(m.group(1)), _parse_kotak_date(m.group(2))
    return None, None


def _parse_kotak_date(s: str) -> date | None:
    s = s.strip()
    try:
        return datetime.strptime(s, "%d %b %Y").date()
    except ValueError:
        return None


def _parse_amount(s: str) -> float:
    return float(s.replace(",", ""))


def _extract_ref(s: str) -> str | None:
    tokens = s.strip().split()
    for t in tokens:
        if len(t) >= 8 and re.fullmatch(r"[A-Z0-9\-]+", t, re.IGNORECASE):
            return t
    return None


def _infer_channel(desc: str) -> str:
    upper = desc.upper()
    if upper.startswith("UPI") or " UPI" in upper:
        return "UPI"
    if "NEFT" in upper:
        return "NEFT"
    if "RTGS" in upper:
        return "RTGS"
    if "IMPS" in upper:
        return "IMPS"
    if "ATM" in upper:
        return "ATM"
    return "OTHER"


def _infer_classification(desc: str, withdrawal: float, deposit: float) -> str:
    upper = desc.upper()
    if withdrawal > 0 and any(kw in upper for kw in ["CC PAYMENT", "CREDIT CARD", "BBPS"]):
        return "card_settlement"
    if any(kw in upper for kw in ["ZERODHA", "GROWW", "NSE CLEARING", "BSE"]):
        return "investment_transfer"
    if withdrawal > 0:
        return "expense"
    if deposit > 0:
        return "income_candidate"
    return "unknown"
