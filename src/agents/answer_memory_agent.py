"""
Answer Memory Agent - Store and retrieve high-quality application answers
Uses semantic matching and success-based ranking to improve application quality
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from sqlalchemy.orm import Session
from utils.database import ApprovedAnswer, Application
from utils.llm_helper import generate_text, generate_json, USE_HAIKU, USE_OLLAMA

logger = logging.getLogger(__name__)


class AnswerMemoryAgent:
    """Manages the lifecycle and retrieval of approved application answers"""

    def __init__(self, db: Session):
        self.db = db

    async def get_best_answer(
        self, 
        question: str, 
        user_id: int, 
        threshold: float = 0.8
    ) -> Optional[Dict[str, Any]]:
        """
        Find the most relevant and successful answer for a question
        
        Returns: {
            "answer": "...",
            "similarity": 0.95,
            "success_rate": 0.8,
            "original_question": "..."
        }
        """
        
        # Get all approved answers for user
        approved_answers = self.db.query(ApprovedAnswer).filter(
            ApprovedAnswer.user_id == user_id
        ).all()
        
        if not approved_answers:
            return None
            
        # Semantic search using LLM (can be replaced with pgvector/embeddings)
        questions_list = [a.question for a in approved_answers]
        
        prompt = f"""
        Compare the "New Question" with the list of "Existing Questions".
        Identify if any existing question is semantically equivalent.
        
        New Question: {question}
        Existing Questions:
        {chr(10).join([f"{i}. {q}" for i, q in enumerate(questions_list)])}
        
        Return JSON: {{"index": -1, "similarity": 0}} or {{"index": 0, "similarity": 0.95}}
        """
        
        try:
            result = await generate_json(prompt, provider=USE_OLLAMA)
            idx = result.get("index", -1)
            similarity = result.get("similarity", 0)
            
            if idx != -1 and 0 <= idx < len(approved_answers) and similarity >= threshold:
                match = approved_answers[idx]
                return {
                    "answer": match.answer,
                    "similarity": similarity,
                    "success_rate": match.success_rate,
                    "original_question": match.question,
                    "id": match.id
                }
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            
        return None

    async def store_approved_answer(
        self,
        user_id: int,
        question: str,
        answer: str,
        question_type: str = "form_field",
        tags: List[str] = None
    ) -> bool:
        """Store a new high-quality answer in memory"""
        
        try:
            # Check for existing
            existing = self.db.query(ApprovedAnswer).filter(
                ApprovedAnswer.user_id == user_id,
                ApprovedAnswer.question == question
            ).first()
            
            if existing:
                existing.answer = answer
                existing.updated_at = datetime.utcnow()
            else:
                new_answer = ApprovedAnswer(
                    user_id=user_id,
                    question=question,
                    answer=answer,
                    question_type=question_type,
                    skill_tags=list(tags) if tags else [],
                    quality_score=self._calculate_quality(answer)
                )
                self.db.add(new_answer)
                
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Error storing answer: {e}")
            return False

    async def format_to_star(self, raw_text: str) -> str:
        """Convert an experience description into STAR format"""
        
        prompt = f"""
        Reformat the following experience into a clear STAR (Situation, Task, Action, Result) structure.
        Ensure the Result section includes quantifiable metrics if possible.
        
        Input: {raw_text}
        
        Return the formatted text only.
        """
        
        return await generate_text(prompt, provider=USE_OLLAMA)

    def _calculate_quality(self, answer: str) -> float:
        """Heuristic-based quality scoring"""
        score = 50.0
        
        # Length check
        words = len(answer.split())
        if 50 < words < 200:
            score += 20
            
        # Metric check
        if any(char.isdigit() for char in answer):
            score += 15
            
        # STAR indicator check
        indicators = ["result", "achieved", "led to", "increased", "decreased"]
        if any(ind in answer.lower() for ind in indicators):
            score += 15
            
        return min(100.0, score)

    def update_success_metrics(self, answer_id: int, interviewed: bool):
        """Update success rate based on outcome"""
        answer = self.db.query(ApprovedAnswer).filter(ApprovedAnswer.id == answer_id).first()
        if answer:
            answer.times_used += 1
            if interviewed:
                # Simple moving average for success rate
                current_success = answer.success_rate or 0
                answer.success_rate = (current_success * (answer.times_used - 1) + 1) / answer.times_used
            self.db.commit()
