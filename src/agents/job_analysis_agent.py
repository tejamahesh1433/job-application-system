"""
Job Analysis Agent - Parse job postings and extract structured data
Classifies job types, extracts requirements, identifies tech stack
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy.orm import Session
from utils.database import Job, JobAnalysis, Company, JobSourceTracking, AuditLog
from utils.llm_helper import generate_json, generate_text, USE_OLLAMA
from utils.playwright_helper import playwright_helper

logger = logging.getLogger(__name__)


class JobAnalysisAgent:
    """Analyzes job postings and extracts structured information"""

    def __init__(self, db: Session):
        self.db = db

    async def analyze_job(
        self,
        job_url: str,
        job_content: str,
        source: str = "linkedin",
    ) -> Dict[str, Any]:
        """
        Analyze a job posting and extract structured data

        Args:
            job_url: URL to the job posting
            job_content: HTML or text content of the job posting
            source: Source of job (linkedin, indeed, company_site, etc.)

        Returns:
            {
                "job_id": "job_xyz123",
                "company_name": "TechCorp",
                "job_title": "Senior DevOps Engineer",
                "job_type": "devops",
                "seniority_level": "senior",
                "location": "San Francisco, CA",
                "remote_type": "hybrid",
                "salary_range": {"min": 150000, "max": 200000, "currency": "USD"},
                "required_skills": {"AWS": "expert", "Kubernetes": "proficient", ...},
                "nice_to_haves": [...],
                "responsibilities": [...],
                "company_industry": "Technology",
                "company_size": "1000-5000",
                "job_db_id": 1,
                "success": true
            }
        """

        try:
            # Check if job already exists
            existing = self.db.query(Job).filter(
                Job.job_url == job_url
            ).first()

            if existing:
                logger.info(f"Job already exists: {existing.id}")
                return {
                    "job_id": existing.job_id,
                    "job_db_id": existing.id,
                    "duplicate": True,
                    "message": "Job already in system"
                }

            # Extract job info using LLM
            extraction_prompt = f"""
Extract structured information from this job posting. Return valid JSON ONLY.

Job URL: {job_url}

Content:
{job_content[:5000]}

Return JSON with EXACTLY these fields (no extra fields):
{{
    "company_name": "string",
    "job_title": "string",
    "job_type": "string (devops|sre|platform|cloud|infrastructure|other)",
    "seniority_level": "string (junior|mid|senior|lead)",
    "location": "string",
    "remote_type": "string (remote|hybrid|on-site)",
    "salary_min": number or null,
    "salary_max": number or null,
    "salary_currency": "string",
    "company_description": "string or null",
    "company_industry": "string or null",
    "company_size": "string or null (50-100, 100-500, etc)",
    "required_skills": {{"skill_name": "proficiency_level"}},
    "nice_to_haves": ["skill1", "skill2"],
    "responsibilities": ["responsibility1", "responsibility2"],
    "requires_sponsorship": boolean,
    "easy_apply": boolean,
    "ats_keywords": ["keyword1", "keyword2"]
}}
"""

            job_data = await generate_json(extraction_prompt, provider=USE_OLLAMA)

            # Create job record
            job = Job(
                job_id=f"{source}_{hash(job_url) % 100000}",
                company_name=job_data.get("company_name", "Unknown"),
                job_title=job_data.get("job_title", ""),
                job_url=job_url,
                source=source,
                description=job_content,
                location=job_data.get("location"),
                remote_type=job_data.get("remote_type", "unknown"),
                salary_min=job_data.get("salary_min"),
                salary_max=job_data.get("salary_max"),
                salary_currency=(job_data.get("salary_currency") or "USD")[:10],
                job_type=job_data.get("job_type", "other"),
                seniority_level=job_data.get("seniority_level", "mid"),
                requires_sponsorship=job_data.get("requires_sponsorship", False),
                easy_apply=job_data.get("easy_apply", False),
                posted_date=datetime.utcnow(),
                required_skills=job_data.get("required_skills", {}),
                nice_to_haves=job_data.get("nice_to_haves", []),
                responsibilities=job_data.get("responsibilities", []),
                company_size=job_data.get("company_size"),
            )

            # Check for blacklist keywords
            job.is_blacklisted = self._check_blacklist(job_data)

            self.db.add(job)
            self.db.flush()  # Get job.id

            # Create JobAnalysis record
            analysis = JobAnalysis(
                job_id=job.id,
                required_skills_json=job_data.get("required_skills", {}),
                nice_to_have_json=job_data.get("nice_to_haves", []),
                role_type=job.job_type,
                ats_keywords=job_data.get("ats_keywords", []),
                ats_score=0.0,  # Will be calculated later
                company_tech_stack=job_data.get("required_skills", {}),  # Initial tech stack from skills
            )
            self.db.add(analysis)

            # Add source tracking
            source_track = JobSourceTracking(
                job_id=job.id,
                source=source,
                url=job_url,
            )
            self.db.add(source_track)

            self.db.commit()
            self.db.refresh(job)

            # 4. Check for duplicates
            from utils.deduplication_system import DeduplicationSystem
            dedup = DeduplicationSystem(self.db)
            duplicates = await dedup.find_duplicates(
                job_title=job.job_title,
                company_name=job.company_name,
                embedding=[] # Analysis vector would go here
            )
            
            is_duplicate = len(duplicates) > 1 # Current one is in DB
            if is_duplicate:
                best_job = dedup.recommend_best_source(duplicates)
                if best_job.id != job.id:
                    job.is_duplicate = True
                    self.db.commit()
                    logger.info(f"⏭️ Marked job {job.id} as duplicate of {best_job.id}")

            logger.info(f"✅ Job analyzed: {job.company_name} - {job.job_title} (ID: {job.id})")

            return {
                "job_id": job.job_id,
                "job_db_id": job.id,
                "company_name": job.company_name,
                "is_duplicate": job.is_duplicate,
                "job_title": job.job_title,
                "job_type": job.job_type,
                "seniority_level": job.seniority_level,
                "location": job.location,
                "remote_type": job.remote_type,
                "salary_range": {
                    "min": job.salary_min,
                    "max": job.salary_max,
                    "currency": job.salary_currency
                },
                "required_skills": job_data.get("required_skills", {}),
                "nice_to_haves": job_data.get("nice_to_haves", []),
                "responsibilities": job_data.get("responsibilities", [])[:3],
                "requires_sponsorship": job.requires_sponsorship,
                "is_blacklisted": job.is_blacklisted,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Error analyzing job: {e}")
            return {
                "success": False,
                "message": f"Error analyzing job: {str(e)}"
            }

    async def classify_job_type(self, job_data: Dict[str, Any]) -> str:
        """
        Classify job into category (DevOps, SRE, Platform, Cloud, Infrastructure)
        """

        classification_prompt = f"""
