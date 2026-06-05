"""
Reporting Agent - Generate daily summaries and analytics reports
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from sqlalchemy.orm import Session
from utils.database import Application, User, Job
from utils.excel_generator import ExcelGenerator
from agents.tracking_agent import TrackingAgent

logger = logging.getLogger(__name__)


class ReportingAgent:
    """Generates insights and reports from application data"""

    def __init__(self, db: Session):
        self.db = db
        self.excel = ExcelGenerator()
        self.tracker = TrackingAgent(db)

    async def generate_daily_summary(self, user_id: int) -> Dict[str, Any]:
        """Generate a summary of today's activities and overall stats"""
        
        today = datetime.utcnow().date()
        
        # 1. Get today's applications
        today_apps = self.db.query(Application).filter(
            Application.user_id == user_id,
            Application.created_at >= today
        ).all()
        
        # 2. Get overall stats
        stats = self.tracker.get_application_stats(user_id)
        
        # 3. Generate Markdown summary
        summary_md = f"""
# Daily Job Application Summary - {today}

## Today's Activity
- **New Applications**: {len(today_apps)}
- **Companies**: {', '.join([a.job.company_name for a in today_apps]) or 'None'}

## Pipeline Health
- **Total Applications**: {stats['total_applications']}
- **Interview Rate**: {stats['interview_rate']}%
- **Response Rate**: {stats['response_rate']}%
- **Offers**: {stats['offers']}

## Action Items
- **Pending Follow-ups**: {len(self.tracker.get_pending_followups(user_id, days=1))}
        """
        
        # 4. Update Master Excel
        all_apps = self.tracker.get_applications(user_id, limit=1000)
        excel_result = self.excel.generate_master_tracker(all_apps)
        
        return {
            "summary_md": summary_md,
            "stats": stats,
            "excel_path": excel_result.get("filepath"),
            "success": True
        }
