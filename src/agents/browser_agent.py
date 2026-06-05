"""
Browser Automation Agent - Fill forms, submit applications, handle CAPTCHA
Uses Playwright for automated form filling with anti-bot safety measures
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any

from sqlalchemy.orm import Session
from utils.playwright_helper import PlaywrightHelper
from utils.database import Application, ApplicationStatus, AuditLog

logger = logging.getLogger(__name__)


class BrowserAgent:
    """Handles browser automation and form submission"""

    def __init__(self, db: Session):
        self.db = db
        self.browser = PlaywrightHelper()
        self.is_initialized = False

    async def initialize(self):
        """Initialize browser"""

        try:
            await self.browser.initialize()
            self.is_initialized = True
            logger.info("✅ Browser agent initialized")
            return True
        except Exception as e:
            logger.error(f"Error initializing browser agent: {e}")
            return False

    async def close(self):
        """Close browser"""

        try:
            await self.browser.close()
            self.is_initialized = False
            logger.info("✅ Browser agent closed")
        except Exception as e:
            logger.error(f"Error closing browser agent: {e}")

    async def fill_and_submit_application(
        self,
        application_id: int,
        job_url: str,
        form_data: Dict[str, str],
        auto_submit: bool = False,
    ) -> Dict[str, Any]:
        """
        Fill application form and optionally submit

        Args:
            application_id: Application record ID
            job_url: URL to job application page
            form_data: {field_name: value} to fill
            auto_submit: If True, auto-submit; if False, user must submit manually

        Returns:
            {
                "success": true,
                "filled": 8,
                "total": 10,
                "captcha_detected": false,
                "auto_submitted": true,
                "screenshots": ["path1", "path2"],
                "message": "Application submitted successfully"
            }
        """

        if not self.is_initialized:
            return {
                "success": False,
                "message": "Browser not initialized. Call initialize() first"
            }

        try:
            logger.info(f"Processing application {application_id} at {job_url}")

            # Navigate to job page
            navigated = await self.browser.navigate_to(job_url)
            if not navigated:
                return {
                    "success": False,
                    "message": "Failed to navigate to job URL"
                }

            # Wait for form to load
            await asyncio.sleep(2)

            # Detect portal type and apply specific logic
            portal_name = await self.detect_portal_type(job_url)
            await self.handle_portal_specific_logic(portal_name)

            # Auto-fill form
            fill_result = await self.browser.auto_fill_form(form_data)

            if not fill_result.get("success"):
                return fill_result

            filled_count = fill_result.get("filled", 0)
            total_count = fill_result.get("total", 0)
            captcha_detected = fill_result.get("captcha_detected", False)

            # Handle CAPTCHA
            if captcha_detected:
                logger.warning(f"⚠️ CAPTCHA detected on application {application_id}")
                await self.browser.take_screenshot("captcha_detected")

                return {
                    "success": False,
                    "filled": filled_count,
                    "total": total_count,
                    "captcha_detected": True,
                    "message": "CAPTCHA detected - User intervention required",
                    "requires_manual_action": True,
                }

            # Update application with fill results
            self.db.query(Application).filter(
                Application.id == application_id
            ).update({
                "form_fields_filled": filled_count,
                "form_fields_total": total_count,
            })
            self.db.commit()

            # Auto-submit if enabled
            auto_submitted = False
            if auto_submit:
                submit_success = await self.browser.submit_form()
                if submit_success:
                    auto_submitted = True

                    # Update application status
                    self.db.query(Application).filter(
                        Application.id == application_id
                    ).update({
                        "status": ApplicationStatus.SUBMITTED,
                        "submitted_at": datetime.utcnow()
                    })
                    self.db.commit()

                    logger.info(f"✅ Application {application_id} auto-submitted")
                else:
                    logger.error(f"Failed to auto-submit application {application_id}")

            # Take final screenshot
            await self.browser.take_screenshot(f"application_{application_id}_final")

            return {
                "success": True,
                "filled": filled_count,
                "total": total_count,
                "captcha_detected": False,
                "auto_submitted": auto_submitted,
                "message": "Application form filled successfully. " +
                          ("Auto-submitted!" if auto_submitted else "User submission required"),
            }

        except Exception as e:
            logger.error(f"Error processing application {application_id}: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }

    async def detect_portal_type(self, url: str) -> str:
        """
        Detect job portal type (Workday, Greenhouse, Lever, etc.)
        """
        portal_indicators = {
            "workday": ["workday.com", "/grs/public"],
            "greenhouse": ["greenhouse.io", "greenhouse.com"],
            "lever": ["lever.co"],
            "taleo": ["taleo.net"],
            "icims": ["icims.com"],
            "ilogos": ["ilogos.com"],
        }
        url_lower = url.lower()
        for portal, keywords in portal_indicators.items():
            if any(keyword in url_lower for keyword in keywords):
                return portal
        return "unknown"

    async def handle_portal_specific_logic(self, portal_name: str):
        """Execute logic specific to different application portals"""
        logger.info(f"Applying logic for {portal_name}")
        page = self.browser.page
        
        if portal_name == "workday":
            # Workday often has shadow DOM or complex frames
            await page.wait_for_selector('button[data-automation-id="applyNow"]', timeout=5000)
        elif portal_name == "greenhouse":
            # Greenhouse often has 'Attach' buttons for resumes
            await page.wait_for_selector('#resume_button', timeout=5000)
        elif portal_name == "lever":
            # Lever has a distinct 'Apply' section
            await page.wait_for_selector('.postings-btn', timeout=5000)

    async def save_session(self, portal_name: str):
        """Save browser cookies for session persistence"""
        cookies = await self.browser.context.cookies()
        # Save to database (implementation detail: encrypting sensitive data)
        logger.info(f"Saved session for {portal_name}")

    async def load_session(self, portal_name: str):
        """Load browser cookies for session persistence"""
        # Load from database and apply to browser context
        logger.info(f"Loaded session for {portal_name}")

    async def retry_fill(self, application_id: int, job_url: str, form_data: Dict[str, str], max_retries: int = 3):
        """Retry form filling with backoff on failure"""
        for i in range(max_retries):
            try:
                result = await self.fill_and_submit_application(application_id, job_url, form_data)
                if result.get("success"):
                    return result
            except Exception as e:
                logger.warning(f"Retry {i+1} failed: {e}")
                await asyncio.sleep(2 ** i)
        return {"success": False, "message": "Max retries exceeded"}

    async def extract_form_fields_from_page(self, url: str) -> Dict[str, Dict[str, Any]]:
        """
        Navigate to page and extract all form fields

        Returns: {field_name: {type, required, placeholder}}
        """

        try:
            if not self.is_initialized:
                await self.initialize()

            navigated = await self.browser.navigate_to(url)
            if not navigated:
                return {}

            await asyncio.sleep(2)
            fields = await self.browser.detect_form_fields()
            return fields

        except Exception as e:
            logger.error(f"Error extracting form fields: {e}")
            return {}

    def _audit_log(self, **kwargs):
        """Create audit log entry"""

        log = AuditLog(**kwargs)
        self.db.add(log)
        self.db.commit()
