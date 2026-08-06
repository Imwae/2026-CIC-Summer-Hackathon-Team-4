"""End-to-end integration test: full application flow with mocked Bedrock client.

Exercises the complete happy-path:
  1. Paste a sample syllabus → POST /api/extract → get ExtractionResponse
  2. Enter commitments (structured data)
  3. POST /api/analyze (uses deterministic capacity logic + mocked AI narrative)
  4. Verify timeline data (per-week breakdown)
  5. POST /api/suggest for over-capacity weeks → get SuggestionResponse

All Bedrock (AI) calls are mocked so the test runs without AWS credentials.
"""

from unittest.mock import MagicMock, patch

# Patch boto3.client at import time so bedrock_client.py module-level
# client creation doesn't require real AWS credentials.
with patch("boto3.client", return_value=MagicMock()):
    import pytest
    from fastapi.testclient import TestClient

    from backend.main import app
    from backend.models import (
        AnalysisResponse,
        CommitmentParseResponse,
        ExtractionResponse,
        SuggestionResponse,
        Deliverable,
        Commitment,
        CourseInput,
        Suggestion,
        WeekResult,
    )

    # Fix capacity.py's fallback imports: when running from project root,
    # `from models import ...` fails so WeekResult/AnalysisResponse are None.
    # Patch them with the correct classes so compute_capacity works.
    import backend.capacity as _capacity
    _capacity.WeekResult = WeekResult
    _capacity.AnalysisResponse = AnalysisResponse
    _capacity.CourseInput = CourseInput


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """FastAPI TestClient wired to the app."""
    return TestClient(app)


@pytest.fixture
def sample_syllabus_text():
    """Realistic syllabus text (subset of CS101 sample)."""
    return (
        "CS101 — Introduction to Computer Science\n"
        "Fall 2025\n\n"
        "EVALUATION SCHEME\n"
        "| Deliverable                | Due Date       | Weight |\n"
        "| Assignment 1: Variables    | Week 4         |   10%  |\n"
        "| Midterm Exam               | Week 7         |   25%  |\n"
        "| Final Exam                 | 2025-12-12     |   35%  |\n"
    )


@pytest.fixture
def mock_extraction_response():
    """The ExtractionResponse that our mocked extract_syllabus will return."""
    return ExtractionResponse(
        status="success",
        course_code="CS101",
        course_name="Introduction to Computer Science",
        deliverables=[
            Deliverable(
                name="Assignment 1: Variables",
                type="exam",
                due_date=None,
                week_number=4,
                weight_percent=10.0,
                estimated_prep_weeks=2,
                estimated_hours_total=10.0,
            ),
            Deliverable(
                name="Midterm Exam",
                type="exam",
                due_date=None,
                week_number=7,
                weight_percent=25.0,
                estimated_prep_weeks=2,
                estimated_hours_total=15.0,
            ),
            Deliverable(
                name="Final Exam",
                type="exam",
                due_date="2025-12-12",
                week_number=14,
                weight_percent=35.0,
                estimated_prep_weeks=3,
                estimated_hours_total=22.0,
            ),
        ],
    )


@pytest.fixture
def commitments():
    """Structured commitments for the analysis step."""
    return [
        Commitment(name="Sleep", category="sleep", hours_per_week=7.0, locked=False),
        Commitment(name="Part-time job", category="work", hours_per_week=20.0, locked=True),
        Commitment(name="Commute", category="commute", hours_per_week=8.0, locked=True),
        Commitment(name="Leisure", category="leisure", hours_per_week=10.0, locked=False),
    ]


@pytest.fixture
def mock_suggestion_response():
    """The SuggestionResponse that our mocked generate_suggestions will return."""
    return SuggestionResponse(
        suggestions=[
            Suggestion(
                description="Reduce part-time work hours during midterm week",
                target_commitment="Part-time job",
                action="reduce",
                detail="Cut shifts from 20h to 12h in weeks 6-7 to free prep time for the midterm.",
                affected_weeks=[6, 7],
            ),
            Suggestion(
                description="Redistribute final exam prep to start earlier",
                target_commitment="Part-time job",
                action="redistribute",
                detail="Begin studying 1 week earlier to spread the 22h over 4 weeks instead of 3.",
                affected_weeks=[11, 12, 13, 14],
            ),
        ],
        locked_acknowledgment="Locked commitments (Part-time job, Commute) are preserved.",
    )


