import hashlib
import os
import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.models import ManualAsset, new_id, utc_now
from app.parsers.base import ParsedStatement
from app.services.accounts_overview import get_accounts_overview
from app.services.dashboard import get_summary
from app.services.data_flags import get_data_flags
from app.services.expenses import get_expenses_summary
from app.services.import_confirm import confirm_import
from app.services.import_preview import preview_import
from app.services.income import get_income_summary
from app.services.networth import get_networth_summary

app = FastAPI(title="Personal Finance Dashboard")

# ALLOWED_ORIGINS = comma-separated list of frontend URLs.
# In dev this defaults to * so the Vite proxy works without config.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
_origins = [o.strip() for o in _raw_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConfirmImportRequest(BaseModel):
    file_sha256: str
    original_filename: str
    parsed: ParsedStatement


class ManualAssetRequest(BaseModel):
    name: str
    kind: str  # "asset" | "liability"
    value: float
    date: str   # ISO date string YYYY-MM-DD
    notes: str | None = None


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/imports/sources")
def imports_sources():
    from app.services.import_preview import list_sources
    return list_sources()


@app.post("/imports/preview")
async def imports_preview(
    source: str = Form(...),
    password: str | None = Form(default=None),
    file: UploadFile = File(...),
):
    content = await file.read()
    file_sha256 = hashlib.sha256(content).hexdigest()

    suffix = Path(file.filename or "").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix) as temp_file:
        temp_file.write(content)
        temp_file.flush()
        try:
            parsed = preview_import(Path(temp_file.name), source, password)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Import preview failed: {exc}") from exc

    return {
        "file_sha256": file_sha256,
        "source": source,
        "parsed": parsed.model_dump(mode="json"),
    }


@app.get("/accounts/overview")
def accounts_overview(db: Session = Depends(get_db)):
    return get_accounts_overview(db)


@app.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    return get_summary(db)


@app.get("/dashboard/networth")
def dashboard_networth(db: Session = Depends(get_db)):
    return get_networth_summary(db)


@app.get("/dashboard/income")
def dashboard_income(db: Session = Depends(get_db)):
    return get_income_summary(db)


@app.get("/dashboard/expenses")
def dashboard_expenses(db: Session = Depends(get_db)):
    return get_expenses_summary(db)


@app.get("/dashboard/data-flags")
def dashboard_data_flags(db: Session = Depends(get_db)):
    return get_data_flags(db)


@app.get("/manual-assets")
def list_manual_assets(db: Session = Depends(get_db)):
    rows = db.query(ManualAsset).order_by(ManualAsset.date.desc()).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "kind": r.kind,
            "value": r.value,
            "date": str(r.date),
            "notes": r.notes,
        }
        for r in rows
    ]


@app.get("/manual-assets/effective")
def effective_manual_assets(month: str, db: Session = Depends(get_db)):
    """Returns the effective (most recent) asset snapshot for a given YYYY-MM month."""
    from calendar import monthrange
    from datetime import date as date_type
    try:
        year, mo = map(int, month.split("-"))
        month_end = date_type(year, mo, monthrange(year, mo)[1])
        month_start = date_type(year, mo, 1)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="month must be YYYY-MM")

    rows = db.query(ManualAsset).filter(ManualAsset.date <= month_end).all()
    latest: dict[str, ManualAsset] = {}
    for r in rows:
        if r.name not in latest or r.date > latest[r.name].date:
            latest[r.name] = r

    return [
        {
            "id": r.id,
            "name": r.name,
            "kind": r.kind,
            "value": r.value,
            "date": str(r.date),
            "notes": r.notes,
            "is_recurring": r.date < month_start,
        }
        for r in sorted(latest.values(), key=lambda x: x.date, reverse=True)
    ]


@app.post("/manual-assets")
def create_manual_asset(body: ManualAssetRequest, db: Session = Depends(get_db)):
    from datetime import date as date_type
    entry = ManualAsset(
        id=new_id(),
        name=body.name,
        kind=body.kind,
        value=body.value,
        date=date_type.fromisoformat(body.date),
        notes=body.notes,
        created_at=utc_now(),
    )
    db.add(entry)
    db.commit()
    return {"id": entry.id, "status": "created"}


@app.put("/manual-assets/{asset_id}")
def update_manual_asset(asset_id: str, body: ManualAssetRequest, db: Session = Depends(get_db)):
    from datetime import date as date_type
    entry = db.query(ManualAsset).filter_by(id=asset_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Asset not found")
    entry.name = body.name
    entry.kind = body.kind
    entry.value = body.value
    entry.date = date_type.fromisoformat(body.date)
    entry.notes = body.notes
    db.commit()
    return {"id": entry.id, "status": "updated"}


@app.delete("/manual-assets/{asset_id}")
def delete_manual_asset(asset_id: str, db: Session = Depends(get_db)):
    entry = db.query(ManualAsset).filter_by(id=asset_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Asset not found")
    db.delete(entry)
    db.commit()
    return {"status": "deleted"}


@app.post("/imports/confirm")
def imports_confirm(body: ConfirmImportRequest, db: Session = Depends(get_db)):
    try:
        return confirm_import(db, body.parsed, body.file_sha256, body.original_filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Import failed: {exc}") from exc
