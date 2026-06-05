"""
Tracking Agent - Manage application records, follow-ups, and database operations
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from sqlalchemy.orm import Session, joinedload
from utils.database import Application, ApplicationStatus, User, Job, AuditLog

logger = logging.getLogger(__name__)


class TrackingAgent:
    """Manages application tracking and follow-ups"""

    def __init__(self, db: Session):
        self.db = db

    def create_application(
        self,
        user_id: int,
        job_id: int,
        match_score: float = 0.0,
        resume_version_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create application record"""

        try:
            user = self.db.query(User).filter(User.id == user_id).first()
            job = self.db.query(Job).filter(Job.id == job_id).first()

            if not user or not job:
                return {"success": False, "message": "User or job not found"}

            # Generate tracking ID
            tracking_id = f"{job_id}_{user_id}_{int(datetime.utcnow().timestamp())}"

            application = Application(
                user_id=user_id,
                job_id=job_id,
                application_tracking_id=tracking_id,
                status=ApplicationStatus.SUBMITTED,
                match_score=match_score,
                resume_id=resume_version_id,
                submitted_at=datetime.utcnow(),
            )

            self.db.add(application)
            self.db.commit()
            self.db.refresh(application)

            logger.info(f"✅ Application created: {tracking_id}")

            return {
                "application_id": application.id,
                "tracking_id": tracking_id,
                "status": application.status,
                "created_at": application.created_at.isoformat(),
                "success": True,
            }

        except Exception as e:
            logger.error(f"Error creating application: {e}")
            return {"success": False, "message": str(e)}

    def update_application(
        self,
        application_id: int,
        **updates
    ) -> Dict[str, Any]:
        """Update application status and details"""

        try:
            app = self.db.query(Application).filter(
                Application.id == application_id
            ).first()

            if not app:
                return {"success": False, "message": "Application not found"}

            original_data = self._get_app_dict(app)

            for key, value in updates.items():
                if hasattr(app, key) and value is not None:
                    setattr(app, key, value)

            self.db.commit()
            self.db.refresh(app)

            # Audit log
            self._audit_log(
                user_id=app.user_id,
                entity_type="application",
                entity_id=app.id,
                action="update",
                original_value=original_data,
                new_value=self._get_app_dict(app),
                changes={k: v for k, v in updates.items() if k in original_data}
            )

            logger.info(f"✅ Application {application_id} updated")

            return {
                "application_id": application_id,
                "status": app.status,
                "updated_at": app.updated_at.isoformat(),
                "success": True,
            }

        except Exception as e:
            logger.error(f"Error updating application: {e}")
            return {"success": False, "message": str(e)}

    def schedule_followup(
        self,
        application_id: int,
        days_from_now: int = 7,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Schedule follow-up for application"""

        try:
            app = self.db.query(Application).filter(
                Application.id == application_id
            ).first()

            if not app:
                return {"success": False, "message": "Application not found"}

            follow_up_date = datetime.utcnow() + timedelta(days=days_from_now)

            self.update_application(
                application_id,
                follow_up_date=follow_up_date,
                notes=notes or app.notes,
            )

            logger.info(
                f"✅ Follow-up scheduled for application {application_id} "
                f"on {follow_up_date.date()}"
            )

            return {
                "application_id": application_id,
                "follow_up_date": follow_up_date.isoformat(),
                "days_from_now": days_from_now,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Error scheduling follow-up: {e}")
            return {"success": False, "message": str(e)}

    def get_applications(
        self,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get applications for user"""

        query = self.db.query(Application).options(
            joinedload(Application.job).joinedload(Job.analysis),
            joinedload(Application.documents),
        ).filter(Application.user_id == user_id)

        if status:
            query = query.filter(Application.status == status)

        apps = query.order_by(Application.created_at.desc()).limit(limit).all()

        return [self._get_app_dict(app) for app in apps]

    def get_pending_followups(
        self,
        user_id: int,
        days: int = 1,
    ) -> List[Dict[str, Any]]:
        """Get applications due for follow-up"""

        cutoff_date = datetime.utcnow() + timedelta(days=days)

        apps = self.db.query(Application).filter(
            Application.user_id == user_id,
            Application.follow_up_date <= cutoff_date,
            Application.follow_up_date.isnot(None),
        ).order_by(Application.follow_up_date.asc()).all()

        return [self._get_app_dict(app) for app in apps]

    def record_response(
        self,
        application_id: int,
        response_type: str,  # interview, rejection, offer
        response_date: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record response from company"""

        try:
            app = self.db.query(Application).filter(
                Application.id == application_id
            ).first()

            if not app:
                return {"success": False, "message": "Application not found"}

            updates = {
                "response_received": True,
                "response_date": response_date or datetime.utcnow(),
                "response_type": response_type,
            }

            if response_type == "interview":
                updates["interview_scheduled"] = True
                updates["status"] = ApplicationStatus.INTERVIEW_SCHEDULED
            elif response_type == "offer":
                updates["status"] = ApplicationStatus.OFFER_RECEIVED
            elif response_type == "rejection":
                updates["status"] = ApplicationStatus.REJECTED

            if notes:
                updates["notes"] = notes

            return self.update_application(application_id, **updates)

        except Exception as e:
            logger.error(f"Error recording response: {e}")
            return {"success": False, "message": str(e)}

    def get_application_stats(
        self,
        user_id: int,
    ) -> Dict[str, Any]:
        """Get statistics for user's applications"""

        apps = self.db.query(Application).filter(
            Application.user_id == user_id
        ).all()

        total = len(apps)
        submitted = sum(1 for a in apps if a.submitted_at)
        responses = sum(1 for a in apps if a.response_received)
        interviews = sum(1 for a in apps if a.interview_scheduled)
        offers = sum(1 for a in apps if a.status == ApplicationStatus.OFFER_RECEIVED)

        scored_apps = [a for a in apps if a.match_score is not None]
        avg_match_score = (
            sum(a.match_score for a in scored_apps) / len(scored_apps)
            if scored_apps
            else 0
        )

        return {
            "total_applications": total,
            "submitted": submitted,
            "responses": responses,
            "interviews": interviews,
            "offers": offers,
            "response_rate": round((responses / submitted * 100) if submitted else 0, 1),
            "interview_rate": round((interviews / submitted * 100) if submitted else 0, 1),
            "average_match_score": round(avg_match_score, 1),
        }

    def is_on_cooldown(self, user_id: int, company_name: str, days: int = 90) -> bool:
        """Check if user has applied to this company recently"""
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        recent_app = self.db.query(Application).join(Job).filter(
            Application.user_id == user_id,
            Job.company_name == company_name,
            Application.created_at >= cutoff_date
        ).first()
        
        return recent_app is not None

    @staticmethod
    def _get_app_dict(app: Application) -> Dict[str, Any]:
        """Convert application to dictionary"""

        job = app.job
        ats_score = job.analysis.ats_score if (job and job.analysis) else None

        return {
            "id": app.id,
            "user_id": app.user_id,
            "job_id": app.job_id,
            "status": app.status,
            "tracking_id": app.application_tracking_id,
            "match_score": app.match_score,
            "ats_score": ats_score,
            "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
            "response_received": app.response_received,
            "response_type": app.response_type,
            "response_date": app.response_date.isoformat() if app.response_date else None,
            "interview_scheduled": app.interview_scheduled,
            "follow_up_date": app.follow_up_date.isoformat() if app.follow_up_date else None,
            "notes": app.notes,
            "created_at": app.created_at.isoformat(),
            # Job details
            "title": job.job_title if job else None,
            "company": job.company_name if job else None,
            "location": job.location if job else None,
            "job_url": job.job_url if job else None,
            # Generated documents
            "documents": [
                {"path": doc.pdf_path, "generated_at": doc.generated_at.isoformat() if doc.generated_at else None}
                for doc in (app.documents or [])
            ],
        }

    def _audit_log(self, **kwargs):
        """Create audit log entry"""

        log = AuditLog(**kwargs)
        self.db.add(log)
        self.db.commit()
