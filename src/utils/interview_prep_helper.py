"""
Interview Preparation Helper
Generate interview prep guides, technical questions, behavioral prep
"""

import logging
from typing import Dict, Any, List, Optional

from utils.llm_helper import generate_text, USE_SONNET

logger = logging.getLogger(__name__)


class InterviewPrepHelper:
    """Generate interview preparation materials"""

    async def generate_interview_prep_pack(
        self,
        user_name: str,
        company_name: str,
        job_title: str,
        user_skills: Dict[str, int],
        job_requirements: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Generate comprehensive interview prep pack

        Returns:
            {
                "company_research": "...",
                "technical_questions": [...],
                "behavioral_questions": [...],
                "star_answers": {...},
                "company_culture": "...",
                "interview_tips": [...]
            }
        """

        try:
            # Company research
            company_research = await self._generate_company_research(company_name)

            # Technical questions specific to role
            tech_questions = await self._generate_technical_questions(
                job_title, list(job_requirements.keys())
            )

            # Behavioral questions
            behavioral_questions = await self._generate_behavioral_questions(job_title)

            # STAR answers
            star_answers = await self._generate_star_answers(job_title)

            # Interview tips
            tips = self._get_interview_tips(job_title)

            return {
                "success": True,
                "company_research": company_research,
                "technical_questions": tech_questions,
                "behavioral_questions": behavioral_questions,
                "star_answers": star_answers,
                "interview_tips": tips,
            }

        except Exception as e:
            logger.error(f"Error generating interview prep: {e}")
            return {"success": False, "message": str(e)}

    async def _generate_company_research(self, company_name: str) -> str:
        """Generate company research brief"""

        prompt = f"""
Generate a 2-3 paragraph research summary about {company_name} for interview preparation.
Include: company mission, recent news, engineering culture, tech stack.
Keep it concise and interview-relevant.
"""

        return await generate_text(prompt, provider=USE_SONNET)

    async def _generate_technical_questions(
        self,
        job_title: str,
        technologies: List[str],
    ) -> List[str]:
        """Generate role-specific technical interview questions"""

        tech_list = ", ".join(technologies[:5])

        prompt = f"""
Generate 5 technical interview questions for a {job_title} role with these technologies: {tech_list}.
Focus on practical, scenario-based questions.
Return as numbered list.
"""

        response = await generate_text(prompt, provider=USE_SONNET)
        questions = [q.strip() for q in response.split('\n') if q.strip() and q[0].isdigit()]

        return questions[:5]

    async def _generate_behavioral_questions(self, job_title: str) -> List[str]:
        """Generate behavioral interview questions"""

        prompt = f"""
Generate 5 behavioral interview questions for a {job_title} candidate.
Use STAR format guidelines (Situation, Task, Action, Result).
Focus on: teamwork, conflict resolution, leadership, problem-solving.
Return as numbered list.
"""

        response = await generate_text(prompt, provider=USE_SONNET)
        questions = [q.strip() for q in response.split('\n') if q.strip() and q[0].isdigit()]

        return questions[:5]

    async def _generate_star_answers(self, job_title: str) -> Dict[str, str]:
        """Generate sample STAR format answers"""

        prompt = f"""
Generate 3 STAR format answers for common {job_title} behavioral questions:
1. Tell us about a time you resolved a conflict with a team member
2. Describe your most complex technical project
3. How do you handle on-call incidents?

Format each as: Situation | Task | Action | Result
"""

        return {
            "conflict_resolution": await generate_text(prompt, provider=USE_SONNET),
            "technical_achievement": "...",
            "incident_handling": "...",
        }

    @staticmethod
    def _get_interview_tips(job_title: str) -> List[str]:
        """Get generic interview tips"""

        tips = [
            "Research the company thoroughly before the interview",
            "Prepare specific examples demonstrating your skills (STAR format)",
            "Ask thoughtful questions about the role and team",
            "Be prepared to discuss your resume and past projects in detail",
            "Practice explaining complex technical concepts in simple terms",
            "Prepare for both technical and behavioral questions",
            "Get a good night's sleep before the interview",
            "Test your audio/video setup if it's a remote interview",
            "Be ready with 3-5 questions to ask the interviewer",
            "Follow up within 24 hours to express continued interest",
        ]

        return tips


# Singleton
interview_prep_helper = InterviewPrepHelper()
