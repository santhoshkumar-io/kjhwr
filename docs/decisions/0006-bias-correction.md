# 0006 — Whether to show bias-corrected error

**Status:** Decided (2026-10-27)

## Context — a finding, not a theory

### Month-wide, measured in Phase 0

The whole range in [0002](0002-date-range.md), deadline mode per [0001](0001-buying-deadline.md),
hourly forecast held across the hour per [0004](0004-matching-times.md):

```
matched 1,488 of 1,488 half-hours (100%)
MAE        2,016 MW        RMSE   2,510 MW
mean bias +1,730 MW        P90    4,189 MW
bias-corrected:  MAE 1,407 MW     P90 3,132 MW
forecast was BELOW actual in 234 of 1,488 half-hours (16%)
```

Removing the mean bias cuts MAE from **2,016 to 1,407 MW** — a 30% reduction. That is the size of
the prize.

### Why the gap is structural and not forecasting skill

The clearest evidence is what happens at **zero lead time**. Selecting the newest forecast published
at or before the target time itself still leaves a bias of **+1,473 MW**:

| Lead time | MAE | Mean bias |
|---|---|---|
| 0 h | 1,691 MW | +1,473 MW |
| 24 h | 1,945 MW | +1,733 MW |
| 42 h | 2,226 MW | +1,848 MW |

A forecast published at the moment of delivery cannot be wrong by 1,473 MW through *forecasting*
error. Something other than weather prediction accounts for most of that gap:

- **WINDFOR** is a forecast of *available* wind generation — what the wind could produce.
- **FUELHH** WIND is *metered* output — what the wind actually delivered, after curtailment and
  after balancing actions reduced it.

In GB, wind is curtailed regularly. So forecast > actual is expected, and a large part of the gap
is **not forecast error at all**.

### One worked day, for illustration only

15 January 2026 under the same deadline (cutoff 14 Jan 11:00 UTC, so the 09:30 run):

```
n = 24 hourly targets
mean bias = +1,094 MW
MAE       =  1,094 MW
```

On that day MAE and mean bias were identical, because every one of the 24 errors was positive
(+113 MW to +2,386 MW). **Do not generalise from this day:** month-wide, the forecast was below
actual 16% of the time. The bias is systematic and large, but it is not absolute, and the app must
not claim it is.

## Decision

Report both, side by side, clearly labelled:

1. **Raw** — the four [0005](0005-error-measures.md) measures as-is. These stay primary: they are what the feeds actually
   say, and we do not hide them.
2. **Bias-corrected** — the same four measures computed after subtracting the mean bias for the
   selected date range and mode. This isolates the part of the miss that is genuinely unpredictable.

The app must also carry one short plain-English paragraph explaining why the forecast runs high.
This goes on Screen 2, in `docs/findings.md`, and in the README.

## Why both and not one

- **Raw only** would make the headline accuracy number mostly a measure of a definition mismatch.
  The "9 times out of 10 the miss was under X MW" claim would be inflated by a known, constant
  offset, and a reviewer would rightly challenge it.
- **Corrected only** would be worse: it would quietly hide a real and important property of the
  data, and the numbers would no longer match what anyone else querying Elexon would compute.

Both, labelled, is the honest answer — and it is the more useful one for the client. A buyer sizing
a safety margin wants the *unpredictable* component, because the predictable offset can simply be
subtracted before buying. That is an actionable finding, not a caveat.

## Consequences

- `/api/metrics` returns two sets of the four measures plus `n`.
- The bias used for correction is computed over the **selected range and mode**, not hardcoded. It
  changes when the user changes the date range, and it is displayed so the user can see it.
- Phase 2 needs a test where a fixture has a known constant offset: bias-corrected MAE must come
  out exactly zero.
- This is the most interesting thing in the data and should be one of the three findings in the
  customer video.
