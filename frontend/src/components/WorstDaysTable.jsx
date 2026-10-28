import { formatMw, formatSignedMw } from '../lib/format.js'

// The five delivery days with the largest typical miss.
//
// Worth reading alongside the bias column: on the January data every one of the worst
// days has a mean bias equal to its MAE, which means every single half-hour that day was
// forecast too high. That is the curtailment signature showing up at day level rather
// than a scattering of bad luck, which is why the bias column is here and not dropped as
// a duplicate.

export default function WorstDaysTable({ days }) {
  if (days.length === 0) return null

  return (
    <section className="panel" aria-labelledby="worst-days-heading">
      <h3 id="worst-days-heading" className="panel-heading">
        The {days.length} worst delivery days
      </h3>

      <div className="table-scroll table-scroll-flush">
        <table className="worst-days">
        <thead>
          <tr>
            <th scope="col">Delivery day</th>
            <th scope="col" className="numeric">
              Typical miss
            </th>
            <th scope="col" className="numeric">
              Average lean
            </th>
            <th scope="col" className="numeric">
              Half-hours
            </th>
          </tr>
        </thead>
        <tbody>
          {days.map((day) => (
            <tr key={day.day}>
              <th scope="row">{day.day}</th>
              <td className="numeric">{formatMw(Math.round(day.mae))} MW</td>
              <td className="numeric">{formatSignedMw(Math.round(day.bias))} MW</td>
              <td className="numeric">{day.n}</td>
            </tr>
          ))}
          </tbody>
        </table>
      </div>

      <p className="panel-note">
        Where the average lean equals the typical miss, every half-hour that day was
        forecast too high — not a mix of good and bad calls.
      </p>
    </section>
  )
}
