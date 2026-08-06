# Semester Capacity Planner — Design Document

#[[file:.kiro/specs/semester-planner/requirements.md]]

---

## 1. System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                  BROWSER — React (Vite)                        │
│                                                              │
│  ┌────────────────┐  ┌─────────────────┐  ┌──────────────┐  │
│  │ SyllabusUpload │  │ CommitmentForm  │  │  Results     │  │
│  │ (PDF + paste)  │  │ (struct + text) │  │  Timeline    │  │
│  └───────┬────────┘  └───────┬─────────┘  │  Breakdown   │  │
│          │                   │             │  Suggestions │  │
│          │                   │             └──────▲───────┘  │
│          │                   │                    │          │
│          └─────────┬─────────┘                    │          │
│                    ▼                              │          │
│              src/api.js ─────── fetch ────────────┤          │
│                                                   │          │
└───────────────────────────────────────────────────┼──────────┘
                                                    │
                    HTTP (localhost:8000)            │
                                                    │
┌───────────────────────────────────────────────────┼──────────┐
│                  BACKEND — FastAPI (Python)        │          │
│                                                              │
│  main.py ─── API routes only                                 │
│    │                                                         │
│    ├──► extractor.py ──► bedrock_client.py (extraction call) │
│    │                                                         │
│    ├──► capacity.py ─── week model, collisions, floors       │
│    │         │                                               │
│    │         └──► bedrock_client.py (analysis + suggest)     │
│    │                                                         │
│    └──► models.py ─── Pydantic schemas (shared contract)     │
│                                                              │
│  prompts.py ─── prompt templates as constants                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                    │
                    ▼
        ┌───────────────────┐
        │  Amazon Bedrock   │
        │  (Claude model)   │
        └───────────────────┘
```

### Key architectural decisions

- **Separation of concerns**: React handles all UI state and rendering. FastAPI handles all business logic and AI calls. They communicate via JSON over HTTP.
- **No shared state**: The backend is stateless. All session state lives in the React app's memory. Refresh = start over (per requirements).
- **AI calls server-side only**: The frontend never touches AWS credentials. All Bedrock invocations route through `bedrock_client.py`.
- **Deterministic logic in Python**: Week-number normalization, collision detection, and recovery floor enforcement happen in `capacity.py` — not delegated to the AI model.

---

## 2. Data Flow

### Phase 1: Syllabus Ingestion (Stories 1, 2, 3)

```
User pastes text or uploads PDF
        │
        ▼
POST /api/extract  { course_text | file (multipart) }
        │
        ▼
extractor.py: if PDF → PyPDF2 extract text
              if no text extracted → return { status: "failure" }
        │
        ▼
bedrock_client.py: call Bedrock with EXTRACTION_PROMPT + syllabus text
        │
        ▼
Parse Bedrock JSON response → validate against ExtractionResponse schema
        │
        ▼
Return to frontend: course_code, course_name, deliverables[]
        │
        ▼
React: display deliverable table, allow prep-week overrides
        │
        ▼
Gate: "Run Analysis" enabled only when ALL courses show status=success
```

### Phase 2: Commitment Capture (Stories 4, 5, 6)

```
User fills structured form OR pastes free-text
        │
        ├── Structured: stored directly in React state
        │
        └── Free-text:
              POST /api/commitments/parse  { text }
                      │
                      ▼
              bedrock_client.py: call Bedrock with COMMITMENT_PARSE_PROMPT
                      │
                      ▼
              Return parsed commitments → user confirms/edits
        │
        ▼
User marks LOCKED/unlocked per commitment
User inputs break weeks (week numbers to exclude)
```

### Phase 3: Capacity Analysis (Stories 7, 8)

```
POST /api/analyze  { courses[], commitments[], break_weeks[] }
        │
        ▼
capacity.py:
  1. Build 15-week timeline from semester_start
  2. For each deliverable: spread prep_hours across prep_weeks before due_date
  3. Per week: sum all prep hours + commitment hours = required
  4. Per week: 168 - (sleep*7) - locked_hours = available
  5. Flag over_capacity weeks (required > available - leisure)
  6. Flag collision weeks (deliverables from 2+ courses same week)
  7. Check recovery floor (sleep >= 7h, leisure >= 10h/week)
  8. Determine feasibility verdict
        │
        ▼
bedrock_client.py: call Bedrock with ANALYSIS_PROMPT + capacity data
  → AI generates narrative verdict and week-by-week commentary
        │
        ▼
