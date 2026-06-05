# Windows Setup Guide - Complete Installation

## Step 1: Python Installation (5 min)

```
1. Go to https://www.python.org/downloads/
2. Download Python 3.12 (Windows installer)
3. Run installer
4. ✅ CHECK: "Add Python to PATH"
5. Click Install Now
6. Wait for completion

Verify:
  Open PowerShell, type:
  python --version
  
  Should show: Python 3.12.x
```

---

## Step 2: Docker Installation (15 min)

```
1. Go to https://www.docker.com/products/docker-desktop
2. Download Docker Desktop for Windows
3. Run installer
4. Accept defaults
5. When prompted, enable WSL 2:
   - Open PowerShell as Admin
   - Run: wsl --install
   - Restart computer
6. Launch Docker Desktop
7. Wait for "Docker is running"

Verify:
  Open PowerShell, type:
  docker --version
  
  Should show: Docker version X.X.X
```

---

## Step 3: PostgreSQL Installation (10 min)

```
1. Go to https://www.postgresql.org/download/windows/
2. Download PostgreSQL 16
3. Run installer
4. Set password for 'postgres' user (save this!)
   Example: MyPostgres123!
5. Port: 5432 (default)
6. When asked about pgvector, enable it
7. Finish installation

Verify:
  Open Command Prompt, type:
  psql -U postgres
  
  Enter password when prompted
  Type: \version
  
  Should show PostgreSQL version
  Type: \q to exit
```

---

## Step 4: Ollama Installation (10 min)

```
1. Go to https://ollama.ai/download
2. Download Ollama for Windows
3. Run installer
4. Accept defaults
5. Ollama will run as background service
6. Restart computer (or restart Ollama)

Verify:
  Open PowerShell, type:
  curl http://localhost:11434/api/tags
  
  Should return JSON with model list
```

---

## Step 5: Download Ollama Models (10 min)

```
Open PowerShell and run:

ollama pull mistral
ollama pull llama2
ollama pull neural-chat

Wait for each to download (10-15 min total)

Verify:
  ollama list
  
  Should show all 3 models installed
```

---

## Step 6: Create Project Directory (5 min)

```powershell
# Create main project folder
mkdir C:\Users\YourUsername\job-application-system
cd C:\Users\YourUsername\job-application-system

# Create subfolders
mkdir docs
mkdir src
mkdir src\agents
mkdir applications
mkdir tracking
mkdir resumes
mkdir screenshots
mkdir logs
mkdir cache
mkdir credentials

# Check structure
dir

# Should show:
# docs, src, applications, tracking, etc.
```

---

## Step 7: Setup Python Virtual Environment (5 min)

```powershell
# Navigate to project
cd C:\Users\YourUsername\job-application-system

# Create virtual environment
python -m venv venv

# Activate it
.\venv\Scripts\Activate.ps1

# You should see (venv) at start of each line now
```

---

## Step 8: Install Python Dependencies (5 min)

```powershell
# Make sure you're in activated environment
# (venv) should be visible at start of line

# Copy all files from outputs to your project/docs folder first

# Create requirements.txt file with this content:
pip install playwright
pip install fastapi
pip install uvicorn
pip install psycopg2-binary
pip install sqlalchemy
pip install anthropic
pip install openai
pip install google-auth-oauthlib
pip install google-api-python-client
pip install openpyxl
pip install reportlab
pip install python-dotenv
pip install requests
pip install sentence-transformers

# OR create requirements.txt and run:
pip install -r requirements.txt
```

---

## Step 9: Install Playwright Browsers (5 min)

```powershell
# Make sure you're in activated environment

playwright install chromium
playwright install firefox
playwright install webkit

# Or all at once:
playwright install

# Wait for browser downloads to complete (~1GB)
```

---

## Step 10: Create .env File (5 min)

```powershell
# In project root, create .env file with:

ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENAI_API_KEY=sk-your-key-here
GOOGLE_CREDENTIALS_FILE=./credentials/gmail_credentials.json
CRUNCHBASE_API_KEY=your-key-here
GMAIL_USER=your_email@gmail.com
GMAIL_APP_PASSWORD=your-app-password
DATABASE_URL=postgresql://postgres:your-password@localhost:5432/job_applications
REDIS_URL=redis://localhost:6379/0
OLLAMA_URL=http://localhost:11434
USE_LOCAL_LLM=true
```

