import { useEffect, useState } from 'react'

// Phase 3 is a deployment smoke test, not a feature. This page shows one real
// number from the Python server so that "is it wired up end to end" is answered
// before anything depends on the answer.
//
// The three states below are all built now rather than retrofitted, because the
// product plan's exit check requires a friendly message when the server is down -
// a blank page is the failure mode it is specifically guarding against.

const LOADING = 'loading'
const READY = 'ready'
const FAILED = 'failed'

export default function App() {
  const [state, setState] = useState(LOADING)
  const [health, setHealth] = useState(null)

  useEffect(() => {
    let cancelled = false

    // Same URL in both environments: locally the Vite proxy forwards /api to the
    // backend container, and on Vercel a top-level rewrite sends it to the Python
    // service with the path intact.
    fetch('/api/health')
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json()
      })
      .then((data) => {
        if (cancelled) return
        setHealth(data)
        setState(READY)
      })
      .catch(() => {
        if (cancelled) return
        setState(FAILED)
      })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <main>
      <header>
        <h1>Wind Forecast Checker</h1>
        <p className="subtitle">
          Day-ahead wind forecast accuracy for the January 2026 buying window.
        </p>
      </header>

      {state === LOADING && <p className="status">Loading data…</p>}

      {state === FAILED && (
        <p className="status error">
          Could not load data. The server may be starting up or unavailable.
        </p>
      )}

      {state === READY && (
        <section className="panel">
          <p className="label">Half-hours of metered wind generation</p>
          <p className="number">{health.actual_rows.toLocaleString()}</p>
          <p className="label">
            {health.forecast_rows.toLocaleString()} forecast rows, covering delivery from{' '}
            {health.delivery_from.slice(0, 10)} to {health.delivery_to.slice(0, 10)}
          </p>
        </section>
      )}

      <footer>
        <p>Phase 3 — deployment check. The charts arrive in Phases 5 and 6.</p>
      </footer>
    </main>
  )
}
