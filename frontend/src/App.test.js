import { describe, it, expect } from 'vitest'
import { canRunAnalysis } from './App'

/**
 * Extraction Gate Tests
 *
 * Validates: Requirement 3 - Extraction Completeness Gate
 * "Run Analysis" is disabled until all uploaded syllabi show successful extraction
 * AND at least one commitment exists.
 */

describe('canRunAnalysis — extraction gate', () => {
  it('returns false when there are no courses uploaded', () => {
    const state = {
      courses: [],
      commitments: [{ name: 'Work', category: 'work', hours_per_week: 10, locked: false }],
    }
    expect(canRunAnalysis(state)).toBe(false)
  })

  it('returns false when any course has status "pending"', () => {
    const state = {
      courses: [
        { id: '1', fileName: 'cs101.pdf', status: 'success', extractionResult: {} },
        { id: '2', fileName: 'eng200.pdf', status: 'pending', extractionResult: null },
      ],
      commitments: [{ name: 'Work', category: 'work', hours_per_week: 10, locked: false }],
    }
    expect(canRunAnalysis(state)).toBe(false)
  })

  it('returns false when any course has status "extracting"', () => {
    const state = {
      courses: [
        { id: '1', fileName: 'cs101.pdf', status: 'extracting', extractionResult: null },
      ],
      commitments: [{ name: 'Work', category: 'work', hours_per_week: 10, locked: false }],
    }
    expect(canRunAnalysis(state)).toBe(false)
  })

  it('returns false when any course has status "failure"', () => {
    const state = {
      courses: [
        { id: '1', fileName: 'cs101.pdf', status: 'success', extractionResult: {} },
        { id: '2', fileName: 'eng200.pdf', status: 'failure', errorMessage: 'Parse error' },
      ],
      commitments: [{ name: 'Work', category: 'work', hours_per_week: 10, locked: false }],
    }
    expect(canRunAnalysis(state)).toBe(false)
  })

  it('returns false when all courses are successful but no commitments exist', () => {
    const state = {
      courses: [
        { id: '1', fileName: 'cs101.pdf', status: 'success', extractionResult: {} },
        { id: '2', fileName: 'eng200.pdf', status: 'success', extractionResult: {} },
      ],
      commitments: [],
    }
    expect(canRunAnalysis(state)).toBe(false)
  })

  it('returns true when ALL courses have status "success" AND at least one commitment exists', () => {
    const state = {
      courses: [
        { id: '1', fileName: 'cs101.pdf', status: 'success', extractionResult: {} },
        { id: '2', fileName: 'eng200.pdf', status: 'success', extractionResult: {} },
        { id: '3', fileName: 'math150.pdf', status: 'success', extractionResult: {} },
      ],
      commitments: [{ name: 'Work', category: 'work', hours_per_week: 10, locked: false }],
    }
    expect(canRunAnalysis(state)).toBe(true)
  })

  it('returns false with a mix of success and failure statuses', () => {
    const state = {
      courses: [
        { id: '1', fileName: 'cs101.pdf', status: 'success', extractionResult: {} },
        { id: '2', fileName: 'eng200.pdf', status: 'failure', errorMessage: 'Bad file' },
        { id: '3', fileName: 'math150.pdf', status: 'success', extractionResult: {} },
      ],
      commitments: [{ name: 'Sleep', category: 'personal', hours_per_week: 56, locked: true }],
    }
    expect(canRunAnalysis(state)).toBe(false)
  })

  it('returns true after a failed file transitions back to success (re-upload scenario)', () => {
    // Simulate: initially a file failed, then user re-uploaded and it succeeded
    const stateAfterReUpload = {
      courses: [
        { id: '1', fileName: 'cs101.pdf', status: 'success', extractionResult: {} },
        { id: '2', fileName: 'eng200.pdf', status: 'success', extractionResult: {} }, // was failure, now success
      ],
      commitments: [{ name: 'Commute', category: 'personal', hours_per_week: 5, locked: false }],
    }
    expect(canRunAnalysis(stateAfterReUpload)).toBe(true)
  })
})
