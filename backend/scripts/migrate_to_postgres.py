"""
Migrate all data from the local SQLite file to a Postgres database.

Usage:
    POSTGRES_URL="postgresql://user:pass@host:5432/dbname" \
    PYTHONPATH=backend python backend/scripts/migrate_to_postgres.py

The script is safe to re-run — it uses INSERT ... ON CONFLICT DO NOTHING so
existing rows are skipped rather than erroring or duplicating.
"""
import os
import sys
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
SQLITE_PATH = REPO_ROOT / "data" / "finance.sqlite3"

POSTGRES_URL = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL", "")
if not POSTGRES_URL:
    sys.exit("ERROR: set POSTGRES_URL or DATABASE_URL to the target Postgres connection string.")

if POSTGRES_URL.startswith("postgres://"):
    POSTGRES_URL = POSTGRES_URL.replace("postgres://", "postgresql://", 1)

if not SQLITE_PATH.exists():
    sys.exit(f"ERROR: SQLite file not found at {SQLITE_PATH}")

# ── Engines ────────────────────────────────────────────────────────────────
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sqlite_engine  = create_engine(f"sqlite:///{SQLITE_PATH}", connect_args={"check_same_thread": False})
pg_engine      = create_engine(POSTGRES_URL)

SqliteSession  = sessionmaker(bind=sqlite_engine)
PgSession      = sessionmaker(bind=pg_engine)

# ── Schema ─────────────────────────────────────────────────────────────────
sys.path.insert(0, str(REPO_ROOT / "backend"))
os.environ["DATABASE_URL"] = POSTGRES_URL          # point init_db at Postgres
from app.database import Base                       # noqa: E402
from app import models                              # noqa: E402, F401 — registers all tables

print("Creating schema in Postgres (if tables don't exist)…")
Base.metadata.create_all(bind=pg_engine)
print("Schema ready.\n")

# ── Table copy order (respects FK dependencies) ───────────────────────────
TABLE_ORDER = [
    "import_batches",
    "accounts",
    "bank_transactions",
    "card_transactions",
    "broker_pnl",
    "broker_holdings",
    "income_entries",
    "manual_assets",
]

# ── Copy ───────────────────────────────────────────────────────────────────
with sqlite_engine.connect() as src, pg_engine.connect() as dst:
    for table in TABLE_ORDER:
        rows = src.execute(text(f"SELECT * FROM {table}")).mappings().all()
        if not rows:
            print(f"  {table}: 0 rows (skipped)")
            continue

        cols = list(rows[0].keys())
        placeholders = ", ".join(f":{c}" for c in cols)
        col_list     = ", ".join(cols)
        stmt = text(
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
            f"ON CONFLICT DO NOTHING"
        )

        inserted = 0
        for row in rows:
            result = dst.execute(stmt, dict(row))
            inserted += result.rowcount

        dst.commit()
        print(f"  {table}: {len(rows)} rows read → {inserted} inserted ({len(rows) - inserted} skipped as duplicates)")

print("\nMigration complete.")
