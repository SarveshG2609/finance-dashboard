from datetime import date
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class SourceKind(str, Enum):
    BANK = "bank"
    CREDIT_CARD = "credit_card"
    BROKER_PNL = "broker_pnl"


class BankTransactionRow(BaseModel):
    row_type: Literal["bank"] = "bank"
    transaction_date: date
    description: str
    withdrawal: float = 0
    deposit: float = 0
    closing_balance: float | None = None
    payment_channel: str | None = None
    classification: str | None = None
    reference: str | None = None


class CardTransactionRow(BaseModel):
    row_type: Literal["card"] = "card"
    transaction_date: date
    description: str
    amount: float
    entry_type: Literal["debit", "credit"]
    is_payment: bool = False
    is_refund: bool = False
    currency: str = "INR"
    foreign_amount: float | None = None
    foreign_currency: str | None = None


class BrokerSummaryRow(BaseModel):
    row_type: Literal["broker_summary"] = "broker_summary"
    broker: str
    period_start: date
    period_end: date
    realized_pnl: float
    unrealized_pnl: float
    charges: float = 0
    other_debits_credits: float = 0
    taxes: float | None = None


class BrokerHoldingRow(BaseModel):
    row_type: Literal["broker_holding"] = "broker_holding"
    as_of_date: date
    symbol_or_name: str
    isin: str | None = None
    quantity: float
    buy_value: float
    current_or_sell_value: float
    realized_pnl: float = 0
    unrealized_pnl: float = 0


AnyRow = Annotated[
    BankTransactionRow | CardTransactionRow | BrokerSummaryRow | BrokerHoldingRow,
    Field(discriminator="row_type"),
]


class ParsedStatement(BaseModel):
    source_kind: SourceKind
    institution: str
    account_name: str
    masked_identifier: str | None = None
    statement_start: date | None = None
    statement_end: date | None = None
    statement_date: date | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    rows: list[AnyRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
