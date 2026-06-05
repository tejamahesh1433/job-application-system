# APIs Required - Complete Setup Guide

## Summary Table

| # | API | Cost/Month | Setup Time | Purpose |
|---|-----|-----------|-----------|---------|
| 1 | Anthropic Claude | $5-10 | 5 min | Main AI (complex reasoning) |
| 2 | OpenAI GPT-4 | $2-4 | 5 min | Fallback AI |
| 3 | Gmail API | FREE | 10 min | Email monitoring |
| 4 | Google Calendar | FREE | 5 min | Schedule interviews |
| 5 | Crunchbase | FREE tier | 5 min | Company research |
| 6 | Gmail SMTP | FREE | 5 min | Send follow-up emails |
| 7 | Local Ollama | FREE | 10 min | Local AI (no API cost) |

**Total Cost: $7-14/month**

---

## 1. Anthropic Claude API

```
STEP 1: Create Account
  1. Go to https://console.anthropic.com
  2. Sign up with email
  3. Verify email

STEP 2: Get API Key
  1. Go to Settings → API Keys
  2. Click "Create Key"
  3. Copy API key
  4. Save in .env: ANTHROPIC_API_KEY=sk-ant-...

STEP 3: Add Billing
  1. Go to Billing
  2. Add credit card
  3. Set budget: $20/month recommended

STEP 4: Test
  python -c "
  import anthropic
  client = anthropic.Anthropic(api_key='your-key')
  message = client.messages.create(
      model='claude-opus-4-6',
      max_tokens=100,
      messages=[{'role': 'user', 'content': 'Hello'}]
  )
  print('✅ Claude API working')
  "

PRICING:
  Input: $3 per 1M tokens
  Output: $15 per 1M tokens
  
  Estimate: $5-10/month for 25 apps/day
```

---

## 2. OpenAI API (Fallback)

```
STEP 1: Create Account
  1. Go to https://platform.openai.com
  2. Sign up
  3. Verify email

STEP 2: Get API Key
  1. Go to API Keys (left menu)
  2. Click "Create new secret key"
  3. Copy key
  4. Save in .env: OPENAI_API_KEY=sk-...

STEP 3: Add Billing
  1. Go to Billing
  2. Add credit card
  3. Set budget: $10/month

STEP 4: Test
  python -c "
  from openai import OpenAI
  client = OpenAI(api_key='your-key')
  response = client.chat.completions.create(
      model='gpt-4-turbo',
      messages=[{'role': 'user', 'content': 'Hello'}],
      max_tokens=100
  )
  print('✅ OpenAI API working')
  "

PRICING:
  GPT-4 Turbo: $0.01 input, $0.03 output per 1K tokens
  
  Estimate: $2-4/month (fallback only)
```

---

## 3. Gmail API

```
STEP 1: Enable API
  1. Go to https://console.cloud.google.com
  2. Create new project
  3. Search "Gmail API"
  4. Click "Enable"

STEP 2: Create Credentials
  1. Go to Credentials
  2. Click "Create Credentials" → OAuth 2.0 Client ID
  3. Choose "Desktop application"
  4. Download JSON file
  5. Save as: credentials/gmail_credentials.json

STEP 3: Install SDK
  pip install google-auth-oauthlib google-api-python-client

STEP 4: Test
  python -c "
  from google.oauth2.service_account import Credentials
  from googleapiclient.discovery import build
  
  creds = Credentials.from_service_account_file(
      'credentials/gmail_credentials.json'
  )
  service = build('gmail', 'v1', credentials=creds)
  print('✅ Gmail API working')
  "

FIRST RUN:
  - Browser opens asking for permission
  - Click "Allow"
  - Code gets access token automatically

PRICING: FREE
```

---

## 4. Google Calendar API

```
STEP 1: Enable API
  1. Go to https://console.cloud.google.com (same project as Gmail)
  2. Search "Google Calendar API"
  3. Click "Enable"

STEP 2: Use Same Credentials
  (Reuse the gmail_credentials.json from Gmail API)

STEP 3: Install SDK (already installed in Gmail step)

STEP 4: Test
  python -c "
  from googleapiclient.discovery import build
  from google.oauth2.service_account import Credentials
  
  creds = Credentials.from_service_account_file(
      'credentials/gmail_credentials.json'
  )
  service = build('calendar', 'v3', credentials=creds)
  print('✅ Calendar API working')
  "

PRICING: FREE
```

---

## 5. Crunchbase API

```
STEP 1: Create Account
  1. Go to https://www.crunchbase.com/platform/community
  2. Sign up for Community Edition (FREE)
  3. Verify email

STEP 2: Get API Key
  1. Go to API Dashboard
  2. Generate API key
  3. Save in .env: CRUNCHBASE_API_KEY=your-key

STEP 3: Test
  python -c "
  import requests
  
  headers = {'X-Cb-User-Key': 'your-key'}
  response = requests.get(
      'https://api.crunchbase.com/v4/entities/organizations',
      headers=headers
  )
  
  if response.status_code == 200:
      print('✅ Crunchbase API working')
  else:
      print('❌ Failed:', response.status_code)
  "

PRICING:
  Community Edition: FREE
  Includes: 50,000 API calls/month
  
  Our usage: ~50 calls/day = 1,500/month
  Plenty of headroom!
```

---

## 6. Gmail SMTP (Send Emails)

