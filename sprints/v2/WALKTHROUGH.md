# Sprint v2 Walkthrough -- Security Hardening + PDF/Notebook Quality

## 1. Summary

Sprint v2 hardened the Paper-to-Notebook application against the 20 security findings from the v1 audit while simultaneously improving PDF extraction quality and notebook generation depth. The sprint resolved all Critical and High severity findings (SEC-001 through SEC-006) and most Medium-severity findings (SEC-007 through SEC-019), adding seven security headers to every response, per-endpoint rate limiting, API key transport via HTTP header instead of form body, PDF magic byte validation, prompt injection sanitization, output code scanning, automatic file cleanup, and LLM call timeouts. On the quality side, PDF extraction now handles multi-column layouts and numbered section headings, the LLM prompt was rewritten to produce graduate-level tutorials with equation-to-code mapping, and a session-based generation history lets users revisit past notebooks. The sprint added 73 new tests (46 unit + 27 integration) for a total of 145 passing tests, with zero semgrep findings and zero pip-audit vulnerabilities.

---

## 2. Architecture Diagram -- v2 Security Layers

```
Browser (Vanilla JS)
  |
  |  API key in X-API-Key header (not form body)
  |  Session cookie: p2n_session (httponly, samesite=strict)
  |
  v
+=====================================================================+
|                         FastAPI Backend                               |
|                                                                       |
|  +---------------------+                                              |
|  | SecurityHeaders     |  7 headers on EVERY response:                |
|  | Middleware           |  CSP, X-Frame-Options, X-Content-Type,      |
|  | (security.py)       |  Referrer-Policy, Permissions-Policy,        |
|  |                     |  X-DNS-Prefetch-Control, COOP                |
|  +---------------------+                                              |
|           |                                                           |
|  +---------------------+                                              |
|  | CORS Middleware      |  Origins: localhost:8000, 127.0.0.1:8000,   |
|  |                     |  localhost:3000                              |
|  |                     |  Methods: GET, POST only                     |
|  |                     |  Headers: X-API-Key, Content-Type only       |
|  +---------------------+                                              |
|           |                                                           |
|  +---------------------+                                              |
|  | Rate Limiter        |  /api/generate: 5/min per IP                 |
|  | (slowapi)           |  /api/upload:   20/min per IP                |
|  |                     |  Others:        60/min per IP                |
|  |                     |  Returns 429 JSON on exceed                  |
|  +---------------------+                                              |
|           |                                                           |
|  +---------------------+  +------------------------------------------+|
|  | Content-Length       |  | PDF Magic Byte Validator                 ||
|  | Pre-check            |  | First 5 bytes must be %PDF-              ||
|  | (errors.py)          |  | Rejects HTML, ZIP disguised as .pdf      ||
|  +---------------------+  +------------------------------------------+|
|           |                                                           |
|  +---------------------+                                              |
|  | Prompt Injection     |  Strips delimiter patterns, role markers,   |
|  | Sanitizer            |  prompt override phrases from paper text    |
|  | (sanitizer.py)       |  BEFORE sending to LLM                     |
|  +---------------------+                                              |
|           |                                                           |
|  +---------------------+                                              |
|  | LLM Call             |  asyncio.wait_for(timeout=120s) on both     |
|  | (llm_generator.py)  |  analyze_paper and generate_notebook_cells   |
|  +---------------------+                                              |
|           |                                                           |
|  +---------------------+                                              |
|  | Output Code Scanner  |  18 dangerous patterns (os.system, eval,    |
|  | (sanitizer.py)       |  subprocess, credential access, curl, etc.) |
|  |                     |  Inserts warning cell before flagged code    |
|  |                     |  + Disclaimer cell on ALL notebooks          |
|  +---------------------+                                              |
|           |                                                           |
|  +---------------------+  +------------------------------------------+|
|  | Error Sanitizer     |  | File Cleanup (cleanup.py)                ||
|  | (pipeline.py)       |  | Background task: every 10 min            ||
|  | Generic fallback —   |  | Deletes .ipynb files older than 1 hour   ||
|  | never leaks raw exc  |  |                                          ||
|  +---------------------+  +------------------------------------------+|
|           |                                                           |
|  +---------------------+                                              |
|  | History Store       |  In-memory dict keyed by session ID          |
|  | (history.py)        |  GET /api/history returns past generations   |
|  |                     |  Max 50 entries per session, 24hr cookie     |
|  +---------------------+                                              |
+=====================================================================+
```

---

## 3. New/Modified Files -- Detailed Breakdown

### 3.1 `app/security.py` -- Security Headers Middleware + Rate Limiter (NEW)

**Purpose:** Centralizes all security infrastructure -- security response headers, rate limiter configuration, and environment detection.

**Key components:**

**Rate limiter** -- uses `slowapi` with per-IP keying:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

**Custom 429 handler** -- returns structured JSON instead of a bare HTTP error:

```python
def rate_limit_exceeded_handler(request: FastAPIRequest, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please wait before making another request.",
            "error": "rate_limit_exceeded",
        },
    )
```

**Security headers** -- seven headers added to every response via Starlette middleware:

```python
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin, no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "font-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    ),
    "X-DNS-Prefetch-Control": "off",
    "Cross-Origin-Opener-Policy": "same-origin",
}

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response
```

Note the CSP: `font-src 'self'` means no external font CDNs are allowed -- the Inter font is now self-hosted under `static/fonts/`. The `frame-ancestors 'none'` directive duplicates the `X-Frame-Options: DENY` for browsers that support CSP Level 2.

**Environment detection** -- controls `/docs` and `/redoc` availability:

```python
def is_production() -> bool:
    return os.environ.get("ENV", "development").lower() == "production"
```

