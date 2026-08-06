"""Tests for error handling: verify user-friendly error messages, no stack traces.

Confirms that submitting invalid/empty text to API endpoints produces
user-friendly error messages. No unhandled stack traces appear in any
error scenario.
"""

from unittest.mock import MagicMock, patch

# Patch boto3.client at import time so bedrock_client.py module-level
# client creation doesn't require real AWS credentials.
with patch("boto3.client", return_value=MagicMock()):
    import pytest
    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.bedrock_client import (
        BedrockClientError,
        BedrockParseError,
        BedrockTimeoutError,
    )
    from backend.models import WeekResult, AnalysisResponse, CourseInput

    # Fix capacity.py's fallback imports
    import backend.capacity as _capacity
    _capacity.WeekResult = WeekResult
    _capacity.AnalysisResponse = AnalysisResponse
    _capacity.CourseInput = CourseInput


STACK_TRACE_PATTERNS = ["Traceback", 'File "', "raise ", "Exception("]


@pytest.fixture
def client():
    """FastAPI TestClient wired to the app."""
    return TestClient(app)


def _assert_no_stack_trace(response_text: str):
    """Assert that the response body does not contain stack trace indicators."""
    for pattern in STACK_TRACE_PATTERNS:
        assert pattern not in response_text, (
            f"Response contains stack trace pattern: '{pattern}'"
        )


# ---------------------------------------------------------------------------
# POST /api/extract — empty/invalid text
# ---------------------------------------------------------------------------


