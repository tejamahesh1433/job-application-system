# ⚡ Quick Start - Phase 1 MVP (5 Minutes)

## What Was Built

✅ **Complete Phase 1 MVP** - A production-ready job application automation system

**Includes**:
- 7 specialized AI agents
- FastAPI backend with 26 endpoints
- PostgreSQL database with 6 core tables
- PDF & Excel generators
- Multi-LLM support (Claude + OpenAI + Ollama)
- Resume parser & ATS optimizer
- Match score calculator (0-100%)
- Cover letter generator
- Audit logging & compliance

## 🚀 Get Started in 5 Minutes

### 1. Setup Python (2 min)

```bash
cd C:\job-application-system

# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Setup Database (2 min)

**Option A: Docker (Easiest)**
```bash
docker run -d ^
  --name jobapp-db ^
  -e POSTGRES_USER=postgres ^
  -e POSTGRES_PASSWORD=password ^
  -p 5432:5432 ^
  postgres:16

# Wait 10 seconds for DB to start...
```

**Option B: Local PostgreSQL**
- Ensure PostgreSQL 16+ is installed and running
- Connection string in .env will be: `postgresql://postgres:password@localhost:5432/job_application_system`

### 3. Configure API Keys (1 min)

```bash
# Copy template
copy .env.example .env

# Edit .env and add:
ANTHROPIC_API_KEY=sk-ant-xxxxx  # from https://console.anthropic.com
OPENAI_API_KEY=sk-xxxxx         # from https://platform.openai.com
DATABASE_URL=postgresql://postgres:password@localhost:5432/job_application_system
```

### 4. Initialize Database

```bash
python -c "from src.utils.database import init_db; init_db()"
```

### 5. Start Server

```bash
python src/main.py
```

✅ **API is now live at http://localhost:8000**

## 📚 API Docs

Open browser: **http://localhost:8000/docs**

(Interactive Swagger UI with all endpoints)

## 🧪 Test It

### Test 1: Check Health
```bash
curl http://localhost:8000/health
```

Expected: `{"status":"healthy",...}`

### Test 2: Process a Job Application

```python
import requests

# 1. Upload resume
user_resp = requests.post(
    "http://localhost:8000/api/user/profile/upload-resume",
    params={"resume_path": "resumes/your_resume.pdf"}
)
user_id = user_resp.json()["user_id"]
print(f"✅ User created: {user_id}")

# 2. Analyze a job
job_resp = requests.post(
    "http://localhost:8000/api/jobs/analyze",
    params={
        "job_url": "https://example.com/jobs/devops-engineer",
        "job_content": "<html>...</html>",  # Paste job HTML here
        "source": "linkedin"
    }
)
job_id = job_resp.json()["job_db_id"]
print(f"✅ Job analyzed: {job_id}")

# 3. Full application workflow
app_resp = requests.post(
    "http://localhost:8000/api/workflow/process-single-application",
    params={"user_id": user_id, "job_id": job_id}
)
app_data = app_resp.json()

print(f"✅ Application processed!")
print(f"   Match Score: {app_data['match_score']}%")
print(f"   Tracking ID: {app_data['tracking_id']}")
print(f"   Status: {app_data['message']}")
```

## 📊 What You Get

**Generated Files**:
- 📄 **PDF**: `applications/2024-01-15/TechCorp_DevOps.pdf` (10 sections)
- 📊 **Excel**: `tracking/Applications_2024_01_15.xlsx` (25 rows)
- 🗄️ **Database**: Complete application record with audit trail

**Data**:
- Match score (0-100%)
- Resume customization level
- Cover letter quality score
- Application tracking ID
- Follow-up scheduling
- Recruiter contact info

## 📁 Project Structure

