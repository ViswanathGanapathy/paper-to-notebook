"""FastAPI application — Paper-to-Notebook backend."""
import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import Cookie, FastAPI, Header, Request, UploadFile, File, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sse_starlette.sse import EventSourceResponse

from app.errors import (
    UploadValidationError,
    validate_content_length,
    validate_pdf_magic_bytes,
    validate_pdf_upload,
)
from app.cleanup import cleanup_generated_files
from app.history import add_history_entry, get_history
from app.pdf_extractor import extract_pdf, PDFExtractionError
from app.pipeline import run_pipeline
from app.security import SecurityHeadersMiddleware, is_production, limiter, rate_limit_exceeded_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
GENERATED_DIR = Path(__file__).resolve().parent.parent / "generated"
GENERATED_DIR.mkdir(exist_ok=True)

CLEANUP_INTERVAL_SECONDS = 600  # 10 minutes


@asynccontextmanager
async def lifespan(app_instance):
    """Startup/shutdown lifecycle — runs background cleanup task."""
    async def _cleanup_loop():
        while True:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            cleanup_generated_files(GENERATED_DIR)

    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()


# Disable docs in production
_docs_url = None if is_production() else "/docs"
_redoc_url = None if is_production() else "/redoc"

app = FastAPI(
    title="Paper-to-Notebook",
    version="0.2.0",
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    lifespan=lifespan,
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Security headers on all responses
app.add_middleware(SecurityHeadersMiddleware)

# CORS: restricted methods and headers (SEC-010)
# WARNING: Never set allow_origins=["*"] with allow_credentials=True — this
# enables any website to make authenticated cross-origin requests (CSRF risk).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/api/health")
@limiter.limit("60/minute")
async def health_check(request: Request) -> dict:
    return {"status": "ok"}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.post("/api/upload")
@limiter.limit("20/minute")
async def upload_pdf(request: Request, file: UploadFile = File(...)) -> dict:
    """Upload a PDF and extract text with structure."""
    try:
        # Pre-check Content-Length before reading body (SEC-006)
        content_length = request.headers.get("content-length")
        if content_length:
            validate_content_length(int(content_length))

        pdf_bytes = await file.read()
        validate_pdf_upload(file.filename or "", len(pdf_bytes))
        validate_pdf_magic_bytes(pdf_bytes)
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        result = extract_pdf(pdf_bytes)
    except PDFExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return result


@app.post("/api/generate")
@limiter.limit("5/minute")
async def generate_notebook(
    request: Request,
    file: UploadFile = File(...),
    x_api_key: str | None = Header(None),
    p2n_session: str | None = Cookie(None),
) -> EventSourceResponse:
    """Upload PDF + API key (via X-API-Key header), stream progress via SSE."""
    api_key = x_api_key or ""
    if not api_key:
        raise HTTPException(status_code=400, detail="Missing API key. Send it via the X-API-Key header.")

    filename = file.filename or ""

    try:
        content_length = request.headers.get("content-length")
        if content_length:
            validate_content_length(int(content_length))

        pdf_bytes = await file.read()
        validate_pdf_upload(filename, len(pdf_bytes))
        validate_pdf_magic_bytes(pdf_bytes)
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Ensure session ID exists
    session_id = p2n_session or str(uuid.uuid4())

    async def event_stream() -> AsyncGenerator[dict, None]:
        async for event in run_pipeline(api_key, pdf_bytes, filename):
            # Record completed generations in history
            if event.get("event") == "complete":
                data = json.loads(event.get("data", "{}"))
                add_history_entry(session_id, data.get("file_id", ""), data.get("title", ""))
            yield event

    return EventSourceResponse(event_stream())


@app.get("/api/download/{file_id}")
@limiter.limit("60/minute")
async def download_notebook(request: Request, file_id: str) -> FileResponse:
    """Download a generated notebook by file ID."""
    safe_id = Path(file_id).name
    notebook_path = GENERATED_DIR / f"{safe_id}.ipynb"

    if not notebook_path.exists():
        raise HTTPException(status_code=404, detail="Notebook not found.")

    return FileResponse(
        path=str(notebook_path),
        media_type="application/octet-stream",
        filename=f"{safe_id}.ipynb",
    )


@app.get("/api/notebook/{file_id}")
@limiter.limit("60/minute")
async def serve_notebook_json(request: Request, file_id: str) -> JSONResponse:
    """Serve notebook as JSON — required for Colab's URL-based import."""
    safe_id = Path(file_id).name
    notebook_path = GENERATED_DIR / f"{safe_id}.ipynb"

    if not notebook_path.exists():
        raise HTTPException(status_code=404, detail="Notebook not found.")

    notebook_data = json.loads(notebook_path.read_text(encoding="utf-8"))
    return JSONResponse(content=notebook_data)


@app.get("/api/history")
@limiter.limit("60/minute")
async def get_generation_history(
    request: Request,
    p2n_session: str | None = Cookie(None),
) -> JSONResponse:
    """Get generation history for the current session."""
    session_id = p2n_session or ""
    if not session_id:
        # No session yet — return empty with a new session cookie
        session_id = str(uuid.uuid4())
        response = JSONResponse(content=[])
        response.set_cookie("p2n_session", session_id, httponly=True, samesite="strict", max_age=86400)
        return response

    history = get_history(session_id)
    return JSONResponse(content=history)
