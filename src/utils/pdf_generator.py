"""
PDF Generator - Create professional 10-section application PDFs
Uses ReportLab for clean, ATS-friendly output
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors

logger = logging.getLogger(__name__)


class PDFGenerator:
    """Generates professional PDF documents"""

    def __init__(self, output_dir: str = "applications"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._add_custom_styles()

    def _add_custom_styles(self):
        """Add custom paragraph styles"""

        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=12,
            fontName='Helvetica-Bold'
        ))

        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#333333'),
            spaceAfter=6,
            fontName='Helvetica-Bold'
        ))

    def generate_application_pdf(
        self,
        user_name: str,
        company_name: str,
        job_title: str,
        application_data: Dict[str, Any],
        output_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate 10-section application PDF

        Sections:
        1. Company Information
        2. Job Details
        3. Match Analysis
        4. Resume Customization
        5. Form Fields
        6. Cover Letter
        7. Interview Preparation
        8. Submission Details
        9. Tracking Information
        10. System Metadata
        """

        try:
            if not output_filename:
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                output_filename = f"{company_name}_{job_title}_{timestamp}.pdf"

            output_path = self.output_dir / output_filename

            # Create PDF
            doc = SimpleDocTemplate(
                str(output_path),
                pagesize=letter,
                rightMargin=0.5*inch,
                leftMargin=0.5*inch,
                topMargin=0.5*inch,
                bottomMargin=0.5*inch,
            )

            story = []

            # Title
            story.append(Paragraph(
                f"Application: {company_name} - {job_title}",
                self.styles['CustomTitle']
            ))
            story.append(Paragraph(
                f"Submitted by: {user_name} | {datetime.utcnow().strftime('%Y-%m-%d')}",
                self.styles['Normal']
            ))
            story.append(Spacer(1, 0.2*inch))

            # Section 1: Company Information
            story.extend(self._build_company_section(application_data.get("company", {})))
            story.append(Spacer(1, 0.1*inch))

            # Section 2: Job Details
            story.extend(self._build_job_section(application_data.get("job", {})))
            story.append(Spacer(1, 0.1*inch))

            # Section 3: Match Analysis
            story.extend(self._build_match_section(application_data.get("match", {})))
            story.append(Spacer(1, 0.1*inch))

            # Section 4: Resume Customization
            story.extend(self._build_resume_section(application_data.get("resume", {})))
            story.append(Spacer(1, 0.1*inch))

            # Section 5: Form Fields
            story.extend(self._build_form_section(application_data.get("form_fields", {})))
            story.append(Spacer(1, 0.1*inch))

            # Section 6: Cover Letter
            story.extend(self._build_cover_letter_section(application_data.get("cover_letter", "")))
            story.append(Spacer(1, 0.1*inch))

            # Section 7: Interview Preparation
            story.extend(self._build_interview_prep_section(application_data.get("interview_prep", {})))
            story.append(Spacer(1, 0.1*inch))

            # Section 8: Submission Details
            story.extend(self._build_submission_section(application_data.get("submission", {})))
            story.append(Spacer(1, 0.1*inch))

            # Section 9: Tracking Info
            story.extend(self._build_tracking_section(application_data.get("tracking", {})))
            story.append(Spacer(1, 0.1*inch))

            # Section 10: System Metadata
            story.extend(self._build_metadata_section(application_data.get("metadata", {})))
            story.append(Spacer(1, 0.1*inch))

            # Build PDF
            doc.build(story)

            logger.info(f"✅ PDF generated: {output_path}")

            return {
                "success": True,
                "pdf_path": str(output_path),
                "filename": output_filename,
                "file_size_kb": output_path.stat().st_size / 1024,
            }

        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }

    @staticmethod
    def _build_company_section(company_data: Dict[str, Any]) -> list:
        """Build company information section"""

        styles = getSampleStyleSheet()
        section = [Paragraph("1. Company Information", styles['Heading2'])]

        section.append(Paragraph(
            f"<b>Name:</b> {company_data.get('name', 'N/A')}", styles['Normal']
        ))
        section.append(Paragraph(
            f"<b>Website:</b> {company_data.get('website', 'N/A')}", styles['Normal']
        ))
        section.append(Paragraph(
            f"<b>Industry:</b> {company_data.get('industry', 'N/A')}", styles['Normal']
        ))

        return section

    @staticmethod
    def _build_job_section(job_data: Dict[str, Any]) -> list:
        """Build job details section"""

        styles = getSampleStyleSheet()
        section = [Paragraph("2. Job Details", styles['Heading2'])]

        section.append(Paragraph(
            f"<b>Title:</b> {job_data.get('title', 'N/A')}", styles['Normal']
        ))
        section.append(Paragraph(
            f"<b>Location:</b> {job_data.get('location', 'N/A')}", styles['Normal']
        ))
        section.append(Paragraph(
            f"<b>Type:</b> {job_data.get('job_type', 'N/A')}", styles['Normal']
        ))

        return section

    @staticmethod
    def _build_match_section(match_data: Dict[str, Any]) -> list:
        """Build match analysis section"""

        styles = getSampleStyleSheet()
        section = [Paragraph("3. Match Analysis", styles['Heading2'])]

        section.append(Paragraph(
            f"<b>Overall Score:</b> {match_data.get('overall_score', 0)}%", styles['Normal']
        ))
        section.append(Paragraph(
            f"<b>Skills Match:</b> {match_data.get('skill_match', 0)}%", styles['Normal']
        ))
        section.append(Paragraph(
            f"<b>Recommendation:</b> {match_data.get('recommendation', 'N/A')}", styles['Normal']
        ))

        return section

    @staticmethod
    def _build_resume_section(resume_data: Dict[str, Any]) -> list:
        """Build resume customization section"""
        styles = getSampleStyleSheet()
        section = [Paragraph("4. Resume Customization", styles['Heading2'])]
        section.append(Paragraph(f"<b>Mode:</b> {resume_data.get('mode', 'N/A')}", styles['Normal']))
        section.append(Paragraph(f"<b>ATS Score:</b> {resume_data.get('ats_score', 0)}", styles['Normal']))
        section.append(Paragraph(f"<b>Changes Made:</b>", styles['Normal']))
        for change in resume_data.get("changes_made", []):
            section.append(Paragraph(f"- {change}", styles['Normal']))
        return section

    @staticmethod
    def _build_form_section(form_data: Dict[str, Any]) -> list:
        """Build form fields section"""
        styles = getSampleStyleSheet()
        section = [Paragraph("5. Form Fields", styles['Heading2'])]
        for question, answer in form_data.get("answers", {}).items():
            section.append(Paragraph(f"<b>Q: {question}</b>", styles['Normal']))
            section.append(Paragraph(f"A: {answer}", styles['Normal']))
            section.append(Spacer(1, 0.05*inch))
        return section

    @staticmethod
    def _build_cover_letter_section(cover_letter: str) -> list:
        """Build cover letter section"""

        styles = getSampleStyleSheet()
        section = [Paragraph("6. Cover Letter", styles['Heading2'])]
        section.append(Paragraph(cover_letter or "N/A", styles['Normal']))
        return section

    @staticmethod
    def _build_interview_prep_section(prep_data: Dict[str, Any]) -> list:
        """Build interview preparation section"""
        styles = getSampleStyleSheet()
        section = [Paragraph("7. Interview Preparation", styles['Heading2'])]
        if "potential_questions" in prep_data:
            section.append(Paragraph("<b>Potential Questions:</b>", styles['Normal']))
            for q in prep_data["potential_questions"]:
                section.append(Paragraph(f"- {q}", styles['Normal']))
        return section

    @staticmethod
    def _build_submission_section(submission_data: Dict[str, Any]) -> list:
        """Build submission details section"""
        styles = getSampleStyleSheet()
        section = [Paragraph("8. Submission Details", styles['Heading2'])]
        section.append(Paragraph(f"<b>Portal:</b> {submission_data.get('portal', 'N/A')}", styles['Normal']))
        section.append(Paragraph(f"<b>Method:</b> {submission_data.get('method', 'N/A')}", styles['Normal']))
        return section

    @staticmethod
    def _build_tracking_section(tracking_data: Dict[str, Any]) -> list:
        """Build tracking information section"""

        styles = getSampleStyleSheet()
        section = [Paragraph("9. Tracking Information", styles['Heading2'])]

        section.append(Paragraph(
            f"<b>Tracking ID:</b> {tracking_data.get('tracking_id', 'N/A')}", styles['Normal']
        ))
        section.append(Paragraph(
            f"<b>Status:</b> {tracking_data.get('status', 'N/A')}", styles['Normal']
        ))
        section.append(Paragraph(
            f"<b>Generated:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']
        ))

        return section

    @staticmethod
    def _build_metadata_section(metadata_data: Dict[str, Any]) -> list:
        """Build system metadata section"""
        styles = getSampleStyleSheet()
        section = [Paragraph("10. System Metadata", styles['Heading2'])]
        section.append(Paragraph(f"<b>Environment:</b> {metadata_data.get('env', 'development')}", styles['Normal']))
        section.append(Paragraph(f"<b>System Version:</b> {metadata_data.get('version', '1.0.0')}", styles['Normal']))
        return section
