import re
from datetime import date, datetime
from pathlib import Path

from app.parsers.base import BankTransactionRow, ParsedStatement, SourceKind
from app.parsers.pdf import extract_pdf_text

DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}\b")
AMOUNT_LINE_RE = re.compile(
    r"(?P<withdrawal>[\d,]+\.\d{2})\s+"
    r"(?P<deposit>[\d,]+\.\d{2})\s+"
    r"(?P<balance>[\d,]+\.\d{2})$"
)


def parse_hdfc_bank_pdf(path: Path, password: str) -> ParsedStatement:
    pages = extract_pdf_text(path, password)
    lines = [line.strip() for page in pages for line in page.splitlines() if line.strip()]

    statement_start, statement_end = _extract_statement_period(lines)
    masked_identifier = _extract_account_number(lines)
    account_name = "HDFC Savings"

    rows: list[BankTransactionRow] = []
    warnings: list[str] = []

    current_block: list[str] = []
    for line in lines:
        if _is_noise_line(line):
            continue
        if DATE_RE.match(line):
            if current_block:
                row = _parse_transaction_block(current_block)
                if row:
                    rows.append(row)
                else:
                    warnings.append(f"Skipped unparsed transaction block: {' '.join(current_block)[:160]}")
            current_block = [line]
        elif current_block:
            current_block.append(line)

    if current_block:
        row = _parse_transaction_block(current_block)
        if row:
            rows.append(row)
        else:
            warnings.append(f"Skipped unparsed transaction block: {' '.join(current_block)[:160]}")

    total_withdrawals = sum(row.withdrawal for row in rows)
    total_deposits = sum(row.deposit for row in rows)
    closing_balance = rows[-1].closing_balance if rows else None

    return ParsedStatement(
        source_kind=SourceKind.BANK,
        institution="HDFC",
        account_name=account_name,
        masked_identifier=masked_identifier,
        statement_start=statement_start,
        statement_end=statement_end,
        statement_date=statement_end,
        summary={
            "total_withdrawals": round(total_withdrawals, 2),
            "total_deposits": round(total_deposits, 2),
            "closing_balance": closing_balance,
        },
        rows=rows,
        warnings=warnings,
    )


def _parse_transaction_block(block: list[str]) -> BankTransactionRow | None:
    amount_index = None
    amount_match = None
    for index in range(len(block) - 1, -1, -1):
        match = AMOUNT_LINE_RE.search(block[index])
        if match:
            amount_index = index
            amount_match = match
            break

    if amount_index is None or amount_match is None:
        return None

    first_line = block[0]
    txn_date = datetime.strptime(first_line[:10], "%d/%m/%Y").date()
    description_parts = [first_line[11:].strip(), *block[1:amount_index]]
    description = " ".join(part for part in description_parts if part).strip()

    withdrawal = _parse_amount(amount_match.group("withdrawal"))
    deposit = _parse_amount(amount_match.group("deposit"))
    closing_balance = _parse_amount(amount_match.group("balance"))

    return BankTransactionRow(
        transaction_date=txn_date,
        description=description,
        withdrawal=withdrawal,
        deposit=deposit,
        closing_balance=closing_balance,
        payment_channel=_infer_payment_channel(description),
        classification=_infer_classification(description, withdrawal, deposit),
        reference=_extract_reference(description),
    )


def _extract_statement_period(lines: list[str]) -> tuple[date | None, date | None]:
    joined = " ".join(lines)
    match = re.search(r"(\d{2}/\d{2}/\d{4})\s+To\s+(\d{2}/\d{2}/\d{4})", joined)
    if not match:
        return None, None
    return (
        datetime.strptime(match.group(1), "%d/%m/%Y").date(),
        datetime.strptime(match.group(2), "%d/%m/%Y").date(),
    )


def _extract_account_number(lines: list[str]) -> str | None:
    for index, line in enumerate(lines):
        if line == "Account Number" and index + 1 < len(lines):
            candidate = lines[index + 1]
            if re.fullmatch(r"\d{8,}", candidate):
                return f"{candidate[:4]}XXXX{candidate[-4:]}"
        if line.startswith(": ") and re.fullmatch(r": \d{8,}", line):
            value = line[2:]
            return f"{value[:4]}XXXX{value[-4:]}"
    return None


def _parse_amount(value: str) -> float:
    return float(value.replace(",", ""))


def _extract_reference(description: str) -> str | None:
    match = re.search(r"\bRef\s+(\d+)\b", description, flags=re.IGNORECASE)
    return match.group(1) if match else None


def _infer_payment_channel(description: str) -> str:
    upper = description.upper()
    if upper.startswith("UPI-") or " UPI" in upper or "UPIVALUE" in upper:
        return "UPI"
    if upper.startswith("NEFT") or " NEFT" in upper:
        return "NEFT"
    if upper.startswith("RTGS") or " RTGS" in upper:
        return "RTGS"
    if upper.startswith("IMPS") or " IMPS" in upper:
        return "IMPS"
    if "ATM" in upper:
        return "ATM"
    return "OTHER"


def _infer_classification(description: str, withdrawal: float, deposit: float) -> str:
    upper = description.upper()
    if withdrawal > 0 and any(token in upper for token in ["CRED CLUB", "CC PAYMENT", "CREDIT CARD", "BBPS"]):
        return "card_settlement"
    if any(token in upper for token in [
        "ZERODHA", "GROWW", "NSE CLEARING", "BSE LTD",
        "NEXT BILLION",    # Groww's bank transfer name
        "FOURDEGREE",      # Wint Wealth (bond investments)
        "WINT",
    ]):
        return "investment_transfer"
    if withdrawal > 0:
        return "expense"
    if deposit > 0:
        return "income_candidate"
    return "unknown"


def _is_noise_line(line: str) -> bool:
    return (
        line.startswith("Page ")
        or line == "Txn Date Narration Withdrawals Deposits Closing Balance"
        or line in {"Sarvesh Gupta", "Customer ID", "Account Number"}
    )
