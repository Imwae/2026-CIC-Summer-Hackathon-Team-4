import { useReducer } from 'react'
import SyllabusUpload from './components/SyllabusUpload'
import CommitmentForm from './components/CommitmentForm'
import Breakdown from './components/Breakdown'
import Suggestions from './components/Suggestions'
import { analyzeSemester, getSuggestions } from './api'
import './App.css'

// --- Phase Constants ---
// The app progresses through these phases linearly:
// input → analyzing → results → suggesting → results
const PHASES = {
  INPUT: 'input',
  ANALYZING: 'analyzing',
  RESULTS: 'results',
  SUGGESTING: 'suggesting',
}

// --- Action Types ---
const Actions = {
  SET_PHASE: 'SET_PHASE',
  ADD_COURSE: 'ADD_COURSE',
  UPDATE_COURSE_STATUS: 'UPDATE_COURSE_STATUS',
  SET_EXTRACTION_RESULT: 'SET_EXTRACTION_RESULT',
  UPDATE_DELIVERABLE: 'UPDATE_DELIVERABLE',
  SET_COMMITMENTS: 'SET_COMMITMENTS',
  UPDATE_COMMITMENT: 'UPDATE_COMMITMENT',
  ADD_COMMITMENT: 'ADD_COMMITMENT',
  TOGGLE_LOCK: 'TOGGLE_LOCK',
  SET_BREAK_WEEKS: 'SET_BREAK_WEEKS',
  SET_ANALYSIS_RESULT: 'SET_ANALYSIS_RESULT',
  SET_SUGGESTIONS: 'SET_SUGGESTIONS',
  SET_ERROR: 'SET_ERROR',
  CLEAR_ERROR: 'CLEAR_ERROR',
  SET_LOADING: 'SET_LOADING',
}

// --- Initial State ---
const initialState = {
  // Phase tracking
  appPhase: PHASES.INPUT,

  // Syllabus data — each course tracks its own extraction status
  courses: [],

  // Commitments entered by the student
  commitments: [],

  // Week numbers the student marks as breaks (reading week, holidays)
  breakWeeks: [],

  // Results from the /api/analyze endpoint
  analysisResult: null,

  // Results from the /api/suggest endpoint
  suggestions: null,

  // UI state
  error: null,
  loading: false,
}

// --- Reducer ---
function appReducer(state, action) {
  switch (action.type) {
    // Phase transitions
    case Actions.SET_PHASE:
      return { ...state, appPhase: action.payload }

    // --- Course management ---
    case Actions.ADD_COURSE:
      return {
        ...state,
        courses: [
          ...state.courses,
          {
            id: action.payload.id,
            fileName: action.payload.fileName,
            status: 'pending',
            extractionResult: null,
            errorMessage: null,
          },
        ],
      }

    case Actions.UPDATE_COURSE_STATUS:
      return {
        ...state,
        courses: state.courses.map((course) =>
          course.id === action.payload.id
            ? {
                ...course,
                status: action.payload.status,
                errorMessage: action.payload.errorMessage ?? course.errorMessage,
              }
            : course
        ),
      }

    case Actions.SET_EXTRACTION_RESULT:
      return {
        ...state,
        courses: state.courses.map((course) =>
          course.id === action.payload.id
            ? {
                ...course,
                status: 'success',
                extractionResult: action.payload.result,
              }
            : course
        ),
      }

    case Actions.UPDATE_DELIVERABLE: {
      const { courseId, deliverableIndex, prepWeeks } = action.payload
      return {
        ...state,
        courses: state.courses.map((course) => {
          if (course.id !== courseId) return course
          const deliverables = course.extractionResult.deliverables.map(
            (d, idx) => {
              if (idx !== deliverableIndex) return d
              // Recalculate estimated_hours_total proportionally
              const ratio = prepWeeks / (d.estimated_prep_weeks || 1)
              return {
                ...d,
                estimated_prep_weeks: prepWeeks,
                estimated_hours_total: Math.round(d.estimated_hours_total * ratio * 10) / 10,
              }
            }
          )
          return {
            ...course,
            extractionResult: {
              ...course.extractionResult,
              deliverables,
            },
          }
        }),
      }
    }

    // --- Commitment management ---
    case Actions.SET_COMMITMENTS:
      // Replace all commitments (e.g., after free-text parse)
      return { ...state, commitments: action.payload }

    case Actions.UPDATE_COMMITMENT:
      return {
        ...state,
        commitments: state.commitments.map((c, idx) =>
          idx === action.payload.index ? { ...c, ...action.payload.updates } : c
        ),
      }

    case Actions.ADD_COMMITMENT:
      return {
        ...state,
        commitments: [...state.commitments, action.payload],
      }

    case Actions.TOGGLE_LOCK:
      return {
        ...state,
        commitments: state.commitments.map((c, idx) =>
          idx === action.payload ? { ...c, locked: !c.locked } : c
        ),
      }

    // --- Break weeks ---
    case Actions.SET_BREAK_WEEKS:
      return { ...state, breakWeeks: action.payload }

    // --- Analysis & Suggestions ---
    case Actions.SET_ANALYSIS_RESULT:
      return {
        ...state,
        analysisResult: action.payload,
        appPhase: PHASES.RESULTS,
        loading: false,
      }

    case Actions.SET_SUGGESTIONS:
      return {
        ...state,
        suggestions: action.payload,
        appPhase: PHASES.RESULTS,
        loading: false,
      }

    // --- UI state ---
    case Actions.SET_ERROR:
      return { ...state, error: action.payload, loading: false }

    case Actions.CLEAR_ERROR:
      return { ...state, error: null }

    case Actions.SET_LOADING:
      return { ...state, loading: action.payload }

    default:
      return state
  }
}

