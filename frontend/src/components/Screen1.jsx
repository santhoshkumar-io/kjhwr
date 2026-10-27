import { useEffect, useState } from 'react'

import Controls from './Controls.jsx'
import ForecastChart from './ForecastChart.jsx'
import SeriesTable from './SeriesTable.jsx'
import { HOURS_AHEAD, controlsToSearch, readControls, seriesUrl } from '../lib/seriesUrl.js'

// Screen 1: what the forecast said before buying, and what really came.
//
// The state machine extends the Phase 3 pattern rather than replacing it, but adds one
// state Phase 3 did not need: REFRESHING. Moving the slider refetches, and swapping the
// chart for a spinner on every step would flash the layout and lose the reader's place.
// So a refetch holds the previous chart at reduced opacity instead.
//
// The `cancelled` flag in each effect is load-bearing, not boilerplate: StrictMode
// double-invokes effects in development, and the slider can outrun its own requests, so a
// late response must not overwrite a newer one.

const LOADING = 'loading'
const REFRESHING = 'refreshing'
const READY = 'ready'
const FAILED = 'failed'

// Long enough that dragging the slider sends one request instead of forty, short enough
// that releasing it feels immediate. Each response is around 250 KB.
const DEBOUNCE_MS = 200

const GENERIC_FAILURE = 'Could not load data. The server may be starting up or unavailable.'

/** The server's own sentence if it sent one, otherwise the generic message. */
async function failureMessage(response) {
  try {
    const body = await response.json()
    if (body && typeof body.error === 'string') return body.error
  } catch {
    // Not JSON - fall through to the generic message.
  }
  return GENERIC_FAILURE
}

export default function Screen1() {
  const [bounds, setBounds] = useState(null)
  const [controls, setControls] = useState(null)
  const [data, setData] = useState(null)
  const [status, setStatus] = useState(LOADING)
  const [message, setMessage] = useState(null)

  // The delivery range comes from the server, so the date picker's limits are the real
  // ones and no date is typed into the page (AGENTS.md rule 2).
  useEffect(() => {
    let cancelled = false

    fetch('/api/health')
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
      })
      .then((health) => {
        if (cancelled) return
        const range = {
          earliest: health.delivery_from.slice(0, 10),
          latest: health.delivery_to.slice(0, 10),
        }
        setBounds(range)
        setControls(readControls(window.location.search, range))
      })
      .catch(() => {
        if (cancelled) return
        setMessage(GENERIC_FAILURE)
        setStatus(FAILED)
      })

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!controls) return undefined
    let cancelled = false

    // No delay for the first load; debounce only once there is a chart to keep.
    const delay = data ? DEBOUNCE_MS : 0
    const timer = setTimeout(() => {
      setStatus((current) => (current === READY ? REFRESHING : current))

      fetch(seriesUrl(controls))
        .then(async (response) => {
          if (!response.ok) throw new Error(await failureMessage(response))
          return response.json()
        })
        .then((series) => {
          if (cancelled) return
          setData(series)
          setMessage(null)
          setStatus(READY)
        })
        .catch((error) => {
          if (cancelled) return
          setMessage(error.message || GENERIC_FAILURE)
          setStatus(FAILED)
        })
    }, delay)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
    // `data` is read to decide the debounce delay, but must not retrigger the fetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [controls])

  // Keep the address bar in step, so the view can be shared or reloaded as it stands.
  // The fragment is carried over deliberately: replacing the URL with the query string
  // alone would drop `#table`, so a link to the table view would lose it on first render.
  useEffect(() => {
    if (!controls) return
    window.history.replaceState(null, '', `${controlsToSearch(controls)}${window.location.hash}`)
  }, [controls])

  if (!controls || !bounds) {
    return (
      <p className={`status${status === FAILED ? ' error' : ''}`}>
        {status === FAILED ? message : 'Loading data…'}
      </p>
    )
  }

  const applied = data?.applied
  const settingSentence =
    applied?.mode === HOURS_AHEAD
      ? `forecast made at least ${applied.hours} hours before delivery`
      : `newest forecast available at the ${applied?.deadline_hour_utc ?? 11}:00 UTC day-ahead deadline`

  return (
    <>
      <Controls
        controls={controls}
        bounds={bounds}
        onChange={setControls}
        disabled={status === LOADING}
      />

      {message && <p className="status error">{message}</p>}

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

      {!data && status !== FAILED && <p className="status">Loading data…</p>}
    </>
  )
}
