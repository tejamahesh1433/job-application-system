"""
Daily Summary Report Generator
Creates daily email report with statistics and follow-ups needed
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

from sqlalchemy.orm import Session
from utils.database import get_db_context, Application, User, Job, ApplicationStatus

logger = logging.getLogger(__name__)


class DailySummaryGenerator:
    """Generate daily summary reports"""

    def __init__(self, user_email: str, app_password: str):
        self.user_email = user_email
        self.app_password = app_password

    def generate_daily_report(self, user_id: int, date: str = None) -> Dict[str, Any]:
        """
        Generate daily summary report

        Args:
            user_id: User ID
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            {
                "date": "2024-01-15",
                "total_applications": 25,
                "submitted": 24,
                "responses": 4,
                "interviews": 2,
                "rejections": 1,
                "pending": 21,
                "response_rate": 16.7,
                "interview_rate": 8.3,
                "followups_needed": 3,
                "best_match": {...},
                "worst_match": {...},
                "report_html": "..."
            }
        """

        if not date:
            date = datetime.utcnow().strftime("%Y-%m-%d")

        with get_db_context() as db:
            try:
                # Get user
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    return {"success": False, "message": "User not found"}

                # Get today's applications
                start_date = datetime.strptime(date, "%Y-%m-%d")
                end_date = start_date + timedelta(days=1)

                apps = db.query(Application).filter(
                    Application.user_id == user_id,
                    Application.created_at >= start_date,
                    Application.created_at < end_date,
                ).all()

                # Calculate stats
                total = len(apps)
                submitted = sum(1 for a in apps if a.submitted_at)
                responses = sum(1 for a in apps if a.response_received)
                interviews = sum(1 for a in apps if a.interview_scheduled)
                offers = sum(1 for a in apps if a.status == ApplicationStatus.OFFER_RECEIVED)
                rejections = sum(1 for a in apps if a.status == ApplicationStatus.REJECTED)
                pending = total - submitted

                # Get best and worst matches
                best_match = max((a for a in apps if a.match_score),
                               key=lambda x: x.match_score, default=None)
                worst_match = min((a for a in apps if a.match_score),
                                key=lambda x: x.match_score, default=None)

                # Get follow-ups needed
                followups_needed = [
                    a for a in apps
                    if a.follow_up_date and a.follow_up_date <= datetime.utcnow()
                    and not a.response_received
                ]

                # Calculate rates
                response_rate = (responses / submitted * 100) if submitted > 0 else 0
                interview_rate = (interviews / submitted * 100) if submitted > 0 else 0

                # Generate HTML report
                html_report = self._generate_html_report(
                    user_name=user.name,
                    date=date,
                    total=total,
                    submitted=submitted,
                    responses=responses,
                    interviews=interviews,
                    offers=offers,
                    rejections=rejections,
                    response_rate=response_rate,
                    interview_rate=interview_rate,
                    applications=apps,
                    followups=followups_needed,
                )

                return {
                    "success": True,
                    "date": date,
                    "total_applications": total,
                    "submitted": submitted,
                    "pending": pending,
                    "responses": responses,
                    "interviews": interviews,
                    "offers": offers,
                    "rejections": rejections,
                    "response_rate": round(response_rate, 1),
                    "interview_rate": round(interview_rate, 1),
                    "followups_needed": len(followups_needed),
                    "best_match": {
                        "company": best_match.job.company_name if best_match else None,
                        "score": best_match.match_score if best_match else None,
                    } if best_match else None,
                    "report_html": html_report,
                }

            except Exception as e:
                logger.error(f"Error generating daily report: {e}")
                return {"success": False, "message": str(e)}

    def send_email_report(self, report: Dict[str, Any]) -> bool:
        """Send email report"""

        try:
            if not report.get("success"):
                return False

            subject = f"Job Applications Daily Summary - {report['date']}"
            html_content = report.get("report_html", "")

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.user_email
            msg["To"] = self.user_email

            msg.attach(MIMEText(html_content, "html"))

            # Send via Gmail SMTP
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.user_email, self.app_password)
                server.send_message(msg)

            logger.info(f"✅ Daily summary email sent for {report['date']}")
            return True

        except Exception as e:
            logger.error(f"Error sending email report: {e}")
            return False

    @staticmethod
    def _generate_html_report(
        user_name: str,
        date: str,
        total: int,
        submitted: int,
        responses: int,
        interviews: int,
        offers: int,
        rejections: int,
        response_rate: float,
        interview_rate: float,
        applications: List,
        followups: List,
    ) -> str:
        """Generate HTML report"""

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #1a1a1a; }}
                .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 20px 0; }}
                .stat-box {{ background: #f0f0f0; padding: 15px; border-radius: 5px; text-align: center; }}
                .stat-number {{ font-size: 24px; font-weight: bold; color: #0066cc; }}
                .stat-label {{ font-size: 12px; color: #666; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #0066cc; color: white; }}
                .green {{ color: #00aa00; }}
                .red {{ color: #cc0000; }}
                .yellow {{ color: #ff9900; }}
            </style>
        </head>
        <body>
            <h1>📊 Job Applications Daily Summary</h1>
            <p>Date: {date} | User: {user_name}</p>

            <div class="stats">
                <div class="stat-box">
                    <div class="stat-number">{total}</div>
                    <div class="stat-label">Total Applications</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{submitted}</div>
                    <div class="stat-label">Submitted</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number green">{responses}</div>
                    <div class="stat-label">Responses ({response_rate:.1f}%)</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number green">{interviews}</div>
                    <div class="stat-label">Interviews ({interview_rate:.1f}%)</div>
                </div>
            </div>

            <h2>📋 Status Breakdown</h2>
            <table>
                <tr>
                    <th>Status</th>
                    <th>Count</th>
                </tr>
                <tr>
                    <td>Submitted</td>
                    <td>{submitted}</td>
                </tr>
                <tr>
                    <td class="green">Responses</td>
                    <td class="green">{responses}</td>
                </tr>
                <tr>
                    <td class="green">Interview Scheduled</td>
                    <td class="green">{interviews}</td>
                </tr>
                <tr>
                    <td class="green">Offers</td>
                    <td class="green">{offers}</td>
                </tr>
                <tr>
                    <td class="red">Rejections</td>
                    <td class="red">{rejections}</td>
                </tr>
            </table>

            <h2>⏰ Follow-ups Needed</h2>
            <p>{len(followups)} application(s) need follow-up today</p>

            <h2>💡 Key Insights</h2>
            <ul>
                <li>Response rate: {response_rate:.1f}% (target: 25%)</li>
                <li>Interview rate: {interview_rate:.1f}% (target: 10%)</li>
                <li>Pending submissions: {total - submitted}</li>
            </ul>

            <hr>
            <p style="color: #999; font-size: 12px;">
                Generated by Job Application Automation System
            </p>
        </body>
        </html>
        """

        return html


if __name__ == "__main__":
    # Example usage
    generator = DailySummaryGenerator(
        user_email="your_email@gmail.com",
        app_password="your_app_password",
    )

    report = generator.generate_daily_report(user_id=1)

    if report.get("success"):
        print(f"✅ Daily summary generated")
        print(f"   Total: {report['total_applications']}")
        print(f"   Submitted: {report['submitted']}")
        print(f"   Responses: {report['responses']}")

        # Send email
        generator.send_email_report(report)
