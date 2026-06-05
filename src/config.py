"""
Application Configuration
Loads settings from environment variables with validation using Pydantic
"""

from typing import Optional, List
from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
import os

# Load .env from project root
from dotenv import load_dotenv
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # ============================================
    # Environment & Debug
    # ============================================
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # ============================================
    # LLM API Keys
    # ============================================
    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    claude_haiku_model: str = os.getenv("CLAUDE_HAIKU_MODEL", "claude-haiku-4-5-20251001")
    claude_sonnet_model: str = os.getenv("CLAUDE_SONNET_MODEL", "claude-sonnet-4-6")
    openai_fallback_model: str = os.getenv("OPENAI_FALLBACK_MODEL", "gpt-4")
    claude_haiku_monthly_budget_usd: float = float(os.getenv("CLAUDE_HAIKU_MONTHLY_BUDGET_USD", "15"))
    claude_sonnet_monthly_budget_usd: float = float(os.getenv("CLAUDE_SONNET_MONTHLY_BUDGET_USD", "5"))
    openai_monthly_budget_usd: float = float(os.getenv("OPENAI_MONTHLY_BUDGET_USD", "3"))

    # ============================================
    # Database
    # ============================================
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5432/job_application_system"
    )
    database_echo: bool = os.getenv("DATABASE_ECHO", "False").lower() == "true"
    database_pool_size: int = int(os.getenv("DATABASE_POOL_SIZE", "5"))
    database_max_overflow: int = int(os.getenv("DATABASE_MAX_OVERFLOW", "10"))

    # ============================================
    # Redis
    # ============================================
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ============================================
    # Google APIs
    # ============================================
    google_client_id: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
    google_client_secret: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")
    gmail_app_password: Optional[str] = os.getenv("GMAIL_APP_PASSWORD")
    gmail_address: Optional[str] = os.getenv("GMAIL_ADDRESS")

    # ============================================
    # Job Discovery APIs
    # ============================================
    jsearch_api_key: Optional[str] = os.getenv("JSEARCH_API_KEY")
    jsearch_per_minute_request_cap: int = int(os.getenv("JSEARCH_PER_MINUTE_REQUEST_CAP", "10"))
    jsearch_daily_request_cap: int = int(os.getenv("JSEARCH_DAILY_REQUEST_CAP", "250"))
    jsearch_monthly_request_cap: int = int(os.getenv("JSEARCH_MONTHLY_REQUEST_CAP", "8000"))
    jsearch_cache_ttl_hours: int = int(os.getenv("JSEARCH_CACHE_TTL_HOURS", "6"))
    jsearch_monthly_budget_usd: float = float(os.getenv("JSEARCH_MONTHLY_BUDGET_USD", "25"))

    # ============================================
    # Crunchbase
    # ============================================
    crunchbase_api_key: Optional[str] = os.getenv("CRUNCHBASE_API_KEY")
    company_research_mode: str = os.getenv("COMPANY_RESEARCH_MODE", "scraping")

    # ============================================
    # Ollama (Local LLM)
    # ============================================
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "mistral")
    use_ollama_for_simple_tasks: bool = (
        os.getenv("USE_OLLAMA_FOR_SIMPLE_TASKS", "True").lower() == "true"
    )
    force_local_llm: bool = (
        os.getenv("FORCE_LOCAL_LLM", "False").lower() == "true"
    )

    # ============================================
    # FastAPI
    # ============================================
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    allowed_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # ============================================
    # Application Settings
    # ============================================
    applications_per_day: int = int(os.getenv("APPLICATIONS_PER_DAY", "30"))
    time_per_application_seconds: int = int(
        os.getenv("TIME_PER_APPLICATION_SECONDS", "96")
    )
    batch_size: int = int(os.getenv("BATCH_SIZE", "5"))
    retry_attempts: int = int(os.getenv("RETRY_ATTEMPTS", "3"))
    retry_delay: int = int(os.getenv("RETRY_DELAY", "5"))

    # ============================================
    # Form Filling
    # ============================================
    min_typing_delay_ms: int = int(os.getenv("MIN_TYPING_DELAY_MS", "50"))
    max_typing_delay_ms: int = int(os.getenv("MAX_TYPING_DELAY_MS", "150"))
    min_click_delay_ms: int = int(os.getenv("MIN_CLICK_DELAY_MS", "100"))
    max_click_delay_ms: int = int(os.getenv("MAX_CLICK_DELAY_MS", "500"))

    # ============================================
    # Feature Flags
    # ============================================
    enable_browser_automation: bool = (
        os.getenv("ENABLE_BROWSER_AUTOMATION", "True").lower() == "true"
    )
    enable_auto_submit: bool = (
        os.getenv("ENABLE_AUTO_SUBMIT", "False").lower() == "true"
    )
    enable_gmail_monitoring: bool = (
        os.getenv("ENABLE_GMAIL_MONITORING", "False").lower() == "true"
    )
    enable_answer_memory: bool = (
        os.getenv("ENABLE_ANSWER_MEMORY", "False").lower() == "true"
    )

    # ============================================
    # File Paths (relative to project root)
    # ============================================
    uploads_dir: str = os.getenv("UPLOADS_DIR", "uploads/")
    applications_dir: str = os.getenv("APPLICATIONS_DIR", "applications/")
    tracking_dir: str = os.getenv("TRACKING_DIR", "tracking/")
    resumes_dir: str = os.getenv("RESUMES_DIR", "resumes/")
    screenshots_dir: str = os.getenv("SCREENSHOTS_DIR", "screenshots/")
    logs_dir: str = os.getenv("LOGS_DIR", "logs/")
    credentials_dir: str = os.getenv("CREDENTIALS_DIR", "credentials/")

    # ============================================
    # Proxy
    # ============================================
    proxy_url: Optional[str] = os.getenv("PROXY_URL")
    use_proxy: bool = os.getenv("USE_PROXY", "False").lower() == "true"

    # ============================================
    # Sentry
    # ============================================
    sentry_dsn: Optional[str] = os.getenv("SENTRY_DSN")

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get application settings (cached)"""
    return Settings()


# Export settings for easy access
settings = get_settings()
