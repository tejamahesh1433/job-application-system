"""
Writing Agent - Generate cover letters, form answers, and emails
Creates STAR-format answers with quality scoring
"""

import logging
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session
from utils.database import User, Job, ApprovedAnswer
from utils.document_store import write_text_document
from utils.llm_helper import generate_text, generate_json, USE_SONNET, USE_HAIKU, USE_OLLAMA
from .answer_memory_agent import AnswerMemoryAgent

logger = logging.getLogger(__name__)


class WritingAgent:
    """Generates professional writing for applications"""

    def __init__(self, db: Session):
        self.db = db
        self.memory = AnswerMemoryAgent(db)

    async def generate_cover_letter(
        self,
        user_id: int,
        job_id: int,
        personalization_level: str = "balanced",  # conservative, balanced, creative
    ) -> Dict[str, Any]:
        """
        Generate personalized cover letter

        Args:
            user_id: User ID
            job_id: Job ID
            personalization_level: How personalized the letter should be

        Returns:
            {
                "cover_letter": "Dear hiring manager...",
                "quality_score": 85,
                "has_star_format": true,
                "has_quantified_results": true,
                "success": true
            }
        """

        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            job = self.db.query(Job).filter(Job.id == job_id).first()

            if not user:
                return {"success": False, "message": "User not found"}
            if not job:
                return {"success": False, "message": "Job not found"}

            prompt = f"""
Write a professional cover letter for this job application. Keep it concise (3-4 paragraphs).

CANDIDATE:
Name: {user.name}
Current Title: {user.current_title}
Experience: {user.years_experience} years
Skills: {', '.join(list(user.skills.keys())[:5])}

JOB:
Title: {job.job_title}
Company: {job.company_name}
Description: {job.description[:500] if job.description else 'N/A'}

GUIDELINES:
1. Start with strong hook - why this specific company/role
2. Highlight 2-3 relevant achievements with numbers/metrics
3. Connect skills to job requirements
4. Show enthusiasm for the role
5. Professional tone, NOT generic
6. 250-350 words

PERSONALIZATION LEVEL: {personalization_level}
- conservative: Professional, proven format
- balanced: Personalized with specific details about company
- creative: Unique voice, storytelling approach

Do not include "Dear Hiring Manager" - just the body.
"""

            cover_letter = await generate_text(prompt, provider=USE_OLLAMA)

            # Score the letter
            quality_score = self._score_cover_letter(cover_letter, user, job)
            file_record = write_text_document(
                category="cover_letters",
                company_name=job.company_name,
                doc_type="cover_letter",
                job_title=job.job_title,
                content=cover_letter,
                metadata={
                    "user_id": user_id,
                    "job_id": job_id,
                    "quality_score": quality_score,
                },
                extension="txt",
            )

            return {
                "cover_letter": cover_letter,
                "file": file_record,
                "quality_score": round(quality_score, 1),
                "has_star_format": "accomplished" in cover_letter.lower() or "results" in cover_letter.lower(),
                "has_quantified_results": any(
                    char.isdigit() for char in cover_letter
                ),
                "success": True,
            }

        except Exception as e:
            logger.error(f"Error generating cover letter: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }

    async def generate_form_answers(
        self,
        user_id: int,
        job_id: int,
        questions: List[str],
    ) -> Dict[str, Any]:
        """
        Generate answers to common application form questions

        Args:
            user_id: User ID
            job_id: Job ID
            questions: List of form questions

        Returns:
            {
                "answers": {
                    "Why are you interested in this role?": "Answer...",
                    "Tell us about your experience with...": "Answer..."
                },
                "quality_scores": {...},
                "success": true
            }
        """

        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            job = self.db.query(Job).filter(Job.id == job_id).first()

            if not user:
                return {"success": False, "message": "User not found"}
            if not job:
                return {"success": False, "message": "Job not found"}

            answers = {}
            quality_scores = {}

            for question in questions:
                # Check if we have a semantically similar answer in memory
                remembered_answer = await self.check_answer_memory(question, user_id)

                if remembered_answer:
                    answers[question] = remembered_answer
                    quality_scores[question] = self._score_answer(remembered_answer)
                    logger.info(f"Used remembered answer for: {question}")
                else:
                    # Generate new answer
                    answer = await self._generate_answer_for_question(
                        question, user, job
                    )
                    # Optionally reformat into STAR if not already
                    if "result" not in answer.lower():
                        answer = await self.format_star_answer(answer)
                        
                    answers[question] = answer
                    quality_scores[question] = self._score_answer(answer)

            return {
                "answers": answers,
                "quality_scores": quality_scores,
                "average_quality": round(
                    sum(quality_scores.values()) / len(quality_scores) if quality_scores else 0, 1
                ),
                "success": True,
            }

        except Exception as e:
            logger.error(f"Error generating form answers: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }

    async def _generate_answer_for_question(
        self,
        question: str,
        user: User,
        job: Job,
    ) -> str:
        """Generate answer to specific question using STAR format"""

        prompt = f"""
Answer this job application question in 3-4 sentences. Use STAR format if applicable.

QUESTION: {question}

CANDIDATE CONTEXT:
Name: {user.name}
Title: {user.current_title}
Experience: {user.years_experience} years
Skills: {', '.join(list(user.skills.keys())[:5])}

JOB CONTEXT:
Role: {job.job_title}
Company: {job.company_name}
Required Skills: {', '.join(list(job.required_skills.keys())[:5])}

GUIDELINES:
1. STAR Format if applicable: Situation, Task, Action, Result
2. Include specific metrics/numbers
3. Keep to 150-250 words
4. Professional and authentic
5. Connect to job requirements

Answer (just the text, no "Answer:" prefix):
"""

        answer = await generate_text(prompt, provider=USE_OLLAMA)
        return answer.strip()

    def approve_answer(
        self,
        user_id: int,
        question: str,
        answer: str,
        question_type: str = "form_field",
        skill_tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Approve and save an answer for future reuse

        Args:
            user_id: User ID
            question: The question
            answer: The answer text
            question_type: Type of question (form_field, cover_letter, etc.)
            skill_tags: Skills relevant to this answer

        Returns:
            Approval confirmation with quality score
        """

        try:
            # Check if answer already exists
            existing = self.db.query(ApprovedAnswer).filter(
                ApprovedAnswer.user_id == user_id,
                ApprovedAnswer.question == question,
            ).first()

            quality_score = self._score_answer(answer)
            has_star = "accomplished" in answer.lower() or "results" in answer.lower()
            has_metrics = any(char.isdigit() for char in answer)

            if existing:
                # Update existing
                existing.answer = answer
                existing.quality_score = quality_score
                existing.star_format = has_star
                existing.has_quantified_results = has_metrics
                action = "updated"
            else:
                # Create new
                approved_answer = ApprovedAnswer(
                    user_id=user_id,
                    question=question,
                    answer=answer,
                    question_type=question_type,
                    skill_tags=skill_tags or [],
                    quality_score=quality_score,
                    star_format=has_star,
                    has_quantified_results=has_metrics,
                )
                self.db.add(approved_answer)
                action = "created"

            self.db.commit()

            logger.info(f"✅ Answer {action} for user {user_id}")

            return {
                "success": True,
                "action": action,
                "quality_score": round(quality_score, 1),
                "has_star_format": has_star,
                "has_metrics": has_metrics,
            }

        except Exception as e:
            logger.error(f"Error approving answer: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }

    def get_approved_answers(
        self,
        user_id: int,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get approved answers for user"""

        answers = self.db.query(ApprovedAnswer).filter(
            ApprovedAnswer.user_id == user_id
        ).order_by(
            ApprovedAnswer.success_rate.desc()
        ).limit(limit).all()

        return [
            {
                "id": a.id,
                "question": a.question,
                "question_type": a.question_type,
                "quality_score": a.quality_score,
                "times_used": a.times_used,
                "success_rate": a.success_rate,
                "has_star_format": a.star_format,
                "has_metrics": a.has_quantified_results,
            }
            for a in answers
        ]

    @staticmethod
    def _score_cover_letter(
        cover_letter: str,
        user: User,
        job: Job,
    ) -> float:
        """Score cover letter quality"""

        score = 50.0

        # Check length (3-4 paragraphs, 250-350 words)
        words = len(cover_letter.split())
        if 250 <= words <= 350:
            score += 15
        elif 200 <= words <= 400:
            score += 10

        # Check for STAR elements
        if any(word in cover_letter.lower() for word in ["accomplished", "achieved", "results"]):
            score += 15

        # Check for metrics
        if any(char.isdigit() for char in cover_letter):
            score += 10

        # Check for company/role specific details
        if job.company_name.lower() in cover_letter.lower():
            score += 10

        # Check for soft skills
        soft_skills = ["team", "collaboration", "leadership", "communication"]
        if any(skill in cover_letter.lower() for skill in soft_skills):
            score += 5

        return min(100, score)

    @staticmethod
    def _score_answer(answer: str) -> float:
        """Score individual answer quality"""

        score = 50.0

        # Length check (150-250 words is ideal)
        words = len(answer.split())
        if 150 <= words <= 250:
            score += 20
        elif 100 <= words <= 300:
            score += 15

        # STAR format check
        if any(word in answer.lower() for word in ["accomplished", "achieved", "resulted", "improved"]):
            score += 15

        # Metrics check
        if any(char.isdigit() for char in answer):
            score += 10

        # Sentence structure (varied)
        sentences = [s for s in answer.split(".") if s.strip()]
        if len(sentences) >= 3:
            score += 5

        return min(100, score)

    async def format_star_answer(self, raw_answer: str) -> str:
        """Format an answer into STAR structure (Situation, Task, Action, Result)"""
        return await self.memory.format_to_star(raw_answer)

    async def check_answer_memory(self, question: str, user_id: int) -> Optional[str]:
        """Check for semantically similar answers in memory"""
        result = await self.memory.get_best_answer(question, user_id)
        return result["answer"] if result else None
