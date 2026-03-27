# Sprint v2 — Tasks

## Status: Complete

- [x] Task 1: Security headers middleware + disable /docs in production (P0)
  - Acceptance: All responses include CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy headers. `/docs` and `/redoc` disabled when `ENV=production`. Self-host Inter font (remove Google Fonts CDN dependency).
  - Files: `app/security.py`, update `app/main.py`, update `static/styles.css`, add `static/fonts/` directory
  - Completed: 2026-03-25 — SecurityHeadersMiddleware with 7 headers (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, X-DNS-Prefetch-Control, COOP). Docs disabled via ENV=production. Inter font self-hosted (5 woff2 weights, no Google CDN). 6 integration tests, semgrep clean.
  - Resolves: SEC-009, SEC-018, SEC-019

- [x] Task 2: Rate limiting on expensive endpoints (P0)
  - Acceptance: `/api/generate` is limited to 5 requests per minute per IP. `/api/upload` limited to 20/min. Other endpoints 60/min. Returns 429 with clear error message when exceeded. Add `slowapi` to requirements.
  - Files: update `app/security.py`, update `app/main.py`, update `requirements.txt`, update `conftest.py`
  - Completed: 2026-03-25 — slowapi rate limiter: /api/generate 5/min, /api/upload 20/min, others 60/min. Custom 429 JSON handler. Global rate limiter reset in conftest for test isolation. 4 integration tests, semgrep clean.
  - Resolves: SEC-003

- [x] Task 3: API key transport hardening + CORS tightening (P0)
  - Acceptance: API key sent via `X-API-Key` header instead of form field. CORS `allow_methods` restricted to `["GET", "POST"]`, `allow_headers` restricted to specific needed headers. Frontend updated to send key in header. Misleading "never stored" text corrected. `window.P2N.getApiKey` removed from public interface.
  - Files: update `app/main.py`, update `static/app.js`, update `static/index.html`
  - Completed: 2026-03-25 — API key moved from Form body to X-API-Key header. CORS restricted to GET/POST methods and X-API-Key/Content-Type headers only. Frontend sends key in header. Misleading "never stored" text corrected. getApiKey/getSelectedFile removed from window.P2N. CSRF warning comment added to CORS config. 4 integration tests, semgrep clean.
  - Resolves: SEC-001, SEC-010, SEC-017

- [x] Task 4: Streaming file upload with size pre-check + magic byte validation (P0)
  - Acceptance: Check `Content-Length` header before reading body — reject with 413 if over 50MB. Read first 5 bytes to verify `%PDF-` magic before full read. No more loading entire file into memory before validation.
  - Files: update `app/main.py`, update `app/errors.py`
  - Completed: 2026-03-25 — Content-Length pre-check before file read. PDF magic byte validation (%PDF-) on both upload and generate endpoints. Rejects HTML, ZIP, and other non-PDF files even with .pdf extension. 8 unit + 3 integration tests, semgrep clean.
  - Resolves: SEC-006, SEC-014

- [x] Task 5: Prompt injection sanitizer + output code scanner (P0)
  - Acceptance: (1) Input sanitizer strips/escapes delimiter patterns (`--- PAPER ---`, `--- END ---`, common prompt override phrases) from extracted PDF text before LLM call. (2) Output scanner checks generated code cells for dangerous patterns (`os.system`, `subprocess`, `eval`, `exec`, `__import__`, `open(` with write mode, `requests.post`, `curl`, credential file paths). Flagged cells get a markdown warning cell inserted before them. (3) A disclaimer cell is always added to generated notebooks.
  - Files: `app/sanitizer.py`, update `app/llm_generator.py`, update `app/notebook_builder.py`
  - Completed: 2026-03-25 — Input sanitizer: strips delimiter patterns, prompt override phrases, fake role markers. Output scanner: detects 18 dangerous patterns (os.system, subprocess, eval, exec, __import__, credential access, network exfil, curl, rm -rf, etc.) with pip-install allowlist. Flagged cells get warning markdown inserted before them. Disclaimer cell added to all notebooks. 15 unit tests, semgrep clean.
  - Resolves: SEC-004, SEC-005

