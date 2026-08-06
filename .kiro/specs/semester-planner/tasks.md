# Semester Capacity Planner — Tasks

## Task 1: Define Pydantic schemas in `backend/models.py`

**Files:** `backend/models.py`
**Parallelizable:** No — this is the foundation. Must complete before Tasks 2–8.
**Stories:** All (shared contract)

### Subtasks:
- [x] Create `Deliverable` model (name, type, due_date, week_number, weight_percent, estimated_prep_weeks, estimated_hours_total)
- [x] Create `ExtractionRequest` model (course_text, file_name)
- [x] Create `ExtractionResponse` model (status, course_code, course_name, deliverables[], error_message)
- [x] Create `Commitment` model (name, category, hours_per_week, locked)
- [x] Create `CommitmentParseRequest` model (text)
- [x] Create `CommitmentParseResponse` model (commitments[])
- [x] Create `CourseInput` model (course_code, course_name, deliverables[])
- [x] Create `AnalysisRequest` model (courses[], commitments[], break_weeks[], semester_start, semester_end)
- [x] Create `WeekResult` model (week_number, start_date, is_break, hours_required, hours_available, over_capacity, collision, deliverables_due[], prep_hours_by_course{})
- [x] Create `AnalysisResponse` model (feasible, feasibility_level, total_weeks, weeks[], critical_weeks[], collision_weeks[], recovery_floor_breached, verdict)
- [x] Create `Suggestion` model (description, target_commitment, action, detail, affected_weeks[])
- [x] Create `SuggestionRequest` model (analysis_result, commitments[])
- [x] Create `SuggestionResponse` model (suggestions[], locked_acknowledgment)
- [x] Create `ErrorResponse` model (error, message, code)

**Acceptance Criterion:** Importing `backend.models` succeeds and all models can be instantiated with sample data matching the API contract in the design doc.

---

## Task 2: Implement prompt templates in `backend/prompts.py`

**Files:** `backend/prompts.py`
**Parallelizable:** Yes (independent of Tasks 3–8, only depends on Task 1 for schema references)
**Stories:** 1, 5, 7, 9

### Subtasks:
- [x] Define `EXTRACTION_PROMPT` template with placeholders for syllabus_text and schema
- [x] Define `ANALYSIS_PROMPT` template with placeholders for capacity_json
- [x] Define `SUGGESTION_PROMPT` template with placeholders for locked_list, over_capacity_weeks_data, unlocked_list, schema
- [x] Define `COMMITMENT_PARSE_PROMPT` template with placeholders for free_text and schema

**Acceptance Criterion:** Each prompt constant is a string with clearly marked placeholders. Formatting with `.format()` or f-string substitution produces a complete prompt with no missing variables.

---

## Task 3: Implement Bedrock client in `backend/bedrock_client.py`

**Files:** `backend/bedrock_client.py`
**Parallelizable:** Yes (can proceed alongside Tasks 4, 5, 6 once Task 1 + 2 are done)
**Stories:** 1, 2, 5, 7, 9
**Depends on:** Task 1, Task 2

### Subtasks:
- [ ] Create boto3 Bedrock runtime client (sole boto3 importer in the project)
- [ ] Implement `extract_syllabus(text: str) -> ExtractionResponse` — calls Bedrock with extraction prompt, parses JSON response
- [ ] Implement `analyze_capacity(capacity_data: dict) -> str` — calls Bedrock with analysis prompt, returns narrative verdict
- [ ] Implement `generate_suggestions(analysis_result: dict, commitments: list) -> SuggestionResponse` — calls Bedrock with suggestion prompt
- [ ] Implement `parse_commitments(text: str) -> CommitmentParseResponse` — calls Bedrock with commitment parse prompt
- [ ] Implement retry logic: on JSON parse failure, strip markdown fences and retry parse once
- [ ] Implement error handling: catch ClientError, timeout, JSON errors → raise descriptive exceptions (never raw stack traces)

**Acceptance Criterion:** Each function calls Bedrock, returns a validated Pydantic model on success, and raises a human-readable exception on failure. No AWS credentials are hardcoded.

