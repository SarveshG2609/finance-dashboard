from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    source_kind: Mapped[str] = mapped_column(String, nullable=False)
    institution: Mapped[str] = mapped_column(String, nullable=False)
    account_name: Mapped[str] = mapped_column(String, nullable=False)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String, nullable=False, index=True)
    statement_start: Mapped[date | None] = mapped_column(Date)
    statement_end: Mapped[date | None] = mapped_column(Date)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="previewed")
    error_message: Mapped[str | None] = mapped_column(Text)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String, nullable=False)
    institution: Mapped[str] = mapped_column(String, nullable=False)
    account_type: Mapped[str] = mapped_column(String, nullable=False)
    masked_identifier: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    bank_transactions: Mapped[list["BankTransaction"]] = relationship(back_populates="account")
    card_transactions: Mapped[list["CardTransaction"]] = relationship(back_populates="account")


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    import_batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"), nullable=False)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    withdrawal: Mapped[float] = mapped_column(Float, default=0)
    deposit: Mapped[float] = mapped_column(Float, default=0)
    closing_balance: Mapped[float | None] = mapped_column(Float)
    payment_channel: Mapped[str | None] = mapped_column(String)
    classification: Mapped[str | None] = mapped_column(String)
    reference: Mapped[str | None] = mapped_column(String)
    dedupe_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    account: Mapped[Account] = relationship(back_populates="bank_transactions")


class CardTransaction(Base):
    __tablename__ = "card_transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    import_batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"), nullable=False)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    statement_date: Mapped[date | None] = mapped_column(Date)
    billing_start: Mapped[date | None] = mapped_column(Date)
    billing_end: Mapped[date | None] = mapped_column(Date)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    entry_type: Mapped[str] = mapped_column(String, nullable=False)
    is_payment: Mapped[int] = mapped_column(Integer, default=0)
    is_refund: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String, default="INR")
    foreign_amount: Mapped[float | None] = mapped_column(Float)
    foreign_currency: Mapped[str | None] = mapped_column(String)
    dedupe_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    account: Mapped[Account] = relationship(back_populates="card_transactions")


class BrokerPnl(Base):
    __tablename__ = "broker_pnl"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    import_batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"), nullable=False)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    broker: Mapped[str] = mapped_column(String, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0)
    charges: Mapped[float] = mapped_column(Float, default=0)
    other_debits_credits: Mapped[float] = mapped_column(Float, default=0)
    taxes: Mapped[float | None] = mapped_column(Float)


class BrokerHolding(Base):
    __tablename__ = "broker_holdings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    import_batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"), nullable=False)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    broker: Mapped[str] = mapped_column(String, nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol_or_name: Mapped[str] = mapped_column(String, nullable=False)
    isin: Mapped[str | None] = mapped_column(String)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    buy_value: Mapped[float] = mapped_column(Float, default=0)
    current_or_sell_value: Mapped[float] = mapped_column(Float, default=0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0)


class IncomeEntry(Base):
    __tablename__ = "income_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    source_name: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    account_name: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ManualAsset(Base):
    __tablename__ = "manual_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
