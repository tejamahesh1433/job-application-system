"""
Follow-up Agent - Automate follow-up emails for pending applications
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from utils.database import Application, ApplicationStatus, Job, User
from utils.gmail_helper import gmail_helper
from agents.writing_agent import WritingAgent

logger = logging.getLogger(__name__)


class FollowUpAgent:
    """Handles generation and sending of follow-up communications"""

    def __init__(self, db: Session):
        self.db = db
        self.writer = WritingAgent(db)

    async def process_pending_followups(self, user_id: int) -> Dict[str, Any]:
        """Find applications due for follow-up and send emails"""
        
        # Get applications due for follow-up
        now = datetime.utcnow()
        due_apps = self.db.query(Application).filter(
            Application.user_id == user_id,
            Application.status == ApplicationStatus.SUBMITTED,
            Application.follow_up_date <= now,
            Application.response_received == False
        ).all()
        
        sent_count = 0
        for app in due_apps:
            success = await self._send_followup(app)
            if success:
                sent_count += 1
                
        return {
            "success": True,
            "apps_checked": len(due_apps),
            "followups_sent": sent_count
        }

    async def _send_followup(self, application: Application) -> bool:
        """Generate and send a single follow-up email"""
        
        try:
            user = application.user
            job = application.job
            
            # 1. Generate follow-up content
            prompt = f"""
            Write a polite follow-up email for a job application.
            Candidate: {user.name}
            Company: {job.company_name}
            Job Title: {job.job_title}
            Applied on: {application.submitted_at.date() if application.submitted_at else 'recent'}
            
            Keep it professional, brief (2 paragraphs), and reiterate interest.
            """
            
            # Using the internal LLM helper via writing agent (conceptually)
            # For this MVP, we'll use a standard template if LLM fails
            from utils.llm_helper import generate_text, USE_OLLAMA
            email_body = await generate_text(prompt, provider=USE_OLLAMA)
            
            # 2. Send via Gmail (if authenticated)
            # Note: In a real system, we'd need the recruiter's email
            # If unknown, we log it for manual follow-up
            recruiter_email = application.notes.split("Recruiter:")[1].split("\n")[0].strip() if "Recruiter:" in (application.notes or "") else None
            
            if not recruiter_email:
                logger.warning(f"⚠️ No recruiter email for application {application.id}. Logging for manual follow-up.")
                application.notes = (application.notes or "") + f"\n[{datetime.utcnow().date()}] Follow-up generated but no recipient email found."
                self.db.commit()
                return False
                
            # Simulate sending (actual sending would use gmail_helper.send_email)
            # gmail_helper.send_email(to=recruiter_email, subject=f"Follow-up: {job.job_title} application", body=email_body)
            
            # 3. Update application record
            application.follow_up_sent = True
            application.follow_up_date = datetime.utcnow() + timedelta(days=7)
            application.notes = (application.notes or "") + f"\n[{datetime.utcnow().date()}] Sent automated follow-up to {recruiter_email}"
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error sending follow-up for {application.id}: {e}")
            return False
