import { useEffect, useRef, useState } from 'react'

import HourOfDayChart from './HourOfDayChart.jsx'
import StatTiles from './StatTiles.jsx'
import SweepChart from './SweepChart.jsx'
import WorstDaysTable from './WorstDaysTable.jsx'
import { metricsUrl, sweepPoints } from '../lib/seriesUrl.js'
import {
  FAILED,
  GENERIC_FAILURE,
  READY,
  REFRESHING,
  getJson,
  useLoader,
} from '../lib/useFetch.js'

// Screen 2: how far the forecast usually misses, and which way.
//
// Two separate loads, because they answer different questions and have different costs:
//
// 1. `/api/metrics` for the current settings - the four numbers, the bias-corrected set,
//    the hour-of-day profile and the worst days. One request.
// 2. The hours-ahead sweep - 25 requests, one per setting, run in parallel. It follows
//    the selected date range but not the mode, because sweeping the setting IS the mode.
//    Keeping it separate means changing only the mode does not re-run the sweep, which
//    would be 25 requests for a result that cannot have changed.

const DEBOUNCE_MS = 200

/** Just the parts of the settings the sweep depends on. */
function sweepKey(controls) {
  return `${controls.start}..${controls.end}`
}

function useSweep(controls) {
  const [points, setPoints] = useState([])
  const [failed, setFailed] = useState(false)
  const key = sweepKey(controls)
  const latest = useRef(0)

  useEffect(() => {
    let cancelled = false
    const token = latest.current + 1
    latest.current = token

    const timer = setTimeout(() => {
      const requests = sweepPoints(controls).map(({ hours, url }) =>
        getJson(url).then((metrics) => ({
          hours,
          mae: metrics.raw.mae,
          matched: metrics.points_matched,
          requested: metrics.points_requested,
          coverage:
            metrics.points_requested > 0
              ? metrics.points_matched / metrics.points_requested
              : 0,
        })),
      )

      Promise.all(requests)
        .then((result) => {
          // A slower earlier sweep must not land on top of a newer one.
          if (cancelled || latest.current !== token) return
          setPoints(result.filter((point) => point.mae !== null))
          setFailed(false)
        })
        .catch(() => {
          if (cancelled || latest.current !== token) return
          setFailed(true)
        })
    }, DEBOUNCE_MS)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
    // Only the date range moves the sweep; the mode cannot change it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  return { points, failed }
}

export default function Screen2({ controls, onFailure }) {
  const url = metricsUrl(controls)
  const { data, status, message } = useLoader(url, () => getJson(url), {
    debounceMs: DEBOUNCE_MS,
  })
  const sweep = useSweep(controls)

  useEffect(() => {
    onFailure(status === FAILED ? message : null)
  }, [status, message, onFailure])

  return (
    <section className="screen" aria-labelledby="screen2-heading">
      <h2 id="screen2-heading" className="screen-heading">
        How accurate is the forecast
      </h2>

      {!data && status !== FAILED && <p className="status">Loading numbers…</p>}

      {data && (
        <div className={status === REFRESHING ? 'refreshing' : undefined}>
          <StatTiles metrics={data} />

          <div className="chart-pair">
            {sweep.points.length > 0 ? (
              <SweepChart points={sweep.points} />
            ) : (
              <p className="status">
                {sweep.failed ? GENERIC_FAILURE : 'Measuring every hours-ahead setting…'}
              </p>
            )}
            <HourOfDayChart hours={data.by_hour_of_day} mode={data.applied.mode} />
          </div>

          <WorstDaysTable days={data.worst_days} />
        </div>
      )}
    </section>
  )
}
