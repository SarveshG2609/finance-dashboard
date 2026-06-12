import hashlib
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import (
    Account,
    BankTransaction,
    BrokerHolding,
    BrokerPnl,
    CardTransaction,
    ImportBatch,
    PortfolioSnapshot,
    new_id,
)
from app.parsers.base import (
    BankTransactionRow,
    BrokerHoldingRow,
    BrokerSummaryRow,
    CardTransactionRow,
    ParsedStatement,
    PortfolioSnapshotRow,
    SourceKind,
)

_SOURCE_KIND_TO_ACCOUNT_TYPE = {
    SourceKind.BANK: "bank",
    SourceKind.CREDIT_CARD: "credit_card",
    SourceKind.BROKER_PNL: "broker",
}

# PORTFOLIO statements don't map to an Account row; handled separately.



def confirm_import(
    db: Session,
    parsed: ParsedStatement,
    file_sha256: str,
    original_filename: str,
) -> dict:
    existing = db.query(ImportBatch).filter_by(file_sha256=file_sha256, status="imported").first()
    if existing:
        raise ValueError(f"File already imported (batch {existing.id}).")

    # eCAS portfolio statements are not linked to an Account row
    if parsed.source_kind == SourceKind.PORTFOLIO:
        return _confirm_portfolio(db, parsed, file_sha256, original_filename)

    account = db.query(Account).filter_by(
        institution=parsed.institution,
        name=parsed.account_name,
    ).first()
    if not account:
        account = Account(
            id=new_id(),
            name=parsed.account_name,
            institution=parsed.institution,
            account_type=_SOURCE_KIND_TO_ACCOUNT_TYPE[parsed.source_kind],
            masked_identifier=parsed.masked_identifier,
        )
        db.add(account)
        db.flush()

    batch = ImportBatch(
        id=new_id(),
        source_kind=parsed.source_kind.value,
        institution=parsed.institution,
        account_name=parsed.account_name,
        original_filename=original_filename,
        file_sha256=file_sha256,
        statement_start=parsed.statement_start,
        statement_end=parsed.statement_end,
        status="previewed",
    )
    db.add(batch)
    db.flush()

    new_rows = 0
    duplicate_rows = 0

    # Track per-statement occurrence counts for within-batch duplicate rows
    # (e.g. same merchant paid twice on same day for same amount)
    card_occurrence: dict[tuple, int] = defaultdict(int)

    for row in parsed.rows:
        if isinstance(row, BankTransactionRow):
            dedupe_key = _bank_dedupe_key(account.id, row)
            if db.query(BankTransaction).filter_by(dedupe_key=dedupe_key).first():
                duplicate_rows += 1
                continue
            db.add(BankTransaction(
                id=new_id(),
                import_batch_id=batch.id,
                account_id=account.id,
                transaction_date=row.transaction_date,
                description=row.description,
                withdrawal=row.withdrawal,
                deposit=row.deposit,
                closing_balance=row.closing_balance,
                payment_channel=row.payment_channel,
                classification=row.classification,
                reference=row.reference,
                dedupe_key=dedupe_key,
            ))
            new_rows += 1

        elif isinstance(row, CardTransactionRow):
            base = (account.id, str(parsed.statement_start), str(row.transaction_date), str(row.amount), row.entry_type, row.description)
            card_occurrence[base] += 1
            dedupe_key = _card_dedupe_key(account.id, row, parsed.statement_start, card_occurrence[base])
            if db.query(CardTransaction).filter_by(dedupe_key=dedupe_key).first():
                duplicate_rows += 1
                continue
            db.add(CardTransaction(
                id=new_id(),
                import_batch_id=batch.id,
                account_id=account.id,
                statement_date=parsed.statement_date,
                billing_start=parsed.statement_start,
                billing_end=parsed.statement_end,
                transaction_date=row.transaction_date,
                description=row.description,
                amount=row.amount,
                entry_type=row.entry_type,
                is_payment=int(row.is_payment),
                is_refund=int(row.is_refund),
                currency=row.currency,
                foreign_amount=row.foreign_amount,
                foreign_currency=row.foreign_currency,
                dedupe_key=dedupe_key,
            ))
            new_rows += 1

        elif isinstance(row, BrokerSummaryRow):
            existing_pnl = db.query(BrokerPnl).filter_by(
                account_id=account.id,
                period_start=row.period_start,
                period_end=row.period_end,
            ).first()
            if existing_pnl:
                duplicate_rows += 1
                continue
            db.add(BrokerPnl(
                id=new_id(),
                import_batch_id=batch.id,
                account_id=account.id,
                broker=row.broker,
                period_start=row.period_start,
                period_end=row.period_end,
                realized_pnl=row.realized_pnl,
                unrealized_pnl=row.unrealized_pnl,
                charges=row.charges,
                other_debits_credits=row.other_debits_credits,
                taxes=row.taxes,
            ))
            new_rows += 1

        elif isinstance(row, BrokerHoldingRow):
            existing_h = db.query(BrokerHolding).filter_by(
                account_id=account.id,
                as_of_date=row.as_of_date,
                symbol_or_name=row.symbol_or_name,
            ).first()
            if existing_h:
                duplicate_rows += 1
                continue
            db.add(BrokerHolding(
                id=new_id(),
                import_batch_id=batch.id,
                account_id=account.id,
                broker=parsed.institution,
                as_of_date=row.as_of_date,
                symbol_or_name=row.symbol_or_name,
                isin=row.isin,
                quantity=row.quantity,
                buy_value=row.buy_value,
                current_or_sell_value=row.current_or_sell_value,
                realized_pnl=row.realized_pnl,
                unrealized_pnl=row.unrealized_pnl,
            ))
            new_rows += 1

    batch.row_count = new_rows
    batch.status = "imported"
    db.commit()

    return {
        "batch_id": batch.id,
        "new_rows": new_rows,
        "duplicate_rows": duplicate_rows,
        "status": "imported",
    }


