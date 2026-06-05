"""
Gmail Monitoring Agent - Scan inbox for application responses and update records
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from sqlalchemy.orm import Session
from utils.database import Application, ApplicationStatus, Job
from utils.gmail_helper import gmail_helper

logger = logging.getLogger(__name__)


class GmailMonitoringAgent:
    """Monitors Gmail and synchronizes with the application database"""

    def __init__(self, db: Session):
        self.db = db

    async def scan_and_update(self, user_id: int, days: int = 7) -> Dict[str, Any]:
        """Scan Gmail for responses and update corresponding applications"""
        
        if not gmail_helper.service:
            if not gmail_helper.authenticate():
                return {"success": False, "message": "Gmail authentication failed"}
        
        emails = gmail_helper.get_recent_emails(days=days)
        updates_made = 0
        
        for email in emails:
            response_type = email.get("response_type")
            if not response_type:
                continue
                
            # Attempt to find the matching application
            # 1. By company name in subject/body
            # 2. By recruiter email (if we have it from tracking)
            
            application = self._find_matching_application(user_id, email)
            
            if application:
                self._update_application_status(application, response_type, email)
                gmail_helper.mark_as_processed(email["message_id"])
                updates_made += 1
                
        return {
            "success": True,
            "emails_scanned": len(emails),
            "updates_made": updates_made
        }

    def _find_matching_application(self, user_id: int, email: Dict[str, Any]) -> Optional[Application]:
        """Find an application record that matches the email content"""
        
        # Get all non-closed applications for user
        active_apps = self.db.query(Application).join(Job).filter(
            Application.user_id == user_id,
            Application.status.notin_([
                ApplicationStatus.REJECTED, 
                ApplicationStatus.OFFER_RECEIVED,
                ApplicationStatus.CLOSED
            ])
        ).all()
        
        text_to_search = (email["subject"] + " " + email["body_preview"]).lower()
        
        for app in active_apps:
            company_name = app.job.company_name.lower()
            if company_name in text_to_search:
                return app
                
        return None

    def _update_application_status(self, application: Application, response_type: str, email: Dict[str, Any]):
        """Update application status based on detected response"""
        
        if response_type == "interview":
            application.status = ApplicationStatus.INTERVIEW_SCHEDULED
            application.interview_scheduled = True
        elif response_type == "offer":
            application.status = ApplicationStatus.OFFER_RECEIVED
        elif response_type == "rejection":
            application.status = ApplicationStatus.REJECTED
            
        application.response_received = True
        application.response_date = datetime.utcnow()
        application.notes = (application.notes or "") + f"\n[{datetime.utcnow().date()}] Detected {response_type} via email: {email['subject']}"
        
        self.db.commit()
        logger.info(f"✅ Updated application {application.id} to {application.status} based on email")
        
        # If interview, attempt to create calendar event
        if response_type == "interview":
            self.create_calendar_event(application, email)

    def create_calendar_event(self, application: Application, email: Dict[str, Any]):
        """Stub for Google Calendar integration - Creates an event for the detected interview"""
        
        try:
            # Extract date/time from email body using LLM or Regex
            # For now, we'll log it as a placeholder
            logger.info(f"📅 [CALENDAR STUB] Creating interview event for {application.job.company_name}")
            logger.info(f"Details: {email['subject']} | Recruiter: {email['from']}")
            
            # In Phase 4, this would call google-api-python-client calendar.events().insert()
            application.notes = (application.notes or "") + f"\n[CALENDAR] Event detected. Please confirm date manually."
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error creating calendar event: {e}")
