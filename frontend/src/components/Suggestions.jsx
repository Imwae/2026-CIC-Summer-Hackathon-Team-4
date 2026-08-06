/**
 * Suggestions component — displays a "Get Suggestions" button when over-capacity
 * weeks exist, shows loading state while generating, and renders locked constraint
 * acknowledgment and AI-generated schedule suggestions once available.
 *
 * Props:
 *   suggestions: SuggestionResponse object { suggestions: [], locked_acknowledgment: string } | null
 *   commitments: array of { name, category, hours_per_week, locked }
 *   analysisResult: AnalysisResponse object with weeks[] array | null
 *   onGetSuggestions: callback to trigger suggestion generation
 *   loading: boolean indicating suggestion generation in progress
 */
export default function Suggestions({ suggestions, commitments, analysisResult, onGetSuggestions, loading }) {
  // Determine if there are over-capacity weeks
  const hasOverCapacityWeeks =
    analysisResult &&
    Array.isArray(analysisResult.weeks) &&
    analysisResult.weeks.some((w) => w.over_capacity === true)

  // Show "Get Suggestions" button when over-capacity weeks exist,
  // suggestions haven't been loaded yet, and we're not currently loading
  const showButton = hasOverCapacityWeeks && !suggestions && !loading

  // Show loading state
  const showLoading = loading && !suggestions

  // If no suggestions loaded and no reason to show the button or loading, render nothing
  if (!suggestions && !showButton && !showLoading) {
    return null
  }

  // If suggestions haven't loaded yet, show button or loading state
  if (!suggestions) {
    return (
      <div style={styles.container}>
        {showButton && (
          <button
            type="button"
            style={styles.getSuggestionsButton}
            onClick={onGetSuggestions}
            aria-label="Get AI suggestions to resolve over-capacity weeks"
          >
            💡 Get Suggestions
          </button>
        )}
        {showLoading && (
          <div style={styles.loadingState} role="status" aria-label="Generating suggestions">
            <span style={styles.loadingSpinner} aria-hidden="true">⏳</span>
            <p style={styles.loadingText}>Generating suggestions...</p>
          </div>
        )}
      </div>
    )
  }

  const { suggestions: suggestionList = [], locked_acknowledgment } = suggestions
  const lockedCommitments = (commitments || []).filter((c) => c.locked)

  return (
    <div style={styles.container}>
      {/* Locked Acknowledgment Section */}
      <LockedAcknowledgment
        lockedAcknowledgment={locked_acknowledgment}
        lockedCommitments={lockedCommitments}
      />

      {/* Suggestion Cards */}
      {suggestionList.length === 0 && (
        <div style={styles.emptyState} role="status" aria-label="No suggestions available">
          <span style={styles.emptyIcon} role="img" aria-hidden="true">💡</span>
          <p style={styles.emptyText}>
            No suggestions yet. Once your schedule is analyzed, suggestions will appear here.
          </p>
        </div>
      )}

      {suggestionList.length > 0 && (
        <div style={styles.cardsSection} aria-label="Schedule suggestions">
          {suggestionList.map((suggestion, idx) => (
            <SuggestionCard key={idx} suggestion={suggestion} index={idx} />
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * Action type color mapping for badge styling.
 */
const actionColors = {
  reduce: { bg: '#fff7ed', text: '#c2410c', border: '#fed7aa' },
  reschedule: { bg: '#eff6ff', text: '#1d4ed8', border: '#bfdbfe' },
  redistribute: { bg: '#f5f3ff', text: '#6d28d9', border: '#ddd6fe' },
}

/**
 * SuggestionCard — renders a single suggestion with description,
 * target commitment, action badge, detail, and affected weeks.
 */
function SuggestionCard({ suggestion, index }) {
  const { description, target_commitment, action, detail, affected_weeks } = suggestion
  const colors = actionColors[action] || actionColors.reduce

  return (
    <article
      style={styles.card}
      aria-label={`Suggestion ${index + 1}: ${description || 'No description'}`}
    >
      {/* Card header: action badge + target commitment */}
      <div style={styles.cardHeader}>
        <span
          style={{
            ...styles.actionBadge,
            backgroundColor: colors.bg,
            color: colors.text,
            border: `1px solid ${colors.border}`,
          }}
          aria-label={`Action type: ${action || 'unknown'}`}
        >
          {action || 'unknown'}
        </span>
        {target_commitment && (
          <span style={styles.targetCommitment} aria-label={`Target: ${target_commitment}`}>
            🎯 {target_commitment}
          </span>
        )}
      </div>

      {/* Description */}
      <p style={styles.cardDescription}>{description || 'No description provided'}</p>

      {/* Detail */}
      {detail && (
        <p style={styles.cardDetail}>
          <span style={styles.detailLabel}>How:</span> {detail}
        </p>
      )}

      {/* Affected weeks */}
      {affected_weeks && affected_weeks.length > 0 && (
        <div style={styles.weeksContainer} aria-label={`Affected weeks: ${affected_weeks.join(', ')}`}>
          <span style={styles.weeksLabel}>Weeks affected:</span>
          <div style={styles.weeksPills}>
            {affected_weeks.map((week) => (
              <span key={week} style={styles.weekPill}>
                {week}
              </span>
            ))}
          </div>
        </div>
      )}
    </article>
  )
}

/**
 * LockedAcknowledgment — displays which constraints are protected
 * with a visually distinct bordered section and lock icons.
 */
function LockedAcknowledgment({ lockedAcknowledgment, lockedCommitments }) {
  // Don't render if there's nothing to show
  if (!lockedAcknowledgment && (!lockedCommitments || lockedCommitments.length === 0)) {
    return null
  }

  return (
    <section style={styles.lockedSection} aria-labelledby="locked-heading">
      {/* Header with lock icon */}
      <div style={styles.lockedHeader}>
        <span style={styles.lockIcon} role="img" aria-label="lock">
          🔒
        </span>
        <h3 id="locked-heading" style={styles.lockedTitle}>
          Protected Constraints
        </h3>
      </div>

      {/* Acknowledgment statement from API */}
      {lockedAcknowledgment && (
        <p style={styles.acknowledgmentText}>{lockedAcknowledgment}</p>
      )}

      {/* List of locked commitments */}
      {lockedCommitments && lockedCommitments.length > 0 && (
        <ul style={styles.lockedList}>
          {lockedCommitments.map((commitment, idx) => (
            <li key={idx} style={styles.lockedItem}>
              <span style={styles.lockIconSmall} role="img" aria-hidden="true">
                🔒
              </span>
              <span style={styles.commitmentName}>{commitment.name}</span>
              <span style={styles.commitmentHours}>
                {commitment.hours_per_week} hrs/week
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

// --- Inline Styles ---
const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1.5rem',
    width: '100%',
  },

  // Locked acknowledgment section
  lockedSection: {
    border: '2px solid #3b82f6',
    borderRadius: '12px',
    padding: '1.25rem 1.5rem',
    backgroundColor: '#eff6ff',
  },
  lockedHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    marginBottom: '0.75rem',
  },
  lockIcon: {
    fontSize: '1.25rem',
  },
  lockedTitle: {
    margin: 0,
    fontSize: '1.1rem',
    fontWeight: 600,
    color: '#1e40af',
  },
  acknowledgmentText: {
    margin: '0 0 1rem 0',
    fontSize: '0.95rem',
    color: '#374151',
    lineHeight: 1.5,
    fontStyle: 'italic',
  },
  lockedList: {
    listStyle: 'none',
    margin: 0,
    padding: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
  },
  lockedItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    padding: '0.5rem 0.75rem',
    backgroundColor: '#ffffff',
    borderRadius: '8px',
    border: '1px solid #bfdbfe',
  },
  lockIconSmall: {
    fontSize: '0.85rem',
  },
  commitmentName: {
    fontWeight: 500,
    color: '#1f2937',
    flex: 1,
  },
  commitmentHours: {
    fontSize: '0.85rem',
    color: '#6b7280',
    whiteSpace: 'nowrap',
  },

  // Suggestion cards
  cardsSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1rem',
  },
  card: {
    padding: '1.25rem 1.5rem',
    border: '1px solid #e5e7eb',
    borderRadius: '12px',
    backgroundColor: '#ffffff',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.06)',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.75rem',
  },
  cardHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.75rem',
    flexWrap: 'wrap',
  },
  actionBadge: {
    display: 'inline-block',
    padding: '0.25rem 0.65rem',
    borderRadius: '9999px',
    fontSize: '0.75rem',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.025em',
  },
  targetCommitment: {
    fontSize: '0.85rem',
    color: '#4b5563',
    fontWeight: 500,
  },
  cardDescription: {
    margin: 0,
    fontSize: '1rem',
    color: '#1f2937',
    lineHeight: 1.5,
    fontWeight: 500,
  },
  cardDetail: {
    margin: 0,
    fontSize: '0.9rem',
    color: '#374151',
    lineHeight: 1.5,
    backgroundColor: '#f9fafb',
    padding: '0.5rem 0.75rem',
    borderRadius: '8px',
    borderLeft: '3px solid #d1d5db',
  },
  detailLabel: {
    fontWeight: 600,
    color: '#6b7280',
  },
  weeksContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    flexWrap: 'wrap',
  },
  weeksLabel: {
    fontSize: '0.8rem',
    color: '#6b7280',
    fontWeight: 500,
  },
  weeksPills: {
    display: 'flex',
    gap: '0.35rem',
    flexWrap: 'wrap',
  },
  weekPill: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: '1.75rem',
    padding: '0.15rem 0.5rem',
    borderRadius: '9999px',
    backgroundColor: '#f3f4f6',
    border: '1px solid #e5e7eb',
    fontSize: '0.75rem',
    fontWeight: 500,
    color: '#374151',
  },

  // Get Suggestions button
  getSuggestionsButton: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.5rem',
    width: '100%',
    padding: '0.875rem 1.5rem',
    fontSize: '1rem',
    fontWeight: 600,
    color: '#ffffff',
    backgroundColor: '#7c3aed',
    border: 'none',
    borderRadius: '10px',
    cursor: 'pointer',
    transition: 'background-color 0.2s ease',
  },

  // Loading state
  loadingState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    padding: '2rem 1rem',
    borderRadius: '12px',
    border: '1px solid #e5e7eb',
    backgroundColor: '#faf5ff',
  },
  loadingSpinner: {
    fontSize: '1.5rem',
    marginBottom: '0.5rem',
    animation: 'pulse 1.5s ease-in-out infinite',
  },
  loadingText: {
    margin: 0,
    fontSize: '0.95rem',
    color: '#6d28d9',
    fontWeight: 500,
  },

  // Empty state
  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    padding: '2rem 1rem',
    borderRadius: '12px',
    border: '1px dashed #d1d5db',
    backgroundColor: '#f9fafb',
  },
  emptyIcon: {
    fontSize: '1.5rem',
    marginBottom: '0.5rem',
  },
  emptyText: {
    margin: 0,
    fontSize: '0.9rem',
    color: '#6b7280',
    textAlign: 'center',
  },
}
