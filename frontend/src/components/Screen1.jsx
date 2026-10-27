import ForecastChart from './ForecastChart.jsx'
import SeriesTable from './SeriesTable.jsx'
import { HOURS_AHEAD, seriesUrl } from '../lib/seriesUrl.js'
import { FAILED, READY, REFRESHING, getJson, useLoader } from '../lib/useFetch.js'

// Screen 1: what the forecast said before buying, and what really came.
//
// The settings now arrive as a prop - App owns them, because Screen 2 follows the same
// range and mode. The fetching pattern moved to useLoader for the same reason: two
// screens needing identical behaviour should not carry two copies of it.

const DEBOUNCE_MS = 200

export default function Screen1({ controls }) {
  const url = seriesUrl(controls)
  const { data, status, message } = useLoader(url, () => getJson(url), {
    debounceMs: DEBOUNCE_MS,
  })

  const applied = data?.applied
  const settingSentence =
    applied?.mode === HOURS_AHEAD
      ? `forecast made at least ${applied.hours} hours before delivery`
      : `newest forecast available at the ${applied?.deadline_hour_utc ?? 11}:00 UTC day-ahead deadline`

  return (
    <section className="screen" aria-labelledby="screen1-heading">
      <h2 id="screen1-heading" className="screen-heading">
        What the forecast said, and what came
      </h2>

      {status === FAILED && <p className="status error">{message}</p>}

      {!data && status !== FAILED && <p className="status">Loading data…</p>}

      {data && (
        <>
          <p className="readout">
            <strong>{data.points_matched.toLocaleString('en-GB')}</strong> of{' '}
            {data.points_requested.toLocaleString('en-GB')} points matched
            <span className="readout-detail"> — {settingSentence}</span>
          </p>

          {/* Holding the previous render at reduced opacity avoids a skeleton flash and
              a layout jump while the next response is in flight. */}
          <div className={status === REFRESHING ? 'refreshing' : undefined}>
            <ForecastChart points={data.points} />
            <SeriesTable points={data.points} />
          </div>
        </>
      )}
    </section>
  )
}
