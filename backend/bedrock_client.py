"""Bedrock client — sole boto3 importer in the project.

Provides AI-powered functions for syllabus extraction, capacity analysis,
suggestion generation, and commitment parsing via Amazon Bedrock.
"""

import json
import os
import re

import boto3
from botocore.exceptions import ClientError, ReadTimeoutError
from pydantic import ValidationError

from backend.models import (
    CommitmentParseResponse,
    ExtractionResponse,
    SuggestionResponse,
)
from backend.prompts import (
    ANALYSIS_PROMPT,
    COMMITMENT_PARSE_PROMPT,
    EXTRACTION_PROMPT,
    SUGGESTION_PROMPT,
)


# ---------------------------------------------------------------------------
# Custom Exception Classes
# ---------------------------------------------------------------------------
class BedrockClientError(Exception):
    """Raised when an AWS Bedrock API call fails (ClientError or connection issue)."""

    def __init__(self, message: str, error_code: str):
        super().__init__(message)
        self.error_code = error_code


class BedrockTimeoutError(Exception):
    """Raised when a Bedrock request times out."""

    def __init__(self, message: str = "Request to Bedrock timed out. Please try again."):
        super().__init__(message)
        self.error_code = "BEDROCK_TIMEOUT"


class BedrockParseError(Exception):
    """Raised when the Bedrock response cannot be parsed or validated."""

    def __init__(self, message: str, error_code: str):
        super().__init__(message)
        self.error_code = error_code


# ---------------------------------------------------------------------------
# Configuration from environment variables (never hardcoded credentials)
# ---------------------------------------------------------------------------
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
)

# ---------------------------------------------------------------------------
# Module-level Bedrock Runtime client
# Uses the boto3 default credential chain (env vars / IAM role)
# ---------------------------------------------------------------------------
bedrock_runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION)


