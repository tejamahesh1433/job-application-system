from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Request
from typing import Dict, Any, Optional
from pathlib import Path
from sqlalchemy.orm import Session
import logging
import shutil

from utils.database import get_db, User
from utils.document_store import safe_name
from agents.profile_agent import ProfileAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["user"])

@router.get("/ping")
async def ping_user():
    return {"message": "user router is active"}

@router.post("/profile/upload-resume")
async def upload_resume(
    user_id: Optional[int] = None,
    resume_path: str = "resumes/resume.pdf",
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Upload and parse resume to extract profile"""
    try:
        profile_agent = ProfileAgent(db)
        result = await profile_agent.extract_profile_from_resume(
            resume_path=resume_path,
            user_id=user_id,
        )
        return result
    except Exception as e:
        logger.error(f"Error uploading resume: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{user_id}/resumes")
async def list_user_resumes(
    user_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all resume versions for a user"""
    try:
        from utils.database import Resume, Job
        resumes = (
            db.query(Resume)
            .filter(Resume.user_id == user_id)
            .order_by(Resume.created_at.desc())
            .all()
        )
        result = []
        for r in resumes:
            job_info = None
            if r.customized_for_job_id:
                job = db.query(Job).filter(Job.id == r.customized_for_job_id).first()
                if job:
                    job_info = {"title": job.job_title, "company": job.company_name}
            result.append({
                "id": r.id,
                "version_number": r.version_number,
                "mode": r.mode,
                "ats_score": r.ats_score,
                "readability_score": r.readability_score,
                "keyword_match_score": r.keyword_match_score,
                "used_count": r.used_count or 0,
                "interviews_generated": r.interviews_generated or 0,
                "offers_generated": r.offers_generated or 0,
                "customization_details": r.customization_details or {},
                "job": job_info,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })
        return {"resumes": result, "total": len(result)}
    except Exception as e:
        logger.error(f"Error listing resumes: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload-resume-file")
async def upload_resume_file(
    file: UploadFile = File(...),
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Upload a resume file (PDF/DOCX) — saves file and registers a base Resume record."""
    from utils.database import Resume, User
    from agents.profile_agent import ProfileAgent

    try:
        # 1. Save file to disk
        resumes_dir = Path(__file__).resolve().parent.parent.parent / "resumes"
        resumes_dir.mkdir(exist_ok=True)
        raw_filename = file.filename or "resume.pdf"
        suffix = Path(raw_filename).suffix or ".pdf"
        filename = f"{safe_name(Path(raw_filename).stem, 'uploaded_resume')}{suffix}"
        dest = resumes_dir / filename
        with dest.open("wb") as buf:
            shutil.copyfileobj(file.file, buf)

        # 2. Ensure the target user exists (create a placeholder if needed)
        resolved_uid: Optional[int] = user_id
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                user = User(id=user_id, name="Default User", email=f"user{user_id}@jobsystem.local")
                db.add(user)
                db.commit()
                db.refresh(user)
            resolved_uid = user.id

        # 3. Create base Resume record if none exists for this user
        if resolved_uid:
            existing = (
                db.query(Resume)
                .filter(Resume.user_id == resolved_uid, Resume.version_number == 1)
                .first()
            )
            if not existing:
                db.add(Resume(
                    user_id=resolved_uid,
                    version_number=1,
                    mode="base",
                    original_text="",
                    customization_details={
                        "changes_summary": "Original uploaded resume — not tailored for any specific job.",
                        "matched_keywords": [],
                        "missing_keywords": [],
                    },
                ))
                db.commit()

        # 4. Extract and update profile from the newly uploaded resume
        try:
            profile_agent = ProfileAgent(db)
            await profile_agent.extract_profile_from_resume(user_id=resolved_uid, resume_path=str(dest))
        except Exception as profile_e:
            logger.error(f"Error extracting profile from uploaded resume: {profile_e}")

        return {
            "success": True,
            "file_saved": filename,
            "user_id": resolved_uid,
            "message": "File uploaded and profile updated successfully",
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error in upload_resume_file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{user_id}/profile")
async def get_user_profile(
    user_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get user profile"""
    try:
        profile_agent = ProfileAgent(db)
        profile = profile_agent.get_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="User not found")
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{user_id}/profile")
async def update_user_profile(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update user profile — accepts both query params and JSON body"""
    try:
        # Support both query params and JSON body
        updates = dict(request.query_params)
        try:
            body = await request.json()
            if isinstance(body, dict):
                updates.update(body)
        except Exception:
            pass

        # Type-coerce known integer fields
        if "years_experience" in updates and updates["years_experience"] not in (None, ""):
            try:
                updates["years_experience"] = int(updates["years_experience"])
            except (ValueError, TypeError):
                updates.pop("years_experience", None)

        # Remove empty strings (treat as no-change)
        updates = {k: v for k, v in updates.items() if v not in ("", None)}

        if not updates:
            return {"success": True, "message": "No changes provided", "user_id": user_id}

        profile_agent = ProfileAgent(db)
        result = await profile_agent.update_profile(user_id=user_id, **updates)
        return result
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tailor-resume")
async def tailor_resume(
    user_id: int,
    job_id: int,
    mode: str = "balanced",
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Tailor resume for a specific job"""
    try:
        from agents.resume_agent import ResumeAgent
        resume_agent = ResumeAgent(db)
        result = await resume_agent.customize_resume(
            user_id=user_id,
            job_id=job_id,
            mode=mode,
        )
        return result
    except Exception as e:
        logger.error(f"Error tailoring resume: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/resume/{resume_id}/download")
async def download_resume(
    resume_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Generate and download resume as PDF (Mock for now)"""
    try:
        from utils.database import Resume
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        
        # In a real system, this would generate a PDF and return a FileResponse
        # For this demo, we'll return a success message and a mock path
        return {
            "success": True,
            "message": "Resume PDF generated successfully",
            "download_url": f"/resumes/resume_v{resume.version_number}.pdf",
            "filename": f"resume_v{resume.version_number}.pdf"
        }
    except Exception as e:
        logger.error(f"Error downloading resume: {e}")
        raise HTTPException(status_code=400, detail=str(e))
