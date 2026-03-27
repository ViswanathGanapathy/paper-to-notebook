# Sprint v1 Walkthrough -- Paper-to-Notebook

## 1. Summary

Paper-to-Notebook is a web application that lets ML researchers upload a PDF research paper and receive a production-quality Google Colab notebook (`.ipynb`) that implements the paper's algorithms, complete with realistic synthetic data and visualizations. The backend is a FastAPI server that chains together PDF extraction (PyMuPDF), a two-phase LLM analysis/generation pipeline (OpenAI gpt-5.4), and notebook assembly (nbformat), streaming real-time status updates to a dark-themed single-page frontend via Server-Sent Events. Sprint v1 delivered the full end-to-end flow across 10 tasks with 72 tests (unit, integration, and E2E).

---

## 2. Architecture Overview

```
                          Browser (Vanilla JS)
  ┌──────────────────────────────────────────────────────────┐
  │                                                          │
  │  Phase 1         Phase 2          Phase 3                │
  │  ┌──────────┐    ┌───────────┐    ┌───────────────────┐  │
  │  │ API Key  │ -> │ PDF       │ -> │ Status Stream +   │  │
  │  │ Input    │    │ Upload    │    │ Download / Colab  │  │
  │  └──────────┘    └───────────┘    └───────────────────┘  │
  │                                                          │
  └───────────────────────┬──────────────────────────────────┘
                          │
              POST /api/generate (multipart form)
              Returns: text/event-stream (SSE)
                          │
  ┌───────────────────────▼──────────────────────────────────┐
  │                  FastAPI Backend                          │
  │                                                          │
  │  main.py ── routes & middleware                           │
  │     │                                                    │
  │     ▼                                                    │
  │  pipeline.py ── orchestrator (yields SSE events)         │
  │     │                                                    │
  │     ├──> pdf_extractor.py ── PyMuPDF text + structure    │
  │     │                                                    │
  │     ├──> llm_generator.py ── Phase 1: analyze_paper()    │
  │     │                        Phase 2: generate_cells()   │
  │     │                        (OpenAI gpt-5.4)            │
  │     │                                                    │
  │     └──> notebook_builder.py ── nbformat assembly        │
  │                                                          │
  │  errors.py ── validation & sanitized error messages      │
  │                                                          │
  │  generated/ ── saved .ipynb files (UUID-named)           │
  └──────────────────────────────────────────────────────────┘
```

---

## 3. Files Created/Modified

### 3.1 `app/main.py` -- FastAPI Application Entry Point

**Purpose:** Defines all HTTP routes, mounts static files, and wires together middleware.

**Key routes:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serves `static/index.html` |
| `GET` | `/api/health` | Health check (`{"status": "ok"}`) |
| `POST` | `/api/upload` | Upload PDF, return extracted text + metadata |
| `POST` | `/api/generate` | Upload PDF + API key, stream SSE progress, produce notebook |
| `GET` | `/api/download/{file_id}` | Download generated `.ipynb` by UUID |
| `GET` | `/api/notebook/{file_id}` | Serve notebook as JSON (for Colab URL import) |

**Important implementation details:**

- CORS is restricted to `localhost:8000`, `127.0.0.1:8000`, and `localhost:3000`.
- The `generated/` directory is created at import time via `GENERATED_DIR.mkdir(exist_ok=True)`.
- Path traversal is prevented in both download and notebook endpoints using `Path(file_id).name`:

```python
safe_id = Path(file_id).name          # strips ../ and other traversal
notebook_path = GENERATED_DIR / f"{safe_id}.ipynb"
```

- The `/api/generate` endpoint returns an `EventSourceResponse` (from `sse-starlette`), wrapping the async generator from `pipeline.run_pipeline`.

---

### 3.2 `app/pdf_extractor.py` -- PDF Text Extraction

**Purpose:** Extracts full text and structural metadata (title, authors, sections) from a PDF using PyMuPDF (fitz).

**Key functions:**

- `extract_pdf(pdf_bytes: bytes) -> dict` -- Main entry point. Returns `{title, authors, page_count, sections, full_text}`.
- `_detect_title(blocks)` -- Finds the largest-font text on page 0.
- `_detect_authors(blocks, title)` -- Grabs the first smaller-font line after the title.
- `_detect_sections(blocks)` -- Groups text by font-size heuristic: anything with font size > body_size + 1.5 is a heading.

