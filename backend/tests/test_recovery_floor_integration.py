"""Integration tests for the recovery floor and not_feasible verdict logic.

These tests call compute_capacity() directly with crafted inputs to verify:
1. Recovery floor breach → feasibility_level == "not_feasible"
2. >3 over-capacity weeks (without floor breach) → feasibility_level == "not_feasible"

No Bedrock/AI calls are involved — this tests the deterministic capacity logic only.
"""

from datetime import date

import pytest

from backend.models import AnalysisResponse, Commitment, CourseInput, Deliverable, WeekResult

# Fix capacity.py's fallback imports — when running from project root via pytest,
# the try/except ImportError in capacity.py fails to resolve models and sets them to None.
import backend.capacity as _capacity
_capacity.WeekResult = WeekResult
_capacity.AnalysisResponse = AnalysisResponse
_capacity.CourseInput = CourseInput

from backend.capacity import compute_capacity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SEMESTER_START = date(2025, 9, 8)
SEMESTER_END = date(2025, 12, 22)  # 15 weeks


@pytest.fixture
def default_commitments():
    """Minimal commitments: 7h sleep/night, no locked hours, 10h leisure."""
    return [
        Commitment(name="Sleep", category="sleep", hours_per_week=7.0, locked=False),
        Commitment(name="Leisure", category="leisure", hours_per_week=10.0, locked=False),
    ]


# ---------------------------------------------------------------------------
# Test 1: Recovery floor breached — single week exceeds 109 hours
# ---------------------------------------------------------------------------


class TestRecoveryFloorBreach:
    """Verify that breaching the recovery floor triggers not_feasible."""

    def test_single_week_exceeds_floor(self, default_commitments):
        """A deliverable with 120h in 1 prep week breaches the 109h floor."""
        courses = [
            CourseInput(
                course_code="CS999",
                course_name="Impossible Course",
                deliverables=[
                    Deliverable(
                        name="Monster Project",
                        type="project",
                        week_number=6,
                        estimated_prep_weeks=1,
                        estimated_hours_total=120.0,
                    )
                ],
            )
        ]

        result = compute_capacity(
            courses=courses,
            commitments=default_commitments,
            break_weeks=[],
            semester_start=SEMESTER_START,
            semester_end=SEMESTER_END,
        )

        assert result.feasibility_level == "not_feasible"
        assert result.recovery_floor_breached is True
        assert result.feasible is False

    def test_exactly_at_floor_not_breached(self, default_commitments):
        """109h exactly does NOT breach the floor (uses > not >=)."""
        courses = [
            CourseInput(
                course_code="CS500",
                course_name="Edge Case Course",
                deliverables=[
                    Deliverable(
                        name="Big Assignment",
                        type="project",
                        week_number=6,
                        estimated_prep_weeks=1,
                        estimated_hours_total=109.0,
                    )
                ],
            )
        ]

        result = compute_capacity(
            courses=courses,
            commitments=default_commitments,
            break_weeks=[],
            semester_start=SEMESTER_START,
            semester_end=SEMESTER_END,
        )

        # 109 is exactly the floor — not breached (> not >=)
        assert result.recovery_floor_breached is False

    def test_floor_breach_with_multiple_courses_stacking(self, default_commitments):
        """Multiple deliverables stacking in the same week breach the floor."""
        # Two courses each put 60h into week 5 (prep_weeks=1, due week 6)
        # Total in week 5 = 120h > 109h floor
        courses = [
            CourseInput(
                course_code="CS101",
                course_name="Course A",
                deliverables=[
                    Deliverable(
                        name="Midterm",
                        type="exam",
                        week_number=6,
                        estimated_prep_weeks=1,
                        estimated_hours_total=60.0,
                    )
                ],
            ),
            CourseInput(
                course_code="ENG200",
                course_name="Course B",
                deliverables=[
                    Deliverable(
                        name="Essay",
                        type="essay",
                        week_number=6,
                        estimated_prep_weeks=1,
                        estimated_hours_total=60.0,
                    )
                ],
            ),
        ]

        result = compute_capacity(
            courses=courses,
            commitments=default_commitments,
            break_weeks=[],
            semester_start=SEMESTER_START,
            semester_end=SEMESTER_END,
        )

        assert result.feasibility_level == "not_feasible"
        assert result.recovery_floor_breached is True
        assert result.feasible is False