class TestExtractErrorHandling:
    """Verify /api/extract returns user-friendly errors for invalid input."""

    def test_empty_course_text_returns_failure(self, client):
        """Empty course_text → status='failure' with readable error_message."""
        response = client.post(
            "/api/extract",
            json={"course_text": "", "file_name": "test.txt"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failure"
        assert data["error_message"] is not None
        assert len(data["error_message"]) > 0
        _assert_no_stack_trace(response.text)

    def test_whitespace_only_course_text_returns_failure(self, client):
        """Whitespace-only course_text → status='failure' with readable error_message."""
        response = client.post(
            "/api/extract",
            json={"course_text": "   \n\t  ", "file_name": "test.txt"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failure"
        assert data["error_message"] is not None
        assert len(data["error_message"]) > 0
        _assert_no_stack_trace(response.text)

    def test_invalid_json_body_returns_error(self, client):
        """Completely invalid JSON body → error response without stack trace."""
        response = client.post(
            "/api/extract",
            content=b"this is not json at all",
            headers={"Content-Type": "application/json"},
        )

        # FastAPI returns 422 for validation errors or the endpoint catches the error
        assert response.status_code in (400, 422, 200, 500)
        _assert_no_stack_trace(response.text)

    @patch("backend.main.extract_syllabus")
    def test_bedrock_timeout_returns_friendly_error(self, mock_extract, client):
        """Bedrock timeout during extraction → user-friendly error, no stack trace."""
        mock_extract.side_effect = BedrockTimeoutError()

        response = client.post(
            "/api/extract",
            json={"course_text": "Some valid text here", "file_name": "test.txt"},
        )

        # The endpoint catches this in its own try/except and returns failure
        data = response.json()
        assert data.get("status") == "failure" or data.get("error") is True
        _assert_no_stack_trace(response.text)

    @patch("backend.main.extract_syllabus")
    def test_unexpected_exception_returns_friendly_error(self, mock_extract, client):
        """Unexpected exception during extraction → user-friendly error, no stack trace."""
        mock_extract.side_effect = RuntimeError("Something went wrong unexpectedly")

        response = client.post(
            "/api/extract",
            json={"course_text": "Some valid text here", "file_name": "test.txt"},
        )

        data = response.json()
        # The endpoint's try/except catches all exceptions and returns failure
        assert data.get("status") == "failure" or data.get("error") is True
        assert "error_message" in data or "message" in data
        _assert_no_stack_trace(response.text)


# ---------------------------------------------------------------------------
# POST /api/commitments/parse — empty/invalid text
# ---------------------------------------------------------------------------


class TestCommitmentsParseErrorHandling:
    """Verify /api/commitments/parse returns user-friendly errors for invalid input."""

    def test_empty_text_returns_error(self, client):
        """Empty text field → 422 with error=true and human-readable message."""
        response = client.post(
            "/api/commitments/parse",
            json={"text": ""},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error"] is True
        assert "message" in data
        assert len(data["message"]) > 0
        assert data["code"] == "PARSE_ERROR"
        _assert_no_stack_trace(response.text)

    def test_whitespace_only_text_returns_error(self, client):
        """Whitespace-only text → 422 with error=true and human-readable message."""
        response = client.post(
            "/api/commitments/parse",
            json={"text": "   \n\t  "},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error"] is True
        assert "message" in data
        assert len(data["message"]) > 0
        _assert_no_stack_trace(response.text)

    def test_missing_text_field_returns_validation_error(self, client):
        """Missing required 'text' field → validation error without stack trace."""
        response = client.post(
            "/api/commitments/parse",
            json={},
        )

        # FastAPI returns 422 for Pydantic validation failures
        assert response.status_code == 422
        _assert_no_stack_trace(response.text)

    @patch("backend.main.parse_commitments")
    def test_bedrock_timeout_returns_friendly_error(self, mock_parse, client):
        """Bedrock timeout → 504 with user-friendly error message."""
        mock_parse.side_effect = BedrockTimeoutError()

        response = client.post(
            "/api/commitments/parse",
            json={"text": "I work 20 hours a week and sleep 8 hours a night"},
        )

        assert response.status_code == 504
        data = response.json()
        assert data["error"] is True
        assert "message" in data
        assert "timed out" in data["message"].lower() or "timeout" in data["message"].lower()
        _assert_no_stack_trace(response.text)

    @patch("backend.main.parse_commitments")
    def test_bedrock_client_error_returns_friendly_error(self, mock_parse, client):
        """Bedrock client error → 502 with user-friendly error message."""
        mock_parse.side_effect = BedrockClientError(
            "AWS Bedrock error: access denied", error_code="PARSE_ERROR"
        )

        response = client.post(
            "/api/commitments/parse",
            json={"text": "I work 20 hours a week"},
        )

        assert response.status_code == 502
        data = response.json()
        assert data["error"] is True
        assert "message" in data
        assert len(data["message"]) > 0
        _assert_no_stack_trace(response.text)

    @patch("backend.main.parse_commitments")
    def test_bedrock_parse_error_returns_friendly_error(self, mock_parse, client):
        """Bedrock parse error → 422 with user-friendly error message."""
        mock_parse.side_effect = BedrockParseError(
            "Failed to parse model response", error_code="PARSE_ERROR"
        )

        response = client.post(
            "/api/commitments/parse",
            json={"text": "I work 20 hours a week"},
        )

        assert response.status_code == 422
        data = response.json()
        assert data["error"] is True
        assert "message" in data
        _assert_no_stack_trace(response.text)


# ---------------------------------------------------------------------------
# Global exception handler — unhandled exceptions
# ---------------------------------------------------------------------------


class TestGlobalExceptionHandler:
    """Verify the catch-all exception handler returns user-friendly errors."""

    @patch("backend.main.parse_commitments")
    def test_unhandled_exception_returns_500_with_friendly_message(
        self, mock_parse
    ):
        """Unhandled exception → 500 with generic user-friendly message, no stack trace."""
        mock_parse.side_effect = ValueError("Some totally unexpected internal error")

        # Use raise_server_exceptions=False so unhandled errors go through
        # the global exception handler instead of being re-raised by TestClient.
        with TestClient(app, raise_server_exceptions=False) as c:
            response = c.post(
                "/api/commitments/parse",
                json={"text": "I work 20 hours a week and sleep 8 hours"},
            )

        assert response.status_code == 500
        data = response.json()
        assert data["error"] is True
        assert "message" in data
        assert "code" in data
        assert data["code"] == "INTERNAL_ERROR"
        # Must NOT contain internal error details
        assert "ValueError" not in data["message"]
        assert "Some totally unexpected" not in data["message"]
        _assert_no_stack_trace(response.text)

    def test_invalid_json_to_commitments_parse(self, client):
        """Sending non-JSON content to /api/commitments/parse → error without stack trace."""
        response = client.post(
            "/api/commitments/parse",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )

        # FastAPI returns 422 for JSON parsing failure
        assert response.status_code == 422
        _assert_no_stack_trace(response.text)

    def test_wrong_content_type_to_extract(self, client):
        """Sending wrong content type to /api/extract → handles gracefully."""
        response = client.post(
            "/api/extract",
            content=b"plain text body",
            headers={"Content-Type": "text/plain"},
        )

        # The endpoint tries to parse as JSON for non-multipart, might fail
        # but should not expose stack trace
        _assert_no_stack_trace(response.text)


# ---------------------------------------------------------------------------
# Error response format validation
# ---------------------------------------------------------------------------


class TestErrorResponseFormat:
    """Verify all error responses follow the { error, message, code } contract."""

    def test_extract_empty_text_has_error_message_field(self, client):
        """ExtractionResponse with status=failure has error_message field."""
        response = client.post(
            "/api/extract",
            json={"course_text": "", "file_name": ""},
        )

        data = response.json()
        assert data["status"] == "failure"
        assert "error_message" in data
        # Error message should be human-readable (not a class name or code)
        assert data["error_message"] != ""
        assert not data["error_message"].startswith("__")

    def test_commitments_parse_empty_has_error_format(self, client):
        """CommitmentParse with empty text returns standard ErrorResponse format."""
        response = client.post(
            "/api/commitments/parse",
            json={"text": ""},
        )

        data = response.json()
        assert "error" in data
        assert "message" in data
        assert "code" in data
        assert data["error"] is True
        assert isinstance(data["message"], str)
        assert isinstance(data["code"], str)
