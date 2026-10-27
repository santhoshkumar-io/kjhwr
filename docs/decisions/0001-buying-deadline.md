# 0001 — The buying deadline time

**Status:** Decided (2026-10-27)

## Context

The team buys on the UK day-ahead market one day before delivery. To reproduce what they could
really see, we need a single cutoff time: the moment after which a newly published forecast was no
longer available to the buyer.

## Decision

**11:00 London time on the day before the delivery day.**

This is day-ahead auction gate closure, the standard GB market deadline.

All delivery days in scope fall in January, when London = UTC (GMT, no daylight saving). So the
cutoff is **11:00 UTC** and no timezone conversion is needed anywhere in the code. This is a
property of the chosen date range, not a general truth — if the range ever moves outside
late-October-to-late-March, this record must be revisited and a real timezone conversion added.

## Consequences

- For any target time on 15 Jan, the cutoff is **14 Jan 11:00 UTC**.
- Observed WINDFOR publish times on 14 Jan were 02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30,
  22:30 UTC. The newest run at or before the cutoff is therefore the **09:30** run. The 11:30 run
  is 30 minutes too late and must be excluded.
- The deadline choice materially changes the results: a 12:00 cutoff would have picked up the
  fresher 11:30 run. 11:00 is the defensible market answer, not a tuned one.
- A forecast published at 11:00:01 is excluded. Phase 2 has a test for exactly this.

## Alternatives rejected

- **09:30** — more conservative, but picks the 07:30 run and makes the forecast ~2h staler than the
  market deadline really implies.
- **12:00** — freshest data, but flatters the result by assuming a deadline later than the real
  auction gate closure.
