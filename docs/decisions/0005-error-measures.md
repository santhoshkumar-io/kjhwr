# 0005 — Which error numbers to show

**Status:** Decided (2026-10-27)

## Decision

Four measures, which are the four big numbers on Screen 2:

| Measure | Definition | Plain sentence it supports |
|---|---|---|
| **MAE** | mean(abs(forecast − actual)) | "The forecast typically missed by X MW." |
| **RMSE** | sqrt(mean((forecast − actual)^2)) | "Large misses are punished: X MW." |
| **Mean bias** | mean(forecast − actual) | "The forecast ran X MW high/low on average." |
| **P90 absolute error** | 90th percentile of abs(error) | "9 times out of 10 the miss was under X MW." |

Error is always defined **forecast minus actual**, so a positive number means the forecast was too
high. This sign convention is stated once here and must not be flipped anywhere in the code.

## Why these four

- **P90** is what makes the "9 times out of 10" sentence in the product plan literally true. MAE
  alone cannot support that claim.
- **Mean bias** is non-negotiable given the finding in [0006](0006-bias-correction.md): without it, a large one-directional
  offset would hide inside MAE and look like random error.
- **MAE** is the number a buyer can hold in their head.
- **RMSE** is included because a technical reviewer expects it, and because a buyer who cares about
  tail risk should see that big misses exist.

Every metric must also return **n**, the number of points it was computed over, so coverage is
never invisible — this matters at high hours-ahead settings, where many points are legitimately
missing.

## Consequences

- No other measures are added without a new decision record. In particular, MAPE was considered and
  left out: wind generation approaches zero, which makes percentage error explode and mislead.
- The bias-corrected variants of these same four measures are covered by [0006](0006-bias-correction.md).