---

### 3.2 `app/sanitizer.py` -- Prompt Injection Sanitizer + Output Code Scanner (NEW)

**Purpose:** Two-sided defense: (1) sanitize text extracted from PDFs before sending to the LLM (input side), and (2) scan LLM-generated code for dangerous patterns before including it in notebooks (output side).

**Input sanitizer** -- three layers of pattern stripping:

1. **Delimiter patterns** -- the prompts in `llm_generator.py` use `--- PAPER TEXT ---` / `--- END PAPER ---` delimiters. If a PDF contains these strings, an attacker could break out of the data section and inject instructions. The sanitizer replaces them with `[REMOVED]`:

```python
_DELIMITER_PATTERNS = [
    r"---\s*PAPER\s*TEXT\s*---",
    r"---\s*END\s*PAPER\s*---",
    r"---\s*END\s*---",
    r"---\s*PAPER\s*ANALYSIS\s*---",
    r"---\s*END\s*ANALYSIS\s*---",
    r"---\s*FULL\s*PAPER\s*TEXT[^-]*---",
]
```

2. **Prompt override phrases** -- common prompt injection phrases are stripped by removing the entire line:

```python
_INJECTION_PHRASES = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(all\s+)?previous",
    r"forget\s+(all\s+)?previous",
    r"you\s+are\s+now\s+a\s+different",
    r"override\s+system\s+prompt",
    r"system\s*prompt\s*:",
    # ...
]
```

3. **Fake role markers** -- chat-model role injection attempts like `[SYSTEM]`, `<<SYS>>`, and `system: you are` are replaced with `[REMOVED]`.

**Output code scanner** -- checks each code cell line-by-line against 18 dangerous patterns:

```python
_DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (r"\bos\.system\s*\(",    "os.system() call -- executes shell commands"),
    (r"\bsubprocess\b",       "subprocess module -- executes external commands"),
    (r"\beval\s*\(",          "eval() -- executes arbitrary code"),
    (r"\bexec\s*\(",          "exec() -- executes arbitrary code"),
    (r"\b__import__\s*\(",    "__import__() -- dynamic module import"),
    (r"\brequests\.post\s*\(","requests.post() -- potential data exfiltration"),
    (r"\.ssh/",               "SSH key file access"),
    (r"\.aws/credentials",    "AWS credential file access"),
    (r"!rm\s+-rf\b",          "rm -rf -- recursive file deletion"),
    (r"shutil\.rmtree\s*\(",  "shutil.rmtree() -- recursive file deletion"),
    # ... 8 more patterns
]
```

An allowlist prevents false positives on safe patterns:

```python
_SAFE_EXCEPTIONS: list[str] = [
    r"^!pip\s+install",  # pip install is safe
    r"^#",               # Comments are safe
]
```

**Warning cell generation** -- when a code cell is flagged, a markdown warning cell is inserted immediately before it:

```python
def generate_warning_cell(reasons: list[str]) -> str:
    items = "\n".join(f"- {r}" for r in reasons[:5])
    return (
        "Warning: Security Warning -- Review the code below before running\n\n"
        "The following cell contains patterns that may be dangerous:\n\n"
        f"{items}\n\n"
        "*This code was AI-generated from a research paper. "
        "Please review it carefully before executing.*"
    )
```

**Disclaimer cell** -- `NOTEBOOK_DISCLAIMER` is a constant markdown string added to every generated notebook regardless of scanner results. It warns users that the code is AI-generated and should be reviewed.

---

### 3.3 `app/cleanup.py` -- Background File Cleanup (NEW)

**Purpose:** Prevents unbounded growth of the `generated/` directory by deleting notebooks older than 1 hour.

```python
DEFAULT_MAX_AGE_SECONDS = 3600  # 1 hour

def cleanup_generated_files(
    directory: Path,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> int:
    if not directory.exists():
        return 0
    now = time.time()
    removed = 0
    for file_path in directory.glob("*.ipynb"):
        try:
            age = now - file_path.stat().st_mtime
            if age > max_age_seconds:
                file_path.unlink()
                removed += 1
                logger.info("Cleaned up old notebook: %s (age: %.0fs)", file_path.name, age)
        except OSError as exc:
            logger.warning("Failed to clean up %s: %s", file_path.name, exc)
    return removed
```

Key design choices:
- Only deletes `.ipynb` files (ignores other file types).
- Uses `st_mtime` (modification time) for age calculation.
- Catches `OSError` per-file so one failure does not abort the entire sweep.
- Called from a background `asyncio` task in `main.py`'s lifespan, running every 10 minutes.

---

### 3.4 `app/history.py` -- Session-Based Generation History (NEW)

**Purpose:** Stores notebook metadata in-memory so users can revisit past generations within their browser session.

```python
MAX_HISTORY_PER_SESSION = 50

# In-memory store: {session_id: [{"file_id": ..., "title": ..., "timestamp": ...}, ...]}
_store: dict[str, list[dict[str, Any]]] = {}

def add_history_entry(session_id: str, file_id: str, title: str) -> None:
    if session_id not in _store:
        _store[session_id] = []
    _store[session_id].append({
        "file_id": file_id,
        "title": title,
        "timestamp": time.time(),
    })
    # Cap to prevent memory abuse
    if len(_store[session_id]) > MAX_HISTORY_PER_SESSION:
        _store[session_id] = _store[session_id][-MAX_HISTORY_PER_SESSION:]

def get_history(session_id: str) -> list[dict[str, Any]]:
    entries = _store.get(session_id, [])
    return list(reversed(entries))  # newest first
```

