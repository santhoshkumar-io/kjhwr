import Screen1 from './components/Screen1.jsx'

// The shell. Phase 3's placeholder body has been replaced by Screen 1; the loading and
// failure states it introduced now live in Screen1, where the fetching does.
//
// Phase 6 adds Screen 2 beside this one and reuses Screen 1's date range and mode, which
// is why the controls are a standalone component with their state held one level up from
// the chart - that state lifts to here without touching the controls themselves.

export default function App() {
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

      <Screen1 />

      <footer>
        <p>
          Forecasts from Elexon WINDFOR, metered generation from FUELHH (fuel type WIND).
          All times UTC. The accuracy numbers arrive in Phase 6.
        </p>
      </footer>
    </main>
  )
}