Classify this job into ONE category:
- devops: DevOps Engineer, DevOps Lead
- sre: Site Reliability Engineer, SRE
- platform: Platform Engineer, Infrastructure
- cloud: Cloud Engineer, Cloud Architect
- infrastructure: Infrastructure Engineer
- other: Doesn't fit above categories

Job Title: {job_data.get('job_title', '')}
Description: {job_data.get('description', '')[:500]}

Return ONLY the category name, nothing else.
"""

        result = await generate_json(classification_prompt, provider=USE_OLLAMA)
        return result.get("category", "other")

    async def extract_salary_range(self, job_text: str) -> Dict[str, Optional[float]]:
        """Extract salary information from job text"""

        salary_prompt = f"""
Extract salary information from this text. Return JSON with min, max, and currency.

Text: {job_text}

Return:
{{
    "min": number or null,
    "max": number or null,
    "currency": "string (USD, EUR, etc)"
}}

Only include salary if explicitly mentioned.
"""

        result = await generate_json(salary_prompt, provider=USE_OLLAMA)
        return {
            "min": result.get("min"),
            "max": result.get("max"),
            "currency": result.get("currency", "USD")
        }

    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get job details"""

        job = self.db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return None

        return {
            "id": job.id,
            "job_id": job.job_id,
            "company_name": job.company_name,
            "job_title": job.job_title,
            "job_url": job.job_url,
            "source": job.source,
            "job_type": job.job_type,
            "seniority_level": job.seniority_level,
            "location": job.location,
            "remote_type": job.remote_type,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "required_skills": job.required_skills,
            "nice_to_haves": job.nice_to_haves,
            "responsibilities": job.responsibilities,
            "company_size": job.company_size,
            "requires_sponsorship": job.requires_sponsorship,
            "is_blacklisted": job.is_blacklisted,
            "posted_date": job.posted_date.isoformat() if job.posted_date else None,
        }

    def search_jobs(
        self,
        job_type: Optional[str] = None,
        location: Optional[str] = None,
        min_salary: Optional[float] = None,
        exclude_blacklisted: bool = True,
        exclude_sponsorship: bool = True,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search jobs with filters"""

        query = self.db.query(Job)

        if exclude_blacklisted:
            query = query.filter(Job.is_blacklisted == False)

        if exclude_sponsorship:
            query = query.filter(Job.requires_sponsorship == False)

        if job_type:
            query = query.filter(Job.job_type == job_type)

        if location:
            query = query.filter(Job.location.ilike(f"%{location}%"))

        if min_salary:
            query = query.filter(
                (Job.salary_min >= min_salary) |
                (Job.salary_max >= min_salary)
            )

        results = query.order_by(Job.posted_date.desc()).limit(limit).all()

        return [self.get_job(job.id) for job in results]

    @staticmethod
    def _check_blacklist(job_data: Dict[str, Any]) -> bool:
        """Check if job meets blacklist criteria"""

        blacklist_keywords = [
            "startup mode",
            "unpaid",
            "equity only",
            "contract role",
            "1099",
        ]

        title = str(job_data.get("job_title") or "").lower()
        desc = str(job_data.get("company_description") or "").lower()
        
        description = f"{title} {desc}"

        return any(keyword in description for keyword in blacklist_keywords)

    def flag_duplicate(self, job_id: int):
        """Mark job as duplicate"""

        job = self.db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.is_duplicate = True
            self.db.commit()

    def flag_blacklist(self, job_id: int):
        """Mark job as blacklisted"""

        job = self.db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.is_blacklisted = True
            self.db.commit()

    async def scrape_indeed(self, keyword: str, location: str) -> List[Dict[str, Any]]:
        """Scrape Indeed for jobs using Playwright"""
        logger.info(f"Scraping Indeed for {keyword} in {location}")
        
        url = f"https://www.indeed.com/jobs?q={keyword}&l={location}"
        await playwright_helper.initialize()
        try:
            if await playwright_helper.navigate_to(url):
                content = await playwright_helper.get_page_content()
                # Extract jobs from list page (simplified)
                extraction_prompt = f"""
                Extract a list of job URLs and titles from this Indeed page content.
                Return JSON: {{"jobs": [{{"title": "string", "url": "string"}}]}}
                Content: {content[:5000]}
                """
                results = await generate_json(extraction_prompt, provider=USE_OLLAMA)
                return results.get("jobs", [])
        finally:
            await playwright_helper.close()
        return []

    async def scrape_linkedin(self, keyword: str, location: str) -> List[Dict[str, Any]]:
        """Scrape LinkedIn for jobs using Playwright"""
        logger.info(f"Scraping LinkedIn for {keyword} in {location}")
        
        url = f"https://www.linkedin.com/jobs/search/?keywords={keyword}&location={location}"
        await playwright_helper.initialize()
        try:
            if await playwright_helper.navigate_to(url):
                content = await playwright_helper.get_page_content()
                extraction_prompt = f"""
                Extract a list of job URLs and titles from this LinkedIn page content.
                Return JSON: {{"jobs": [{{"title": "string", "url": "string"}}]}}
                Content: {content[:5000]}
                """
                results = await generate_json(extraction_prompt, provider=USE_OLLAMA)
                return results.get("jobs", [])
        finally:
            await playwright_helper.close()
        return []

    async def scrape_company_careers(self, company_name: str) -> List[Dict[str, Any]]:
        """Search and scrape company career page"""
        logger.info(f"Scraping career page for {company_name}")
        
        # First search for the career page
        search_url = f"https://www.google.com/search?q={company_name}+careers"
        await playwright_helper.initialize()
        try:
            if await playwright_helper.navigate_to(search_url):
                content = await playwright_helper.get_page_content()
                find_url_prompt = f"Find the career page URL for {company_name} from this search result content. Return ONLY the URL.\nContent: {content[:2000]}"
                career_url = await generate_text(find_url_prompt, provider=USE_OLLAMA)
                
                if career_url and career_url.startswith("http"):
                    if await playwright_helper.navigate_to(career_url):
                        page_content = await playwright_helper.get_page_content()
                        extract_jobs_prompt = "Extract a list of DevOps/SRE job titles and URLs from this career page.\nReturn JSON: {\"jobs\": [{\"title\": \"string\", \"url\": \"string\"}]}\nContent: " + page_content[:5000]
                        results = await generate_json(extract_jobs_prompt)
                        return results.get("jobs", [])
        finally:
            await playwright_helper.close()
        return []

    async def detect_duplicates_across_sources(self, job_title: str, company_name: str) -> Optional[Job]:
        """Find the same job on multiple sources using title and company"""
        return self.db.query(Job).filter(
            Job.job_title.ilike(job_title),
            Job.company_name.ilike(company_name)
        ).first()

    async def rank_sources(self, company_name: str, job_title: str) -> str:
        """Rank sources: Company site > LinkedIn > Indeed"""
        jobs = self.db.query(Job).filter(
            Job.company_name.ilike(company_name),
            Job.job_title.ilike(job_title)
        ).all()
        
        sources = [j.source for j in jobs]
        if "company_site" in sources:
            return "company_site"
        if "linkedin" in sources:
            return "linkedin"
        return "indeed" if "indeed" in sources else "unknown"

    async def extract_ats_keywords(self, job_description: str) -> List[str]:
        """Extract ATS keywords from job description using LLM"""
        prompt = f"""
        Extract the top 15 ATS keywords (skills, tools, certifications) from this job description.
        Return as a JSON list of strings.
        
        Description: {job_description[:2000]}
        """
        result = await generate_json(prompt, provider=USE_OLLAMA)
        return result.get("keywords", [])

    async def calculate_ats_score(self, job_description: str, resume_text: str) -> float:
        """Calculate ATS score (0-100) based on keyword density and relevance"""
        prompt = f"""
        Compare this job description and resume. Calculate an ATS compatibility score from 0 to 100.
        Return JSON: {{"score": number}}
        
        Job: {job_description[:1500]}
        Resume: {resume_text[:1500]}
        """
        result = await generate_json(prompt, provider=USE_OLLAMA)
        return float(result.get("score", 0.0))