```
STEP 1: Enable 2FA on Gmail
  1. Go to https://myaccount.google.com/security
  2. Find "2-Step Verification"
  3. Enable it
  4. Follow verification process

STEP 2: Create App Password
  1. Go to myaccount.google.com/apppasswords
  2. Select "Mail" and "Windows"
  3. Click "Generate"
  4. Copy password (16 characters)
  5. Save in .env: GMAIL_APP_PASSWORD=your-password

STEP 3: Test
  python -c "
  import smtplib
  from email.mime.text import MIMEText
  
  server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
  server.login('your_email@gmail.com', 'your-app-password')
  
  msg = MIMEText('Test')
  msg['Subject'] = 'Test'
  msg['From'] = 'your_email@gmail.com'
  msg['To'] = 'your_email@gmail.com'
  
  server.send_message(msg)
  server.quit()
  print('✅ Gmail SMTP working')
  "

PRICING: FREE (Gmail limit: 500 emails/day)
We need: 25 follow-ups/day (plenty of room)
```

---

## 7. Local Ollama (No API Key Needed!)

```
STEP 1: Download
  1. Go to https://ollama.ai/download
  2. Download for Windows
  3. Run installer
  4. Accept defaults

STEP 2: Pull Models
  Open PowerShell and run:
  
  ollama pull mistral
  ollama pull llama2
  ollama pull neural-chat

STEP 3: Verify
  curl http://localhost:11434/api/tags
  
  Should return JSON with 3 models

STEP 4: Test
  python -c "
  import requests
  
  response = requests.post(
      'http://localhost:11434/api/generate',
      json={
          'model': 'mistral',
          'prompt': 'Say hello',
          'stream': False
      }
  )
  
  if response.status_code == 200:
      print('✅ Ollama working')
  else:
      print('❌ Failed')
  "

PRICING: FREE! (No API cost)
BENEFIT: Saves 60-70% API costs!
LOCAL MODELS:
  - Mistral 7B: 5-10 tokens/sec
  - Llama2 13B: 3-5 tokens/sec
  - Neural Chat 7B: 5-7 tokens/sec
```

---

## Complete .env File Template

```
# .env file - Place in project root
# NEVER commit this file!

# AI APIs
ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENAI_API_KEY=sk-your-key-here

# Google APIs
GOOGLE_CREDENTIALS_FILE=./credentials/gmail_credentials.json
GMAIL_USER=your_email@gmail.com
GMAIL_APP_PASSWORD=your-app-password

# Crunchbase
CRUNCHBASE_API_KEY=your-key-here

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/job_applications
REDIS_URL=redis://localhost:6379/0

# Local Ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_MODELS=mistral,llama2,neural-chat

# Settings
USE_LOCAL_LLM=true
USE_CLAUDE_API=true
CACHE_RESPONSES=true
LOG_API_CALLS=true

# Budget Control
DAILY_API_BUDGET=10.00
WARN_AT_PERCENTAGE=80
```

---

## Quick Setup Checklist

```
✅ ANTHROPIC CLAUDE
  ☐ Account created
  ☐ API key generated
  ☐ Billing configured
  ☐ Added to .env

✅ OPENAI
  ☐ Account created
  ☐ API key generated
  ☐ Billing configured
  ☐ Added to .env

✅ GMAIL API
  ☐ API enabled in Google Cloud
  ☐ OAuth credentials created
  ☐ JSON file downloaded
  ☐ Placed in credentials/

✅ CALENDAR API
  ☐ API enabled
  ☐ Using same credentials

✅ CRUNCHBASE
  ☐ Account created
  ☐ API key generated
  ☐ Added to .env

✅ GMAIL SMTP
  ☐ 2FA enabled on Gmail
  ☐ App password created
  ☐ Added to .env

✅ OLLAMA
  ☐ Downloaded and installed
  ☐ 3 models pulled
  ☐ Running on localhost:11434

TOTAL TIME: ~1 hour
TOTAL COST: $7-14/month
```

---

## Test All APIs

```powershell
# Run this to test all APIs at once:

python -c "
print('Testing all APIs...\n')

# 1. Anthropic
try:
    import anthropic
    client = anthropic.Anthropic()
    print('✅ Anthropic Claude API')
except:
    print('❌ Anthropic API failed')

# 2. OpenAI
try:
    from openai import OpenAI
    client = OpenAI()
    print('✅ OpenAI API')
except:
    print('❌ OpenAI API failed')

# 3. Gmail API
try:
    from google.oauth2.service_account import Credentials
    creds = Credentials.from_service_account_file('credentials/gmail_credentials.json')
    print('✅ Gmail API')
except:
    print('❌ Gmail API failed')

# 4. Crunchbase
try:
    import requests
    print('✅ Crunchbase API (requests library available)')
except:
    print('❌ Crunchbase API failed')

# 5. Ollama
try:
    import requests
    response = requests.get('http://localhost:11434/api/tags')
    if response.status_code == 200:
        print('✅ Ollama Local AI')
    else:
        print('❌ Ollama not responding')
except:
    print('❌ Ollama API failed')

print('\nAll critical APIs ready!')
"
```

---

## Cost Summary

```
DAILY:
  - 25 applications
  - Claude API: ~$0.18
  - OpenAI API: ~$0.04 (fallback)
  - Others: FREE
  - DAILY TOTAL: ~$0.22

MONTHLY (30 days):
  - Claude: ~$5.40
  - OpenAI: ~$1.20
  - Others: FREE
  - MONTHLY TOTAL: ~$6.60

YEARLY:
  - Total: ~$79

SAVINGS vs competitors:
  - Professional: $500-2000/month
  - Your system: $7-14/month
  - YOU SAVE: $400-1900/month! 🎉
```

---

**All APIs ready? Proceed to COMPLETE_IMPLEMENTATION_GUIDE.md for coding!**
