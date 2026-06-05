# COWORK AUTOMATION PROMPT - Job Application System

## Project Overview
Build an intelligent job application automation system that applies to 25+ DevOps/SRE jobs per day, generates professional PDF documentation, creates Excel tracking spreadsheets, and leverages local Ollama AI to reduce API costs by 70%.

**Target**: Apply to 25 jobs daily, generate 25 PDFs, create Excel tracking, all in 40 minutes.

---

## Hardware Specification
- **System**: Alienware RTX 5080 Laptop
- **GPU**: NVIDIA RTX 5080 (for local LLM models)
- **CPU**: Intel Core Ultra 9 (multi-core processing)
- **RAM**: 64GB DDR5
- **SSD**: 6TB
- **OS**: Windows 11 Pro

---

## Core System Architecture

### 7 Specialized Agents
1. **Profile Agent** - Extract and manage user skills, experience, certifications
2. **Resume Agent** - Customize resume safely (no hallucinations, truth-verified)
3. **Job Analysis Agent** - Parse job postings, extract requirements, classify role type
4. **Match Agent** - Score compatibility between user and job (0-100%)
5. **Writing Agent** - Generate cover letters, form answers, emails
6. **Browser Automation Agent** - Use Playwright to fill forms and submit applications
7. **Tracking Agent** - Database storage, follow-up scheduling, analytics

### 6 Core Layers
1. **Layer 0**: ATS Optimization Engine (analyze keyword density, formatting)
2. **Layer 1**: User Knowledge System (your profile as single source of truth)
3. **Layer 2**: Job Intelligence System (analyze jobs independently)
4. **Layer 3**: Application Execution System (automation)
5. **Layer 4**: Answer Memory Engine (store approved answers, reuse, saves 40+ hours)
6. **Layer 5**: Compliance & Safety Layer (audit trail, no hallucinations)
7. **Layer 6**: Confidence Scoring System (detailed match breakdown)

---

## Key Features (92 Total)

