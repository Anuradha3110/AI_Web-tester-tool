from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.set_fill_color(30, 30, 30)
        self.set_text_color(255, 255, 255)
        self.cell(0, 12, "AI Web Tester - API Migration Work Summary", fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def section_title(self, title):
        self.set_font("Helvetica", "B", 12)
        self.set_fill_color(220, 230, 245)
        self.set_text_color(20, 60, 120)
        self.cell(0, 9, title, fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_x(self.l_margin)
        self.multi_cell(0, 6, text)
        self.ln(1)

    def bullet(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_x(self.l_margin)
        self.multi_cell(0, 6, f"    * {text}")

    def code_block(self, text):
        self.set_font("Courier", "", 9)
        self.set_fill_color(245, 245, 245)
        self.set_draw_color(200, 200, 200)
        self.set_x(self.l_margin)
        self.multi_cell(0, 5.5, text, fill=True, border=1)
        self.set_font("Helvetica", "", 10)
        self.ln(1)

    def label(self, text):
        self.set_font("Helvetica", "B", 10)
        self.set_x(self.l_margin)
        self.cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")

    def tag(self, label, color):
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(*color)
        self.set_text_color(255, 255, 255)
        self.cell(28, 6, label, fill=True, align="C")
        self.set_text_color(0, 0, 0)
        self.ln(8)


pdf = PDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_page()

# Meta info
pdf.set_font("Helvetica", "", 10)
pdf.set_text_color(100, 100, 100)
pdf.cell(0, 6, "Date: 22 May 2026     Project: AI Web Tester     Location: ai-web-tester/backend/", new_x="LMARGIN", new_y="NEXT")
pdf.set_text_color(0, 0, 0)
pdf.ln(4)

# ── Issue 1 ──────────────────────────────────────────────────────────────────
pdf.section_title("Issue 1 - Anthropic API: Credit Balance Too Low")
pdf.tag("ERROR", (200, 60, 60))
pdf.body_text(
    "The AI Web Tester uses Claude (Anthropic API) to drive browser actions. "
    "The backend returned HTTP 400 with the message: 'Your credit balance is too "
    "low to access the Anthropic API.' This blocked every test run immediately."
)
pdf.label("Root Cause:")
pdf.bullet("Anthropic API key had zero remaining credits.")
pdf.ln(2)
pdf.label("Options Considered:")
pdf.bullet("Top up Anthropic credits (simplest, no code change)")
pdf.bullet("Switch to Google Gemini free tier")
pdf.bullet("Switch to Groq free tier")
pdf.bullet("Use local Ollama model")
pdf.bullet("Use AWS Bedrock / Google Vertex AI")
pdf.ln(2)
pdf.label("Decision:")
pdf.body_text("Switch to Google Gemini 2.0 Flash (free tier) - supports multimodal (images + text), minimal code change required.")
pdf.ln(3)

# ── Fix 1 ──────────────────────────────────────────────────────────────────
pdf.section_title("Fix 1 - Migrated agent.py from Anthropic to Google Gemini")
pdf.tag("FIXED", (40, 160, 80))
pdf.label("Files Changed:")
pdf.bullet("backend/agent.py")
pdf.bullet("backend/.env  (ANTHROPIC_API_KEY -> GEMINI_API_KEY)")
pdf.bullet("backend/.env.example")
pdf.ln(2)
pdf.label("Key Code Changes in agent.py:")
pdf.code_block(
    "# Before\n"
    "import anthropic\n"
    "self.client = anthropic.Anthropic(api_key=api_key)\n"
    "self.model = 'claude-sonnet-4-6'\n\n"
    "# After\n"
    "import google.generativeai as genai\n"
    "import PIL.Image\n"
    "genai.configure(api_key=api_key)\n"
    "self.model = genai.GenerativeModel(\n"
    "    model_name='gemini-2.0-flash',\n"
    "    system_instruction=SYSTEM_PROMPT,\n"
    "    generation_config=genai.types.GenerationConfig(max_output_tokens=512),\n"
    ")"
)
pdf.label("Conversation Format Change:")
pdf.code_block(
    "# Before (Anthropic)\n"
    "{'role': 'user',      'content': content_blocks}  # list with image+text\n"
    "{'role': 'assistant', 'content': ai_text}\n\n"
    "# After (Gemini)\n"
    "{'role': 'user',  'parts': [PIL.Image.open(path), user_text]}\n"
    "{'role': 'model', 'parts': [ai_text]}"
)
pdf.label("Package Installed:")
pdf.bullet("google-generativeai  (pip install google-generativeai)")
pdf.ln(3)

# ── Issue 2 ──────────────────────────────────────────────────────────────────
pdf.section_title("Issue 2 - Gemini Free Tier Blocked in India (limit: 0)")
pdf.tag("ERROR", (200, 60, 60))
pdf.body_text(
    "After switching to Gemini, every API call returned HTTP 429 with "
    "'Quota exceeded' and limit: 0 for all free-tier metrics "
    "(GenerateRequestsPerDayPerProjectPerModel-FreeTier, etc.).\n\n"
    "Tried creating a fresh API key from Google AI Studio - same result. "
    "The limit: 0 on every metric confirms the Gemini free tier is "
    "completely unavailable in the user's region (India). "
    "This is a Google infrastructure restriction, not a key or quota issue."
)
pdf.ln(2)
pdf.label("Decision:")
pdf.body_text("Switch to Groq - completely free, no regional restrictions, 1,000 requests/day free tier.")
pdf.ln(3)

# ── Fix 2 ──────────────────────────────────────────────────────────────────
pdf.section_title("Fix 2 - Migrated agent.py from Gemini to Groq (llama-3.3-70b-versatile)")
pdf.tag("FIXED", (40, 160, 80))
pdf.label("Files Changed:")
pdf.bullet("backend/agent.py")
pdf.bullet("backend/.env  (GEMINI_API_KEY -> GROQ_API_KEY)")
pdf.bullet("backend/.env.example")
pdf.ln(2)
pdf.label("Key Code Changes in agent.py:")
pdf.code_block(
    "# Before (Gemini)\n"
    "import google.generativeai as genai, PIL.Image\n"
    "self.model = genai.GenerativeModel('gemini-2.0-flash', ...)\n"
    "response = self.model.generate_content(conversation)\n"
    "ai_text = response.text.strip()\n\n"
    "# After (Groq)\n"
    "from groq import Groq\n"
    "self.client = Groq(api_key=api_key)\n"
    "self.model = 'llama-3.3-70b-versatile'\n"
    "response = self.client.chat.completions.create(\n"
    "    model=self.model, max_tokens=512,\n"
    "    messages=[{'role':'system','content':SYSTEM_PROMPT}] + conversation\n"
    ")\n"
    "ai_text = response.choices[0].message.content.strip()"
)
pdf.label("Conversation Format (back to OpenAI-compatible):")
pdf.code_block(
    "{'role': 'user',      'content': user_text}\n"
    "{'role': 'assistant', 'content': ai_text}"
)
pdf.body_text("Note: Groq does not support vision - screenshots are no longer sent to the AI. The agent still captures full page HTML which is sufficient for navigation and testing.")
pdf.label("Package Installed:")
pdf.bullet("groq  (pip install groq)")
pdf.ln(3)

# ── Issue 3 ──────────────────────────────────────────────────────────────────
pdf.section_title("Issue 3 - Groq Free Tier: Request Too Large (413)")
pdf.tag("ERROR", (200, 60, 60))
pdf.body_text(
    "HTTP 413: 'Request too large for model llama-3.3-70b-versatile. "
    "Limit 12000 TPM, Requested 13417 tokens.'\n\n"
    "Groq's free tier enforces a 12,000 tokens-per-minute limit. "
    "The conversation history grows with each step (up to 15 steps), "
    "and the page HTML (truncated at 4,000 chars) was too large "
    "when combined with accumulated message history."
)
pdf.ln(2)

# ── Fix 3 ──────────────────────────────────────────────────────────────────
pdf.section_title("Fix 3 - Reduced HTML size and capped conversation history")
pdf.tag("FIXED", (40, 160, 80))
pdf.label("Files Changed:")
pdf.bullet("backend/browser.py  - HTML truncation: 4,000 -> 2,000 chars")
pdf.bullet("backend/agent.py    - conversation history: full -> last 4 messages only")
pdf.ln(2)
pdf.label("browser.py change:")
pdf.code_block(
    "# Before\n"
    "return content[:4000]\n\n"
    "# After\n"
    "return content[:2000]"
)
pdf.label("agent.py change:")
pdf.code_block(
    "# Before\n"
    "messages=[{'role': 'system', 'content': SYSTEM_PROMPT}] + conversation\n\n"
    "# After\n"
    "trimmed = conversation[-4:]   # keep last 4 messages (2 exchanges)\n"
    "messages=[{'role': 'system', 'content': SYSTEM_PROMPT}] + trimmed"
)
pdf.label("Token Budget After Fix (approx.):")
pdf.bullet("System prompt:           ~400 tokens")
pdf.bullet("4 history messages:      ~1,400 tokens")
pdf.bullet("Current user message:    ~500 tokens")
pdf.bullet("Total per request:       ~2,300 tokens  (well under 12,000 limit)")
pdf.ln(4)

# ── Final State ──────────────────────────────────────────────────────────────
pdf.section_title("Final State - Working Configuration")
pdf.label("Model:")
pdf.bullet("Groq  - llama-3.3-70b-versatile (free tier, no regional restriction)")
pdf.ln(1)
pdf.label("Environment Variable Required:")
pdf.code_block("GROQ_API_KEY=gsk_...   # in backend/.env")
pdf.label("Get API Key:")
pdf.bullet("https://console.groq.com  -> API Keys -> Create API Key  (free signup)")
pdf.ln(1)
pdf.label("Free Tier Limits (Groq):")
pdf.bullet("1,000 requests / day")
pdf.bullet("30 requests / minute")
pdf.bullet("~12,000 tokens / minute on free on-demand tier")
pdf.ln(1)
pdf.label("Packages Installed in venv:")
pdf.bullet("google-generativeai  (installed but no longer used)")
pdf.bullet("Pillow               (installed but no longer used)")
pdf.bullet("groq                 (active)")
pdf.ln(4)

# ── Change Summary Table ─────────────────────────────────────────────────────
pdf.section_title("Change Log Summary")
pdf.set_font("Helvetica", "B", 9)
pdf.set_fill_color(200, 215, 235)
col_w = [38, 52, 95]
pdf.cell(col_w[0], 7, "File", border=1, fill=True)
pdf.cell(col_w[1], 7, "Change", border=1, fill=True)
pdf.cell(col_w[2], 7, "Reason", border=1, fill=True)
pdf.ln()

rows = [
    ("agent.py", "Anthropic -> Gemini", "Anthropic credits exhausted"),
    ("agent.py", "Gemini -> Groq", "Gemini free tier blocked in India"),
    ("agent.py", "Trim history to last 4 msgs", "Groq 12K TPM limit exceeded"),
    ("browser.py", "HTML truncation 4K -> 2K chars", "Groq 12K TPM limit exceeded"),
    (".env", "ANTHROPIC_API_KEY -> GEMINI_API_KEY -> GROQ_API_KEY", "Key rotation with each provider change"),
    (".env.example", "Same as .env", "Keep example in sync"),
]
pdf.set_font("Helvetica", "", 9)
fill = False
for r in rows:
    pdf.set_fill_color(245, 248, 252) if fill else pdf.set_fill_color(255, 255, 255)
    h = 7
    pdf.cell(col_w[0], h, r[0], border=1, fill=fill)
    pdf.cell(col_w[1], h, r[1], border=1, fill=fill)
    pdf.multi_cell(col_w[2], h, r[2], border=1, fill=fill)
    fill = not fill

out_path = r"C:\Users\biswa\OneDrive\Desktop\AI assistant tool\ai-web-tester\AI_Web_Tester_Migration_Summary.pdf"
pdf.output(out_path)
print(f"PDF saved: {out_path}")