# ---------------------------------------------------------------------------
# Helper: strip markdown code fences from model output
# ---------------------------------------------------------------------------
def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers from model output."""
    stripped = text.strip()
    stripped = re.sub(r"^```(?:json)?\s*\n?", "", stripped)
    stripped = re.sub(r"\n?```\s*$", "", stripped)
    return stripped.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def extract_syllabus(text: str) -> ExtractionResponse:
    """Call Bedrock to extract structured deliverables from syllabus text.

    Args:
        text: Raw syllabus text (pasted or extracted from PDF).

    Returns:
        ExtractionResponse with status="success" and extracted course info,
        or status="failure" with a human-readable error_message.
    """
    # 1. Format the extraction prompt
    prompt = EXTRACTION_PROMPT.format(
        syllabus_text=text,
        schema=json.dumps(ExtractionResponse.model_json_schema(), indent=2),
    )

    # 2. Build the request body for Claude Messages API
    request_body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
    )

    # 3. Call Bedrock
    try:
        response = bedrock_runtime.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=request_body,
        )
    except ClientError as exc:
        error_msg = exc.response["Error"].get("Message", str(exc))
        return ExtractionResponse(
            status="failure",
            error_message=f"AWS Bedrock error: {error_msg}",
        )
    except ReadTimeoutError:
        return ExtractionResponse(
            status="failure",
            error_message="Request to Bedrock timed out. Please try again.",
        )
    except ConnectionError:
        return ExtractionResponse(
            status="failure",
            error_message="Network connection error while contacting Bedrock. Check your network and try again.",
        )
    except Exception as exc:
        return ExtractionResponse(
            status="failure",
            error_message=f"Unexpected error during syllabus extraction: {type(exc).__name__}: {exc}",
        )

    # 4. Parse the response body
    try:
        response_body = json.loads(response["body"].read())
        raw_text = response_body["content"][0]["text"]
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        return ExtractionResponse(
            status="failure",
            error_message=f"Unexpected response format from Bedrock: {exc}",
        )

    # 5. Parse JSON from model output with one retry on failure
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        # Retry: strip markdown code fences and parse again
        try:
            cleaned = _strip_markdown_fences(raw_text)
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            return ExtractionResponse(
                status="failure",
                error_message=f"Failed to parse model response as JSON: {exc}",
            )

    # 6. Validate against ExtractionResponse schema
    try:
        result = ExtractionResponse.model_validate(parsed)
    except ValidationError as exc:
        return ExtractionResponse(
            status="failure",
            error_message=f"Model output did not match expected schema: {exc}",
        )

    return result


def analyze_capacity(capacity_data: dict) -> str:
    """Call Bedrock to generate a feasibility narrative for the semester plan.

    Args:
        capacity_data: Dictionary containing weekly capacity breakdown
            (hours available, hours required, deliverables per week, etc.)

    Returns:
        A plain-text narrative verdict string (under 200 words) describing
        whether the schedule is feasible, tight, or not feasible.

    Raises:
        BedrockClientError: On AWS API or connection failures.
        BedrockTimeoutError: When the request times out.
        BedrockParseError: When the response cannot be parsed.
    """
    # 1. Format the analysis prompt
    prompt = ANALYSIS_PROMPT.format(
        capacity_json=json.dumps(capacity_data, indent=2, default=str)
    )

    # 2. Build the request body for Claude Messages API
    request_body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
    )

    # 3. Call Bedrock
    try:
        response = bedrock_runtime.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=request_body,
        )
    except ClientError as exc:
        error_msg = exc.response["Error"].get("Message", str(exc))
        raise BedrockClientError(
            f"AWS Bedrock error during capacity analysis: {error_msg}",
            error_code="ANALYSIS_FAILED",
        )
    except ReadTimeoutError:
        raise BedrockTimeoutError(
            "Request to Bedrock timed out during capacity analysis. Please try again."
        )
    except ConnectionError:
        raise BedrockClientError(
            "Network connection error while contacting Bedrock. Check your network and try again.",
            error_code="ANALYSIS_FAILED",
        )
    except Exception as exc:
        raise BedrockClientError(
            f"Unexpected error during capacity analysis: {type(exc).__name__}: {exc}",
            error_code="ANALYSIS_FAILED",
        )

    # 4. Parse the response body
    try:
        response_body = json.loads(response["body"].read())
        raw_text = response_body["content"][0]["text"]
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise BedrockParseError(
            f"Unexpected response format from Bedrock: {exc}",
            error_code="ANALYSIS_FAILED",
        )

    # 5. Return the narrative text directly (strip markdown fences if present)
    result = raw_text.strip()
    if result.startswith("```"):
        result = _strip_markdown_fences(result)

    return result


def generate_suggestions(
    analysis_result: dict, commitments: list
) -> SuggestionResponse:
    """Call Bedrock to generate schedule adjustment suggestions.

    Args:
        analysis_result: Dictionary containing the AnalysisResponse data
            (weeks with over_capacity flags, hours_required/available, etc.)
        commitments: List of commitment dicts/objects with lock flags.

    Returns:
        SuggestionResponse with actionable suggestions and locked acknowledgment.

    Raises:
        BedrockClientError: On AWS API or connection failures.
        BedrockTimeoutError: When the request times out.
        BedrockParseError: When the response cannot be parsed or validated.
    """
    # 1. Extract locked and unlocked commitments
    locked_items = []
    unlocked_items = []
    for c in commitments:
        # Support both dict and object access
        if isinstance(c, dict):
            name = c.get("name", "Unknown")
            category = c.get("category", "other")
            hours = c.get("hours_per_week", 0)
            locked = c.get("locked", False)
        else:
            name = getattr(c, "name", "Unknown")
            category = getattr(c, "category", "other")
            hours = getattr(c, "hours_per_week", 0)
            locked = getattr(c, "locked", False)

        entry = f"- {name} ({category}): {hours} hrs/week"
        if locked:
            locked_items.append(entry)
        else:
            unlocked_items.append(entry)

    locked_list = "\n".join(locked_items) if locked_items else "None"
    unlocked_list = "\n".join(unlocked_items) if unlocked_items else "None"

    # 2. Extract over-capacity weeks
    weeks = analysis_result.get("weeks", [])
    over_capacity_lines = []
    for week in weeks:
        if isinstance(week, dict):
            is_over = week.get("over_capacity", False)
            week_num = week.get("week_number", "?")
            required = week.get("hours_required", 0)
            available = week.get("hours_available", 0)
            deliverables_due = week.get("deliverables_due", [])
        else:
            is_over = getattr(week, "over_capacity", False)
            week_num = getattr(week, "week_number", "?")
            required = getattr(week, "hours_required", 0)
            available = getattr(week, "hours_available", 0)
            deliverables_due = getattr(week, "deliverables_due", [])

        if is_over:
            deficit = required - available
            due_str = ", ".join(deliverables_due) if deliverables_due else "N/A"
            over_capacity_lines.append(
                f"- Week {week_num}: {required:.1f}h required vs {available:.1f}h available "
                f"(deficit: {deficit:.1f}h). Due: {due_str}"
            )

    over_capacity_weeks_data = (
        "\n".join(over_capacity_lines) if over_capacity_lines else "None"
    )

    # 3. Build the prompt
    prompt = SUGGESTION_PROMPT.format(
        locked_list=locked_list,
        over_capacity_weeks_data=over_capacity_weeks_data,
        unlocked_list=unlocked_list,
        schema=json.dumps(SuggestionResponse.model_json_schema(), indent=2),
    )

    # 4. Build the request body for Claude Messages API
    request_body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
    )

    # 5. Call Bedrock
    try:
        response = bedrock_runtime.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=request_body,
        )
    except ClientError as exc:
        error_msg = exc.response["Error"].get("Message", str(exc))
        raise BedrockClientError(
            f"AWS Bedrock error during suggestion generation: {error_msg}",
            error_code="SUGGESTION_FAILED",
        )
    except ReadTimeoutError:
        raise BedrockTimeoutError(
            "Request to Bedrock timed out during suggestion generation. Please try again."
        )
    except ConnectionError:
        raise BedrockClientError(
            "Network connection error while contacting Bedrock. Check your network and try again.",
            error_code="SUGGESTION_FAILED",
        )
    except Exception as exc:
        raise BedrockClientError(
            f"Unexpected error during suggestion generation: {type(exc).__name__}: {exc}",
            error_code="SUGGESTION_FAILED",
        )

    # 6. Parse the response body
    try:
        response_body = json.loads(response["body"].read())
        raw_text = response_body["content"][0]["text"]
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise BedrockParseError(
            f"Unexpected response format from Bedrock: {exc}",
            error_code="SUGGESTION_FAILED",
        )

    # 7. Parse JSON from model output with one retry on failure
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        # Retry: strip markdown code fences and parse again
        try:
            cleaned = _strip_markdown_fences(raw_text)
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise BedrockParseError(
                f"Failed to parse suggestion response as JSON: {exc}",
                error_code="SUGGESTION_FAILED",
            )

    # 8. Validate against SuggestionResponse schema
    try:
        result = SuggestionResponse.model_validate(parsed)
    except ValidationError as exc:
        raise BedrockParseError(
            f"Suggestion response did not match expected schema: {exc}",
            error_code="SUGGESTION_FAILED",
        )

    return result


def parse_commitments(text: str) -> CommitmentParseResponse:
    """Call Bedrock to parse free-text commitment descriptions into structured data.

    Args:
        text: Free-text description of a student's weekly schedule/commitments.

    Returns:
        CommitmentParseResponse with a list of parsed Commitment objects.

    Raises:
        BedrockClientError: On AWS API or connection failures.
        BedrockTimeoutError: When the request times out.
        BedrockParseError: When the response cannot be parsed or validated.
    """
    # 1. Format the commitment parse prompt
    prompt = COMMITMENT_PARSE_PROMPT.format(
        free_text=text,
        schema=json.dumps(CommitmentParseResponse.model_json_schema(), indent=2),
    )

    # 2. Build the request body for Claude Messages API
    request_body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
    )

    # 3. Call Bedrock
    try:
        response = bedrock_runtime.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=request_body,
        )
    except ClientError as exc:
        error_msg = exc.response["Error"].get("Message", str(exc))
        raise BedrockClientError(
            f"AWS Bedrock error during commitment parsing: {error_msg}",
            error_code="PARSE_ERROR",
        )
    except ReadTimeoutError:
        raise BedrockTimeoutError(
            "Request to Bedrock timed out during commitment parsing. Please try again."
        )
    except ConnectionError:
        raise BedrockClientError(
            "Network connection error while contacting Bedrock. Check your network and try again.",
            error_code="PARSE_ERROR",
        )
    except Exception as exc:
        raise BedrockClientError(
            f"Unexpected error during commitment parsing: {type(exc).__name__}: {exc}",
            error_code="PARSE_ERROR",
        )

    # 4. Parse the response body
    try:
        response_body = json.loads(response["body"].read())
        raw_text = response_body["content"][0]["text"]
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise BedrockParseError(
            f"Unexpected response format from Bedrock: {exc}",
            error_code="PARSE_ERROR",
        )

    # 5. Parse JSON from model output with one retry on failure
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        # Retry: strip markdown code fences and parse again
        try:
            cleaned = _strip_markdown_fences(raw_text)
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise BedrockParseError(
                f"Failed to parse commitment response as JSON: {exc}",
                error_code="PARSE_ERROR",
            )

    # 6. Validate against CommitmentParseResponse schema
    try:
        result = CommitmentParseResponse.model_validate(parsed)
    except ValidationError as exc:
        raise BedrockParseError(
            f"Commitment response did not match expected schema: {exc}",
            error_code="PARSE_ERROR",
        )

    return result