---

## Task 4: Implement PDF extraction in `backend/extractor.py`

**Files:** `backend/extractor.py`
**Parallelizable:** Yes (independent of Tasks 3, 5, 6)
**Stories:** 2
**Depends on:** Task 1

### Subtasks:
- [ ] Implement `extract_text_from_pdf(file_bytes: bytes) -> str | None` — uses PyPDF2 to extract text from uploaded PDF bytes
- [ ] Return `None` if no usable text is extracted (empty or whitespace-only)
- [ ] Handle corrupted/invalid PDF files gracefully — return None, don't crash

**Acceptance Criterion:** Given a text-based PDF, the function returns the full text content. Given a scanned/image PDF or corrupt file, it returns None without raising an exception.

---

## Task 5: Implement capacity analysis in `backend/capacity.py`

**Files:** `backend/capacity.py`
**Parallelizable:** Yes (independent of Tasks 3, 4, 6)
**Stories:** 7, 8
**Depends on:** Task 1

### Subtasks:
- [ ] Implement `generate_weeks(semester_start: date, num_weeks: int) -> list[Week]` — creates week objects with start dates
- [ ] Implement `spread_prep_hours(courses, weeks, break_weeks)` — distributes deliverable prep hours across weeks before due date
- [ ] Implement `compute_available_hours(commitments) -> float` — calculates weekly available hours (168 - sleep*7 - locked hours)
- [ ] Implement `detect_collisions(courses, weeks)` — flags weeks with deliverables from 2+ courses
- [ ] Implement `check_recovery_floor(weeks, commitments) -> bool` — returns True if floor is breached
- [ ] Implement `compute_capacity(courses, commitments, break_weeks, semester_start, semester_end) -> AnalysisResult` — orchestrates all above, returns complete week-by-week breakdown
- [ ] Implement feasibility verdict logic: not_feasible (floor breached or >3 over-capacity weeks), tight (1-3 over-capacity), feasible (0 over-capacity)

**Acceptance Criterion:** Given sample courses with known deliverables and commitments, `compute_capacity` returns correct over-capacity flags, collision flags, and feasibility level. Break weeks show is_break=True with zero required hours.

---

## Task 6: Implement FastAPI routes in `backend/main.py`

**Files:** `backend/main.py`
**Parallelizable:** No — integrates Tasks 3, 4, 5. Should start once those are substantially complete.
**Stories:** All
**Depends on:** Tasks 1, 3, 4, 5

### Subtasks:
- [ ] Create FastAPI app instance with CORS middleware (allow localhost:5173 in dev)
- [ ] Implement `POST /api/extract` — accepts JSON (text paste) or multipart (PDF upload), calls extractor then bedrock_client, returns ExtractionResponse
- [ ] Implement `POST /api/commitments/parse` — accepts free-text, calls bedrock_client, returns CommitmentParseResponse
- [ ] Implement `POST /api/analyze` — accepts AnalysisRequest, runs capacity.compute_capacity, calls bedrock_client for narrative, returns AnalysisResponse
- [ ] Implement `POST /api/suggest` — accepts SuggestionRequest, calls bedrock_client, returns SuggestionResponse
- [ ] Implement global exception handler — catches all unhandled exceptions, returns ErrorResponse (never exposes stack traces)
- [ ] Add static file serving for production (serve `frontend/dist/` at root)

**Acceptance Criterion:** All four API endpoints respond with the correct JSON shape. Errors return `{ error: true, message, code }`. The server starts with `uvicorn backend.main:app` without errors.

---

## Task 7: Scaffold React frontend with Vite

**Files:** `frontend/` (package.json, vite.config.js, index.html, src/main.jsx, src/App.jsx)
**Parallelizable:** Yes (can proceed alongside backend tasks once Task 1 defines the contract)
**Stories:** All (frontend foundation)

