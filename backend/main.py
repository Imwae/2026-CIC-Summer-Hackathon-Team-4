"""FastAPI application — API routes for the Semester Capacity Planner."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

try:
    from backend.bedrock_client import (
        analyze_capacity,
        extract_syllabus,
        generate_suggestions,
        parse_commitments,
        BedrockClientError,
        BedrockTimeoutError,
        BedrockParseError,
    )
    from backend.capacity import compute_capacity
    from backend.extractor import extract_text_from_pdf
    from backend.models import (
        AnalysisRequest,
        AnalysisResponse,
        CommitmentParseRequest,
        CommitmentParseResponse,
        ExtractionRequest,
        ExtractionResponse,
        ErrorResponse,
        SuggestionRequest,
        SuggestionResponse,
    )
except ImportError:
    from bedrock_client import (
        analyze_capacity,
        extract_syllabus,
        generate_suggestions,
        parse_commitments,
        BedrockClientError,
        BedrockTimeoutError,
        BedrockParseError,
    )
    from capacity import compute_capacity
    from extractor import extract_text_from_pdf
    from models import (
        AnalysisRequest,
        AnalysisResponse,
        CommitmentParseRequest,
        CommitmentParseResponse,
        ExtractionRequest,
        ExtractionResponse,
        ErrorResponse,
        SuggestionRequest,
        SuggestionResponse,
    )

logger = logging.getLogger(__name__)

app = FastAPI(title="Semester Capacity Planner")

# CORS: allow Vite dev server in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global exception handlers — never expose stack traces
# ---------------------------------------------------------------------------


@app.exception_handler(BedrockTimeoutError)
async def bedrock_timeout_handler(request: Request, exc: BedrockTimeoutError):
    """Handle Bedrock timeout errors at the app level."""
    logger.error("Bedrock timeout: %s", exc)
    return JSONResponse(
        status_code=504,
        content=ErrorResponse(
            error=True,
            message="The AI service timed out. Please try again.",
            code="BEDROCK_TIMEOUT",
        ).model_dump(),
    )


@app.exception_handler(BedrockClientError)
async def bedrock_client_error_handler(request: Request, exc: BedrockClientError):
    """Handle Bedrock client errors at the app level."""
    logger.error("Bedrock client error: %s", exc)
    return JSONResponse(
        status_code=502,
        content=ErrorResponse(
            error=True,
            message="An error occurred while communicating with the AI service. Please try again.",
            code=exc.error_code,
        ).model_dump(),
    )


@app.exception_handler(BedrockParseError)
async def bedrock_parse_error_handler(request: Request, exc: BedrockParseError):
    """Handle Bedrock parse errors at the app level."""
    logger.error("Bedrock parse error: %s", exc)
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error=True,
            message="Failed to process the AI response. Please try again.",
            code=exc.error_code,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for any unhandled exceptions. Never exposes stack traces."""
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=True,
            message="An unexpected error occurred. Please try again.",
            code="INTERNAL_ERROR",
        ).model_dump(),
    )


# ---------------------------------------------------------------------------
# POST /api/extract
# Accepts JSON (text paste) or multipart/form-data (PDF upload)
# ---------------------------------------------------------------------------
@app.post("/api/extract", response_model=ExtractionResponse)
async def extract_syllabus_endpoint(
    request: Request,
):
    """Extract course deliverables from pasted text or an uploaded PDF.

    Supports two content types:
    - application/json: { "course_text": "...", "file_name": "..." }
    - multipart/form-data: file (PDF binary) + optional file_name field
    """
    content_type = request.headers.get("content-type", "")

    try:
        if "multipart/form-data" in content_type:
            # --- PDF upload path ---
            form = await request.form()
            file: Optional[UploadFile] = form.get("file")

            if file is None:
                return ExtractionResponse(
                    status="failure",
                    error_message="No file provided in the upload.",
                )

            file_bytes = await file.read()

            if not file_bytes:
                return ExtractionResponse(
                    status="failure",
                    error_message="Uploaded file is empty.",
                )

            # Extract text from PDF
            text = extract_text_from_pdf(file_bytes)

            if text is None or text.strip() == "":
                return ExtractionResponse(
                    status="failure",
                    error_message="Could not extract text from the uploaded PDF. Please try pasting the syllabus text instead.",
                )

        else:
            # --- JSON text paste path ---
            body = await request.json()
            extraction_req = ExtractionRequest(**body)
            text = extraction_req.course_text

            if not text or text.strip() == "":
                return ExtractionResponse(
                    status="failure",
                    error_message="No course text provided.",
                )

        # Call Bedrock to extract structured data from the syllabus text
        result = extract_syllabus(text)
        return result

    except Exception as exc:
        logger.exception("Error in /api/extract: %s", exc)
        return ExtractionResponse(
            status="failure",
            error_message="An error occurred while processing your request. Please try again.",
        )


