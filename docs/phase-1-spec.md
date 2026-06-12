# Personal Finance Dashboard - Phase 1 Spec

## Goal

Build a local-first web app that imports actual bank, card, and broker statements, normalizes them into a SQLite database, and shows a personal finance dashboard.

Phase 1 focuses on reliable local ingestion and useful current/monthly summaries. It does not include Gmail automation, hosted deployment, or deep expense categorization.

## Source Files Validated

### Bank Statements

| Source | File Type | Password Support | Notes |
| --- | --- | --- | --- |
| HDFC Bank savings account | PDF | Required | Transaction rows include date, narration, withdrawals, deposits, closing balance. |
| Kotak savings account | PDF | Required, AES | Transaction rows include date, description, reference, withdrawal, deposit, balance. |

### Credit Card Statements

| Source | File Type | Password Support | Notes |
| --- | --- | --- | --- |
| HDFC Swiggy card | PDF | Required | Transaction rows include date/time, description, amount, and credit markers. |
| HDFC Tata Neu card | PDF | Required | Similar to HDFC Swiggy, includes UPI card transactions and NeuCoins sections. |
| SBI card | PDF | Required | Transactions use credit/debit suffixes: `C` and `D`. |
| ICICI Sapphiro card | PDF | Required, AES | Transactions include date, serial number, description, reward points, amount, and `CR` marker for credits. |
| ICICI MMT card | PDF | Required, AES | Same ICICI structure, may include foreign currency transaction details. |

### Broker Reports

| Source | File Type | Notes |
| --- | --- | --- |
| Zerodha P&L | XLSX | Sheets: `Equity`, `Other Debits and Credits`. Contains summary P&L, charges, realized/unrealized symbol rows. |
| Groww P&L | XLSX | Sheets: `Trade Level`, `Scrip Level`. Contains realized/unrealized P&L, charges, trade rows, scrip rows. |

## Phase 1 Scope

### Included

- Local web app.
- SQLite database.
- PDF and XLSX import.
- Password-based PDF reading.
- AES-encrypted PDF support through Python `cryptography`.
- Source-specific parsers for validated formats.
- Import preview before saving.
- Permanent normalized records.
- Import history and duplicate protection.
- Dashboard charts and summary cards.
- Manual income and manual asset/liability entry.

### Excluded

- Gmail automation.
- Cloud hosting.
- Automatic tax filing reports.
- Fine-grained expense categorization such as food/travel/shopping.
- Permanent storage of decrypted PDFs.
- User-editable transaction screens beyond import confirmation/manual entries.

## Normalized Data Model

### `import_batches`

Tracks every uploaded/imported file.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | text primary key | UUID. |
| `source_kind` | text | `bank`, `credit_card`, `broker_pnl`, `manual`. |
| `institution` | text | Example: `HDFC`, `SBI`, `ICICI`, `Kotak`, `Zerodha`, `Groww`. |
| `account_name` | text | User-facing source name. |
| `original_filename` | text | Original upload name. |
| `file_sha256` | text | Used for duplicate protection. |
| `statement_start` | date nullable | Source period start. |
| `statement_end` | date nullable | Source period end. |
| `imported_at` | datetime | Local import time. |
| `row_count` | integer | Number of normalized rows saved. |
| `status` | text | `previewed`, `imported`, `failed`. |
| `error_message` | text nullable | Parser/import error if any. |

### `accounts`

Represents bank accounts, cards, broker accounts, and manual asset buckets.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | text primary key | UUID. |
| `name` | text | Example: `HDFC Savings`, `SBI Cashback Card`. |
| `institution` | text | Source institution. |
| `account_type` | text | `bank`, `credit_card`, `broker`, `mutual_fund`, `manual_asset`, `manual_liability`. |
| `masked_identifier` | text nullable | Masked card/account number. |
| `created_at` | datetime | Creation time. |

### `bank_transactions`

Normalized bank statement rows.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | text primary key | UUID. |
| `import_batch_id` | text | FK to `import_batches`. |
| `account_id` | text | FK to `accounts`. |
| `transaction_date` | date | Bank transaction date. |
| `description` | text | Full narration. |
| `withdrawal` | real | Debit amount, default `0`. |
| `deposit` | real | Credit amount, default `0`. |
| `closing_balance` | real nullable | Balance after transaction. |
| `payment_channel` | text nullable | `UPI`, `NEFT`, `RTGS`, `IMPS`, `CARD_PAYMENT`, `ATM`, `OTHER`. |
| `reference` | text nullable | Extracted ref number if available. |
| `dedupe_key` | text unique | Hash of account/date/amount/description/reference. |

### `card_transactions`