// --- Gate condition helper ---
// "Run Analysis" is only enabled when ALL courses extracted successfully
// AND the student has entered at least one commitment.
function canRunAnalysis(state) {
  const hasSuccessfulCourses =
    state.courses.length > 0 &&
    state.courses.every((c) => c.status === 'success')
  const hasCommitments = state.commitments.length > 0
  return hasSuccessfulCourses && hasCommitments
}

// --- App Component ---
function App() {
  const [state, dispatch] = useReducer(appReducer, initialState)

  // Handler: call the analysis API
  const handleRunAnalysis = async () => {
    if (!canRunAnalysis(state)) return
    dispatch({ type: Actions.SET_PHASE, payload: PHASES.ANALYZING })
    dispatch({ type: Actions.SET_LOADING, payload: true })

    try {
      // Build courses array from extraction results, sanitizing types
      const courses = state.courses.map((c) => ({
        course_code: c.extractionResult.course_code || 'UNKNOWN',
        course_name: c.extractionResult.course_name || c.fileName || 'Unknown Course',
        deliverables: (c.extractionResult.deliverables || []).map((d) => ({
          name: d.name || 'Unnamed',
          type: ['exam', 'essay', 'project', 'presentation', 'lab', 'other'].includes(d.type) ? d.type : 'other',
          due_date: d.due_date || null,
          week_number: parseInt(d.week_number, 10) || 1,
          weight_percent: d.weight_percent != null ? parseFloat(d.weight_percent) : null,
          estimated_prep_weeks: parseInt(d.estimated_prep_weeks, 10) || 1,
          estimated_hours_total: parseFloat(d.estimated_hours_total) || 1.0,
        })),
      }))

      // Sanitize commitments to match expected schema
      const commitments = state.commitments.map((c) => ({
        name: c.name || 'Unknown',
        category: ['work', 'commute', 'sleep', 'extracurricular', 'leisure', 'other'].includes(c.category) ? c.category : 'other',
        hours_per_week: parseFloat(c.hours_per_week) || 0,
        locked: Boolean(c.locked),
      }))

      const result = await analyzeSemester({
        courses,
        commitments,
        breakWeeks: state.breakWeeks,
        semesterStart: '2025-09-08',  // TODO: make configurable via date picker
        semesterEnd: '2025-12-22',    // TODO: make configurable via date picker
      })

      dispatch({ type: Actions.SET_ANALYSIS_RESULT, payload: result })
    } catch (err) {
      dispatch({ type: Actions.SET_ERROR, payload: err.message })
      dispatch({ type: Actions.SET_PHASE, payload: PHASES.INPUT })
    }
  }

  // Handler: transition to suggesting phase and call API
  const handleGetSuggestions = async () => {
    dispatch({ type: Actions.SET_PHASE, payload: PHASES.SUGGESTING })
    dispatch({ type: Actions.SET_LOADING, payload: true })
    try {
      const result = await getSuggestions({
        analysisResult: state.analysisResult,
        commitments: state.commitments,
      })
      dispatch({ type: Actions.SET_SUGGESTIONS, payload: result })
    } catch (err) {
      dispatch({ type: Actions.SET_ERROR, payload: err.message })
      dispatch({ type: Actions.SET_PHASE, payload: PHASES.RESULTS })
    }
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <h1>Semester Capacity Planner</h1>
      </header>

      {/* Error banner */}
      {state.error && (
        <div className="error-banner" role="alert">
          <p>{state.error}</p>
          <button
            type="button"
            onClick={() => dispatch({ type: Actions.CLEAR_ERROR })}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Main content — conditional on phase */}
      <main className="app-main">
        {/* Input phase: syllabus upload + commitment form */}
        {state.appPhase === PHASES.INPUT && (
          <section className="phase-input">
            <SyllabusUpload dispatch={dispatch} courses={state.courses} />

            <CommitmentForm dispatch={dispatch} commitments={state.commitments} breakWeeks={state.breakWeeks} />

            {/* Run Analysis button — disabled until gate condition met */}
            <button
              type="button"
              className="btn-primary"
              disabled={!canRunAnalysis(state)}
              onClick={handleRunAnalysis}
            >
              Run Analysis
            </button>
          </section>
        )}

        {/* Analyzing phase: loading indicator */}
        {state.appPhase === PHASES.ANALYZING && (
          <section className="phase-analyzing">
            <p>Analyzing your semester...</p>
          </section>
        )}

        {/* Results phase: timeline + breakdown + suggestions */}
        {state.appPhase === PHASES.RESULTS && (
          <section className="phase-results">
            {/* Placeholder for Timeline component */}
            <div className="placeholder" data-component="Timeline">
              <p>Timeline (placeholder)</p>
            </div>

            {/* Breakdown component — pie chart of commitment proportions */}
            <Breakdown commitments={state.commitments} />

            {/* Suggestions component — shows button when over-capacity, then renders cards */}
            <Suggestions
              suggestions={state.suggestions}
              commitments={state.commitments}
              analysisResult={state.analysisResult}
              onGetSuggestions={handleGetSuggestions}
              loading={state.loading}
            />
          </section>
        )}

        {/* Suggesting phase: loading indicator for suggestion generation */}
        {state.appPhase === PHASES.SUGGESTING && (
          <section className="phase-suggesting">
            <p>Generating suggestions...</p>
          </section>
        )}
      </main>
    </div>
  )
}

export { PHASES, Actions, initialState, appReducer, canRunAnalysis }
export default App
