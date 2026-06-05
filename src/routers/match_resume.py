from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from sqlalchemy.orm import Session
import logging

from utils.database import get_db
from agents.match_agent import MatchAgent
from agents.resume_agent import ResumeAgent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["match & resume"])


@router.post("/api/match/calculate")
async def calculate_match(
    user_id: int,
    job_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Calculate match score between user and job"""
    try:
        match_agent = MatchAgent(db)
        result = await match_agent.calculate_match(
            user_id=user_id,
            job_id=job_id,
        )
        return result
    except Exception as e:
        logger.error(f"Error calculating match: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/resume/customize")
async def customize_resume(
    user_id: int,
    job_id: int,
    mode: str = "balanced",
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Customize resume for specific job"""
    try:
        resume_agent = ResumeAgent(db)
        result = await resume_agent.customize_resume(
            user_id=user_id,
            job_id=job_id,
            mode=mode,
        )
        return result
    except Exception as e:
        logger.error(f"Error customizing resume: {e}")
        raise HTTPException(status_code=400, detail=str(e))
