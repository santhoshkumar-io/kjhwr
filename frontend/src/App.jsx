import { useEffect, useState } from 'react'

import Controls from './components/Controls.jsx'
import Screen1 from './components/Screen1.jsx'
import Screen2 from './components/Screen2.jsx'
import { controlsToSearch, readControls } from './lib/seriesUrl.js'
import { FAILED, GENERIC_FAILURE, getJson } from './lib/useFetch.js'

// The shell, and the owner of the one thing both screens share: the settings.
//
// Phase 5 kept the control state inside Screen 1 because only Screen 1 existed. The
// product plan requires Screen 2 to follow "the same date range and mode as Screen 1", so
// the state lifts here and both screens read it. `Controls` was built presentational for
// exactly this move and needed no change.
//
// One filter row at the top scoping everything below it also means the two screens can
// never disagree about which slice of January they are describing - a dashboard whose
// chart and whose numbers come from different ranges is worse than no dashboard.

export default function App() {
  const [bounds, setBounds] = useState(null)
  const [controls, setControls] = useState(null)
  const [failure, setFailure] = useState(null)

  // The delivery range comes from the server, so the date picker's limits are the real
  // ones and no date is typed into the page (AGENTS.md rule 2).
  useEffect(() => {
    let cancelled = false

    getJson('/api/health')
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
        setFailure(GENERIC_FAILURE)
      })

    return () => {
      cancelled = true
    }
  }, [])

  // Keep the address bar in step, so a view can be shared or reloaded as it stands. The
  // fragment is carried over deliberately: replacing the URL with the query string alone
  // would drop `#table`, so a link to the table view would lose it on first render.
  useEffect(() => {
    if (!controls) return
    window.history.replaceState(null, '', `${controlsToSearch(controls)}${window.location.hash}`)
  }, [controls])

  return (
    <main>
      <header>
        <h1>Wind Forecast Checker</h1>
        <p className="subtitle">
          Day-ahead wind forecast accuracy for the January 2026 buying window. National
          wind generation from Elexon: the forecast a buyer could actually see at the
          moment of commitment, against what the wind really did.
        </p>
      </header>

      {failure && <p className="status error">{failure}</p>}

      {!controls && !failure && <p className="status">Loading data…</p>}

      {controls && bounds && (
        <>
          <Controls controls={controls} bounds={bounds} onChange={setControls} />
          <Screen1 controls={controls} />
          <Screen2 controls={controls} />
        </>
      )}

      <footer>
        <p>
          Forecasts from Elexon WINDFOR, metered generation from FUELHH (fuel type WIND).
          All times UTC. Error is forecast minus actual, so a positive number means the
          forecast was too high.
        </p>
      </footer>
    </main>
  )
}
