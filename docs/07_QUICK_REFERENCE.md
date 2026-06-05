# Quick Reference Guide

## 1. Installation Checklist

```
INSTALLATION ORDER:

1. Python 3.12         [ ] Time: 5 min
2. Docker Desktop      [ ] Time: 15 min
3. PostgreSQL 16       [ ] Time: 10 min
4. Ollama              [ ] Time: 10 min
5. Playwright          [ ] Time: 5 min
6. Project setup       [ ] Time: 5 min
7. Dependencies        [ ] Time: 5 min
8. Google credentials  [ ] Time: 10 min
9. .env configuration  [ ] Time: 5 min
10. Test all          [ ] Time: 10 min

TOTAL TIME: 80 minutes (~1.5 hours)
```

---

## 2. API Quick Setup

```
API               | Cost/Month | Setup Time | Status
─────────────────┼───────────┼───────────┼────────
Anthropic Claude | $5-10     | 5 min     | REQUIRED
OpenAI GPT-4    | $2-4      | 5 min     | FALLBACK
Gmail API       | FREE      | 10 min    | REQUIRED
Calendar API    | FREE      | 5 min     | OPTIONAL
Crunchbase      | FREE      | 5 min     | OPTIONAL
Gmail SMTP      | FREE      | 5 min     | OPTIONAL
Ollama (local)  | FREE      | 10 min    | SAVES 70%
─────────────────┼───────────┼───────────┼────────
TOTAL          | $7-14     | 45 min    |

Total Cost: ~$84-168/year
Competitor Cost: ~$6000-24000/year
SAVINGS: $5900-23900/year!
```

---

## 3. Daily Workflow Timeline

```
Time    | Action                        | Duration | Output
────────┼──────────────────────────────┼─────────┼──────────────
10:00   | Start services               | 2 min   | Services online
10:02   | Load 25 jobs                 | 3 min   | Job list ready
10:05   | Process jobs (batch)         | 40 min  | See below...
10:45   | Generate summary             | 5 min   | Report ready
────────┼──────────────────────────────┼─────────┼──────────────

Per Application (40 min ÷ 25 = 96 sec):
- Analyze job:           5 sec
- Customize resume:      10 sec
- Generate answers:      20 sec
- Fill form:             45 sec
- Submit:                10 sec
- Generate PDF:          5 sec
- Update Excel:          1 sec
TOTAL:                   96 sec ≈ 1.5 min
```

---

## 4. Browser Selection

```
Browser    | Speed | Compatibility | Size | Best For
───────────┼───────┼──────────────┼──────┼────────────────
Chromium   | ⚡⚡⚡⚡⚡ | ⭐ Best     | 380MB| PRIMARY (use)
Firefox    | ⚡⚡⚡⚡  | ⭐ Good     | 340MB| Fallback
WebKit     | ⚡⚡⚡⚡⚡ | ⚠️  Limited | 400MB| Testing

RECOMMENDATION: Use Chromium
INSTALL: playwright install chromium
```

---

## 5. Job Sources & Sites

```
Source          | Jobs Available | Difficulty | Recommended
────────────────┼───────────────┼───────────┼─────────────
Indeed.com      | 50,000+       | Easy      | ✅ Primary
LinkedIn.com    | 100,000+      | Medium    | ✅ Primary
Company careers | 500,000+      | Easy      | ✅ Direct
ZipRecruiter    | 50,000+       | Easy      | ✅
Angel List      | 20,000+       | Medium    | ✅
GitHub Jobs     | 10,000+       | Easy      | ⭕ Optional
Crunchbase      | API only      | API       | ⭕ Alternative
Recruiter email | Direct        | Manual    | 🔧 Manual
```

---

## 6. File Sizes & Storage

```
Type              | Size/Unit  | Daily (25) | Monthly (750) | Yearly
──────────────────┼───────────┼───────────┼──────────────┼────────
PDF per app       | 150-200KB | 4-5 MB    | 120-150 MB   | 1.5 GB
Excel daily       | 50 KB     | 50 KB     | 1.5 MB       | 20 MB
Excel master      | 100 KB    | grows     | grows        | grows
Screenshots       | 1-2 MB    | 25-50 MB  | 750 MB       | 10 GB
Database          | varies    | 5-10 MB   | 150 MB       | 2 GB
Total per day     |           | 30-60 MB  |              |
Total per month   |           |           | 1-2 GB       |
Total per year    |           |           |              | 12-15 GB

Your SSD: 6 TB
Storage used: <1%
You can store: 5 MILLION applications!
```

---

## 7. Python Packages Required

```
Category     | Package              | Version  | Purpose
─────────────┼──────────────────────┼─────────┼──────────────────
Framework   | fastapi              | 0.104   | API framework
            | uvicorn              | 0.24    | ASGI server
Browser     | playwright           | 1.40    | Automation
Database    | sqlalchemy           | 2.0     | ORM
            | psycopg2-binary      | 2.9     | PostgreSQL driver
AI/LLM      | anthropic            | 0.7     | Claude API
            | openai               | 1.3     | OpenAI API
Documents   | openpyxl             | 3.11    | Excel
            | reportlab            | 4.0     | PDF
Google      | google-auth-*        | 1.1     | Gmail API
Utilities   | python-dotenv        | 1.0     | .env loading
            | requests             | 2.31    | HTTP requests
```

---

## 8. Database Tables Summary

