from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

from utils.database import get_db
from agents.writing_agent import WritingAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/writing", tags=["writing"])


class AnswerCreate(BaseModel):
    question: str
    answer: str
    question_type: str = "custom"
    skill_tags: List[str] = []
    quality_score: Optional[float] = None
    star_format: bool = False
    has_quantified_results: bool = False


class AnswerUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    question_type: Optional[str] = None
    skill_tags: Optional[List[str]] = None
    quality_score: Optional[float] = None
    star_format: Optional[bool] = None
    has_quantified_results: Optional[bool] = None


@router.get("/answers/{user_id}")
async def list_answers(
    user_id: int,
    question_type: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all saved answers for a user"""
    try:
        from utils.database import ApprovedAnswer
        q = db.query(ApprovedAnswer).filter(ApprovedAnswer.user_id == user_id)
        if question_type:
            q = q.filter(ApprovedAnswer.question_type == question_type)
        answers = q.order_by(ApprovedAnswer.times_used.desc()).all()
        result = [_serialize_answer(a) for a in answers]
        return {"answers": result, "total": len(result)}
    except Exception as e:
        logger.error(f"Error listing answers: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/answers/improve")
async def improve_answer(
    answer: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Improve an answer using AI (STAR formatting)"""
    try:
        from agents.answer_memory_agent import AnswerMemoryAgent
        agent = AnswerMemoryAgent(db)
        improved = await agent.format_to_star(answer)
        return {"improved": improved}
    except Exception as e:
        logger.error(f"Error improving answer: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/answers/{user_id}")
async def create_answer(
    user_id: int,
    body: AnswerCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Save a new answer to the memory bank"""
    try:
        from utils.database import ApprovedAnswer
        from datetime import datetime
        answer = ApprovedAnswer(
            user_id=user_id,
            question=body.question,
            answer=body.answer,
            question_type=body.question_type,
            skill_tags=body.skill_tags,
            quality_score=body.quality_score,
            star_format=body.star_format,
            has_quantified_results=body.has_quantified_results,
        )
        db.add(answer)
        db.commit()
        db.refresh(answer)
        return _serialize_answer(answer)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating answer: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/answers/{answer_id}")
async def update_answer(
    answer_id: int,
    body: AnswerUpdate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update an existing answer"""
    try:
        from utils.database import ApprovedAnswer
        from datetime import datetime
        answer = db.query(ApprovedAnswer).filter(ApprovedAnswer.id == answer_id).first()
        if not answer:
            raise HTTPException(status_code=404, detail="Answer not found")
        for field, val in body.dict(exclude_none=True).items():
            setattr(answer, field, val)
        answer.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(answer)
        return _serialize_answer(answer)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating answer: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/answers/{answer_id}")
async def delete_answer(
    answer_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete an answer from memory"""
    try:
        from utils.database import ApprovedAnswer
        answer = db.query(ApprovedAnswer).filter(ApprovedAnswer.id == answer_id).first()
        if not answer:
            raise HTTPException(status_code=404, detail="Answer not found")
        db.delete(answer)
        db.commit()
        return {"deleted": True, "id": answer_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting answer: {e}")
        raise HTTPException(status_code=400, detail=str(e))


def _serialize_answer(a) -> Dict[str, Any]:
    return {
        "id": a.id,
        "question": a.question,
        "answer": a.answer,
        "question_type": a.question_type or "custom",
        "skill_tags": a.skill_tags or [],
        "quality_score": a.quality_score,
        "readability_score": a.readability_score,
        "relevance_score": a.relevance_score,
        "star_format": bool(a.star_format),
        "has_quantified_results": bool(a.has_quantified_results),
        "times_used": a.times_used or 0,
        "interviews_generated": a.interviews_generated or 0,
        "offers_generated": a.offers_generated or 0,
        "success_rate": a.success_rate or 0.0,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "last_used": a.last_used.isoformat() if a.last_used else None,
    }


@router.post("/cover-letter")
async def generate_cover_letter(
    user_id: int,
    job_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Generate personalized cover letter"""
    try:
        writing_agent = WritingAgent(db)
        result = await writing_agent.generate_cover_letter(
            user_id=user_id,
            job_id=job_id,
        )
        return result
    except Exception as e:
        logger.error(f"Error generating cover letter: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/form-answers")
async def generate_form_answers(
    user_id: int,
    job_id: int,
    questions: List[str],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Generate answers to form questions"""
    try:
        writing_agent = WritingAgent(db)
        result = await writing_agent.generate_form_answers(
            user_id=user_id,
            job_id=job_id,
            questions=questions,
        )
        return result
    except Exception as e:
        logger.error(f"Error generating form answers: {e}")
        raise HTTPException(status_code=400, detail=str(e))
@router.post("/answers/improve-legacy")
async def improve_answer_legacy(
    answer: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Improve an answer using AI (STAR formatting)"""
    try:
        from agents.answer_memory_agent import AnswerMemoryAgent
        agent = AnswerMemoryAgent(db)
        improved = await agent.format_to_star(answer)
        return {"improved": improved}
    except Exception as e:
        logger.error(f"Error improving answer: {e}")
        raise HTTPException(status_code=400, detail=str(e))