**Section detection algorithm:**

```python
# Calculate body font size (most common size across all blocks)
sizes = [b["font_size"] for b in blocks]
body_size = max(set(sizes), key=sizes.count)

# Headings have font size > body size + 1.5
heading_threshold = body_size + 1.5
```

**Guards:**

- `MAX_PAGES = 50` -- PDFs exceeding this are rejected before text extraction.
- `MIN_TEXT_LENGTH = 100` -- If total extracted text is under 100 chars, the PDF is assumed to be scanned/empty.
- Invalid bytes (not a PDF) are caught by `fitz.open()` and re-raised as `PDFExtractionError`.

---

### 3.3 `app/llm_generator.py` -- OpenAI LLM Integration

**Purpose:** Two-phase LLM pipeline using gpt-5.4 to (1) analyze a paper and (2) generate notebook cells.

**Phase 1 -- `analyze_paper(client, paper_text) -> dict`:**

Sends the full paper text with `ANALYSIS_SYSTEM_PROMPT` to extract:
- Title, summary, key algorithms (with equations and parameters)
- Methodology steps, data characteristics, suggested packages, evaluation metrics

Uses `response_format={"type": "json_object"}` and `temperature=0.2` for deterministic structured output.

**Phase 2 -- `generate_notebook_cells(client, analysis, paper_text) -> list[dict]`:**

Takes the Phase 1 analysis plus the first 15,000 characters of the paper text as context. The `GENERATION_SYSTEM_PROMPT` is detailed and prescriptive:

- Every code cell must re-import its dependencies (prevents `NameError` after kernel restart)
- Targets 25-40 cells with specific ordering: title, setup, imports, background, data generation, per-algorithm sections (math + code + test + visualization), pipeline, experiments, discussion, references

Uses `temperature=0.3` and JSON structured output. Cells are validated after parsing:

```python
for cell in cells:
    if isinstance(cell, dict) and "cell_type" in cell and "source" in cell:
        if cell["cell_type"] in ("markdown", "code"):
            validated.append({...})
```

---

### 3.4 `app/notebook_builder.py` -- .ipynb Assembly

**Purpose:** Converts the list of cell dicts from the LLM into a valid, Colab-ready `.ipynb` file using nbformat.

**Key function:**

`build_notebook(cells, paper_meta) -> bytes` produces a complete notebook with:

1. **Notebook-level metadata** -- Python 3 kernel, Colab provenance, GPU accelerator hint.
2. **Header cell** -- Markdown with paper title, authors, attribution to Paper-to-Notebook, usage instructions.
3. **Setup cell** -- Auto-generated `!pip install -q ...` from detected imports.
4. **LLM-generated cells** -- All non-empty cells from the LLM, in order.
5. **Validation** -- `nbformat.validate(nb)` ensures the output is spec-compliant.

**Package detection** (`_detect_packages`):

Scans all code cells for `import X` / `from X` patterns and maps aliases to pip package names:

```python
common_packages = {
    "numpy": "numpy", "np": "numpy",
    "torch": "torch", "plt": "matplotlib",
    "sklearn": "scikit-learn", "pd": "pandas",
    "sns": "seaborn", ...
}
```

---

### 3.5 `app/pipeline.py` -- Pipeline Orchestrator

**Purpose:** Ties the entire backend pipeline together as an async generator that yields SSE events.

**Stages (each yields status messages):**

1. **PDF Extraction** -- Calls `extract_pdf()`, reports page count, section count, and paper title.
2. **Paper Analysis (LLM Phase 1)** -- Calls `analyze_paper()`, reports identified algorithms and methodology.
3. **Notebook Generation (LLM Phase 2)** -- Calls `generate_notebook_cells()`, reports cell counts (code vs. markdown).
4. **Notebook Assembly** -- Calls `build_notebook()`, writes to `generated/{uuid4}.ipynb`.

**SSE event types:**

| Event | Payload | When |
|-------|---------|------|
| `status` | `{"message": "..."}` | Each pipeline stage progress update |
| `complete` | `{"file_id", "title", "colab_url", "notebook_path"}` | Pipeline finished successfully |
| `error` | `{"message": "..."}` | Any stage failure |

**Error sanitization** (`_sanitize_error`):

