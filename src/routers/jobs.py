from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
import logging
import random
import re
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from config import settings
from utils.database import get_db
from utils.discovery_store import discovery_store
from utils.usage_ledger import UsageLimitExceeded, usage_ledger
from agents.job_discovery_agent import JobDiscoveryAgent
from agents.job_analysis_agent import JobAnalysisAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Skills pools for realistic data
SKILL_POOLS = {
    'devops': {
        'matched': ['Kubernetes', 'Docker', 'AWS', 'CI/CD', 'Linux', 'Terraform', 'Python', 'Git'],
        'missing': ['Helm', 'ArgoCD', 'Pulumi', 'Istio', 'Datadog']
    },
    'backend': {
        'matched': ['Python', 'Go', 'PostgreSQL', 'REST APIs', 'Redis', 'Docker'],
        'missing': ['GraphQL', 'gRPC', 'Kafka', 'Rust']
    },
    'frontend': {
        'matched': ['React', 'TypeScript', 'CSS', 'Next.js', 'Git'],
        'missing': ['Vue', 'Svelte', 'WebGL', 'Three.js']
    },
    'default': {
        'matched': ['Python', 'AWS', 'Docker', 'Git', 'Linux'],
        'missing': ['Kubernetes', 'Terraform', 'Go']
    }
}

WARNING_POOL = [
    '⚠ Sponsorship not mentioned in posting',
    '⚠ Recruiter email missing from listing',
    '⚠ Possible duplicate — similar role posted 3 days ago',
    '⚠ Company has mixed Glassdoor reviews (3.2/5)',
    '⚠ No salary range listed',
    '⚠ High turnover signal — role reposted 3 times',
]

COMPANIES = [
    ("Google", "Mountain View, CA", "Technology", "100,000+", "1998"),
    ("Meta", "Menlo Park, CA", "Social Media", "60,000+", "2004"),
    ("Amazon", "Seattle, WA", "E-Commerce / Cloud", "1,500,000+", "1994"),
    ("Netflix", "Los Gatos, CA", "Streaming", "12,000+", "1997"),
    ("Stripe", "San Francisco, CA", "Fintech", "8,000+", "2010"),
    ("Datadog", "New York, NY", "Observability", "5,000+", "2010"),
    ("Cloudflare", "Austin, TX", "Security / CDN", "3,500+", "2009"),
    ("HashiCorp", "San Francisco, CA", "DevOps Tools", "2,000+", "2012"),
    ("GitLab", "Remote", "DevOps Platform", "2,000+", "2011"),
    ("Vercel", "San Francisco, CA", "Frontend Platform", "500+", "2015"),
    ("Confluent", "Mountain View, CA", "Data Streaming", "3,000+", "2014"),
    ("Snowflake", "San Mateo, CA", "Data Cloud", "6,000+", "2012"),
    ("CrowdStrike", "Austin, TX", "Cybersecurity", "8,000+", "2011"),
    ("Palantir", "Denver, CO", "Data Analytics", "3,500+", "2003"),
    ("Databricks", "San Francisco, CA", "Data & AI", "5,000+", "2013"),
]

SALARIES = ["$120K", "$130K", "$140K", "$150K", "$160K", "$175K", "$190K", "$200K", "$220K"]
POSTED = ["1h ago", "2h ago", "5h ago", "12h ago", "1d ago", "2d ago", "3d ago"]
TECH_STACKS = [
    ['K8s', 'AWS', 'Go', 'React'],
    ['Docker', 'GCP', 'Python', 'Vue'],
    ['Terraform', 'Azure', 'Java', 'Angular'],
    ['AWS', 'Node.js', 'PostgreSQL', 'Redis'],
]

LIVE_SOURCE_VALUES = {"", "all", "remotive", "arbeitnow", "jsearch"}
US_LOCATION_HINTS = (
    "usa", "u.s.", "u.s.a", "united states", "north america",
    "americas", "america", "anywhere", "worldwide", "global", "remote"
)