The 50-entry cap prevents a single session from consuming unbounded memory. History is keyed by a `p2n_session` cookie (httponly, samesite=strict, 24-hour TTL) set by the `/api/history` endpoint. History is lost on server restart -- acceptable for v2.

---

### 3.5 `app/errors.py` -- Enhanced Validation (MODIFIED)

**Purpose:** Centralized upload validation. v2 adds two new validators: `validate_pdf_magic_bytes` and `validate_content_length`.

**Magic byte validation** (SEC-014) -- catches files with `.pdf` extension but non-PDF content:

```python
PDF_MAGIC_BYTES = b"%PDF-"

def validate_pdf_magic_bytes(data: bytes) -> None:
    if len(data) < len(PDF_MAGIC_BYTES):
        raise UploadValidationError(
            "File is too small to be a valid PDF. Please upload a proper PDF file."
        )
    if not data[:len(PDF_MAGIC_BYTES)] == PDF_MAGIC_BYTES:
        raise UploadValidationError(
            "File does not appear to be a valid PDF (missing PDF header). "
            "Please upload a genuine .pdf file."
        )
```

**Content-Length pre-check** (SEC-006) -- rejects oversized uploads before reading the full request body:

```python
def validate_content_length(content_length: int | None) -> None:
    if content_length is None or content_length <= 0:
        return  # Unknown size -- will be validated after read
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if content_length > max_bytes:
        size_mb = content_length / (1024 * 1024)
        raise UploadValidationError(
            f"File size ({size_mb:.1f} MB) exceeds the {MAX_FILE_SIZE_MB} MB limit."
        )
```

---

### 3.6 `app/pdf_extractor.py` -- Enhanced PDF Extraction (MODIFIED)

**Purpose:** Text extraction with PyMuPDF. v2 adds multi-column layout handling, position-aware block extraction, and numbered section heading detection.

**Multi-column detection** -- uses page-width heuristics to classify blocks as left, right, or center:

```python
def _sort_blocks_reading_order(blocks: list[dict], page_width: float) -> list[dict]:
    mid_x = page_width / 2.0
    margin = page_width * 0.1  # 10% margin for column detection

    left_blocks = [b for b in blocks if b["x"] < mid_x - margin]
    right_blocks = [b for b in blocks if b["x"] >= mid_x + margin]
    center_blocks = [b for b in blocks if mid_x - margin <= b["x"] < mid_x + margin]

    is_two_column = len(left_blocks) >= 3 and len(right_blocks) >= 3

    if is_two_column:
        # Full-width first (by y), then left col, then right col
        result = []
        all_sorted = sorted(blocks, key=lambda b: b["y"])
        for b in all_sorted:
            if mid_x - margin <= b["x"] < mid_x + margin:
                result.append(b)
        for b in sorted(left_blocks, key=lambda b: b["y"]):
            if b not in result:
                result.append(b)
        for b in sorted(right_blocks, key=lambda b: b["y"]):
            if b not in result:
                result.append(b)
        return result
    else:
        return sorted(blocks, key=lambda b: (b["y"], b["x"]))
```

**Numbered heading detection** -- a regex fallback when font-size heuristics fail (common in two-column papers where headings share the body font size):

```python
_NUMBERED_HEADING_RE = re.compile(r"^\s*(\d+\.?\d*\.?\d*)\s+[A-Z]")

# In _detect_sections:
if not is_heading and _NUMBERED_HEADING_RE.match(block["text"]):
    if len(block["text"]) < 80:  # Headings are typically short
        is_heading = True
```

**Position-aware block extraction** -- each block now carries `x`, `y`, `page`, and `font_size` metadata, enabling the column detection and reading-order sorting above.

---

### 3.7 `app/llm_generator.py` -- Richer Prompts + Timeouts (MODIFIED)

**Purpose:** Two-phase LLM pipeline. v2 adds input sanitization, 120-second timeouts, and a major prompt rewrite.

**Prompt injection sanitization** -- paper text is sanitized before both LLM calls:

```python
from app.sanitizer import sanitize_paper_text

async def analyze_paper(client, paper_text):
    safe_text = sanitize_paper_text(paper_text)
    response = await asyncio.wait_for(
        client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": f"...\n--- PAPER TEXT ---\n{safe_text}\n--- END PAPER ---"},
            ],
            ...
        ),
        timeout=LLM_TIMEOUT_SECONDS,  # 120 seconds
    )
```

**LLM timeout** (SEC-015) -- both `analyze_paper` and `generate_notebook_cells` are wrapped with `asyncio.wait_for(timeout=120)`. If the OpenAI API does not respond within 2 minutes, an `asyncio.TimeoutError` is raised and caught by the pipeline's error handler.

```python
LLM_TIMEOUT_SECONDS = 120  # 2 minutes per API call
```

**Enhanced generation prompt** -- the `GENERATION_SYSTEM_PROMPT` was rewritten with 10 critical requirements (up from 7 in v1):

1. Production Python (type hints, docstrings)
2. Realistic synthetic data (domain-appropriate distributions)
3. Complete implementation (every key algorithm)
4. **Equation-to-code mapping** (NEW in v2) -- "For every key equation, show it in LaTeX/markdown, then EXPLICITLY connect it to the code"
5. **Step-by-step algorithm breakdown** (NEW in v2) -- numbered walkthrough before code
6. **Why this matters** (NEW in v2) -- intuition sections explaining importance
7. Visualizations
8. **Expected vs actual output** (NEW in v2) -- verification cells comparing expected shapes/ranges
9. Runnable in Colab (self-contained imports per cell)
10. **Educational depth** (NEW in v2) -- graduate-level tutorial quality

