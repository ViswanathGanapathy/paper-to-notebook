# Sprint v2 — PRD: Security Hardening + PDF/Notebook Quality

## Overview
Harden the Paper-to-Notebook application against the 20 security findings from the v1 audit,
focusing on the Critical and High severity issues: prompt injection mitigation, rate limiting,
security headers, API key handling, and resource exhaustion prevention. Additionally, improve
PDF parsing quality (tables, multi-column layouts, math notation) and enhance generated notebook
explanations. Add generation history so users can revisit past notebooks without re-generating.

## Goals
- All Critical and High security findings (SEC-001 through SEC-006) are resolved
- Medium-severity findings (SEC-007 through SEC-013, SEC-015) are resolved
- Rate limiting prevents abuse of the expensive `/api/generate` endpoint
- Prompt injection is mitigated with input sanitization + output code scanning
- Generated notebooks include richer explanations (step-by-step algorithm walkthrough, equation-to-code mapping)
- PDF extraction handles multi-column papers, tables, and math notation better
- Users can view a history of their generated notebooks in the current browser session

## User Stories
- As a researcher, I want the generated notebook to explain each algorithm step-by-step
  with equations mapped to code, so I can deeply understand the implementation
- As a user, I want to see my previously generated notebooks, so I don't re-upload the same paper
- As a user, I want to trust that the generated code is safe to run, so I don't have to
  manually audit every cell for malicious patterns
- As a user, I want the app to handle complex papers with tables and multi-column layouts
  correctly, so I get complete text extraction

## Technical Architecture

### What Changes from v1
```
v1 Architecture (unchanged)              v2 Additions
┌──────────────────────────┐    ┌──────────────────────────────────────┐
│  Browser (Vanilla JS)    │    │  + Session-based generation history  │
│  Phase 1 → 2 → 3        │    │  + API key sent via header (not form)│
│                          │    │  + History panel in UI               │
└────────────┬─────────────┘    └──────────────────────────────────────┘
             │
┌────────────▼─────────────┐    ┌──────────────────────────────────────┐
│  FastAPI Backend         │    │  + Security headers middleware       │
│  main.py → pipeline.py   │    │  + Rate limiting (slowapi)           │
│  → llm_generator.py      │    │  + Prompt injection sanitizer        │
│  → notebook_builder.py   │    │  + Output code scanner               │
│  → pdf_extractor.py      │    │  + Streaming file upload (no full    │
│                          │    │    read into memory)                 │
│  generated/              │    │  + Auto-cleanup (1hr TTL)            │
│                          │    │  + /docs disabled in production      │
│  errors.py               │    │  + Enhanced error sanitization       │
└──────────────────────────┘    └──────────────────────────────────────┘
```

### New Components
- **`app/security.py`** — Security headers middleware, rate limiter setup, CORS tightening
- **`app/sanitizer.py`** — Prompt injection sanitizer (input) + code scanner (output)
- **`app/history.py`** — In-memory session history (keyed by browser session ID)
- **Enhanced `app/pdf_extractor.py`** — Multi-column detection, table extraction, math notation handling
- **Enhanced `app/llm_generator.py`** — Richer prompts for detailed explanations, equation-to-code mapping

### Security Architecture
```
Request Flow with Security:

Browser                    FastAPI
  │                          │
  ├─── X-API-Key header ────▶│  (not in form body anymore)
  │                          │
  │                          ├── Rate limiter check (slowapi)
  │                          │   └── 429 if over limit
  │                          │
  │                          ├── Security headers added to response
  │                          │   (CSP, X-Frame-Options, HSTS, etc.)
  │                          │
  │                          ├── File size check BEFORE full read
  │                          │   └── 413 if Content-Length too large
  │                          │
  │                          ├── PDF magic byte validation (%PDF-)
  │                          │
  │                          ├── Text extraction
  │                          │
  │                          ├── Prompt injection sanitizer
  │                          │   └── Strip delimiter patterns
  │                          │   └── Escape adversarial sequences
  │                          │
  │                          ├── LLM call (with timeout)
  │                          │
  │                          ├── Output code scanner
  │                          │   └── Flag: os.system, subprocess,
  │                          │     eval, exec, network exfil,
  │                          │     credential access
  │                          │   └── Add warning cell if flagged
  │                          │
  │                          └── Notebook assembly + response
```

## Out of Scope (v3+)
- User authentication (accounts, OAuth, sessions with persistence)
- Dockerization and cloud deployment
- Persistent database for history (v2 uses in-memory, browser sessionStorage)
- Notebook editing/customization before download
- Multiple LLM provider support (Anthropic, Gemini)
- OCR for scanned PDFs (would need Tesseract/cloud OCR)

## Dependencies
- Sprint v1 (all 10 tasks complete, 72 tests passing)
- `slowapi` package for rate limiting
- `secure` package for security headers (or custom middleware)
