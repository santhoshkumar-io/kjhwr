import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { formatMw, formatMwAxis } from '../lib/format.js'
import { DEADLINE } from '../lib/seriesUrl.js'

// "Which hours of the day is the forecast worst at?"
//
// One measure across 24 ordered bins, so this is a magnitude comparison: columns in a
// single hue, not a multi-colour chart. The bars start at zero because a floating
// baseline would turn a modest spread into a dramatic one - the honest picture is that
// the overnight hours are somewhat worse, not catastrophically so.
//
// The caption carries a real caveat. In deadline mode every delivery day is served by one
// run published at 11:00 the day before, so a later delivery hour is also a longer-lead
// forecast - this axis is a lead-time axis wearing an hour-of-day label. The pattern does
// survive when lead time is held constant, but the chart alone cannot show that, so it
// does not claim it.

const HOURS_IN_DAY = 24

/**
 * All 24 slots, whether or not the setting leaves data in them.
 *
 * At high hours-ahead settings the horizon runs out and whole delivery hours can end up
 * with no matched half-hours at all - at 48 h, hours 00 and 01 have none. The API
 * correctly omits them rather than reporting a zero, but handing that straight to the
 * chart made the axis start at 02 and quietly shift, so an hour with no data looked like
 * an hour that did not exist.
 *
 * Filling the gap with `null` - never 0, which would claim a perfect forecast - keeps the
 * axis fixed at 00-23 and renders the missing hours as the blanks they are.
 */
function allHours(measured) {
  const byHour = new Map(measured.map((entry) => [entry.hour_utc, entry]))
  return Array.from({ length: HOURS_IN_DAY }, (_, hour) =>
    byHour.get(hour) ?? { hour_utc: hour, mae: null, n: 0 },
  )
}

function HourTooltip({ active, payload }) {
  if (!active || !payload || payload.length === 0) return null
  const point = payload[0].payload
  const hour = String(point.hour_utc).padStart(2, '0')

  if (point.mae === null) {
    return (
      <div className="tooltip">
        <p className="tooltip-time">
          {hour}:00–{hour}:59 UTC
        </p>
        <p className="tooltip-meta">
          No half-hour in this range had a forecast available at this setting.
        </p>
      </div>
    )
  }

  return (
    <div className="tooltip">
      <p className="tooltip-time">
        {hour}:00–{hour}:59 UTC
      </p>
      <p className="tooltip-row">
        <span className="tooltip-key tooltip-key-forecast" aria-hidden="true" />
        <span className="tooltip-value">{formatMw(Math.round(point.mae))} MW</span>
        <span className="tooltip-name">typical miss</span>
      </p>
      <p className="tooltip-meta">Over {point.n.toLocaleString('en-GB')} half-hours</p>
    </div>
  )
}

export default function HourOfDayChart({ hours, mode }) {
  const data = allHours(hours)
  const missing = data.filter((entry) => entry.mae === null).length

  return (
    <figure className="chart-figure">
      <figcaption className="chart-head">
        <h3 className="chart-title">
          Typical miss by hour of the day <span className="chart-unit">· MW</span>
        </h3>
      </figcaption>

      <div className="chart-plot chart-plot-small">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid
              vertical={false}
              stroke="var(--grid)"
              strokeDasharray="0"
              strokeWidth={1}
            />
            <XAxis
              dataKey="hour_utc"
              tickFormatter={(hour) => String(hour).padStart(2, '0')}
              tick={{ fill: 'var(--muted)', fontSize: 12 }}
              stroke="var(--grid)"
              tickMargin={8}
              interval={2}
              label={{
                value: 'delivery hour, UTC',
                position: 'insideBottom',
                offset: -4,
                fill: 'var(--muted)',
                fontSize: 12,
              }}
              height={46}
            />
            <YAxis
              tickFormatter={formatMwAxis}
              tick={{ fill: 'var(--muted)', fontSize: 12 }}
              stroke="var(--grid)"
              width={48}
            />
            <Tooltip
              content={<HourTooltip />}
              cursor={{ fill: 'var(--grid)' }}
              isAnimationActive={false}
            />
            {/* A 2px surface gap separates touching columns - a border around each bar
                would be heavier ink doing the same job. */}
            <Bar
              dataKey="mae"
              fill="var(--series-forecast)"
              radius={[2, 2, 0, 0]}
              maxBarSize={22}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <p className="chart-foot">
        {missing > 0 && (
          <>
            {missing} {missing === 1 ? 'hour has' : 'hours have'} no bar: at this
            hours-ahead setting no forecast reached those delivery hours at all.{' '}
          </>
        )}
        {mode === DEADLINE ? (
          <>
            In day-ahead deadline mode one run serves each delivery day, so a later hour is
            also a longer-lead forecast — this axis is partly a lead-time axis. Switch to
            the hours-ahead mode to hold lead time roughly constant.
          </>
        ) : (
          <>
            Lead time is roughly constant across this chart, so the differences here are
            time-of-day effects rather than forecast staleness.
          </>
        )}
      </p>
    </figure>
  )
}