The notebook structure was expanded to 12 sections (from 8 in v1), including Background & Motivation, Prerequisite Concepts, Summary & Key Takeaways. Cell target increased from 25-40 to 30-50.

---

### 3.8 `app/notebook_builder.py` -- Code Scanning Integration (MODIFIED)

**Purpose:** Converts LLM cell output to a valid `.ipynb`. v2 adds the disclaimer cell and per-cell code scanning.

**Disclaimer cell** -- inserted immediately after the header cell in every notebook:

```python
from app.sanitizer import NOTEBOOK_DISCLAIMER, generate_warning_cell, scan_code_cell

# In build_notebook():
nb.cells.append(nbformat.v4.new_markdown_cell(NOTEBOOK_DISCLAIMER))
```

**Per-cell scanning** -- every code cell is scanned before inclusion:

```python
for cell in cells:
    # ...
    if cell_type == "code":
        scan = scan_code_cell(source)
        if scan.is_flagged:
            logger.warning("Flagged code cell: %s", scan.reasons)
            warning_md = generate_warning_cell(scan.reasons)
            nb.cells.append(nbformat.v4.new_markdown_cell(warning_md))
        nb.cells.append(nbformat.v4.new_code_cell(source))
```

The flagged code is still included (not removed), but a visible warning is inserted before it. This avoids breaking the notebook while making the risk visible to the user.

---

### 3.9 `app/pipeline.py` -- Enhanced Error Handling (MODIFIED)

**Purpose:** Pipeline orchestrator yielding SSE events. v2 adds generic error fallback and filename sanitization.

**Generic error fallback** (SEC-011) -- unrecognized errors no longer leak raw exception details:

```python
def _sanitize_error(exc: Exception) -> str:
    msg = str(exc)
    if "api_key" in msg.lower() or "authentication" in msg.lower():
        return "Invalid or expired API key. Please check your OpenAI API key."
    if "rate" in msg.lower() and "limit" in msg.lower():
        return "OpenAI rate limit exceeded. Please wait a moment and try again."
    if "timeout" in msg.lower():
        return "Request timed out. The paper may be too long. Try a shorter paper."
    if "connection" in msg.lower() or "network" in msg.lower():
        return "Network error connecting to OpenAI. Please check your connection and try again."
    # Generic fallback -- never leak raw exception details
    logger.error("Unhandled pipeline error: %s", msg)
    return "An unexpected error occurred during processing. Please try again."
```

In v1, the fallback was `return f"An error occurred: {msg}"` which leaked the full exception message. Now unrecognized errors return a generic message and log the details server-side only.

**Filename sanitization** (SEC-012) -- before reflecting a filename in SSE status messages:

```python
def _sanitize_filename(filename: str) -> str:
    safe = re.sub(r"<[^>]*>", "", filename)       # Strip HTML/script tags
    safe = re.sub(r"[^\w\s\-_.\(\)]", "", safe)   # Keep only safe characters
    if len(safe) > 100:
        safe = safe[:97] + "..."
    return safe.strip() or "uploaded file"
```

**Notebook assembly error routing** -- in v1, `build_notebook()` exceptions were not caught. Now they go through `_sanitize_error`:

```python
try:
    notebook_bytes = build_notebook(cells, paper_meta)
except Exception as exc:
    yield _error(_sanitize_error(exc))
    return
```

---

### 3.10 `app/main.py` -- Application Entry Point (MODIFIED)

**Purpose:** FastAPI app setup, routes, and middleware wiring. v2 adds significant changes.

**Lifespan with background cleanup:**

```python
@asynccontextmanager
async def lifespan(app_instance):
    async def _cleanup_loop():
        while True:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)  # 600s = 10 min
            cleanup_generated_files(GENERATED_DIR)
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()
```

**Docs disabled in production:**

```python
_docs_url = None if is_production() else "/docs"
_redoc_url = None if is_production() else "/redoc"
app = FastAPI(docs_url=_docs_url, redoc_url=_redoc_url, lifespan=lifespan)
```

**Rate limiter wiring:**

```python
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
```

**Per-endpoint rate limits:**

| Endpoint | Rate Limit |
|----------|-----------|
| `POST /api/generate` | 5/minute |
| `POST /api/upload` | 20/minute |
| `GET /api/health` | 60/minute |
| `GET /api/download/{id}` | 60/minute |
| `GET /api/notebook/{id}` | 60/minute |
| `GET /api/history` | 60/minute |

**API key via header:**

```python
@app.post("/api/generate")
@limiter.limit("5/minute")
async def generate_notebook(
    request: Request,
    file: UploadFile = File(...),
    x_api_key: str | None = Header(None),    # NEW: from header
    p2n_session: str | None = Cookie(None),   # NEW: session cookie
) -> EventSourceResponse:
    api_key = x_api_key or ""
    if not api_key:
        raise HTTPException(status_code=400, detail="Missing API key. Send it via the X-API-Key header.")
```

**CORS tightening:**

```python
# WARNING: Never set allow_origins=["*"] with allow_credentials=True -- this
# enables any website to make authenticated cross-origin requests (CSRF risk).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],           # Was ["*"] in v1
    allow_headers=["X-API-Key", "Content-Type"],  # Was ["*"] in v1
)
```

**Magic byte validation on both upload and generate endpoints:**

```python
pdf_bytes = await file.read()
validate_pdf_upload(filename, len(pdf_bytes))
validate_pdf_magic_bytes(pdf_bytes)               # NEW in v2
```

**History API endpoint:**

