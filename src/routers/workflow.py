from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from sqlalchemy.orm import Session
import logging

from utils.database import get_db, User, Job
from utils.discovery_store import discovery_store
from agents.match_agent import MatchAgent
from agents.resume_agent import ResumeAgent
from agents.writing_agent import WritingAgent
from agents.tracking_agent import TrackingAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


@router.post("/process-single-application")
async def process_single_application(
    user_id: int,
    job_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Process single job application (MVP - user controls everything)
    """
    try:
        logger.info(f"Processing application for user {user_id}, job {job_id}")

        # Initialize agents
        match_agent = MatchAgent(db)
        resume_agent = ResumeAgent(db)
        writing_agent = WritingAgent(db)
        tracking_agent = TrackingAgent(db)

        llm_warnings = []

        # Step 1: Calculate match (gracefully handle missing API keys)
        match_score = 0.0
        recommendation = "UNKNOWN"
        resume_ats_score = None
        cover_letter_quality = None

        try:
            match_result = await match_agent.calculate_match(user_id, job_id)
            if match_result.get("success"):
                match_score = match_result.get("match_score", 0)
                recommendation = match_result.get("recommendation", "UNKNOWN")
            else:
                llm_warnings.append(match_result.get("message", "Match calculation failed"))
        except Exception as e:
            llm_warnings.append(f"Match skipped: {str(e)[:80]}")

        # Step 2: Customize resume (skip gracefully if LLM unavailable)
        try:
            resume_result = await resume_agent.customize_resume(
                user_id=user_id, job_id=job_id, mode="balanced"
            )
            resume_ats_score = resume_result.get("ats_score")
        except Exception as e:
            llm_warnings.append(f"Resume customization skipped: {str(e)[:80]}")

        # Step 3: Generate cover letter (skip gracefully if LLM unavailable)
        try:
            cover_letter = await writing_agent.generate_cover_letter(
                user_id=user_id, job_id=job_id
            )
            cover_letter_quality = cover_letter.get("quality_score")
        except Exception as e:
            llm_warnings.append(f"Cover letter skipped: {str(e)[:80]}")

        # Step 4: Always create application record (even if LLM failed)
        app_result = tracking_agent.create_application(
            user_id=user_id,
            job_id=job_id,
            match_score=match_score,
        )

        if not app_result.get("success"):
            raise HTTPException(status_code=400, detail=app_result.get("message", "Failed to save application"))

        job = db.query(Job).filter(Job.id == job_id).first()
        if job and job.job_url:
            discovery_store.mark_applied_by_url(job.job_url, user_id=user_id)

        msg = "Application saved. Visit job site to submit manually."
        if llm_warnings:
            msg = "Application saved (AI steps skipped — configure API keys in .env for full AI processing)."

        return {
            "success": True,
            "application_id": app_result.get("application_id"),
            "tracking_id": app_result.get("tracking_id"),
            "match_score": match_score,
            "recommendation": recommendation,
            "resume_ats_score": resume_ats_score,
            "cover_letter_quality": cover_letter_quality,
            "llm_warnings": llm_warnings,
            "next_steps": "Visit job URL and submit application manually",
            "message": msg,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing application: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch-process")
async def process_batch_applications(
    user_id: int,
    job_ids: List[int],
    phase: str = "phase2",
) -> Dict[str, Any]:
    """Process batch of applications"""
    try:
        from batch_applications import run_batch_processing

        result = await run_batch_processing(
            user_id=user_id,
            job_ids=job_ids,
            phase=phase,
        )
        return result
    except Exception as e:
        logger.error(f"Error processing batch: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/interview-prep")
async def generate_interview_prep(
    user_id: int,
    job_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Generate interview preparation pack"""
    try:
        from utils.interview_prep_helper import interview_prep_helper

        user = db.query(User).filter(User.id == user_id).first()
        job = db.query(Job).filter(Job.id == job_id).first()

        if not user or not job:
            raise HTTPException(status_code=404, detail="User or job not found")

        result = await interview_prep_helper.generate_interview_prep_pack(
            user_name=user.name,
            company_name=job.company_name,
            job_title=job.job_title,
            user_skills=user.skills or {},
            job_requirements=job.required_skills or {},
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating interview prep: {e}")
        raise HTTPException(status_code=400, detail=str(e))