---

## Step 11: Setup PostgreSQL Database (10 min)

```powershell
# Open Command Prompt
psql -U postgres

# When prompted, enter password

# Then run these commands:
CREATE DATABASE job_applications;
\c job_applications
CREATE EXTENSION IF NOT EXISTS vector;

# You should see: CREATE EXTENSION

# Type: \q to exit
```

---

## Step 12: Download and Place Google Credentials (5 min)

```
1. Go to https://console.cloud.google.com
2. Create new project
3. Enable "Gmail API" and "Google Calendar API"
4. Go to Credentials
5. Create OAuth 2.0 Client ID (Desktop)
6. Download JSON file
7. Rename to: gmail_credentials.json
8. Move to: C:\Users\YourUsername\job-application-system\credentials\

Your folder should look like:
  credentials\
    └─ gmail_credentials.json
```

---

## Step 13: Test Everything (10 min)

```powershell
# Make sure you're in activated environment
# cd C:\Users\YourUsername\job-application-system
# .\venv\Scripts\Activate.ps1

# Test 1: Python
python --version
# Should show: Python 3.12.x

# Test 2: PostgreSQL
psql -U postgres -d job_applications -c "SELECT 1"
# Should show: 1

# Test 3: Ollama
curl http://localhost:11434/api/tags
# Should return JSON with models

# Test 4: Playwright
python -c "from playwright.sync_api import sync_playwright; print('✅ Playwright OK')"

# Test 5: Docker
docker ps
# Should show running containers (might be empty, that's OK)

# Test 6: Redis (optional)
docker run -d -p 6379:6379 redis:latest
# Then test:
redis-cli ping
# Should return: PONG
```

---

## Step 14: Create Main Python File (5 min)

Create `src/main.py` with basic content:

```python
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/health")
async def health_check():
    return JSONResponse({"status": "healthy"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Step 15: Start Your System (5 min)

```powershell
# Terminal 1: Activate venv
cd C:\Users\YourUsername\job-application-system
.\venv\Scripts\Activate.ps1

# Terminal 2: Start FastAPI
cd C:\Users\YourUsername\job-application-system
.\venv\Scripts\Activate.ps1
python src/main.py

# Terminal 3: Start Redis
docker run -d -p 6379:6379 redis:latest

# Terminal 4: Start PostgreSQL (if using Docker)
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:16

# Or PostgreSQL already running from Step 3

# Test in browser:
http://localhost:8000/health
# Should show: {"status":"healthy"}
```

---

## Troubleshooting

### "Python not found"
- Restart PowerShell
- Verify Python in PATH: python --version

### "Docker not starting"
- Enable WSL 2: wsl --install
- Enable Hyper-V in Windows Features
- Restart computer

### "PostgreSQL connection refused"
- Check PostgreSQL running: Get-Process postgres
- Verify password is correct
- Reset password: ALTER USER postgres WITH PASSWORD 'newpassword';

### "Ollama not responding"
- Check it's running: http://localhost:11434/api/tags
- Restart Ollama service
- Verify GPU: nvidia-smi

### "Playwright browser not found"
- Reinstall: playwright install chromium
- Check disk space (need ~1GB)

---

## ✅ Success Checklist

- ☐ Python 3.12 installed
- ☐ Docker Desktop running
- ☐ PostgreSQL running on port 5432
- ☐ Ollama running on port 11434
- ☐ 3 Ollama models downloaded
- ☐ Project folders created
- ☐ Virtual environment activated
- ☐ Dependencies installed
- ☐ Playwright browsers installed
- ☐ .env file created with API keys
- ☐ Google credentials file placed
- ☐ PostgreSQL database created
- ☐ All tests passing
- ☐ FastAPI runs on http://localhost:8000

**If all checkmarks are done, you're ready to build! 🚀**

---

## Next Steps

1. Download all documentation files to `docs/` folder
2. Read COMPLETE_IMPLEMENTATION_GUIDE.md for code structure
3. Read APIS_REQUIRED.md to get API keys
4. Start with 5 test applications
5. Scale to 25+ per day

**Total setup time: 2-3 hours**
