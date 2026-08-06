import { useMemo } from 'react'
import { Bar } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'

// Register Chart.js components needed for stacked bar + line overlay
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend
)

// Distinct color palette for courses
const COURSE_COLORS = [
  { bg: 'rgba(54, 162, 235, 0.7)', border: 'rgba(54, 162, 235, 1)' },
  { bg: 'rgba(255, 159, 64, 0.7)', border: 'rgba(255, 159, 64, 1)' },
  { bg: 'rgba(75, 192, 192, 0.7)', border: 'rgba(75, 192, 192, 1)' },
  { bg: 'rgba(153, 102, 255, 0.7)', border: 'rgba(153, 102, 255, 1)' },
  { bg: 'rgba(255, 205, 86, 0.7)', border: 'rgba(255, 205, 86, 1)' },
  { bg: 'rgba(201, 203, 207, 0.7)', border: 'rgba(201, 203, 207, 1)' },
  { bg: 'rgba(255, 99, 132, 0.7)', border: 'rgba(255, 99, 132, 1)' },
  { bg: 'rgba(100, 181, 246, 0.7)', border: 'rgba(100, 181, 246, 1)' },
]

// Distinct color palette for commitments (visually separate from course colors)
const COMMITMENT_COLORS = [
  { bg: 'rgba(239, 83, 80, 0.6)', border: 'rgba(239, 83, 80, 1)' },     // Work — red
  { bg: 'rgba(171, 71, 188, 0.6)', border: 'rgba(171, 71, 188, 1)' },   // Commute — purple
  { bg: 'rgba(66, 165, 245, 0.6)', border: 'rgba(66, 165, 245, 1)' },   // Sleep — blue
  { bg: 'rgba(102, 187, 106, 0.6)', border: 'rgba(102, 187, 106, 1)' }, // Extracurricular — green
  { bg: 'rgba(255, 167, 38, 0.6)', border: 'rgba(255, 167, 38, 1)' },   // Leisure — orange
  { bg: 'rgba(141, 110, 99, 0.6)', border: 'rgba(141, 110, 99, 1)' },   // Custom 1 — brown
  { bg: 'rgba(0, 150, 136, 0.6)', border: 'rgba(0, 150, 136, 1)' },     // Custom 2 — teal
  { bg: 'rgba(121, 134, 203, 0.6)', border: 'rgba(121, 134, 203, 1)' }, // Custom 3 — indigo
]

// Break week color (grayed out)
const BREAK_COLOR = { bg: 'rgba(200, 200, 200, 0.3)', border: 'rgba(200, 200, 200, 0.6)' }

// Break week full-column background overlay
const BREAK_WEEK_BG = 'rgba(180, 180, 180, 0.25)'

// Over-capacity highlight
const OVER_CAPACITY_BG = 'rgba(255, 0, 0, 0.15)'

/**
 * Timeline component — renders a stacked bar chart showing weekly prep hours by course
 * and commitment hours as additional stacked segments.
 *
 * Props:
 *   analysisResult: AnalysisResponse object (or null/undefined)
 *   commitments: array of { name, category, hours_per_week, locked } (or null/undefined)
 */
