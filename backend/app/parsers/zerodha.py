"""
Zerodha equity P&L XLSX parser.
Sheet "Equity": summary at top, then a header row, then symbol rows.
Open holdings (Open Quantity > 0) are returned as BrokerHoldingRow entries.
"""
import re
from datetime import date
from pathlib import Path

import openpyxl

from app.parsers.base import BrokerHoldingRow, BrokerSummaryRow, ParsedStatement, SourceKind


def parse_zerodha_xlsx(path: Path, password: str | None = None) -> ParsedStatement:
    wb = openpyxl.load_workbook(str(path), data_only=True)
    ws = wb["Equity"]

    rows_raw = list(ws.iter_rows(values_only=True))

    client_id, period_start, period_end, summary_vals = _parse_header(rows_raw)
    realized_pnl = summary_vals.get("realized_pnl", 0.0)
    unrealized_pnl = summary_vals.get("unrealized_pnl", 0.0)
    charges = summary_vals.get("charges", 0.0)
    other = summary_vals.get("other", 0.0)

    # Find the data header row (contains "Symbol")
    header_idx = None
    for i, row in enumerate(rows_raw):
        if row[1] == "Symbol":
            header_idx = i
            break

    holdings: list[BrokerHoldingRow] = []
    if header_idx is not None:
        for row in rows_raw[header_idx + 1 :]:
            h = _parse_holding_row(row, period_end)
            if h:
                holdings.append(h)

    summary_row = BrokerSummaryRow(
        broker="Zerodha",
        period_start=period_start or date.today(),
        period_end=period_end or date.today(),
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        charges=charges,
        other_debits_credits=other,
    )

    total_value = sum(h.current_or_sell_value for h in holdings)

    return ParsedStatement(
        source_kind=SourceKind.BROKER_PNL,
        institution="Zerodha",
        account_name=f"Zerodha ({client_id})" if client_id else "Zerodha",
        masked_identifier=client_id,
        statement_start=period_start,
        statement_end=period_end,
        statement_date=period_end,
        summary={
            "realized_pnl": round(realized_pnl, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "charges": round(charges, 2),
            "total_holdings_value": round(total_value, 2),
            "holdings_count": len(holdings),
        },
        rows=[summary_row, *holdings],
        warnings=[],
    )


def _parse_header(rows: list) -> tuple[str | None, date | None, date | None, dict]:
    client_id = None
    period_start = None
    period_end = None
    vals: dict = {}

    for row in rows:
        cell1 = row[1] if len(row) > 1 else None
        cell2 = row[2] if len(row) > 2 else None

        if cell1 == "Client ID" and cell2:
            client_id = str(cell2)
        elif isinstance(cell1, str) and "P&L Statement" in cell1:
            m = re.search(r"from\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", cell1)
            if m:
                period_start = date.fromisoformat(m.group(1))
                period_end = date.fromisoformat(m.group(2))
        elif cell1 == "Realized P&L" and isinstance(cell2, (int, float)):
            vals["realized_pnl"] = float(cell2)
        elif cell1 == "Unrealized P&L" and isinstance(cell2, (int, float)):
            vals["unrealized_pnl"] = float(cell2)
        elif cell1 == "Charges" and isinstance(cell2, (int, float)):
            vals["charges"] = float(cell2)
        elif cell1 == "Other Credit & Debit" and isinstance(cell2, (int, float)):
            vals["other"] = float(cell2)

    return client_id, period_start, period_end, vals


def _parse_holding_row(row: tuple, as_of: date | None) -> BrokerHoldingRow | None:
    # Columns (0-indexed): 0=None, 1=Symbol, 2=ISIN, 3=Qty, 4=BuyVal, 5=SellVal,
    # 6=RealPnl, 7=RealPct, 8=PrevClose, 9=OpenQty, 10=OpenType, 11=OpenVal,
    # 12=UnrealPnl, 13=UnrealPct
    if len(row) < 13:
        return None
    symbol = row[1]
    isin = row[2] if row[2] else None
    open_qty = _to_float(row[9])
    open_value = _to_float(row[11])
    prev_close = _to_float(row[8])
    unrealized = _to_float(row[12])
    realized = _to_float(row[6])
    buy_value = _to_float(row[4])

    if not symbol or open_qty is None or open_qty <= 0:
        return None

    # Use open_value when available; else compute from prev_close
    current_value = open_value if (open_value and open_value > 0) else (
        (prev_close or 0) * open_qty
    )

    return BrokerHoldingRow(
        as_of_date=as_of or date.today(),
        symbol_or_name=str(symbol),
        isin=str(isin) if isin else None,
        quantity=open_qty,
        buy_value=buy_value or max(0, current_value - (unrealized or 0)),
        current_or_sell_value=current_value,
        realized_pnl=realized or 0.0,
        unrealized_pnl=unrealized or 0.0,
    )


def _to_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
