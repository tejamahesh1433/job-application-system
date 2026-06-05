"""
Interview Preparation Agent - Generate personalized interview guides
Combines company research, role requirements, and user's past successful answers
"""

import logging
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session
from utils.database import User, Job
from utils.interview_prep_helper import interview_prep_helper
from agents.answer_memory_agent import AnswerMemoryAgent

logger = logging.getLogger(__name__)


class InterviewPrepAgent:
    """Orchestrates interview preparation using role context and user memory"""

    def __init__(self, db: Session):
        self.db = db
        self.memory = AnswerMemoryAgent(db)

    async def generate_prep_guide(
        self,
        user_id: int,
        job_id: int
    ) -> Dict[str, Any]:
        """Generate a complete interview prep guide"""
        
        user = self.db.query(User).filter(User.id == user_id).first()
        job = self.db.query(Job).filter(Job.id == job_id).first()
        
        if not user or not job:
            return {"success": False, "message": "User or Job not found"}
            
        # 1. Use helper for base guides
        base_pack = await interview_prep_helper.generate_interview_prep_pack(
            user_name=user.name,
            company_name=job.company_name,
            job_title=job.job_title,
            user_skills=user.skills or {},
            job_requirements=job.required_skills or {}
        )
        
        if not base_pack.get("success"):
            return base_pack
            
        # 2. Enrich with personalized successful answers from memory
        personalized_star_answers = {}
        common_questions = [
            "conflict resolution",
            "technical challenge",
            "leadership",
            "problem solving"
        ]
        
        for q_theme in common_questions:
            best_match = await self.memory.get_best_answer(q_theme, user_id)
            if best_match:
                personalized_star_answers[q_theme] = {
                    "question": best_match["original_question"],
                    "answer": best_match["answer"],
                    "success_rate": best_match["success_rate"]
                }
                
        base_pack["personalized_star_answers"] = personalized_star_answers
        
        return base_pack