# Explicit non-US location keywords — jobs with these are excluded
NON_US_EXCLUSIONS = frozenset([
    # UK / Ireland
    "uk", "united kingdom", "great britain", "england", "scotland",
    "wales", "london", "manchester", "bristol", "edinburgh",
    "dublin", "ireland",
    # Europe
    "europe", "eu only", "eu citizen", "european union", "emea",
    "germany", "berlin", "munich", "hamburg", "frankfurt",
    "france", "paris", "lyon",
    "netherlands", "amsterdam", "rotterdam",
    "spain", "madrid", "barcelona",
    "italy", "rome", "milan",
    "sweden", "stockholm",
    "norway", "oslo",
    "denmark", "copenhagen",
    "finland", "helsinki",
    "switzerland", "zurich", "geneva",
    "austria", "vienna",
    "poland", "warsaw",
    "czech", "prague",
    "belgium", "brussels",
    "portugal", "lisbon",
    # Canada / Oceania
    "canada", "toronto", "vancouver", "montreal", "ottawa",
    "australia", "sydney", "melbourne", "brisbane",
    "new zealand", "auckland",
    # Asia / Pacific
    "india", "bangalore", "mumbai", "delhi", "hyderabad", "chennai",
    "asia", "apac", "singapore", "japan", "tokyo",
    "china", "beijing", "shanghai",
    # LatAm / Africa / Middle East
    "brazil", "sao paulo", "mexico", "latam", "latin america",
    "africa", "nairobi", "lagos", "south africa", "cape town",
    "middle east", "dubai", "uae", "israel", "tel aviv",
])
DEFAULT_SKILLS = ["Python", "AWS", "Docker", "Kubernetes", "Linux", "Git", "Terraform", "CI/CD"]
ROLE_QUERY_EXPANSIONS = {
    "devops": ["devops", "site reliability", "platform engineer", "cloud engineer", "infrastructure engineer"],
    "sre": ["sre", "site reliability", "platform engineer", "infrastructure engineer"],
    "platform": ["platform engineer", "devops", "site reliability", "infrastructure engineer"],
    "cloud": ["cloud engineer", "devops", "infrastructure engineer"],
}


def _search_terms(keyword: str) -> List[str]:
    normalized = (keyword or "").strip().lower()
    terms = [keyword.strip()] if keyword and keyword.strip() else []
    for trigger, expansions in ROLE_QUERY_EXPANSIONS.items():
        if trigger in normalized:
            terms.extend(expansions)
    return list(dict.fromkeys(term for term in terms if term))


def _strip_html(value: str, max_chars: int = 1200) -> str:
    if not value:
        return ""
    text = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)[:max_chars]


def _parse_dt(value: Any):
    """Parse a datetime value (ISO string or Unix int) to an aware UTC datetime."""
    if not value:
        return None
    if isinstance(value, int):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _format_posted(value: Any) -> str:
    """Relative posting time: '5m ago', '2h 30m ago', '3d ago'."""
    dt = _parse_dt(value)
    if not dt:
        return "Recently"
    try:
        delta = datetime.now(timezone.utc) - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return "Just now"
        mins = secs // 60
        if mins < 60:
            return f"{mins}m ago"
        hours = mins // 60
        rem_min = mins % 60
        if hours < 24:
            return f"{hours}h {rem_min}m ago" if rem_min else f"{hours}h ago"
        days = delta.days
        if days == 1:
            return "Yesterday"
        if days < 7:
            return f"{days}d ago"
        weeks = days // 7
        return f"{weeks}w ago" if weeks < 5 else f"{days // 30}mo ago"
    except Exception:
        return "Recently"


def _format_posted_exact(value: Any) -> str:
    """Exact posting datetime: 'Jun 4, 2026 · 10:30 UTC'."""
    dt = _parse_dt(value)
    if not dt:
        return ""
    try:
        month = dt.strftime("%b")
        day = str(dt.day)
        year = dt.strftime("%Y")
        hhmm = dt.strftime("%H:%M")
        return f"{month} {day}, {year} · {hhmm} UTC"
    except Exception:
        return ""


def _is_us_or_global(candidate_location: str) -> bool:
    """Return True if the location is US, global remote, or unspecified.
    Rejects jobs explicitly limited to non-US regions.
    """
    if not candidate_location or not candidate_location.strip():
        return True  # No location stated → assume worldwide remote, accept
    loc = candidate_location.lower()
    for excl in NON_US_EXCLUSIONS:
        if excl in loc:
            return False
    return True  # US city, "Remote", "Worldwide", "Anywhere" — all accepted


