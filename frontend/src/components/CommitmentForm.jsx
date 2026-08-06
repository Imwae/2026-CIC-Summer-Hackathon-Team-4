import { useEffect, useState } from 'react'
import { Actions } from '../App'
import { parseCommitments } from '../api'
import './CommitmentForm.css'

/**
 * Default commitments — initialized when the component mounts if
 * the parent state has no commitments yet.
 */
const DEFAULT_COMMITMENTS = [
  { name: 'Work', category: 'work', hours_per_week: 0, locked: false },
  { name: 'Commute', category: 'commute', hours_per_week: 0, locked: false },
  { name: 'Sleep', category: 'sleep', hours_per_week: 8, locked: false },
  { name: 'Extracurricular', category: 'extracurricular', hours_per_week: 0, locked: false },
  { name: 'Leisure', category: 'leisure', hours_per_week: 10, locked: false },
]

/**
 * The set of default category names used to distinguish
 * custom commitments from built-in ones.
 */
const DEFAULT_CATEGORIES = new Set(
  DEFAULT_COMMITMENTS.map((c) => c.category)
)

/**
 * Field definitions for the 5 structured inputs.
 * Each entry maps to a category in the commitments array.
 */
const FIELDS = [
  {
    category: 'work',
    label: 'Work hours',
    unit: 'per week',
    min: 0,
    max: 80,
    step: 1,
  },
  {
    category: 'commute',
    label: 'Commute hours',
    unit: 'per week',
    min: 0,
    max: 40,
    step: 0.5,
  },
  {
    category: 'sleep',
    label: 'Sleep hours',
    unit: 'per night',
    min: 0,
    max: 16,
    step: 0.5,
  },
  {
    category: 'extracurricular',
    label: 'Extracurricular hours',
    unit: 'per week',
    min: 0,
    max: 40,
    step: 1,
  },
  {
    category: 'leisure',
    label: 'Leisure hours',
    unit: 'per week',
    min: 0,
    max: 60,
    step: 1,
  },
]

/**
 * Total number of weeks in the semester.
 */
const SEMESTER_WEEKS = 15

/**
 * CommitmentForm — Structured number inputs for the student's weekly commitments.
 *
 * Renders 5 labeled fields (work, commute, sleep, extracurricular, leisure)
 * plus a break week selector and a section for user-defined custom commitments.
 *
 * @param {{ dispatch: Function, commitments: Array, breakWeeks: number[] }} props
 */
