"""
Match Agent - Calculate compatibility between user and jobs
Scores skill match, experience match, and provides detailed breakdown
"""

import logging
import math
from typing import Dict, List, Optional, Any, Tuple

from sqlalchemy.orm import Session
from utils.database import User, Job, Application
from utils.llm_helper import generate_json, USE_OLLAMA

logger = logging.getLogger(__name__)


class MatchAgent:
    """Calculates match scores between users and jobs"""

    def __init__(self, db: Session):
        self.db = db

    async def calculate_match(
        self,
        user_id: int,
        job_id: int,
    ) -> Dict[str, Any]:
        """
        Calculate overall match score (0-100) and detailed breakdown

        Args:
            user_id: User ID
            job_id: Job ID

        Returns:
            {
                "match_score": 85,  # 0-100
                "skill_match": 85,
                "experience_match": 80,
                "seniority_match": 90,
                "location_match": 70,
                "salary_match": 95,
                "missing_skills": ["Rust", "Go"],
                "matching_skills": ["AWS", "Kubernetes", "Terraform"],
                "nice_to_have_match": ["Docker"],
                "analysis": "Strong match! You have most required skills...",
                "recommendation": "STRONG_MATCH|GOOD_MATCH|MEDIUM_MATCH|WEAK_MATCH",
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

            # Get user skills as list for semantic match
            user_skill_list = list(user.skills.keys()) if user.skills else []
            job_req_list = list(job.required_skills.keys()) if job.required_skills else []

            # Perform semantic skill match
            semantic_results = await self.semantic_skill_match(user_skill_list, job_req_list)
            
            # Calculate individual scores
            skill_score, matching_skills, missing_skills, partially_matched = (
                self._calculate_skill_match_enhanced(user, job, semantic_results)
            )
            experience_score = self._calculate_experience_match(user, job)
            seniority_score = self._calculate_seniority_match(user, job)
            location_score = self._calculate_location_match(user, job)
            salary_score = self._calculate_salary_match(user, job)

            # Calculate weighted overall score
            overall_score = (
                skill_score * 0.40 +  # 40% weight on skills
                experience_score * 0.25 +  # 25% weight on experience
                seniority_score * 0.15 +  # 15% weight on seniority
                salary_score * 0.10 +  # 10% weight on salary
                location_score * 0.10  # 10% weight on location
            )

            # Get nice-to-have matches
            nice_to_have_match = [
                skill for skill in (job.nice_to_haves or [])
                if any(skill.lower() == s.lower() for s in user_skill_list)
            ]

            # Generate analysis
            analysis = self._generate_analysis(
                user=user,
                job=job,
                skill_score=skill_score,
                experience_score=experience_score,
                missing_skills=missing_skills,
                matching_skills=matching_skills,
            )

            # Determine recommendation
            recommendation = self._get_recommendation(overall_score)

            # Predict interview probability
            interview_prob = await self.predict_interview_probability(
                overall_score, job.job_type, job.company_size
            )

            return {
                "match_score": round(overall_score, 1),
                "skill_match": round(skill_score, 1),
                "experience_match": round(experience_score, 1),
                "seniority_match": round(seniority_score, 1),
                "location_match": round(location_score, 1),
                "salary_match": round(salary_score, 1),
                "interview_probability": round(interview_prob, 1),
                "matching_skills": matching_skills,
                "partially_matched_skills": partially_matched,
                "missing_skills": missing_skills,
                "nice_to_have_match": nice_to_have_match,
                "analysis": analysis,
                "recommendation": recommendation,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Error calculating match: {e}")
            return {
                "success": False,
                "message": f"Error calculating match: {str(e)}"
            }

    def _calculate_skill_match_enhanced(
        self,
        user: User,
        job: Job,
        semantic_results: Dict[str, Any],
    ) -> Tuple[float, List[str], List[str], List[str]]:
        """
        Calculate skill match percentage using semantic results

        Returns: (score, matching_skills, missing_skills, partially_matched)
        """

        matching = []
        partially_matched = []
        missing = semantic_results.get("missing", [])

        # Process semantic matches
        for match in semantic_results.get("matched", []):
            user_skill = match.get("user")
            job_req = match.get("job")
            score = match.get("score", 0.0)

            if score >= 0.8:
                matching.append(job_req)
            elif score >= 0.5:
                partially_matched.append(f"{job_req} (Semantic Match: {user_skill})")
            else:
                missing.append(job_req)

        # Remove duplicates from missing
        missing = list(set(missing))
        
        # Calculate score
        num_reqs = len(job.required_skills) if job.required_skills else 1
        matched_percentage = (len(matching) / num_reqs) * 100
        partial_percentage = (len(partially_matched) / num_reqs) * 50

        score = min(100, matched_percentage + partial_percentage)

        return score, matching, missing, partially_matched

    def _calculate_experience_match(self, user: User, job: Job) -> float:
        """Calculate experience match based on years"""

        if not user.years_experience or not job.seniority_level:
            return 50.0

        seniority_years = {
            "junior": 2,
            "mid": 5,
            "senior": 8,
            "lead": 12,
        }

        required_years = seniority_years.get(job.seniority_level, 5)

        if user.years_experience >= required_years:
            return 100.0
        else:
            # Partial credit for some experience
            return (user.years_experience / required_years) * 100

    def _calculate_seniority_match(self, user: User, job: Job) -> float:
        """Check if user seniority matches job level"""

        seniority_order = ["junior", "mid", "senior", "lead"]

        # Try to infer user seniority from title
        user_seniority = self._infer_seniority(user.current_title)
        job_seniority = job.seniority_level

        if not user_seniority or not job_seniority:
            return 50.0

        user_idx = seniority_order.index(user_seniority) if user_seniority in seniority_order else 1
        job_idx = seniority_order.index(job_seniority) if job_seniority in seniority_order else 1

        # Prefer exact match or overqualification
        if user_idx >= job_idx:
            return 100.0
        else:
            # Slight penalty for underqualification
            return max(50.0, 100.0 - ((job_idx - user_idx) * 20))

    def _calculate_location_match(self, user: User, job: Job) -> float:
        """Check location compatibility"""

        if not user.location or not job.location:
            return 70.0  # Neutral if unknown

        # Remote is always good
        if job.remote_type == "remote":
            return 100.0

        # Check if locations match
        user_loc = user.location.lower()
        job_loc = job.location.lower()

        if user_loc == job_loc:
            return 100.0
        elif job.remote_type == "hybrid":
            return 80.0
        else:
            return 50.0

    def _calculate_salary_match(self, user: User, job: Job) -> float:
        """Check if salary range is reasonable"""

        # If no salary info, assume good match
        if not job.salary_min or not job.salary_max:
            return 70.0

        # Estimate user salary expectation based on seniority
        # (In real system, you'd track user salary expectations)
        seniority = self._infer_seniority(user.current_title)
        user_expected_min = {
            "junior": 80000,
            "mid": 120000,
            "senior": 150000,
            "lead": 200000,
        }.get(seniority, 120000)

        # Check if job salary meets expectations
        if job.salary_max >= user_expected_min:
            return 100.0
        else:
            return (job.salary_max / user_expected_min) * 100

    @staticmethod
    def _get_level_number(level_str: str) -> int:
        """Convert proficiency level string to number"""

        levels = {
            "novice": 1,
            "beginner": 2,
            "intermediate": 5,
            "proficient": 7,
            "advanced": 8,
            "expert": 10,
        }

        return levels.get(level_str.lower(), 5)

    @staticmethod
    def _infer_seniority(title: str) -> Optional[str]:
        """Infer seniority level from job title"""

        title_lower = title.lower() if title else ""

        if any(w in title_lower for w in ["lead", "principal", "staff", "director"]):
            return "lead"
        elif any(w in title_lower for w in ["senior", "sr."]):
            return "senior"
        elif any(w in title_lower for w in ["junior", "jr."]):
            return "junior"
        else:
            return "mid"

    def _generate_analysis(
        self,
        user: User,
        job: Job,
        skill_score: float,
        experience_score: float,
        missing_skills: List[str],
        matching_skills: List[str],
    ) -> str:
        """Generate human-readable analysis"""

        analysis_parts = []

        # Skill analysis
        if skill_score >= 85:
            analysis_parts.append(
                f"✅ Excellent skill match! You have {len(matching_skills)} of the required skills."
            )
        elif skill_score >= 70:
            analysis_parts.append(
                f"✅ Good skill match! You have most required skills. Missing: {', '.join(missing_skills[:2])}"
            )
        elif skill_score >= 50:
            analysis_parts.append(
                f"⚠️ Partial skill match. You have some required skills but missing: {', '.join(missing_skills[:3])}"
            )
        else:
            analysis_parts.append(
                f"❌ Limited skill match. You're missing several key skills."
            )

        # Experience analysis
        if experience_score >= 85:
            analysis_parts.append(
                f"You have sufficient experience for this {job.seniority_level} role."
            )
        elif experience_score >= 70:
            analysis_parts.append("You have moderate experience for this role.")
        else:
            analysis_parts.append(
                "You may be slightly underqualified in experience, but your skills could compensate."
            )

        return " ".join(analysis_parts)

    @staticmethod
    def _get_recommendation(score: float) -> str:
        """Get recommendation based on score"""

        if score >= 85:
            return "STRONG_MATCH"
        elif score >= 70:
            return "GOOD_MATCH"
        elif score >= 50:
            return "MEDIUM_MATCH"
        else:
            return "WEAK_MATCH"

    async def semantic_skill_match(self, user_skills: List[str], job_requirements: List[str]) -> Dict[str, Any]:
        """Use LLM to perform semantic matching (e.g. 'Kubernetes' matches 'Container orchestration')"""
        prompt = f"""
        Compare the user skills and job requirements. Identify semantic matches even if names differ.
        Return JSON: {{"matched": [{{"user": "skill", "job": "req", "score": 0-1}}], "missing": ["req"]}}
        
        User Skills: {', '.join(user_skills)}
        Job Requirements: {', '.join(job_requirements)}
        """
        return await generate_json(prompt, provider=USE_OLLAMA)

    async def predict_interview_probability(self, match_score: float, job_type: str, company_size: str) -> float:
        """Predict probability of getting an interview (0-100)"""
        # Heuristic based on match score and market trends
        base_prob = match_score * 0.8
        
        # Adjust for company size (smaller companies often respond faster)
        if company_size and any(s in company_size for s in ["1-10", "11-50", "51-200"]):
            base_prob += 10
            
        # Adjust for role type (DevOps/SRE is high demand)
        if job_type in ["devops", "sre"]:
            base_prob += 5
            
        return min(95.0, max(5.0, base_prob))

    async def analyze_missing_skills(self, user_skills: List[str], required_skills: List[str]) -> List[Dict[str, Any]]:
        """Analyze missing skills and their learning impact"""
        missing = [s for s in required_skills if s.lower() not in [us.lower() for us in user_skills]]
        
        if not missing:
            return []
            
        prompt = f"""
        For these missing skills, provide learning impact (High/Medium/Low) and time to learn.
        Return JSON: [{{"skill": "name", "impact": "level", "time": "est"}}]
        
        Missing: {', '.join(missing)}
        """
        return await generate_json(prompt, provider=USE_OLLAMA)

    async def estimate_salary(self, job_title: str, location: str) -> Dict[str, Any]:
        """Estimate salary range based on role and location using LLM knowledge"""
        
        prompt = f"""
        Provide a realistic annual salary range (USD) for this role and location.
        Role: {job_title}
        Location: {location}
        
        Return JSON: {{"min": 100000, "max": 150000, "currency": "USD", "confidence": "High/Medium/Low"}}
        """
        
        return await generate_json(prompt, provider=USE_OLLAMA)