def _normalize_job_type(value: str) -> str:
    text = (value or "").replace("_", "-").replace(" ", "-").lower()
    mapping = {
        "full-time": "Full Time",
        "fulltime": "Full Time",
        "contract": "Contract",
        "part-time": "Part Time",
        "freelance": "Freelance",
        "internship": "Internship",
    }
    return mapping.get(text, value or "Not specified")


def _passes_job_type(job_type_value: str, requested: Optional[str]) -> bool:
    if not requested or requested == "all":
        return True
    normalized = _normalize_job_type(job_type_value).lower().replace(" ", "-")
    return requested.lower() in normalized


def _salary_min_usd(salary: str) -> int:
    if not salary:
        return 0
    numbers = re.findall(r"\$?\s*(\d{2,3})(?:[,.]\d+)?\s*[kK]?", salary)
    if not numbers:
        return 0
    value = min(int(n) for n in numbers)
    return value * 1000 if value < 1000 else value


def _passes_salary(salary: str, salary_min: Optional[str]) -> bool:
    try:
        requested = int(salary_min or "0") * 1000
    except ValueError:
        requested = 0
    if requested <= 0:
        return True
    parsed = _salary_min_usd(salary)
    return parsed == 0 or parsed >= requested


def _passes_us_location(candidate_location: str, selected_location: str) -> bool:
    selected = (selected_location or "").lower()
    candidate = (candidate_location or "").lower()
    if selected in ("remote", "anywhere in usa"):
        return not candidate or any(hint in candidate for hint in US_LOCATION_HINTS)
    city = selected.split(",")[0].strip()
    return city in candidate or any(hint in candidate for hint in ("usa", "united states", "remote", "worldwide"))


def _extract_skills(text: str, tags: Optional[List[str]] = None) -> Dict[str, List[str]]:
    haystack = f"{text} {' '.join(tags or [])}".lower()
    matched = []
    for skill in DEFAULT_SKILLS:
        aliases = {
            "CI/CD": ["ci/cd", "cicd", "jenkins", "github actions", "gitlab ci"],
            "Kubernetes": ["kubernetes", "k8s"],
            "AWS": ["aws", "amazon web services"],
        }.get(skill, [skill.lower()])
        if any(alias in haystack for alias in aliases):
            matched.append(skill)
    missing = [skill for skill in DEFAULT_SKILLS if skill not in matched][:3]
    return {"matched": matched[:6], "missing": missing}


