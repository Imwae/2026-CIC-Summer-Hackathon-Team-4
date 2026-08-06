"""Prompt templates for the Semester Capacity Planner AI interactions."""

EXTRACTION_PROMPT = """\
Role: You are a syllabus parser. Extract all graded deliverables from the \
following course syllabus text.

For each deliverable, provide:
- name: the deliverable title
- type: one of [exam, essay, project, presentation, lab, other]
- due_date: in YYYY-MM-DD format, or "Week N" if only a relative date is given
- weight_percent: percentage weight if stated, null otherwise
- estimated_prep_weeks: how many weeks a student should spend preparing
- estimated_hours_total: total preparation hours estimate

Also extract:
- course_code: the course code/number
- course_name: the full course name

Return valid JSON matching this schema exactly: {schema}

Syllabus text:
---
{syllabus_text}
---"""

ANALYSIS_PROMPT = """\
Role: You are an academic workload analyst. Given the following weekly capacity \
breakdown, write a brief feasibility narrative.

Rules:
- State whether the schedule is feasible, tight, or not feasible
- Identify the hardest weeks and explain why
- Do NOT predict grades or academic outcomes
- Do NOT suggest changes (that comes later)
- Keep it under 200 words

Data:
{capacity_json}"""

SUGGESTION_PROMPT = """\
Role: You are a schedule advisor for a student with fixed constraints.

LOCKED commitments (you MUST NOT suggest changing these):
{locked_list}

Recovery floor (you MUST NOT breach these):
- Sleep: minimum 7 hours per night
- Leisure: minimum 10 hours per week

Over-capacity weeks:
{over_capacity_weeks_data}

Unlocked commitments (you MAY suggest changes to these):
{unlocked_list}

Generate 2-4 specific, actionable suggestions. Each must:
- Reference a specific course or commitment by name
- Specify the action: reduce, reschedule, or redistribute
- Include affected weeks
- Never breach the recovery floor

Return valid JSON matching this schema: {schema}"""

COMMITMENT_PARSE_PROMPT = """\
Role: You are parsing a student's description of their typical weekly schedule \
into structured data.

Extract each distinct commitment with:
- name: descriptive label
- category: one of [work, commute, sleep, extracurricular, leisure, other]
- hours_per_week: estimated weekly hours

For sleep, provide hours per NIGHT (the system converts to weekly).

Student's description:
---
{free_text}
---

Return valid JSON matching this schema: {schema}"""
