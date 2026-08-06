"""Tests for PDF extraction — specifically verifying graceful handling of corrupted/invalid files."""

import io

import pytest
from PyPDF2 import PdfWriter

from backend.extractor import extract_text_from_pdf


class TestExtractTextFromPdfCorruptedFiles:
    """Verify that extract_text_from_pdf returns None (never crashes) for invalid inputs."""

    def test_empty_bytes(self):
        """Empty byte string should return None, not raise."""
        result = extract_text_from_pdf(b"")
        assert result is None

    def test_random_bytes(self):
        """Random/garbage bytes should return None, not raise."""
        result = extract_text_from_pdf(b"\x00\x01\x02\xff\xfe\xfd" * 100)
        assert result is None

    def test_truncated_pdf_header(self):
        """A truncated PDF (just the header) should return None, not raise."""
        result = extract_text_from_pdf(b"%PDF-1.4")
        assert result is None

    def test_non_pdf_text_file(self):
        """Plain text content (not a PDF) should return None, not raise."""
        result = extract_text_from_pdf(b"This is just plain text, not a PDF file at all.")
        assert result is None

    def test_html_content(self):
        """HTML content should return None, not raise."""
        html = b"<html><body><h1>Not a PDF</h1></body></html>"
        result = extract_text_from_pdf(html)
        assert result is None

    def test_truncated_valid_pdf(self):
        """A valid PDF that is abruptly truncated mid-stream should return None, not raise."""
        # Create a real PDF in memory, then truncate it
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        buf = io.BytesIO()
        writer.write(buf)
        full_pdf = buf.getvalue()

        # Truncate to half the content — should be unreadable
        truncated = full_pdf[: len(full_pdf) // 2]
        result = extract_text_from_pdf(truncated)
        assert result is None

    def test_single_null_byte(self):
        """A single null byte should return None, not raise."""
        result = extract_text_from_pdf(b"\x00")
        assert result is None

    def test_large_random_bytes(self):
        """A large chunk of random data should return None, not raise."""
        import os

        random_data = os.urandom(10_000)
        result = extract_text_from_pdf(random_data)
        assert result is None

    def test_valid_pdf_with_no_text(self):
        """A valid PDF that contains no extractable text (blank page) returns None."""
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        buf = io.BytesIO()
        writer.write(buf)
        blank_pdf = buf.getvalue()

        result = extract_text_from_pdf(blank_pdf)
        assert result is None
