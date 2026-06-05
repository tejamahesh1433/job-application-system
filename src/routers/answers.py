from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
import logging
from datetime import datetime

from utils.database import get_db, ApprovedAnswer
from agents.writing_agent import WritingAgent
from agents.answer_memory_agent import AnswerMemoryAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/answers", tags=["answers"])

@router.get("/{user_id}")
async def get_answers(
    user_id: int,
    category: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "performance",  # performance, recent, used
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get saved answers for user with filtering"""
    try:
        query = db.query(ApprovedAnswer).filter(ApprovedAnswer.user_id == user_id)
        
        if category and category != "All Answers":
            query = query.filter(ApprovedAnswer.category == category)
            
        if search:
            query = query.filter(
                or_(
                    ApprovedAnswer.question.ilike(f"%{search}%"),
                    ApprovedAnswer.answer.ilike(f"%{search}%"),
                    ApprovedAnswer.category.ilike(f"%{search}%")
                )
            )
            
        if sort_by == "performance":
            query = query.order_by(desc(ApprovedAnswer.success_rate), desc(ApprovedAnswer.quality_score))
        elif sort_by == "recent":
            query = query.order_by(desc(ApprovedAnswer.updated_at))
        elif sort_by == "used":
            query = query.order_by(desc(ApprovedAnswer.times_used))
            
        answers = query.all()
        
        serialized = []
        for a in answers:
            answer_text = a.answer or ""
            serialized.append(
                {
                    "id": a.id,
                    "question": a.question or "",
                    "answer_preview": answer_text[:200] + "..." if len(answer_text) > 200 else answer_text,
                    "answer": answer_text,
                    "question_type": a.question_type or a.category or "custom",
                    "category": a.category,
                    "role_type": a.role_type,
                    "times_used": a.times_used or 0,
                    "success_rate": round((a.success_rate or 0) * 100, 1),
                    "quality_score": a.quality_score,
                    "readability_score": a.readability_score,
                    "relevance_score": a.relevance_score,
                    "star_format": bool(a.star_format),
                    "has_quantified_results": bool(a.has_quantified_results),
                    "interviews_generated": a.interviews_generated or 0,
                    "offers_generated": a.offers_generated or 0,
                    "last_used": a.last_used.isoformat() if a.last_used else None,
                    "skill_tags": a.skill_tags or [],
                    "tags": a.skill_tags or [],
                    "weak_indicators": a.weak_indicators or [],
                    "recommender_notes": a.recommender_notes,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
            )

        return {
            "success": True,
            "count": len(answers),
            "answers": serialized
        }
    except Exception as e:
        logger.error(f"Error getting answers: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{user_id}/stats")
async def get_answer_stats(
    user_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get aggregate stats for answer memory"""
    try:
        answers = db.query(ApprovedAnswer).filter(ApprovedAnswer.user_id == user_id).all()
        
        if not answers:
            return {
                "total_answers": 0,
                "avg_success_rate": 0,
                "best_category": "N/A",
                "most_used": "N/A",
                "generated_today": 0
            }
            
        total = len(answers)
        avg_success = sum(a.success_rate or 0 for a in answers) / total if total > 0 else 0
        
        # Best category
        cats = {}
        for a in answers:
            if a.category:
                cats[a.category] = cats.get(a.category, 0) + 1
        best_cat = max(cats, key=cats.get) if cats else "N/A"
        
        # Most used
        most_used_answer = max(answers, key=lambda a: a.times_used or 0) if answers else None
        most_used_question = most_used_answer.question if most_used_answer and most_used_answer.question else "N/A"
        
        # Generated today
        today = datetime.utcnow().date()
        generated_today = sum(1 for a in answers if a.created_at and a.created_at.date() == today)
        
        return {
            "total_answers": total,
            "avg_success_rate": round(avg_success * 100, 1),
            "best_category": best_cat,
            "most_used": most_used_question[:50] + "..." if most_used_question != "N/A" else "N/A",
            "generated_today": generated_today
        }
    except Exception as e:
        logger.error(f"Error getting answer stats: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/save")
async def save_answer(
    data: Dict[str, Any],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Save or update an answer"""
    try:
        user_id = data.get("user_id")
        answer_id = data.get("id")
        if not user_id and not answer_id:
            raise HTTPException(status_code=400, detail="user_id is required when creating an answer")
        
        if answer_id:
            answer = db.query(ApprovedAnswer).filter(ApprovedAnswer.id == answer_id).first()
            if not answer:
                raise HTTPException(status_code=404, detail="Answer not found")
        else:
            answer = ApprovedAnswer(user_id=user_id)
            db.add(answer)
            
        answer.question = data.get("question", answer.question)
        answer.answer = data.get("answer", answer.answer)
        answer.question_type = data.get("question_type", answer.question_type)
        answer.category = data.get("category", data.get("question_type", answer.category))
        answer.role_type = data.get("role_type", answer.role_type)
        answer.skill_tags = data.get("skill_tags", data.get("tags", answer.skill_tags))
        
        # Auto-detect STAR format and quality
        writing_agent = WritingAgent(db)
        quality_score = writing_agent._score_answer(answer.answer)
        answer.quality_score = quality_score
        answer.star_format = "result" in answer.answer.lower() or "accomplished" in answer.answer.lower()
        
        db.commit()
        return {"success": True, "id": answer.id}
    except Exception as e:
        logger.error(f"Error saving answer: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/improve")
async def improve_answer(
    data: Dict[str, Any],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """AI improve an answer"""
    try:
        user_id = data.get("user_id")
        raw_answer = data.get("answer")
        question = data.get("question")
        
        writing_agent = WritingAgent(db)
        # Use writing agent to format to STAR or improve
        improved = await writing_agent.format_star_answer(raw_answer)
        
        return {
            "success": True,
            "improved_answer": improved,
            "improved": improved,
            "quality_boost": 15.5 # Mock boost value
        }
    except Exception as e:
        logger.error(f"Error improving answer: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/suggest")
async def suggest_answer(
    data: Dict[str, Any],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Suggest best answer for a question"""
    try:
        user_id = data.get("user_id")
        question = data.get("question")
        
        memory_agent = AnswerMemoryAgent(db)
        best_match = await memory_agent.get_best_answer(question, user_id)
        
        if best_match:
            return {
                "success": True,
                "found": True,
                "answer": best_match["answer"],
                "similarity": best_match["similarity"],
                "recommender_notes": f"Matches your previous answer for: {best_match['original_question']}"
            }
        else:
            return {"success": True, "found": False}
    except Exception as e:
        logger.error(f"Error suggesting answer: {e}")
        raise HTTPException(status_code=400, detail=str(e))