```python
def _sanitize_error(exc: Exception) -> str:
    msg = str(exc)
    if "api_key" in msg.lower() or "authentication" in msg.lower():
        return "Invalid or expired API key. Please check your OpenAI API key."
    if "rate" in msg.lower() and "limit" in msg.lower():
        return "OpenAI rate limit exceeded. Please wait a moment and try again."
    if "timeout" in msg.lower():
        return "Request timed out. The paper may be too long. Try a shorter paper."
    return f"An error occurred: {msg}"
```

**Colab URL construction:**

The `complete` event includes a Colab URL template with `{BASE_URL}` placeholder. The frontend substitutes `window.location.origin` to build the final URL:

```
https://colab.research.google.com/url=<origin>/api/notebook/<file_id>
```

This means "Open in Colab" only works when the app is deployed to a public URL that Colab's servers can reach.

---

### 3.6 `app/errors.py` -- Custom Exceptions and Validation

**Purpose:** Centralized upload validation and custom exception types.

**Components:**

- `UploadValidationError(Exception)` -- Raised for invalid uploads.
- `MAX_FILE_SIZE_MB = 50` -- Maximum file size constant.
- `validate_pdf_upload(filename, file_size)` -- Checks:
  1. Filename is not empty
  2. Filename ends with `.pdf` (case-insensitive)
  3. File size is under 50 MB

Used by both `/api/upload` and `/api/generate` endpoints.

---

### 3.7 `static/index.html` -- Frontend HTML

**Purpose:** Single-page shell with three phases, no build step required.

**Structure:**

- **Header** -- Gradient title "Paper-to-Notebook" with tagline.
- **Phase 1 (API Key)** -- Password input + "Continue" button + privacy hint ("Your key stays in your browser").
- **Phase 2 (Upload)** -- Drag-and-drop zone with SVG icon, hidden file input, file info display, "Generate Notebook" button.
- **Phase 3 (Results)** -- Animated progress pulse bar, scrollable status log, "Download .ipynb" and "Open in Colab" action buttons.
- **Footer** -- "Powered by gpt-5.4".

All interactive elements have `data-testid` attributes for E2E testing.

---

### 3.8 `static/styles.css` -- Design System

**Purpose:** Dark theme inspired by arcprize.org with CSS custom properties, animations, and responsive breakpoints.

**Design tokens (CSS variables):**

```css
--bg: #0A0A0A;
--surface: #141414;
--accent-start: #6C63FF;       /* purple */
--accent-end: #4ECDC4;         /* teal */
--accent-gradient: linear-gradient(135deg, var(--accent-start), var(--accent-end));
--error: #FF6B6B;
--radius: 12px;
--transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
```

**Animations:**

| Name | Effect | Used on |
|------|--------|---------|
| `phaseIn` | Fade + slide up from 12px | Phase transitions |
| `fadeSlideIn` | Fade + slide up from 8px | Status entries, action buttons |
| `pulse` | Horizontal sweep 0% to 400% | Progress bar |
| `glowPulse` | Box-shadow intensity oscillation | Upload zone drag-over |
| `dotPulse` | Opacity 1 to 0.3 | Active status dot |

**Responsive:** At `max-width: 480px`, the input group and action buttons stack vertically, upload zone padding shrinks.

---

### 3.9 `static/app.js` -- Frontend Logic

**Purpose:** Vanilla JS (IIFE, strict mode) handling all user interactions and SSE stream parsing.

**State:** Two variables: `apiKey` (string) and `selectedFile` (File object).

**Phase transitions:**

`showPhase(phase)` hides all three phases and shows the target. Phases use CSS class `hidden` (display: none) with animation on reveal.

**API key validation:**

- Must not be empty
- Must start with `sk-`
- Key is stored only in the JS closure, never sent to a server except as form data to `/api/generate`

**File handling:**

- Click-to-browse and drag-and-drop both supported
- Client-side PDF MIME type check (`file.type !== "application/pdf"`)
- Displays filename and formatted size

**SSE stream consumption:**

The app uses `fetch()` + `ReadableStream` (not `EventSource`) because SSE comes from a POST endpoint and `EventSource` only supports GET:

```javascript
fetch("/api/generate", { method: "POST", body: formData })
    .then(function (response) {
        return readSSEStream(response.body.getReader());
    })
```

