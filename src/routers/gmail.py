from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
import logging

from config import settings
from utils.database import get_db
from agents.tracking_agent import TrackingAgent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gmail & followups"])


# ============================================
# Gmail Integration
# ============================================

@router.post("/api/gmail/authenticate")
async def authenticate_gmail() -> Dict[str, Any]:
    """Authenticate with Gmail API"""
    try:
        from utils.gmail_helper import gmail_helper

        success = gmail_helper.authenticate()
        return {
            "success": success,
            "message": "Gmail authenticated" if success else "Authentication failed",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/gmail/check-responses")
async def check_email_responses(
    user_id: int,
    days: int = 7,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Check Gmail for responses"""
    try:
        from utils.gmail_helper import gmail_helper

        emails = gmail_helper.get_recent_emails(days=days)

        interviews = sum(1 for e in emails if e.get("response_type") == "interview")
        offers = sum(1 for e in emails if e.get("response_type") == "offer")
        rejections = sum(1 for e in emails if e.get("response_type") == "rejection")

        return {
            "success": True,
            "emails_checked": len(emails),
            "interviews": interviews,
            "offers": offers,
            "rejections": rejections,
        }
    except Exception as e:
        logger.error(f"Error checking email: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# Daily Summary
# ============================================

@router.get("/api/daily-summary/{user_id}")
async def get_daily_summary(
    user_id: int,
    date: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Generate daily summary report"""
    try:
        from daily_summary import DailySummaryGenerator

        generator = DailySummaryGenerator(
            user_email=settings.gmail_address or "your_email@gmail.com",
            app_password=settings.gmail_app_password or "",
        )

        report = generator.generate_daily_report(user_id, date)
        return report
    except Exception as e:
        logger.error(f"Error generating daily summary: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================
# Follow-ups
# ============================================

@router.post("/api/applications/{application_id}/schedule-followup")
async def schedule_followup(
    application_id: int,
    days: int = 7,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Schedule follow-up for application"""
    try:
        tracking_agent = TrackingAgent(db)
        result = tracking_agent.schedule_followup(
            application_id=application_id,
            days_from_now=days,
            notes=notes,
        )
        return result
    except Exception as e:
        logger.error(f"Error scheduling followup: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/followups/{user_id}/pending")
async def get_pending_followups(
    user_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get all pending follow-ups"""
    try:
        tracking_agent = TrackingAgent(db)
        followups = tracking_agent.get_pending_followups(
            user_id=user_id,
            days=1,
        )
        return {
            "success": True,
            "pending_followups": len(followups),
            "applications": followups,
        }
    except Exception as e:
        logger.error(f"Error getting pending followups: {e}")
        raise HTTPException(status_code=400, detail=str(e))
