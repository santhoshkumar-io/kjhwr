import { formatHeld, formatLeadHours, formatMw, formatShortUtc } from '../lib/format.js'

// The chart's table twin.
//
// A tooltip must enhance, never gate: every value the hover shows has to be reachable
// without a pointer, for a keyboard or screen-reader user and for anyone reading a
// printout. This is that path, and it is also where `publish_time` and `is_held` become
// legible at a glance rather than one half-hour at a time - which is what decision 0004
// means by the hold staying visible.
//
// Collapsed by default, because the chart is the answer and this is the audit trail.

export default function SeriesTable({ points }) {
  // Opening on #table makes the audit trail linkable - "look at the numbers behind this"
  // is a sentence someone sends a colleague - and it is what lets the table be captured
  // for the phase notes, since a headless browser cannot click a disclosure open.
  const openByDefault =
    typeof window !== 'undefined' && window.location.hash === '#table'

  return (
    <details className="table-view" id="table" open={openByDefault}>
      <summary>Show as table ({points.length.toLocaleString('en-GB')} half-hours)</summary>

      <div className="table-scroll">
        <table>
          <caption className="visually-hidden">
            Forecast and real wind generation by delivery half-hour, times in UTC
          </caption>
          <thead>
            <tr>
              <th scope="col">Delivery (UTC)</th>
              <th scope="col" className="numeric">
                Forecast MW
              </th>
              <th scope="col" className="numeric">
                Real wind MW
              </th>
              <th scope="col">Forecast published</th>
              <th scope="col" className="numeric">
                Lead time
              </th>
              <th scope="col">Hold</th>
            </tr>
          </thead>
          <tbody>
            {points.map((point) => (
              <tr key={point.target_time}>
                <th scope="row">{formatShortUtc(point.target_time)}</th>
                <td className="numeric">{formatMw(point.forecast_mw)}</td>
                <td className="numeric">{formatMw(point.actual_mw)}</td>
                <td>{formatShortUtc(point.publish_time)}</td>
                <td className="numeric">{formatLeadHours(point.lead_time_hours)}</td>
                <td>{formatHeld(point.is_held)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