Normalized credit card rows.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | text primary key | UUID. |
| `import_batch_id` | text | FK to `import_batches`. |
| `account_id` | text | FK to `accounts`. |
| `statement_date` | date nullable | Statement date. |
| `billing_start` | date nullable | Billing period start. |
| `billing_end` | date nullable | Billing period end. |
| `transaction_date` | date | Card transaction date. |
| `description` | text | Merchant/transaction narration. |
| `amount` | real | Positive amount. |
| `entry_type` | text | `debit` or `credit`. |
| `is_payment` | integer | `1` if card payment received. |
| `is_refund` | integer | `1` if refund/cashback/credit adjustment. |
| `currency` | text | Default `INR`. |
| `foreign_amount` | real nullable | For international transactions. |
| `foreign_currency` | text nullable | Example: `USD`, `IDR`. |
| `dedupe_key` | text unique | Hash of card/date/amount/description/type. |

### `broker_pnl`

Period-level broker P&L summary.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | text primary key | UUID. |
| `import_batch_id` | text | FK to `import_batches`. |
| `account_id` | text | FK to `accounts`. |
| `broker` | text | `Zerodha`, `Groww`, `SMC` later. |
| `period_start` | date | Report start. |
| `period_end` | date | Report end. |
| `realized_pnl` | real | Realized P&L. |
| `unrealized_pnl` | real | Unrealized P&L. |
| `charges` | real | Brokerage, exchange charges, STT, GST, etc. |
| `other_debits_credits` | real | Other debits/credits if available. |
| `taxes` | real nullable | Tax split if available. |

### `broker_holdings`

Symbol/scrip-level holdings and P&L rows.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | text primary key | UUID. |
| `import_batch_id` | text | FK to `import_batches`. |
| `account_id` | text | FK to `accounts`. |
| `broker` | text | Source broker. |
| `as_of_date` | date | Report date/period end. |
| `symbol_or_name` | text | Symbol or stock name. |
| `isin` | text nullable | ISIN where available. |
| `quantity` | real | Quantity/open quantity. |
| `buy_value` | real | Buy/invested value. |
| `current_or_sell_value` | real | Current value for unrealized, sell value for realized. |
| `realized_pnl` | real | Realized symbol P&L. |
| `unrealized_pnl` | real | Unrealized symbol P&L. |

### `income_entries`

Manual income source tagging.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | text primary key | UUID. |
| `date` | date | Income date. |
| `source_name` | text | Example: `Zol`, `Client ABC`. |
| `amount` | real | Income amount. |
| `account_name` | text nullable | Destination account. |
| `notes` | text nullable | Optional notes. |
| `created_at` | datetime | Entry time. |

### `manual_assets`

Manual asset/liability values not covered by statements.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | text primary key | UUID. |
| `date` | date | Snapshot date. |
| `name` | text | Example: `Cash`, `Loan Outstanding`, `Gold`. |
| `kind` | text | `asset` or `liability`. |
| `value` | real | Snapshot value. |
| `notes` | text nullable | Optional notes. |
| `created_at` | datetime | Entry time. |

## Parser Output Contract

Every parser should return the same envelope:

```json
{
  "source_kind": "credit_card",
  "institution": "HDFC",
  "account_name": "Swiggy HDFC",
  "masked_identifier": "526873XXXXXX2789",
  "statement_start": "2026-04-20",
  "statement_end": "2026-05-19",
  "statement_date": "2026-05-19",
  "summary": {
    "total_debits": 4407.6,
    "total_credits": 18055.1,
    "closing_balance": null
  },
  "rows": []
}
```

Rows vary by source kind but must be normalized before insertion.

## Source Parser Requirements

### HDFC Bank PDF

Extract:

- Customer/account identifier.
- Statement period.
- Opening balance.
- Per-row date.
- Multi-line narration.
- Withdrawal.
- Deposit.
- Closing balance.
- UPI/payment reference where available.
- Payment channel inferred from narration prefix.

### Kotak Bank PDF

Extract:

- Account number/masked identifier.
- Statement period.
- Opening and closing balance.
- Per-row date.
- Description.
- Reference number.
- Withdrawal/deposit.
- Balance.

### HDFC Card PDFs

Applies to Swiggy HDFC and Tata Neu HDFC.

Extract:

- Card name and masked card number.
- Statement date.
- Billing period.
- Total amount due.
- Per-row transaction date/time.
- Description.
- Amount.
- Whether row is debit or credit based on `+` marker.
- Payment/refund/cashback flags based on description.

### SBI Card PDFs

Extract:

- Statement period.
- Statement date.
- Payment due date.
- Card masked number.
- Transaction date.
- Description.
- Amount.
- Entry type from `C` or `D`.
- Payment/refund flags from description.

### ICICI Card PDFs

Applies to Sapphiro and MMT.

Extract:

- Statement period.
- Statement date.
- Payment due date.
- Card masked number.
- Transaction date.
- Serial number.
- Description.
- Reward points if present.
- Foreign currency amount/currency if present.
- INR amount.
- Entry type from `CR` marker.

### Zerodha XLSX

Extract:

- Period from `P&L Statement for Equity`.
- Summary charges.
- Other credit/debit.
- Realized P&L.
- Unrealized P&L.
- Symbol-level rows from the equity sheet.
- Other debits and credits sheet rows.

