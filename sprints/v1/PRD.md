# Sprint v1 — PRD: Paper-to-Notebook (Research Paper → Colab Notebook Generator)

## Overview
Build a web application where researchers upload a PDF research paper and receive a
production-quality Google Colab notebook (.ipynb) that implements the paper's algorithms
and methodology as a structured tutorial. The app uses OpenAI's gpt-5.4 reasoning model
to deeply understand the paper and generate runnable, research-grade code with realistic
synthetic data. Target users are ML researchers at top labs (OpenAI, DeepMind, etc.) who
want to accelerate paper replication.

## Goals
- User can open the app, enter their OpenAI API key, and upload a PDF research paper
- The system extracts text from the PDF and sends it to gpt-5.4 for deep analysis
- A high-quality, structured .ipynb notebook is generated with runnable code and realistic synthetic data
- User sees real-time streaming status updates during generation (not a blank loading screen)
- User can download the .ipynb file or click "Open in Colab" to launch it directly
- UI matches the clean, dark, modern aesthetic of arcprize.org

## User Stories
- As an ML researcher, I want to upload a paper and get a runnable notebook, so I can replicate results faster
- As a user, I want to see progress updates while the notebook generates, so I know the system is working
- As a user, I want to enter my own OpenAI API key, so I control my usage and costs
- As a user, I want to open the generated notebook directly in Colab, so I can start experimenting immediately

## Technical Architecture

### Tech Stack
- **Backend**: Python 3.11+ / FastAPI
- **PDF Parsing**: PyMuPDF (fitz) for text + structure extraction
- **LLM**: OpenAI API — gpt-5.4 (reasoning model for deep paper understanding)
- **Notebook Generation**: nbformat (programmatic .ipynb creation)
- **Streaming**: Server-Sent Events (SSE) for real-time status updates to the frontend
- **Frontend**: Single-page vanilla HTML/CSS/JS (no build step), served by FastAPI static files
- **Design**: Dark theme inspired by arcprize.org — Inter font, dark backgrounds, clean spacing

### Component Diagram
```
┌─────────────────────────────────────────────────────┐
│                   Browser (Frontend)                 │
│  ┌───────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ API Key   │→ │ PDF      │→ │ Status Stream +  │  │
│  │ Input     │  │ Upload   │  │ Download/Colab   │  │
│  └───────────┘  └──────────┘  └──────────────────┘  │
└──────────────────────┬──────────────────────────────┘
                       │ REST + SSE
┌──────────────────────▼──────────────────────────────┐
│                 FastAPI Backend                       │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐  │
│  │ PDF      │→ │ OpenAI    │→ │ Notebook         │  │
│  │ Extractor│  │ Analyzer  │  │ Builder          │  │
│  └──────────┘  └───────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Data Flow
1. User enters OpenAI API key (stored in browser session only, never persisted)
2. User uploads PDF → backend extracts full text + section structure via PyMuPDF
3. Backend sends extracted text to gpt-5.4 with a carefully crafted prompt
4. gpt-5.4 returns structured notebook content (markdown + code cells)
5. Backend assembles .ipynb file using nbformat
6. Throughout steps 2-5, SSE streams status messages to the frontend
7. User downloads .ipynb or clicks "Open in Colab" (via Colab's GitHub Gist URL scheme or file upload)

### Notebook Quality Requirements
The generated notebook must be **research-grade**, not a toy demo:
- **Structure**: Title, abstract summary, background/motivation, algorithm breakdown (step-by-step),
  implementation with type hints and docstrings, experiments with synthetic data, results visualization,
  discussion/limitations, references
- **Code quality**: Production Python — type hints, proper imports, modular functions, numpy/pytorch
  as appropriate, matplotlib/plotly visualizations
- **Synthetic data**: Realistic distributions matching the paper's domain (not random noise).
  Data generation is clearly documented and parameterized
- **Runnable**: Every cell should execute in Google Colab without errors (pip installs included)
- **Educational**: Inline explanations connect code to paper equations/concepts

## Out of Scope (v2+)
- User authentication and accounts
- Usage tracking and rate limiting
- Batch processing (multiple papers)
- Paper comparison mode
- Notebook editing in-browser before download
- Persistent storage of generated notebooks
- Deployment infrastructure (Docker, cloud hosting)
- Custom notebook templates or style preferences

## Dependencies
- None (greenfield project)
- User provides their own OpenAI API key at runtime
