"""
CDSL eCAS (Consolidated Account Statement) PDF parser.

Each monthly statement contains:
  - A 12-month portfolio valuation trend (total only for historical months)
  - Current-month asset class breakdown: Equity | MF Folios | MF in Demat

Historical months (is_imputed=True): total known, equity/mf split estimated
using the current month's ratio.  When a later eCAS covers that month as its
"current" month, the imputed row is replaced with actual data.
"""
import re
from datetime import datetime
from pathlib import Path

from app.parsers.base import ParsedStatement, PortfolioSnapshotRow, SourceKind
from app.parsers.pdf import extract_pdf_text

# "01-05-2026" date format in period line
PERIOD_RE = re.compile(
    r"FOR THE PERIOD FROM\s+(\d{2}-\d{2}-\d{4})\s+TO\s+(\d{2}-\d{2}-\d{4})",
    re.IGNORECASE,
)

# Trend table row: "Jun 2025  32,73,485.86 ..." — first two tokens only
TREND_ROW_RE = re.compile(r"^([A-Z][a-z]{2} \d{4})\s+([\d,]+\.\d{2})")

# Asset class lines (on the summary page)
EQUITY_RE = re.compile(r"^Equity\s+([\d,]+\.\d{2})")
MF_FOLIO_RE = re.compile(r"^Mutual Fund Folios\s+([\d,]+\.\d{2})")
MF_DEMAT_RE = re.compile(r"^Mutual Funds Held in Demat Form\s+([\d,]+\.\d{2})")


def parse_ecas_pdf(path: Path, password: str | None) -> ParsedStatement:
    pages = extract_pdf_text(path, password)
    lines = [ln.strip() for page in pages for ln in page.splitlines() if ln.strip()]
    full_text = "\n".join(lines)

    statement_month = _extract_statement_month(full_text)
    trend_totals = _extract_trend(lines)          # {month_str: total_value}
    equity_val, mf_folio_val, mf_demat_val = _extract_asset_classes(lines)

    if not statement_month:
        # Fall back to last row of trend table
        if trend_totals:
            statement_month = max(trend_totals)
        else:
            raise ValueError("Could not determine statement month from eCAS PDF.")

    mf_val = round(mf_folio_val + mf_demat_val, 2)
    total_actual = round(equity_val + mf_val, 2)

    # Compute split ratios from the current month's actual data
    equity_ratio = equity_val / total_actual if total_actual else 0.0
    mf_ratio = mf_val / total_actual if total_actual else 1.0

    rows: list[PortfolioSnapshotRow] = []

    for month_str, total in sorted(trend_totals.items()):
        if month_str == statement_month:
            # Current month — actual split
            rows.append(PortfolioSnapshotRow(
                month=month_str,
                total_value=round(total, 2),
                equity_value=round(equity_val, 2),
                mf_value=round(mf_val, 2),
                is_imputed=False,
            ))
        else:
            # Historical month — impute split from current-month ratio
            rows.append(PortfolioSnapshotRow(
                month=month_str,
                total_value=round(total, 2),
                equity_value=round(total * equity_ratio, 2),
                mf_value=round(total * mf_ratio, 2),
                is_imputed=True,
            ))

    # Derive date objects for ParsedStatement metadata
    start_date = datetime.strptime(min(trend_totals), "%Y-%m").date() if trend_totals else None
    end_date = datetime.strptime(statement_month, "%Y-%m").date() if statement_month else None

    return ParsedStatement(
        source_kind=SourceKind.PORTFOLIO,
        institution="CDSL",
        account_name="eCAS Portfolio",
        statement_start=start_date,
        statement_end=end_date,
        statement_date=end_date,
        summary={
            "statement_month": statement_month,
            "total_value": total_actual,
            "equity_value": round(equity_val, 2),
            "mf_value": round(mf_val, 2),
            "months_in_trend": len(trend_totals),
        },
        rows=rows,
        warnings=[],
    )


def _extract_statement_month(text: str) -> str | None:
    m = PERIOD_RE.search(text)
    if m:
        # period end date e.g. "31-05-2026" → "2026-05"
        end_str = m.group(2)  # DD-MM-YYYY
        d = datetime.strptime(end_str, "%d-%m-%Y")
        return d.strftime("%Y-%m")
    return None


def _extract_trend(lines: list[str]) -> dict[str, float]:
    """Parse all Month-Year / Portfolio-Value pairs from the trend table."""
    result: dict[str, float] = {}
    for line in lines:
        m = TREND_ROW_RE.match(line)
        if m:
            mon_str = m.group(1)   # e.g. "Jun 2025"
            value = float(m.group(2).replace(",", ""))
            try:
                d = datetime.strptime(mon_str, "%b %Y")
                result[d.strftime("%Y-%m")] = value
            except ValueError:
                pass
    return result


def _extract_asset_classes(lines: list[str]) -> tuple[float, float, float]:
    """Return (equity, mf_folio, mf_demat) values from the asset class breakdown."""
    equity = mf_folio = mf_demat = 0.0
    for line in lines:
        m = EQUITY_RE.match(line)
        if m:
            equity = float(m.group(1).replace(",", ""))
            continue
        m = MF_FOLIO_RE.match(line)
        if m:
            mf_folio = float(m.group(1).replace(",", ""))
            continue
        m = MF_DEMAT_RE.match(line)
        if m:
            mf_demat = float(m.group(1).replace(",", ""))
    return equity, mf_folio, mf_demat
