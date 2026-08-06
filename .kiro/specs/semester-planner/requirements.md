# Semester Capacity Planner — Requirements

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

---

## 4. User Stories and Acceptance Criteria

### Story 1: Syllabus Input via Text Paste

As a student, I want to paste my syllabus text into the app so that the system
can extract my deadlines without requiring a PDF file.

**Acceptance Criteria:**
- [ ] The app displays a text input area per course where the student can paste syllabus content
- [ ] On submission, the system returns a structured list of deliverables (name, type, due date, weight, estimated prep weeks)
- [ ] The extraction status is shown per course: success with item count, or failure with a retry prompt
- [ ] The student can view and override AI-estimated prep-time values before proceeding to analysis

### Story 2: Syllabus Input via PDF Upload

As a student, I want to upload PDF syllabi so that the system extracts deadlines
automatically without manual copying.

**Acceptance Criteria:**
- [ ] The app accepts multiple PDF file uploads in a single session
- [ ] Each file shows individual extraction status (processing, success, failure)
- [ ] When a PDF yields no usable text, the system prompts for manual paste for that file only — other successful uploads are unaffected
- [ ] Extraction results are cached per file so re-running analysis does not reprocess unchanged uploads

### Story 3: Extraction Completeness Gate

As a student, I want the system to wait until all my syllabi are extracted
before running analysis so that I get a complete picture.

**Acceptance Criteria:**
- [ ] The "Run Analysis" action is disabled until all uploaded syllabi show successful extraction
- [ ] Failed extractions display a clear prompt to re-upload or paste text
- [ ] Re-uploading a failed file does not reset or affect previously successful extractions

### Story 4: Commitment Capture (Structured)

As a student, I want to enter my weekly commitments in a form so the system
knows how much time I have available.

**Acceptance Criteria:**
- [ ] The form captures: work hours/week, commute hours/week, sleep hours/night, extracurricular hours/week, and discretionary/leisure hours/week
- [ ] Each commitment has a toggle to mark it as LOCKED (cannot be modified by suggestions)
- [ ] Locked commitments are visually distinguished (e.g., lock icon, different color)
- [ ] The student can add custom-named commitments beyond the defaults

### Story 5: Commitment Capture (Free-Text)

As a student, I want to describe my typical week in plain text as an
alternative to filling out a form.

**Acceptance Criteria:**
- [ ] The app provides a free-text area as an alternative to the structured form
- [ ] On submission, the text is sent to Bedrock and parsed into structured commitments
- [ ] The parsed result is displayed for the student to confirm or edit before analysis proceeds
- [ ] The student can mark parsed commitments as LOCKED before confirming

### Story 6: Break Week Input

As a student, I want to mark break weeks (reading week, holidays) so the system
excludes them from capacity calculations.

**Acceptance Criteria:**
- [ ] The app provides a way to select or input specific week numbers as breaks
- [ ] Break weeks are excluded from all capacity and collision calculations
- [ ] Break weeks are visually indicated on the timeline visualization
- [ ] No fixed break schedule is assumed — all breaks are student-specified

### Story 7: Capacity Analysis

As a student, I want to see which weeks will overwhelm me so I can plan ahead
or drop a course before the deadline.

**Acceptance Criteria:**
- [ ] The system computes per-week required hours (coursework prep + locked commitments) vs. available hours
- [ ] Deliverable prep hours are spread across multiple weeks before the due date (not single-week spike)
- [ ] Weeks where required > available are flagged as over-capacity
- [ ] Weeks with deliverables from 2+ courses due are flagged as collision weeks
- [ ] The system reports a feasibility verdict: feasible, tight, or not feasible
- [ ] The system does NOT predict grades, GPA, or academic outcomes

### Story 8: Recovery Floor Enforcement

As a student, I want the system to protect my sleep and rest time so that
"solutions" don't come at the cost of my health.

**Acceptance Criteria:**
- [ ] The system never generates suggestions that reduce sleep below 7 hours/night
- [ ] The system never generates suggestions that reduce leisure below 10 hours/week
- [ ] When a schedule is only feasible by breaching the recovery floor, the system reports "not feasible" rather than suggesting the student sleep less
- [ ] The recovery floor values (7h sleep, 10h leisure) are displayed to the student

### Story 9: Suggestions for Over-Capacity Weeks

As a student, I want actionable suggestions for making my schedule work, limited
to things I've said I'm willing to change.

