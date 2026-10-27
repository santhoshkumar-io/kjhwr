# 0006 — Whether to show bias-corrected error

**Status:** Decided (2026-10-27)

## Context — a finding, not a theory

Before any code was written, one day of the real comparison was computed by hand against the live
API. For 15 January 2026 under the [0001](0001-buying-deadline.md) deadline (cutoff 14 Jan 11:00 UTC, so the 09:30 run):

```
n = 24 hourly targets
mean bias = +1,094 MW
MAE       =  1,094 MW
```

MAE and mean bias are **identical**, because every single one of the 24 errors was positive. The
forecast was higher than the actual at every hour of the day, by between +113 MW and +2,386 MW.

That is not the signature of forecast noise. It is the signature of the two feeds measuring
different quantities:

- **WINDFOR** is a forecast of *available* wind generation — what the wind could produce.
- **FUELHH** WIND is *metered* output — what the wind actually delivered, after curtailment and
  after balancing actions reduced it.

In GB, wind is curtailed regularly. So forecast > actual is expected, and a large part of the gap
is **not forecast error at all**.

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