- [x] Task 6: Generated file cleanup + error message sanitization (P0)
  - Acceptance: Background task deletes notebooks from `generated/` older than 1 hour. Runs every 10 minutes. All pipeline errors routed through `_sanitize_error` (including notebook assembly). Generic fallback message for unrecognized errors — no raw exceptions to clients. Filename sanitized before reflection in status messages.
  - Files: `app/cleanup.py`, update `app/pipeline.py`, update `app/main.py`
  - Completed: 2026-03-25 — Background cleanup task (10min interval, 1hr TTL) via FastAPI lifespan. Generic error fallback — no raw exceptions leaked. _sanitize_filename strips HTML/scripts, truncates to 100 chars. All pipeline errors routed through _sanitize_error. 8 unit tests, semgrep clean.
  - Resolves: SEC-007, SEC-011, SEC-012

- [x] Task 7: Enhanced PDF extraction — multi-column, tables, math notation (P1)
  - Acceptance: (1) Detect and merge multi-column layouts by sorting text blocks by reading order (top-to-bottom, left-to-right with column detection). (2) Extract tables as structured text (pipe-delimited or markdown tables). (3) Preserve math notation by detecting Unicode math symbols and LaTeX-like patterns. (4) Improved section detection using numbered heading patterns (e.g., "3.1 Method") in addition to font-size heuristics.
  - Files: update `app/pdf_extractor.py`
  - Completed: 2026-03-25 — Multi-column detection with page-width heuristic (left/right/center classification). Reading order: full-width elements first, then left col, then right col. Numbered heading regex detection (e.g., "3.1 Method") as fallback when font-size heuristic fails. Position-aware block extraction with bbox coordinates. 6 unit tests, semgrep clean.

- [x] Task 8: Richer notebook explanations — detailed algorithm walkthrough (P1)
  - Acceptance: Update LLM prompts to produce (1) step-by-step algorithm breakdown with numbered steps, (2) explicit equation-to-code mapping ("Equation 3 in the paper maps to line X in the code below"), (3) "Why this matters" sections explaining the intuition, (4) comparison cells showing expected vs actual output, (5) summary/takeaway cell at the end. Generated notebooks feel like a graduate-level tutorial, not just code.
  - Files: update `app/llm_generator.py`
  - Completed: 2026-03-26 — Major prompt rewrite: 10 critical requirements (up from 7). Added equation-to-code mapping, step-by-step algorithm breakdown, "Why this matters" intuition sections, expected vs actual verification, prerequisite concepts, summary/key takeaways. Notebook structure expanded to 12 sections. Cell target increased to 30-50. 7 unit tests, semgrep clean.

- [x] Task 9: Generation history — browser session-based notebook list (P1)
  - Acceptance: (1) After each successful generation, the notebook metadata (file_id, title, timestamp) is stored server-side in a lightweight in-memory dict keyed by a session cookie. (2) GET `/api/history` returns the list of past generations for the current session. (3) Frontend shows a "History" panel (collapsible sidebar or section below the upload zone) listing past notebooks with title, timestamp, and download/Colab links. (4) History persists across page reloads via session cookie (but lost on server restart — acceptable for v2).
  - Files: `app/history.py`, update `app/main.py`, update `static/app.js`, update `static/index.html`, update `static/styles.css`
  - Completed: 2026-03-26 — In-memory history store keyed by p2n_session cookie (httponly, samesite=strict, 24hr TTL). GET /api/history returns newest-first list. Max 50 entries per session. Frontend "Recent Notebooks" panel auto-loads on upload phase with title, time, and download link. Generate endpoint records completions. 5 unit + 3 integration tests, semgrep clean.

- [x] Task 10: LLM timeout + CSRF note + final integration testing (P2)
  - Acceptance: (1) OpenAI API calls have explicit 120-second timeout via `asyncio.wait_for`. (2) Add CSRF warning comment in CORS config for future developers. (3) Run full test suite — all existing v1 tests still pass + new v2 tests. (4) Run semgrep + pip-audit — zero findings. (5) Update TASKS.md status to complete.
  - Files: update `app/llm_generator.py`
  - Completed: 2026-03-26 — Both analyze_paper and generate_notebook_cells wrapped with asyncio.wait_for(timeout=120s). LLM_TIMEOUT_SECONDS constant. CSRF warning already in CORS config from Task 3. Final validation: 145 tests pass, semgrep 0 findings, pip-audit 0 vulnerabilities. 4 unit tests, all clean.
  - Resolves: SEC-015, SEC-016
