import { useReducer } from 'react'
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

  // Handler: transition to analyzing phase
  const handleRunAnalysis = () => {
    if (!canRunAnalysis(state)) return
    dispatch({ type: Actions.SET_PHASE, payload: PHASES.ANALYZING })
    dispatch({ type: Actions.SET_LOADING, payload: true })
    // Actual API call will be wired in api.js integration task
  }

  // Handler: transition to suggesting phase
  const handleGetSuggestions = () => {
    dispatch({ type: Actions.SET_PHASE, payload: PHASES.SUGGESTING })
    dispatch({ type: Actions.SET_LOADING, payload: true })
    // Actual API call will be wired in api.js integration task
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
            {/* Placeholder for SyllabusUpload component */}
            <div className="placeholder" data-component="SyllabusUpload">
              <p>Syllabus Upload (placeholder)</p>
            </div>

            {/* Placeholder for CommitmentForm component */}
            <div className="placeholder" data-component="CommitmentForm">
              <p>Commitment Form (placeholder)</p>
            </div>

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

        {/* Results phase: timeline + breakdown + optional suggestions trigger */}
        {state.appPhase === PHASES.RESULTS && (
          <section className="phase-results">
            {/* Placeholder for Timeline component */}
            <div className="placeholder" data-component="Timeline">
              <p>Timeline (placeholder)</p>
            </div>

            {/* Placeholder for Breakdown component */}
            <div className="placeholder" data-component="Breakdown">
              <p>Breakdown (placeholder)</p>
            </div>

            {/* Get Suggestions button — shown when over-capacity weeks exist */}
            {state.analysisResult && (
              <button
                type="button"
                className="btn-secondary"
                onClick={handleGetSuggestions}
              >
                Get Suggestions
              </button>
            )}

            {/* Placeholder for Suggestions component */}
            {state.suggestions && (
              <div className="placeholder" data-component="Suggestions">
                <p>Suggestions (placeholder)</p>
              </div>
            )}
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
