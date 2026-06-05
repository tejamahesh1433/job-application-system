"""
FastAPI Main Application
Job Application Automation System
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from utils.database import init_db

# ============================================
# Setup
# ============================================

logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Job Application Automation System",
    description="Apply to 25+ jobs per day with AI assistance",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for dashboard
static_dir = Path(__file__).resolve().parent.parent / "static"
app.mount("/dashboard", StaticFiles(directory=str(static_dir), html=True), name="static")


# ============================================
# Routers
# ============================================

from routers import jobs, applications, dashboard, match_resume, writing, workflow, gmail, answers, llm, documents
from routers.user import router as user_router

app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(dashboard.router)
app.include_router(user_router)
app.include_router(match_resume.router)
app.include_router(writing.router)
app.include_router(workflow.router)
app.include_router(gmail.router)
app.include_router(answers.router)
app.include_router(llm.router)
app.include_router(documents.router)


# ============================================
# Startup & Health
# ============================================

@app.get("/")
async def root():
    """Redirect the base URL to the dashboard."""
    return RedirectResponse(url="/dashboard")


@app.on_event("startup")
async def startup_event():
    """Initialize database and load models"""
    logger.info("Starting Job Application System...")
    try:
        init_db()
        logger.info("Database initialized")
        _migrate_schema()
        _seed_default_user()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    logger.info("System ready for applications!")


def _migrate_schema():
    """Add columns that were added to models after the table was first created."""
    from sqlalchemy import text
    from utils.database import SessionLocal
    db = SessionLocal()
    migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS skills JSONB DEFAULT '{}'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS certifications JSONB DEFAULT '{}'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS github_profile VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS linkedin_profile VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS portfolio_url VARCHAR(255)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS resume_parsed JSONB",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS original_resume_path VARCHAR(512)",
        "ALTER TABLE jobs ALTER COLUMN salary_currency TYPE VARCHAR(50)",
    ]
    try:
        for sql in migrations:
            db.execute(text(sql))
        db.commit()
        logger.info("Schema migration complete")
    except Exception as e:
        db.rollback()
        logger.warning(f"Schema migration warning: {e}")
    finally:
        db.close()


def _seed_default_user():
    """Ensure user ID 1 exists — the app uses user_id=1 throughout."""
    from sqlalchemy import text
    from utils.database import SessionLocal, User
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.id == 1).first():
            db.add(User(id=1, name="Default User", email="user@jobsystem.local"))
            db.commit()
            # Advance the sequence so future auto-inserts don't collide with id=1
            db.execute(text("SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM users), 1))"))
            db.commit()
            logger.info("Seeded default user (id=1)")
    except Exception as e:
        db.rollback()
        logger.warning(f"Could not seed default user: {e}")
    finally:
        db.close()


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Check system health"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment,
    }


# ============================================
# Run Server
# ============================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
