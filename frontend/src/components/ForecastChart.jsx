import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import {
  formatAxisDay,
  formatAxisTime,
  formatFullUtc,
  formatHeld,
  formatLeadHours,
  formatMw,
  formatMwAxis,
  formatShortUtc,
} from '../lib/format.js'

// Screen 1's chart: two lines, one Y axis.
//
// Both series are megawatts, so they share a scale. A second Y axis would let the two
// lines be scaled independently and make any gap between them meaningless - which is
// exactly the comparison this screen exists to support. One axis, always.
//
// Three choices worth knowing about:
//
// 1. **`connectNulls={false}`.** A target half-hour with no permitted forecast is a null
//    in the data (AGENTS.md rule 3), and Recharts would happily draw straight through it.
//    Bridging a gap would invent a forecast the buyer never had. At hours=48 this is 279
//    of 1,488 points, so it is the normal case, not an edge case.
// 2. **`type="linear"`.** A monotone spline would bend the line between real observations
//    and imply values nobody published. Straight segments between measured points are the
//    honest rendering.
// 3. **No dots and no animation.** A month is 1,488 points; a marker on each would be a
//    smear, and re-animating them on every slider step would make dragging unusable.

const FORECAST = 'forecast_mw'
const ACTUAL = 'actual_mw'

const HALF_HOURS_PER_DAY = 48

/** Y-axis gradations, in MW. */
const TICK_STEP = 5000

/**
 * A y-axis that stops on round numbers.
 *
 * Left to itself Recharts divides the data range into equal parts and produces ticks like
 * 5.5K and 16.5K, which nobody holds in their head. Anchoring at zero and stepping in
 * 5,000 MW gives an axis that can be read at a glance, and starting at zero matters here:
 * these are generation volumes, and a truncated baseline would exaggerate the gap between
 * the two lines, which is the one comparison this screen exists to support.
 */
function yAxis(points) {
  let highest = 0
  for (const point of points) {
    if (point[ACTUAL] > highest) highest = point[ACTUAL]
    if (point[FORECAST] !== null && point[FORECAST] > highest) highest = point[FORECAST]
  }

  const top = Math.max(TICK_STEP, Math.ceil(highest / TICK_STEP) * TICK_STEP)
  const ticks = []
  for (let value = 0; value <= top; value += TICK_STEP) ticks.push(value)
  return { ticks, top }
}

/**
 * Explicit x-axis ticks, so a month does not produce an unreadable crush of labels.
 *
 * Recharts' automatic interval picks evenly spaced *indices*, which lands ticks at
 * arbitrary times like 07:30. These land on real boundaries instead - midnight for a
 * multi-day range, whole hours within a single day.
 */
function axisTicks(points, singleDay) {
  if (points.length === 0) return []

  if (singleDay) {
    // Every 3 hours: 00:00, 03:00, ... 21:00.
    return points.filter((_, index) => index % 6 === 0).map((point) => point.target_time)
  }

  const days = points.filter((point) => point.target_time.slice(11, 16) === '00:00')
  const stride = Math.max(1, Math.ceil(days.length / 8))
  return days.filter((_, index) => index % stride === 0).map((point) => point.target_time)
}

function ChartTooltip({ active, payload }) {
  if (!active || !payload || payload.length === 0) return null

  // Every series at this x shares the same source row, so the extra fields - publish
  // time, lead time, the hold flag - come off whichever series is present. The forecast
  // may legitimately be absent; the actual never is.
  const row = payload[0].payload
  const hasForecast = row[FORECAST] !== null && row[FORECAST] !== undefined

  return (
    <div className="tooltip">
      <p className="tooltip-time">{formatFullUtc(row.target_time)}</p>

      <p className="tooltip-row">
        <span className="tooltip-key tooltip-key-forecast" aria-hidden="true" />
        <span className="tooltip-value">{formatMw(row[FORECAST])} MW</span>
        <span className="tooltip-name">Forecast</span>
      </p>

      <p className="tooltip-row">
        <span className="tooltip-key tooltip-key-actual" aria-hidden="true" />
        <span className="tooltip-value">{formatMw(row[ACTUAL])} MW</span>
        <span className="tooltip-name">Real wind</span>
      </p>

      {hasForecast ? (
        <p className="tooltip-meta">
          Published {formatShortUtc(row.publish_time)} UTC ·{' '}
          {formatLeadHours(row.lead_time_hours)} ahead
          <br />
          {formatHeld(row.is_held)}
        </p>
      ) : (
        <p className="tooltip-meta">
          No forecast published early enough for this half-hour.
        </p>
      )}
    </div>
  )
}

export default function ForecastChart({ points }) {
  const singleDay = points.length <= HALF_HOURS_PER_DAY
  const ticks = axisTicks(points, singleDay)
  const formatTick = singleDay ? formatAxisTime : formatAxisDay
  const { ticks: yTicks, top: yTop } = yAxis(points)

  return (
    <figure className="chart-figure">
      <figcaption className="chart-head">
        <h2 className="chart-title">
          Forecast against real wind <span className="chart-unit">· MW</span>
        </h2>
        <ul className="legend">
          <li>
            <span className="legend-key legend-key-forecast" aria-hidden="true" />
            Forecast
          </li>
          <li>
            <span className="legend-key legend-key-actual" aria-hidden="true" />
            Real wind
          </li>
        </ul>
      </figcaption>

      <div className="chart-plot">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            {/* Solid hairlines. Recharts dashes gridlines by default, which reads as a
                threshold or a projection when it is only a grid. */}
            <CartesianGrid
              vertical={false}
              stroke="var(--grid)"
              strokeDasharray="0"
              strokeWidth={1}
            />
            <XAxis
              dataKey="target_time"
              ticks={ticks}
              tickFormatter={formatTick}
              tick={{ fill: 'var(--muted)', fontSize: 12 }}
              stroke="var(--grid)"
              tickMargin={8}
              minTickGap={0}
            />
            {/* The unit lives in the heading rather than as an axis label: Recharts
                places an axis label at a fixed offset, where it collided with the
                topmost tick. */}
            <YAxis
              domain={[0, yTop]}
              ticks={yTicks}
              tickFormatter={formatMwAxis}
              tick={{ fill: 'var(--muted)', fontSize: 12 }}
              stroke="var(--grid)"
              width={48}
            />
            <Tooltip
              content={<ChartTooltip />}
              cursor={{ stroke: 'var(--muted)', strokeWidth: 1 }}
              isAnimationActive={false}
            />
            <Line
              dataKey={ACTUAL}
              name="Real wind"
              type="linear"
              stroke="var(--series-actual)"
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              dot={false}
              activeDot={{ r: 4, strokeWidth: 0 }}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
              dataKey={FORECAST}
              name="Forecast"
              type="linear"
              stroke="var(--series-forecast)"
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
              dot={false}
              activeDot={{ r: 4, strokeWidth: 0 }}
              connectNulls={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <p className="chart-foot">
        Delivery half-hours, {singleDay ? 'times' : 'dates'} in UTC. Each point is a
        settlement half-hour.
      </p>
    </figure>
  )
}