# ---------------------------------------------------------------------------
# End-to-end test
# ---------------------------------------------------------------------------

class TestEndToEndFlow:
    """Full happy-path integration test: extract → analyze → suggest."""

    @patch("backend.main.extract_syllabus")
    def test_extract_syllabus_from_pasted_text(
        self, mock_extract, client, sample_syllabus_text, mock_extraction_response
    ):
        """Step 1: POST /api/extract with pasted syllabus text returns deliverables."""
        mock_extract.return_value = mock_extraction_response

        response = client.post(
            "/api/extract",
            json={"course_text": sample_syllabus_text, "file_name": "cs101.txt"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["course_code"] == "CS101"
        assert data["course_name"] == "Introduction to Computer Science"
        assert len(data["deliverables"]) == 3

        # Verify deliverable structure
        d1 = data["deliverables"][0]
        assert d1["name"] == "Assignment 1: Variables"
        assert d1["week_number"] == 4
        assert d1["weight_percent"] == 10.0
        assert d1["estimated_prep_weeks"] == 2

        # Confirm the mock was called with the syllabus text
        mock_extract.assert_called_once_with(sample_syllabus_text)

    @patch("backend.main.analyze_capacity")
    def test_analyze_capacity_with_timeline(
        self, mock_narrative, client, mock_extraction_response, commitments
    ):
        """Step 2-4: POST /api/analyze with extraction data + commitments returns timeline."""
        mock_narrative.return_value = "This semester is tight but manageable."

        # Build the analysis request from the extraction output
        course_input = {
            "course_code": mock_extraction_response.course_code,
            "course_name": mock_extraction_response.course_name,
            "deliverables": [d.model_dump() for d in mock_extraction_response.deliverables],
        }

        analysis_payload = {
            "courses": [course_input],
            "commitments": [c.model_dump() for c in commitments],
            "break_weeks": [],
            "semester_start": "2025-09-08",
            "semester_end": "2025-12-22",
        }

        response = client.post("/api/analyze", json=analysis_payload)

        assert response.status_code == 200
        data = response.json()

        # Gate condition: analysis requires successful extraction data
        assert "feasibility_level" in data
        assert data["feasibility_level"] in ("feasible", "tight", "not_feasible")
        assert "total_weeks" in data
        assert data["total_weeks"] == 15

        # Timeline data: per-week breakdown
        assert "weeks" in data
        assert len(data["weeks"]) == 15

        # Verify each week has the expected fields
        week1 = data["weeks"][0]
        assert "week_number" in week1
        assert "start_date" in week1
        assert "is_break" in week1
        assert "hours_required" in week1
        assert "hours_available" in week1
        assert "over_capacity" in week1
        assert "collision" in week1
        assert "deliverables_due" in week1
        assert "prep_hours_by_course" in week1

        # Critical weeks and collision weeks should be lists
        assert isinstance(data["critical_weeks"], list)
        assert isinstance(data["collision_weeks"], list)

        # Verdict should be the AI narrative
        assert data["verdict"] == "This semester is tight but manageable."

        # Recovery floor should be a boolean
        assert isinstance(data["recovery_floor_breached"], bool)

    @patch("backend.main.analyze_capacity")
    @patch("backend.main.generate_suggestions")
    def test_suggest_for_over_capacity_weeks(
        self,
        mock_suggest,
        mock_narrative,
        client,
        mock_extraction_response,
        commitments,
        mock_suggestion_response,
    ):
        """Step 5: POST /api/suggest with analysis result returns actionable suggestions."""
        mock_narrative.return_value = "Tight schedule detected."
        mock_suggest.return_value = mock_suggestion_response

        # First run analysis to get a real result (capacity logic is deterministic)
        course_input = {
            "course_code": mock_extraction_response.course_code,
            "course_name": mock_extraction_response.course_name,
            "deliverables": [d.model_dump() for d in mock_extraction_response.deliverables],
        }

        analysis_payload = {
            "courses": [course_input],
            "commitments": [c.model_dump() for c in commitments],
            "break_weeks": [],
            "semester_start": "2025-09-08",
            "semester_end": "2025-12-22",
        }

        analysis_response = client.post("/api/analyze", json=analysis_payload)
        assert analysis_response.status_code == 200
        analysis_data = analysis_response.json()

        # Now request suggestions
        suggest_payload = {
            "analysis_result": analysis_data,
            "commitments": [c.model_dump() for c in commitments],
        }

        response = client.post("/api/suggest", json=suggest_payload)

        assert response.status_code == 200
        data = response.json()

        # Verify suggestion structure
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)
        assert len(data["suggestions"]) == 2

        s1 = data["suggestions"][0]
        assert "description" in s1
        assert "target_commitment" in s1
        assert "action" in s1
        assert s1["action"] in ("reduce", "reschedule", "redistribute")
        assert "detail" in s1
        assert "affected_weeks" in s1
        assert isinstance(s1["affected_weeks"], list)

        # Locked acknowledgment
        assert "locked_acknowledgment" in data
        assert "Part-time job" in data["locked_acknowledgment"]

    @patch("backend.main.extract_syllabus")
    @patch("backend.main.analyze_capacity")
    @patch("backend.main.generate_suggestions")
    def test_full_flow_end_to_end(
        self,
        mock_suggest,
        mock_narrative,
        mock_extract,
        client,
        sample_syllabus_text,
        mock_extraction_response,
        commitments,
        mock_suggestion_response,
    ):
        """Complete flow: extract → analyze → suggest, chained sequentially."""
        mock_extract.return_value = mock_extraction_response
        mock_narrative.return_value = "Feasibility: tight. Two over-capacity weeks detected."
        mock_suggest.return_value = mock_suggestion_response

        # --- Step 1: Extract ---
        extract_resp = client.post(
            "/api/extract",
            json={"course_text": sample_syllabus_text, "file_name": "cs101.txt"},
        )
        assert extract_resp.status_code == 200
        extraction = extract_resp.json()
        assert extraction["status"] == "success"
        assert len(extraction["deliverables"]) > 0

        # --- Step 2: Build analysis input from extraction output + commitments ---
        course_input = {
            "course_code": extraction["course_code"],
            "course_name": extraction["course_name"],
            "deliverables": extraction["deliverables"],
        }

        analysis_payload = {
            "courses": [course_input],
            "commitments": [c.model_dump() for c in commitments],
            "break_weeks": [9],  # Reading week
            "semester_start": "2025-09-08",
            "semester_end": "2025-12-22",
        }

        # --- Step 3: Analyze ---
        analyze_resp = client.post("/api/analyze", json=analysis_payload)
        assert analyze_resp.status_code == 200
        analysis = analyze_resp.json()

        # Verify timeline data
        assert analysis["total_weeks"] == 15
        assert len(analysis["weeks"]) == 15
        assert analysis["weeks"][8]["is_break"] is True  # Week 9 (0-indexed: 8) is break

        # Verify feasibility info present
        assert analysis["feasibility_level"] in ("feasible", "tight", "not_feasible")
        assert isinstance(analysis["feasible"], bool)
        assert "verdict" in analysis

        # --- Step 4: Suggest ---
        suggest_payload = {
            "analysis_result": analysis,
            "commitments": [c.model_dump() for c in commitments],
        }

        suggest_resp = client.post("/api/suggest", json=suggest_payload)
        assert suggest_resp.status_code == 200
        suggestions = suggest_resp.json()

        assert len(suggestions["suggestions"]) >= 1
        assert "locked_acknowledgment" in suggestions
