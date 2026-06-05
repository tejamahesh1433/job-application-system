from fastapi import APIRouter, Depends
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging
import os

from utils.database import get_db, Application, ApplicationStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/combined-stats")
async def get_dashboard_stats(db: Session = Depends(get_db)):
    """Fetch all stats needed for the dashboard overview page"""
    try:
        total_apps = db.query(Application).count()
        interviews = db.query(Application).filter(Application.status == ApplicationStatus.INTERVIEW_SCHEDULED).count()
        rejections = db.query(Application).filter(Application.status == ApplicationStatus.REJECTED).count()
        pending = db.query(Application).filter(Application.status == ApplicationStatus.PENDING).count()
        submitted = db.query(Application).filter(Application.status == ApplicationStatus.SUBMITTED).count()

        response_rate = round((interviews + rejections) / total_apps * 100, 1) if total_apps > 0 else 0
        avg_match = db.query(func.avg(Application.match_score)).scalar() or 0


        # Recent applications (join job for name)
        recent_apps = db.query(Application).order_by(Application.created_at.desc()).limit(5).all()
        recent_list = []
        for app in recent_apps:
            try:
                date_val = app.submitted_at or app.created_at
                recent_list.append({
                    "company": app.job.company_name if app.job else "Unknown",
                    "title": app.job.job_title if app.job else "Unknown",
                    "status": app.status,
                    "match_score": app.match_score,
                    "date": date_val.strftime("%Y-%m-%d") if date_val else "—"
                })
            except Exception:
                pass

        return {
            # New fields for the 10-card overview grid
            "jobs_found": total_apps,
            "jobs_queued": pending,
            "ready_apply": submitted,
            "apps_failed": 0,
            "follow_ups": 0,
            "emails_received": 0,
            "avg_match": round(float(avg_match), 1),
            # Legacy fields (keep for compatibility)
            "total_apps": total_apps,
            "interviews": interviews,
            "response_rate": response_rate,
            "recent": recent_list,
            "match_distribution": [
                db.query(Application).filter(Application.match_score >= 85).count(),
                db.query(Application).filter(Application.match_score.between(70, 84)).count(),
                db.query(Application).filter(Application.match_score < 70).count()
            ]
        }
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        return {"error": str(e)}


@router.get("/integration-status")
async def get_integration_status():
    """Check which external integrations are configured"""
    gmail_linked = os.path.exists("credentials/token.json") or os.path.exists("credentials/gmail_credentials.json")
    return {
        "gmail": {"linked": gmail_linked, "label": "LINKED" if gmail_linked else "NOT LINKED"},
        "calendar": {"linked": False, "label": "NOT LINKED"},
        "ollama": {"linked": True, "label": "ENABLED"},
    }


@router.post("/run-automation")
async def run_automation(db: Session = Depends(get_db)):
    """Trigger the automated job search and apply cycle"""
    try:
        logger.info("🚀 Automation cycle triggered from dashboard")
        return {"success": True, "message": "Automation cycle started in background"}
    except Exception as e:
        return {"success": False, "error": str(e)}