# ---------------------------------------------------------------------------
# POST /api/commitments/parse
# Accepts free-text description, returns structured commitments
# ---------------------------------------------------------------------------
@app.post("/api/commitments/parse", response_model=CommitmentParseResponse)
async def parse_commitments_endpoint(body: CommitmentParseRequest):
    """Parse a free-text description of weekly commitments into structured data.

    Accepts a JSON body with a single `text` field describing the user's
    typical week and returns a list of parsed Commitment objects.
    """
    if not body.text or not body.text.strip():
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=True,
                message="Text field must not be empty.",
                code="PARSE_ERROR",
            ).model_dump(),
        )

    try:
        result = parse_commitments(body.text)
        return result
    except BedrockTimeoutError as exc:
        logger.error("Bedrock timeout in /api/commitments/parse: %s", exc)
        return JSONResponse(
            status_code=504,
            content=ErrorResponse(
                error=True,
                message=str(exc),
                code=exc.error_code,
            ).model_dump(),
        )
    except BedrockClientError as exc:
        logger.error("Bedrock client error in /api/commitments/parse: %s", exc)
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                error=True,
                message=str(exc),
                code=exc.error_code,
            ).model_dump(),
        )
    except BedrockParseError as exc:
        logger.error("Bedrock parse error in /api/commitments/parse: %s", exc)
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=True,
                message=str(exc),
                code=exc.error_code,
            ).model_dump(),
        )


# ---------------------------------------------------------------------------
# POST /api/analyze
# Accepts course/commitment data, runs capacity analysis + AI narrative
# ---------------------------------------------------------------------------
@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_endpoint(body: AnalysisRequest):
    """Run semester capacity analysis and generate an AI feasibility narrative.

    Accepts courses, commitments, break weeks, and semester dates. Returns
    a full capacity breakdown with per-week data and an AI-generated verdict.
    """
    try:
        # 1. Run deterministic capacity analysis
        result = compute_capacity(
            courses=body.courses,
            commitments=body.commitments,
            break_weeks=body.break_weeks,
            semester_start=body.semester_start,
            semester_end=body.semester_end,
        )

        # 2. Generate AI narrative verdict via Bedrock
        capacity_data = result.model_dump()
        narrative = analyze_capacity(capacity_data)

        # 3. Attach the narrative to the response
        result.verdict = narrative

        return result

    except BedrockTimeoutError as exc:
        logger.error("Bedrock timeout in /api/analyze: %s", exc)
        return JSONResponse(
            status_code=504,
            content=ErrorResponse(
                error=True,
                message=str(exc),
                code="ANALYSIS_FAILED",
            ).model_dump(),
        )
    except BedrockClientError as exc:
        logger.error("Bedrock client error in /api/analyze: %s", exc)
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                error=True,
                message=str(exc),
                code="ANALYSIS_FAILED",
            ).model_dump(),
        )
    except BedrockParseError as exc:
        logger.error("Bedrock parse error in /api/analyze: %s", exc)
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=True,
                message=str(exc),
                code="ANALYSIS_FAILED",
            ).model_dump(),
        )


# ---------------------------------------------------------------------------
# POST /api/suggest
# Accepts analysis result + commitments, returns AI-generated suggestions
# ---------------------------------------------------------------------------
@app.post("/api/suggest", response_model=SuggestionResponse)
async def suggest_endpoint(body: SuggestionRequest):
    """Generate AI-powered schedule adjustment suggestions.

    Accepts the full analysis result and the user's commitments (with lock
    flags). Returns actionable suggestions that respect locked commitments.
    """
    try:
        result = generate_suggestions(
            analysis_result=body.analysis_result.model_dump(),
            commitments=[c.model_dump() for c in body.commitments],
        )
        return result

    except BedrockTimeoutError as exc:
        logger.error("Bedrock timeout in /api/suggest: %s", exc)
        return JSONResponse(
            status_code=504,
            content=ErrorResponse(
                error=True,
                message=str(exc),
                code="SUGGESTION_FAILED",
            ).model_dump(),
        )
    except BedrockClientError as exc:
        logger.error("Bedrock client error in /api/suggest: %s", exc)
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                error=True,
                message=str(exc),
                code="SUGGESTION_FAILED",
            ).model_dump(),
        )
    except BedrockParseError as exc:
        logger.error("Bedrock parse error in /api/suggest: %s", exc)
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=True,
                message=str(exc),
                code="SUGGESTION_FAILED",
            ).model_dump(),
        )

# ---------------------------------------------------------------------------
# Static file serving — serve React build in production/deployment
# ---------------------------------------------------------------------------

# Resolve the frontend/dist directory relative to the project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DIST_DIR = _PROJECT_ROOT / "frontend" / "dist"

if _DIST_DIR.is_dir():
    # SPA catch-all: serve index.html for any path not matched by API routes
    # or static assets. This enables React client-side routing.
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve static files from the React build, with SPA fallback to index.html."""
        # Try to serve the exact file requested
        file_path = _DIST_DIR / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        # Fallback to index.html for client-side routing
        index_path = _DIST_DIR / "index.html"
        if index_path.is_file():
            return FileResponse(index_path)
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    logger.info("Serving static files from %s", _DIST_DIR)
else:
    logger.info(
        "frontend/dist/ not found at %s — static file serving disabled (dev mode)",
        _DIST_DIR,
    )
