// Formatting, in one place.
//
// Everything on Screen 1 is displayed in UTC, because both Elexon feeds are UTC and
// the buying deadline in decision 0001 is expressed in UTC. A browser in London in
// January would agree by accident; a browser anywhere else would silently shift every
// label by its own offset and quietly answer a different question. So every formatter
// here pins `timeZone: 'UTC'` and the axis says so out loud.
//
// The Intl formatters are built once at module scope rather than per call: the table
// view formats up to 1,488 rows x 4 columns, and constructing a DateTimeFormat is the
// expensive part.

const MISSING = '—'

const dayMonth = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'UTC',
  day: '2-digit',
  month: 'short',
})

const dayMonthYear = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'UTC',
  day: '2-digit',
  month: 'short',
  year: 'numeric',
})

const hourMinute = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'UTC',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

/** Megawatts with thousands separators. A missing value is a dash, never a zero. */
export function formatMw(value) {
  if (value === null || value === undefined) return MISSING
  return value.toLocaleString('en-GB')
}

/** Y-axis ticks, compact from a thousand up: 0, 5K, 10K. */
export function formatMwAxis(value) {
  if (value === 0) return '0'
  if (Math.abs(value) >= 1000) return `${value / 1000}K`
  return String(value)
}

/** "02 Jan" - the x-axis tick when the range spans more than one day. */
export function formatAxisDay(iso) {
  return dayMonth.format(new Date(iso))
}

/** "00:30" - the x-axis tick when the range is a single day. */
export function formatAxisTime(iso) {
  return hourMinute.format(new Date(iso))
}

/** "02 Jan 2026 00:30 UTC" - the tooltip heading. */
export function formatFullUtc(iso) {
  const at = new Date(iso)
  return `${dayMonthYear.format(at)} ${hourMinute.format(at)} UTC`
}

/** "01 Jan 09:30" - compact, for the publish time in a tooltip or table cell. */
export function formatShortUtc(iso) {
  if (!iso) return MISSING
  const at = new Date(iso)
  return `${dayMonth.format(at)} ${hourMinute.format(at)}`
}

/** "15.0 h" - lead time is genuinely fractional, so the half hour is kept. */
export function formatLeadHours(hours) {
  if (hours === null || hours === undefined) return MISSING
  return `${hours.toFixed(1)} h`
}

/**
 * The hold flag as words.
 *
 * Decision 0004 holds each hourly forecast across its two half-hours and requires the
 * distinction to stay visible. "held from the hour" is what a buyer needs to understand;
 * a raw `true` is not.
 */
export function formatHeld(isHeld) {
  if (isHeld === null || isHeld === undefined) return MISSING
  return isHeld ? 'held from the hour' : 'published for this half-hour'
}

export { MISSING }

/**
 * Megawatts with an explicit sign, for bias.
 *
 * Bias is the one measure whose direction is the point: +1,730 and -1,730 mean opposite
 * things to a buyer. A bare "1,730" would hide that, so the sign is always shown.
 */
export function formatSignedMw(value) {
  if (value === null || value === undefined) return MISSING
  const sign = value > 0 ? '+' : value < 0 ? '−' : ''
  return `${sign}${Math.abs(value).toLocaleString('en-GB')}`
}
