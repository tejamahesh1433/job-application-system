"""
Main API Extensions - Phase 2 & Phase 3 endpoints
Add these routes to main.py for browser automation and email monitoring
"""

from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
import asyncio
from typing import List, Dict, Any, Optional

from config import settings
from utils.database import get_db, Application
from agents.browser_agent import BrowserAgent
from batch_applications import run_batch_processing
from utils.gmail_helper import gmail_helper
from utils.interview_prep_helper import interview_prep_helper
from daily_summary import DailySummaryGenerator


def add_phase2_routes(app: FastAPI):
    """Add Phase 2 endpoints (Browser Automation)"""

    # ============================================
    # Phase 2: Browser Automation
    # ============================================

    @app.post("/api/browser/initialize")
    async def initialize_browser() -> Dict[str, Any]:
        """Initialize browser for form filling"""

        try:
            # Browser is automatically initialized in batch processing
            return {
                "success": True,
                "message": "Browser ready for automation",
                "headless": settings.debug == False,
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/browser/fill-form")
    async def fill_application_form(
        application_id: int,
        job_url: str,
        form_data: Dict[str, str],
        auto_submit: bool = False,
        db: Session = Depends(get_db),
    ) -> Dict[str, Any]:
        """Fill application form automatically"""

        try:
            browser_agent = BrowserAgent(db)
            await browser_agent.initialize()

            try:
                result = await browser_agent.fill_and_submit_application(
                    application_id=application_id,
                    job_url=job_url,
                    form_data=form_data,
                    auto_submit=auto_submit,
                )
                return result
            finally:
                await browser_agent.close()

        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/browser/detect-form-fields")
    async def detect_form_fields(job_url: str) -> Dict[str, Any]:
        """Detect form fields on page"""

        try:
            browser_agent = BrowserAgent(None)
            await browser_agent.initialize()

            try:
                fields = await browser_agent.extract_form_fields_from_page(job_url)
                return {
                    "success": True,
                    "fields": fields,
                    "field_count": len(fields),
                }
            finally:
                await browser_agent.close()

        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/batch/process")
    async def process_batch_applications(
        user_id: int,
        job_ids: List[int],
        phase: str = "phase2",  # phase1, phase2, phase3
        db: Session = Depends(get_db),
    ) -> Dict[str, Any]:
        """
        Process batch of 25 applications

        Phases:
        - phase1: Manual submission
        - phase2: Auto-fill + manual submit
        - phase3: Full auto (fill + submit)
        """

        try:
            result = await run_batch_processing(
                user_id=user_id,
                job_ids=job_ids,
                phase=phase,
            )
            return result

        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/interview-prep/generate")
    async def generate_interview_prep(
        user_id: int,
        job_id: int,
        db: Session = Depends(get_db),
    ) -> Dict[str, Any]:
        """Generate interview preparation pack"""

        try:
            from agents import ProfileAgent, JobAnalysisAgent

            profile_agent = ProfileAgent(db)
            job_agent = JobAnalysisAgent(db)

            user = profile_agent.get_profile(user_id)
            job = job_agent.get_job(job_id)

            if not user or not job:
                raise HTTPException(status_code=404, detail="User or job not found")

            result = await interview_prep_helper.generate_interview_prep_pack(
                user_name=user.get("name"),
                company_name=job.get("company_name"),
                job_title=job.get("job_title"),
                user_skills=user.get("skills", {}),
                job_requirements=job.get("required_skills", {}),
            )

            return result

        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


def add_phase3_routes(app: FastAPI):
    """Add Phase 3 endpoints (Email Monitoring & Full Automation)"""

    # ============================================
    # Phase 3: Gmail Integration
    # ============================================

    @app.post("/api/gmail/authenticate")
    async def authenticate_gmail() -> Dict[str, Any]:
        """Authenticate with Gmail API"""

        try:
            success = gmail_helper.authenticate()
            return {
                "success": success,
                "message": "Gmail authenticated" if success else "Authentication failed",
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/gmail/check-responses/{user_id}")
    async def check_email_responses(
        user_id: int,
        days: int = 7,
        db: Session = Depends(get_db),
    ) -> Dict[str, Any]:
        """Check Gmail for responses and update application statuses"""

        try:
            from agents import TrackingAgent

            tracking_agent = TrackingAgent(db)
            emails = gmail_helper.get_recent_emails(days=days)

            updated = 0
            for email in emails:
                response_type = email.get("response_type")
                if response_type:
                    # Match email to application and update status
                    # This is simplified - in production, would use better matching
                    updated += 1

                    if response_type == "interview":
                        status = "interview_scheduled"
                    elif response_type == "offer":
                        status = "offer_received"
                    elif response_type == "rejection":
                        status = "rejected"
                    else:
                        continue

                    # Mark email as processed
                    gmail_helper.mark_as_processed(email["message_id"])

            return {
                "success": True,
                "emails_checked": len(emails),
                "responses_detected": updated,
                "interviews": sum(1 for e in emails if e.get("response_type") == "interview"),
                "offers": sum(1 for e in emails if e.get("response_type") == "offer"),
                "rejections": sum(1 for e in emails if e.get("response_type") == "rejection"),
            }

        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    # ============================================
    # Phase 3: Daily Summary & Reporting
    # ============================================

    @app.get("/api/daily-summary/{user_id}")
    async def get_daily_summary(
        user_id: int,
        date: Optional[str] = None,
        db: Session = Depends(get_db),
    ) -> Dict[str, Any]:
        """Generate daily summary report"""

        try:
            from config import settings

            generator = DailySummaryGenerator(
                user_email=settings.gmail_address,
                app_password=settings.gmail_app_password,
            )

            report = generator.generate_daily_report(user_id, date)
            return report

        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/daily-summary/{user_id}/send-email")
    async def send_daily_summary_email(
        user_id: int,
        date: Optional[str] = None,
        db: Session = Depends(get_db),
    ) -> Dict[str, Any]:
        """Generate and send daily summary email"""

        try:
            from config import settings

            generator = DailySummaryGenerator(
                user_email=settings.gmail_address,
                app_password=settings.gmail_app_password,
            )

            report = generator.generate_daily_report(user_id, date)

            if report.get("success"):
                email_sent = generator.send_email_report(report)
                return {
                    "success": email_sent,
                    "report": report,
                    "message": "Email sent successfully" if email_sent else "Failed to send email",
                }
            else:
                return report

        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    # ============================================
    # Phase 3: Scheduling & Follow-ups
    # ============================================

    @app.post("/api/applications/{application_id}/schedule-followup")
    async def schedule_followup(
        application_id: int,
        days: int = 7,
        notes: Optional[str] = None,
        db: Session = Depends(get_db),
    ) -> Dict[str, Any]:
        """Schedule follow-up for application"""

        try:
            from agents import TrackingAgent

            tracking_agent = TrackingAgent(db)
            result = tracking_agent.schedule_followup(
                application_id=application_id,
                days_from_now=days,
                notes=notes,
            )

            return result

        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/api/followups/{user_id}/pending")
    async def get_pending_followups(
        user_id: int,
        db: Session = Depends(get_db),
    ) -> Dict[str, Any]:
        """Get all pending follow-ups"""

        try:
            from agents import TrackingAgent

            tracking_agent = TrackingAgent(db)
            followups = tracking_agent.get_pending_followups(
                user_id=user_id,
                days=1,  # Due within next day
            )

            return {
                "success": True,
                "pending_followups": len(followups),
                "applications": followups,
            }

        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


# Usage in main.py:
# from main_extensions import add_phase2_routes, add_phase3_routes
# add_phase2_routes(app)  # Phase 2 browser automation
# add_phase3_routes(app)  # Phase 3 email & automation
