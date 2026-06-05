"""
Job Discovery Agent - Find live jobs from Indeed, LinkedIn, Glassdoor & more
Uses JSearch API (RapidAPI) — real-time data, no scraping, no bans.

Covers: Indeed · LinkedIn · Glassdoor · ZipRecruiter · Google Jobs · Monster
No LLM needed here — JSearch returns structured data directly.
"""

import logging
import asyncio
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

import httpx
from sqlalchemy.orm import Session

from config import settings
from utils.database import Job, JobSourceTracking, AuditLog
from utils.usage_ledger import UsageLimitExceeded, usage_ledger

logger = logging.getLogger(__name__)

JSEARCH_BASE = "https://jsearch.p.rapidapi.com"
JSEARCH_HEADERS = {
    "x-rapidapi-host": "jsearch.p.rapidapi.com",
    "x-rapidapi-key": settings.jsearch_api_key or "",
    "Content-Type": "application/json",
}
CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "jsearch"

# DevOps / SRE / Cloud job search queries
DEFAULT_QUERIES = [
    "DevOps Engineer",
    "Site Reliability Engineer",
    "Platform Engineer",
    "Cloud Infrastructure Engineer",
    "Kubernetes Engineer",
]

# Platforms JSearch aggregates (for logging)
SUPPORTED_PLATFORMS = [
    "Indeed", "LinkedIn", "Glassdoor", "ZipRecruiter",
    "Google Jobs", "Monster", "CareerBuilder",
]