def _score_job(keyword: str, title: str, description: str, tags: Optional[List[str]] = None) -> Dict[str, int]:
    text = f"{title} {description} {' '.join(tags or [])}".lower()
    title_text = (title or "").lower()
    keyword_terms = [term for term in re.split(r"\W+", keyword.lower()) if len(term) > 2]
    keyword_hits = sum(1 for term in keyword_terms if term in text)
    title_hits = sum(1 for term in keyword_terms if term in title_text)
    phrase_bonus = 12 if keyword.lower().strip() and keyword.lower().strip() in text else 0
    skill_hits = len(_extract_skills(text, tags)["matched"])
    match = min(98, 54 + phrase_bonus + keyword_hits * 7 + title_hits * 8 + skill_hits * 5)
    ats = min(96, 60 + skill_hits * 6 + min(len(description) // 300, 8))
    interview = max(35, min(95, int((match + ats) / 2) - 5))
    return {"match": match, "ats": ats, "interview": interview}


def _jsearch_employment_types(job_type: Optional[str]) -> str:
    requested = (job_type or "all").lower()
    if requested == "contract":
        return "CONTRACTOR"
    if requested in ("part-time", "parttime"):
        return "PARTTIME"
    if requested in ("internship", "intern"):
        return "INTERN"
    return "FULLTIME,CONTRACTOR"


def _api_location(location: str) -> str:
    text = (location or "").strip()
    normalized = text.lower()
    if normalized in ("anywhere in usa", "usa", "us", "u.s.", "united states"):
        return "United States"
    if normalized in ("remote", "anywhere"):
        return "United States"
    return text or "United States"


def _format_jsearch_salary(raw: Dict[str, Any]) -> str:
    minimum = raw.get("job_min_salary") or raw.get("job_salary_min")
    maximum = raw.get("job_max_salary") or raw.get("job_salary_max")
    currency = raw.get("job_salary_currency") or "USD"
    if minimum and maximum:
        return f"{currency} {int(float(minimum)):,}-{int(float(maximum)):,}"
    if minimum:
        return f"{currency} {int(float(minimum)):,}+"
    return "Not listed"


def _jsearch_location(raw: Dict[str, Any]) -> str:
    parts = [
        raw.get("job_city"),
        raw.get("job_state"),
        raw.get("job_country"),
    ]
    location = ", ".join(str(part) for part in parts if part)
    if location:
        return location
    return "Remote" if raw.get("job_is_remote") else "Not listed"


def _normalize_jsearch_for_ui(raw: Dict[str, Any], keyword: str) -> Optional[Dict[str, Any]]:
    url = raw.get("job_apply_link") or raw.get("job_google_link") or raw.get("job_url")
    if not url:
        return None

    title = raw.get("job_title") or "Untitled Role"
    description = _strip_html(raw.get("job_description") or "", max_chars=1600)
    skills_raw = raw.get("job_required_skills") or []
    if not isinstance(skills_raw, list):
        skills_raw = []
    skills = _extract_skills(description, skills_raw)
    scores = _score_job(keyword, title, description, skills_raw)
    posted = raw.get("job_posted_at_datetime_utc") or raw.get("job_posted_at_timestamp")
    publisher = raw.get("job_publisher") or "JSearch"
    employment = raw.get("job_employment_type") or ""

    return {
        "title": title,
        "company": raw.get("employer_name") or "Unknown Company",
        "location": _jsearch_location(raw),
        "url": url,
        "source": f"JSearch/{publisher}",
        "match": f"{scores['match']}%",
        "ats": f"{scores['ats']}%",
        "interview_prob": f"{scores['interview']}%",
        "salary": _format_jsearch_salary(raw),
        "work_type": "Remote" if raw.get("job_is_remote") else "Onsite",
        "job_type": _normalize_job_type(employment.replace("_", "-")),
        "posted": _format_posted(posted),
        "posted_exact": _format_posted_exact(posted),
        "skills_matched": skills["matched"],
        "skills_missing": skills["missing"],
        "warnings": ["Salary not listed"] if not (raw.get("job_min_salary") or raw.get("job_salary_min")) else [],
        "industry": "Technology",
        "company_size": "Not listed",
        "founded": "Not listed",
        "tech_stack": list(dict.fromkeys(skills_raw[:6] + skills["matched"]))[:6],
        "description": description or "Description available on the job posting site.",
        "is_live": True,
    }


async def _fetch_jsearch_jobs_for_ui(
    db: Session,
    keyword: str,
    location: str,
    work_type: str,
    job_type: str,
) -> List[Dict[str, Any]]:
    if not settings.jsearch_api_key:
        return []

    agent = JobDiscoveryAgent(db)
    raw_jobs = await agent.search_jobs(
        query=keyword,
        location=_api_location(location),
        num_pages=1,
        date_posted="week",
        remote_only=(work_type == "remote"),
        employment_types=_jsearch_employment_types(job_type),
    )
    if not raw_jobs and (job_type or "").lower() not in ("", "all"):
        logger.info(f"JSearch returned no {job_type} jobs; retrying all employment types")
        raw_jobs = await agent.search_jobs(
            query=keyword,
            location=_api_location(location),
            num_pages=1,
            date_posted="week",
            remote_only=(work_type == "remote"),
            employment_types="FULLTIME,CONTRACTOR",
        )
    jobs = []
    for raw in raw_jobs:
        normalized = _normalize_jsearch_for_ui(raw, keyword)
        if normalized:
            jobs.append(normalized)
    return jobs


def _fetch_remotive_jobs(
    keyword: str,
    location: str,
    work_type: str,
    job_type: str,
    salary_min: str,
) -> List[Dict[str, Any]]:
    if work_type not in ("all", "remote"):
        return []

    raw_jobs = []
    for term in _search_terms(keyword):
        params = {"search": term, "limit": 50}
        response = requests.get(
            f"https://remotive.com/api/remote-jobs?{urlencode(params)}",
            timeout=15,
            headers={"User-Agent": "JobFlowAI/1.0"},
        )
        response.raise_for_status()
        raw_jobs.extend(response.json().get("jobs", []))

    expanded_terms = _search_terms(keyword)
    expanded_term_words = [[word for word in re.split(r"\W+", term) if len(word) > 2] for term in expanded_terms]
    jobs = []
    for item in raw_jobs:
        candidate_location = item.get("candidate_required_location") or "Remote"
        salary = item.get("salary") or ""
        raw_job_type = item.get("job_type") or ""
        description = _strip_html(item.get("description", ""))
        tags = item.get("tags") or []
        searchable = f"{item.get('title', '')} {description} {' '.join(tags)}".lower()
        
        passes_keyword = False
        if not expanded_term_words or not any(expanded_term_words):
            passes_keyword = True
        else:
            for words in expanded_term_words:
                if words and all(w in searchable for w in words):
                    passes_keyword = True
                    break
                    
        if not passes_keyword:
            continue
        # Strict US-or-global filter (replaces old _passes_us_location)
        if not _is_us_or_global(candidate_location):
            continue
        if not _passes_job_type(raw_job_type, job_type):
            continue
        if not _passes_salary(salary, salary_min):
            continue

        skills = _extract_skills(description, tags)
        best_score_term = max(expanded_terms, key=lambda term: _score_job(term, item.get("title", ""), description, tags)["match"])
        scores = _score_job(best_score_term, item.get("title", ""), description, tags)
        pub_date = item.get("publication_date")

        jobs.append({
            "title": item.get("title") or "Untitled Role",
            "company": item.get("company_name") or "Unknown Company",
            "location": candidate_location,
            "url": item.get("url"),
            "source": "Remotive",
            "match": f"{scores['match']}%",
            "ats": f"{scores['ats']}%",
            "interview_prob": f"{scores['interview']}%",
            "salary": salary or "Not listed",
            "work_type": "Remote",
            "job_type": _normalize_job_type(raw_job_type),
            "posted": _format_posted(pub_date),
            "posted_exact": _format_posted_exact(pub_date),
            "skills_matched": skills["matched"],
            "skills_missing": skills["missing"],
            "warnings": ["Salary not listed"] if not salary else [],
            "industry": item.get("category") or "Technology",
            "company_size": "Not listed",
            "founded": "Not listed",
            "tech_stack": list(dict.fromkeys((tags or [])[:6] + skills["matched"]))[:6],
            "description": description or "Description available on the job posting site.",
            "is_live": True,
        })
    return jobs


def _fetch_arbeitnow_jobs(
    keyword: str,
    location: str,
    work_type: str,
    job_type: str,
    salary_min: str,
) -> List[Dict[str, Any]]:
    response = requests.get(
        "https://www.arbeitnow.com/api/job-board-api",
        timeout=15,
        headers={"User-Agent": "JobFlowAI/1.0"},
    )
    response.raise_for_status()

    expanded_terms = _search_terms(keyword)
    expanded_term_words = [[word for word in re.split(r"\W+", term) if len(word) > 2] for term in expanded_terms]
    jobs = []
    for item in response.json().get("data", []):
        title = item.get("title") or ""
        description = _strip_html(item.get("description", ""))
        tags = item.get("tags") or []
        searchable = f"{title} {description} {' '.join(tags)}".lower()
        
        passes_keyword = False
        if not expanded_term_words or not any(expanded_term_words):
            passes_keyword = True
        else:
            for words in expanded_term_words:
                if words and all(w in searchable for w in words):
                    passes_keyword = True
                    break
                    
        if not passes_keyword:
            continue

        is_remote = bool(item.get("remote"))
        if work_type == "remote" and not is_remote:
            continue
        if work_type == "onsite" and is_remote:
            continue
        if work_type == "hybrid":
            continue

        candidate_location = item.get("location") or ("Remote" if is_remote else "")
        # Strict US-or-global filter
        if not _is_us_or_global(candidate_location):
            continue

        raw_types = item.get("job_types") or []
        raw_job_type = raw_types[0] if raw_types else ""
        if not _passes_job_type(raw_job_type, job_type):
            continue
        if not _passes_salary("", salary_min):
            continue

        skills = _extract_skills(description, tags)
        scores = _score_job(keyword, title, description, tags)
        created_at = item.get("created_at")
        jobs.append({
            "title": title or "Untitled Role",
            "company": item.get("company_name") or "Unknown Company",
            "location": candidate_location or "Remote",
            "url": item.get("url"),
            "source": "Arbeitnow",
            "match": f"{scores['match']}%",
            "ats": f"{scores['ats']}%",
            "interview_prob": f"{scores['interview']}%",
            "salary": "Not listed",
            "work_type": "Remote" if is_remote else "Onsite",
            "job_type": _normalize_job_type(raw_job_type),
            "posted": _format_posted(created_at),
            "posted_exact": _format_posted_exact(created_at),
            "skills_matched": skills["matched"],
            "skills_missing": skills["missing"],
            "warnings": ["Salary not listed"],
            "industry": tags[0] if tags else "Technology",
            "company_size": "Not listed",
            "founded": "Not listed",
            "tech_stack": list(dict.fromkeys((tags or [])[:6] + skills["matched"]))[:6],
            "description": description or "Description available on the job posting site.",
            "is_live": True,
        })
    return jobs

from pydantic import BaseModel


class JobAnalysisRequest(BaseModel):
    job_url: str
    job_content: str
    source: str = "linkedin"


class DiscoverRequest(BaseModel):
    queries: Optional[List[str]] = None          # defaults to DevOps/SRE/Platform/etc.
    location: str = "United States"
    num_pages: int = 1                            # 1 page ≈ 10 jobs per query
    date_posted: str = "today"                    # today | 3days | week | month
    remote_only: bool = False
    employment_types: str = "FULLTIME"


@router.get("/usage")
async def get_job_search_usage() -> Dict[str, Any]:
    """Return usage, caps, and the current low-cost routing plan."""
    return {
        "success": True,
        "applications_per_day_target": settings.applications_per_day,
        "routing": {
            "free_search": "Remotive/Arbeitnow via /api/jobs/search",
            "paid_discovery": "JSearch via /api/jobs/discover",
            "bulk_analysis": "Ollama/local LLM",
            "resume_tailoring": "Claude Haiku only for high-match jobs",
            "interview_prep": "Claude Sonnet only after interview signal",
            "fallback": "OpenAI only if Claude is unavailable or fails",
        },
        "usage": usage_ledger.monthly_summary(),
    }


@router.get("/saved")
async def get_saved_discovery_jobs(user_id: int = 1) -> Dict[str, Any]:
    """Return the persistent Job Discovery inbox."""
    jobs = discovery_store.list_jobs(user_id=user_id)
    return {
        "success": True,
        "jobs": jobs,
        "total": len(jobs),
        "is_live": False,
        "message": "Saved discovery inbox",
    }


@router.delete("/saved/{job_id}")
async def remove_saved_discovery_job(job_id: str, user_id: int = 1) -> Dict[str, Any]:
    """Hide a job from Job Discovery without deleting application history."""
    job = discovery_store.update_status(job_id=job_id, status="removed", user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Saved job not found")
    return {"success": True, "job_id": job_id, "message": "Removed from Job Discovery"}


@router.post("/saved/{job_id}/applied")
async def mark_saved_discovery_job_applied(job_id: str, user_id: int = 1) -> Dict[str, Any]:
    """Move a job out of Job Discovery after an application workflow starts/succeeds."""
    job = discovery_store.update_status(job_id=job_id, status="applied", user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Saved job not found")
    return {"success": True, "job_id": job_id, "message": "Moved to Applications"}


@router.post("/discover")
async def discover_jobs(
    request: DiscoverRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Discover jobs through JSearch with local cache and request caps."""
    try:
        agent = JobDiscoveryAgent(db)
        result = await agent.run_discovery(
            queries=request.queries,
            location=request.location,
            num_pages=request.num_pages,
            date_posted=request.date_posted,
            remote_only=request.remote_only,
            employment_types=request.employment_types,
        )
        result["usage"] = usage_ledger.monthly_summary()
        return result
    except UsageLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc))

@router.post("/analyze")
async def analyze_job(
    request: JobAnalysisRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Analyze job posting and extract structured data"""
    try:
        job_agent = JobAnalysisAgent(db)
        result = await job_agent.analyze_job(
            job_url=request.job_url, 
            job_content=request.job_content, 
            source=request.source
        )
        return result
    except Exception as e:
        logger.error(f"Error analyzing job: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/search")
async def search_jobs_api(
    keyword: str,
    location: str = "Remote",
    country: str = "United States",
    work_type: Optional[str] = "all",
    job_type: Optional[str] = "all",
    role_type: Optional[str] = "",
    salary_min: Optional[str] = "0",
    experience: Optional[str] = "",
    source: Optional[str] = "",
    user_id: int = 1,
    force: bool = False,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Search live job feeds and return only real job posting URLs."""
    try:
        logger.info(f"Job search: '{keyword}' in '{location}', {country}")
        source_value = (source or "").lower()
        if source_value not in LIVE_SOURCE_VALUES:
            logger.info(f"Unsupported source '{source_value}' requested; falling back to all live sources")
            source_value = ""

        search_params = {
            "keyword": keyword,
            "location": location,
            "country": country,
            "work_type": work_type or "all",
            "job_type": job_type or "all",
            "role_type": role_type or "",
            "salary_min": salary_min or "0",
            "experience": experience or "",
            "source": source_value,
        }
        search_key = discovery_store.search_key(search_params)
        if not force and discovery_store.has_search(search_key, user_id=user_id):
            saved_jobs = discovery_store.list_jobs(user_id=user_id)
            return {
                "jobs": saved_jobs,
                "success": True,
                "total": len(saved_jobs),
                "is_live": False,
                "from_cache": True,
                "sources": ["Saved inbox"],
                "message": "Loaded saved Job Discovery results. Use Refresh Search to call job providers again.",
            }

        providers = []
        if source_value in ("", "all", "remotive"):
            providers.append(("Remotive", _fetch_remotive_jobs))
        if source_value in ("", "all", "arbeitnow"):
            providers.append(("Arbeitnow", _fetch_arbeitnow_jobs))

        jobs: List[Dict[str, Any]] = []
        provider_errors = []
        if source_value != "jsearch":
            for provider_name, provider in providers:
                try:
                    jobs.extend(provider(keyword, location, work_type or "all", job_type or "all", salary_min or "0"))
                except Exception as exc:
                    provider_errors.append(f"{provider_name}: {exc}")
                    logger.warning(f"Live job provider failed ({provider_name}): {exc}")

        should_try_jsearch = source_value == "jsearch"
        if should_try_jsearch:
            try:
                jsearch_jobs = await _fetch_jsearch_jobs_for_ui(
                    db=db,
                    keyword=keyword,
                    location=location,
                    work_type=work_type or "all",
                    job_type=job_type or "all",
                )
                jobs.extend(jsearch_jobs)
                if source_value == "jsearch":
                    providers.append(("JSearch", _fetch_jsearch_jobs_for_ui))
                elif jsearch_jobs:
                    providers.append(("JSearch fallback", _fetch_jsearch_jobs_for_ui))
            except UsageLimitExceeded:
                raise
            except Exception as exc:
                provider_errors.append(f"JSearch: {exc}")
                logger.warning(f"JSearch fallback failed: {exc}")

        seen_urls = set()
        unique_jobs = []
        for job in jobs:
            url = job.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            unique_jobs.append(job)

        unique_jobs.sort(key=lambda item: int(str(item.get("match", "0")).rstrip("%")), reverse=True)
        limited_jobs = unique_jobs[:25]

        message = None
        if not limited_jobs:
            message = "No real jobs matched these filters. Try All Types, Full Time, or broader keywords."
            if provider_errors:
                message += " Live provider errors: " + "; ".join(provider_errors)

        saved_jobs = discovery_store.save_search(
            search_key=search_key,
            params=search_params,
            jobs=limited_jobs,
            user_id=user_id,
        )

        return {
            "jobs": saved_jobs,
            "success": True,
            "total": len(saved_jobs),
            "is_live": True,
            "from_cache": False,
            "sources": [name for name, _ in providers],
            "message": message,
        }
    except UsageLimitExceeded as e:
        logger.warning(f"Job search blocked by usage guard: {e}")
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching jobs: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{job_id}")
async def get_job(
    job_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get job details"""
    try:
        job_agent = JobAnalysisAgent(db)
        job = job_agent.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job: {e}")
        raise HTTPException(status_code=400, detail=str(e))