Return AnalysisResponse to frontend
```

### Phase 4: Suggestion Generation (Story 9)

```
POST /api/suggest  { analysis_result, commitments[], lock_flags }
        │
        ▼
bedrock_client.py: call Bedrock with SUGGESTION_PROMPT
  Constraints passed to prompt:
    - List of LOCKED commitments (must not be modified)
    - Recovery floor minimums (sleep >= 7h, leisure >= 10h)
    - Over-capacity weeks and their hour deficits
        │
        ▼
Return SuggestionResponse: suggestions[] + locked_acknowledgment
```

### Phase 5: Visualization (Stories 10, 11)

```
React receives AnalysisResponse
        │
        ├── Timeline.jsx: renders week-by-week bar chart
        │     - Y-axis: hours
        │     - Stacked bars: prep by course + commitments
        │     - Red highlight on over-capacity weeks
        │     - Warning icon on collision weeks
        │     - Grayed out break weeks
        │
        └── Breakdown.jsx: renders pie chart
              - Slices: each commitment as % of total semester hours
              - Locked commitments get distinct visual (border/pattern)
              - Labels: commitment name + percentage
```

---

## 3. API Contract

### POST /api/extract

**Request** (multipart/form-data OR JSON):
```json
{
  "course_text": "string (pasted syllabus text)",
  "file_name": "string (original filename for display)"
}
```
Or multipart with `file` field (PDF binary) + `file_name` field.

**Response**:
```json
{
  "status": "success | failure",
  "course_code": "string",
  "course_name": "string",
  "deliverables": [
    {
      "name": "string",
      "type": "exam | essay | project | presentation | lab | other",
      "due_date": "string (YYYY-MM-DD or Week N)",
      "week_number": 6,
      "weight_percent": 25.0,
      "estimated_prep_weeks": 2,
      "estimated_hours_total": 12.0
    }
  ],
  "error_message": "string | null"
}
```

### POST /api/commitments/parse

**Request**:
```json
{
  "text": "string (free-text description of typical week)"
}
```

**Response**:
```json
{
  "commitments": [
    {
      "name": "string",
      "category": "work | commute | sleep | extracurricular | leisure | other",
      "hours_per_week": 20.0,
      "locked": false
    }
  ]
}
```

### POST /api/analyze

**Request**:
```json
{
  "courses": [
    {
      "course_code": "string",
      "course_name": "string",
      "deliverables": [
        {
          "name": "string",
          "type": "string",
          "week_number": 6,
          "weight_percent": 25.0,
          "estimated_prep_weeks": 2,
          "estimated_hours_total": 12.0
        }
      ]
    }
  ],
  "commitments": [
    {
      "name": "string",
      "category": "string",
      "hours_per_week": 20.0,
      "locked": true
    }
  ],
  "break_weeks": [7, 12],
  "semester_start": "2025-09-08",
  "semester_end": "2025-12-19"
}
```

**Response**:
```json
{
  "feasible": true,
  "feasibility_level": "feasible | tight | not_feasible",
  "total_weeks": 15,
  "weeks": [
    {
      "week_number": 1,
      "start_date": "2025-09-08",
      "is_break": false,
      "hours_required": 42.5,
      "hours_available": 65.0,
      "over_capacity": false,
      "collision": false,
      "deliverables_due": ["CS101: Midterm Exam"],
      "prep_hours_by_course": { "CS101": 6.0, "ENG200": 4.0 }
    }
  ],
  "critical_weeks": [9, 13],
  "collision_weeks": [9],
  "recovery_floor_breached": false,
  "verdict": "string (AI-generated feasibility narrative)"
}
```

### POST /api/suggest

**Request**:
```json
{
  "analysis_result": { "...same as AnalysisResponse above..." },
  "commitments": [ "...commitment objects with lock flags..." ]
}
```

**Response**:
```json
{
  "suggestions": [
    {
      "description": "string (human-readable suggestion)",
      "target_commitment": "string (name of unlocked commitment)",
      "action": "reduce | reschedule | redistribute",
      "detail": "string (specific actionable change)",
      "affected_weeks": [9, 10]
    }
  ],
  "locked_acknowledgment": "string (explicit statement of what cannot be changed)"
}
```

---

## 4. Frontend Component Design (React)

### Component Tree

```
App.jsx
├── Header (app title, semester dates display)
├── SyllabusUpload.jsx
│   ├── FileUploadZone (drag-drop + file picker)
│   ├── TextPasteInput (textarea per course)
│   ├── ExtractionStatusList (per-file status cards)
│   └── DeliverableTable (editable prep-week overrides)
├── CommitmentForm.jsx
│   ├── StructuredInputs (labeled number fields + lock toggles)
│   ├── FreeTextInput (textarea + parse button)
│   ├── ParsedConfirmation (shows AI-parsed result for review)
│   └── BreakWeekSelector (checkbox/multi-select for week numbers)
├── Timeline.jsx
│   └── WeeklyBarChart (Chart.js stacked bar)
├── Breakdown.jsx
│   └── PieChart (Chart.js doughnut)
└── Suggestions.jsx
    ├── LockedAcknowledgment (displays what's protected)
    └── SuggestionCards (one card per suggestion)
```

### State Management

All state lives in `App.jsx` using React `useState`/`useReducer`. No external state library needed given the linear flow.

```javascript
state = {
  // Phase tracking
  appPhase: 'input' | 'analyzing' | 'results' | 'suggesting',

  // Syllabus data
  courses: [
    {
      id: string,
      fileName: string,
      status: 'pending' | 'extracting' | 'success' | 'failure',
      extractionResult: ExtractionResponse | null,
      errorMessage: string | null
    }
  ],

  // Commitments
  commitments: [
    { name, category, hours_per_week, locked }
  ],
  breakWeeks: number[],

  // Results
  analysisResult: AnalysisResponse | null,
  suggestions: SuggestionResponse | null,

  // UI
  error: string | null,
  loading: boolean
}
```

### State Transitions

| Current Phase | Action | Next Phase | Condition |
|---------------|--------|------------|-----------|
| input | Click "Run Analysis" | analyzing | All courses status=success AND commitments.length > 0 |
| analyzing | API returns | results | AnalysisResponse received |
| results | Click "Get Suggestions" | suggesting | over-capacity weeks exist |
| suggesting | API returns | results | SuggestionResponse merged into view |

---

## 5. Capacity Calculation Logic (capacity.py)

### Constants
```python
TOTAL_HOURS_PER_WEEK = 168
MIN_SLEEP_HOURS_PER_NIGHT = 7
MIN_LEISURE_HOURS_PER_WEEK = 10
SEMESTER_WEEKS = 15
```

### Algorithm

```python
def compute_capacity(courses, commitments, break_weeks, semester_start):
    # 1. Build week timeline
    weeks = generate_weeks(semester_start, SEMESTER_WEEKS)

    # 2. Compute available hours per week
    sleep_commitment = find_commitment(commitments, 'sleep')
    sleep_hours_per_week = sleep_commitment.hours_per_week * 7  # nightly -> weekly
    locked_hours = sum(c.hours_per_week for c in commitments if c.locked and c.category != 'sleep')
    leisure_hours = find_commitment(commitments, 'leisure').hours_per_week
    available = TOTAL_HOURS_PER_WEEK - sleep_hours_per_week - locked_hours

    # 3. Spread deliverable prep across weeks
    for course in courses:
        for deliverable in course.deliverables:
            prep_per_week = deliverable.estimated_hours_total / deliverable.estimated_prep_weeks
            start_week = deliverable.week_number - deliverable.estimated_prep_weeks
            for w in range(start_week, deliverable.week_number):
                if w not in break_weeks and 1 <= w <= SEMESTER_WEEKS:
                    weeks[w].prep_hours[course.course_code] += prep_per_week

    # 4. Per-week analysis
    for week in weeks:
        if week.number in break_weeks:
            week.is_break = True
            continue
        week.hours_required = sum(week.prep_hours.values())
        week.hours_available = available - leisure_hours
        week.over_capacity = week.hours_required > week.hours_available

    # 5. Collision detection
    for week in weeks:
        courses_with_due = set()
        for course in courses:
            for d in course.deliverables:
                if d.week_number == week.number:
                    courses_with_due.add(course.course_code)
        week.collision = len(courses_with_due) >= 2

    # 6. Recovery floor check
    recovery_floor_breached = any(
        week.hours_required > (TOTAL_HOURS_PER_WEEK - MIN_SLEEP_HOURS_PER_NIGHT * 7 - MIN_LEISURE_HOURS_PER_WEEK)
        for week in weeks if not week.is_break
    )

    # 7. Feasibility verdict
    over_capacity_count = sum(1 for w in weeks if w.over_capacity)
    if recovery_floor_breached:
        feasibility_level = "not_feasible"
    elif over_capacity_count > 3:
        feasibility_level = "not_feasible"
    elif over_capacity_count > 0:
        feasibility_level = "tight"
    else:
        feasibility_level = "feasible"

    return AnalysisResult(...)
```

---

## 6. AI Prompt Design

### Extraction Prompt (per syllabus)

```
Role: You are a syllabus parser. Extract all graded deliverables from the
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
---
```

### Analysis Prompt

```
Role: You are an academic workload analyst. Given the following weekly capacity
breakdown, write a brief feasibility narrative.

Rules:
- State whether the schedule is feasible, tight, or not feasible
- Identify the hardest weeks and explain why
- Do NOT predict grades or academic outcomes
- Do NOT suggest changes (that comes later)
- Keep it under 200 words

Data:
{capacity_json}
```

### Suggestion Prompt

```
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

Return valid JSON matching this schema: {schema}
```

### Commitment Parse Prompt

```
Role: You are parsing a student's description of their typical weekly schedule
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

Return valid JSON matching this schema: {schema}
```

---

## 7. Error Handling Design

### Backend error responses

All errors return a consistent shape:
```json
{
  "error": true,
  "message": "Human-readable error description",
  "code": "EXTRACTION_FAILED | ANALYSIS_FAILED | SUGGESTION_FAILED | PARSE_ERROR | BEDROCK_TIMEOUT"
}
```

### Error handling by layer

| Layer | Strategy |
|-------|----------|
| `extractor.py` | Catch PyPDF2 exceptions → return `{ status: "failure", error_message }` |
| `bedrock_client.py` | Catch boto3 exceptions, JSON parse errors. Retry once on invalid JSON. Surface readable message on second failure. |
| `main.py` | Global exception handler wraps all unhandled errors into `{ error: true, message }`. Never exposes stack traces. |
| React `api.js` | Check `response.ok`. On error, parse message and set `state.error`. Display in a dismissible banner. |

### Retry logic

- Bedrock calls: 1 automatic retry on JSON parse failure (model sometimes returns markdown-wrapped JSON)
- No retry on timeout (user clicks retry manually)
- No retry on PDF extraction failure (user provides paste instead)

---

## 8. Security Boundaries

| Boundary | Enforcement |
|----------|-------------|
| AWS credentials | Never sent to frontend. `bedrock_client.py` uses boto3 default credential chain (env vars / IAM role). |
| File uploads | Max 10MB per file (enforced by FastAPI request size limit). |
| Input validation | All requests validated via Pydantic models before processing. |
| No persistence | No database, no file writes, no cookies. Each session is ephemeral. |
| CORS | In development: allow localhost:5173 (Vite dev server). In production: same-origin only. |

---

## 9. Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Frontend framework | React 18 + Vite | Fast dev server, HMR, modern JSX. No SSR complexity needed. |
| Charts | Chart.js + react-chartjs-2 | Proven library, supports stacked bar + doughnut. React wrapper available. |
| HTTP client | fetch (native) | No extra dependency needed for simple JSON POST calls. |
| Backend framework | FastAPI | Async, Pydantic-native, easy Lambda packaging via Mangum. |
| PDF parsing | PyPDF2 | Lightweight, pure Python, no native deps. Sufficient for text-based PDFs. |
| AI model | Claude 3 Sonnet via Bedrock | Good balance of quality and speed for structured extraction tasks. |
| Lambda adapter | Mangum | Standard FastAPI-to-Lambda bridge. Deferred to post-hackathon. |
| Dev proxy | Vite proxy config | Forward `/api/*` requests to FastAPI during development. |

---

## 10. Development Setup

### Local development flow

```
Terminal 1: cd backend && uvicorn main:app --reload --port 8000
Terminal 2: cd frontend && npm run dev          (Vite on port 5173)
```

Vite proxies `/api/*` to `localhost:8000` via `vite.config.js`:
```javascript
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
```

### Environment variables (backend)

```
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
```

---

## 11. Deployment Architecture (Post-Hackathon)

```
┌──────────────┐         ┌──────────────────────┐
│   Browser    │ ──────► │  Lambda Function URL  │
└──────────────┘         │                      │
                         │  Mangum → FastAPI    │
                         │  /api/* → handlers   │
                         │  /* → static React   │
                         │        build files   │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   Amazon Bedrock     │
                         │   (via IAM role)     │
                         └──────────────────────┘
```

- React build output (`npm run build`) bundled into Lambda deployment package
- FastAPI serves static files from `frontend/dist/`
- Lambda execution role grants `bedrock:InvokeModel` permission
- Function URL provides public HTTPS endpoint, no API Gateway needed
- Timeout: 60 seconds (sufficient for Bedrock round-trip)