### Subtasks:
- [ ] Initialize Vite React project in `frontend/` directory
- [ ] Configure `vite.config.js` with proxy: `/api` → `http://localhost:8000`
- [ ] Install dependencies: react, react-dom, chart.js, react-chartjs-2
- [ ] Create `src/main.jsx` entry point
- [ ] Create `src/App.jsx` with state management (useReducer) and phase tracking
- [ ] Create `src/api.js` with fetch helpers for all 4 API endpoints (extract, parse, analyze, suggest)
- [ ] Verify `npm run dev` starts successfully and proxies API calls

**Acceptance Criterion:** `npm run dev` launches the Vite dev server. Navigating to localhost:5173 shows the app shell. API calls from `api.js` reach the backend via the proxy.

---

## Task 8: Implement SyllabusUpload component

**Files:** `frontend/src/components/SyllabusUpload.jsx`
**Parallelizable:** Yes (can proceed alongside Tasks 9, 10, 11)
**Stories:** 1, 2, 3
**Depends on:** Task 7

### Subtasks:
- [ ] Create file upload zone (drag-drop area + file input for PDFs)
- [ ] Create text paste input (textarea with submit button per course)
- [ ] Display per-file extraction status cards (pending, extracting spinner, success with item count, failure with retry)
- [ ] On successful extraction, display deliverable table with editable prep-week fields
- [ ] On failure, show prompt to re-upload or paste text — without clearing other successful extractions
- [ ] Integrate with `api.js` extract endpoint

**Acceptance Criterion:** A user can paste text and see extracted deliverables displayed in a table. A user can upload a PDF and see extraction status. Failed extractions show a retry prompt. Prep-week values are editable before analysis.

---

## Task 9: Implement CommitmentForm component

**Files:** `frontend/src/components/CommitmentForm.jsx`
**Parallelizable:** Yes (alongside Tasks 8, 10, 11)
**Stories:** 4, 5, 6
**Depends on:** Task 7

### Subtasks:
- [ ] Create structured form with labeled number inputs: work hours, commute hours, sleep hours/night, extracurricular hours, leisure hours
- [ ] Add "Add Custom Commitment" button for user-defined entries
- [ ] Add lock toggle per commitment (checkbox or icon button) — locked items visually distinguished
- [ ] Create free-text alternative input (textarea + "Parse" button)
- [ ] On parse success, display parsed commitments for confirmation/editing before accepting
- [ ] Create break week selector (checkboxes or multi-select for weeks 1–15)
- [ ] Integrate with `api.js` commitments/parse endpoint

**Acceptance Criterion:** A user can enter commitments via form fields and mark them as locked. Locked items show a visual indicator. Free-text input triggers parsing and shows results for confirmation. Break weeks can be selected.

---

## Task 10: Implement Timeline and Breakdown visualization components

**Files:** `frontend/src/components/Timeline.jsx`, `frontend/src/components/Breakdown.jsx`
**Parallelizable:** Yes (alongside Tasks 8, 9, 11)
**Stories:** 10, 11
**Depends on:** Task 7

### Subtasks:
- [ ] Implement `Timeline.jsx` with Chart.js stacked bar chart (weeks on x-axis, hours on y-axis)
- [ ] Color-code stacked bars by course (prep hours) + commitments
- [ ] Highlight over-capacity weeks with red background/border
- [ ] Mark collision weeks with warning indicator
- [ ] Gray out break weeks
- [ ] Implement `Breakdown.jsx` with Chart.js doughnut/pie chart
- [ ] Show each commitment as proportional slice with label + percentage
- [ ] Visually distinguish locked vs unlocked commitments (border style or pattern)

**Acceptance Criterion:** Given an AnalysisResponse, the Timeline renders a stacked bar chart with visible red highlighting on over-capacity weeks and collision indicators. The Breakdown renders a pie chart with labeled slices totaling 100%.

---

## Task 11: Implement Suggestions component

**Files:** `frontend/src/components/Suggestions.jsx`
**Parallelizable:** Yes (alongside Tasks 8, 9, 10)
**Stories:** 9
**Depends on:** Task 7

### Subtasks:
- [ ] Display locked acknowledgment section (what constraints are protected)
- [ ] Render suggestion cards (one per suggestion) showing: description, target commitment, action type, detail, affected weeks
- [ ] Add "Get Suggestions" button that appears only when over-capacity weeks exist
- [ ] Show loading state while suggestions are being generated
- [ ] Integrate with `api.js` suggest endpoint

