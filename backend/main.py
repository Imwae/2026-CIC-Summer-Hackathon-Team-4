"""FastAPI application — API routes for the Semester Capacity Planner."""

import logging
from typing import Optional

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.bedrock_client import extract_syllabus
from backend.extractor import extract_text_from_pdf
from backend.models import ExtractionRequest, ExtractionResponse, ErrorResponse

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
# Global exception handler — never expose stack traces
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=True,
            message="An unexpected error occurred. Please try again.",
            code="EXTRACTION_FAILED",
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