### Groww XLSX

Extract:

- Period from title.
- Summary realized P&L.
- Summary unrealized P&L.
- Total charges.
- Trade-level realized/unrealized rows.
- Scrip-level realized/unrealized rows.

## Import Flow

1. User uploads PDF/XLSX.
2. App calculates file SHA-256.
3. App auto-detects source if possible; otherwise user selects source.
4. If PDF is encrypted, app asks for password.
5. Parser extracts structured preview.
6. App shows:
   - source/institution/account
   - statement period
   - row count
   - total debits/spends
   - total credits/payments
   - ending balance/P&L where available
   - parser warnings
7. User confirms import.
8. App inserts into SQLite inside one transaction.
9. App stores original filename and file hash, but not decrypted PDF contents.

## Duplicate Protection

Use three levels:

1. Exact file duplicate: `file_sha256`.
2. Statement duplicate: same institution, account, period, source kind.
3. Row duplicate: per-row `dedupe_key`.

On duplicate import, preview should show rows as:

- `new`
- `duplicate`
- `conflict`

## Dashboard Metrics V1

### Net Worth

- Latest bank balances by account.
- Broker current value from holdings.
- Manual assets.
- Manual liabilities.
- Total net worth.

### Spending

- Monthly total card debits excluding payments/refunds.
- Monthly bank withdrawals excluding obvious self/card payments where rules are available.
- UPI spend from bank statement and Tata Neu UPI card rows.
- Card-wise spend.

### Double-Counting Rules

Credit card bill payments often appear twice:

1. As actual spends inside the card statement.
2. As a bank withdrawal when the credit card bill is paid.

The dashboard must not count both as expenses.

Use this treatment:

- If a credit card statement is imported for a period, card transaction debits are the source of card spend.
- The matching bank debit used to pay that card bill is treated as a transfer/settlement, not spend.
- If a card statement is not imported yet, the bank debit for that card bill may be used as a temporary card-spend proxy.
- Once the actual card statement is imported, replace the proxy spend with card transaction spend.

Bank transactions should therefore support a derived classification:

| Classification | Meaning |
| --- | --- |
| `expense` | Real bank spend, such as UPI or direct debit. |
| `card_settlement` | Bank payment toward a credit card bill. Excluded from spend when the card statement exists. |
| `self_transfer` | Movement between own accounts. Excluded from spend/income. |
| `investment_transfer` | Transfer to/from broker or mutual fund platform. Excluded from daily spend. |
| `income_candidate` | Bank credit that may correspond to manual income tagging. |

For Phase 1, card settlement detection should use narration rules such as `CRED`, `CC PAYMENT`, `CREDIT CARD`, `BBPS`, card account identifiers, and known payment amounts from imported card statements.

### Income

- Manual income total.
- Income by `source_name`.
- Month-on-month income by source.

### Investments

- Broker-wise realized P&L.
- Broker-wise unrealized P&L.
- Total charges.
- Holdings value.

### Subscriptions

Detect recurring candidates from card transactions:

- Same normalized merchant/description.
- Appears in at least two billing periods, or matches subscription keywords.
- Keywords: `SUBSCRIPTION`, `APPLE`, `AWS`, `LINKEDIN`, `CLAUDE`, `NETFLIX`, `SPOTIFY`, `GOOGLE`, `MICROSOFT`.

## Proposed App Architecture

### Backend

- Python FastAPI.
- SQLite.
- SQLAlchemy or SQLModel.
- Parser modules under `app/parsers`.
- Service layer for imports and dashboard calculations.

### Frontend

- React + Vite.
- Dashboard-first interface.
- Import page with preview/confirm.
- Manual income/assets forms.
- Charts with Recharts.

### Local Storage

- SQLite database in project data directory.
- Uploaded source files are read during import and discarded by default.
- Optional later setting: retain original PDFs in encrypted local storage.

## Implementation Order

1. Create backend/frontend skeleton.
2. Add Python dependencies, including PDF AES support.
3. Create SQLite schema and migrations/init script.
4. Implement parser contract types.
5. Implement HDFC bank parser.
6. Implement import preview API.
7. Implement import confirmation and duplicate protection.
8. Implement HDFC card parser.
9. Implement SBI card parser.
10. Implement ICICI card parser.
11. Implement Kotak bank parser.
12. Implement Zerodha and Groww XLSX parsers.
13. Build dashboard summary API.
14. Build dashboard UI.
15. Add manual income/assets screens.

## First Build Target

The first end-to-end slice should be:

1. HDFC bank PDF upload.
2. Password input.
3. Parse preview with row count, withdrawals, deposits, and closing balance.
4. Confirm import into SQLite.
5. Dashboard card showing HDFC account balance and monthly UPI spend.

This proves the hardest parts early: encrypted PDF handling, multi-line statement row parsing, normalization, storage, and dashboard calculation.