```python
@app.get("/api/history")
@limiter.limit("60/minute")
async def get_generation_history(request: Request, p2n_session: str | None = Cookie(None)):
    session_id = p2n_session or ""
    if not session_id:
        session_id = str(uuid.uuid4())
        response = JSONResponse(content=[])
        response.set_cookie("p2n_session", session_id, httponly=True, samesite="strict", max_age=86400)
        return response
    history = get_history(session_id)
    return JSONResponse(content=history)
```

---

### 3.11 `static/app.js` -- Frontend Logic (MODIFIED)

**Key v2 changes:**

**API key sent via header instead of form body** (SEC-001):

```javascript
// v1: formData.append("api_key", apiKey);
// v2:
fetch("/api/generate", {
    method: "POST",
    headers: { "X-API-Key": apiKey },
    body: formData,
})
```

**Sensitive functions removed from `window.P2N`** (SEC-017):

```javascript
// v1: window.P2N = { addStatus, showComplete, showPhase, phaseResults, getApiKey, getSelectedFile };
// v2:
window.P2N = {
    addStatus: addStatus,
    showComplete: showComplete,
    showPhase: showPhase,
    phaseResults: phaseResults,
    // getApiKey and getSelectedFile REMOVED
};
```

**History panel** -- `loadHistory()` fetches `GET /api/history` when the upload phase is shown and renders a "Recent Notebooks" panel with title, timestamp, and download link for each entry.

---

### 3.12 `static/index.html` -- Frontend HTML (MODIFIED)

**Key v2 changes:**

**Corrected API key hint** (SEC-017) -- the v1 text "Your key stays in your browser and is never stored on our servers" was misleading since the key IS sent to the server. The v2 text:

```html
<p class="api-key-hint">
    Your key is sent securely to our server for each generation request
    but is never stored or logged.
</p>
```

**History panel added:**

```html
<section class="history-panel hidden" id="history-panel" data-testid="history-panel">
    <div class="history-card">
        <h4 class="history-title">Recent Notebooks</h4>
        <div class="history-list" id="history-list" data-testid="history-list"></div>
    </div>
</section>
```

---

### 3.13 `static/styles.css` -- Design System (MODIFIED)

**Key v2 changes:**

**Self-hosted Inter font** (SEC-018) -- replaced Google Fonts CDN with local `@font-face` declarations:

```css
/* Self-hosted Inter font -- no external CDN dependency (SEC-018) */
@font-face {
    font-family: 'Inter';
    font-style: normal;
    font-weight: 400;
    font-display: swap;
    src: url('/static/fonts/Inter-Regular.woff2') format('woff2');
}
/* ... 4 more weights: 300, 500, 600, 700 */
```

**History panel styles** -- `.history-panel`, `.history-card`, `.history-item`, `.history-item-title`, `.history-item-time`, `.history-item-actions` classes added for the Recent Notebooks UI.

---

### 3.14 `requirements.txt` -- Dependencies (MODIFIED)

```
fastapi==0.135.2          # was 0.115.6
uvicorn[standard]==0.34.0
python-multipart==0.0.22  # was 0.0.20
openai==1.61.0
PyMuPDF==1.25.3
nbformat==5.10.4
sse-starlette==2.2.1
slowapi==0.1.9            # NEW for rate limiting
pytest==8.3.4
httpx==0.28.1
```

`slowapi` is the only new dependency. `fastapi` and `python-multipart` were bumped to newer versions.

---

### 3.15 `conftest.py` -- Test Configuration (MODIFIED)

**Added rate limiter reset fixture** to prevent cross-test interference:

```python
@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset the rate limiter before each test to prevent cross-test interference."""
    from app.security import limiter
    limiter.reset()
    yield
```

This runs before every test, ensuring rate limit counters from one test do not cause unexpected 429 responses in subsequent tests.

---

## 4. Security Audit Resolution Map

The v1 audit identified 20 security findings. Here is how each was resolved in v2:

| Finding | Severity | Description | Resolution | Files |
|---------|----------|-------------|------------|-------|
| **SEC-001** | Critical | API key sent in form body (visible in network logs as form field) | Moved to `X-API-Key` HTTP header | `app/main.py`, `static/app.js` |
| **SEC-003** | Critical | No rate limiting -- expensive LLM endpoint can be abused | slowapi rate limiter: 5/min on generate, 20/min on upload, 60/min on others | `app/security.py`, `app/main.py` |
| **SEC-004** | Critical | No prompt injection protection -- malicious PDF text could override LLM instructions | Input sanitizer strips delimiters, override phrases, and role markers | `app/sanitizer.py`, `app/llm_generator.py` |
| **SEC-005** | High | Generated code is not scanned -- could contain os.system, eval, credential theft | Output scanner with 18 dangerous patterns + warning cells + disclaimer | `app/sanitizer.py`, `app/notebook_builder.py` |
| **SEC-006** | High | File read into memory before size check -- DoS vector | Content-Length pre-check before `file.read()` | `app/errors.py`, `app/main.py` |
| **SEC-007** | Medium | Generated files never cleaned up -- disk exhaustion | Background cleanup task: 10-min interval, 1-hour TTL | `app/cleanup.py`, `app/main.py` |
| **SEC-009** | Medium | No security headers on responses | 7 security headers via middleware (CSP, X-Frame-Options, etc.) | `app/security.py`, `app/main.py` |
| **SEC-010** | Medium | CORS allows all methods and all headers | Restricted to GET/POST methods and X-API-Key/Content-Type headers | `app/main.py` |
| **SEC-011** | Medium | Raw exception messages leaked to clients | Generic fallback message for unrecognized errors | `app/pipeline.py` |
| **SEC-012** | Medium | Filenames reflected in status without sanitization (XSS risk) | `_sanitize_filename` strips HTML tags and special chars | `app/pipeline.py` |
| **SEC-013** | Medium | Notebook assembly errors not routed through sanitizer | `build_notebook()` exceptions now caught and sanitized | `app/pipeline.py` |
| **SEC-014** | Medium | No magic byte validation -- non-PDFs with .pdf extension accepted | `validate_pdf_magic_bytes()` checks `%PDF-` header | `app/errors.py`, `app/main.py` |
| **SEC-015** | Medium | No timeout on LLM API calls -- could hang indefinitely | `asyncio.wait_for(timeout=120)` on both LLM calls | `app/llm_generator.py` |
| **SEC-016** | Low | No CSRF warning comment for future developers | Comment added above CORS config | `app/main.py` |
| **SEC-017** | Low | `getApiKey` exposed on `window.P2N` public interface | Removed from `window.P2N` export | `static/app.js` |
| **SEC-018** | Low | Google Fonts CDN dependency leaks user IPs | Inter font self-hosted in `static/fonts/` | `static/styles.css`, `static/fonts/` |
| **SEC-019** | Low | `/docs` and `/redoc` accessible in production | Disabled when `ENV=production` | `app/security.py`, `app/main.py` |