# ---------------------------------------------------------------------------
# Test 2: >3 over-capacity weeks without floor breach → not_feasible
# ---------------------------------------------------------------------------


class TestOverCapacityCountNotFeasible:
    """Verify that >3 over-capacity weeks triggers not_feasible even without
    breaching the recovery floor."""

    def test_four_over_capacity_weeks(self):
        """4 weeks over-capacity (but each below 109h floor) → not_feasible."""
        # With 7h sleep + 20h locked work + 10h leisure:
        # available - leisure = 168 - 49 - 20 - 10 = 89h
        # Each deliverable puts 95h in a single week (>89 but <109)
        commitments = [
            Commitment(name="Sleep", category="sleep", hours_per_week=7.0, locked=False),
            Commitment(name="Work", category="work", hours_per_week=20.0, locked=True),
            Commitment(name="Leisure", category="leisure", hours_per_week=10.0, locked=False),
        ]

        courses = [
            CourseInput(
                course_code="CS500",
                course_name="Heavy Course",
                deliverables=[
                    Deliverable(
                        name=f"Project {i}",
                        type="project",
                        week_number=wk,
                        estimated_prep_weeks=1,
                        estimated_hours_total=95.0,
                    )
                    for i, wk in enumerate([4, 7, 10, 13], start=1)
                ],
            )
        ]

        result = compute_capacity(
            courses=courses,
            commitments=commitments,
            break_weeks=[],
            semester_start=SEMESTER_START,
            semester_end=SEMESTER_END,
        )

        assert result.feasibility_level == "not_feasible"
        assert result.recovery_floor_breached is False  # Each week < 109
        assert result.feasible is False
        assert len(result.critical_weeks) >= 4

    def test_three_over_capacity_weeks_is_tight_not_infeasible(self):
        """Exactly 3 over-capacity weeks → 'tight', NOT 'not_feasible'."""
        commitments = [
            Commitment(name="Sleep", category="sleep", hours_per_week=7.0, locked=False),
            Commitment(name="Work", category="work", hours_per_week=20.0, locked=True),
            Commitment(name="Leisure", category="leisure", hours_per_week=10.0, locked=False),
        ]

        courses = [
            CourseInput(
                course_code="CS500",
                course_name="Heavy Course",
                deliverables=[
                    Deliverable(
                        name=f"Project {i}",
                        type="project",
                        week_number=wk,
                        estimated_prep_weeks=1,
                        estimated_hours_total=95.0,
                    )
                    for i, wk in enumerate([4, 7, 10], start=1)
                ],
            )
        ]

        result = compute_capacity(
            courses=courses,
            commitments=commitments,
            break_weeks=[],
            semester_start=SEMESTER_START,
            semester_end=SEMESTER_END,
        )

        assert result.feasibility_level == "tight"
        assert result.recovery_floor_breached is False
        assert result.feasible is False  # tight is still not "feasible"
        assert len(result.critical_weeks) == 3

    def test_five_over_capacity_weeks(self):
        """5 over-capacity weeks clearly triggers not_feasible."""
        commitments = [
            Commitment(name="Sleep", category="sleep", hours_per_week=7.0, locked=False),
            Commitment(name="Work", category="work", hours_per_week=20.0, locked=True),
            Commitment(name="Leisure", category="leisure", hours_per_week=10.0, locked=False),
        ]

        courses = [
            CourseInput(
                course_code="CS500",
                course_name="Heavy Course",
                deliverables=[
                    Deliverable(
                        name=f"Project {i}",
                        type="project",
                        week_number=wk,
                        estimated_prep_weeks=1,
                        estimated_hours_total=95.0,
                    )
                    for i, wk in enumerate([3, 5, 7, 9, 11], start=1)
                ],
            )
        ]

        result = compute_capacity(
            courses=courses,
            commitments=commitments,
            break_weeks=[],
            semester_start=SEMESTER_START,
            semester_end=SEMESTER_END,
        )

        assert result.feasibility_level == "not_feasible"
        assert result.recovery_floor_breached is False
        assert result.feasible is False
        assert len(result.critical_weeks) >= 5
