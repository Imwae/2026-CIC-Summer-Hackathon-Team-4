/**
 * API fetch helpers for the Semester Capacity Planner.
 *
 * All endpoints use native fetch with relative paths (Vite proxies /api → backend).
 * On failure, each helper throws an Error with the backend's error message.
 */

/**
 * Internal helper — checks response.ok and throws with the backend error message
 * if the request failed.
 */
async function handleResponse(response) {
  if (!response.ok) {
    let message = `Request failed with status ${response.status}`
    try {
      const errorData = await response.json()
      if (errorData.message) {
        message = errorData.message
      }
    } catch {
      // Response body wasn't valid JSON — keep default message
    }
    throw new Error(message)
  }
  return response.json()
}

/**
 * Extract deliverables from a syllabus.
 *
 * Supports two modes:
 *  1. Text paste — sends JSON body with course_text and file_name.
 *  2. PDF upload — sends multipart/form-data with a File object and file_name.
 *
 * @param {{ courseText?: string, file?: File, fileName: string }} params
 * @returns {Promise<object>} Parsed extraction response
 */
export async function extractSyllabus({ courseText, file, fileName }) {
  let response

  if (file) {
    // PDF upload mode — multipart/form-data
    const formData = new FormData()
    formData.append('file', file)
    formData.append('file_name', fileName)

    response = await fetch('/api/extract', {
      method: 'POST',
      body: formData,
      // Let the browser set the Content-Type with the correct boundary
    })
  } else {
    // Text paste mode — JSON body
    response = await fetch('/api/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        course_text: courseText,
        file_name: fileName,
      }),
    })
  }

  return handleResponse(response)
}

/**
 * Parse free-text commitment descriptions into structured commitment objects.
 *
 * @param {string} text — free-text description of a typical week
 * @returns {Promise<object>} Parsed commitments response
 */
export async function parseCommitments(text) {
  const response = await fetch('/api/commitments/parse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })

  return handleResponse(response)
}

/**
 * Run the semester feasibility analysis.
 *
 * @param {{ courses: Array, commitments: Array, breakWeeks: number[], semesterStart: string, semesterEnd: string }} params
 * @returns {Promise<object>} Analysis result
 */
export async function analyzeSemester({ courses, commitments, breakWeeks, semesterStart, semesterEnd }) {
  const response = await fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      courses,
      commitments,
      break_weeks: breakWeeks,
      semester_start: semesterStart,
      semester_end: semesterEnd,
    }),
  })

  return handleResponse(response)
}

/**
 * Get AI-generated suggestions to resolve over-capacity weeks.
 *
 * @param {{ analysisResult: object, commitments: Array }} params
 * @returns {Promise<object>} Suggestions response
 */
export async function getSuggestions({ analysisResult, commitments }) {
  const response = await fetch('/api/suggest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      analysis_result: analysisResult,
      commitments,
    }),
  })

  return handleResponse(response)
}
