"""
Application Form Records API
Every field filled by the browser agent is stored here per company/application.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from utils.database import ApplicationFormRecord, get_db

router = APIRouter(prefix="/api/form-records", tags=["form-records"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class FormField(BaseModel):
    label: str                        # "First Name", "Years of Experience", etc.
    field_type: str = "text"          # text, email, select, textarea, checkbox, file
    section: str = "General"          # "Personal Info", "Work Experience", etc.
    question: Optional[str] = None    # Full question text if different from label
    value: str = ""                   # What was filled in
    was_auto_filled: bool = True      # False if user typed it manually


class FormRecordCreate(BaseModel):
    user_id: int = 1
    application_id: Optional[int] = None
    company_name: str
    job_title: Optional[str] = ""
    platform: Optional[str] = ""
    form_url: Optional[str] = ""
    status: str = "filled"            # filled | submitted | error
    fields: List[FormField] = []
    error_message: Optional[str] = None


def _serialize(rec: ApplicationFormRecord) -> Dict[str, Any]:
    return {
        "id":             rec.id,
        "company_name":   rec.company_name,
        "job_title":      rec.job_title or "",
        "platform":       rec.platform or "",
        "form_url":       rec.form_url or "",
        "status":         rec.status,
        "total_fields":   rec.total_fields,
        "filled_fields":  rec.filled_fields,
        "fields":         rec.fields or [],
        "error_message":  rec.error_message,
        "filled_at":      rec.filled_at.isoformat() if rec.filled_at else None,
        "application_id": rec.application_id,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
def list_form_records(
    user_id: int = 1,
    company: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List all form records, optionally filtered by company or platform."""
    q = db.query(ApplicationFormRecord).filter(ApplicationFormRecord.user_id == user_id)
    if company:
        q = q.filter(ApplicationFormRecord.company_name.ilike(f"%{company}%"))
    if platform:
        q = q.filter(ApplicationFormRecord.platform.ilike(f"%{platform}%"))
    records = q.order_by(ApplicationFormRecord.filled_at.desc()).limit(limit).all()

    # Group by company for the UI
    by_company: Dict[str, List] = {}
    for r in records:
        key = r.company_name
        by_company.setdefault(key, []).append(_serialize(r))

    return {
        "success": True,
        "total": len(records),
        "by_company": by_company,
        "records": [_serialize(r) for r in records],
    }


@router.get("/{record_id}")
def get_form_record(record_id: int, user_id: int = 1, db: Session = Depends(get_db)):
    """Get a single form record with all fields."""
    rec = db.query(ApplicationFormRecord).filter(
        ApplicationFormRecord.id == record_id,
        ApplicationFormRecord.user_id == user_id,
    ).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Form record not found")
    return {"success": True, "record": _serialize(rec)}


@router.post("")
def create_form_record(body: FormRecordCreate, db: Session = Depends(get_db)):
    """
    Called by the browser agent after filling a form.
    Stores every field with what was asked and what was filled.
    """
    fields_data = [f.dict() for f in body.fields]
    filled = sum(1 for f in fields_data if f.get("value"))

    rec = ApplicationFormRecord(
        user_id=body.user_id,
        application_id=body.application_id,
        company_name=body.company_name,
        job_title=body.job_title or "",
        platform=body.platform or "",
        form_url=body.form_url or "",
        status=body.status,
        fields=fields_data,
        total_fields=len(fields_data),
        filled_fields=filled,
        error_message=body.error_message,
        filled_at=datetime.utcnow(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"success": True, "record": _serialize(rec)}


@router.delete("/{record_id}")
def delete_form_record(record_id: int, user_id: int = 1, db: Session = Depends(get_db)):
    rec = db.query(ApplicationFormRecord).filter(
        ApplicationFormRecord.id == record_id,
        ApplicationFormRecord.user_id == user_id,
    ).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Form record not found")
    db.delete(rec)
    db.commit()
    return {"success": True}


@router.get("/stats/summary")
def form_stats(user_id: int = 1, db: Session = Depends(get_db)):
    """Summary stats for the dashboard."""
    records = db.query(ApplicationFormRecord).filter(
        ApplicationFormRecord.user_id == user_id
    ).all()
    companies = list({r.company_name for r in records})
    submitted = sum(1 for r in records if r.status == "submitted")
    return {
        "total_forms": len(records),
        "submitted": submitted,
        "companies_applied": len(companies),
        "avg_fields": round(
            sum(r.total_fields for r in records) / len(records), 1
        ) if records else 0,
    }