### Tier 1: Automation (12 features)
- Browser session persistence (don't log in repeatedly)
- Duplicate job detection across sources
- Best application source ranking (company site > LinkedIn > Indeed)
- Company research auto-summary
- Recruiter email extraction
- Portal-specific automation (Workday, Greenhouse, Lever)
- Intelligent retry system
- Screenshot capture after each step
- Resume upload failure recovery
- Anti-bot safe typing (50-150ms per char)
- Anti-bot safe clicking (random delays, natural movement)
- Adaptive delays based on portal performance

### Tier 2: Intelligence (11 features)
- Semantic skill matching (not just keyword)
- Role-type classifier (DevOps/SRE/Platform/Cloud/Infrastructure)
- Resume tailoring modes (conservative/balanced/aggressive ATS)
- Truth source mapping (track every change)
- Hallucination detection (verify no invented experience)
- Missing skill impact analysis (learn what to study)
- Interview probability prediction (85% chance of interview)
- Easy Apply detection (LinkedIn)
- Company blacklist & preferred list
- Job filtering rules (skip sponsorship-required, onsite-only, contract-only, low-salary)
- ATS keyword optimization

### Tier 3: Answer Optimization (11 features)
- Dynamic answer ranking (by interview success rate)
- Answer quality scoring (relevance, length, specificity, quantification, STAR format)
- STAR format auto-generation
- Role-specific answer libraries (Kubernetes, Terraform, CI/CD, AWS, incident response)
- Automatic achievement extraction from resume
- AI-generated metrics suggestions
- Resume readability scoring
- Recruiter-friendly formatting
- Resume section reordering (intelligent, job-specific)
- Bullet compression for one-page resumes
- Version history & rollback

### Tier 4: Scheduling & Follow-up (7 features)
- Timezone-aware follow-up scheduling (business hours, company timezone)
- Recruiter response detection from Gmail
- Automatic interview status updates (parse emails)
- Calendar integration for interviews (Google Calendar)
- AI-generated interview prep packs
- Automatic follow-up email generation
- Application batching queue (5 at a time, staggered)

### Tier 5: Interview Preparation (5 features)
- Technical interview simulation (K8s/Terraform/AWS questions)
- Mock DevOps troubleshooting scenarios
- System design interview prep
- Behavioral interview preparation (STAR answers from your projects)
- Company-specific interview questions prediction

### Tier 6: Analytics & Learning (12 features)
- Response analytics dashboard (response rate, interview rate, rejection rate)
- Best-performing resume tracking
- Why rejected pattern analysis
- Skill gap trend analysis
- Personalized learning recommendations
- Observability dashboard
- Queue retry monitoring
- Offline/manual mode
- Export to CSV/PDF
- Chrome extension (future)
- Voice notes for interview prep
- Mobile review interface

### Additional Tiers (38+ features)
- Company tech-stack detection
- GitHub project relevance scoring
- Certification relevance scoring
- Resume-to-job semantic similarity
- Compensation benchmarking by location
- Recruiter response likelihood estimation
- Best time to apply prediction
- Application cooldown rules
- Hidden jobs detector
- Auto-prioritize recently posted
- Local embedding models (no API cost)
- Local LLM fallback (Ollama)
- Encrypted storage
- AI model fallback system (Claude → GPT-4 → GPT-3.5)
- Token usage tracking
- Caching for repeated analysis
- Vector memory for applications
- Answer embedding similarity search
- Confidence scoring per answer
- High-risk answer warnings
- PDF quality validation
- DOCX fallback generation
- Automatic naming conventions
- Multi-resume strategy A/B testing
- Best performing wording learning
- Daily application limits
- Auto cleanup of old files
- Dark mode UI
- And more...

---

## Deliverables Per Application (25 daily)

### 1. PDF Document (10 Sections)
```
1. Company Information (research summary)
2. Job Details (requirements, salary, location)
3. Match Analysis (skills 90%, experience 85%, overall 88%)
4. Resume Customization (before/after comparison)
5. Form Fields (all 8+ fields filled with details)
6. Cover Letter (full personalized text)
7. Interview Preparation (likely questions, company research)
8. Submission Details (confirmation, tracking ID, recruiter)
9. Tracking Information (status, follow-up date, notes)
10. System Metadata (tokens used, API cost, processing time)
```

### 2. Daily Excel Tracker (25 rows)
**Columns**: No., Date, Company, Job Title, Match Score, Interview %, Status, Resume Version, Fields, Submitted At, Follow-up Date, PDF Document Link, Recruiter Email, Notes

Color-coded: Green (85%+), Yellow (70-85%), Red (<70%)

### 3. Master Excel Tracker (Cumulative)
**Tracks all applications across all days with:**
- Response received? (Yes/No)
- Interview scheduled? (Yes/No)
- Offer received? (Yes/No)
- Summary statistics
- Average match score
- Response/interview/offer rates

### 4. Database Records
Store everything in PostgreSQL with full audit trail

---

## Technical Stack

### Backend
- **Framework**: FastAPI (Python)
- **Language**: Python 3.11+
- **Database**: PostgreSQL 16 + pgvector (for vector similarity search)
- **Cache**: Redis
- **Task Queue**: Celery (optional for async tasks)

### Browser Automation
- **Tool**: Playwright (not Selenium)
- **Browsers**: Chromium (primary), Firefox (fallback)
- **Mode**: Headless (invisible, faster)

### AI/LLM
- **Primary AI**: Anthropic Claude API ($5-10/month)
- **Fallback AI**: OpenAI GPT-4 ($2-4/month)
- **Local AI**: Ollama (Mistral 7B, Llama2 13B, Neural Chat 7B - FREE, reduces API cost 70%)

### Vector Search & Embeddings
- **Vector DB**: pgvector (PostgreSQL extension) OR Qdrant
- **Embeddings**: sentence-transformers (local, no API cost)

### Document Generation
- **PDF**: ReportLab
- **Excel**: openpyxl
- **Word**: python-docx

### APIs Required
1. **Anthropic Claude** (https://console.anthropic.com) - $5-10/month
2. **OpenAI GPT-4** (https://platform.openai.com) - $2-4/month (fallback)
3. **Gmail API** (Google Cloud Console) - FREE
4. **Google Calendar API** (Google Cloud Console) - FREE
5. **Crunchbase API** (https://www.crunchbase.com/platform/community) - FREE tier
6. **Gmail SMTP** (native to Gmail with app password) - FREE

---

## Installation & Setup

### Step 1: Install Core Tools (1.5 hours)
- Python 3.12
- Docker Desktop (for PostgreSQL, Redis)
- PostgreSQL 16
- Ollama (local LLM)
- Playwright (browser automation)

### Step 2: Setup APIs (1 hour)
- Get API keys from: Anthropic, OpenAI, Crunchbase
- Download Google OAuth credentials
- Create Gmail app password
- Test all connections

### Step 3: Project Setup (30 minutes)
- Create project structure
- Create virtual environment
- Install Python dependencies
- Create .env file with API keys
- Initialize PostgreSQL database
- Download Ollama models

### Step 4: Test (15 minutes)
- Run health checks
- Test browser automation with single application
- Verify PDF generation
- Verify Excel creation

**Total Setup Time: 2.5-3 hours**

---

## Daily Workflow (40 minutes for 25 apps)

```
10:00 - Start services (PostgreSQL, Redis, Ollama, FastAPI)
10:05 - Load 25 job URLs from Indeed/LinkedIn/company sites
10:10 - Process batch (25 × 96 sec = 40 min):
        - Analyze job (Claude API): 5 sec
        - Customize resume (Ollama local): 10 sec
        - Generate answers (Mix of local + API): 20 sec
        - Fill form (Playwright): 45 sec
        - Submit (manual approval or auto): 10 sec
        - Generate PDF (local): 5 sec
        - Update Excel (local): 1 sec
10:50 - Complete!

OUTPUTS:
✅ 25 PDF documents (in applications/2024-01-15/ folder)
✅ 1 Daily Excel tracker (25 rows + PDF links)
✅ 1 Master Excel updated (all applications)
✅ 25 database records
✅ API cost: ~$5
✅ Time invested: 40 minutes
✅ Time saved vs manual: 5.5 hours
```

---

## Implementation Phases

### Phase 1 (Weeks 1-2): MVP - User Controls Everything
- ✅ Job discovery + analysis
- ✅ Resume customization (user approves)
- ✅ Form field detection + auto-fill
- ✅ Manual form submission (user clicks submit)
- ✅ PDF generation (local)
- ✅ Excel tracking (local)
- ✅ Application tracking to database
**Time per app: 12 minutes | Safety: Maximum (user controls)**

### Phase 2 (Weeks 3-4): Form Auto-Fill
- ✅ Automatic form filling (all fields)
- ✅ CAPTCHA detection + handling
- ✅ Manual user submission (click submit button)
- ✅ Screenshot evidence after each step
- ✅ Answer memory system (saves 40+ hours!)
- ✅ Interview prep generation
**Time per app: 7 minutes | Safety: High**

### Phase 3 (Weeks 5+): Full Automation
- ✅ Auto-submit applications
- ✅ Zero user interaction per application
- ✅ Daily summary email
- ✅ Automatic error fallback (CAPTCHA, bot detection)
- ✅ Gmail monitoring for responses
- ✅ Auto-detect interviews, offers, rejections
- ✅ Follow-up scheduling
**Time per app: 2-3 minutes | Safety: Medium (audit trail)**

---

## Cost Analysis

### Monthly API Cost
```
Anthropic Claude:  $5-10  (complex reasoning)
OpenAI (fallback): $2-4   (if Claude fails)
Gmail API:         FREE
Calendar API:      FREE
Crunchbase:        FREE (tier)
Gmail SMTP:        FREE
Local Ollama:      FREE (saves 70% of API costs!)
─────────────────────────
TOTAL:             $7-14/month

Competitor pricing: $500-2000/month
YOUR SAVINGS:      $486-1986/month
```

### Expected Results (After 50 Applications)
```
Response rate:      25% (target: 20-30%)
Interviews:         12+ (target: 10-20)
Offers:             2+ (target: 1-3)
Time per app:       2.5 min (target: 2-3 min)
Total time:         2 hours (target: <3.5 hours)
Hours saved:        12+ (target: 10+)
API cost:           $2.50 (target: <$3)
PDFs generated:     50 ✅
Excel tracking:     Complete ✅
```

---

## Project Structure

```
job-application-system/
├── docs/                    (All documentation - 9 files)
│   ├── 01_START_HERE.md
│   ├── 02_WINDOWS_SETUP_GUIDE.md
│   ├── 03_APIS_REQUIRED.md
│   ├── 04_DOCUMENT_GENERATION_SYSTEM.md
│   ├── 05_COMPLETE_IMPLEMENTATION_GUIDE.md
│   ├── 06_COMPLETE_SYSTEM_FLOW.md
│   ├── 07_QUICK_REFERENCE.md
│   ├── 08_COMPLETE_FEATURE_LIST.md
│   └── 09_FINAL_SUMMARY.md
│
├── src/
│   ├── main.py              (FastAPI entry point)
│   ├── batch_applications.py (Process 25 apps at once)
│   ├── daily_summary.py     (Generate daily report)
│   ├── test_apis.py         (Test all API connections)
│   ├── config.py            (Configuration)
│   ├── agents/
│   │   ├── profile_agent.py
│   │   ├── resume_agent.py
│   │   ├── job_analysis_agent.py
│   │   ├── match_agent.py
│   │   ├── writing_agent.py
│   │   ├── browser_agent.py
│   │   └── tracking_agent.py
│   └── utils/
│       ├── database.py
│       ├── pdf_generator.py
│       ├── excel_generator.py
│       ├── llm_helper.py
│       └── playwright_helper.py
│
├── applications/            (Generated PDFs, organized by date)
│   ├── 2024-01-15/
│   │   ├── TechCorp_2024_01_15_SeniorDevOpsEngineer.pdf
│   │   └── ... (25 PDFs per day)
│   └── 2024-01-16/
│
├── tracking/                (Excel files)
│   ├── Applications_2024_01_15.xlsx (daily: 25 rows)
│   ├── Applications_2024_01_16.xlsx
│   └── Master_All_Applications.xlsx (cumulative)
│
├── resumes/                 (Resume versions)
│   ├── 2024_01_15_conservative.pdf
│   ├── 2024_01_15_balanced.pdf
│   └── 2024_01_15_aggressive_ats.pdf
│
├── screenshots/             (Form filling evidence)
│   ├── 2024-01-15/
│   │   ├── TechCorp_filled_form.png
│   │   └── TechCorp_submitted.png
│   └── ...
│
├── logs/                    (System logs)
│   ├── application.log
│   ├── api_calls.json
│   └── errors.log
│
├── credentials/             (API credentials - NEVER commit!)
│   └── gmail_credentials.json
│
├── requirements.txt         (Python dependencies)
├── .env                     (API keys - NEVER commit!)
├── .gitignore              (Exclude secrets)
└── README.md               (Project info)
```

---

## Success Criteria

✅ **Phase 1 Complete (Week 2)**
- Can apply to 25 jobs with user control
- PDFs generate correctly
- Excel tracking works
- Time per app: ~12 min

✅ **Phase 2 Complete (Week 4)**
- Auto-fill working (CAPTCHA detection)
- Answer memory saves 40+ hours
- Interview prep generation working
- Time per app: ~7 min

✅ **Phase 3 Complete (Week 6)**
- Full automation working
- Auto-submit + fallbacks
- Gmail monitoring working
- Time per app: ~2-3 min

✅ **Final System**
- 25 applications/day
- 40 minutes processing time
- 25 PDFs generated
- Excel tracking complete
- $7-14/month cost
- 10+ hours saved vs manual

---

## Important Notes

1. **Use Playwright, not Selenium** - Faster, better for headless automation
2. **Use Chromium browser** - Most compatible with job sites
3. **Use Ollama for 70% cost reduction** - Local LLM for simple tasks, Claude API for complex
4. **Truth verification is critical** - No hallucinated experience, verify against original resume
5. **Phase it gradually** - Start with MVP (user control), then add auto-fill, then full automation
6. **Rate limiting is essential** - Use 45-second delays between applications to avoid bot detection
7. **Audit trail required** - Log every change, timestamp everything, store original vs modified
8. **Fallback strategies needed** - Always have manual fallback, CAPTCHA handling, error recovery

---

## This Prompt Will Build:

✅ **Intelligent job automation system** with 92 features
✅ **7 specialized agents** orchestrating the workflow
✅ **6 core system layers** providing structure
✅ **Local Ollama AI** for 70% cost reduction
✅ **Professional PDF documents** (10 sections each)
✅ **Excel tracking** (daily + master trackers)
✅ **Complete browser automation** (Playwright)
✅ **Answer memory engine** (saves 40+ hours)
✅ **Interview preparation system** (automatic)
✅ **Compliance & audit trail** (full logging)
✅ **Production-ready code** (with error handling)
✅ **3 implementation phases** (MVP → Auto-fill → Full)

---

## Start Building!

This prompt gives Cowork everything needed to build a world-class job application system. The documentation (9 files) provides step-by-step guidance, code examples, API setup, and troubleshooting.

**Total value: Professional service would cost $10,000+. Your cost: $7-14/month!**

Good luck! 🚀