export default function Timeline({ analysisResult, commitments }) {
  const chartData = useMemo(() => {
    if (!analysisResult || !analysisResult.weeks || analysisResult.weeks.length === 0) {
      return null
    }

    const { weeks } = analysisResult

    // Collect all unique course codes across all weeks
    const courseSet = new Set()
    for (const week of weeks) {
      if (week.prep_hours_by_course) {
        for (const code of Object.keys(week.prep_hours_by_course)) {
          courseSet.add(code)
        }
      }
    }
    const courseCodes = Array.from(courseSet)

    // X-axis labels
    const labels = weeks.map((w) => `Week ${w.week_number}`)

    // Build one dataset per course (prep hours)
    const datasets = courseCodes.map((code, idx) => {
      const colorIdx = idx % COURSE_COLORS.length
      const color = COURSE_COLORS[colorIdx]

      const data = weeks.map((week) => {
        if (week.is_break) return 0
        return week.prep_hours_by_course?.[code] ?? 0
      })

      // Per-bar styling: gray out break weeks, red border on over-capacity
      const backgroundColor = weeks.map((week) => {
        if (week.is_break) return BREAK_COLOR.bg
        return color.bg
      })

      const borderColor = weeks.map((week) => {
        if (week.is_break) return BREAK_COLOR.border
        if (week.over_capacity) return 'rgba(220, 38, 38, 1)'
        return color.border
      })

      const borderWidth = weeks.map((week) => {
        if (week.over_capacity) return 2
        return 1
      })

      return {
        label: code,
        data,
        backgroundColor,
        borderColor,
        borderWidth,
        stack: 'hours',
      }
    })

    // Build one dataset per commitment
    if (commitments && commitments.length > 0) {
      commitments.forEach((commitment, idx) => {
        const colorIdx = idx % COMMITMENT_COLORS.length
        const color = COMMITMENT_COLORS[colorIdx]

        const data = weeks.map((week) => {
          if (week.is_break) return 0
          return commitment.hours_per_week ?? 0
        })

        const backgroundColor = weeks.map((week) => {
          if (week.is_break) return BREAK_COLOR.bg
          return color.bg
        })

        const borderColor = weeks.map((week) => {
          if (week.is_break) return BREAK_COLOR.border
          if (week.over_capacity) return 'rgba(220, 38, 38, 1)'
          return color.border
        })

        // Locked commitments get a thicker dashed border to distinguish them
        const borderWidth = weeks.map((week) => {
          if (commitment.locked) return 3
          if (week.over_capacity) return 2
          return 1
        })

        const borderDash = commitment.locked ? [4, 2] : undefined

        datasets.push({
          label: `${commitment.name}${commitment.locked ? ' 🔒' : ''}`,
          data,
          backgroundColor,
          borderColor,
          borderWidth,
          borderDash,
          stack: 'hours',
        })
      })
    }

    // Available hours reference line (line dataset overlaid on bar chart)
    const availableHoursData = weeks.map((week) => {
      if (week.is_break) return null
      return week.hours_available ?? null
    })

    datasets.push({
      label: 'Available Hours',
      data: availableHoursData,
      type: 'line',
      borderColor: 'rgba(34, 197, 94, 0.8)',
      backgroundColor: 'rgba(34, 197, 94, 0.1)',
      borderWidth: 2,
      borderDash: [6, 3],
      pointRadius: 0,
      fill: false,
      tension: 0,
      order: 0, // draw on top
    })

    return { labels, datasets }
  }, [analysisResult, commitments])

  const options = useMemo(() => {
    if (!analysisResult || !analysisResult.weeks) return {}

    const { weeks } = analysisResult

    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      plugins: {
        title: {
          display: true,
          text: 'Weekly Hours Breakdown (Prep + Commitments)',
          font: { size: 16 },
        },
        legend: {
          position: 'top',
          labels: {
            // Filter out the line dataset from the legend if desired
            filter(item) {
              return true
            },
          },
        },
        tooltip: {
          callbacks: {
            afterTitle(tooltipItems) {
              const idx = tooltipItems[0]?.dataIndex
              if (idx == null) return ''
              const week = weeks[idx]
              const parts = []
              if (week.is_break) parts.push('Break Week')
              if (week.over_capacity) parts.push('Over Capacity')
              if (week.collision) parts.push('Collision')
              if (week.deliverables_due?.length > 0) {
                parts.push(`Due: ${week.deliverables_due.join(', ')}`)
              }
              return parts.length > 0 ? parts.join(' | ') : ''
            },
          },
        },
      },
      scales: {
        x: {
          stacked: true,
          title: {
            display: true,
            text: 'Weeks',
          },
        },
        y: {
          stacked: true,
          beginAtZero: true,
          title: {
            display: true,
            text: 'Hours',
          },
        },
      },
    }
  }, [analysisResult])

  // Custom plugin to draw red background on over-capacity weeks and collision markers
  const backgroundPlugin = useMemo(() => {
    if (!analysisResult || !analysisResult.weeks) return null

    const { weeks } = analysisResult

    return {
      id: 'overCapacityBackground',
      beforeDraw(chart) {
        const { ctx, chartArea, scales } = chart
        if (!chartArea || !scales.x) return

        const xScale = scales.x
        const { top, bottom } = chartArea

        for (let i = 0; i < weeks.length; i++) {
          const week = weeks[i]
          const x = xScale.getPixelForValue(i)
          const barWidth = xScale.width / weeks.length
          const left = x - barWidth / 2

          // Gray background overlay for break weeks (full column)
          if (week.is_break) {
            ctx.save()
            // Fill the entire column with gray background
            ctx.fillStyle = BREAK_WEEK_BG
            ctx.fillRect(left, top, barWidth, bottom - top)

            // Draw diagonal hatch pattern for extra distinction
            ctx.strokeStyle = 'rgba(150, 150, 150, 0.3)'
            ctx.lineWidth = 1
            ctx.beginPath()
            const step = 10
            for (let y = top; y < bottom; y += step) {
              ctx.moveTo(left, y)
              ctx.lineTo(left + Math.min(step, barWidth), y + step)
            }
            for (let xOff = step; xOff < barWidth; xOff += step) {
              ctx.moveTo(left + xOff, top)
              ctx.lineTo(left + Math.min(xOff + (bottom - top), barWidth), bottom)
            }
            ctx.stroke()

            // Draw "BREAK" label centered in the column
            ctx.fillStyle = 'rgba(100, 100, 100, 0.7)'
            ctx.font = 'bold 11px sans-serif'
            ctx.textAlign = 'center'
            ctx.textBaseline = 'middle'
            const centerY = top + (bottom - top) / 2
            ctx.fillText('BREAK', x, centerY)
            ctx.restore()
            continue
          }

          // Red background for over-capacity weeks
          if (week.over_capacity) {
            ctx.save()
            ctx.fillStyle = OVER_CAPACITY_BG
            ctx.fillRect(left, top, barWidth, bottom - top)
            ctx.restore()
          }

          // Collision indicator — orange triangle at the top
          if (week.collision) {
            ctx.save()
            ctx.fillStyle = 'rgba(245, 158, 11, 0.9)'
            ctx.beginPath()
            ctx.moveTo(x - 6, top + 2)
            ctx.lineTo(x + 6, top + 2)
            ctx.lineTo(x, top + 14)
            ctx.closePath()
            ctx.fill()

            // Exclamation mark
            ctx.fillStyle = '#fff'
            ctx.font = 'bold 8px sans-serif'
            ctx.textAlign = 'center'
            ctx.fillText('!', x, top + 11)
            ctx.restore()
          }
        }
      },
    }
  }, [analysisResult])

  // Handle null/empty analysisResult
  if (!analysisResult || !analysisResult.weeks || analysisResult.weeks.length === 0) {
    return (
      <div className="timeline-placeholder" style={{ padding: '2rem', textAlign: 'center', color: '#6b7280' }}>
        <p>No analysis data available. Run an analysis to see your weekly timeline.</p>
      </div>
    )
  }

  if (!chartData) return null

  const plugins = backgroundPlugin ? [backgroundPlugin] : []

  return (
    <div className="timeline-container" style={{ position: 'relative', width: '100%', minHeight: '400px' }}>
      <Bar data={chartData} options={options} plugins={plugins} />

      {/* Legend supplement for indicators */}
      <div className="timeline-legend" style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem', fontSize: '0.8rem', color: '#6b7280', flexWrap: 'wrap' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <span style={{ display: 'inline-block', width: '12px', height: '12px', backgroundColor: OVER_CAPACITY_BG, border: '1px solid rgba(220, 38, 38, 0.5)' }} />
          Over Capacity
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <span style={{ display: 'inline-block', width: '0', height: '0', borderLeft: '6px solid transparent', borderRight: '6px solid transparent', borderTop: '10px solid rgba(245, 158, 11, 0.9)' }} />
          Collision Week
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <span style={{ display: 'inline-block', width: '12px', height: '12px', backgroundColor: BREAK_WEEK_BG, border: `1px solid rgba(150, 150, 150, 0.6)` }} />
          Break Week
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <span style={{ display: 'inline-block', width: '12px', height: '12px', border: '3px dashed rgba(100,100,100,0.7)', backgroundColor: 'transparent' }} />
          Locked Commitment
        </span>
      </div>
    </div>
  )
}