**Still open (deferred to v3):**

| Finding | Severity | Description | Why Deferred |
|---------|----------|-------------|-------------- |
| **SEC-002** | Critical | No CSRF token on state-changing endpoints | Requires user authentication (out of scope for v2) |
| **SEC-008** | Medium | No authentication -- anyone with the URL can use the app | Requires OAuth/sessions infrastructure (v3) |

---

## 5. Data Flow with Security Checks

Here is the step-by-step flow when a user generates a notebook in v2, with security checkpoints marked as `[SEC]`:

```
1. User enters OpenAI API key in browser
   |-> Stored in JS closure only (not on window.P2N)

2. User selects/drops a PDF file
   |-> Client-side validation: must be application/pdf

3. User clicks "Generate Notebook"
   |-> Frontend sends POST /api/generate
       API key in X-API-Key header [SEC-001]
       PDF file in multipart body

4. [SEC] SecurityHeadersMiddleware adds 7 security headers to response [SEC-009]

5. [SEC] Rate limiter checks: 5 requests/minute per IP [SEC-003]
   |-> 429 with JSON error if exceeded

6. [SEC] Content-Length pre-check BEFORE reading body [SEC-006]
   |-> 413-equivalent (400) if Content-Length > 50 MB

7. Backend reads file body
   |-> validate_pdf_upload(): checks .pdf extension, < 50 MB

8. [SEC] PDF magic byte validation [SEC-014]
   |-> First 5 bytes must be %PDF-
   |-> Rejects HTML, ZIP, etc. disguised as .pdf

9. Backend starts SSE stream

10. Stage 1: PDF Extraction
    |-> pdf_extractor.extract_pdf(pdf_bytes)
    |-> Multi-column layout detection (page-width heuristic)
    |-> Reading order: full-width -> left col -> right col
    |-> Section detection: font-size heuristic + numbered heading regex
    |-> Filename sanitized before reflection in status [SEC-012]
    |-> SSE: "Extracted 12 pages with 8 sections. Paper: 'Title'"

11. [SEC] Stage 2: Paper Analysis (LLM Phase 1)
    |-> sanitize_paper_text(full_text) [SEC-004]
    |   |-> Strip delimiter patterns
    |   |-> Remove prompt override phrases
    |   |-> Neutralize fake role markers
    |-> asyncio.wait_for(timeout=120s) [SEC-015]
    |-> analyze_paper(client, safe_text)
    |-> Error sanitization: generic fallback for unrecognized errors [SEC-011]
    |-> SSE: "Identified 3 key algorithm(s)..."

12. [SEC] Stage 3: Notebook Generation (LLM Phase 2)
    |-> sanitize_paper_text(paper_text[:15000]) [SEC-004]
    |-> asyncio.wait_for(timeout=120s) [SEC-015]
    |-> generate_notebook_cells(client, analysis, safe_text)
    |-> Enhanced prompt: equation-to-code, step-by-step, intuition
    |-> SSE: "Generated 38 cells (22 code, 16 markdown)"

13. Stage 4: Notebook Assembly
    |-> build_notebook(cells, paper_meta)
    |-> Header cell + Disclaimer cell [SEC-005]
    |-> [SEC] Each code cell scanned for 18 dangerous patterns [SEC-005]
    |   |-> Flagged cells get warning markdown inserted before them
    |-> build_notebook errors caught and sanitized [SEC-013]
    |-> Writes to generated/{uuid4}.ipynb
    |-> SSE: "Notebook ready for download!"

14. [SEC] History recording
    |-> add_history_entry(session_id, file_id, title) [Task 9]
    |-> SSE complete event with file_id, title, colab_url

15. Frontend receives complete event
    |-> Sets Download button href
    |-> Constructs Colab URL
    |-> Shows action buttons

16. [SEC] Background cleanup (every 10 minutes) [SEC-007]
    |-> Deletes .ipynb files older than 1 hour from generated/
```

---

## 6. Test Coverage -- 73 New v2 Tests

**Total: 145 tests (72 from v1 + 73 new in v2)**

### 6.1 Unit Tests -- Sanitizer (15 tests)

`tests/unit/test_sanitizer.py`