`readSSEStream` reads chunks from the `ReadableStream`, splits on `\n\n` (SSE event boundaries), and dispatches to `parseSSEBlock` which extracts `event:` and `data:` fields.

**Status display:**

Each status message appears as a `div.status-entry` with a pulsing dot icon. When a new status arrives, all previous entries are marked complete (dot replaced with checkmark, `active` class removed). On error, a "Try Again" button is injected.

**Colab URL construction:**

```javascript
var fullNotebookUrl = window.location.origin + notebookPath;
var colabUrl = "https://colab.research.google.com/url=" + encodeURIComponent(fullNotebookUrl);
```

**Test hook:** `window.P2N` exposes internal functions (`addStatus`, `showComplete`, `getApiKey`, etc.) for E2E tests.

---

### 3.10 `requirements.txt` -- Python Dependencies

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
python-multipart==0.0.20
openai==1.61.0
PyMuPDF==1.25.3
nbformat==5.10.4
sse-starlette==2.2.1
pytest==8.3.4
httpx==0.28.1
```

All pinned to exact versions. `httpx` is required by FastAPI's `TestClient`. `sse-starlette` provides the `EventSourceResponse` class. `python-multipart` is needed for form/file uploads.

---

### 3.11 `conftest.py` -- Root Test Configuration

```python
import nest_asyncio
nest_asyncio.apply()
```

Patches the event loop to allow nested `run_until_complete` calls, needed because `sse-starlette` and Playwright both manipulate the async event loop.

---

### 3.12 `pytest.ini` -- Pytest Settings

```ini
[pytest]
asyncio_mode = auto
```

Enables automatic async test discovery without requiring `@pytest.mark.asyncio` on every test.

---

## 4. Data Flow

Here is the step-by-step flow when a user generates a notebook:

```
1. User enters OpenAI API key in browser
   └─> Stored in JS variable only, never persisted

2. User selects/drops a PDF file
   └─> Client-side validation: must be application/pdf

3. User clicks "Generate Notebook"
   └─> Frontend sends POST /api/generate
       Body: multipart form with api_key (string) + file (PDF bytes)

4. Backend validates upload
   ├─> errors.validate_pdf_upload(): checks .pdf extension, <50MB
   └─> Returns HTTP 400 if invalid (frontend shows error + "Try Again")

5. Backend starts SSE stream (EventSourceResponse)
   └─> pipeline.run_pipeline() async generator begins

6. Stage 1: PDF Extraction
   ├─> pdf_extractor.extract_pdf(pdf_bytes)
   ├─> PyMuPDF opens PDF, iterates pages
   ├─> Extracts text blocks with font sizes
   ├─> Detects title (largest font, page 0)
   ├─> Detects authors (line after title)
   ├─> Detects sections (font > body_size + 1.5)
   ├─> Rejects if >50 pages or <100 chars extracted
   └─> SSE: "Extracted 12 pages with 8 sections. Paper: 'Title'"

7. Stage 2: Paper Analysis (LLM Phase 1)
   ├─> llm_generator.analyze_paper(client, full_text)
   ├─> Sends full paper text to gpt-5.4 with analysis prompt
   ├─> Returns JSON: title, algorithms, methodology, packages, metrics
   └─> SSE: "Identified 3 key algorithm(s): Self-Attention, FFN, ..."

8. Stage 3: Notebook Generation (LLM Phase 2)
   ├─> llm_generator.generate_notebook_cells(client, analysis, full_text)
   ├─> Sends analysis + first 15K chars of paper to gpt-5.4
   ├─> Returns JSON: list of {cell_type, source} dicts
   ├─> Validates cell structure, filters invalid entries
   └─> SSE: "Generated 32 cells (18 code, 14 markdown)"

9. Stage 4: Notebook Assembly
   ├─> notebook_builder.build_notebook(cells, paper_meta)
   ├─> Creates nbformat v4 notebook with Colab metadata
   ├─> Adds header cell, auto-detected pip install cell
   ├─> Appends all non-empty LLM cells
   ├─> Validates with nbformat.validate()
   ├─> Writes to generated/{uuid4}.ipynb
   └─> SSE: "Notebook ready for download!"

10. SSE complete event
    └─> {"file_id": "abc-123", "title": "...", "colab_url": "...", "notebook_path": "..."}

