import { formatMw, formatSignedMw } from '../lib/format.js'

// The four numbers from decision 0005, and the bias-corrected set beside them.
//
// Each tile carries three things: the measure's real name, so a reviewer can map it to
// 0005; the figure; and a sentence written as a **procurement consequence** - what the
// buyer does differently - rather than a statistics definition. That phrasing is required
// by the product plan, and it is what makes the exit check ("a person who has never seen
// the app can explain each big number from its sentence alone") achievable.
//
// No figure is written here. Every one arrives from /api/metrics (AGENTS.md rule 2).

/** The bias tile reads differently depending on which way the forecast leaned. */
function biasTile(bias) {
  if (bias === null || bias === undefined) {
    return { title: 'Average lean', sentence: 'No matched half-hours in this range.' }
  }
  if (bias >= 0) {
    return {
      title: 'Runs high by',
      sentence:
        'Take this much off the forecast before you buy — it promises more wind than it delivers.',
    }
  }
  return {
    title: 'Runs low by',
    sentence:
      'Add this much to the forecast before you buy — more wind arrives than it promises.',
  }
}

function Tile({ title, measure, value, sentence, emphasis }) {
  return (
    <li className={`tile${emphasis ? ' tile-emphasis' : ''}`}>
      <p className="tile-title">
        {title} <span className="tile-measure">{measure}</span>
      </p>
      <p className="tile-value">
        {value} <span className="tile-unit">MW</span>
      </p>
      <p className="tile-sentence">{sentence}</p>
    </li>
  )
}

export default function StatTiles({ metrics }) {
  const raw = metrics.raw
  const corrected = metrics.bias_corrected
  const lean = biasTile(raw.bias)

  const matched = metrics.points_matched
  const requested = metrics.points_requested
  const below = metrics.forecast_below_actual
  const belowShare = matched > 0 ? Math.round((100 * below) / matched) : null

  return (
    <>
      <ul className="tiles">
        <Tile
          title="Typical miss"
          measure="MAE"
          value={formatMw(raw.mae === null ? null : Math.round(raw.mae))}
          sentence="Plan for about this much unplanned top-up on an ordinary half-hour."
        />
        <Tile
          title="With big misses weighted"
          measure="RMSE"
          value={formatMw(raw.rmse === null ? null : Math.round(raw.rmse))}
          sentence="Cover only the typical miss and the bad half-hours will still catch you out."
        />
        <Tile
          title={lean.title}
          measure="mean bias"
          value={formatSignedMw(raw.bias === null ? null : Math.round(raw.bias))}
          sentence={lean.sentence}
        />
        <Tile
          title="Safe 9 times in 10"
          measure="P90"
          value={formatMw(raw.p90 === null ? null : Math.round(raw.p90))}
          sentence="Buy cover for this and only one half-hour in ten goes past it."
          emphasis
        />
      </ul>

      {/* Decision 0005: every measure reports the n it was computed over, so coverage is
          never invisible. At high hours-ahead settings many points are legitimately
          missing, and an average over 81% of the month is not the same claim. */}
      <p className="tiles-foot">
        Measured over <strong>{matched.toLocaleString('en-GB')}</strong> of{' '}
        {requested.toLocaleString('en-GB')} half-hours
        {belowShare !== null && (
          <>
            {' '}· the forecast was <em>below</em> actual on {belowShare}% of them
          </>
        )}
      </p>

      <section className="panel corrected" aria-labelledby="corrected-heading">
        <h3 id="corrected-heading" className="panel-heading">
          After removing the known bias
        </h3>

        <ul className="corrected-row">
          <li>
            <span className="corrected-label">Typical miss</span>
            <span className="corrected-value">
              {formatMw(corrected.mae === null ? null : Math.round(corrected.mae))} MW
            </span>
          </li>
          <li>
            <span className="corrected-label">Big misses weighted</span>
            <span className="corrected-value">
              {formatMw(corrected.rmse === null ? null : Math.round(corrected.rmse))} MW
            </span>
          </li>
          <li>
            <span className="corrected-label">Safe 9 in 10</span>
            <span className="corrected-value">
              {formatMw(corrected.p90 === null ? null : Math.round(corrected.p90))} MW
            </span>
          </li>
          <li>
            <span className="corrected-label">Bias removed</span>
            <span className="corrected-value">
              {formatSignedMw(
                corrected.bias_used === null ? null : Math.round(corrected.bias_used),
              )}{' '}
              MW
            </span>
          </li>
        </ul>

        <p className="panel-note">
          The bias removed is measured over the selected range and mode — it is not a fixed
          number, and it changes when you change the dates.
        </p>

        <p className="panel-prose">
          <strong>Why the forecast runs high.</strong> The two feeds measure different
          things. WINDFOR forecasts the wind generation that will be <em>available</em>;
          FUELHH meters what was actually <em>delivered</em>, after curtailment and
          balancing actions reduced it. In GB wind is curtailed regularly, so forecast
          above actual is expected and a large part of this gap is not forecast error at
          all. The corrected figures above strip that systematic lean out and leave the
          part that is genuinely unpredictable — which is the number worth sizing a safety
          margin against. It is a lean, not a rule: the forecast still came in{' '}
          <em>below</em> actual on {belowShare === null ? 'some' : `${belowShare}% of`}{' '}
          matched half-hours, so this cannot be treated as a guaranteed one-way offset.
        </p>
      </section>
    </>
  )
}