class JobDiscoveryAgent:
    """
    Discovers live jobs via JSearch API and feeds them into the job analysis pipeline.

    Flow:
        search_jobs() → fetch raw job listings from JSearch
        _normalize_job() → map JSearch fields → your Job model fields
        save_jobs() → persist to DB (skips duplicates)
        run_discovery() → full pipeline: search → normalize → save → return summary
    """

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    async def run_discovery(
        self,
        queries: Optional[List[str]] = None,
        location: str = "United States",
        num_pages: int = 1,
        date_posted: str = "today",          # today | 3days | week | month
        remote_only: bool = False,
        employment_types: str = "FULLTIME",  # FULLTIME,PARTTIME,CONTRACTOR
    ) -> Dict[str, Any]:
        """
        Main entry point — run a full discovery cycle.

        Args:
            queries:          Search terms. Defaults to DEFAULT_QUERIES.
            location:         e.g. "United States", "New York", "Remote"
            num_pages:        Pages per query (1 page = ~10 jobs)
            date_posted:      Filter freshness: today | 3days | week | month
            remote_only:      Only remote jobs
            employment_types: Comma-separated job types

        Returns:
            {
                "new_jobs": 12,
                "duplicates_skipped": 3,
                "total_fetched": 15,
                "jobs": [...],
                "queries_run": [...],
                "success": True
            }
        """
        if not settings.jsearch_api_key:
            return {
                "success": False,
                "message": "JSEARCH_API_KEY not set in .env — get one free at rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch"
            }

        queries = queries or DEFAULT_QUERIES
        all_jobs: List[Dict[str, Any]] = []
        errors: List[str] = []

        for query in queries:
            try:
                jobs = await self.search_jobs(
                    query=query,
                    location=location,
                    num_pages=num_pages,
                    date_posted=date_posted,
                    remote_only=remote_only,
                    employment_types=employment_types,
                )
                all_jobs.extend(jobs)
                logger.info(f"JSearch [{query}] → {len(jobs)} jobs found")
                await asyncio.sleep(0.5)  # polite rate limiting
            except Exception as e:
                error_msg = f"Query '{query}' failed: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Save to DB
        saved, skipped = await self.save_jobs(all_jobs)

        result = {
            "success": True,
            "total_fetched": len(all_jobs),
            "new_jobs": saved,
            "duplicates_skipped": skipped,
            "queries_run": queries,
            "errors": errors,
            "jobs": [self._to_summary(j) for j in all_jobs[:saved]],
        }

        logger.info(
            f"Discovery complete: {saved} new jobs saved, {skipped} duplicates skipped "
            f"across {len(queries)} queries"
        )
        return result

    async def search_jobs(
        self,
        query: str,
        location: str = "United States",
        num_pages: int = 1,
        date_posted: str = "today",
        remote_only: bool = False,
        employment_types: str = "FULLTIME",
    ) -> List[Dict[str, Any]]:
        """
        Search JSearch API and return list of raw job dicts.

        JSearch response fields used:
            job_id, employer_name, job_title, job_description,
            job_city, job_state, job_country, job_is_remote,
            job_employment_type, job_apply_link, job_posted_at_timestamp,
            job_salary_min, job_salary_max, job_salary_currency,
            job_required_skills, job_highlights, job_publisher
        """
        params = {
            "query": f"{query} in {location}",
            "num_pages": str(num_pages),
            "date_posted": date_posted,
            "employment_types": employment_types,
        }
        if remote_only:
            params["remote_jobs_only"] = "true"

        data = await self._jsearch_get("search", params)

        jobs = data.get("data", [])
        logger.debug(f"JSearch returned {len(jobs)} jobs for query: {query}")
        return jobs

    async def get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch full job details by JSearch job_id.
        Use this when you need the complete description for analysis.
        """
        data = await self._jsearch_get("job-details", {"job_id": job_id, "country": "us"})

        jobs = data.get("data", [])
        return jobs[0] if jobs else None

    async def search_by_company(
        self,
        company_name: str,
        location: str = "United States",
    ) -> List[Dict[str, Any]]:
        """Find all open jobs at a specific company."""
        return await self.search_jobs(
            query=f"{company_name} DevOps OR SRE OR Platform Engineer",
            location=location,
            num_pages=2,
            date_posted="month",
        )

    async def save_jobs(
        self, raw_jobs: List[Dict[str, Any]]
    ) -> tuple[int, int]:
        """
        Normalize JSearch jobs and persist to DB.
        Returns (saved_count, skipped_count).
        """
        saved = 0
        skipped = 0

        for raw in raw_jobs:
            try:
                normalized = self._normalize_job(raw)
                job_url = normalized["job_url"]

                # Skip if already in DB
                existing = self.db.query(Job).filter(Job.job_url == job_url).first()
                if existing:
                    skipped += 1
                    continue

                job = Job(
                    job_id=f"jsearch_{raw.get('job_id', '')[:20]}",
                    company_name=normalized["company_name"],
                    job_title=normalized["job_title"],
                    job_url=normalized["job_url"],
                    source=normalized["source"],
                    description=normalized["description"],
                    location=normalized["location"],
                    remote_type=normalized["remote_type"],
                    salary_min=normalized["salary_min"],
                    salary_max=normalized["salary_max"],
                    salary_currency=(normalized["salary_currency"] or "USD")[:10],
                    job_type=normalized["job_type"],
                    seniority_level=normalized["seniority_level"],
                    requires_sponsorship=False,  # JSearch doesn't expose this
                    easy_apply=normalized["easy_apply"],
                    posted_date=normalized["posted_date"],
                    required_skills=normalized["required_skills"],
                    nice_to_haves=[],
                    responsibilities=normalized["responsibilities"],
                    company_size=None,
                    is_blacklisted=self._is_blacklisted(normalized),
                )

                self.db.add(job)
                self.db.flush()

                # Source tracking
                self.db.add(JobSourceTracking(
                    job_id=job.id,
                    source=normalized["source"],
                    url=job_url,
                ))

                # Audit log
                self.db.add(AuditLog(
                    action="job_discovered",
                    entity_type="job",
                    entity_id=job.id,
                    details={
                        "source": normalized["source"],
                        "publisher": raw.get("job_publisher", "unknown"),
                        "via": "jsearch_api",
                    },
                ))

                saved += 1

            except Exception as e:
                logger.error(f"Error saving job {raw.get('job_id')}: {e}")
                self.db.rollback()

        self.db.commit()
        return saved, skipped

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    async def _jsearch_get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call JSearch with local cache and daily/monthly request caps."""
        cached = self._read_cache(endpoint, params)
        if cached is not None:
            return cached

        usage_ledger.ensure_request_capacity(
            service="jsearch",
            operation="request",
            daily_cap=settings.jsearch_daily_request_cap,
            monthly_cap=settings.jsearch_monthly_request_cap,
            per_minute_cap=settings.jsearch_per_minute_request_cap,
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{JSEARCH_BASE}/{endpoint}",
                    params=params,
                    headers=JSEARCH_HEADERS,
                )
                response.raise_for_status()
                data = response.json()
        except UsageLimitExceeded:
            raise
        except Exception:
            raise

        usage_ledger.record(
            service="jsearch",
            operation="request",
            provider="jsearch",
            model="rapidapi",
            metadata={"endpoint": endpoint, "params": params},
        )
        self._write_cache(endpoint, params, data)
        return data

    @staticmethod
    def _cache_key(endpoint: str, params: Dict[str, Any]) -> str:
        raw = json.dumps({"endpoint": endpoint, "params": params}, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _read_cache(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        key = self._cache_key(endpoint, params)
        path = CACHE_DIR / f"{key}.json"
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(payload.get("cached_at"))
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=timezone.utc)
            expires_at = cached_at + timedelta(hours=settings.jsearch_cache_ttl_hours)
            if datetime.now(timezone.utc) > expires_at:
                return None
            logger.debug(f"JSearch cache hit: {endpoint} {params}")
            return payload.get("data")
        except Exception as exc:
            logger.warning(f"Ignoring invalid JSearch cache file {path.name}: {exc}")
            return None

    def _write_cache(self, endpoint: str, params: Dict[str, Any], data: Dict[str, Any]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            key = self._cache_key(endpoint, params)
            payload = {
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "endpoint": endpoint,
                "params": params,
                "data": data,
            }
            (CACHE_DIR / f"{key}.json").write_text(json.dumps(payload), encoding="utf-8")
        except Exception as exc:
            logger.warning(f"Could not write JSearch cache: {exc}")

    def _normalize_job(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map JSearch API fields → your Job model fields.

        JSearch field reference:
          employer_name         → company_name
          job_title             → job_title
          job_apply_link        → job_url (direct apply link)
          job_description       → description
          job_city/state/country → location
          job_is_remote         → remote_type
          job_employment_type   → job_type
          job_salary_min/max    → salary_min/max
          job_required_skills   → required_skills (list)
          job_highlights        → responsibilities (Qualifications + Responsibilities)
          job_publisher         → source (Indeed / LinkedIn / etc.)
          job_posted_at_timestamp → posted_date
        """
        # Location
        city = raw.get("job_city") or ""
        state = raw.get("job_state") or ""
        country = raw.get("job_country") or ""
        location_parts = [p for p in [city, state, country] if p]
        location = ", ".join(location_parts) if location_parts else "Unknown"

        # Remote type
        is_remote = raw.get("job_is_remote", False)
        emp_type = (raw.get("job_employment_type") or "").upper()
        remote_type = "remote" if is_remote else ("hybrid" if "HYBRID" in emp_type else "onsite")

        # Job type (map to your categories)
        title_lower = (raw.get("job_title") or "").lower()
        if any(k in title_lower for k in ["devops", "dev ops"]):
            job_type = "devops"
        elif any(k in title_lower for k in ["sre", "site reliability"]):
            job_type = "sre"
        elif any(k in title_lower for k in ["platform"]):
            job_type = "platform"
        elif any(k in title_lower for k in ["cloud", "aws", "azure", "gcp"]):
            job_type = "cloud"
        elif any(k in title_lower for k in ["infrastructure", "infra"]):
            job_type = "infrastructure"
        else:
            job_type = "other"

        # Seniority
        if any(k in title_lower for k in ["senior", "sr.", "staff", "principal", "lead"]):
            seniority = "senior"
        elif any(k in title_lower for k in ["junior", "jr.", "entry", "associate"]):
            seniority = "junior"
        elif any(k in title_lower for k in ["manager", "director", "head", "vp"]):
            seniority = "manager"
        else:
            seniority = "mid"

        # Skills — JSearch returns a flat list; convert to {skill: "required"} dict
        raw_skills: List[str] = raw.get("job_required_skills") or []
        required_skills = {skill: "required" for skill in raw_skills if skill}

        # If no skills list, extract from highlights
        if not required_skills:
            highlights = raw.get("job_highlights") or {}
            quals = highlights.get("Qualifications") or []
            for q in quals[:10]:
                # Each qualification is a sentence; use it as a pseudo-skill key
                if len(q) < 80:  # Short items are likely skill names
                    required_skills[q] = "required"

        # Responsibilities
        highlights = raw.get("job_highlights") or {}
        responsibilities = (highlights.get("Responsibilities") or [])[:5]

        # Salary
        salary_min = raw.get("job_salary_min") or raw.get("job_min_salary")
        salary_max = raw.get("job_salary_max") or raw.get("job_max_salary")
        salary_currency = raw.get("job_salary_currency") or "USD"

        # Posted date
        ts = raw.get("job_posted_at_timestamp")
        posted_date = (
            datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
            if ts else datetime.utcnow()
        )

        # Source — JSearch tells us which platform it found the job on
        publisher = (raw.get("job_publisher") or "unknown").lower()
        if "linkedin" in publisher:
            source = "linkedin"
        elif "indeed" in publisher:
            source = "indeed"
        elif "glassdoor" in publisher:
            source = "glassdoor"
        elif "ziprecruiter" in publisher:
            source = "ziprecruiter"
        else:
            source = publisher.split()[0] if publisher else "jsearch"

        # Easy apply — LinkedIn Easy Apply or Indeed Apply
        easy_apply = raw.get("job_apply_is_direct", False) or "easy" in publisher

        return {
            "company_name": raw.get("employer_name") or "Unknown",
            "job_title": raw.get("job_title") or "",
            "job_url": raw.get("job_apply_link") or raw.get("job_url") or "",
            "description": raw.get("job_description") or "",
            "location": location,
            "remote_type": remote_type,
            "job_type": job_type,
            "seniority_level": seniority,
            "salary_min": float(salary_min) if salary_min else None,
            "salary_max": float(salary_max) if salary_max else None,
            "salary_currency": salary_currency,
            "required_skills": required_skills,
            "responsibilities": responsibilities,
            "posted_date": posted_date,
            "source": source,
            "easy_apply": easy_apply,
        }

    @staticmethod
    def _is_blacklisted(job: Dict[str, Any]) -> bool:
        """Flag jobs that match blacklist criteria."""
        blacklist = ["unpaid", "equity only", "1099", "no visa", "no sponsorship"]
        text = f"{job.get('job_title','')} {job.get('description','')}".lower()
        return any(k in text for k in blacklist)

    @staticmethod
    def _to_summary(raw: Dict[str, Any]) -> Dict[str, Any]:
        """Compact summary dict for API responses."""
        return {
            "title": raw.get("job_title"),
            "company": raw.get("employer_name"),
            "location": raw.get("job_city"),
            "remote": raw.get("job_is_remote"),
            "publisher": raw.get("job_publisher"),
            "apply_link": raw.get("job_apply_link"),
            "posted": raw.get("job_posted_at_datetime_utc"),
        }