def _confirm_portfolio(
    db: Session,
    parsed: ParsedStatement,
    file_sha256: str,
    original_filename: str,
) -> dict:
    """Insert/update portfolio_snapshots from an eCAS statement.

    Rules:
    - Actual (is_imputed=False) always overwrites an existing imputed row.
    - Imputed never overwrites an existing actual row.
    - Imputed CAN overwrite an older imputed row (better total from newer statement).
    """
    batch = ImportBatch(
        id=new_id(),
        source_kind=parsed.source_kind.value,
        institution=parsed.institution,
        account_name=parsed.account_name,
        original_filename=original_filename,
        file_sha256=file_sha256,
        statement_start=parsed.statement_start,
        statement_end=parsed.statement_end,
        status="previewed",
    )
    db.add(batch)
    db.flush()

    new_rows = updated_rows = skipped = 0

    for row in parsed.rows:
        if not isinstance(row, PortfolioSnapshotRow):
            continue

        existing = (
            db.query(PortfolioSnapshot)
            .filter(PortfolioSnapshot.month == row.month)
            .first()
        )

        if existing is None:
            db.add(PortfolioSnapshot(
                id=new_id(),
                import_batch_id=batch.id,
                month=row.month,
                equity_value=row.equity_value,
                mf_value=row.mf_value,
                total_value=row.total_value,
                is_imputed=row.is_imputed,
            ))
            new_rows += 1
        elif not existing.is_imputed and row.is_imputed:
            # Never replace actual data with an estimate
            skipped += 1
        else:
            # Actual overwrites imputed; newer imputed overwrites older imputed
            existing.equity_value = row.equity_value
            existing.mf_value = row.mf_value
            existing.total_value = row.total_value
            existing.is_imputed = row.is_imputed
            existing.import_batch_id = batch.id
            updated_rows += 1

    batch.row_count = new_rows + updated_rows
    batch.status = "imported"
    db.commit()

    return {
        "batch_id": batch.id,
        "new_rows": new_rows,
        "updated_rows": updated_rows,
        "duplicate_rows": skipped,
        "status": "imported",
    }


def _bank_dedupe_key(account_id: str, row: BankTransactionRow) -> str:
    parts = "|".join([
        account_id,
        str(row.transaction_date),
        str(row.withdrawal),
        str(row.deposit),
        row.description,
        row.reference or "",
    ])
    return hashlib.sha256(parts.encode()).hexdigest()


def _card_dedupe_key(account_id: str, row: CardTransactionRow, billing_start, occurrence: int = 1) -> str:
    parts = "|".join([
        account_id,
        str(billing_start),
        str(row.transaction_date),
        str(row.amount),
        row.entry_type,
        row.description,
        str(occurrence),
    ])
    return hashlib.sha256(parts.encode()).hexdigest()
