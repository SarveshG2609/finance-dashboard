"""
Parser registry — the single source of truth for all importable statement types.

To add a new source:
  1. Write backend/app/parsers/<name>.py with a parse_<name>(path, password?) function
  2. Add one entry to _REGISTRY below
  3. Done — the frontend dropdown populates automatically from GET /imports/sources
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.parsers.base import ParsedStatement
from app.parsers.groww import parse_groww_mf_xlsx, parse_groww_stocks_xlsx
from app.parsers.hdfc_bank import parse_hdfc_bank_pdf
from app.parsers.hdfc_card import parse_hdfc_card_pdf
from app.parsers.icici_card import parse_icici_card_pdf
from app.parsers.kotak_bank import parse_kotak_bank_pdf
from app.parsers.sbi_card import parse_sbi_card_pdf
from app.parsers.zerodha import parse_zerodha_xlsx


@dataclass(frozen=True)
class SourceSpec:
    id: str
    label: str
    requires_password: bool
    accept: str          # file-input accept filter, e.g. ".pdf" or ".xlsx"
    parser: Callable     # callable: (path, password?) -> ParsedStatement


_REGISTRY: list[SourceSpec] = [
    SourceSpec("hdfc_bank",    "HDFC Bank – Savings Account",          True,  ".pdf",  parse_hdfc_bank_pdf),
    SourceSpec("hdfc_card",    "HDFC Credit Card",                     True,  ".pdf",  parse_hdfc_card_pdf),
    SourceSpec("sbi_card",     "SBI Credit Card",                      True,  ".pdf",  parse_sbi_card_pdf),
    SourceSpec("kotak_bank",   "Kotak Bank – Savings Account",         True,  ".pdf",  parse_kotak_bank_pdf),
    SourceSpec("icici_card",   "ICICI Credit Card",                    True,  ".pdf",  parse_icici_card_pdf),
    SourceSpec("zerodha",      "Zerodha – Equity P&L (XLSX)",          False, ".xlsx", parse_zerodha_xlsx),
    SourceSpec("groww_stocks", "Groww – Stock Holdings (XLSX)",        False, ".xlsx", parse_groww_stocks_xlsx),
    SourceSpec("groww_mf",     "Groww – Mutual Fund Holdings (XLSX)",  False, ".xlsx", parse_groww_mf_xlsx),
]

_REGISTRY_MAP: dict[str, SourceSpec] = {s.id: s for s in _REGISTRY}


def list_sources() -> list[dict]:
    """Serialisable list consumed by GET /imports/sources."""
    return [
        {
            "id": s.id,
            "label": s.label,
            "requires_password": s.requires_password,
            "accept": s.accept,
        }
        for s in _REGISTRY
    ]


def preview_import(path: Path, source: str, password: str | None = None) -> ParsedStatement:
    spec = _REGISTRY_MAP.get(source)
    if not spec:
        raise ValueError(f"Unknown import source: '{source}'. Available: {list(_REGISTRY_MAP)}")

    if spec.requires_password and not password:
        raise ValueError(f"A password is required for '{spec.label}'.")

    if spec.requires_password:
        return spec.parser(path, password)
    return spec.parser(path)
