"""
Profile Agent - Extract and manage user profile information
Reads resume and maintains single source of truth for skills, experience, certifications
"""

import json
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from sqlalchemy.orm import Session
from utils.database import User, AuditLog
from utils.llm_helper import generate_json, generate_text

logger = logging.getLogger(__name__)


class ProfileAgent:
    """Manages user profile data extraction and storage"""

    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger(__name__)

    async def extract_profile_from_resume(
        self,
        resume_path: str,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Extract profile information from resume (PDF/DOCX)

        Args:
            resume_path: Path to resume file
            user_id: Optional existing user ID to update

        Returns:
            {
                "user_id": 1,
                "name": "John Doe",
                "email": "john@example.com",
                "current_title": "Senior DevOps Engineer",
                "years_experience": 8,
                "skills": {"AWS": 8, "Kubernetes": 7, "Terraform": 7, ...},
                "certifications": {"CKA": true, "AWS-SAA": true},
                "github_profile": "https://github.com/...",
                "linkedin_profile": "https://linkedin.com/...",
                "success": true,
                "message": "Profile extracted successfully"
            }
        """

        try:
            # Read resume file
            resume_text = self._read_resume(resume_path)

            # Extract structured profile using LLM
            profile_prompt = f"""
Analyze this resume and extract the following information in JSON format:
- Name
- Email address
- Phone number
- Current location
- Current company and job title
- Years of experience
- Technical skills with proficiency level (1-10)
- Certifications and licenses
- GitHub profile URL (if mentioned)
- LinkedIn profile URL (if mentioned)
- Portfolio/personal website URL (if mentioned)

Resume:
{resume_text}

Return ONLY valid JSON with these keys:
{{
    "name": "string",
    "email": "string",
    "phone": "string",
    "location": "string",
    "current_company": "string",
    "current_title": "string",
    "years_experience": number,
    "skills": {{"skill_name": proficiency_level}},
    "certifications": {{"cert_name": true}},
    "github_profile": "string or null",
    "linkedin_profile": "string or null",
    "portfolio_url": "string or null"
}}
"""

            profile_data = await generate_json(profile_prompt)

            # Save or update user in database
            if user_id:
                user = self.db.query(User).filter(User.id == user_id).first()
                if not user:
                    raise ValueError(f"User {user_id} not found")
                # Update existing user
                original_data = self._get_user_dict(user)
            else:
                user = User()
                original_data = {}

            # Update user fields
            user.name = profile_data.get("name", "Unknown")
            user.email = profile_data.get("email", "")
            user.phone = profile_data.get("phone")
            user.location = profile_data.get("location")
            user.current_company = profile_data.get("current_company")
            user.current_title = profile_data.get("current_title")
            user.years_experience = profile_data.get("years_experience")
            user.github_profile = profile_data.get("github_profile")
            user.linkedin_profile = profile_data.get("linkedin_profile")
            user.portfolio_url = profile_data.get("portfolio_url")

            # Store skills and certifications
            user.skills = profile_data.get("skills", {})
            user.certifications = profile_data.get("certifications", {})
            user.resume_parsed = profile_data
            user.original_resume_path = str(resume_path)

            # Save to database
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

            # Log audit trail
            self._audit_log(
                user_id=user.id,
                entity_type="user",
                entity_id=user.id,
                action="update" if user_id else "create",
                original_value=original_data if user_id else None,
                new_value=self._get_user_dict(user),
                reason="Profile extracted from resume"
            )

            logger.info(f"✅ Profile extracted for user {user.id}: {user.name}")

            return {
                "user_id": user.id,
                "name": user.name,
                "email": user.email,
                "current_title": user.current_title,
                "years_experience": user.years_experience,
                "skills": user.skills,
                "certifications": user.certifications,
                "success": True,
                "message": "Profile extracted successfully"
            }

        except Exception as e:
            logger.error(f"Error extracting profile: {e}")
            return {
                "success": False,
                "message": f"Error extracting profile: {str(e)}"
            }

    async def validate_profile(self, user_id: int) -> Dict[str, Any]:
        """
        Validate that profile is complete and accurate

        Returns completeness score and missing fields
        """

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "message": "User not found"}

        # Check required fields
        required_fields = {
            "name": user.name,
            "email": user.email,
            "current_title": user.current_title,
            "skills": user.skills,
        }

        missing_fields = [
            field for field, value in required_fields.items()
            if not value
        ]

        # Calculate completeness score
        total_fields = len(required_fields) + 5  # + phone, location, certifications, github, linkedin
        filled_fields = (
            (1 if user.phone else 0) +
            (1 if user.location else 0) +
            (1 if user.certifications else 0) +
            (1 if user.github_profile else 0) +
            (1 if user.linkedin_profile else 0) +
            len([f for f in required_fields.values() if f])
        )

        completeness_score = (filled_fields / total_fields) * 100

        return {
            "user_id": user_id,
            "completeness_score": round(completeness_score, 2),
            "missing_fields": missing_fields,
            "suggestions": self._get_validation_suggestions(missing_fields),
            "success": len(missing_fields) == 0,
            "message": "Profile is complete" if len(missing_fields) == 0 else f"Missing {len(missing_fields)} fields"
        }

    def get_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user profile"""

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "location": user.location,
            "current_company": user.current_company,
            "current_title": user.current_title,
            "years_experience": user.years_experience,
            "skills": user.skills,
            "certifications": user.certifications,
            "github_profile": user.github_profile,
            "linkedin_profile": user.linkedin_profile,
            "portfolio_url": user.portfolio_url,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
        }

    async def update_profile(
        self,
        user_id: int,
        **updates
    ) -> Dict[str, Any]:
        """Update specific profile fields"""

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "message": "User not found"}

        original_data = self._get_user_dict(user)

        # Update allowed fields
        allowed_fields = {
            "name", "email", "phone", "location",
            "current_company", "current_title", "years_experience",
            "skills", "certifications", "github_profile",
            "linkedin_profile", "portfolio_url"
        }

        for field, value in updates.items():
            if field in allowed_fields and value is not None:
                setattr(user, field, value)

        self.db.commit()
        self.db.refresh(user)

        # Audit log
        self._audit_log(
            user_id=user.id,
            entity_type="user",
            entity_id=user.id,
            action="update",
            original_value=original_data,
            new_value=self._get_user_dict(user),
            reason=f"Profile fields updated: {', '.join(updates.keys())}"
        )

        logger.info(f"✅ Profile updated for user {user_id}")
        return {
            "user_id": user_id,
            "success": True,
            "message": "Profile updated successfully"
        }

    def _read_resume(self, resume_path: str) -> str:
        """Read resume file (PDF or DOCX)"""

        path = Path(resume_path)
        if not path.exists():
            raise FileNotFoundError(f"Resume not found: {resume_path}")

        try:
            if path.suffix.lower() == ".pdf":
                from pypdf import PdfReader
                with open(path, "rb") as f:
                    reader = PdfReader(f)
                    text = "\n".join(
                        page.extract_text() for page in reader.pages
                    )
                return text

            elif path.suffix.lower() == ".docx":
                from docx import Document
                doc = Document(path)
                text = "\n".join(para.text for para in doc.paragraphs)
                return text

            else:
                raise ValueError(f"Unsupported file format: {path.suffix}")

        except Exception as e:
            logger.error(f"Error reading resume: {e}")
            raise

    @staticmethod
    def _get_user_dict(user: User) -> Dict[str, Any]:
        """Convert user object to dictionary"""
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "location": user.location,
            "current_company": user.current_company,
            "current_title": user.current_title,
            "years_experience": user.years_experience,
            "skills": user.skills,
            "certifications": user.certifications,
            "github_profile": user.github_profile,
            "linkedin_profile": user.linkedin_profile,
        }

    @staticmethod
    def _get_validation_suggestions(missing_fields: List[str]) -> List[str]:
        """Get suggestions for missing fields"""

        suggestions = {
            "name": "Add your full name to the profile",
            "email": "Add your email address for recruiter contact",
            "current_title": "Add your current job title for matching",
            "skills": "Add your technical skills for better job matching",
            "phone": "Add your phone number so recruiters can reach you",
            "location": "Add your location for better local job matches",
            "certifications": "Add your certifications to stand out",
            "github_profile": "Add your GitHub profile to showcase projects",
            "linkedin_profile": "Add your LinkedIn profile for networking",
        }

        return [suggestions.get(field, f"Add {field}") for field in missing_fields]

    def _audit_log(self, **kwargs):
        """Create audit log entry"""
        log = AuditLog(**kwargs)
        self.db.add(log)
        self.db.commit()
