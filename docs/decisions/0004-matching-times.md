# 0004 — How to match forecast times to real-wind times

**Status:** Decided (2026-10-27)

## Context

The two feeds are published at different resolutions. This was confirmed against the live API, not
assumed:

| Feed | Resolution | Rows per day |
|---|---|---|
| `FUELHH` (fuelType WIND) — actual | **30 minutes** | 48 |
| `WINDFOR` — forecast | **60 minutes** | 24 |

A naive join on `startTime` would match only the `:00` half-hours and silently drop half the
measured data. Something explicit has to be decided.

## Decision

**Hold the hourly forecast across the hour (zero-order hold).**

Each hourly forecast value applies to both half-hours inside that hour:

```
forecast for 10:00  ->  applies to target 10:00  (is_held = false)
                    ->  applies to target 10:30  (is_held = true)
```

This gives **1,488 comparison points** for the range in [0002](0002-date-range.md) — one for every measured half-hour.

## Why this, and why it is not the thing Phase 2 forbids

Phase 2 says *never fill or guess missing values*. That rule is about **absent data**: a target time
with no permitted forecast stays missing forever. It is not violated here, because nothing is
absent — WINDFOR's native resolution simply is hourly, and a forecast for "the 10:00 hour" is a
statement about the whole hour, including 10:30.

To keep that distinction visible rather than asserted:

- The hold lives in its own named function, `expand_hourly_to_half_hourly(...)`, so a reviewer can
  read it in isolation.
- Every expanded row carries the source run's `publishTime` **and** an `is_held` flag.
- `is_held` is returned by `/api/series` and shown in the Screen 1 hover text.

Nobody looking at the app can mistake a held value for an independently published one.

## Consequences

- 1,488 comparison points, so the comparison series and the actuals file have the same length.
- Half of all forecast values in the series are repeats. Error metrics therefore weight each
  forecast hour twice — once per half-hour. This is the intended reading ("how wrong was the
  forecast over this hour of delivery") but must be stated in the findings.
- `forecasts.csv` stores the **raw hourly** rows. The hold is applied in Phase 2, never in Phase 1,
  so it stays testable and reversible.

## Alternatives rejected

- **On-the-hour only** (compare `:00`, discard `:30`) — defensible and simpler, but throws away 744
  real measurements for no analytical gain.
- **Interpolate between hourly forecasts** — invents forecast values that were never published.
  This genuinely would be the thing Phase 2 forbids.
