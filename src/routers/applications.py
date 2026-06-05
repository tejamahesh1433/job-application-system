from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import logging

from utils.database import get_db
from agents.tracking_agent import TrackingAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/applications", tags=["applications"])

@router.post("/create")
async def create_application(
    user_id: int,
    job_id: int,
    match_score: float = 0.0,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create application record"""
    try:
        tracking_agent = TrackingAgent(db)
        result = tracking_agent.create_application(
            user_id=user_id,
            job_id=job_id,
            match_score=match_score,
        )
        return result
    except Exception as e:
        logger.error(f"Error creating application: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{user_id}")
async def get_applications(
    user_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get applications for user"""
    try:
        tracking_agent = TrackingAgent(db)
        apps = tracking_agent.get_applications(
            user_id=user_id,
            status=status,
        )
        return {
            "count": len(apps),
            "applications": apps,
        }
    except Exception as e:
        logger.error(f"Error getting applications: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{application_id}/status")
async def update_application_status(
    application_id: int,
    status: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update application status"""
    try:
        # Normalize: "INTERVIEW_SCHEDULED" → "interview_scheduled"
        normalized = status.lower().replace("-", "_").replace(" ", "_")
        tracking_agent = TrackingAgent(db)
        result = tracking_agent.update_application(application_id, status=normalized)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating status: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{application_id}/notes")
async def update_application_notes(
    application_id: int,
    notes: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update application notes"""
    try:
        tracking_agent = TrackingAgent(db)
        result = tracking_agent.update_application(application_id, notes=notes)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating notes: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{user_id}/stats")
async def get_application_stats(
    user_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get application statistics"""
    try:
        tracking_agent = TrackingAgent(db)
        stats = tracking_agent.get_application_stats(user_id)
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=400, detail=str(e))