**Acceptance Criterion:** When over-capacity weeks exist, a "Get Suggestions" button appears. Clicking it shows a loading state, then renders suggestion cards referencing specific commitments. Locked constraints are explicitly acknowledged.

---

## Task 12: Create sample syllabus fixtures

**Files:** `data/sample_syllabi/`
**Parallelizable:** Yes (anytime)
**Stories:** 1, 2 (testing/demo)

### Subtasks:
- [ ] Create `cs101_syllabus.txt` — sample Computer Science syllabus with 4-5 deliverables, mix of exams and assignments
- [ ] Create `eng200_syllabus.txt` — sample English syllabus with essays and presentations
- [ ] Create `math150_syllabus.txt` — sample Math syllabus with weekly quizzes and midterm/final
- [ ] Ensure dates use the fixed semester window (Sept week 2 – Dec week 3)

**Acceptance Criterion:** Each sample file contains realistic syllabus text with identifiable course code, deliverable names, due dates (some absolute, some relative like "Week 6"), and weights.

---

## Task 13: Integration testing and requirements.txt

**Files:** `backend/requirements.txt`, all files
**Parallelizable:** No — final integration. Depends on Tasks 1–11.
**Stories:** All

### Subtasks:
- [ ] Create `backend/requirements.txt` with pinned versions (fastapi, uvicorn, pydantic, pypdf2, boto3, mangum)
- [ ] Create `frontend/package.json` dependencies verified (react, react-dom, chart.js, react-chartjs-2, vite)
- [ ] End-to-end test: paste sample syllabus → extract → enter commitments → analyze → view timeline → get suggestions
- [ ] Verify error handling: submit invalid text → confirm user-friendly error message appears
- [ ] Verify extraction gate: confirm "Run Analysis" is disabled until all extractions succeed
- [ ] Verify recovery floor: create over-loaded schedule → confirm "not feasible" verdict appears

**Acceptance Criterion:** The full app runs locally with two terminals (uvicorn + vite). A user can complete the entire flow from syllabus input to viewing suggestions. No unhandled stack traces appear in any error scenario.

---

## Parallelization Map

```
Task 1 (models.py) ─────────────────────────────────────────────────►
   │
   ├── Task 2 (prompts.py) ──────────────────────────────────────────►
   │
   ├── Task 4 (extractor.py) ────────────────────────────────────────►
   │
   ├── Task 5 (capacity.py) ─────────────────────────────────────────►
   │
   ├── Task 7 (React scaffold) ──┬── Task 8  (SyllabusUpload) ──────►
   │                              ├── Task 9  (CommitmentForm) ──────►
   │                              ├── Task 10 (Timeline/Breakdown) ──►
   │                              └── Task 11 (Suggestions) ─────────►
   │
   ├── Task 3 (bedrock_client) ──────────────────────────────────────►
   │        │
   │        └── Task 6 (main.py routes) ─────────────────────────────►
   │
   └── Task 12 (sample fixtures) ────────────────────────────────────►

                                          Task 13 (integration) ─────►
```

## Developer Assignment Suggestion (3 devs, 8 hours)

| Developer | Tasks | Focus Area |
|-----------|-------|------------|
| Dev A (Backend) | 1 → 2 → 3 → 6 | Schemas, prompts, Bedrock client, API routes |
| Dev B (Backend + Charts) | 5 → 4 → 10 → 13 | Capacity logic, PDF extraction, Timeline/Breakdown charts, integration |
| Dev C (Frontend) | 7 → 8 → 9 → 11 | React scaffold, SyllabusUpload, CommitmentForm, Suggestions |

Dev B takes the visualization components (Task 10) because they finish `capacity.py` around midday and know the AnalysisResponse data shape best. Charts are self-contained — they take an AnalysisResponse and render it, no coupling to the rest of the UI.

Dev A and Dev C can start in parallel once Task 1 is committed (the shared contract).