| Test | What it verifies |
|------|-----------------|
| `test_sanitize_strips_delimiter_patterns` | `--- END PAPER ---` is stripped from text |
| `test_sanitize_strips_prompt_override_phrases` | "Ignore all previous instructions" is removed |
| `test_sanitize_strips_system_prompt_attempts` | `[SYSTEM]` role markers are stripped |
| `test_sanitize_preserves_normal_text` | Normal academic text passes through unchanged |
| `test_sanitize_handles_multiple_injections` | Multiple injection types in one text are all caught |
| `test_scan_flags_os_system` | `os.system()` calls are flagged |
| `test_scan_flags_subprocess` | `subprocess` usage is flagged |
| `test_scan_flags_eval` | `eval()` calls are flagged |
| `test_scan_flags_dunder_import` | `__import__()` is flagged |
| `test_scan_flags_credential_access` | `.ssh/id_rsa` access is flagged |
| `test_scan_flags_network_exfiltration` | `requests.post` to external URLs is flagged |
| `test_scan_flags_curl` | `!curl` shell commands are flagged |
| `test_scan_allows_safe_code` | Normal numpy/torch code is NOT flagged |
| `test_scan_allows_file_open_read` | `open("data.csv", "r")` is NOT flagged |
| `test_scan_allows_pip_install` | `!pip install` is NOT flagged |

### 6.2 Unit Tests -- Upload Validation (8 tests)

`tests/unit/test_upload_validation.py`

| Test | What it verifies |
|------|-----------------|
| `test_validate_magic_bytes_valid_pdf` | `%PDF-1.7` bytes pass validation |
| `test_validate_magic_bytes_rejects_non_pdf` | ZIP bytes (`PK\x03\x04`) are rejected |
| `test_validate_magic_bytes_rejects_empty` | Empty bytes are rejected |
| `test_validate_magic_bytes_rejects_short` | Too-short bytes (`%PD`) are rejected |
| `test_validate_magic_bytes_rejects_html_disguised_as_pdf` | HTML with `.pdf` extension is caught |
| `test_content_length_check_rejects_oversized` | Content-Length > 50 MB raises error |
| `test_content_length_check_accepts_valid` | 1 MB passes without error |
| `test_content_length_check_accepts_zero` | Zero/None content-length is allowed |

### 6.3 Unit Tests -- File Cleanup + Error Sanitization (8 tests)

`tests/unit/test_file_cleanup.py`

| Test | What it verifies |
|------|-----------------|
| `test_cleanup_removes_old_files` | Files older than `max_age_seconds` are deleted, new ones preserved |
| `test_cleanup_ignores_non_ipynb` | `.txt` files are not touched |
| `test_cleanup_handles_empty_dir` | Empty directory returns 0 removed |
| `test_sanitize_error_generic_fallback` | Unknown errors do not leak file paths or tracebacks |
| `test_sanitize_error_no_raw_exception_for_unknown` | Database errors do not leak IP addresses |
| `test_sanitize_filename_strips_html` | `<img src=x onerror=alert(1)>` stripped from filenames |
| `test_sanitize_filename_truncates_long_names` | 300-char filenames truncated to <= 100 |
| `test_sanitize_filename_preserves_normal_names` | `attention_is_all_you_need.pdf` unchanged |

### 6.4 Unit Tests -- Prompt Quality (7 tests)

`tests/unit/test_prompt_quality.py`

| Test | What it verifies |
|------|-----------------|
| `test_generation_prompt_requires_equation_mapping` | Prompt contains "equation", "code", and mapping directive |
| `test_generation_prompt_requires_step_by_step` | Prompt contains "step-by-step" |
| `test_generation_prompt_requires_intuition` | Prompt contains "intuition" or "why matters" |
| `test_generation_prompt_requires_expected_vs_actual` | Prompt contains "expected" and "actual"/"output" |
| `test_generation_prompt_requires_summary` | Prompt contains "summary" or "takeaway" |
| `test_generation_prompt_targets_graduate_level` | Prompt contains "graduate" or "tutorial" |
| `test_notebook_structure_includes_all_sections` | Prompt mentions background, motivation, limitation, reference |

### 6.5 Unit Tests -- History (5 tests)

`tests/unit/test_history.py`

| Test | What it verifies |
|------|-----------------|
| `test_add_and_get_history` | Can add an entry and retrieve it by session ID |
| `test_history_ordered_newest_first` | Entries returned newest first |
| `test_empty_history` | Unknown session returns empty list |
| `test_history_isolated_between_sessions` | Different sessions have independent histories |
| `test_history_max_entries` | History capped at `MAX_HISTORY_PER_SESSION` (50) |

### 6.6 Unit Tests -- LLM Timeout (4 tests)

`tests/unit/test_llm_timeout.py`

| Test | What it verifies |
|------|-----------------|
| `test_llm_timeout_constant_exists` | `LLM_TIMEOUT_SECONDS` is between 60 and 300 |
| `test_analyze_paper_uses_timeout` | `analyze_paper` source contains `wait_for` or `timeout` |
| `test_generate_cells_uses_timeout` | `generate_notebook_cells` source contains `wait_for` or `timeout` |
| `test_cors_has_csrf_warning` | `app/main.py` contains "CSRF" comment |

### 6.7 Unit Tests -- PDF Extraction v2 (6 tests)

`tests/unit/test_pdf_extraction_v2.py`

| Test | What it verifies |
|------|-----------------|
| `test_two_column_extracts_both_columns` | Text from both left and right columns is present |
| `test_two_column_reading_order` | Left column text appears before right column text |
| `test_two_column_sections_detected` | Introduction and Methodology headings found in two-column paper |
| `test_table_content_extracted` | Table values ("Baseline", "0.92", "Accuracy") are in extracted text |
| `test_numbered_sections_detected_by_pattern` | Numbered headings ("1 Introduction") detected when font size is uniform |
| `test_numbered_subsections_detected` | Subsections like "3.1 Sub-section" are detected |

### 6.8 Integration Tests -- Security Headers (6 tests)

`tests/integration/test_security_headers.py`

