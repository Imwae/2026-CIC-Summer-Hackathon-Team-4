"""PDF text extraction utilities for the Semester Capacity Planner."""

import io
from typing import Optional

from PyPDF2 import PdfReader


def extract_text_from_pdf(file_bytes: bytes) -> Optional[str]:
    """Extract text content from uploaded PDF bytes.

    Args:
        file_bytes: Raw bytes of a PDF file (e.g. from an uploaded file).

    Returns:
        The concatenated text from all pages, or None if the PDF is
        corrupted, image-only, or contains no usable text.
    """
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text_parts: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

        full_text = "\n".join(text_parts)

        if not full_text.strip():
            return None

        return full_text
    except Exception:
        # Corrupted PDF, invalid format, or any PyPDF2 error
        return None
