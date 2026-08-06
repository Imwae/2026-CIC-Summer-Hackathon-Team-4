import { useMemo } from 'react'
import { Doughnut } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  ArcElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'

// Register Chart.js components needed for doughnut chart
ChartJS.register(ArcElement, Title, Tooltip, Legend)

// Color palette for commitment slices (reuses the commitment color scheme from Timeline)
const SLICE_COLORS = [
  { bg: 'rgba(239, 83, 80, 0.85)', border: 'rgba(239, 83, 80, 1)' },     // Work — red
  { bg: 'rgba(171, 71, 188, 0.85)', border: 'rgba(171, 71, 188, 1)' },   // Commute — purple
  { bg: 'rgba(66, 165, 245, 0.85)', border: 'rgba(66, 165, 245, 1)' },   // Sleep — blue
  { bg: 'rgba(102, 187, 106, 0.85)', border: 'rgba(102, 187, 106, 1)' }, // Extracurricular — green
  { bg: 'rgba(255, 167, 38, 0.85)', border: 'rgba(255, 167, 38, 1)' },   // Leisure — orange
  { bg: 'rgba(141, 110, 99, 0.85)', border: 'rgba(141, 110, 99, 1)' },   // Custom 1 — brown
  { bg: 'rgba(0, 150, 136, 0.85)', border: 'rgba(0, 150, 136, 1)' },     // Custom 2 — teal
  { bg: 'rgba(121, 134, 203, 0.85)', border: 'rgba(121, 134, 203, 1)' }, // Custom 3 — indigo
]

// Reduced-opacity versions for unlocked slices
const UNLOCKED_OPACITY = 0.45

/**
 * Converts an rgba color string to use a different alpha value.
 */
function withAlpha(rgba, alpha) {
  return rgba.replace(/[\d.]+\)$/, `${alpha})`)
}

/**
 * Breakdown component — renders a doughnut/pie chart showing each commitment
 * as a proportional slice of total semester hours.
 *
 * Locked commitments are visually distinguished by:
 * - Full opacity background (vs reduced opacity for unlocked)
 * - Thick dark border (3px dark gray)
 * - Slight offset (popped out from center)
 *
 * Props:
 *   commitments: array of { name, category, hours_per_week, locked } (or null/undefined)
 */
export default function Breakdown({ commitments }) {
  const chartData = useMemo(() => {
    if (!commitments || commitments.length === 0) {
      return null
    }

    const totalHours = commitments.reduce((sum, c) => sum + (c.hours_per_week ?? 0), 0)

    if (totalHours === 0) {
      return null
    }

    // Build labels with "name (XX%)" format
    const labels = commitments.map((c) => {
      const pct = ((c.hours_per_week ?? 0) / totalHours * 100).toFixed(1)
      return `${c.name} (${pct}%)`
    })

    const data = commitments.map((c) => c.hours_per_week ?? 0)

    // Locked slices get full opacity; unlocked slices are more transparent
    const backgroundColor = commitments.map((c, idx) => {
      const colorIdx = idx % SLICE_COLORS.length
      if (c.locked) {
        return SLICE_COLORS[colorIdx].bg // Full opacity (0.85)
      }
      return withAlpha(SLICE_COLORS[colorIdx].bg, UNLOCKED_OPACITY)
    })

    // Locked slices get a dark, prominent border; unlocked get a subtle matching border
    const borderColor = commitments.map((c, idx) => {
      const colorIdx = idx % SLICE_COLORS.length
      if (c.locked) {
        return 'rgba(30, 30, 30, 0.9)' // Dark border for locked
      }
      return withAlpha(SLICE_COLORS[colorIdx].border, 0.4) // Light border for unlocked
    })

    // Locked commitments get a thicker border (3px vs 1px)
    const borderWidth = commitments.map((c) => (c.locked ? 3 : 1))

    // Locked slices are offset (popped out) from the center for extra emphasis
    const offset = commitments.map((c) => (c.locked ? 6 : 0))

    return {
      labels,
      datasets: [
        {
          data,
          backgroundColor,
          borderColor,
          borderWidth,
          offset,
          hoverOffset: 12,
        },
      ],
    }
  }, [commitments])

  const options = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      title: {
        display: true,
        text: 'Semester Time Breakdown',
        font: { size: 16 },
      },
      legend: {
        position: 'right',
        labels: {
          generateLabels(chart) {
            const dataset = chart.data.datasets[0]
            return chart.data.labels.map((label, i) => {
              const isLocked = commitments && commitments[i]?.locked
              return {
                text: isLocked ? `🔒 ${label}` : label,
                fillStyle: dataset.backgroundColor[i],
                strokeStyle: dataset.borderColor[i],
                lineWidth: dataset.borderWidth[i],
                hidden: false,
                index: i,
              }
            })
          },
        },
      },
      tooltip: {
        callbacks: {
          label(context) {
            const idx = context.dataIndex
            const hours = context.parsed
            const total = context.dataset.data.reduce((sum, v) => sum + v, 0)
            const pct = ((hours / total) * 100).toFixed(1)
            const locked = commitments && commitments[idx]?.locked ? ' (Locked 🔒)' : ''
            return `${hours} hrs/week — ${pct}%${locked}`
          },
        },
      },
    },
  }), [commitments])

  // Handle null/empty commitments
  if (!commitments || commitments.length === 0) {
    return (
      <div className="breakdown-placeholder" style={{ padding: '2rem', textAlign: 'center', color: '#6b7280' }}>
        <p>No commitment data available. Enter your commitments to see the breakdown.</p>
      </div>
    )
  }

  if (!chartData) return null

  return (
    <div className="breakdown-container" style={{ position: 'relative', width: '100%', height: '350px', maxWidth: '700px', margin: '0 auto' }}>
      <Doughnut data={chartData} options={options} />

      {/* Legend supplement explaining locked vs unlocked visual distinction */}
      <div className="breakdown-legend" style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem', fontSize: '0.8rem', color: '#6b7280', flexWrap: 'wrap' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <span style={{ display: 'inline-block', width: '14px', height: '14px', border: '3px solid rgba(30,30,30,0.9)', backgroundColor: 'rgba(102,187,106,0.85)', borderRadius: '2px' }} />
          🔒 Locked (bold border, offset)
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <span style={{ display: 'inline-block', width: '14px', height: '14px', border: '1px solid rgba(100,100,100,0.4)', backgroundColor: 'rgba(102,187,106,0.45)', borderRadius: '2px' }} />
          Unlocked (faded)
        </span>
      </div>
    </div>
  )
}
