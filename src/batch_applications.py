"""
Batch Applications Processor
Process 25 job applications in sequence with timing tracking
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from utils.database import get_db_context, Job, User, Application
from agents import (
    ProfileAgent, JobAnalysisAgent, ResumeAgent,
    MatchAgent, WritingAgent, TrackingAgent
)
from agents.browser_agent import BrowserAgent
from utils.pdf_generator import PDFGenerator
from utils.excel_generator import ExcelGenerator
from config import settings

logger = logging.getLogger(__name__)


class BatchApplicationProcessor:
    """Process batch of job applications"""

    def __init__(self):
        self.pdf_generator = PDFGenerator(settings.applications_dir)
        self.excel_generator = ExcelGenerator(settings.tracking_dir)
        self.browser_agent: Optional[BrowserAgent] = None

    async def process_batch(
        self,
        user_id: int,
        job_ids: List[int],
        auto_fill: bool = True,
        auto_submit: bool = False,
    ) -> Dict[str, Any]:
        """
        Process batch of applications

        Args:
            user_id: User ID
            job_ids: List of job IDs to process
            auto_fill: Enable form auto-fill (Phase 2)
            auto_submit: Enable auto-submit (Phase 3)

        Returns:
            {
                "total": 25,
                "successful": 23,
                "failed": 2,
                "total_time": 1234.5,
                "time_per_application": 49.4,
                "applications": [...],
                "pdf_count": 23,
                "excel_generated": true
            }
        """

        start_time = time.time()
        applications = []
        failed_jobs = []

        logger.info(f"🚀 Starting batch processing: {len(job_ids)} applications")

        # Initialize browser if auto-fill enabled
        if auto_fill:
            self.browser_agent = BrowserAgent(next(get_db_context()))
            await self.browser_agent.initialize()

        try:
            # Process each job
            for idx, job_id in enumerate(job_ids[:25], 1):  # Max 25
                app_start = time.time()

                app_result = await self._process_single_application(
                    user_id=user_id,
                    job_id=job_id,
                    auto_fill=auto_fill,
                    auto_submit=auto_submit,
                )

                app_time = time.time() - app_start

                if app_result.get("success"):
                    applications.append({
                        **app_result,
                        "processing_time": app_time,
                    })
                    logger.info(
                        f"✅ [{idx}/{len(job_ids)}] Application {job_id} "
                        f"processed in {app_time:.1f}s"
                    )
                else:
                    failed_jobs.append(job_id)
                    logger.error(
                        f"❌ [{idx}/{len(job_ids)}] Application {job_id} failed"
                    )

                # Rate limiting to avoid bot detection
                if idx < len(job_ids):
                    await asyncio.sleep(2)  # 2 second delay between apps

        finally:
            # Close browser
            if self.browser_agent:
                await self.browser_agent.close()

        # Generate batch reports
        total_time = time.time() - start_time
        successful = len(applications)
        failed = len(failed_jobs)

        # Generate Excel trackers
        excel_result = self.excel_generator.generate_daily_tracker(
            applications=applications,
            date=datetime.utcnow().strftime("%Y_%m_%d"),
        )

        master_result = self.excel_generator.generate_master_tracker(
            applications=[...],  # Get all from DB
        )

        return {
            "total": len(job_ids),
            "successful": successful,
            "failed": failed,
            "success_rate": round((successful / len(job_ids) * 100) if job_ids else 0, 1),
            "total_time_seconds": round(total_time, 1),
            "time_per_application": round(total_time / len(job_ids) if job_ids else 0, 1),
            "failed_job_ids": failed_jobs,
            "applications": applications,
            "pdf_count": sum(1 for app in applications if app.get("pdf_generated")),
            "daily_excel_generated": excel_result.get("success"),
            "master_excel_updated": master_result.get("success"),
            "phase": "Phase 2 (Auto-fill)" if auto_fill else "Phase 1 (Manual)",
            "message": f"✅ Batch complete: {successful}/{len(job_ids)} successful in {total_time/60:.1f} minutes",
        }

    async def _process_single_application(
        self,
        user_id: int,
        job_id: int,
        auto_fill: bool = True,
        auto_submit: bool = False,
    ) -> Dict[str, Any]:
        """Process single application"""

        with get_db_context() as db:
            try:
                # Get user and job
                user = db.query(User).filter(User.id == user_id).first()
                job = db.query(Job).filter(Job.id == job_id).first()

                if not user or not job:
                    return {"success": False, "message": "User or job not found"}

                # Initialize agents
                match_agent = MatchAgent(db)
                resume_agent = ResumeAgent(db)
                writing_agent = WritingAgent(db)
                tracking_agent = TrackingAgent(db)

                # 1. Calculate match (5s)
                match_result = await match_agent.calculate_match(user_id, job_id)
                match_score = match_result.get("match_score", 0)

                # 2. Customize resume (10s)
                resume_result = await resume_agent.customize_resume(
                    user_id=user_id,
                    job_id=job_id,
                    mode="balanced",
                )

                # 3. Generate cover letter (15s)
                cover_letter = await writing_agent.generate_cover_letter(
                    user_id=user_id,
                    job_id=job_id,
                )

                # 4. Create application record
                app_result = tracking_agent.create_application(
                    user_id=user_id,
                    job_id=job_id,
                    match_score=match_score,
                )

                application_id = app_result.get("application_id")

                # 5. Auto-fill form if enabled (Phase 2)
                form_data = {}
                captcha_detected = False
                auto_submitted = False

                if auto_fill and self.browser_agent and job.job_url:
                    form_result = await self.browser_agent.fill_and_submit_application(
                        application_id=application_id,
                        job_url=job.job_url,
                        form_data=form_data,
                        auto_submit=auto_submit,
                    )

                    captcha_detected = form_result.get("captcha_detected", False)
                    auto_submitted = form_result.get("auto_submitted", False)

                # 6. Generate PDF
                pdf_result = self.pdf_generator.generate_application_pdf(
                    user_name=user.name,
                    company_name=job.company_name,
                    job_title=job.job_title,
                    application_data={
                        "company": {
                            "name": job.company_name,
                            "industry": job.company_industry,
                        },
                        "job": {
                            "title": job.job_title,
                            "location": job.location,
                            "job_type": job.job_type,
                        },
                        "match": {
                            "overall_score": match_score,
                            "skill_match": match_result.get("skill_match_percentage"),
                            "recommendation": match_result.get("recommendation"),
                        },
                        "cover_letter": cover_letter.get("cover_letter", ""),
                        "tracking": {
                            "tracking_id": app_result.get("tracking_id"),
                            "status": "pending",
                        },
                    },
                )

                return {
                    "success": True,
                    "application_id": application_id,
                    "job_id": job_id,
                    "company": job.company_name,
                    "job_title": job.job_title,
                    "match_score": match_score,
                    "pdf_generated": pdf_result.get("success"),
                    "pdf_path": pdf_result.get("pdf_path"),
                    "form_filled": not captcha_detected,
                    "captcha_detected": captcha_detected,
                    "auto_submitted": auto_submitted,
                    "status": "submitted" if auto_submitted else "pending",
                }

            except Exception as e:
                logger.error(f"Error processing application {job_id}: {e}")
                return {
                    "success": False,
                    "job_id": job_id,
                    "message": str(e),
                }


async def run_batch_processing(
    user_id: int,
    job_ids: List[int],
    phase: str = "phase1",  # phase1, phase2, phase3
):
    """
    Run batch processing with different automation levels

    Phases:
    - phase1: Manual submission (user clicks submit)
    - phase2: Auto-fill + manual submit
    - phase3: Full auto (fill + submit)
    """

    processor = BatchApplicationProcessor()

    auto_fill = phase in ["phase2", "phase3"]
    auto_submit = phase == "phase3"

    result = await processor.process_batch(
        user_id=user_id,
        job_ids=job_ids,
        auto_fill=auto_fill,
        auto_submit=auto_submit,
    )

    return result


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) < 2:
        print("Usage: python batch_applications.py <user_id> [job_ids...] [--phase phase2]")
        sys.exit(1)

    user_id = int(sys.argv[1])
    job_ids = [int(id) for id in sys.argv[2:] if id.isdigit()]

    phase = "phase2" if "--phase" not in sys.argv else sys.argv[sys.argv.index("--phase") + 1]

    # Run async
    asyncio.run(run_batch_processing(user_id, job_ids, phase))
