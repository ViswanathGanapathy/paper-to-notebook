# Sprint v1 — Tasks

## Status: In Progress

- [x] Task 1: Project setup — FastAPI backend with static file serving (P0)
  - Acceptance: `uvicorn app.main:app --reload` starts, serves a "Hello World" page at localhost:8000, project structure is clean
  - Files: `app/main.py`, `app/__init__.py`, `requirements.txt`, `static/index.html`, `.gitignore`, `.env.example`
  - Completed: 2026-03-24 — FastAPI app with CORS, static serving, health check endpoint. 3 integration tests passing, semgrep clean.

- [x] Task 2: Build the frontend UI — dark theme inspired by arcprize.org (P0)
  - Acceptance: Beautiful single-page app with dark background (#0A0A0A), Inter font, three-phase UI (API key → upload → results), responsive layout, no functionality yet — just the visual shell
  - Files: `static/index.html`, `static/styles.css`, `static/app.js`
  - Completed: 2026-03-24 — Dark theme with gradient header, three-phase UI (API key → drag-and-drop upload → status/download), responsive layout. 8 E2E tests passing, semgrep clean.

- [x] Task 3: PDF upload endpoint + text extraction with PyMuPDF (P0)
  - Acceptance: POST `/api/upload` accepts a PDF file, extracts full text with section headers preserved, returns JSON with extracted text and metadata (title, page count, sections). Test with a real arxiv PDF.
  - Files: `app/pdf_extractor.py`, update `app/main.py`
  - Completed: 2026-03-24 — PyMuPDF extraction with font-size heuristics for title/section detection. Handles empty, large, and invalid PDFs. 8 unit + 4 integration tests, semgrep clean.

- [x] Task 4: OpenAI integration — paper analysis and notebook content generation (P0)
  - Acceptance: Given extracted paper text and an API key, calls gpt-5.4 and returns structured notebook content (list of cells with type, source, and metadata). The prompt produces research-grade output, not toy code.
  - Files: `app/llm_generator.py`
  - Completed: 2026-03-24 — Two-phase LLM pipeline (analyze → generate) with research-grade prompts targeting gpt-5.4. JSON structured output with validation. 6 unit tests (mocked), semgrep clean.

- [x] Task 5: Notebook assembly — convert LLM output to .ipynb with nbformat (P0)
  - Acceptance: Takes structured cell data from Task 4, produces a valid .ipynb file that opens in Jupyter/Colab without errors. Includes Colab metadata (GPU runtime hint, collapsed sections).
  - Files: `app/notebook_builder.py`
  - Completed: 2026-03-24 — nbformat v4 notebook builder with Colab metadata (GPU, provenance), header cell with attribution, auto pip-install detection, empty cell filtering. 10 unit tests, semgrep clean.

- [x] Task 6: SSE streaming endpoint for real-time status updates (P0)
  - Acceptance: POST `/api/generate` accepts API key + PDF, streams status events ("Extracting PDF...", "Analyzing paper structure...", "Generating implementation code...", "Building notebook..."), then sends a final event with the notebook download URL
  - Files: `app/pipeline.py`, update `app/main.py`
  - Completed: 2026-03-25 — Full pipeline orchestrator with SSE streaming (extract → analyze → generate → build). Descriptive status messages with paper details. Download endpoint with path traversal protection. 5 integration tests, semgrep clean.

- [x] Task 7: Connect frontend to backend — full upload-to-download flow (P0)
  - Acceptance: End-to-end flow works: enter API key → upload PDF → see streaming status messages appear in real-time → download button appears when done → clicking downloads a valid .ipynb file
  - Files: update `static/app.js`
  - Completed: 2026-03-25 — Full frontend-backend wiring with fetch POST + ReadableStream SSE parsing, status message display with active/complete transitions, download button wiring, error handling with "Try Again" button. 4 E2E tests, semgrep clean.

- [x] Task 8: "Open in Colab" functionality (P1)
  - Acceptance: Clicking "Open in Colab" opens a new tab with the generated notebook loaded in Google Colab, ready to run
  - Files: update `app/main.py`, update `static/app.js`, update `app/pipeline.py`
  - Completed: 2026-03-25 — Added /api/notebook/{file_id} JSON endpoint for Colab, pipeline emits colab_url in complete event, frontend constructs Colab URL from current origin. Works when deployed with public URL. 2 integration tests, semgrep clean.

- [x] Task 9: Error handling, input validation, and edge cases (P1)
  - Acceptance: App handles all error cases gracefully — invalid API key (clear message), non-PDF file (rejected), oversized PDF (>50 pages warning), OpenAI rate limits (retry with backoff), network failures (reconnect SSE), empty/scanned PDFs (helpful error)
  - Files: `app/errors.py`, updates to `app/main.py`
  - Completed: 2026-03-25 — Created errors.py with UploadValidationError, validate_pdf_upload (file type + 50MB size limit), sanitized error messages for auth/rate-limit/timeout. Updated endpoints to use centralized validation. Path traversal protection verified. 10 unit + 5 integration tests, semgrep clean.

- [x] Task 10: UI polish — animations, micro-interactions, and final styling (P2)
  - Acceptance: The app feels polished and premium — smooth transitions between phases, status messages have staggered fade-in, buttons have hover effects, drag-and-drop has visual feedback, the overall experience feels worthy of a top-tier research tool
  - Files: update `static/styles.css`
  - Completed: 2026-03-25 — Phase transitions with fade+slide animation, pulsing glow on drag-over, input focus glow ring, active status dot pulse, action buttons fade-in, upload zone hover glow, text selection styling. 7 E2E tests, semgrep clean.