```
Table                    | Purpose                    | Key Fields
────────────────────────┼────────────────────────────┼─────────────────
users                   | User accounts              | id, email, name
user_profiles           | Your skills/experience    | id, skills, exp
jobs                    | Job postings              | id, title, url
job_analysis            | Parsed job requirements   | id, skills, ats
applications            | Your applications        | id, status, date
saved_answers           | Answer memory            | id, question, ans
application_documents   | PDFs                      | id, doc_path
daily_excel_trackers    | Daily Excel files        | id, date, count
interviews              | Interview scheduling     | id, date, type
```

---

## 9. Troubleshooting Quick Fixes

```
Problem                      | Solution
─────────────────────────────┼──────────────────────────────
Python not found            | Restart PowerShell, verify PATH
Docker won't start          | Enable WSL 2, enable Hyper-V
PostgreSQL connection error | Check password, port 5432
Ollama not responding       | Restart Ollama, verify http://localhost:11434
Playwright browser missing  | playwright install chromium
Google credentials error    | Download JSON again, check path
API key invalid            | Verify .env file, check typos
Form fill fails            | Check CSS selectors, try headful mode
RAM/CPU high              | Reduce parallel browsers from 5 to 2
Disk space warning        | You have 6TB, shouldn't happen
```

---

## 10. Success Metrics

```
Metric                  | Target    | After 50 apps | After 100 apps
────────────────────────┼──────────┼──────────────┼──────────────
Applications submitted  | 25/day   | 50           | 100
Response rate          | 20-30%   | 25%          | 25%+
Interviews scheduled   | 10-20    | 12           | 20+
Offers received        | 2-4      | 2            | 3+
Time per application   | 2-3 min  | 2.5 min      | 2 min
Total time per 25 apps | 40 min   | 40 min       | 40 min
API cost per day       | <$1      | $0.70        | $0.70
API cost per month     | <$30     | $21          | $21
Hours saved vs manual  | 10+      | 12+          | 25+
```

---

## 11. Match Score Guide

```
Score    | Status           | Action        | Interview %
─────────┼──────────────────┼──────────────┼──────────────
85-100%  | STRONG MATCH ✅  | Apply NOW    | 85%+
70-85%   | GOOD MATCH ✅    | Apply        | 70-85%
50-70%   | MODERATE ⚠️      | Apply (caution)| 50-70%
<50%     | WEAK MATCH ❌    | SKIP         | <50%
```

---

## 12. Resume Mode Guide

```
Mode         | Original | Custom | Best For           | ATS | Interview %
─────────────┼──────────┼────────┼───────────────────┼─────┼──────────
Conservative | 90%      | 10%    | Safe, no risk      | 70% | 60%
Balanced     | 50%      | 50%    | Default (best)     | 88% | 75%
Aggressive   | 30%      | 70%    | High risk, high    | 95% | 80%
             |          |        | ATS keyword push   |     |

RECOMMENDATION: Use "Balanced" by default
              Switch to "Conservative" if worried
              Use "Aggressive" for known ATS sites
```

---

## 13. Excel Shortcuts

```
Column          | Width  | Purpose
────────────────┼────────┼─────────────────────────
No.             | 5      | Number 1-25
Date Applied    | 12     | YYYY-MM-DD
Company         | 15     | Company name
Job Title       | 25     | Role title
Match Score     | 10     | Color coded
Interview %     | 12     | 0-100%
Status          | 10     | APPLIED, OFFERED, etc
Resume Version  | 12     | conservative/balanced/aggressive
Form Fields     | 10     | How many filled
Submitted At    | 12     | HH:MM time
Follow-up Date  | 12     | YYYY-MM-DD
PDF Link        | 35     | CLICK to open
Recruiter Email | 20     | hiring@company.com
Notes           | 20     | Match score, notes
```

---

## 14. API Cost Per Operation

```
Operation                        | Tokens | Cost
─────────────────────────────────┼────────┼─────────
Analyze job (Claude)             | 1,500  | $0.0045
Match scoring (Claude)           | 800    | $0.0024
Resume customization (Ollama)    | —      | $0
Answer generation (Mix)          | 2,100  | $0.0063
Interview prep (Claude)          | 1,500  | $0.0045
Cover letter (Ollama)            | —      | $0
PDF generation (Local)           | —      | $0
Excel update (Local)             | —      | $0
─────────────────────────────────┼────────┼──────────
TOTAL PER APPLICATION            | 6,400  | $0.028
```

---

## 15. Common Commands

```powershell
# Start everything
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Test APIs
python src/test_apis.py

# Run batch
python src/batch_applications.py --count=25

# Check results
dir applications\
dir tracking\

# Activate on startup
.\venv\Scripts\Activate.ps1

# Deactivate when done
deactivate
```

---

## 16. File Download Checklist

```
✅ Essential Files (MUST DOWNLOAD):
  [ ] 01_START_HERE.md
  [ ] 02_WINDOWS_SETUP_GUIDE.md
  [ ] 03_APIS_REQUIRED.md
  [ ] 04_DOCUMENT_GENERATION_SYSTEM.md
  [ ] 05_COMPLETE_IMPLEMENTATION_GUIDE.md
  [ ] 06_COMPLETE_SYSTEM_FLOW.md
  [ ] 07_QUICK_REFERENCE.md (this file)

⭐ Recommended (SHOULD DOWNLOAD):
  [ ] 08_COMPLETE_FEATURE_LIST.md
  [ ] 09_INDEX.md

📚 Optional (NICE TO HAVE):
  [ ] ARCHITECTURE_DETAILED.js
  [ ] WORKFLOW_EXAMPLES.js
  [ ] COMPLETE_SUMMARY.md
```

---

**Now you have the complete quick reference! Print or bookmark this page!**
