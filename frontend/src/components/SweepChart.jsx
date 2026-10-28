import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { formatMw, formatMwAxis } from '../lib/format.js'

// "How much worse is the forecast the earlier you have to commit?"
//
// This chart is built by SWEEPING the hours-ahead setting and comparing whole series. It
// must never be built by bucketing a deadline-mode series by lead time: in deadline mode a
// single run serves each delivery day, so a target's lead time is its hour of day plus a
// constant - they correlate at 0.9993 on the real data. A lead-time-bucketed chart
// therefore relabels overnight wind behaviour as forecast staleness, and it slopes the
// wrong way, which is how the mistake was caught in Phase 2.
//
// The horizon is the other thing to be honest about. Each forecast run's reach ends at a
// fixed wall-clock point, so above about 42 hours the newest permitted run often does not
// reach the target at all. Those points are averaged over fewer half-hours, so they are
// drawn as hollow markers and the count travels in the tooltip - the comparison stops
// being like-for-like there and the chart has to say so.

const FULL_COVERAGE = 1

/** Y-axis gradations, in MW. */
const TICK_STEP = 250

/**
 * A y-axis fitted to the data rather than anchored at zero.
 *
 * The hour-of-day chart next to this one uses columns, and columns must grow from zero or
 * their lengths stop meaning anything. A trend line is different: nothing here is a
 * length to be compared against the origin, and the question the chart answers is "how
 * much worse does it get", which a mostly-empty plot hides. Forcing zero here left the
 * whole line squeezed into the top quarter and the 37% rise read as flat.
 *
 * The axis is labelled in megawatts and starts on a round number, so the scale is plain
 * rather than implied.
 */
function yAxis(points) {
  const values = points.map((point) => point.mae)
  const low = Math.floor(Math.min(...values) / TICK_STEP) * TICK_STEP
  const high = Math.ceil(Math.max(...values) / TICK_STEP) * TICK_STEP
  const ticks = []
  for (let value = low; value <= high; value += TICK_STEP) ticks.push(value)
  return { ticks, domain: [low, high] }
}

function CoverageDot({ cx, cy, payload }) {
  if (cx === null || cy === null || cx === undefined || cy === undefined) return null
  const partial = payload.coverage < FULL_COVERAGE
  return (
    <circle
      cx={cx}
      cy={cy}
      r={partial ? 4 : 3}
      fill={partial ? 'var(--bg)' : 'var(--series-forecast)'}
      stroke="var(--series-forecast)"
      strokeWidth={partial ? 2 : 0}
    />
  )
}

function SweepTooltip({ active, payload }) {
  if (!active || !payload || payload.length === 0) return null
  const point = payload[0].payload
  const partial = point.coverage < FULL_COVERAGE

  return (
    <div className="tooltip">
      <p className="tooltip-time">{point.hours} hours before delivery</p>
      <p className="tooltip-row">
        <span className="tooltip-key tooltip-key-forecast" aria-hidden="true" />
        <span className="tooltip-value">{formatMw(Math.round(point.mae))} MW</span>
        <span className="tooltip-name">typical miss</span>
      </p>
      <p className="tooltip-meta">
        Averaged over {point.matched.toLocaleString('en-GB')} of{' '}
        {point.requested.toLocaleString('en-GB')} half-hours
        {partial && (
          <>
            <br />
            Fewer points than the rest of the line — not a like-for-like comparison.
          </>
        )}
      </p>
    </div>
  )
}

export default function SweepChart({ points }) {
  const partial = points.filter((p) => p.coverage < FULL_COVERAGE)
  const firstPartial = partial.length > 0 ? partial[0].hours : null
  const { ticks: yTicks, domain: yDomain } = yAxis(points)

  return (
    <figure className="chart-figure">
      <figcaption className="chart-head">
        <h3 className="chart-title">
          Typical miss by how far ahead the forecast was made <span className="chart-unit">· MW</span>
        </h3>
      </figcaption>

      <div className="chart-plot chart-plot-small">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid
              vertical={false}
              stroke="var(--grid)"
              strokeDasharray="0"
              strokeWidth={1}
            />
            <XAxis
              dataKey="hours"
              type="number"
              domain={[0, 48]}
              ticks={[0, 6, 12, 18, 24, 30, 36, 42, 48]}
              tick={{ fill: 'var(--muted)', fontSize: 12 }}
              stroke="var(--grid)"
              tickMargin={8}
              // Nine fixed ticks fit a half-width desktop card and crowd a phone; this
              // lets Recharts thin them when there is no room.
              minTickGap={24}
              label={{
                value: 'hours before delivery',
                position: 'insideBottom',
                offset: -4,
                fill: 'var(--muted)',
                fontSize: 12,
              }}
              height={46}
            />
            <YAxis
              domain={yDomain}
              ticks={yTicks}
              tickFormatter={formatMwAxis}
              tick={{ fill: 'var(--muted)', fontSize: 12 }}
              stroke="var(--grid)"
              width={48}
            />
            <Tooltip
              content={<SweepTooltip />}
              cursor={{ stroke: 'var(--muted)', strokeWidth: 1 }}
              isAnimationActive={false}
            />
            <Line
              dataKey="mae"
              type="linear"
              stroke="var(--series-forecast)"
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              dot={<CoverageDot />}
              activeDot={{ r: 5, strokeWidth: 0 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <p className="chart-foot">
        Each point is the whole selected range re-measured at that setting, so the mix of
        delivery hours is identical across the line.{' '}
        {firstPartial !== null && (
          <>
            Hollow markers from {firstPartial} h onward are averaged over fewer half-hours,
            because the forecast horizon runs out — above there the comparison is no longer
            like-for-like.
          </>
        )}
      </p>
    </figure>
  )
}
