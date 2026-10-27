# 0002 — Which dates to cover

**Status:** Decided (2026-10-27)

## Context

`task.md` says: *"Please consider data relevant only for purchase decisions to be made in
January 2026."* The scope is defined by **decision** dates, not delivery dates. These are different
sets, and conflating them is the easiest way to get the range wrong.

## Decision

| | Range |
|---|---|
| Purchase decision days | **1 – 31 January 2026** |
| Delivery (target) days | **2 January – 1 February 2026** inclusive |
| Forecast publish times to download | **30 December 2025 – 1 February 2026** |

## Derivation — do not "simplify" this

A decision made on day *D* buys power for delivery on day *D+1*. So decisions on 1–31 Jan buy
delivery for 2 Jan – 1 Feb. That is **31 delivery days**, which is where the 1,488 figure comes
from: 31 × 48 half-hours.

The forecast publish range starts on 30 December because the hours-ahead slider reaches 48 hours:
the earliest target (2 Jan 00:00) minus 48h is 31 Dec 00:00, and we need runs published at or
before that cutoff.

Anyone who "corrects" the delivery range to 1–31 January will break the 1,488 row check and
silently answer a different question than the brief asked.

## Consequences

- `actuals.csv`: 1,488 half-hourly rows expected (January has no daylight-saving transition, so
  every day really does have 48 half-hours).
- `forecasts.csv`: roughly 20,000 rows (~8 runs/day x 73 hourly targets x ~34 publish days).
- UI copy may say "January 2026"; the axis and date picker show the real delivery range.
