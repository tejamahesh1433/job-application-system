"""
Database Configuration and Models
SQLAlchemy setup for PostgreSQL with pgvector support
"""

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Boolean, Text, JSON, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from datetime import datetime
from typing import Optional, List
from enum import Enum as PyEnum
from contextlib import contextmanager

from config import settings

# Database setup
engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ApplicationStatus(str, PyEnum):
    """Application status enum"""
    PENDING = "pending"
    DRAFT = "draft"
    SUBMITTED = "submitted"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEWED = "interviewed"
    OFFER_RECEIVED = "offer_received"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ResumeMode(str, PyEnum):
    """Resume customization modes"""
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


# ============================================
# Database Models
# ============================================

class User(Base):
    """User profile - single source of truth for candidate info"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    location = Column(String(255), nullable=True)
    current_company = Column(String(255), nullable=True)
    current_title = Column(String(255), nullable=True)
    years_experience = Column(Integer, nullable=True)

    # Skills & certifications (denormalized for quick access by agents)
    skills = Column(JSONB, default={})
    certifications = Column(JSONB, default={})

    # Social / portfolio links
    github_profile = Column(String(255), nullable=True)
    linkedin_profile = Column(String(255), nullable=True)
    portfolio_url = Column(String(255), nullable=True)

    # Raw resume data
    resume_parsed = Column(JSONB, nullable=True)
    original_resume_path = Column(String(512), nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    applications = relationship("Application", back_populates="user")
    resumes = relationship("Resume", back_populates="user")
    answers = relationship("ApprovedAnswer", back_populates="user")
    experience = relationship("ExperienceRecord", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, name={self.name})>"


class UserProfile(Base):
    """Detailed user profile data"""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    
    skills_json = Column(JSONB, default={})  # {"AWS": 8, "Kubernetes": 7, ...}
    experience_json = Column(JSONB, default={})
    certifications_json = Column(JSONB, default={})
    
    github_profile = Column(String(255), nullable=True)
    linkedin_profile = Column(String(255), nullable=True)
    portfolio_url = Column(String(255), nullable=True)

    user = relationship("User", back_populates="profile")


class Company(Base):
    """Company information and research"""
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True)
    website = Column(String(255), nullable=True)
    founded_date = Column(String(50), nullable=True)
    funding = Column(String(100), nullable=True)
    tech_stack = Column(JSONB, default={})
    competitors = Column(JSONB, default=[])
    
    preferred_list_flag = Column(Boolean, default=False)
    blacklist_flag = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    jobs = relationship("Job", back_populates="company")
    research = relationship("CompanyResearch", back_populates="company", uselist=False)
    contacts = relationship("RecruiterContact", back_populates="company")


class Job(Base):
    """Job posting data"""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(255), unique=True, index=True)  # External job ID
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    company_name = Column(String(255), nullable=False)
    job_title = Column(String(255), nullable=False)
    job_url = Column(String(512), nullable=False)
    source = Column(String(50))  # "indeed", "linkedin", "company_site", etc.

    # Job Details
    description = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    remote_type = Column(String(50))  # "remote", "hybrid", "on-site"
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    salary_currency = Column(String(50), default="USD")

    # Structured requirements (denormalized from JobAnalysis for agent access)
    required_skills = Column(JSONB, default={})
    nice_to_haves = Column(JSONB, default=[])
    responsibilities = Column(JSONB, default=[])
    company_size = Column(String(50), nullable=True)

    # Classification
    job_type = Column(String(50))  # "devops", "sre", "platform", "cloud", "infrastructure"
    seniority_level = Column(String(50))  # "junior", "mid", "senior", "lead"
    
    # Status
    is_duplicate = Column(Boolean, default=False)
    is_blacklisted = Column(Boolean, default=False)
    requires_sponsorship = Column(Boolean, default=False)
    easy_apply = Column(Boolean, default=False)

    # Metadata
    posted_date = Column(DateTime, nullable=True)
    last_scraped = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    company = relationship("Company", back_populates="jobs")
    analysis = relationship("JobAnalysis", back_populates="job", uselist=False)
    applications = relationship("Application", back_populates="job")
    source_tracking = relationship("JobSourceTracking", back_populates="job", foreign_keys="JobSourceTracking.job_id")

    def __repr__(self):
        return f"<Job(id={self.id}, company={self.company_name}, title={self.job_title})>"


class JobAnalysis(Base):
    """Detailed job analysis results"""
    __tablename__ = "job_analysis"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), unique=True)
    
    required_skills_json = Column(JSONB, default={})
    nice_to_have_json = Column(JSONB, default={})
    role_type = Column(String(50))
    ats_keywords = Column(JSONB, default=[])
    ats_score = Column(Float, default=0.0)
    company_tech_stack = Column(JSONB, default={})

    job = relationship("Job", back_populates="analysis")


class Application(Base):
    """Job application record"""
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=True)

    # Tracking
    application_tracking_id = Column(String(255), unique=True, nullable=True, index=True)
    status = Column(String(50), default=ApplicationStatus.PENDING, index=True)
    submitted_at = Column(DateTime, nullable=True)
    response_date = Column(DateTime, nullable=True)
    response_received = Column(Boolean, default=False)
    response_type = Column(String(50), nullable=True)  # "interview", "rejection", "offer"

    match_score = Column(Float)  # 0-100
    interview_probability = Column(Float)  # 0-100
    interview_scheduled = Column(Boolean, default=False)
    follow_up_scheduled = Column(DateTime, nullable=True)
    follow_up_date = Column(DateTime, nullable=True)
    follow_up_sent = Column(Boolean, default=False)

    # Form fill tracking
    form_fields_filled = Column(Integer, nullable=True)
    form_fields_total = Column(Integer, nullable=True)

    notes = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


    # Relationships
    user = relationship("User", back_populates="applications")
    job = relationship("Job", back_populates="applications")
    documents = relationship("ApplicationDocument", back_populates="application")
    logs = relationship("ApplicationLog", back_populates="application")
    interviews = relationship("Interview", back_populates="application")
    resume = relationship("Resume", back_populates="applications")


class Resume(Base):
    """Resume versions"""
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    version_number = Column(Integer)
    mode = Column(String(50))  # conservative, balanced, aggressive

    original_text = Column(Text)
    customized_text = Column(Text)

    # Structured resume storage used by ResumeAgent
    resume_content = Column(Text, nullable=True)
    resume_json = Column(JSONB, nullable=True)
    customized_for_job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    customization_details = Column(JSONB, default={})

    ats_score = Column(Float)
    readability_score = Column(Float)
    keyword_match_score = Column(Float, nullable=True)

    used_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    interviews_generated = Column(Integer, default=0)
    offers_generated = Column(Integer, default=0)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="resumes")
    applications = relationship("Application", back_populates="resume")


class SavedAnswer(Base):
    """Stored answers for reuse"""
    __tablename__ = "saved_answers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    question_text = Column(Text)
    answer_text = Column(Text)
    
    quality_score = Column(Float)
    confidence_score = Column(Float)
    
    times_used = Column(Integer, default=0)
    interviews_generated = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)


class ApplicationDocument(Base):
    """Documents generated for an application"""
    __tablename__ = "application_documents"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"))
    
    pdf_path = Column(String(512))
    generated_at = Column(DateTime, default=datetime.utcnow)
    file_size = Column(Integer)

    application = relationship("Application", back_populates="documents")


class ApplicationLog(Base):
    """Detailed log of agent actions for an application"""
    __tablename__ = "application_logs"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"))
    
    timestamp = Column(DateTime, default=datetime.utcnow)
    event_type = Column(String(100))
    agent_name = Column(String(100))
    action = Column(String(255))
    details_json = Column(JSONB, default={})
    success = Column(Boolean, default=True)

    application = relationship("Application", back_populates="logs")


class Interview(Base):
    """Scheduled interviews"""
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"))
    
    scheduled_date = Column(DateTime)
    interviewer_name = Column(String(255), nullable=True)
    interview_type = Column(String(100))  # phone, technical, onsite
    prep_package_path = Column(String(512), nullable=True)
    status = Column(String(50), default="scheduled")

    application = relationship("Application", back_populates="interviews")


class DailyExcelTracker(Base):
    """Records of daily Excel exports"""
    __tablename__ = "daily_excel_trackers"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, default=datetime.utcnow, unique=True)
    excel_path = Column(String(512))
    applications_count = Column(Integer, default=0)
    successful_count = Column(Integer, default=0)


class MasterExcelMetadata(Base):
    """Metadata for the master Excel tracker"""
    __tablename__ = "master_excel_metadata"

    id = Column(Integer, primary_key=True, index=True)
    total_applications = Column(Integer, default=0)
    total_responses = Column(Integer, default=0)
    total_interviews = Column(Integer, default=0)
    total_offers = Column(Integer, default=0)
    response_rate = Column(Float, default=0.0)
    interview_rate = Column(Float, default=0.0)


class RecruiterContact(Base):
    """Recruiter contact information"""
    __tablename__ = "recruiter_contacts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    email = Column(String(255), index=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    response_rate = Column(Float, default=0.0)

    company = relationship("Company", back_populates="contacts")


class BrowserSession(Base):
    """Stored browser sessions for persistence"""
    __tablename__ = "browser_sessions"

    id = Column(Integer, primary_key=True, index=True)
    portal_name = Column(String(100), index=True)
    encrypted_cookies = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)


class CompanyResearch(Base):
    """In-depth company research"""
    __tablename__ = "company_research"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), unique=True)
    
    summary = Column(Text)
    tech_stack_json = Column(JSONB, default={})
    recent_news_json = Column(JSONB, default=[])
    funding_json = Column(JSONB, default={})

    company = relationship("Company", back_populates="research")


class SkillMapping(Base):
    """Taxonomy of skills"""
    __tablename__ = "skill_mappings"

    id = Column(Integer, primary_key=True, index=True)
    skill_name = Column(String(255), unique=True)
    category = Column(String(100))
    years = Column(Integer, default=0)
    proficiency = Column(String(50))


class ExperienceRecord(Base):
    """Detailed experience records"""
    __tablename__ = "experience_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    job_title = Column(String(255))
    company = Column(String(255))
    years = Column(Float)
    achievements_json = Column(JSONB, default=[])

    user = relationship("User", back_populates="experience")


class JobSourceTracking(Base):
    """Track where jobs came from for deduplication"""
    __tablename__ = "job_source_tracking"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    source = Column(String(100))
    url = Column(String(512))
    crawled_at = Column(DateTime, default=datetime.utcnow)
    duplicate_of = Column(Integer, ForeignKey("jobs.id"), nullable=True)

    job = relationship("Job", back_populates="source_tracking", foreign_keys=[job_id])
    duplicate_job = relationship("Job", foreign_keys=[duplicate_of])


class Analytics(Base):
    """Daily system analytics"""
    __tablename__ = "analytics"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, default=datetime.utcnow, unique=True)
    
    applications_sent = Column(Integer, default=0)
    interviews_scheduled = Column(Integer, default=0)
    responses_received = Column(Integer, default=0)
    response_rate = Column(Float, default=0.0)
    best_resume_version = Column(Integer)


class ApprovedAnswer(Base):
    """Answer memory system - approved answers to reuse"""
    __tablename__ = "approved_answers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Question & Answer
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)

    # Question Type
    question_type = Column(String(100))  # "cover_letter", "why_this_job", "technical_question", etc.
    category = Column(String(100), index=True)  # e.g., "Kubernetes", "Behavioral"
    role_type = Column(String(100))
    skill_tags = Column(JSONB, default=[])  # Skills relevant to this answer

    # Quality Metrics
    quality_score = Column(Float)  # 0-100
    star_format = Column(Boolean, default=False)
    has_quantified_results = Column(Boolean, default=False)
    readability_score = Column(Float)
    relevance_score = Column(Float)

    # Performance Tracking
    times_used = Column(Integer, default=0)
    interviews_generated = Column(Integer, default=0)
    offers_generated = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)  # Percentage
    
    # Versioning & Performance
    version_history = Column(JSONB, default=[])  # [{"version": 1, "answer": "...", "date": "...", "success_rate": 0.7}]
    interview_outcomes = Column(JSONB, default=[])  # [{"interview_id": 1, "result": "offer"}]
    
    # AI Analysis
    recommender_notes = Column(Text)  # Why AI suggests this answer
    weak_indicators = Column(JSONB, default=[])  # ["Too generic", "No metrics"]
    company_specific = Column(String(255))  # Linked to a specific company research

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="answers")

    def __repr__(self):
        return f"<ApprovedAnswer(id={self.id}, type={self.question_type})>"


class AuditLog(Base):
    """Audit trail for all changes"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # What changed
    entity_type = Column(String(100))  # "application", "resume", "answer", etc.
    entity_id = Column(Integer)
    action = Column(String(50))  # "create", "update", "delete", "submit"

    # Original and New Values
    original_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)
    changes = Column(JSONB, default={})  # What specifically changed

    # Context
    reason = Column(String(255), nullable=True)
    additional_metadata = Column(JSONB, default={})

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, entity={self.entity_type})>"


# ============================================
# Database Functions
# ============================================

def init_db():
    """Initialize database (create all tables)"""
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully!")


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager for database operations"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