| Test | What it verifies |
|------|-----------------|
| `test_security_headers_present` | X-Content-Type-Options, X-Frame-Options, Referrer-Policy, CSP, Permissions-Policy |
| `test_csp_blocks_external_scripts` | CSP has `default-src`, no Google Fonts CDN |
| `test_security_headers_on_static` | Security headers present on static file responses too |
| `test_docs_disabled_in_production` | `/docs` and `/redoc` return 404 when `ENV=production` |
| `test_docs_enabled_in_development` | `/docs` returns 200 in development mode |
| `test_self_hosted_font_served` | `/static/fonts/Inter-Regular.woff2` returns 200 |

### 6.9 Integration Tests -- Rate Limiting (4 tests)

`tests/integration/test_rate_limiting.py`

| Test | What it verifies |
|------|-----------------|
| `test_generate_rate_limited` | 6th request to `/api/generate` within a minute returns 429 |
| `test_upload_rate_limited` | 21st request to `/api/upload` within a minute returns 429 |
| `test_health_not_quickly_limited` | 30 requests to `/api/health` all return 200 |
| `test_rate_limit_returns_clear_message` | 429 response includes "rate"/"limit" in message |

### 6.10 Integration Tests -- API Key Transport (4 tests)

`tests/integration/test_api_key_transport.py`

| Test | What it verifies |
|------|-----------------|
| `test_generate_accepts_api_key_in_header` | `X-API-Key` header accepted, returns SSE stream |
| `test_generate_rejects_missing_api_key` | Missing API key returns 400 or 422 |
| `test_cors_methods_restricted` | DELETE not in `Access-Control-Allow-Methods` |
| `test_cors_headers_restricted` | `X-API-Key` is in `Access-Control-Allow-Headers` |

### 6.11 Integration Tests -- Magic Bytes (3 tests)

`tests/integration/test_magic_bytes.py`

| Test | What it verifies |
|------|-----------------|
| `test_upload_rejects_non_pdf_magic_bytes` | HTML with `.pdf` extension returns 400 |
| `test_upload_accepts_real_pdf` | Real PDF with correct magic bytes returns 200 |
| `test_generate_rejects_non_pdf_magic_bytes` | ZIP disguised as `.pdf` rejected on generate endpoint |

### 6.12 Integration Tests -- History API (3 tests)

`tests/integration/test_history_api.py`

| Test | What it verifies |
|------|-----------------|
| `test_history_endpoint_returns_list` | `GET /api/history` returns a JSON list |
| `test_history_empty_for_new_session` | New session has empty history |
| `test_history_uses_session_cookie` | History tied to `p2n_session` cookie |

---

## 7. Remaining Limitations

### Open Security Findings

1. **SEC-002 (Critical) -- No CSRF protection.** State-changing endpoints (`POST /api/generate`, `POST /api/upload`) have no CSRF token. The CORS config mitigates this for browser-based requests (same-origin only), but a CSRF warning comment was added for future developers. Full CSRF protection requires user authentication, which is out of scope for v2.

2. **SEC-008 (Medium) -- No user authentication.** Anyone with the URL can use the app. The only gate is the user-provided OpenAI API key. Adding OAuth or session-based auth is planned for v3.

### Functional Limitations

3. **History is in-memory.** All generation history is lost on server restart. A persistent database (SQLite or PostgreSQL) is planned for v3.

4. **Prompt injection sanitization is pattern-based.** The sanitizer uses regex to strip known injection patterns, but novel or obfuscated attacks could bypass it. The output code scanner provides a second layer of defense, but neither layer is foolproof.

5. **Multi-column detection is heuristic.** The page-width-based column detection works for standard two-column academic papers but may fail on three-column layouts, conference posters, or papers with unusual formatting.

6. **No OCR for scanned PDFs.** Papers that are scanned images (no text layer) still fail the 100-character minimum check and are rejected.

7. **Paper text still truncated at 15K characters in Phase 2.** Very long papers may lose content from later sections.

8. **"Open in Colab" still requires a public URL.** The app must be deployed publicly for Colab to fetch the notebook JSON.

9. **No retry logic for LLM API calls.** If an OpenAI request fails or times out, the pipeline fails. Retry with exponential backoff is not implemented.

10. **Rate limiter is per-IP, not per-user.** Users behind a shared NAT (corporate office, university) share a rate limit pool.

---

## 8. What's Next -- v3 Priorities

Based on the open findings and remaining limitations:

1. **User authentication and persistent sessions** -- Add OAuth (Google/GitHub) or email-based auth. Store sessions in a database. This resolves SEC-002 (CSRF with auth tokens) and SEC-008 (no auth).

2. **Persistent history database** -- Migrate from in-memory dict to SQLite or PostgreSQL. History survives server restarts.

3. **Dockerization and cloud deployment** -- Dockerfile, docker-compose.yml, and deployment to a cloud provider so "Open in Colab" works end-to-end.

4. **LLM retry with backoff** -- Wrap OpenAI calls in `tenacity` with exponential backoff for rate limits and transient failures.

5. **Multiple LLM provider support** -- Add Anthropic Claude and Google Gemini as alternative backends.

6. **Notebook execution validation** -- After generation, execute the notebook in a sandboxed environment and report cell-level pass/fail.

7. **OCR for scanned PDFs** -- Integrate Tesseract or cloud OCR for image-only PDFs.

8. **Streaming LLM output** -- Stream token-by-token to the frontend to reduce perceived latency.

9. **Custom templates** -- Let users choose notebook styles (PyTorch vs. TensorFlow), detail levels, or specific sections to include.

10. **Usage tracking and cost estimation** -- Show estimated token usage and cost before generation begins.