function CommitmentForm({ dispatch, commitments = [], breakWeeks = [] }) {
  const [showAddForm, setShowAddForm] = useState(false)
  const [customName, setCustomName] = useState('')
  const [customHours, setCustomHours] = useState('')
  const [freeText, setFreeText] = useState('')
  const [isParsing, setIsParsing] = useState(false)
  const [parseError, setParseError] = useState(null)
  const [parsedResults, setParsedResults] = useState(null)

  // Initialize default commitments if none exist
  useEffect(() => {
    if (commitments.length === 0) {
      dispatch({ type: Actions.SET_COMMITMENTS, payload: DEFAULT_COMMITMENTS })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * Find the index + value for a given category in the commitments array.
   */
  const getCommitment = (category) => {
    const index = commitments.findIndex((c) => c.category === category)
    if (index === -1) return { index: -1, value: 0 }
    return { index, value: commitments[index].hours_per_week }
  }

  /**
   * Toggle a week number in the breakWeeks array. Dispatches SET_BREAK_WEEKS
   * with the updated array of selected week numbers.
   */
  const handleBreakWeekToggle = (weekNumber) => {
    const updated = breakWeeks.includes(weekNumber)
      ? breakWeeks.filter((w) => w !== weekNumber)
      : [...breakWeeks, weekNumber].sort((a, b) => a - b)
    dispatch({ type: Actions.SET_BREAK_WEEKS, payload: updated })
  }

  /**
   * Handle value change for a field. Dispatches UPDATE_COMMITMENT with the new hours_per_week.
   */
  const handleChange = (category, rawValue) => {
    const { index } = getCommitment(category)
    if (index === -1) return

    const value = parseFloat(rawValue) || 0
    dispatch({
      type: Actions.UPDATE_COMMITMENT,
      payload: { index, updates: { hours_per_week: value } },
    })
  }

  /**
   * Get custom commitments (those not in the default categories).
   */
  const customCommitments = commitments
    .map((c, idx) => ({ ...c, originalIndex: idx }))
    .filter((c) => !DEFAULT_CATEGORIES.has(c.category))

  /**
   * Handle adding a new custom commitment.
   */
  const handleAddCustom = () => {
    const trimmedName = customName.trim()
    if (!trimmedName) return

    const hours = parseFloat(customHours) || 0
    dispatch({
      type: Actions.ADD_COMMITMENT,
      payload: {
        name: trimmedName,
        category: 'other',
        hours_per_week: hours,
        locked: false,
      },
    })

    // Reset form
    setCustomName('')
    setCustomHours('')
    setShowAddForm(false)
  }

  /**
   * Handle removing a custom commitment by filtering it out.
   */
  const handleRemoveCustom = (originalIndex) => {
    const updated = commitments.filter((_, idx) => idx !== originalIndex)
    dispatch({ type: Actions.SET_COMMITMENTS, payload: updated })
  }

  /**
   * Handle editing hours for a custom commitment.
   */
  const handleCustomHoursChange = (originalIndex, rawValue) => {
    const value = parseFloat(rawValue) || 0
    dispatch({
      type: Actions.UPDATE_COMMITMENT,
      payload: { index: originalIndex, updates: { hours_per_week: value } },
    })
  }

  /**
   * Handle parsing free-text schedule description into structured commitments.
   * Stores results in local state for user review before dispatching.
   */
  const handleParse = async () => {
    const trimmed = freeText.trim()
    if (!trimmed) return

    setIsParsing(true)
    setParseError(null)

    try {
      const result = await parseCommitments(trimmed)
      const parsed = result.commitments || result
      // Ensure each parsed commitment has a locked field
      const normalized = parsed.map((c) => ({
        name: c.name || '',
        category: c.category || 'other',
        hours_per_week: c.hours_per_week ?? 0,
        locked: c.locked ?? false,
      }))
      setParsedResults(normalized)
    } catch (err) {
      setParseError(err.message || 'Failed to parse commitments. Please try again.')
    } finally {
      setIsParsing(false)
    }
  }

  /**
   * Accept parsed results — dispatch to parent state and clear local parsed state.
   */
  const handleAcceptParsed = () => {
    if (!parsedResults) return
    dispatch({ type: Actions.SET_COMMITMENTS, payload: parsedResults })
    setParsedResults(null)
    setFreeText('')
  }

  /**
   * Cancel parsed results — discard and return to free-text input.
   */
  const handleCancelParsed = () => {
    setParsedResults(null)
  }

  /**
   * Update a field in one of the parsed results during confirmation.
   */
  const handleParsedItemChange = (index, field, value) => {
    setParsedResults((prev) =>
      prev.map((item, i) =>
        i === index ? { ...item, [field]: value } : item
      )
    )
  }

  return (
    <section className="commitment-form" aria-label="Weekly commitments">
      <h2 className="commitment-form__title">Weekly Commitments</h2>
      <p className="commitment-form__description">
        Enter your regular weekly time commitments so we can calculate your available study hours.
      </p>

      <div className="commitment-form__fields">
        {FIELDS.map((field) => {
          const { index, value } = getCommitment(field.category)
          const isLocked = index !== -1 && commitments[index]?.locked
          const inputId = `commitment-${field.category}`

          return (
            <div
              key={field.category}
              className={`commitment-form__field${isLocked ? ' commitment-form__field--locked' : ''}`}
            >
              <label
                htmlFor={inputId}
                className="commitment-form__label"
              >
                {field.label}
                <span className="commitment-form__unit">({field.unit})</span>
              </label>
              <div className="commitment-form__input-row">
                <input
                  id={inputId}
                  type="number"
                  className="commitment-form__input"
                  min={field.min}
                  max={field.max}
                  step={field.step}
                  value={value}
                  onChange={(e) => handleChange(field.category, e.target.value)}
                  aria-describedby={`${inputId}-hint`}
                />
                <button
                  type="button"
                  className={`commitment-form__lock-btn${isLocked ? ' commitment-form__lock-btn--active' : ''}`}
                  onClick={() => dispatch({ type: Actions.TOGGLE_LOCK, payload: index })}
                  aria-label={isLocked ? `Unlock ${field.label}` : `Lock ${field.label}`}
                  aria-pressed={isLocked}
                >
                  {isLocked ? '🔒' : '🔓'}
                </button>
              </div>
              <span id={`${inputId}-hint`} className="commitment-form__hint">
                {field.min}–{field.max} hours
              </span>
            </div>
          )
        })}
      </div>

      {/* Break week selector */}
      <fieldset className="commitment-form__break-section" aria-label="Break weeks">
        <legend className="commitment-form__break-legend">Break Weeks</legend>
        <p className="commitment-form__break-description">
          Select weeks you won't be studying (reading week, holidays, etc.). These are excluded from capacity calculations.
        </p>
        <div className="commitment-form__break-grid">
          {Array.from({ length: SEMESTER_WEEKS }, (_, i) => i + 1).map((week) => {
            const isChecked = breakWeeks.includes(week)
            const checkboxId = `break-week-${week}`
            return (
              <label
                key={week}
                htmlFor={checkboxId}
                className={`commitment-form__break-chip${isChecked ? ' commitment-form__break-chip--selected' : ''}`}
              >
                <input
                  id={checkboxId}
                  type="checkbox"
                  className="commitment-form__break-checkbox"
                  checked={isChecked}
                  onChange={() => handleBreakWeekToggle(week)}
                  aria-label={`Week ${week}`}
                />
                <span className="commitment-form__break-chip-text">{week}</span>
              </label>
            )
          })}
        </div>
        {breakWeeks.length > 0 && (
          <p className="commitment-form__break-summary" aria-live="polite">
            {breakWeeks.length} break {breakWeeks.length === 1 ? 'week' : 'weeks'} selected
          </p>
        )}
      </fieldset>

      {/* Free-text alternative input section */}
      <div className="commitment-form__freetext-section" aria-label="Describe your week in free text">
        <div className="commitment-form__freetext-divider">
          <span className="commitment-form__freetext-divider-text">Or describe your week</span>
        </div>

        {/* Show confirmation UI when parsed results are available */}
        {parsedResults ? (
          <div
            className="commitment-form__parsed-confirmation"
            role="region"
            aria-label="Parsed commitments for review"
          >
            <h3 className="commitment-form__parsed-heading">
              Parsed Commitments — Review &amp; Edit
            </h3>
            <p className="commitment-form__parsed-description">
              Review the parsed commitments below. Edit names or hours, toggle locks, then accept or cancel.
            </p>

            <div className="commitment-form__parsed-list">
              {parsedResults.map((item, index) => {
                const nameId = `parsed-name-${index}`
                const hoursId = `parsed-hours-${index}`
                return (
                  <div
                    key={index}
                    className={`commitment-form__parsed-item${item.locked ? ' commitment-form__parsed-item--locked' : ''}`}
                  >
                    <div className="commitment-form__parsed-item-fields">
                      <div className="commitment-form__parsed-item-field">
                        <label htmlFor={nameId} className="commitment-form__label">
                          Name
                        </label>
                        <input
                          id={nameId}
                          type="text"
                          className="commitment-form__input commitment-form__input--text"
                          value={item.name}
                          onChange={(e) =>
                            handleParsedItemChange(index, 'name', e.target.value)
                          }
                          aria-label={`Commitment name ${index + 1}`}
                        />
                      </div>
                      <div className="commitment-form__parsed-item-field commitment-form__parsed-item-field--category">
                        <span className="commitment-form__label">Category</span>
                        <span className="commitment-form__parsed-category">
                          {item.category}
                        </span>
                      </div>
                      <div className="commitment-form__parsed-item-field">
                        <label htmlFor={hoursId} className="commitment-form__label">
                          Hours/week
                        </label>
                        <input
                          id={hoursId}
                          type="number"
                          className="commitment-form__input"
                          min={0}
                          max={80}
                          step={0.5}
                          value={item.hours_per_week}
                          onChange={(e) =>
                            handleParsedItemChange(
                              index,
                              'hours_per_week',
                              parseFloat(e.target.value) || 0
                            )
                          }
                          aria-label={`${item.name} hours per week`}
                        />
                      </div>
                      <div className="commitment-form__parsed-item-field commitment-form__parsed-item-field--lock">
                        <span className="commitment-form__label">Lock</span>
                        <button
                          type="button"
                          className={`commitment-form__lock-btn${item.locked ? ' commitment-form__lock-btn--active' : ''}`}
                          onClick={() =>
                            handleParsedItemChange(index, 'locked', !item.locked)
                          }
                          aria-label={item.locked ? `Unlock ${item.name}` : `Lock ${item.name}`}
                          aria-pressed={item.locked}
                        >
                          {item.locked ? '🔒' : '🔓'}
                        </button>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            <div className="commitment-form__parsed-actions">
              <button
                type="button"
                className="commitment-form__parsed-accept-btn"
                onClick={handleAcceptParsed}
              >
                Accept
              </button>
              <button
                type="button"
                className="commitment-form__parsed-cancel-btn"
                onClick={handleCancelParsed}
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <>
            <label htmlFor="freetext-schedule" className="commitment-form__freetext-label">
              Describe your typical weekly schedule
            </label>
            <textarea
              id="freetext-schedule"
              className="commitment-form__freetext-textarea"
              placeholder="e.g. I work 20 hours a week at a coffee shop, commute about 5 hours total, sleep 7 hours a night, and spend around 6 hours on clubs and sports..."
              value={freeText}
              onChange={(e) => {
                setFreeText(e.target.value)
                if (parseError) setParseError(null)
              }}
              disabled={isParsing}
              rows={4}
              aria-describedby="freetext-hint"
            />
            <span id="freetext-hint" className="commitment-form__freetext-hint">
              We'll use AI to parse this into structured commitments for you.
            </span>

            {parseError && (
              <p className="commitment-form__freetext-error" role="alert">
                {parseError}
              </p>
            )}

            <button
              type="button"
              className="commitment-form__freetext-parse-btn"
              onClick={handleParse}
              disabled={isParsing || !freeText.trim()}
              aria-busy={isParsing}
            >
              {isParsing ? 'Parsing...' : 'Parse'}
            </button>
          </>
        )}
      </div>

      {/* Custom commitments section */}
      <div className="commitment-form__custom-section" aria-label="Custom commitments">
        {customCommitments.length > 0 && (
          <div className="commitment-form__custom-list">
            <h3 className="commitment-form__custom-heading">Custom Commitments</h3>
            {customCommitments.map((c) => {
              const inputId = `commitment-custom-${c.originalIndex}`
              const isLocked = c.locked
              return (
                <div
                  key={c.originalIndex}
                  className={`commitment-form__custom-item${isLocked ? ' commitment-form__custom-item--locked' : ''}`}
                >
                  <label htmlFor={inputId} className="commitment-form__custom-name">
                    {c.name}
                  </label>
                  <input
                    id={inputId}
                    type="number"
                    className="commitment-form__input"
                    min={0}
                    max={80}
                    step={1}
                    value={c.hours_per_week}
                    onChange={(e) =>
                      handleCustomHoursChange(c.originalIndex, e.target.value)
                    }
                    aria-label={`${c.name} hours per week`}
                  />
                  <span className="commitment-form__unit">(per week)</span>
                  <button
                    type="button"
                    className={`commitment-form__lock-btn${isLocked ? ' commitment-form__lock-btn--active' : ''}`}
                    onClick={() => dispatch({ type: Actions.TOGGLE_LOCK, payload: c.originalIndex })}
                    aria-label={isLocked ? `Unlock ${c.name}` : `Lock ${c.name}`}
                    aria-pressed={isLocked}
                  >
                    {isLocked ? '🔒' : '🔓'}
                  </button>
                  <button
                    type="button"
                    className="commitment-form__remove-btn"
                    onClick={() => handleRemoveCustom(c.originalIndex)}
                    aria-label={`Remove ${c.name}`}
                  >
                    Remove
                  </button>
                </div>
              )
            })}
          </div>
        )}

        {/* Add custom commitment button or inline form */}
        {!showAddForm ? (
          <button
            type="button"
            className="commitment-form__add-btn"
            onClick={() => setShowAddForm(true)}
          >
            + Add Custom Commitment
          </button>
        ) : (
          <div className="commitment-form__add-form" role="group" aria-label="Add a custom commitment">
            <div className="commitment-form__add-form-fields">
              <div className="commitment-form__add-form-field">
                <label htmlFor="custom-commitment-name" className="commitment-form__label">
                  Name
                </label>
                <input
                  id="custom-commitment-name"
                  type="text"
                  className="commitment-form__input commitment-form__input--text"
                  placeholder="e.g. Gym, Cooking"
                  value={customName}
                  onChange={(e) => setCustomName(e.target.value)}
                  autoFocus
                />
              </div>
              <div className="commitment-form__add-form-field">
                <label htmlFor="custom-commitment-hours" className="commitment-form__label">
                  Hours per week
                </label>
                <input
                  id="custom-commitment-hours"
                  type="number"
                  className="commitment-form__input"
                  min={0}
                  max={80}
                  step={1}
                  placeholder="0"
                  value={customHours}
                  onChange={(e) => setCustomHours(e.target.value)}
                />
              </div>
            </div>
            <div className="commitment-form__add-form-actions">
              <button
                type="button"
                className="commitment-form__add-form-submit"
                onClick={handleAddCustom}
                disabled={!customName.trim()}
              >
                Add
              </button>
              <button
                type="button"
                className="commitment-form__add-form-cancel"
                onClick={() => {
                  setShowAddForm(false)
                  setCustomName('')
                  setCustomHours('')
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

export default CommitmentForm
