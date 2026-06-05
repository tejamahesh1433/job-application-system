"""
Job Vault API — view, update, and export every discovered job.
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import io

from utils.discovery_store import discovery_store, ALL_STATUSES

router = APIRouter(prefix="/api/vault", tags=["vault"])


class StatusUpdate(BaseModel):
    status: str
    notes: str = ""
    user_id: int = 1


class NotesUpdate(BaseModel):
    notes: str
    user_id: int = 1


@router.get("")
def get_vault(
    status: Optional[str] = Query(None, description="Filter by status, or 'all'"),
    user_id: int = 1,
):
    """Return all jobs in the vault, optionally filtered by status."""
    jobs = discovery_store.vault_list(user_id=user_id, status_filter=status or "all")
    counts = discovery_store.vault_counts(user_id=user_id)
    return {
        "success": True,
        "total": len(jobs),
        "counts": counts,
        "statuses": ALL_STATUSES,
        "jobs": jobs,
    }


@router.get("/counts")
def get_counts(user_id: int = 1):
    """Return just the counts per status (for navbar badge updates)."""
    counts = discovery_store.vault_counts(user_id=user_id)
    return {"success": True, "counts": counts}


@router.put("/{job_id}/status")
def update_status(job_id: str, body: StatusUpdate):
    """Update a job's status (active/applied/interview/offer/rejected/ghosted/removed)."""
    if body.status not in ALL_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(ALL_STATUSES)}"
        )
    job = discovery_store.update_status(
        job_id=job_id,
        status=body.status,
        user_id=body.user_id,
        notes=body.notes,
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found in vault")
    return {"success": True, "job": job}


@router.put("/{job_id}/notes")
def update_notes(job_id: str, body: NotesUpdate):
    """Update notes for a job without changing its status."""
    ok = discovery_store.update_notes(
        job_id=job_id,
        notes=body.notes,
        user_id=body.user_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Job not found in vault")
    return {"success": True}


@router.get("/export/csv")
def export_csv(user_id: int = 1):
    """Download all vault jobs as a CSV file."""
    csv_str = discovery_store.export_csv(user_id=user_id)
    return StreamingResponse(
        io.StringIO(csv_str),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=job_vault.csv"},
    )


@router.get("/export/excel")
def export_excel(user_id: int = 1):
    """Download all vault jobs as an Excel file."""
    try:
        xlsx_bytes = discovery_store.export_excel_bytes(user_id=user_id)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=job_vault.xlsx"},
    )
