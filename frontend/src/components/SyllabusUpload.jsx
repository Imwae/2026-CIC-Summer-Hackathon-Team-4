import { useState, useRef, useCallback } from 'react'
import { Actions } from '../App'
import { extractSyllabus } from '../api'
import './SyllabusUpload.css'

/**
 * ExtractionStatusCard — Displays the extraction status for a single course/file.
 * Shows one of four states: pending, extracting, success, or failure.
 *
 * @param {{ course: Object, onRetry: Function }} props
 */
function ExtractionStatusCard({ course, onRetry }) {
  const { id, fileName, status, extractionResult, errorMessage } = course

  const itemCount =
    status === 'success' && extractionResult?.deliverables
      ? extractionResult.deliverables.length
      : 0

  return (
    <div
      className={`status-card status-card--${status}`}
      role="status"
      aria-label={`${fileName}: ${status === 'extracting' ? 'extraction in progress' : status === 'success' ? `extraction complete, ${itemCount} deliverable${itemCount !== 1 ? 's' : ''} found` : status === 'failure' ? `extraction failed: ${errorMessage || 'unknown error'}` : 'pending extraction'}`}
    >
      <div className="status-card__icon" aria-hidden="true">
        {status === 'pending' && (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
        )}
        {status === 'extracting' && (
          <div className="status-card__spinner" role="img" aria-label="Loading" />
        )}
        {status === 'success' && (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
        )}
        {status === 'failure' && (
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
        )}
      </div>

      <div className="status-card__content">
        <span className="status-card__filename">{fileName}</span>
        {status === 'pending' && (
          <span className="status-card__detail">Waiting to extract...</span>
        )}
        {status === 'extracting' && (
          <span className="status-card__detail">Extracting deliverables...</span>
        )}
        {status === 'success' && (
          <span className="status-card__detail">
            {itemCount} deliverable{itemCount !== 1 ? 's' : ''} found
          </span>
        )}
        {status === 'failure' && (
          <span className="status-card__detail status-card__detail--error">
            {errorMessage || 'Extraction failed'}
          </span>
        )}
      </div>

      {status === 'failure' && (
        <button
          type="button"
          className="status-card__retry"
          onClick={() => onRetry(id)}
          aria-label={`Retry extraction for ${fileName}`}
        >
          Retry
        </button>
      )}
    </div>
  )
}

/**
 * FailureRecoveryPrompt — Shown inline below a failed extraction card.
 * Gives the user two options to recover for this specific course:
 *  1. Re-upload a new PDF file
 *  2. Paste syllabus text manually
 *
 * Only affects the single failed course — other courses remain untouched.
 *
 * @param {{ course: Object, dispatch: Function }} props
 */
function FailureRecoveryPrompt({ course, dispatch }) {
  const [pasteText, setPasteText] = useState('')
  const [isRecovering, setIsRecovering] = useState(false)
  const recoveryFileInputRef = useRef(null)

  const handleRecoveryFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Reset input so same file can be selected again
    e.target.value = ''

    setIsRecovering(true)
    dispatch({
      type: Actions.UPDATE_COURSE_STATUS,
      payload: { id: course.id, status: 'extracting', errorMessage: null },
    })

    try {
      const result = await extractSyllabus({
        file,
        fileName: course.fileName,
      })
      dispatch({
        type: Actions.SET_EXTRACTION_RESULT,
        payload: { id: course.id, result },
      })
    } catch (error) {
      dispatch({
        type: Actions.UPDATE_COURSE_STATUS,
        payload: {
          id: course.id,
          status: 'failure',
          errorMessage: error.message || 'Extraction failed',
        },
      })
    } finally {
      setIsRecovering(false)
    }
  }

  const handlePasteSubmit = async () => {
    if (!pasteText.trim()) return

    setIsRecovering(true)
    dispatch({
      type: Actions.UPDATE_COURSE_STATUS,
      payload: { id: course.id, status: 'extracting', errorMessage: null },
    })

    try {
      const result = await extractSyllabus({
        courseText: pasteText.trim(),
        fileName: course.fileName,
      })
      dispatch({
        type: Actions.SET_EXTRACTION_RESULT,
        payload: { id: course.id, result },
      })
      setPasteText('')
    } catch (error) {
      dispatch({
        type: Actions.UPDATE_COURSE_STATUS,
        payload: {
          id: course.id,
          status: 'failure',
          errorMessage: error.message || 'Extraction failed',
        },
      })
    } finally {
      setIsRecovering(false)
    }
  }

  return (
    <div
      className="recovery-prompt"
      role="region"
      aria-label={`Recovery options for ${course.fileName}`}
    >
      <p className="recovery-prompt__message">
        Extraction failed for this course. You can try uploading a different PDF or paste the syllabus text directly.
      </p>

      {/* Option 1: Re-upload a PDF */}
      <div className="recovery-prompt__option">
        <span className="recovery-prompt__option-label">Option 1: Upload a new PDF</span>
        <button
          type="button"
          className="recovery-prompt__upload-btn"
          onClick={() => recoveryFileInputRef.current?.click()}
          disabled={isRecovering}
          aria-label={`Upload a new PDF for ${course.fileName}`}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          Choose PDF
        </button>
        <input
          ref={recoveryFileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          onChange={handleRecoveryFileChange}
          className="upload-zone__input"
          aria-hidden="true"
          tabIndex={-1}
        />
      </div>

      {/* Option 2: Paste text */}
      <div className="recovery-prompt__option">
        <span className="recovery-prompt__option-label">Option 2: Paste syllabus text</span>
        <textarea
          className="recovery-prompt__textarea"
          placeholder="Paste your syllabus text here..."
          rows={5}
          value={pasteText}
          onChange={(e) => setPasteText(e.target.value)}
          disabled={isRecovering}
          aria-label={`Paste syllabus text for ${course.fileName}`}
        />
        <button
          type="button"
          className="recovery-prompt__submit-btn"
          disabled={!pasteText.trim() || isRecovering}
          onClick={handlePasteSubmit}
          aria-label={`Extract pasted text for ${course.fileName}`}
        >
          {isRecovering ? 'Extracting...' : 'Extract from Text'}
        </button>
      </div>
    </div>
  )
}

