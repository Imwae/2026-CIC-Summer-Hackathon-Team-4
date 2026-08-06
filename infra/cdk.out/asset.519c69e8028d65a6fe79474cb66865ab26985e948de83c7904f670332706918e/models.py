"""Pydantic schemas for the Semester Capacity Planner API contract."""

import re
from datetime import date
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, field_validator


class Deliverable(BaseModel):
    """A single course deliverable extracted from a syllabus."""

    name: str
    type: Literal["exam", "essay", "project", "presentation", "lab", "other"]
    due_date: Optional[str] = None
    week_number: int
    weight_percent: Optional[float] = None
    estimated_prep_weeks: int
    estimated_hours_total: float

    @field_validator('week_number', 'estimated_prep_weeks', mode='before')
    @classmethod
    def coerce_to_int(cls, v):
        if isinstance(v, str):
            # Handle "Week 5" style strings
            match = re.search(r'\d+', str(v))
            return int(match.group()) if match else 1
        return int(v) if v is not None else 1

    @field_validator('type', mode='before')
    @classmethod
    def coerce_type(cls, v):
        valid_types = {"exam", "essay", "project", "presentation", "lab", "other"}
        if isinstance(v, str) and v.lower() in valid_types:
            return v.lower()
        return "other"


class ExtractionRequest(BaseModel):
    """Request body for the POST /api/extract endpoint."""

    course_text: str
    file_name: str = ""


class ExtractionResponse(BaseModel):
    """Response body for the POST /api/extract endpoint."""

    status: Literal["success", "failure"]
    course_code: Optional[str] = None
    course_name: Optional[str] = None
    deliverables: List[Deliverable] = []
    error_message: Optional[str] = None


class Commitment(BaseModel):
    """A recurring weekly commitment (work, sleep, commute, etc.)."""

    name: str
    category: Literal["work", "commute", "sleep", "extracurricular", "leisure", "other"]
    hours_per_week: float
    locked: bool = False


class CommitmentParseRequest(BaseModel):
    """Request body for the POST /api/commitments/parse endpoint."""

    text: str


class CommitmentParseResponse(BaseModel):
    """Response body for the POST /api/commitments/parse endpoint."""

    commitments: List[Commitment]

class CourseInput(BaseModel):
    """A course with its deliverables, used as input for semester analysis."""

    course_code: str
    course_name: str
    deliverables: List[Deliverable]


class AnalysisRequest(BaseModel):
    """Request body for the POST /api/analyze endpoint."""

    courses: List[CourseInput]
    commitments: List[Commitment]
    break_weeks: List[int] = []
    semester_start: date
    semester_end: date


class WeekResult(BaseModel):
    """A single week's capacity analysis result."""

    week_number: int
    start_date: str  # YYYY-MM-DD format
    is_break: bool
    hours_required: float
    hours_available: float
    over_capacity: bool
    collision: bool
    deliverables_due: List[str] = []  # e.g. ["CS101: Midterm Exam"]
    prep_hours_by_course: Dict[str, float] = {}  # e.g. {"CS101": 6.0, "ENG200": 4.0}


class AnalysisResponse(BaseModel):
    """Response body for the POST /api/analyze endpoint."""

    feasible: bool
    feasibility_level: Literal["feasible", "tight", "not_feasible"]
    total_weeks: int
    weeks: List[WeekResult]
    critical_weeks: List[int]  # week numbers that are over capacity
    collision_weeks: List[int]  # week numbers with deliverables from 2+ courses
    recovery_floor_breached: bool
    verdict: str  # AI-generated feasibility narrative


class Suggestion(BaseModel):
    """A single AI-generated suggestion for resolving over-capacity weeks."""

    description: str
    target_commitment: str
    action: Literal["reduce", "reschedule", "redistribute"]
    detail: str
    affected_weeks: List[int]


class SuggestionRequest(BaseModel):
    """Request body for the POST /api/suggest endpoint."""

    analysis_result: AnalysisResponse
    commitments: List[Commitment]

class SuggestionResponse(BaseModel):
    """Response body for the POST /api/suggest endpoint."""

    suggestions: List[Suggestion]
    locked_acknowledgment: str


class ErrorResponse(BaseModel):
    """Standardized error response returned by all API endpoints on failure."""

    error: bool = True
    message: str
    code: Literal[
        "EXTRACTION_FAILED",
        "ANALYSIS_FAILED",
        "SUGGESTION_FAILED",
        "PARSE_ERROR",
        "BEDROCK_TIMEOUT",
        "INTERNAL_ERROR",
    ]