```
job-application-system/
├── src/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings
│   ├── agents/              # 7 AI agents
│   │   ├── profile_agent.py
│   │   ├── job_analysis_agent.py
│   │   ├── resume_agent.py
│   │   ├── match_agent.py
│   │   ├── writing_agent.py
│   │   ├── tracking_agent.py
│   │   └── browser_agent.py (Phase 2)
│   └── utils/               # Utilities
│       ├── database.py
│       ├── llm_helper.py
│       ├── pdf_generator.py
│       └── excel_generator.py
├── docs/                    # 9 documentation files
├── README.md               # Full documentation
├── PHASE_1_SUMMARY.md      # What was built
├── QUICK_START.md          # This file
├── requirements.txt        # Dependencies
├── .env.example           # Configuration template
└── .gitignore            # Git ignore
```

## 🎯 Features in Phase 1

### ✅ Implemented
- Resume parsing (PDF/DOCX)
- Job analysis
- Match scoring (40% skill + 25% experience + 15% seniority + 10% salary + 10% location)
- Resume customization (3 modes: conservative/balanced/aggressive)
- Cover letter generation
- Form answer generation
- PDF generation (10 sections)
- Excel tracking
- Database storage
- Audit logging
- Multi-LLM support

### ⏳ Phase 2 (Coming Next)
- Playwright browser automation
- Auto-fill forms
- CAPTCHA detection
- Answer memory system
- Screenshot capture
- Manual form submission

### 🔮 Phase 3 (Future)
- Auto-submit applications
- Gmail monitoring
- Response detection
- Interview scheduling
- Automatic follow-ups

## 🔑 API Endpoints Quick Reference

**Users**:
- `POST /api/user/profile/upload-resume` - Parse resume
- `GET /api/user/{user_id}/profile` - Get profile

**Jobs**:
- `POST /api/jobs/analyze` - Analyze job
- `GET /api/jobs/{job_id}` - Get job details

**Matching**:
- `POST /api/match/calculate` - Get match score

**Resume**:
- `POST /api/resume/customize` - Customize for job

**Writing**:
- `POST /api/writing/cover-letter` - Generate letter
- `POST /api/writing/form-answers` - Generate answers

**Workflow**:
- `POST /api/workflow/process-single-application` - Full process

**Details**: See `docs/07_QUICK_REFERENCE.md`

## ❌ Troubleshooting

### "Could not connect to database"
```bash
# Check if PostgreSQL is running
docker ps  # or: systemctl status postgresql

# Start if needed
docker start jobapp-db
```

### "ANTHROPIC_API_KEY not found"
```bash
# Copy and edit .env
copy .env.example .env
# Add your API keys from:
# - https://console.anthropic.com
# - https://platform.openai.com
```

### "Port 8000 already in use"
```bash
# Kill process
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Or change port in .env
API_PORT=8001
```

### "Resume parsing failed"
- Ensure resume file exists
- Use PDF or DOCX format
- Path should be relative or absolute

## 📖 Documentation

**For More Details**:
- `README.md` - Full feature list and setup
- `PHASE_1_SUMMARY.md` - Technical details
- `docs/01_START_HERE.md` - Getting started
- `docs/02_WINDOWS_SETUP_GUIDE.md` - Windows-specific
- `docs/03_APIS_REQUIRED.md` - API key setup
- `docs/05_COMPLETE_IMPLEMENTATION_GUIDE.md` - Technical guide
- `docs/07_QUICK_REFERENCE.md` - API reference

## 💡 Next Steps

1. **Setup** - Follow 5-minute setup above
2. **Test** - Run health check and test workflow
3. **Customize** - Add your own resume
4. **Process** - Test with real job posting
5. **Review** - Check generated PDF and Excel
6. **Integrate** - Build Phase 2 automation (if desired)

## 🎉 You're Ready!

Everything is set up. Start the server and begin processing job applications!

```bash
python src/main.py
```

Then visit: **http://localhost:8000/docs**

## 📞 Need Help?

Check the `docs/` folder for comprehensive guides on every aspect of the system.

---

**Happy job hunting! 🚀**

Built with ❤️ for automated job applications
