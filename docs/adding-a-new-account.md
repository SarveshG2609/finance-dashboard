# Adding a New Account / Statement Type

This guide covers the end-to-end steps to integrate any new bank, credit card, or broker
into the dashboard. The only file that needs a backend change is the parser itself plus
one line in the registry.

---

## Step 1 — Write the parser

Create `backend/app/parsers/<source_id>.py`.

The file must expose a single public function:

```python
# Password-protected PDF (bank / credit card)
def parse_<source_id>_pdf(path: Path, password: str) -> ParsedStatement: ...

# No password (XLSX broker exports)
def parse_<source_id>_xlsx(path: Path) -> ParsedStatement: ...
```

### Return type contract

Return a `ParsedStatement` (from `app.parsers.base`) with:

| Field | What to put |
|---|---|
| `source_kind` | `SourceKind.BANK`, `SourceKind.CREDIT_CARD`, or `SourceKind.BROKER_PNL` |
| `institution` | Short name used as the account grouping key, e.g. `"HDFC"`, `"Axis"` |
| `account_name` | Human-readable name detected from the statement header |
| `masked_identifier` | Masked account/card number if present, else `None` |
| `statement_start` / `statement_end` | Billing / statement period as `date` objects |
| `rows` | List of typed row objects (see below) |
| `warnings` | Any parse anomalies worth surfacing to the user |

### Row types

| Statement type | Row class to use |
|---|---|
| Bank | `BankTransactionRow` |
| Credit card | `CardTransactionRow` |
| Broker P&L summary | `BrokerSummaryRow` |
| Broker holdings | `BrokerHoldingRow` |

All row classes require a `row_type` literal field (already set by default).
Import them from `app.parsers.base`.

### Tips

- **Card name detection:** only look at the first 2–3 lines of each page, never the full
  text. Offer / terms sections mention other card products by name and will give false
  matches.
- **Test the parser directly** before wiring it in:
  ```bash
  PYTHONPATH=backend python3 -c "
  from app.parsers.<source_id> import parse_<source_id>_pdf
  from pathlib import Path
  p = parse_<source_id>_pdf(Path('~/Downloads/statement.pdf'), 'password')
  print(p.account_name, len(p.rows), 'rows')
  for r in p.rows[:3]: print(r)
  "
  ```

---

## Step 2 — Register it (one line)

Open `backend/app/services/import_preview.py` and add an entry to `_REGISTRY`:

```python
from app.parsers.<source_id> import parse_<source_id>_pdf

SourceSpec(
    id          = "<source_id>",          # unique slug, lowercase, underscores
    label       = "Axis Bank – Savings",  # shown in the Import dropdown
    requires_password = True,             # False for XLSX exports
    accept      = ".pdf",                 # ".pdf" or ".xlsx"
    parser      = parse_<source_id>_pdf,
),
```

That's it. The frontend Import dropdown fetches `GET /imports/sources` on every page
load, so it picks up the new entry automatically — no frontend changes needed.

---

## Step 3 — Verify end-to-end

1. Restart the backend:
   ```bash
   PYTHONPATH=backend uvicorn app.main:app --reload
   ```
2. Open `http://localhost:5174` → Import tab.
3. The new source should appear in the dropdown.
4. Upload a real statement file, check the preview table looks correct, then confirm.
5. Open the Accounts tab and verify the new account appears with the right last-sync date.

---

## What you do NOT need to change

| File | Why untouched |
|---|---|
| `import_confirm.py` | Handles all 4 row types generically |
| `accounts_overview.py` | Queries by `account_type`, not by institution name |
| `networth.py` | Classifies holdings by ISIN / symbol, not by source |
| `ImportPage.tsx` | Sources list is fetched from the API |
| Any other frontend file | Dashboard reads from DB, not from parsers |
