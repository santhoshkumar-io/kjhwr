// The control state, and its two-way mapping to the URL query string.
//
// Why the URL carries the state: a buyer can send a colleague the exact view they are
// looking at, which is the whole point of a shared analysis tool. It also makes every
// state of this screen reachable without clicking - which is how the Phase 5 exit checks
// get screenshotted, since a headless browser cannot drag a slider.
//
// The mode names are the server's, spelled exactly as `forecast_selection.MODES` has
// them. They travel from here into the query string and back out of `applied.mode`, so a
// mismatch would be a 400 rather than something subtle.

export const DEADLINE = 'deadline'
export const HOURS_AHEAD = 'hours_ahead'

export const MIN_HOURS = 0
export const MAX_HOURS = 48

/** The slider's position when the page is opened without one. */
const DEFAULT_HOURS = 24

function clampDate(value, earliest, latest) {
  if (!value) return null
  if (earliest && value < earliest) return earliest
  if (latest && value > latest) return latest
  return value
}

function clampHours(value) {
  const hours = Number.parseInt(value, 10)
  if (Number.isNaN(hours)) return DEFAULT_HOURS
  return Math.min(MAX_HOURS, Math.max(MIN_HOURS, hours))
}

/**
 * Read the controls out of a query string, falling back to the full delivery range.
 *
 * `bounds` comes from `/api/health`, so the defaults and the clamping are the server's
 * real delivery range rather than dates typed in here (AGENTS.md rule 2).
 */
export function readControls(search, bounds) {
  const params = new URLSearchParams(search)
  const mode = params.get('mode') === HOURS_AHEAD ? HOURS_AHEAD : DEADLINE

  return {
    mode,
    hours: clampHours(params.get('hours')),
    start: clampDate(params.get('start'), bounds.earliest, bounds.latest) || bounds.earliest,
    end: clampDate(params.get('end'), bounds.earliest, bounds.latest) || bounds.latest,
  }
}

/** The query string to put in the address bar. */
export function controlsToSearch(controls) {
  const params = new URLSearchParams({
    start: controls.start,
    end: controls.end,
    mode: controls.mode,
    hours: String(controls.hours),
  })
  return `?${params.toString()}`
}

/**
 * The `/api/series` URL for these controls.
 *
 * `hours` is sent in both modes on purpose. Phase 4 accepts it in deadline mode, ignores
 * it, and reports `applied.hours: null`, which means the slider can stay mounted and keep
 * its position without the frontend special-casing every request. The slider shows this
 * component's own `hours`; `applied.hours` is what the server says it actually used, and
 * those two are deliberately different things.
 */
export function seriesUrl(controls) {
  return `/api/series${controlsToSearch(controls)}`
}

/** The `/api/metrics` URL for these controls - the same settings Screen 1 uses. */
export function metricsUrl(controls) {
  return `/api/metrics${controlsToSearch(controls)}`
}

/** How far apart the swept points are, in hours. 25 points across 0-48. */
export const SWEEP_STEP = 2

/**
 * The URLs for the "miss vs how far ahead" sweep.
 *
 * This chart must be built by sweeping X across whole series, never by bucketing a
 * deadline-mode series by lead time. In deadline mode one run serves each delivery day,
 * so a target's lead time is just its hour of day plus a constant - the two correlate at
 * 0.9993 - and a lead-time-bucketed chart relabels overnight wind behaviour as forecast
 * staleness. It even slopes the wrong way.
 *
 * The sweep follows the selected **date range** but not the mode, because sweeping the
 * hours-ahead setting is itself the mode. That is said on the chart so it does not look
 * like the mode switch is being ignored.
 */
export function sweepPoints(controls) {
  const points = []
  for (let hours = MIN_HOURS; hours <= MAX_HOURS; hours += SWEEP_STEP) {
    points.push({
      hours,
      url: metricsUrl({ ...controls, mode: HOURS_AHEAD, hours }),
    })
  }
  return points
}
