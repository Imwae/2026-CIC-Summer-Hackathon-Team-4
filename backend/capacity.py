"""Capacity analysis logic for the Semester Capacity Planner.

This module contains deterministic week-building, prep-hour spreading,
collision detection, recovery floor enforcement, and feasibility verdicts.
It does NOT call Bedrock — narrative generation is delegated to bedrock_client.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Set, Union

# Import Pydantic models lazily to avoid circular imports at module level;
# the type hint below uses a string forward reference.
# At runtime the function receives CourseInput instances.
try:
    from backend.models import CourseInput, AnalysisResponse, WeekResult
except ImportError:
    try:
        from models import CourseInput, AnalysisResponse, WeekResult
    except ImportError:
        # Fallback when running the self-test directly
        CourseInput = None  # type: ignore
        AnalysisResponse = None  # type: ignore
        WeekResult = None  # type: ignore

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

TOTAL_HOURS_PER_WEEK = 168
MIN_SLEEP_HOURS_PER_NIGHT = 7
MIN_LEISURE_HOURS_PER_WEEK = 10
SEMESTER_WEEKS = 15


# ---------------------------------------------------------------------------
# Internal Week model
# ---------------------------------------------------------------------------

@dataclass
class Week:
    """Internal representation of a single semester week.

    This is the working object used throughout capacity.py.
    It is converted to WeekResult (the Pydantic API response model) at the
    end of compute_capacity.
    """

    number: int
    start_date: date
    is_break: bool = False
    hours_required: float = 0.0
    hours_available: float = 0.0
    over_capacity: bool = False
    collision: bool = False
    deliverables_due: List[str] = field(default_factory=list)
    prep_hours: Dict[str, float] = field(default_factory=dict)  # keyed by course_code


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def generate_weeks(semester_start: date, num_weeks: int) -> List[Week]:
    """Create a list of Week objects covering the semester.

    Args:
        semester_start: The date of the first day of the semester (Week 1 start).
        num_weeks: Total number of weeks to generate.

    Returns:
        A list of ``num_weeks`` Week objects.  Week 1 starts on
        ``semester_start``, Week 2 starts on ``semester_start + 7 days``,
        and so on.  All boolean flags default to False and all numeric fields
        default to 0.0.
    """
    weeks: List[Week] = []
    for i in range(num_weeks):
        week_number = i + 1  # 1-indexed
        start = semester_start + timedelta(days=i * 7)
        weeks.append(Week(number=week_number, start_date=start))
    return weeks


def spread_prep_hours(
    courses: List,  # List[CourseInput]
    weeks: List[Week],
    break_weeks: Union[List[int], Set[int]],
) -> None:
    """Distribute each deliverable's prep hours across weeks before its due date.

    Mutates ``weeks`` in-place:
    - Adds prep hours to ``week.prep_hours[course_code]`` for each week in the
      prep window (``[due_week - prep_weeks, due_week)``), skipping break weeks
      and weeks outside ``[1, SEMESTER_WEEKS]``.
    - Appends the deliverable label (``"COURSE_CODE: name"``) to
      ``week.deliverables_due`` on the week where the deliverable is due.

    Args:
        courses: List of CourseInput objects, each with a ``course_code`` and
            a ``deliverables`` list of Deliverable objects.
        weeks: List of Week objects as returned by ``generate_weeks``.  The
            list is 0-indexed; week number ``w`` maps to ``weeks[w - 1]``.
        break_weeks: Week numbers (integers) to skip when spreading prep hours.

    Edge cases:
    - If ``estimated_prep_weeks`` is 0 or falsy, all prep hours are assigned
      to the deliverable's due week (no spread, no division by zero).
    - Week numbers outside ``[1, SEMESTER_WEEKS]`` are silently ignored.
    - Break weeks receive no prep hours but are not counted against the spread
      window; the remaining non-break weeks each still receive the same
      ``prep_per_week`` share (no redistribution of skipped hours).
    """
    # Build a lookup dict keyed by week number for O(1) access.
    week_by_number: Dict[int, Week] = {w.number: w for w in weeks}

    break_set: Set[int] = set(break_weeks)

    for course in courses:
        for deliverable in course.deliverables:
            due_week: int = deliverable.week_number
            label: str = f"{course.course_code}: {deliverable.name}"

            # --- Populate deliverables_due on the due week ---
            if due_week in week_by_number:
                due_week_obj = week_by_number[due_week]
                if label not in due_week_obj.deliverables_due:
                    due_week_obj.deliverables_due.append(label)

            # --- Spread prep hours ---
            prep_weeks: int = deliverable.estimated_prep_weeks or 0

            if prep_weeks == 0:
                # Guard: assign all hours to the due week itself, no spread.
                if due_week in week_by_number and due_week not in break_set:
                    week_by_number[due_week].prep_hours.setdefault(course.course_code, 0.0)
                    week_by_number[due_week].prep_hours[course.course_code] += (
                        deliverable.estimated_hours_total
                    )
                continue

            prep_per_week: float = deliverable.estimated_hours_total / prep_weeks
            start_week: int = due_week - prep_weeks

            for w in range(start_week, due_week):
                if w in break_set:
                    continue
                if not (1 <= w <= SEMESTER_WEEKS):
                    continue
                week_by_number[w].prep_hours.setdefault(course.course_code, 0.0)
                week_by_number[w].prep_hours[course.course_code] += prep_per_week


def detect_collisions(courses: List, weeks: List[Week]) -> None:  # List[CourseInput]
    """Flag weeks where deliverables from 2 or more distinct courses are due.

    Mutates ``weeks`` in-place:
    - Sets ``week.collision = True`` when deliverables from 2 or more distinct
      courses are due in the same week.
    - Sets ``week.collision = False`` otherwise (ensures the field is always set).

    Note: This function only updates ``week.collision``.  The ``week.deliverables_due``
    list is populated by ``spread_prep_hours`` and is not modified here.

    Args:
        courses: List of CourseInput objects, each with a ``course_code`` and
            a ``deliverables`` list of Deliverable objects.
        weeks: List of Week objects as returned by ``generate_weeks``.
    """
    for week in weeks:
        courses_with_due: Set[str] = set()
        for course in courses:
            for d in course.deliverables:
                if d.week_number == week.number:
                    courses_with_due.add(course.course_code)
        week.collision = len(courses_with_due) >= 2


def check_recovery_floor(weeks: List[Week], commitments: List) -> bool:
    """Check whether the recovery floor is breached in any non-break week.

    The recovery floor is the absolute minimum hours that must be reserved for
    sleep (7 h/night × 7 = 49 h/week) and leisure (10 h/week).  If any
    non-break week's ``hours_required`` exceeds
    ``TOTAL_HOURS_PER_WEEK - MIN_SLEEP_HOURS_PER_NIGHT * 7 - MIN_LEISURE_HOURS_PER_WEEK``
    (i.e. 168 − 49 − 10 = 109), the schedule is physically infeasible without
    sacrificing health.

    Args:
        weeks: List of Week objects with ``hours_required`` already populated
            (e.g. after ``spread_prep_hours`` has run).
        commitments: Accepted for API consistency but not used in the core
            calculation — the floor is derived from module-level constants.

    Returns:
        ``True`` if any non-break week breaches the recovery floor,
        ``False`` otherwise.
    """
    floor = TOTAL_HOURS_PER_WEEK - MIN_SLEEP_HOURS_PER_NIGHT * 7 - MIN_LEISURE_HOURS_PER_WEEK
    return any(
        week.hours_required > floor
        for week in weeks
        if not week.is_break
    )


def compute_available_hours(commitments: List) -> float:  # List[Commitment]
    """Calculate the weekly hours available for coursework prep.

    Formula::

        available = TOTAL_HOURS_PER_WEEK - sleep_hours_per_week - locked_hours

    Where:
    - ``sleep_hours_per_week`` = sleep commitment's ``hours_per_week`` × 7
      (sleep is stored as hours *per night*; multiply to get weekly total).
    - ``locked_hours`` = sum of ``hours_per_week`` for all locked commitments
      whose category is **not** ``'sleep'``.

    If no sleep commitment is present in the list the function defaults to
    ``MIN_SLEEP_HOURS_PER_NIGHT * 7`` (49 h/week).

    Args:
        commitments: List of Commitment-like objects, each with ``category``,
            ``hours_per_week``, and ``locked`` attributes.

    Returns:
        A float representing the weekly hours left over after sleep and locked
        commitments are accounted for.  The value may be negative if locked
        commitments exceed 168 h (caller is responsible for interpreting that).
    """
    # --- Find sleep commitment ---
    sleep_commitment = next(
        (c for c in commitments if c.category == "sleep"), None
    )
    if sleep_commitment is not None:
        sleep_hours_per_week = sleep_commitment.hours_per_week * 7
    else:
        sleep_hours_per_week = MIN_SLEEP_HOURS_PER_NIGHT * 7  # default: 49 h/week

    # --- Sum locked non-sleep commitments ---
    locked_hours = sum(
        c.hours_per_week
        for c in commitments
        if c.locked and c.category != "sleep"
    )

    return TOTAL_HOURS_PER_WEEK - sleep_hours_per_week - locked_hours


def compute_capacity(
    courses: List,
    commitments: List,
    break_weeks: Union[List[int], Set[int]],
    semester_start: date,
    semester_end: date,
):
    """Orchestrate a full capacity analysis and return an AnalysisResponse.

    This is the top-level entry point that coordinates all sub-functions:
    1. Build week timeline from semester_start/semester_end
    2. Mark break weeks
    3. Spread prep hours across weeks
    4. Compute per-week available/required hours
    5. Detect collisions
    6. Check recovery floor
    7. Determine feasibility verdict
    8. Convert internal Week objects to WeekResult models

    Args:
        courses: List of CourseInput objects.
        commitments: List of Commitment objects.
        break_weeks: Week numbers (ints) designated as break weeks.
        semester_start: First day of the semester.
        semester_end: Last day of the semester (used to calculate num_weeks).

    Returns:
        An AnalysisResponse Pydantic model with all fields populated.
        The ``verdict`` field is left as an empty string (filled later by
        bedrock_client narrative generation).
    """
    # 1. Calculate number of weeks from date range
    num_weeks = max(1, (semester_end - semester_start).days // 7)

    # 2. Build week timeline
    weeks = generate_weeks(semester_start, num_weeks)

    # 3. Mark break weeks
    break_set: Set[int] = set(break_weeks)
    for week in weeks:
        if week.number in break_set:
            week.is_break = True

    # 4. Spread deliverable prep hours across weeks
    spread_prep_hours(courses, weeks, break_weeks)

    # 5. Compute available hours (before leisure deduction)
    available = compute_available_hours(commitments)

    # 6. Find leisure commitment hours (default to MIN_LEISURE_HOURS_PER_WEEK)
    leisure_commitment = next(
        (c for c in commitments if c.category == "leisure"), None
    )
    leisure_hours = (
        leisure_commitment.hours_per_week if leisure_commitment is not None
        else MIN_LEISURE_HOURS_PER_WEEK
    )

    # 7. Per-week analysis: set hours_required, hours_available, over_capacity
    for week in weeks:
        if week.is_break:
            continue
        week.hours_required = sum(week.prep_hours.values())
        week.hours_available = available - leisure_hours
        week.over_capacity = week.hours_required > week.hours_available

    # 8. Collision detection
    detect_collisions(courses, weeks)

    # 9. Recovery floor check
    recovery_floor_breached = check_recovery_floor(weeks, commitments)

    # 10. Feasibility verdict
    over_capacity_count = sum(1 for w in weeks if w.over_capacity)
    if recovery_floor_breached or over_capacity_count > 3:
        feasibility_level = "not_feasible"
    elif over_capacity_count > 0:
        feasibility_level = "tight"
    else:
        feasibility_level = "feasible"

    # 11. Build result lists
    critical_weeks = [w.number for w in weeks if w.over_capacity]
    collision_weeks = [w.number for w in weeks if w.collision]

    # 12. Convert internal Week objects to WeekResult Pydantic models
    week_results = [
        WeekResult(
            week_number=w.number,
            start_date=w.start_date.isoformat(),
            is_break=w.is_break,
            hours_required=w.hours_required,
            hours_available=w.hours_available,
            over_capacity=w.over_capacity,
            collision=w.collision,
            deliverables_due=w.deliverables_due,
            prep_hours_by_course=dict(w.prep_hours),
        )
        for w in weeks
    ]

    # 13. Return AnalysisResponse
    return AnalysisResponse(
        feasible=(feasibility_level == "feasible"),
        feasibility_level=feasibility_level,
        total_weeks=num_weeks,
        weeks=week_results,
        critical_weeks=critical_weeks,
        collision_weeks=collision_weeks,
        recovery_floor_breached=recovery_floor_breached,
        verdict="",
    )


# ---------------------------------------------------------------------------
# Quick self-test (python backend/capacity.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from datetime import date as _date

    # ------------------------------------------------------------------
    # Test generate_weeks
    # ------------------------------------------------------------------
    test_start = _date(2025, 9, 8)
    weeks = generate_weeks(test_start, SEMESTER_WEEKS)

    assert len(weeks) == 15, f"Expected 15 weeks, got {len(weeks)}"
    assert weeks[0].number == 1
    assert weeks[0].start_date == _date(2025, 9, 8)
    assert weeks[1].number == 2
    assert weeks[1].start_date == _date(2025, 9, 15)
    assert weeks[14].number == 15
    assert weeks[14].start_date == _date(2025, 12, 15)

    for w in weeks:
        assert w.is_break is False
        assert w.over_capacity is False
        assert w.collision is False
        assert w.hours_required == 0.0
        assert w.hours_available == 0.0
        assert w.deliverables_due == []
        assert w.prep_hours == {}

    print("generate_weeks: all assertions passed.")
    for w in weeks:
        print(f"  Week {w.number:2d}: {w.start_date}")

    # ------------------------------------------------------------------
    # Minimal stub types so the self-test doesn't require models.py
    # ------------------------------------------------------------------
    class _Deliverable:
        def __init__(self, name, week_number, estimated_prep_weeks, estimated_hours_total):
            self.name = name
            self.week_number = week_number
            self.estimated_prep_weeks = estimated_prep_weeks
            self.estimated_hours_total = estimated_hours_total

    class _Course:
        def __init__(self, course_code, deliverables):
            self.course_code = course_code
            self.deliverables = deliverables

    # ------------------------------------------------------------------
    # Test 1: Basic spread — 1 course, 1 deliverable, no break weeks
    #
    # Deliverable due in week 8, 12 hours total, 3 prep weeks.
    # Expected: weeks 5, 6, 7 each get 4.0 h for "CS101".
    # Week 8 gets "CS101: Midterm" in deliverables_due.
    # ------------------------------------------------------------------
    weeks1 = generate_weeks(test_start, SEMESTER_WEEKS)
    d1 = _Deliverable("Midterm", week_number=8, estimated_prep_weeks=3, estimated_hours_total=12.0)
    c1 = _Course("CS101", [d1])

    spread_prep_hours([c1], weeks1, break_weeks=[])

    for wn in [5, 6, 7]:
        actual = weeks1[wn - 1].prep_hours.get("CS101", 0.0)
        assert actual == 4.0, f"Week {wn}: expected 4.0 h, got {actual}"
    # Due week should NOT have prep hours (only deliverables_due)
    assert weeks1[7].prep_hours.get("CS101", 0.0) == 0.0, "Week 8 should have no prep hours"
    assert "CS101: Midterm" in weeks1[7].deliverables_due, "Week 8 should list the deliverable"
    # Non-prep weeks should be untouched
    for wn in list(range(1, 5)) + list(range(9, 16)):
        assert weeks1[wn - 1].prep_hours == {}, f"Week {wn} should have no prep hours"

    print("\nTest 1 (basic spread): PASSED")

    # ------------------------------------------------------------------
    # Test 2: Break week — one prep week is a break
    #
    # Same deliverable (due week 8, 12 h, 3 prep weeks → windows weeks 5-7).
    # Week 6 is a break week.
    # Implementation behaviour: break weeks are SKIPPED entirely — they
    # receive 0 h.  The remaining non-break weeks (5 and 7) still each
    # get prep_per_week = 4.0 h (no redistribution of skipped hours).
    # ------------------------------------------------------------------
    weeks2 = generate_weeks(test_start, SEMESTER_WEEKS)
    spread_prep_hours([c1], weeks2, break_weeks=[6])

    assert weeks2[4].prep_hours.get("CS101", 0.0) == 4.0, "Week 5 should still have 4.0 h"
    assert weeks2[5].prep_hours.get("CS101", 0.0) == 0.0, "Week 6 (break) should have 0 h"
    assert weeks2[6].prep_hours.get("CS101", 0.0) == 4.0, "Week 7 should still have 4.0 h"
    assert "CS101: Midterm" in weeks2[7].deliverables_due

    print("Test 2 (break week): PASSED")
    print("  Behaviour: break weeks are skipped; remaining non-break prep weeks")
    print("  each keep their original share (no redistribution of skipped hours).")

    # ------------------------------------------------------------------
    # Test 3: Zero prep weeks guard — must not raise ZeroDivisionError
    #
    # When estimated_prep_weeks=0 all hours are assigned to the due week.
    # ------------------------------------------------------------------
    weeks3 = generate_weeks(test_start, SEMESTER_WEEKS)
    d3 = _Deliverable("Quiz", week_number=5, estimated_prep_weeks=0, estimated_hours_total=6.0)
    c3 = _Course("ENG200", [d3])

    spread_prep_hours([c3], weeks3, break_weeks=[])

    # Due week gets all hours
    assert weeks3[4].prep_hours.get("ENG200", 0.0) == 6.0, (
        "Zero prep weeks: all hours should land on the due week"
    )
    assert "ENG200: Quiz" in weeks3[4].deliverables_due
    # No other week should be touched
    for wn in list(range(1, 5)) + list(range(6, 16)):
        assert weeks3[wn - 1].prep_hours.get("ENG200", 0.0) == 0.0, (
            f"Week {wn} should have no prep hours (zero-prep-weeks guard)"
        )

    print("Test 3 (zero prep weeks guard): PASSED")

    print("\nAll spread_prep_hours assertions passed.")

    # ------------------------------------------------------------------
    # Test compute_available_hours
    # ------------------------------------------------------------------
    class _Commitment:
        def __init__(self, category, hours_per_week, locked):
            self.category = category
            self.hours_per_week = hours_per_week
            self.locked = locked

    # Test A: Normal case — 8 h sleep/night, 20 h work (locked), 5 h commute (locked)
    # available = 168 - (8*7) - (20 + 5) = 168 - 56 - 25 = 87.0
    comms_a = [
        _Commitment("sleep", 8.0, False),
        _Commitment("work", 20.0, True),
        _Commitment("commute", 5.0, True),
        _Commitment("leisure", 10.0, False),  # not locked → doesn't count
    ]
    result_a = compute_available_hours(comms_a)
    assert result_a == 87.0, f"Test A: expected 87.0, got {result_a}"
    print("\nTest A (normal case): PASSED  →", result_a)

    # Test B: No sleep commitment → defaults to MIN_SLEEP_HOURS_PER_NIGHT * 7 = 49
    # available = 168 - 49 - 20 = 99.0
    comms_b = [
        _Commitment("work", 20.0, True),
    ]
    result_b = compute_available_hours(comms_b)
    assert result_b == 99.0, f"Test B: expected 99.0, got {result_b}"
    print("Test B (no sleep commitment): PASSED  →", result_b)

    # Test C: Unlocked work doesn't reduce available hours
    # available = 168 - (7*7) - 0 = 168 - 49 - 0 = 119.0
    comms_c = [
        _Commitment("sleep", 7.0, False),
        _Commitment("work", 30.0, False),  # unlocked → ignored
    ]
    result_c = compute_available_hours(comms_c)
    assert result_c == 119.0, f"Test C: expected 119.0, got {result_c}"
    print("Test C (unlocked work ignored): PASSED  →", result_c)

    # Test D: Sleep is locked but must still not be double-counted in locked_hours
    # available = 168 - (8*7) - 0 = 112.0  (sleep locked flag ignored for locked_hours)
    comms_d = [
        _Commitment("sleep", 8.0, True),  # locked sleep should NOT count in locked_hours
    ]
    result_d = compute_available_hours(comms_d)
    assert result_d == 112.0, f"Test D: expected 112.0, got {result_d}"
    print("Test D (locked sleep not double-counted): PASSED  →", result_d)

    # Test E: Empty commitments list → default sleep, no locked hours
    # available = 168 - 49 - 0 = 119.0
    result_e = compute_available_hours([])
    assert result_e == 119.0, f"Test E: expected 119.0, got {result_e}"
    print("Test E (empty commitments): PASSED  →", result_e)

    print("\nAll compute_available_hours assertions passed.")

    # ------------------------------------------------------------------
    # Test detect_collisions
    # ------------------------------------------------------------------

    # Test DC-1: Two courses with deliverables in the same week → collision = True
    weeks_dc1 = generate_weeks(test_start, SEMESTER_WEEKS)
    d_cs = _Deliverable("Midterm", week_number=7, estimated_prep_weeks=2, estimated_hours_total=10.0)
    d_eng = _Deliverable("Essay", week_number=7, estimated_prep_weeks=2, estimated_hours_total=8.0)
    c_cs = _Course("CS101", [d_cs])
    c_eng = _Course("ENG200", [d_eng])

    detect_collisions([c_cs, c_eng], weeks_dc1)

    assert weeks_dc1[6].collision is True, "Week 7 should be a collision (2 courses due)"
    for wn in list(range(1, 7)) + list(range(8, 16)):
        assert weeks_dc1[wn - 1].collision is False, f"Week {wn} should NOT be a collision"
    print("\nTest DC-1 (two courses same week): PASSED")

    # Test DC-2: Two deliverables from the SAME course in the same week → no collision
    weeks_dc2 = generate_weeks(test_start, SEMESTER_WEEKS)
    d_q1 = _Deliverable("Quiz 1", week_number=5, estimated_prep_weeks=1, estimated_hours_total=4.0)
    d_q2 = _Deliverable("Quiz 2", week_number=5, estimated_prep_weeks=1, estimated_hours_total=4.0)
    c_same = _Course("CS101", [d_q1, d_q2])

    detect_collisions([c_same], weeks_dc2)

    assert weeks_dc2[4].collision is False, "Week 5 should NOT be a collision (same course)"
    print("Test DC-2 (two deliverables from same course): PASSED")

    # Test DC-3: No deliverables at all → no collisions anywhere
    weeks_dc3 = generate_weeks(test_start, SEMESTER_WEEKS)
    detect_collisions([], weeks_dc3)
    for w in weeks_dc3:
        assert w.collision is False, f"Week {w.number} should NOT be a collision (no courses)"
    print("Test DC-3 (no courses): PASSED")

    # Test DC-4: Three courses all due in same week → still collision
    weeks_dc4 = generate_weeks(test_start, SEMESTER_WEEKS)
    c4a = _Course("CS101", [_Deliverable("A", week_number=10, estimated_prep_weeks=1, estimated_hours_total=5.0)])
    c4b = _Course("ENG200", [_Deliverable("B", week_number=10, estimated_prep_weeks=1, estimated_hours_total=5.0)])
    c4c = _Course("MATH300", [_Deliverable("C", week_number=10, estimated_prep_weeks=1, estimated_hours_total=5.0)])

    detect_collisions([c4a, c4b, c4c], weeks_dc4)

    assert weeks_dc4[9].collision is True, "Week 10 should be a collision (3 courses due)"
    print("Test DC-4 (three courses same week): PASSED")

    print("\nAll detect_collisions assertions passed.")


    # ------------------------------------------------------------------
    # Test check_recovery_floor
    # ------------------------------------------------------------------

    # Floor = 168 - 49 - 10 = 109

    # Test RF-1: All weeks under floor → returns False
    weeks_rf1 = generate_weeks(test_start, SEMESTER_WEEKS)
    for w in weeks_rf1:
        w.hours_required = 100.0  # Under 109
    assert check_recovery_floor(weeks_rf1, []) is False, "RF-1: all under floor → False"
    print("\nTest RF-1 (all weeks under floor): PASSED")

    # Test RF-2: One week exactly at the floor (109) → not breached (> not >=)
    weeks_rf2 = generate_weeks(test_start, SEMESTER_WEEKS)
    for w in weeks_rf2:
        w.hours_required = 50.0
    weeks_rf2[4].hours_required = 109.0  # Exactly at floor
    assert check_recovery_floor(weeks_rf2, []) is False, "RF-2: exactly at floor → False"
    print("Test RF-2 (exactly at floor boundary): PASSED")

    # Test RF-3: One week over the floor → returns True
    weeks_rf3 = generate_weeks(test_start, SEMESTER_WEEKS)
    for w in weeks_rf3:
        w.hours_required = 50.0
    weeks_rf3[7].hours_required = 110.0  # Over 109
    assert check_recovery_floor(weeks_rf3, []) is True, "RF-3: one week over floor → True"
    print("Test RF-3 (one week over floor): PASSED")

    # Test RF-4: Break week over floor is excluded → returns False
    weeks_rf4 = generate_weeks(test_start, SEMESTER_WEEKS)
    for w in weeks_rf4:
        w.hours_required = 50.0
    weeks_rf4[5].is_break = True
    weeks_rf4[5].hours_required = 150.0  # Over floor but it's a break week
    assert check_recovery_floor(weeks_rf4, []) is False, "RF-4: break week excluded → False"
    print("Test RF-4 (break week excluded): PASSED")

    # Test RF-5: Non-break week over floor with break weeks present → returns True
    weeks_rf5 = generate_weeks(test_start, SEMESTER_WEEKS)
    for w in weeks_rf5:
        w.hours_required = 50.0
    weeks_rf5[5].is_break = True
    weeks_rf5[5].hours_required = 150.0  # break → ignored
    weeks_rf5[9].hours_required = 120.0  # non-break → triggers breach
    assert check_recovery_floor(weeks_rf5, []) is True, "RF-5: non-break week over floor → True"
    print("Test RF-5 (non-break over floor with breaks present): PASSED")

    # Test RF-6: Empty weeks list → returns False (no weeks to breach)
    assert check_recovery_floor([], []) is False, "RF-6: empty weeks → False"
    print("Test RF-6 (empty weeks list): PASSED")

    print("\nAll check_recovery_floor assertions passed.")

    # ------------------------------------------------------------------
    # Test compute_capacity
    # ------------------------------------------------------------------

    # Need to import or mock the Pydantic models for the orchestrator tests
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from models import AnalysisResponse as _AnalysisResponse, WeekResult as _WeekResult, Commitment as _CommitmentModel, CourseInput as _CourseInputModel, Deliverable as _DeliverableModel

    # Test CC-1: Basic feasible scenario — low prep, no collisions, no floor breach
    sem_start = _date(2025, 9, 8)
    sem_end = _date(2025, 12, 22)  # ~15 weeks

    comms_cc1 = [
        _CommitmentModel(name="Sleep", category="sleep", hours_per_week=7.0, locked=False),
        _CommitmentModel(name="Work", category="work", hours_per_week=20.0, locked=True),
        _CommitmentModel(name="Leisure", category="leisure", hours_per_week=10.0, locked=False),
    ]
    # One course, one deliverable: 6 h total, 2 prep weeks before week 5
    courses_cc1 = [
        _CourseInputModel(
            course_code="CS101",
            course_name="Intro to CS",
            deliverables=[
                _DeliverableModel(
                    name="Quiz",
                    type="exam",
                    week_number=5,
                    estimated_prep_weeks=2,
                    estimated_hours_total=6.0,
                )
            ],
        )
    ]

    result_cc1 = compute_capacity(courses_cc1, comms_cc1, [], sem_start, sem_end)
    assert result_cc1.feasibility_level == "feasible", f"CC-1: expected feasible, got {result_cc1.feasibility_level}"
    assert result_cc1.feasible is True
    assert result_cc1.total_weeks == 15
    assert result_cc1.recovery_floor_breached is False
    assert result_cc1.critical_weeks == []
    assert result_cc1.verdict == ""
    assert len(result_cc1.weeks) == 15
    print("\nTest CC-1 (basic feasible): PASSED")

    # Test CC-2: Break weeks are handled correctly
    result_cc2 = compute_capacity(courses_cc1, comms_cc1, [3, 4], sem_start, sem_end)
    # Week 3 and 4 should be breaks
    assert result_cc2.weeks[2].is_break is True, "CC-2: Week 3 should be break"
    assert result_cc2.weeks[3].is_break is True, "CC-2: Week 4 should be break"
    assert result_cc2.weeks[2].hours_required == 0.0, "CC-2: Break week should have 0 hours_required"
    assert result_cc2.weeks[2].over_capacity is False, "CC-2: Break week should not be over_capacity"
    print("Test CC-2 (break weeks): PASSED")

    # Test CC-3: Collision detection through orchestrator
    courses_cc3 = [
        _CourseInputModel(
            course_code="CS101",
            course_name="Intro to CS",
            deliverables=[
                _DeliverableModel(name="Midterm", type="exam", week_number=7, estimated_prep_weeks=2, estimated_hours_total=10.0),
            ],
        ),
        _CourseInputModel(
            course_code="ENG200",
            course_name="English Lit",
            deliverables=[
                _DeliverableModel(name="Essay", type="essay", week_number=7, estimated_prep_weeks=2, estimated_hours_total=8.0),
            ],
        ),
    ]
    result_cc3 = compute_capacity(courses_cc3, comms_cc1, [], sem_start, sem_end)
    assert 7 in result_cc3.collision_weeks, "CC-3: Week 7 should be a collision week"
    print("Test CC-3 (collision detection via orchestrator): PASSED")

    # Test CC-4: Feasibility levels — "tight" (1-3 over-capacity weeks)
    # Create a scenario where 2 weeks are over-capacity
    # available - leisure = 168 - 49 - 20 - 10 = 89 h
    # We need deliverables requiring >89 h in exactly 2 weeks
    courses_cc4 = [
        _CourseInputModel(
            course_code="CS500",
            course_name="Advanced CS",
            deliverables=[
                _DeliverableModel(name="Project A", type="project", week_number=4, estimated_prep_weeks=1, estimated_hours_total=100.0),
                _DeliverableModel(name="Project B", type="project", week_number=8, estimated_prep_weeks=1, estimated_hours_total=100.0),
            ],
        ),
    ]
    result_cc4 = compute_capacity(courses_cc4, comms_cc1, [], sem_start, sem_end)
    assert result_cc4.feasibility_level == "tight", f"CC-4: expected tight, got {result_cc4.feasibility_level}"
    assert result_cc4.feasible is False
    assert len(result_cc4.critical_weeks) >= 1
    print("Test CC-4 (tight feasibility): PASSED")

    # Test CC-5: Feasibility levels — "not_feasible" (>3 over-capacity weeks)
    courses_cc5 = [
        _CourseInputModel(
            course_code="CS500",
            course_name="Advanced CS",
            deliverables=[
                _DeliverableModel(name="P1", type="project", week_number=3, estimated_prep_weeks=1, estimated_hours_total=100.0),
                _DeliverableModel(name="P2", type="project", week_number=5, estimated_prep_weeks=1, estimated_hours_total=100.0),
                _DeliverableModel(name="P3", type="project", week_number=7, estimated_prep_weeks=1, estimated_hours_total=100.0),
                _DeliverableModel(name="P4", type="project", week_number=9, estimated_prep_weeks=1, estimated_hours_total=100.0),
            ],
        ),
    ]
    result_cc5 = compute_capacity(courses_cc5, comms_cc1, [], sem_start, sem_end)
    assert result_cc5.feasibility_level == "not_feasible", f"CC-5: expected not_feasible, got {result_cc5.feasibility_level}"
    assert result_cc5.feasible is False
    print("Test CC-5 (not_feasible — >3 over-capacity): PASSED")

    # Test CC-6: not_feasible due to recovery floor breach
    # Need hours_required > 109 in a week
    # Floor = 168 - 49 - 10 = 109. With 1 prep week of 110 h, the week should breach.
    courses_cc6 = [
        _CourseInputModel(
            course_code="CS999",
            course_name="Impossible Course",
            deliverables=[
                _DeliverableModel(name="Monster", type="project", week_number=6, estimated_prep_weeks=1, estimated_hours_total=110.0),
            ],
        ),
    ]
    result_cc6 = compute_capacity(courses_cc6, comms_cc1, [], sem_start, sem_end)
    assert result_cc6.recovery_floor_breached is True, "CC-6: recovery floor should be breached"
    assert result_cc6.feasibility_level == "not_feasible", f"CC-6: expected not_feasible, got {result_cc6.feasibility_level}"
    print("Test CC-6 (not_feasible — recovery floor breached): PASSED")

    # Test CC-7: semester_end calculation of num_weeks
    short_end = _date(2025, 9, 29)  # 3 weeks from start
    result_cc7 = compute_capacity([], comms_cc1, [], sem_start, short_end)
    assert result_cc7.total_weeks == 3, f"CC-7: expected 3 weeks, got {result_cc7.total_weeks}"
    assert len(result_cc7.weeks) == 3
    print("Test CC-7 (num_weeks from semester_end): PASSED")

    print("\nAll compute_capacity assertions passed.")
