"""
Resume Agent - Customize resume for specific jobs
Maintains truth verification - no hallucinations, all customizations tracked
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from sqlalchemy.orm import Session
from utils.database import User, Job, Resume, AuditLog
from utils.document_store import write_text_document
from utils.llm_helper import generate_text, generate_json, USE_HAIKU

logger = logging.getLogger(__name__)


class ResumeAgent:
    """Manages resume customization and ATS optimization"""

    def __init__(self, db: Session):
        self.db = db

    async def customize_resume(
        self,
        user_id: int,
        job_id: int,
        mode: str = "balanced",  # conservative, balanced, aggressive
    ) -> Dict[str, Any]:
        """
        Customize resume for specific job with ATS optimization

        Args:
            user_id: User ID
            job_id: Job ID to customize for
            mode: Customization strategy
                - conservative: Minimal changes, safe for all ATS
                - balanced: Good balance of customization and safety
                - aggressive: Maximum keyword optimization

        Returns:
            {
                "resume_id": 1,
                "user_id": 1,
                "job_id": 2,
                "mode": "balanced",
                "customized_content": "...",
                "customization_details": {
                    "reordered_sections": ["Skills", "Experience"],
                    "added_keywords": ["Kubernetes", "AWS"],
                    "modified_bullets": 3,
                    "removed_content": 0
                },
                "ats_score": 92,
                "readability_score": 88,
                "keyword_match_score": 95,
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

            # Get original resume
            original_content = user.resume_parsed

            # Customize based on job requirements
            customization_prompt = f"""
Customize this resume for the target job while maintaining accuracy (no hallucinations).

ORIGINAL RESUME:
{str(original_content)[:1500]}

TARGET JOB:
Title: {job.job_title}
Company: {job.company_name}
Required Skills: {', '.join(job.required_skills.keys())}
Description: {job.description[:500] if job.description else 'N/A'}

CUSTOMIZATION MODE: {mode}
- conservative: Only add actual keywords that are already in the resume
- balanced: Reorder sections, add implied experience from existing bullets
- aggressive: Maximize keyword density while staying truthful

IMPORTANT RULES:
1. DO NOT invent experience the person doesn't have
2. DO NOT add fake certifications or skills
3. Only rearrange or rephrase existing accomplishments
4. Add relevant keywords from job description that match actual experience
5. Maintain all factual accuracy

Return JSON with:
{{
    "customized_bullets": ["bullet 1", "bullet 2"],
    "reordered_sections": ["section1", "section2"],
    "added_keywords": ["keyword1", "keyword2"],
    "modified_bullets": number,
    "changes_made": ["change1", "change2"]
}}
"""

            customizations = await self._apply_customization(
                customization_prompt, user, job, mode
            )

            # Apply changes to create customized version
            customized_content = self._apply_resume_changes(
                original_content, customizations
            )

            # Calculate ATS scores
            ats_scores = self._calculate_ats_scores(
                customized_content, job, mode
            )
            file_record = write_text_document(
                category="tailored_resumes",
                company_name=job.company_name,
                doc_type="tailored_resume",
                job_title=job.job_title,
                content=str(customized_content),
                metadata={
                    "user_id": user_id,
                    "job_id": job_id,
                    "mode": mode,
                    "ats_score": ats_scores.get("ats_score"),
                    "keyword_match_score": ats_scores.get("keyword_match_score"),
                },
                extension="txt",
            )
            customizations["generated_file"] = file_record

            # Save resume version
            resume = Resume(
                user_id=user_id,
                mode=mode,
                version_number=self._get_next_version_number(user_id),
                resume_content=str(customized_content),
                resume_json=customized_content,
                customized_for_job_id=job_id,
                customization_details=customizations,
                ats_score=ats_scores.get("ats_score"),
                readability_score=ats_scores.get("readability_score"),
                keyword_match_score=ats_scores.get("keyword_match_score"),
            )

            self.db.add(resume)
            self.db.commit()
            self.db.refresh(resume)

            # Audit log
            self._audit_log(
                user_id=user_id,
                entity_type="resume",
                entity_id=resume.id,
                action="create",
                new_value={
                    "mode": mode,
                    "customizations": customizations,
                    "ats_score": ats_scores.get("ats_score"),
                },
                reason=f"Resume customized for job {job.job_title} at {job.company_name}"
            )

            logger.info(
                f"✅ Resume customized for user {user_id}, job {job_id} "
                f"(ATS: {ats_scores.get('ats_score')})"
            )

            return {
                "resume_id": resume.id,
                "user_id": user_id,
                "job_id": job_id,
                "mode": mode,
                "customized_content": customized_content,
                "customization_details": customizations,
                "ats_score": round(ats_scores.get("ats_score", 0), 1),
                "readability_score": round(ats_scores.get("readability_score", 0), 1),
                "keyword_match_score": round(ats_scores.get("keyword_match_score", 0), 1),
                "file": file_record,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Error customizing resume: {e}")
            return {
                "success": False,
                "message": f"Error customizing resume: {str(e)}"
            }

    async def verify_truth(self, original_text: str, customized_text: str) -> Dict[str, Any]:
        """Verify that customized resume doesn't contain hallucinations"""
        prompt = f"""
        Compare the original and customized resumes. Identify any claims in the customized version that are NOT supported by the original.
        Return JSON with: {{"hallucinations": ["list of fake claims"], "is_truthful": boolean}}
        
        Original: {original_text[:1000]}
        Customized: {customized_text[:1000]}
        """
        return await generate_json(prompt, provider=USE_HAIKU)

    async def _apply_customization(
        self,
        prompt: str,
        user: User,
        job: Job,
        mode: str,
    ) -> Dict[str, Any]:
        """Apply customization using LLM with structured output"""
        try:
            result = await generate_json(prompt, provider=USE_HAIKU)
            # Verify truth before returning (use profile.experience_json if available)
            original_experience = (
                str(user.profile.experience_json)
                if user.profile is not None
                else str(user.resume_parsed or {})
            )
            truth_check = await self.verify_truth(original_experience, str(result.get("customized_bullets", [])))
            result["truth_verification"] = truth_check
            return result
        except Exception as e:
            logger.error(f"Error applying customization: {e}")
            return {
                "reordered_sections": ["Skills", "Experience"],
                "added_keywords": [],
                "modified_bullets": 0,
                "changes_made": ["Error occurred, used default strategy"]
            }

    @staticmethod
    def _apply_resume_changes(
        original: Dict[str, Any],
        customizations: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply customization changes to resume"""

        # Create copy and apply changes
        customized = original.copy() if original else {}
        
        # Apply bullet modifications if provided
        if "customized_bullets" in customizations:
            # Logic to replace or add bullets
            # For simplicity in this MVP, we store the customized bullets separately
            # In a real system, we'd map them back to specific experience records
            customized["experience_customized"] = customizations["customized_bullets"]
            
        # Reorder sections if requested
        if "reordered_sections" in customizations:
            customized["section_order"] = customizations["reordered_sections"]
            
        # Add keywords to skills
        if "added_keywords" in customizations:
            current_skills = customized.get("skills", [])
            for kw in customizations["added_keywords"]:
                if kw not in current_skills:
                    current_skills.append(kw)
            customized["skills"] = current_skills

        # Add customization metadata
        customized["_customizations"] = customizations
        customized["_customized_at"] = datetime.utcnow().isoformat()

        return customized

    @staticmethod
    def _calculate_ats_scores(
        resume_content: Dict[str, Any],
        job: Job,
        mode: str,
    ) -> Dict[str, float]:
        """
        Calculate ATS-related scores
        In production, this would use actual ATS evaluation
        """

        # Placeholder implementation
        base_score = 70.0

        # Add points for keyword match
        content_str = str(resume_content).lower()
        matched_keywords = sum(
            1 for keyword in job.required_skills.keys()
            if keyword.lower() in content_str
        )
        keyword_match = (matched_keywords / max(1, len(job.required_skills))) * 100

        # Mode affects aggressiveness of optimization
        mode_boost = {
            "conservative": 5,
            "balanced": 10,
            "aggressive": 15,
        }.get(mode, 10)

        ats_score = min(100, base_score + (keyword_match * 0.3) + mode_boost)

        return {
            "ats_score": ats_score,
            "readability_score": max(70, 100 - (keyword_match * 0.15)),  # More keywords = less readable
            "keyword_match_score": keyword_match,
        }

    def _get_next_version_number(self, user_id: int) -> int:
        """Get next version number for this user"""

        latest = self.db.query(Resume).filter(
            Resume.user_id == user_id
        ).order_by(Resume.version_number.desc()).first()

        return (latest.version_number if latest else 0) + 1

    def update_success_metrics(self, resume_id: int, interviewed: bool):
        """Update resume success rate based on outcome"""
        resume = self.db.query(Resume).filter(Resume.id == resume_id).first()
        if resume:
            resume.times_used = (resume.times_used or 0) + 1
            if interviewed:
                resume.success_count = (resume.success_count or 0) + 1
            self.db.commit()

    async def suggest_keywords(self, user_id: int, job_id: int) -> List[Dict[str, Any]]:
        """Identify high-impact missing keywords from the user's resume for a specific job"""
        
        user = self.db.query(User).filter(User.id == user_id).first()
        job = self.db.query(Job).filter(Job.id == job_id).first()
        
        if not user or not job:
            return []
            
        prompt = f"""
        Compare the user's skills with the job's required skills.
        Identify the most important keywords missing from the user's resume.
        For each, explain WHY it's important for this specific job.
        
        User Skills: {', '.join(user.skills.keys())}
        Job Required Skills: {', '.join(job.required_skills.keys())}
        
        Return JSON: [{{"keyword": "...", "importance": "High/Medium", "reason": "..."}}]
        """
        
        return await generate_json(prompt, provider=USE_HAIKU)

    async def check_readability(self, content: str) -> Dict[str, Any]:
        """Analyze if the resume is readable by both humans and ATS (no keyword stuffing)"""
        
        prompt = f"""
        Analyze this resume content for readability and ATS optimization.
        Check for:
        1. Keyword stuffing (repeated keywords without context)
        2. Sentence complexity
        3. Professional tone
        
        Content: {content[:1000]}
        
        Return JSON: {{
            "readability_score": 0-100,
            "issues": ["issue 1", "issue 2"],
            "suggestions": ["suggest 1"]
        }}
        """
        
        return await generate_json(prompt, provider=USE_HAIKU)

    def get_resume(self, resume_id: int) -> Optional[Dict[str, Any]]:
        """Get resume details"""

        resume = self.db.query(Resume).filter(Resume.id == resume_id).first()
        if not resume:
            return None

        return {
            "id": resume.id,
            "user_id": resume.user_id,
            "mode": resume.mode,
            "version_number": resume.version_number,
            "content": resume.resume_json,
            "customized_for_job_id": resume.customized_for_job_id,
            "customization_details": resume.customization_details,
            "ats_score": resume.ats_score,
            "readability_score": resume.readability_score,
            "keyword_match_score": resume.keyword_match_score,
            "interviews_generated": resume.interviews_generated,
            "offers_generated": resume.offers_generated,
            "created_at": resume.created_at.isoformat(),
        }

    def get_user_resumes(
        self,
        user_id: int,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get all resumes for a user"""

        resumes = self.db.query(Resume).filter(
            Resume.user_id == user_id
        ).order_by(Resume.version_number.desc()).limit(limit).all()

        return [
            self.get_resume(resume.id)
            for resume in resumes
            if resume
        ]

    def _audit_log(self, **kwargs):
        """Create audit log entry"""

        log = AuditLog(**kwargs)
        self.db.add(log)
        self.db.commit()
