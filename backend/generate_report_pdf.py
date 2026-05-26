"""
Generates a PDF summary of the AI Web Tester project built today.
Run: python generate_report_pdf.py
Output: AI_Web_Tester_Project_Report.pdf  (same folder as this script)
"""

import asyncio
import os
from playwright.async_api import async_playwright

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PDF = os.path.join(BASE_DIR, "AI_Web_Tester_Project_Report.pdf")

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: #1e293b; background: #fff; }

  /* ---------- cover ---------- */
  .cover {
    background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 100%);
    color: #fff;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 60px 40px;
    page-break-after: always;
  }
  .cover .badge {
    background: rgba(255,255,255,0.15);
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: 50px;
    padding: 6px 20px;
    font-size: 12px;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 28px;
  }
  .cover h1 { font-size: 42px; font-weight: 800; line-height: 1.15; margin-bottom: 16px; }
  .cover .sub { font-size: 18px; opacity: 0.85; margin-bottom: 40px; }
  .cover .meta { font-size: 13px; opacity: 0.65; line-height: 2; }
  .cover .stack-grid {
    display: grid; grid-template-columns: repeat(3,1fr); gap: 16px;
    margin: 36px 0; width: 100%; max-width: 600px;
  }
  .cover .stack-item {
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 12px; padding: 14px 12px; font-size: 12px;
  }
  .cover .stack-item .label { opacity: 0.6; font-size: 10px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
  .cover .stack-item .value { font-weight: 700; font-size: 13px; }

  /* ---------- page layout ---------- */
  .page { padding: 48px 52px; page-break-after: always; }
  .page:last-child { page-break-after: auto; }

  /* ---------- section ---------- */
  .section-label {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 2px; color: #2563eb; margin-bottom: 10px;
    padding-bottom: 6px; border-bottom: 2px solid #dbeafe;
  }
  h2 { font-size: 22px; font-weight: 800; color: #0f172a; margin-bottom: 20px; }
  h3 { font-size: 15px; font-weight: 700; color: #1e3a5f; margin: 24px 0 10px; }
  p { line-height: 1.7; color: #374151; margin-bottom: 10px; }

  /* ---------- table ---------- */
  table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 12px; }
  th { background: #1e3a5f; color: #fff; padding: 10px 14px; text-align: left; font-weight: 600; font-size: 11px; }
  td { padding: 9px 14px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
  tr:nth-child(even) td { background: #f8fafc; }
  tr:hover td { background: #eff6ff; }

  /* ---------- code ---------- */
  pre {
    background: #0f172a; color: #e2e8f0;
    border-radius: 10px; padding: 18px 20px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11.5px; line-height: 1.65;
    overflow: hidden; margin: 12px 0; white-space: pre-wrap;
  }
  code { background: #dbeafe; color: #1e40af; padding: 2px 6px; border-radius: 4px; font-size: 11.5px; font-family: 'Consolas', monospace; }

  /* ---------- cards ---------- */
  .card {
    background: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 12px; padding: 20px; margin: 12px 0;
  }
  .card-title { font-weight: 700; color: #1e3a5f; margin-bottom: 8px; font-size: 14px; }

  /* ---------- flow ---------- */
  .flow { display: flex; flex-direction: column; gap: 0; margin: 16px 0; }
  .flow-step {
    display: flex; align-items: flex-start; gap: 16px; padding: 14px 18px;
    background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; margin-bottom: 6px;
  }
  .flow-num {
    width: 28px; height: 28px; background: #2563eb; color: #fff;
    border-radius: 50%; display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 12px; flex-shrink: 0;
  }
  .flow-content .title { font-weight: 700; font-size: 13px; color: #1e3a5f; }
  .flow-content .desc { font-size: 12px; color: #64748b; margin-top: 2px; }

  /* ---------- verdict chips ---------- */
  .chip {
    display: inline-block; padding: 3px 10px; border-radius: 20px;
    font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
  }
  .chip-pass { background: #dcfce7; color: #15803d; }
  .chip-fail { background: #fee2e2; color: #b91c1c; }
  .chip-fix  { background: #fef3c7; color: #b45309; }
  .chip-new  { background: #dbeafe; color: #1d4ed8; }

  /* ---------- two-col ---------- */
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 16px 0; }

  /* ---------- file tree ---------- */
  .tree { font-family: 'Consolas', monospace; font-size: 12px; line-height: 1.9;
          background: #0f172a; color: #94a3b8; padding: 20px; border-radius: 10px; }
  .tree .dir  { color: #60a5fa; }
  .tree .file { color: #e2e8f0; }
  .tree .note { color: #475569; }

  /* ---------- alert ---------- */
  .alert { padding: 14px 18px; border-radius: 10px; margin: 14px 0; font-size: 12.5px; border-left: 4px solid; }
  .alert-blue  { background: #eff6ff; border-color: #2563eb; color: #1e40af; }
  .alert-green { background: #f0fdf4; border-color: #16a34a; color: #15803d; }
  .alert-red   { background: #fff1f2; border-color: #e11d48; color: #be123c; }

  /* ---------- footer ---------- */
  .footer { text-align: center; font-size: 11px; color: #94a3b8; padding-top: 32px; border-top: 1px solid #e2e8f0; margin-top: 40px; }
</style>
</head>
<body>

<!-- ========== COVER ========== -->
<div class="cover">
  <div class="badge">Project Documentation — 18 May 2026</div>
  <h1>AI Web Tester</h1>
  <p class="sub">Intelligent Website Quality Checker<br>powered by Claude AI + Playwright</p>

  <div class="stack-grid">
    <div class="stack-item"><div class="label">AI Brain</div><div class="value">Claude API</div></div>
    <div class="stack-item"><div class="label">Browser</div><div class="value">Playwright</div></div>
    <div class="stack-item"><div class="label">Backend</div><div class="value">FastAPI</div></div>
    <div class="stack-item"><div class="label">Frontend</div><div class="value">Next.js</div></div>
    <div class="stack-item"><div class="label">Database</div><div class="value">SQLite</div></div>
    <div class="stack-item"><div class="label">Language</div><div class="value">Python + JS</div></div>
  </div>

  <div class="meta">
    Built by: Biswa &nbsp;|&nbsp; Organisation: Webisdom<br>
    Date: 18 May 2026 &nbsp;|&nbsp; Model: claude-sonnet-4-6
  </div>
</div>

<!-- ========== PAGE 1: OVERVIEW ========== -->
<div class="page">
  <div class="section-label">Section 1</div>
  <h2>What Is This Tool?</h2>

  <p>The <strong>AI Web Tester</strong> is an intelligent website quality-checking tool. Instead of writing test scripts manually, a developer simply describes a test goal in plain English. The AI reads the website, decides what browser actions to take, executes them on a real browser, and reports a <strong>PASSED / FAILED</strong> verdict with screenshots at every step.</p>

  <div class="alert alert-blue">
    <strong>Example:</strong> Developer types: <em>"Test the login flow on https://client-site.com"</em><br>
    → AI opens the site → finds login → fills credentials → clicks login → checks dashboard loads → Reports: <strong>PASSED</strong>
  </div>

  <h3>Why AI-Powered Testing?</h3>
  <table>
    <tr><th>Without AI</th><th>With AI Web Tester</th></tr>
    <tr><td>Write test scripts manually</td><td>Describe goal in plain English</td></tr>
    <tr><td>Works only on specific sites</td><td>Works on ANY website</td></tr>
    <tr><td>Breaks when UI changes</td><td>AI adapts to current page structure</td></tr>
    <tr><td>Requires coding knowledge</td><td>Anyone on the team can use it</td></tr>
    <tr><td>Static test cases</td><td>Dynamic, intelligent decision-making</td></tr>
  </table>

  <h3>Core Architecture Flow</h3>
  <div class="flow">
    <div class="flow-step">
      <div class="flow-num">1</div>
      <div class="flow-content">
        <div class="title">Developer Input</div>
        <div class="desc">Provides a URL + test goal in plain English via the chat UI or API</div>
      </div>
    </div>
    <div class="flow-step">
      <div class="flow-num">2</div>
      <div class="flow-content">
        <div class="title">Claude AI Interprets</div>
        <div class="desc">Reads the current page HTML + screenshot and decides the next browser action</div>
      </div>
    </div>
    <div class="flow-step">
      <div class="flow-num">3</div>
      <div class="flow-content">
        <div class="title">Playwright Executes</div>
        <div class="desc">Controls a real Chromium browser: click, type, navigate, scroll, verify</div>
      </div>
    </div>
    <div class="flow-step">
      <div class="flow-num">4</div>
      <div class="flow-content">
        <div class="title">Screenshot Captured</div>
        <div class="desc">Screenshot taken after every step; page state sent back to Claude for next decision</div>
      </div>
    </div>
    <div class="flow-step">
      <div class="flow-num">5</div>
      <div class="flow-content">
        <div class="title">Result Saved &amp; Reported</div>
        <div class="desc">PASSED / FAILED verdict with all steps stored in SQLite; shown in the UI</div>
      </div>
    </div>
  </div>
</div>

<!-- ========== PAGE 2: PROJECT STRUCTURE ========== -->
<div class="page">
  <div class="section-label">Section 2</div>
  <h2>Project Structure</h2>

  <p><strong>Location:</strong> <code>C:\\Users\\biswa\\OneDrive\\Desktop\\AI assistant tool\\ai-web-tester\\</code></p>

  <div class="tree">
    <span class="dir">ai-web-tester/</span><br>
    ├── <span class="dir">backend/</span> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="note">← FastAPI + Claude AI + Playwright</span><br>
    │&nbsp;&nbsp; ├── <span class="file">main.py</span> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="note">← FastAPI server &amp; API endpoints</span><br>
    │&nbsp;&nbsp; ├── <span class="file">agent.py</span> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="note">← Claude AI agent loop (brain)</span><br>
    │&nbsp;&nbsp; ├── <span class="file">browser.py</span> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="note">← Playwright browser controller</span><br>
    │&nbsp;&nbsp; ├── <span class="file">database.py</span> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="note">← SQLite database layer</span><br>
    │&nbsp;&nbsp; ├── <span class="file">show_reports.py</span> &nbsp;<span class="note">← CLI report viewer</span><br>
    │&nbsp;&nbsp; ├── <span class="file">requirements.txt</span><br>
    │&nbsp;&nbsp; ├── <span class="file">.env</span> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="note">← ANTHROPIC_API_KEY</span><br>
    │&nbsp;&nbsp; ├── <span class="file">web_tester.db</span> &nbsp;&nbsp;<span class="note">← SQLite database</span><br>
    │&nbsp;&nbsp; └── <span class="dir">screenshots/</span> &nbsp;&nbsp;&nbsp;&nbsp;<span class="note">← PNG screenshots per step</span><br>
    ├── <span class="dir">frontend/</span> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="note">← Next.js Chat UI</span><br>
    │&nbsp;&nbsp; ├── <span class="dir">pages/</span><br>
    │&nbsp;&nbsp; │&nbsp;&nbsp; ├── <span class="file">index.js</span> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span class="note">← Main testing interface</span><br>
    │&nbsp;&nbsp; │&nbsp;&nbsp; └── <span class="file">reports.js</span> &nbsp;&nbsp;&nbsp;<span class="note">← Full reports viewer</span><br>
    │&nbsp;&nbsp; ├── <span class="dir">components/</span><br>
    │&nbsp;&nbsp; │&nbsp;&nbsp; ├── <span class="file">TestResult.js</span> &nbsp;<span class="note">← Pass/fail display + screenshots</span><br>
    │&nbsp;&nbsp; │&nbsp;&nbsp; └── <span class="file">HistoryPanel.js</span><span class="note">← Recent tests sidebar</span><br>
    │&nbsp;&nbsp; └── <span class="file">package.json</span><br>
    └── <span class="file">README.md</span>
  </div>

  <h3>Tech Stack</h3>
  <table>
    <tr><th>Layer</th><th>Technology</th><th>Version</th><th>Purpose</th></tr>
    <tr><td>AI Reasoning</td><td>Claude API (Anthropic)</td><td>claude-sonnet-4-6</td><td>Interprets goals, decides browser actions</td></tr>
    <tr><td>Browser Control</td><td>Playwright (Python)</td><td>1.59.0</td><td>Controls real Chromium browser</td></tr>
    <tr><td>Backend API</td><td>FastAPI + Uvicorn</td><td>0.136.1</td><td>REST API server</td></tr>
    <tr><td>Frontend UI</td><td>Next.js + Tailwind CSS</td><td>14.2.5</td><td>Chat interface &amp; reports</td></tr>
    <tr><td>Database</td><td>SQLite</td><td>built-in</td><td>Stores all test runs &amp; steps</td></tr>
    <tr><td>AI SDK</td><td>anthropic (Python)</td><td>0.102.0</td><td>Claude API client</td></tr>
  </table>
</div>

<!-- ========== PAGE 3: BACKEND FILES ========== -->
<div class="page">
  <div class="section-label">Section 3</div>
  <h2>Backend — Key Files Explained</h2>

  <h3>main.py — FastAPI Server</h3>
  <p>The entry point of the backend. Sets up the REST API with CORS, mounts the screenshots directory as a static file server, and exposes these endpoints:</p>
  <table>
    <tr><th>Method</th><th>Endpoint</th><th>Description</th></tr>
    <tr><td><code>POST</code></td><td><code>/test</code></td><td>Run a new AI-powered test. Accepts url + goal + optional credentials</td></tr>
    <tr><td><code>GET</code></td><td><code>/tests</code></td><td>List all past test runs from SQLite (newest first)</td></tr>
    <tr><td><code>GET</code></td><td><code>/tests/{id}</code></td><td>Get full detail of one test run including all steps</td></tr>
    <tr><td><code>DELETE</code></td><td><code>/tests/{id}</code></td><td>Delete a test run and its steps</td></tr>
    <tr><td><code>GET</code></td><td><code>/health</code></td><td>Health check — also confirms API key is configured</td></tr>
    <tr><td><code>GET</code></td><td><code>/screenshots/{file}</code></td><td>Serves screenshot PNG files</td></tr>
  </table>
  <p>Key design decision: uses <strong>absolute paths</strong> (via <code>__file__</code>) for the database and screenshots folder so the server can be started from any directory.</p>

  <h3>agent.py — Claude AI Agent Loop</h3>
  <p>This is the "brain" of the tool. The agent loop works as follows:</p>
  <pre>for step in range(max_steps=15):
    page_html  = get current page HTML (stripped of scripts/styles)
    screenshot = take screenshot of current state

    → Send to Claude: goal + page HTML + screenshot (multimodal)
    ← Claude returns JSON: { action, target, value, reasoning, is_complete, verdict }

    → Execute the action via Playwright (click / type / check / scroll …)
    → Take new screenshot
    → Save step result

    if is_complete: return PASSED / FAILED verdict</pre>
  <p>The system prompt instructs Claude to respond <strong>only with a JSON object</strong> — no markdown, no extra text — making parsing reliable. If Claude's response can't be parsed, the agent marks the test as FAILED with a clear error.</p>

  <h3>browser.py — Playwright Controller</h3>
  <p>Wraps Playwright's async API into simple methods. Each method tries multiple strategies to find elements:</p>
  <table>
    <tr><th>Method</th><th>What It Does</th></tr>
    <tr><td><code>go_to(url)</code></td><td>Navigates to URL, auto-adds https:// if missing</td></tr>
    <tr><td><code>click(selector)</code></td><td>Tries CSS selector → text match → role (button/link) as fallback</td></tr>
    <tr><td><code>type(selector, text)</code></td><td>Fills input field using fill() or type() as fallback</td></tr>
    <tr><td><code>check(selector, value)</code></td><td>Verifies element exists or page contains expected text</td></tr>
    <tr><td><code>scroll(direction)</code></td><td>Scrolls up or down 600px via JavaScript</td></tr>
    <tr><td><code>screenshot(name)</code></td><td>Captures PNG with timestamp, saves to backend/screenshots/</td></tr>
    <tr><td><code>get_page_content()</code></td><td>Returns cleaned HTML (scripts/styles stripped) for Claude</td></tr>
  </table>

  <h3>database.py — SQLite Layer</h3>
  <p>Two tables are created automatically on startup:</p>
  <pre>test_runs:
  id (TEXT PK) | url | goal | status | final_verdict | duration
  total_steps  | passed_steps | failed_steps | error | created_at

test_steps:
  id (INT PK) | test_run_id (FK) | step_number | action | target
  value | reasoning | status | error_message | screenshot_path | created_at</pre>
</div>

<!-- ========== PAGE 4: FRONTEND ========== -->
<div class="page">
  <div class="section-label">Section 4</div>
  <h2>Frontend — Next.js Chat UI</h2>

  <div class="two-col">
    <div class="card">
      <div class="card-title">pages/index.js — Main Interface</div>
      <p style="font-size:12px;">Chat-style UI with:</p>
      <ul style="font-size:12px; padding-left:18px; line-height:2;">
        <li>URL input field</li>
        <li>Test goal textarea + example chips</li>
        <li>Optional credentials (username/password)</li>
        <li>Animated loading state while AI runs</li>
        <li>Inline test result display</li>
        <li>Link to Reports page</li>
        <li>History sidebar panel</li>
      </ul>
    </div>
    <div class="card">
      <div class="card-title">pages/reports.js — Reports Viewer</div>
      <p style="font-size:12px;">Full-page database viewer:</p>
      <ul style="font-size:12px; padding-left:18px; line-height:2;">
        <li>Stats bar: Total / Passed / Failed / Errors</li>
        <li>Scrollable run list on the left</li>
        <li>Detail panel on the right</li>
        <li>Full steps table with action/target/status/reasoning</li>
        <li>All screenshots displayed inline</li>
        <li>Delete button per run</li>
      </ul>
    </div>
  </div>

  <div class="two-col">
    <div class="card">
      <div class="card-title">components/TestResult.js</div>
      <p style="font-size:12px;">Displays after a test completes:</p>
      <ul style="font-size:12px; padding-left:18px; line-height:2;">
        <li>Verdict banner (green=PASSED, red=FAILED)</li>
        <li>Step count and duration</li>
        <li>Expandable step-by-step list</li>
        <li>Action chips (colour-coded by type)</li>
        <li>Screenshot per step when expanded</li>
        <li>Detailed error message if test failed</li>
      </ul>
    </div>
    <div class="card">
      <div class="card-title">components/HistoryPanel.js</div>
      <p style="font-size:12px;">Sidebar history from the database:</p>
      <ul style="font-size:12px; padding-left:18px; line-height:2;">
        <li>Fetches GET /tests on load</li>
        <li>Shows URL, goal, verdict, steps, duration</li>
        <li>Click any run to reload it into the main view</li>
        <li>Delete button per row</li>
      </ul>
    </div>
  </div>

  <h3>Frontend → Backend Communication</h3>
  <pre>// Run a test
POST http://localhost:8000/test
Body: { "url": "https://site.com", "goal": "Test login flow", "credentials": {"username": "...", "password": "..."} }

// Get all past runs
GET http://localhost:8000/tests?limit=20

// Get one run with all steps
GET http://localhost:8000/tests/{test_id}</pre>

  <p>The Next.js config proxies <code>/api/*</code> to the backend via <code>next.config.js</code> rewrites. Direct calls use <code>http://localhost:8000</code>.</p>
</div>

<!-- ========== PAGE 5: BUGS FIXED ========== -->
<div class="page">
  <div class="section-label">Section 5</div>
  <h2>Bugs Found &amp; Fixed Today</h2>

  <div class="card">
    <div class="card-title">Bug 1 — Tool returned ERROR with no details &nbsp;<span class="chip chip-fail">FIXED</span></div>
    <p><strong>Root cause:</strong> <code>uvicorn.run(..., reload=True)</code> spawns a child subprocess for file-watching. That child process couldn't reliably find the <code>.env</code> file, so <code>ANTHROPIC_API_KEY</code> was never loaded. The agent silently failed with an empty exception message.</p>
    <p><strong>Fix:</strong> Changed <code>reload=True</code> → <code>reload=False</code> in <code>main.py</code>. The server now runs in a single direct process that always loads <code>.env</code> correctly.</p>
  </div>

  <div class="card">
    <div class="card-title">Bug 2 — Empty error message swallowed silently &nbsp;<span class="chip chip-fail">FIXED</span></div>
    <p><strong>Root cause:</strong> The agent caught all exceptions with <code>str(exc)</code>. If the exception had no message (e.g. bare <code>Exception()</code>), this returned <code>""</code> — so the UI showed ERROR with zero details.</p>
    <p><strong>Fix:</strong> Added fallback: <code>f"{type(exc).__name__}: {traceback.format_exc().splitlines()[-1]}"</code> so there is always a meaningful error string. Also added Python <code>logging</code> to print the full traceback to the server console.</p>
  </div>

  <div class="card">
    <div class="card-title">Bug 3 — finally block could override original exception &nbsp;<span class="chip chip-fail">FIXED</span></div>
    <p><strong>Root cause:</strong> <code>await browser.stop()</code> was called in a bare <code>finally</code> block. If <code>stop()</code> itself raised, Python discards the original exception and raises the new one instead.</p>
    <p><strong>Fix:</strong> Wrapped <code>browser.stop()</code> in its own <code>try/except</code> inside the <code>finally</code> block.</p>
  </div>

  <div class="card">
    <div class="card-title">Bug 4 — Frontend showed no error details when error was empty &nbsp;<span class="chip chip-fail">FIXED</span></div>
    <p><strong>Root cause:</strong> The error block in <code>TestResult.js</code> used <code>{error &amp;&amp; ...}</code>. An empty string <code>""</code> is falsy in JavaScript, so the error section never rendered.</p>
    <p><strong>Fix:</strong> Changed condition to <code>{(final_verdict === "ERROR" || error) &amp;&amp; ...}</code> with a fallback message: <em>"Check that the backend is running and ANTHROPIC_API_KEY is set in backend/.env"</em></p>
  </div>

  <div class="card">
    <div class="card-title">Bug 5 — Database / screenshots in wrong directory &nbsp;<span class="chip chip-fail">FIXED</span></div>
    <p><strong>Root cause:</strong> <code>Database(db_path="web_tester.db")</code> used a relative path. Running <code>python main.py</code> from a different directory would create the database there. OneDrive sync also caused the file to appear empty in DB Browser.</p>
    <p><strong>Fix:</strong> All paths now use <code>os.path.dirname(os.path.abspath(__file__))</code> so the database and screenshots always land in the <code>backend/</code> folder regardless of where the server is started.</p>
  </div>
</div>

<!-- ========== PAGE 6: HOW TO RUN ========== -->
<div class="page">
  <div class="section-label">Section 6</div>
  <h2>Setup &amp; How to Run</h2>

  <h3>One-Time Setup (already done)</h3>
  <table>
    <tr><th>Step</th><th>Command</th><th>Status</th></tr>
    <tr><td>Create Python venv</td><td><code>python -m venv venv</code></td><td><span class="chip chip-pass">Done</span></td></tr>
    <tr><td>Install Python deps</td><td><code>pip install fastapi uvicorn anthropic playwright python-dotenv</code></td><td><span class="chip chip-pass">Done</span></td></tr>
    <tr><td>Install Chromium browser</td><td><code>playwright install chromium</code></td><td><span class="chip chip-pass">Done</span></td></tr>
    <tr><td>Set API key</td><td>Edit <code>backend/.env</code> → <code>ANTHROPIC_API_KEY=sk-ant-...</code></td><td><span class="chip chip-pass">Done</span></td></tr>
    <tr><td>Install Node deps</td><td><code>cd frontend &amp;&amp; npm install</code></td><td><span class="chip chip-pass">Done</span></td></tr>
  </table>

  <h3>Every Day — Start the Tool</h3>
  <p><strong>Terminal 1 — Start Backend:</strong></p>
  <pre>cd "C:\\Users\\biswa\\OneDrive\\Desktop\\AI assistant tool\\ai-web-tester\\backend"
venv\\Scripts\\activate
python main.py
# Server starts at http://localhost:8000</pre>

  <p><strong>Terminal 2 — Start Frontend:</strong></p>
  <pre>cd "C:\\Users\\biswa\\OneDrive\\Desktop\\AI assistant tool\\ai-web-tester\\frontend"
npm run dev
# UI opens at http://localhost:3000</pre>

  <h3>Using the Tool</h3>
  <div class="flow">
    <div class="flow-step">
      <div class="flow-num">1</div>
      <div class="flow-content">
        <div class="title">Open <code>http://localhost:3000</code></div>
        <div class="desc">The chat interface loads in your browser</div>
      </div>
    </div>
    <div class="flow-step">
      <div class="flow-num">2</div>
      <div class="flow-content">
        <div class="title">Enter a website URL</div>
        <div class="desc">e.g. https://example.com or any client website</div>
      </div>
    </div>
    <div class="flow-step">
      <div class="flow-num">3</div>
      <div class="flow-content">
        <div class="title">Describe the test goal</div>
        <div class="desc">e.g. "Test the login flow", "Verify the contact form works", "Check search returns results"</div>
      </div>
    </div>
    <div class="flow-step">
      <div class="flow-num">4</div>
      <div class="flow-content">
        <div class="title">(Optional) Add login credentials</div>
        <div class="desc">Expand the credentials section and enter username/password if login is needed</div>
      </div>
    </div>
    <div class="flow-step">
      <div class="flow-num">5</div>
      <div class="flow-content">
        <div class="title">Click Run Test</div>
        <div class="desc">AI controls the browser. Results appear with PASSED/FAILED verdict and screenshots</div>
      </div>
    </div>
    <div class="flow-step">
      <div class="flow-num">6</div>
      <div class="flow-content">
        <div class="title">View full reports at <code>/reports</code></div>
        <div class="desc">All past test runs with step-by-step breakdown and screenshots from SQLite</div>
      </div>
    </div>
  </div>

  <h3>Viewing the SQLite Database</h3>
  <table>
    <tr><th>Method</th><th>How</th></tr>
    <tr><td>In-app Reports page</td><td>Go to <code>http://localhost:3000/reports</code> — best option, no extra tools needed</td></tr>
    <tr><td>CLI script</td><td><code>cd backend &amp;&amp; venv\\Scripts\\python show_reports.py</code></td></tr>
    <tr><td>DB Browser for SQLite</td><td>Download from sqlitebrowser.org → Open <code>backend\\web_tester.db</code></td></tr>
    <tr><td>VS Code Extension</td><td>Install "SQLite Viewer" extension → open the .db file directly</td></tr>
    <tr><td>REST API</td><td><code>http://localhost:8000/tests</code> in browser while backend runs</td></tr>
  </table>
</div>

<!-- ========== PAGE 7: DATABASE SCHEMA ========== -->
<div class="page">
  <div class="section-label">Section 7</div>
  <h2>Database Schema &amp; Sample Data</h2>

  <h3>Table: test_runs</h3>
  <table>
    <tr><th>Column</th><th>Type</th><th>Description</th></tr>
    <tr><td><code>id</code></td><td>TEXT (PK)</td><td>UUID — unique identifier for each test run</td></tr>
    <tr><td><code>url</code></td><td>TEXT</td><td>Website URL that was tested</td></tr>
    <tr><td><code>goal</code></td><td>TEXT</td><td>Plain-English test goal provided by the developer</td></tr>
    <tr><td><code>status</code></td><td>TEXT</td><td>completed / error / max_steps_reached</td></tr>
    <tr><td><code>final_verdict</code></td><td>TEXT</td><td>PASSED / FAILED / ERROR</td></tr>
    <tr><td><code>duration</code></td><td>REAL</td><td>Total time taken in seconds</td></tr>
    <tr><td><code>total_steps</code></td><td>INTEGER</td><td>Number of browser actions taken</td></tr>
    <tr><td><code>passed_steps</code></td><td>INTEGER</td><td>Steps that executed successfully</td></tr>
    <tr><td><code>failed_steps</code></td><td>INTEGER</td><td>Steps that encountered errors</td></tr>
    <tr><td><code>error</code></td><td>TEXT</td><td>Error message if status is error</td></tr>
    <tr><td><code>created_at</code></td><td>TEXT</td><td>ISO datetime when the test ran</td></tr>
  </table>

  <h3>Table: test_steps</h3>
  <table>
    <tr><th>Column</th><th>Type</th><th>Description</th></tr>
    <tr><td><code>id</code></td><td>INTEGER (PK)</td><td>Auto-increment step ID</td></tr>
    <tr><td><code>test_run_id</code></td><td>TEXT (FK)</td><td>Links to test_runs.id</td></tr>
    <tr><td><code>step_number</code></td><td>INTEGER</td><td>Step order (1, 2, 3 …)</td></tr>
    <tr><td><code>action</code></td><td>TEXT</td><td>go_to / click / type / check / scroll / wait / done</td></tr>
    <tr><td><code>target</code></td><td>TEXT</td><td>CSS selector or text Claude chose as the target</td></tr>
    <tr><td><code>value</code></td><td>TEXT</td><td>Text value for type/select actions</td></tr>
    <tr><td><code>reasoning</code></td><td>TEXT</td><td>Claude's explanation for choosing this action</td></tr>
    <tr><td><code>status</code></td><td>TEXT</td><td>passed / failed</td></tr>
    <tr><td><code>error_message</code></td><td>TEXT</td><td>Playwright error if step failed</td></tr>
    <tr><td><code>screenshot_path</code></td><td>TEXT</td><td>Absolute path to the PNG screenshot for this step</td></tr>
    <tr><td><code>created_at</code></td><td>TEXT</td><td>ISO datetime when step was recorded</td></tr>
  </table>

  <h3>Test Runs Recorded Today</h3>
  <table>
    <tr><th>URL</th><th>Goal</th><th>Verdict</th><th>Steps</th><th>Duration</th></tr>
    <tr><td>example.com</td><td>Check if the page loads</td><td><span class="chip chip-pass">PASSED</span></td><td>1</td><td>6.7s</td></tr>
    <tr><td>example.com</td><td>Verify homepage loads with heading</td><td><span class="chip chip-pass">PASSED</span></td><td>1</td><td>6.9s</td></tr>
    <tr><td>google.com</td><td>Check if search functionality works</td><td><span class="chip chip-pass">PASSED</span></td><td>4</td><td>32s</td></tr>
    <tr><td>google.com</td><td>Search for IPL news, save top 5 links</td><td><span class="chip chip-fail">FAILED</span></td><td>7</td><td>126s</td></tr>
    <tr><td>various</td><td>Early test runs (before bug fix)</td><td><span class="chip chip-fix">ERROR</span></td><td>0</td><td>&lt;0.1s</td></tr>
  </table>

  <div class="footer">
    AI Web Tester — Project Documentation &nbsp;|&nbsp; Built on 18 May 2026 &nbsp;|&nbsp; Webisdom &nbsp;|&nbsp; Powered by Claude claude-sonnet-4-6
  </div>
</div>

</body>
</html>"""


async def generate():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(HTML, wait_until="domcontentloaded")
        await page.pdf(
            path=OUTPUT_PDF,
            format="A4",
            print_background=True,
            margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
        )
        await browser.close()
    print(f"PDF saved to: {OUTPUT_PDF}")


if __name__ == "__main__":
    asyncio.run(generate())