11. Frontend receives complete event
    ├─> Sets Download button href to /api/download/{file_id}
    ├─> Constructs Colab URL: https://colab.research.google.com/url=<origin>/api/notebook/{file_id}
    └─> Shows action buttons with fade-in animation

12. User clicks "Download .ipynb"
    └─> GET /api/download/{file_id} -> FileResponse (application/octet-stream)

13. User clicks "Open in Colab"
    └─> Opens new tab -> Colab fetches /api/notebook/{file_id} (JSON) -> loads notebook
```

---

## 5. Test Coverage

**72 tests total** across three tiers.

### Unit Tests (34 tests)

#### `tests/unit/test_pdf_extractor.py` (8 tests)
| Test | What it verifies |
|------|-----------------|
| `test_extract_returns_required_fields` | Output dict has title, page_count, sections, full_text |
| `test_extract_page_count` | Correct page count from sample PDF |
| `test_extract_title` | Title detection from largest font on page 0 |
| `test_extract_sections` | Section headers (Abstract, Introduction, Model Architecture) detected |
| `test_extract_full_text` | Full text contains multi-page content ("Transformer", "encoder-decoder") |
| `test_empty_pdf_raises` | Empty PDF raises PDFExtractionError with "no text" message |
| `test_large_pdf_raises` | 55-page PDF raises PDFExtractionError with "50" in message |
| `test_invalid_bytes_raises` | Non-PDF bytes raise PDFExtractionError |

#### `tests/unit/test_llm_generator.py` (6 tests)
| Test | What it verifies |
|------|-----------------|
| `test_analyze_paper_returns_structure` | analyze_paper returns dict with title, key_algorithms, methodology |
| `test_generate_notebook_cells_returns_list` | generate_notebook_cells returns list of valid cell dicts |
| `test_generate_notebook_cells_has_code_and_markdown` | Both cell types are present in output |
| `test_analyze_paper_prompt_includes_paper_text` | Paper text is included in the API call messages |
| `test_analyze_paper_uses_correct_model` | Model name is gpt-5.4 |
| `test_full_pipeline_create_client` | create_openai_client returns client with correct api_key |

All LLM tests use `unittest.mock.AsyncMock` to mock the OpenAI API.

#### `tests/unit/test_notebook_builder.py` (10 tests)
| Test | What it verifies |
|------|-----------------|
| `test_build_notebook_returns_bytes` | Output is non-empty bytes |
| `test_notebook_is_valid_nbformat` | Output passes nbformat.validate() |
| `test_notebook_has_python3_kernel` | Kernel metadata is Python 3 |
| `test_notebook_has_colab_metadata` | Colab provenance metadata present |
| `test_notebook_has_accelerator` | GPU accelerator hint in metadata |
| `test_notebook_has_header_cell` | First cell has paper title + attribution |
| `test_notebook_has_setup_cell` | First code cell has pip install command |
| `test_notebook_contains_all_llm_cells` | Algorithm content from input cells is present |
| `test_notebook_cell_count` | Total cells >= header + setup + LLM cells |
| `test_empty_cells_skipped` | Cells with empty source are filtered out |

#### `tests/unit/test_error_handling.py` (10 tests)
| Test | What it verifies |
|------|-----------------|
| `test_sanitize_error_auth` | Auth errors produce "API key" message, no raw codes |
| `test_sanitize_error_rate_limit` | Rate limit errors produce friendly message |
| `test_sanitize_error_timeout` | Timeout errors produce friendly message |
| `test_sanitize_error_generic` | Unknown errors still produce a message |
| `test_pdf_extraction_error_is_exception` | PDFExtractionError is raiseable |
| `test_max_file_size_constant_exists` | MAX_FILE_SIZE_MB is a positive number |
| `test_validate_pdf_upload_rejects_non_pdf` | .txt files rejected with "PDF" in message |
| `test_validate_pdf_upload_rejects_oversized` | Files over limit rejected with "size" in message |
| `test_validate_pdf_upload_accepts_valid` | Valid PDF name + size passes without error |
| `test_validate_pdf_upload_rejects_empty_filename` | Empty filename rejected |

### Integration Tests (19 tests)

#### `tests/integration/test_app_setup.py` (3 tests)
| Test | What it verifies |
|------|-----------------|
| `test_health_check` | GET /api/health returns 200 + `{"status": "ok"}` |
| `test_static_index_served` | GET / returns HTML with "Paper-to-Notebook" |
| `test_cors_headers` | OPTIONS request returns CORS headers |

#### `tests/integration/test_upload_endpoint.py` (4 tests)
| Test | What it verifies |
|------|-----------------|
| `test_upload_pdf_success` | Valid PDF returns 200 with title, sections, page_count |
| `test_upload_non_pdf_rejected` | .txt upload returns 400 |
| `test_upload_large_pdf_rejected` | 55-page PDF returns 400 with "50" in detail |
| `test_upload_no_file_returns_422` | Missing file field returns 422 |

#### `tests/integration/test_generate_endpoint.py` (5 tests)
| Test | What it verifies |
|------|-----------------|
| `test_generate_streams_sse_events` | SSE stream has status + complete events with file_id |
| `test_generate_creates_downloadable_notebook` | After generation, /api/download/{id} returns 200 |
| `test_generate_rejects_missing_api_key` | Missing api_key field returns 422 |
| `test_generate_rejects_non_pdf` | .txt file returns 400 |
| `test_download_nonexistent_returns_404` | Non-existent file_id returns 404 |

#### `tests/integration/test_colab_link.py` (2 tests)
| Test | What it verifies |
|------|-----------------|
| `test_complete_event_includes_colab_url` | Complete SSE event has colab_url with colab.research.google.com |
| `test_notebook_endpoint_serves_ipynb` | /api/notebook/{id} returns JSON with cells key |

#### `tests/integration/test_error_cases.py` (5 tests)
| Test | What it verifies |
|------|-----------------|
| `test_upload_oversized_file` | Large PDF returns 400 |
| `test_generate_non_pdf_returns_400` | .txt to /api/generate returns 400 with "PDF" |
| `test_generate_empty_filename_returns_400` | File without .pdf extension returns 400 |
| `test_download_path_traversal_blocked` | `../../etc/passwd` and URL-encoded variants return 404 |
| `test_notebook_path_traversal_blocked` | Path traversal on /api/notebook returns 404 |

### E2E Tests (19 tests)

All E2E tests use Playwright to drive a real browser against a running uvicorn server.

#### `tests/e2e/test_frontend_ui.py` (8 tests -- server on port 8765)
| Test | What it verifies |
|------|-----------------|
| `test_page_loads_with_dark_theme` | Background is rgb(10,10,10), title is "Paper-to-Notebook" |
| `test_api_key_phase_visible` | API key input and submit button visible on load |
| `test_upload_phase_hidden_initially` | Upload zone is hidden before API key entry |
| `test_transition_to_upload_phase` | Entering API key shows upload zone, hides API key phase |
| `test_results_phase_elements_exist` | Download and Colab buttons exist but are hidden initially |
| `test_status_log_exists` | Status log div exists in DOM |
| `test_responsive_layout` | At 375px width, API key input is still visible |
| `test_inter_font_loaded` | Body font-family includes "Inter" |

#### `tests/e2e/test_full_flow.py` (4 tests -- server on port 8766)
| Test | What it verifies |
|------|-----------------|
| `test_full_flow_api_key_to_upload` | API key entry transitions to upload phase |
| `test_file_selection_shows_generate_button` | Selecting a PDF shows file info + generate button |
| `test_generate_shows_status_phase` | Clicking generate transitions to results phase with status log |
| `test_status_messages_appear_in_log` | Status log has text content after generation starts |

#### `tests/e2e/test_ui_polish.py` (7 tests -- server on port 8767)
| Test | What it verifies |
|------|-----------------|
| `test_phase_transition_has_animation` | Phase containers have CSS transition on opacity/transform |
| `test_upload_zone_glow_on_hover` | Upload zone responds to hover (visual test with screenshot) |
| `test_button_hover_effects` | Submit button has non-"none" CSS transition |
| `test_powered_by_badge_visible` | Footer contains "gpt-5.4" |
| `test_keyboard_enter_submits_api_key` | Enter key in API key input triggers phase transition |
| `test_mobile_layout_stacked` | At 375px, input is >= 250px wide (stacked layout) |
| `test_full_polished_flow_screenshot` | Captures desktop screenshots at 1280x800 for visual review |

---

## 6. Security Measures

### API Key Handling
- The OpenAI API key is entered in a `type="password"` input with `autocomplete="off"` and `spellcheck="false"`.
- The key is stored only in a JS closure variable -- never written to localStorage, cookies, or any persistent storage.
- The key is sent to the backend only as a form field in the POST `/api/generate` request, then passed directly to the OpenAI client. It is never logged or stored on the server.
- The frontend displays: "Your key stays in your browser and is never stored on our servers."

### Path Traversal Protection
Both `/api/download/{file_id}` and `/api/notebook/{file_id}` use `Path(file_id).name` to strip directory traversal sequences. This means `../../etc/passwd` becomes `passwd`, which does not match any file in `generated/`. Tested explicitly in `test_error_cases.py`.

### Input Validation
- File extension must be `.pdf` (case-insensitive).
- File size capped at 50 MB.
- PDF page count capped at 50 pages.
- Minimum text length of 100 characters (rejects scanned/image-only PDFs).
- All validation errors return user-friendly messages without leaking internals.

### Error Sanitization
The `_sanitize_error()` function in `pipeline.py` strips raw error codes and internal details from LLM API errors, returning only generic user-friendly messages for auth failures, rate limits, and timeouts.

### CORS
Origins are explicitly whitelisted (localhost:8000, 127.0.0.1:8000, localhost:3000). Not wildcard.

---

## 7. Known Limitations

1. **No authentication or rate limiting.** Anyone with the URL can use the app. The only gate is the user-provided OpenAI API key.

2. **"Open in Colab" requires a public URL.** Colab's servers must be able to fetch the notebook JSON from `/api/notebook/{file_id}`. This does not work on localhost -- the app must be deployed to a publicly accessible domain.

3. **Generated notebooks are stored on disk indefinitely.** There is no cleanup mechanism for the `generated/` directory. Files accumulate until manually deleted.

4. **No concurrent request handling for heavy workloads.** The LLM calls are async, but there is no queue, backpressure, or worker pool. Under heavy load, all requests hit OpenAI simultaneously.

5. **PDF extraction is heuristic-based.** Title and section detection rely on font-size comparisons, which can fail on PDFs with unusual formatting, multi-column layouts, or non-standard fonts.

6. **Paper text truncation.** In Phase 2 (generation), only the first 15,000 characters of the paper are sent to the LLM (`paper_text[:15000]`). Very long papers may lose important content from later sections.

7. **No notebook validation beyond nbformat.** The generated code is not executed or syntax-checked. Runtime errors in cells are possible.

8. **Single-file storage with no database.** File IDs are UUIDs, but there is no metadata stored about who generated what or when.

9. **No retry logic for LLM API calls.** If an OpenAI request fails, the entire pipeline fails. There is no automatic retry with exponential backoff.

10. **E2E tests require Playwright installed.** The E2E test suite depends on Playwright browsers being installed (`playwright install`), which adds significant setup overhead.

---

## 8. What's Next (v2 Priorities)

Based on the PRD's "Out of Scope (v2+)" section and the limitations above:

1. **Deployment infrastructure** -- Dockerize the app, add a `docker-compose.yml`, and deploy to a cloud provider so "Open in Colab" works end-to-end.

2. **Generated file cleanup** -- Add a TTL-based cleanup job (or use temp directories) so `generated/` does not grow unbounded.

3. **LLM retry with backoff** -- Wrap OpenAI calls in a retry decorator (e.g., `tenacity`) with exponential backoff for rate limits and transient failures.

4. **Notebook execution validation** -- After generation, execute the notebook in a sandboxed environment and report cell-level pass/fail.

5. **User accounts and history** -- Add authentication so users can view their previously generated notebooks.

6. **Batch processing** -- Accept multiple papers and generate notebooks in parallel.

7. **Improved PDF parsing** -- Use a more robust parser (e.g., GROBID, science-parse) for better section/figure/table detection.

8. **Streaming LLM output** -- Stream the LLM generation token-by-token to the frontend instead of waiting for the full response, reducing perceived latency.

9. **Custom templates** -- Let users choose notebook styles, frameworks (PyTorch vs. TensorFlow), or detail levels.

10. **Usage tracking and cost estimation** -- Show estimated token usage and cost before generation begins.