/**
 * DeliverableTable — Displays extracted deliverables for a course with
 * editable prep-week fields so students can override AI estimates.
 *
 * @param {{ course: Object, dispatch: Function }} props
 */
function DeliverableTable({ course, dispatch }) {
  const { extractionResult } = course
  if (!extractionResult || !extractionResult.deliverables?.length) return null

  const handlePrepWeeksChange = (index, value) => {
    const prepWeeks = Math.max(1, parseInt(value, 10) || 1)
    dispatch({
      type: Actions.UPDATE_DELIVERABLE,
      payload: { courseId: course.id, deliverableIndex: index, prepWeeks },
    })
  }

  return (
    <div className="deliverable-table" aria-label={`Deliverables for ${extractionResult.course_name || course.fileName}`}>
      <h4 className="deliverable-table__title">
        {extractionResult.course_code && `${extractionResult.course_code} — `}
        {extractionResult.course_name || course.fileName}
      </h4>
      <div className="deliverable-table__wrapper">
        <table className="deliverable-table__table">
          <thead>
            <tr>
              <th>Deliverable</th>
              <th>Type</th>
              <th>Due</th>
              <th>Weight</th>
              <th>Prep Weeks</th>
              <th>Est. Hours</th>
            </tr>
          </thead>
          <tbody>
            {extractionResult.deliverables.map((d, idx) => (
              <tr key={idx}>
                <td className="deliverable-table__name">{d.name}</td>
                <td className="deliverable-table__type">
                  <span className={`deliverable-badge deliverable-badge--${d.type}`}>
                    {d.type}
                  </span>
                </td>
                <td className="deliverable-table__due">
                  {d.due_date || `Week ${d.week_number}`}
                </td>
                <td className="deliverable-table__weight">
                  {d.weight_percent != null ? `${d.weight_percent}%` : '—'}
                </td>
                <td className="deliverable-table__prep">
                  <input
                    type="number"
                    className="deliverable-table__prep-input"
                    min={1}
                    max={15}
                    value={d.estimated_prep_weeks}
                    onChange={(e) => handlePrepWeeksChange(idx, e.target.value)}
                    aria-label={`Prep weeks for ${d.name}`}
                  />
                </td>
                <td className="deliverable-table__hours">
                  {d.estimated_hours_total}h
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/**
 * SyllabusUpload — File upload zone with drag-and-drop and file picker for PDFs,
 * plus a text paste input for manually pasting syllabus content.
 *
 * @param {{ dispatch: Function, courses: Array }} props
 */
function SyllabusUpload({ dispatch, courses = [] }) {
  const [isDragging, setIsDragging] = useState(false)
  const [courseText, setCourseText] = useState('')
  const [courseName, setCourseName] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const fileInputRef = useRef(null)

  const handleFiles = useCallback(
    (files) => {
      const pdfFiles = Array.from(files).filter(
        (file) => file.type === 'application/pdf'
      )

      pdfFiles.forEach((file) => {
        const id = crypto.randomUUID()

        // Add course entry
        dispatch({
          type: Actions.ADD_COURSE,
          payload: { id, fileName: file.name },
        })

        // Set status to extracting
        dispatch({
          type: Actions.UPDATE_COURSE_STATUS,
          payload: { id, status: 'extracting' },
        })

        // Call extract API independently for each file
        extractSyllabus({ file, fileName: file.name })
          .then((result) => {
            dispatch({
              type: Actions.SET_EXTRACTION_RESULT,
              payload: { id, result },
            })
          })
          .catch((error) => {
            dispatch({
              type: Actions.UPDATE_COURSE_STATUS,
              payload: {
                id,
                status: 'failure',
                errorMessage: error.message || 'Extraction failed',
              },
            })
          })
      })
    },
    [dispatch]
  )

  const handleDragEnter = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    e.stopPropagation()
    // Only set dragging to false if we're leaving the drop zone entirely
    if (!e.currentTarget.contains(e.relatedTarget)) {
      setIsDragging(false)
    }
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    handleFiles(e.dataTransfer.files)
  }

  const handleFileInputChange = (e) => {
    if (e.target.files.length > 0) {
      handleFiles(e.target.files)
    }
    // Reset input so the same file can be selected again if needed
    e.target.value = ''
  }

  const handleClick = () => {
    fileInputRef.current?.click()
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      fileInputRef.current?.click()
    }
  }

  const handleTextSubmit = async () => {
    if (!courseText.trim() || !courseName.trim()) return

    const id = crypto.randomUUID()
    const fileName = courseName.trim()

    // Add course and set status to extracting
    dispatch({
      type: Actions.ADD_COURSE,
      payload: { id, fileName },
    })
    dispatch({
      type: Actions.UPDATE_COURSE_STATUS,
      payload: { id, status: 'extracting' },
    })

    setIsSubmitting(true)

    try {
      const result = await extractSyllabus({
        courseText: courseText.trim(),
        fileName,
      })

      dispatch({
        type: Actions.SET_EXTRACTION_RESULT,
        payload: { id, result },
      })

      // Clear inputs on success
      setCourseText('')
      setCourseName('')
    } catch (error) {
      dispatch({
        type: Actions.UPDATE_COURSE_STATUS,
        payload: {
          id,
          status: 'failure',
          errorMessage: error.message || 'Extraction failed',
        },
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleRetry = useCallback(
    (courseId) => {
      // Placeholder: reset status to pending so the user can re-attempt
      dispatch({
        type: Actions.UPDATE_COURSE_STATUS,
        payload: { id: courseId, status: 'pending', errorMessage: null },
      })
    },
    [dispatch]
  )

  return (
    <section className="syllabus-upload" aria-label="Syllabus upload">
      <h2 className="syllabus-upload__title">Upload Syllabi</h2>

      {/* File Upload Zone */}
      <div
        className={`upload-zone ${isDragging ? 'upload-zone--dragging' : ''}`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={0}
        aria-label="Upload PDF files. Drag and drop or click to browse."
      >
        <div className="upload-zone__icon" aria-hidden="true">
          <svg
            width="48"
            height="48"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
        </div>
        <p className="upload-zone__text">
          Drag and drop PDF syllabi here, or click to browse
        </p>
        <p className="upload-zone__hint">Accepts .pdf files only</p>
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,application/pdf"
        multiple
        onChange={handleFileInputChange}
        className="upload-zone__input"
        aria-hidden="true"
        tabIndex={-1}
      />

      {/* Text Paste Input */}
      <div className="text-paste" aria-label="Paste syllabus text">
        <h3 className="text-paste__title">Or paste syllabus text</h3>

        <div className="text-paste__field">
          <label htmlFor="course-name" className="text-paste__label">
            Course name
          </label>
          <input
            id="course-name"
            type="text"
            className="text-paste__input"
            placeholder="e.g. CS 101 — Intro to Computer Science"
            value={courseName}
            onChange={(e) => setCourseName(e.target.value)}
            disabled={isSubmitting}
            aria-required="true"
          />
        </div>

        <div className="text-paste__field">
          <label htmlFor="syllabus-text" className="text-paste__label">
            Syllabus content
          </label>
          <textarea
            id="syllabus-text"
            className="text-paste__textarea"
            placeholder="Paste your syllabus text here..."
            rows={8}
            value={courseText}
            onChange={(e) => setCourseText(e.target.value)}
            disabled={isSubmitting}
            aria-required="true"
          />
        </div>

        <button
          type="button"
          className="text-paste__submit"
          disabled={!courseText.trim() || !courseName.trim() || isSubmitting}
          onClick={handleTextSubmit}
          aria-label="Extract syllabus from pasted text"
        >
          {isSubmitting ? 'Extracting...' : 'Extract Syllabus'}
        </button>
      </div>

      {/* Extraction Status Cards */}
      {courses.length > 0 && (
        <div
          className="extraction-status-list"
          aria-label="Extraction status for uploaded files"
          role="region"
        >
          <h3 className="extraction-status-list__title">Uploaded Courses</h3>
          <ul className="extraction-status-list__items" aria-live="polite">
            {courses.map((course) => (
              <li key={course.id} className="extraction-status-list__item">
                <ExtractionStatusCard course={course} onRetry={handleRetry} />
                {course.status === 'failure' && (
                  <FailureRecoveryPrompt course={course} dispatch={dispatch} />
                )}
                {course.status === 'success' && (
                  <DeliverableTable course={course} dispatch={dispatch} />
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

export default SyllabusUpload
