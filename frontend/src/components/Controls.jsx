import { DEADLINE, HOURS_AHEAD, MAX_HOURS, MIN_HOURS } from '../lib/seriesUrl.js'

// One filter row, above everything it scopes.
//
// Phase 6's accuracy screen follows the same date range and mode as this screen, so this
// component is deliberately presentational: it owns no state and reports changes upward.
// Lifting the state from Screen 1 to App in Phase 6 then needs no change here.
//
// The date inputs carry min and max from `/api/health`, so the picker cannot offer a day
// the server would refuse. That is the "page cannot choose a date outside the range" exit
// check; the server's own 400 is the backstop for a hand-typed URL.

export default function Controls({ controls, bounds, onChange, disabled }) {
  const isHoursAhead = controls.mode === HOURS_AHEAD

  function set(patch) {
    onChange({ ...controls, ...patch })
  }

  return (
    <section className="controls" aria-label="Chart settings">
      <div className="control-group">
        <label className="control-label" htmlFor="from-date">
          From
        </label>
        <input
          id="from-date"
          type="date"
          className="control-input"
          value={controls.start}
          min={bounds.earliest}
          max={controls.end}
          disabled={disabled}
          onChange={(event) => set({ start: event.target.value })}
        />
      </div>

      <div className="control-group">
        <label className="control-label" htmlFor="to-date">
          To
        </label>
        <input
          id="to-date"
          type="date"
          className="control-input"
          value={controls.end}
          min={controls.start}
          max={bounds.latest}
          disabled={disabled}
          onChange={(event) => set({ end: event.target.value })}
        />
      </div>

      <fieldset className="control-group mode-group" disabled={disabled}>
        <legend className="control-label">Which forecast</legend>

        <label className="radio">
          <input
            type="radio"
            name="mode"
            value={DEADLINE}
            checked={!isHoursAhead}
            onChange={() => set({ mode: DEADLINE })}
          />
          <span>Day-ahead deadline</span>
        </label>

        <label className="radio">
          <input
            type="radio"
            name="mode"
            value={HOURS_AHEAD}
            checked={isHoursAhead}
            onChange={() => set({ mode: HOURS_AHEAD })}
          />
          <span>Forecast made at least X hours before</span>
        </label>
      </fieldset>

      <div className="control-group slider-group">
        <label className="control-label" htmlFor="hours-ahead">
          Hours before delivery
        </label>
        <div className="slider-row">
          <input
            id="hours-ahead"
            type="range"
            className="control-slider"
            min={MIN_HOURS}
            max={MAX_HOURS}
            step="1"
            value={controls.hours}
            // Left enabled in deadline mode would imply it does something, so it is
            // disabled rather than hidden: the reader can see the setting exists and
            // which mode it belongs to.
            disabled={disabled || !isHoursAhead}
            onChange={(event) => set({ hours: Number(event.target.value) })}
          />
          <output className="slider-value" htmlFor="hours-ahead">
            {isHoursAhead ? `${controls.hours} h` : '—'}
          </output>
        </div>
      </div>
    </section>
  )
}