**Acceptance Criteria:**
- [ ] Suggestions only modify commitments the student has NOT marked as LOCKED
- [ ] Each suggestion references at least one named course or commitment from the student's input
- [ ] The system explicitly acknowledges which constraints are locked and cannot be changed
- [ ] Suggestions may relocate leisure/study time to different days but never reduce leisure below 10h/week

### Story 10: Visualization — Commitment Pie Chart

As a student, I want to see a pie chart showing how my semester time is
distributed across all commitments so I can see the big picture.

**Acceptance Criteria:**
- [ ] A pie chart displays showing all commitments as proportional slices of total semester hours
- [ ] Each slice is labeled with the commitment name and percentage
- [ ] The full circle represents 100% of available semester time
- [ ] Locked commitments are visually distinguished from unlocked ones in the chart

### Story 11: Visualization — Weekly Hours Breakdown

As a student, I want to see a breakdown of how my hours are allocated each week
so I can identify where my time goes.

**Acceptance Criteria:**
- [ ] A per-week view shows hours allocated to each category (coursework by course, work, commute, sleep, leisure, etc.)
- [ ] Over-capacity weeks are visually highlighted (e.g., red background or border)
- [ ] Collision weeks are visually distinguished (e.g., warning icon or distinct color)
- [ ] Break weeks are shown as empty/grayed out

---

## 5. Semester Window

- The semester window is fixed: 2nd week of September through 3rd week of
  December (~15 weeks).
- Relative dates (e.g., "Week 6") are resolved against the semester start date
  (2nd Monday of September).
- Break weeks are manually input by the student; no fixed break schedule is assumed.

---

## 6. Non-Functional Requirements

- **NFR-1**: Full analysis SHALL complete in under 30 seconds for 5 syllabi.
- **NFR-2**: Extraction results SHALL be cached per file so that re-running
  analysis does not reprocess unchanged uploads.
- **NFR-3**: AWS credentials SHALL NOT be exposed to the frontend.
- **NFR-4**: An AI call failure SHALL surface a readable message, never an
  unhandled stack trace.
- **NFR-5**: The system SHALL be deployed to AWS Lambda with a public Function
  URL. (Deferred to post-hackathon; architecture is Lambda-ready but demo runs
  locally via uvicorn.)

---

## 7. Technical Architecture

- **AI**: Amazon Bedrock (Claude), invoked server-side only
- **Backend**: Python, FastAPI locally / Lambda handler in deployment
- **Frontend**: React (Vite), served as static build by the same Lambda
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
frontend/                # React app (Vite)
  src/
    App.jsx            # Root component, state machine, routing
    components/
      SyllabusUpload.jsx   # File upload + paste input per course
      CommitmentForm.jsx   # Structured commitment capture + lock toggles
      Timeline.jsx         # Week-by-week capacity timeline chart
      Breakdown.jsx        # Hours allocation breakdown chart
      Suggestions.jsx      # Suggestion display
    api.js             # API call helpers
    main.jsx           # Entry point
  index.html           # Vite HTML shell
  package.json
  vite.config.js
```

### AI call boundaries

Three distinct calls, each with a defined JSON contract:

1. **Syllabus extraction** — one call per uploaded file. Input: syllabus text or
   PDF text. Output: structured deliverable list with dates, weights, and
   preparation lead times (shown to student for override).
2. **Capacity analysis** — one call. Input: merged deliverable timeline plus the
   student's commitments and lock flags. Output: weekly required/available hours,
   feasibility verdict, critical weeks.
3. **Suggestion generation** — one call. Input: capacity analysis result plus
   lock flags. Output: specific, actionable changes to unlocked commitments only.

Week-number normalization and collision detection are performed in Python
(`capacity.py`), not by the model.

---

## 8. Explicitly Out of Scope

- User accounts, login, persistence between sessions
- OCR for scanned documents (manual paste fallback covers this)
- Integration with any real student information system
- Mobile-specific layouts
- More than one institution's course conventions

---

## 9. Build Priority

Implement in this order. If time runs short, cut from the bottom.

1. Paste-text input → extraction → capacity analysis → timeline (end-to-end)
2. Locked constraints and suggestion generation
3. Multiple PDF upload
4. Hours breakdown visualization
5. Narrative walkthrough of the highest-load week

---

## 10. Instructions for Task Breakdown

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
