# AI Web Tester

AI-powered website quality checker. Describe a test goal in plain English, and the AI controls a real browser to verify it — then reports pass/fail with screenshots.

## Tech Stack
- **AI Brain**: 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 (ANTHROPIC_API_KEY)
- **Browser**: Playwright (Python)
- **Backend**: FastAPI
- **Frontend**: Next.js + Tailwind CSS
- **Database**: SQLite

## Project Structure
```
ai-web-tester/
├── backend/
│   ├── main.py          # FastAPI server (POST /test, GET /tests)
│   ├── agent.py         # Claude AI agent loop
│   ├── browser.py       # Playwright browser controller
│   ├── database.py      # SQLite storage
│   ├── screenshots/     # Test screenshots saved here
│   ├── requirements.txt
│   └── .env             # ANTHROPIC_API_KEY goes here
├── frontend/
│   ├── pages/index.js   # Main chat UI
│   ├── components/
│   │   ├── TestResult.js
│   │   └── HistoryPanel.js
│   └── package.json
└── README.md
```

## Setup & Run

### 1. Backend

```bash
cd backend

# Copy env file and add your API key
copy .env.example .env
# Edit .env: ANTHROPIC_API_KEY=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 

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Start backend
python main.py
# Runs at http://localhost:8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# Runs at http://localhost:3000
```

## Usage

1. Open http://localhost:3000
2. Enter a website URL
3. Describe your test goal in plain English
4. Optionally add login credentials
5. Click **Run Test**
6. Watch the AI execute steps and see the result with screenshots

## Example Test Goals
- "Check if the homepage loads and has a navigation menu"
- "Test the login flow with correct credentials"
- "Verify the contact form can be submitted"
- "Check if the search returns results"
- "Test that clicking the signup button opens the registration form"

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /test | Run a new test |
| GET | /tests | List all past tests |
| GET | /tests/{id} | Get specific test details |
| DELETE | /tests/{id} | Delete a test record |
| GET | /health | Health check |

## Database Schema (SQLite)

**test_runs**: id, url, goal, status, final_verdict, duration, total_steps, passed_steps, failed_steps, error, created_at

**test_steps**: id, test_run_id, step_number, action, target, value, reasoning, status, error_message, screenshot_path, created_at
