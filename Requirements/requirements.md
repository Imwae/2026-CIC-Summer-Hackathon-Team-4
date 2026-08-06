# Semester Capacity Planner — Requirements Spec

## 1. Problem Statement

Students routinely commit to course loads that are structurally impossible once
work, commute, and fixed commitments are accounted for. They discover this in
week 9, when several deadlines land in the same week and there is no slack left
to absorb them.

Existing planners assume everything in a student's life is movable. For working,
commuting, and first-generation students, it is not. A tool that recommends
"work fewer hours" to someone paying rent is useless advice.

## 2. Target Users

Primary: undergraduate students balancing coursework with paid employment,
commuting, or significant fixed commitments.

Secondary: any student registering for a semester who wants to know whether the
load is survivable before the drop deadline passes.

## 3. Core Concept

The student uploads their course syllabi and describes their weekly commitments.
They mark which commitments are **locked** (cannot be changed). The system
extracts real deadlines from the syllabi, builds a week-by-week capacity model,
and reports where the schedule runs out of hours — working only within the
commitments the student has said are movable.

## 4. Functional Requirements

### FR-1: Syllabus ingestion
- The system SHALL accept multiple PDF syllabus uploads in a single session.
- The system SHALL accept pasted plain text as an alternative input for any course.
- The system SHALL extract, per course: course code, graded deliverables, due
  dates, deliverable type, and weight where stated.
- The system SHALL display per-file extraction status (success, item count, or failure).
- WHEN a PDF yields no usable text, the system SHALL prompt for manual paste for
  that file only, without failing the other uploads.
- The system SHALL request a term start date from the student and use it to
  resolve relative dates ("Week 6") into week numbers.

### FR-2: Commitment capture
- The system SHALL capture: hours worked per week, commute time, sleep hours per
  night, extracurricular commitments, and discretionary/leisure time.
- The system SHALL accept free-text description of a typical week as an
  alternative to structured fields.
- The system SHALL allow the student to mark any commitment as LOCKED.
- The system SHALL visually indicate locked commitments in the interface.

### FR-3: Capacity analysis
- The system SHALL compute total weekly hours required (coursework + fixed
  commitments) against total hours available.
- The system SHALL model deliverable preparation as spanning multiple weeks
  before the due date, not as a single-week cost.
- The system SHALL identify weeks where required hours exceed available hours.
- The system SHALL identify collision weeks where deliverables from two or more
  courses overlap.
- The system SHALL report structural feasibility only. It SHALL NOT predict
  grades, GPA, academic outcomes, or personal characteristics.

### FR-4: Recovery floor
- The system SHALL treat sleep and discretionary time as protected inputs.
- The system SHALL NOT generate suggestions that reduce sleep below 7 hours per
  night or discretionary time below 10 hours per week.
- WHEN a schedule is feasible only by breaching the recovery floor, the system
  SHALL report it as not feasible rather than resolving it by removing rest.

### FR-5: Suggestions
- The system SHALL generate suggestions that modify only unlocked commitments.
- The system SHALL explicitly acknowledge locked constraints in its output.
- Suggestions SHALL be specific to the student's actual courses and commitments,
  referenced by name.
- The system MAY suggest relocating leisure or study time to different days; it
  SHALL NOT suggest reducing leisure below the floor.

### FR-6: Visualization
- The system SHALL display a week-by-week timeline showing required hours per
  week, with collision and over-capacity weeks visually distinguished.
- The system SHALL display a breakdown of where weekly hours are allocated.

## 5. Non-Functional Requirements

- **NFR-1**: Full analysis SHALL complete in under 30 seconds for 5 syllabi.
- **NFR-2**: Extraction results SHALL be cached per file so that re-running
  analysis does not reprocess unchanged uploads.
- **NFR-3**: AWS credentials SHALL NOT be exposed to the frontend.
- **NFR-4**: An AI call failure SHALL surface a readable message, never an
  unhandled stack trace.
- **NFR-5**: The system SHALL be deployed to AWS Lambda with a public Function URL.

## 6. Technical Architecture

- **AI**: Amazon Bedrock (Claude), invoked server-side only
- **Backend**: Python, FastAPI locally / Lambda handler in deployment
- **Frontend**: HTML/CSS/JS, served by the same Lambda
- **Storage**: None. Static JSON data files; no database, no persistence, no auth
- **Deployment**: Single Lambda function with Function URL, timeout 60s,
  Bedrock access via execution role

### File structure

```
backend/
  main.py              # Routes only
  bedrock_client.py    # All Bedrock calls; sole boto3 importer
  prompts.py           # Prompt templates as named constants
  extractor.py         # PDF -> text, per-file handling
  capacity.py          # Week model, collision detection, floor enforcement
  models.py            # Pydantic request/response schemas
data/
  sample_syllabi/      # Demo fixtures
frontend/
  index.html
  app.js               # State + API calls
  charts.js            # Timeline + breakdown rendering
  styles.css
```

### AI call boundaries

Three distinct calls, each with a defined JSON contract:

1. **Syllabus extraction** — one call per uploaded file. Input: syllabus text or
   PDF. Output: structured deliverable list with dates, weights, and preparation
   lead times.
2. **Capacity analysis** — one call. Input: merged deliverable timeline plus the
   student's commitments and lock flags. Output: weekly required/available hours,
   feasibility verdict, critical weeks.
3. **Suggestion generation** — one call. Input: capacity analysis result plus
   lock flags. Output: specific, actionable changes to unlocked commitments only.

Week-number normalization and collision detection are performed in Python
(`capacity.py`), not by the model.

## 7. Explicitly Out of Scope

- User accounts, login, persistence between sessions
- OCR for scanned documents (manual paste fallback covers this)
- Integration with any real student information system
- Mobile-specific layouts
- More than one institution's course conventions

## 8. Build Priority

Implement in this order. If time runs short, cut from the bottom.

1. Paste-text input → extraction → capacity analysis → timeline (end-to-end)
2. Locked constraints and suggestion generation
3. Multiple PDF upload
4. Hours breakdown visualization
5. Narrative walkthrough of the highest-load week

## 9. Instructions for Task Breakdown

Follow the file structure above exactly. Do not create additional directories or
files without stating why.

Produce a task list where each task names the specific file or files it touches.
Mark tasks that touch different files as parallelizable; tasks touching the same
file must be sequential. The team has three developers of mixed experience and
approximately eight hours.

For each task, state its acceptance criterion as an observable behaviour, not as
an implementation detail.

Define the JSON schemas in `models.py` as the first task, before any dependent
work begins, so that frontend and backend can proceed against a fixed contract.
