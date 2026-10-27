# Phase 0 — Confirm the data shape at month scale: evidence

Date: 2026-10-27. Branch: `build`. Script: `backend/scripts/explore_sample.py`.

Run with `python3 backend/scripts/explore_sample.py`. Exits 0 when every check passes, 1 otherwise.
It writes no files and imports nothing from the app — Phase 1 saves the data, this phase only
proves the assumptions the decision records rest on.

## Headline findings

1. **`/stream` has no date-range cap.** The paged form `/datasets/{ds}` rejects any range over
   7 days with HTTP 400. The `/stream` form returns the entire range in one request. `/stream` is
   also the form `task.md` links to. **Phase 1 therefore needs no chunking**, and the product plan's
   "small date chunks" instruction has been removed.
2. **`/stream` returns a bare JSON array** — no `{"data": [...]}` wrapper, unlike the paged form.
   This is the single most likely thing to break a naive parser, so `fetch_stream()` asserts the
   response type.
3. **Actuals are complete.** 1,488 rows, 31 delivery days, exactly 48 half-hours every day, no
   duplicates. January has no daylight-saving transition, so there is no 46/50-period day. The
   product plan's "or list every missing half-hour" escape clause was not needed.
4. **Forecasts are hourly; actuals are half-hourly.** This is what forces decision `0004`.
5. **21% of forecast rows are hindcast rows** (4,081 of 19,856) whose target precedes their own
   publish time. The `startTime >= publishTime` filter is load-bearing, not a formality.
6. **The bias is systematic but not absolute.** Month-wide the forecast was below actual in 16% of
   half-hours. The single-day sample used when `0006` was first written showed 100% positive errors;
   that record has been corrected.
7. **Error does rise with lead time**, from 1,691 MW at 0 h to 2,320 MW at 46 h. The product plan's
   original Phase 6 expectation was right and has been restored.

## Reference figures for Phase 2

Phase 2 reimplements the selection logic properly, with tests, in
`backend/app/forecast_selection.py`. It must reproduce these numbers. The two implementations were
written separately, so agreement between them is a meaningful cross-check rather than a tautology.

| Measure | Deadline mode, January 2026 |
|---|---|
| Matched points | 1,488 of 1,488 (100%) |
| MAE | 2,016 MW |
| RMSE | 2,510 MW |
| Mean bias | +1,730 MW |
| P90 absolute error | 4,189 MW |
| Bias-corrected MAE | 1,407 MW |
| Bias-corrected P90 | 3,132 MW |
| Forecast below actual | 234 of 1,488 (16%) |

## Full output

```text
Phase 0 - confirm the shape of the Elexon data at month scale.
base: https://data.elexon.co.uk/bmrs/api/v1  (no API key required)

1. Actuals - FUELHH, fuelType WIND, one request for the whole delivery range
----------------------------------------------------------------------------
  fetched 1488 rows in ONE request (2026-01-02 .. 2026-02-01)
  fields: ['dataset', 'fuelType', 'generation', 'publishTime', 'settlementDate', 'settlementPeriod', 'startTime']
  first 3 rows by target time:
    2026-01-02T00:00:00Z  sp= 1   15228 MW
    2026-01-02T00:30:00Z  sp= 2   15505 MW
    2026-01-02T01:00:00Z  sp= 3   15599 MW
  [PASS] exactly 1488 half-hourly rows  (got 1488)
  [PASS] no duplicate target times  (0 duplicates)
  [PASS] 31 distinct delivery days  (got 31)
  [PASS] every delivery day has exactly 48 half-hours  (no gaps, no DST break)
  [PASS] every target time is on a 30-minute boundary  (actuals are half-hourly)
  [PASS] all times are UTC (trailing Z)
  [PASS] fuelType filter returned WIND only

2. Forecasts - WINDFOR, one request for the whole publish range
---------------------------------------------------------------
  fetched 19856 rows in ONE request (2025-12-30T00:00Z .. 2026-02-02T00:00Z)
  fields: ['dataset', 'generation', 'publishTime', 'startTime']
  first 3 rows of the earliest run:
    pub 2025-12-30T02:30:00Z  target 2025-12-29T21:00:00Z    9160 MW
    pub 2025-12-30T02:30:00Z  target 2025-12-29T22:00:00Z    8937 MW
    pub 2025-12-30T02:30:00Z  target 2025-12-29T23:00:00Z    8781 MW
  runs: 272 over 34 publish days
  publish gap: 2.0h .. 4.0h
  max lead per run: 46.5h .. 66.5h
  [PASS] every forecast target time is on a whole hour  (forecasts are HOURLY, actuals are half-hourly)
  [PASS] exactly 8 runs published every day  (per-day counts seen: [8])
  [PASS] every run carries exactly 73 hourly targets  (sizes seen: [73])
  [PASS] gaps between runs stay within 2-4 hours  (2.0h .. 4.0h - cadence is irregular, so a cutoff can sit mid-gap)
  [PASS] max lead per run is ~46.5-66.5h (horizon ends at a fixed wall-clock point)  (46.5h .. 66.5h - this is why coverage falls off near X=48)
  [PASS] runs really do contain hindcast rows (target before publish)  (4081 of 19856 = 21%, so the filter is load-bearing)
  [PASS] no duplicate (target, publish) pair  (0 duplicates)

3. Date-range cap - the assumption that lets Phase 1 skip chunking
------------------------------------------------------------------
  paged form, 31-day range  -> HTTP 400
  stream form, 31-day range -> HTTP 200
  paged rejection says: {"type":"https://tools.ietf.org/html/rfc9110#section-15.5.1","title":"One or more validation errors occurred.","status":400,"errors":{"":["The date range between SettlementDateFrom and SettlementDateT
  [PASS] the paged form rejects a range over 7 days  (HTTP 400; '7 days' in body: True)
  [PASS] the /stream form accepts the full range (no cap)  (so Phase 1 needs no chunking; task.md links to /stream anyway)

4. Slider coverage and the lead-time ceiling (reference figures for Phase 2)
----------------------------------------------------------------------------
  DEADLINE MODE (cutoff 11:00Z the day before):
    matched 1488 of 1488 half-hours (100%)
    MAE     2016 MW      RMSE    2510 MW
    bias   +1730 MW      P90     4189 MW
    bias-corrected: MAE 1407 MW   P90 3132 MW
    forecast was BELOW actual in 234 of 1488 half-hours (16%)

    X(h)   matched/1488      MAE MW   bias MW
      0     1488 (100%)        1691     +1473
      6     1488 (100%)        1766     +1562
     12     1488 (100%)        1804     +1594
     24     1488 (100%)        1945     +1733
     36     1488 (100%)        2154     +1831
     42     1488 (100%)        2226     +1848
     44     1457 ( 98%)        2266     +1853
     46     1333 ( 90%)        2316     +1861
     47     1271 ( 85%)        2320     +1842
     48     1209 ( 81%)        2316     +1810
  [PASS] deadline mode covers every half-hour (no gaps at the real buying deadline)  (1488/1488)
  [PASS] the forecast is not always high - bias is systematic, not absolute  (below actual in 16% of half-hours)

Summary
-------
  all checks passed; the decision records in docs/decisions/ still hold
```

## Verification that the checks can actually fail

A check script that cannot fail proves nothing. Two assertions were deliberately broken and then
reverted.

Expecting 9 runs per day instead of 8:

```text
  [FAIL] exactly 8 runs published every day  (per-day counts seen: [8])
  ...
  1 CHECK(S) FAILED:
    - exactly 8 runs published every day
```

Inverting the hourly-resolution check, to confirm a failure names the decision it invalidates:

```text
  [FAIL] every forecast target time is on a whole hour
  1 CHECK(S) FAILED:
    - every forecast target time is on a whole hour  <-- invalidates decision 0004
```

Exit code was 1 in both cases and 0 after reverting. Other checks continued to run after a failure
rather than aborting at the first one, so a single broken assumption does not hide the rest.

## Environment note carried forward

The system interpreter on this machine is **Python 3.9.6**, while `0003` commits the project to
Python 3.12 (which the container will provide from Phase 3). This script is stdlib-only and
3.9-compatible on purpose, because it has to run before Docker exists.

From Phase 2 onward, app code and tests run in the container, so they may use 3.12 features. If
tests are ever expected to run on the bare host, either install 3.12 locally or keep the code
3.9-compatible — do not assume `python3` on this machine is 3.12.

## Changes made to earlier records

| File | Change |
|---|---|
| `docs/decisions/0006-bias-correction.md` | Corrected the overstated bias. Month-wide figures now lead the record; the 15 Jan all-positive day is kept as an illustration explicitly labelled not to generalise from. Added the zero-lead-time evidence (+1,473 MW at X=0), which is the strongest argument that the gap is structural. |
| `docs/decisions/0002-date-range.md` | "roughly 20,000 rows" replaced with the measured 19,856, plus the single-request finding. |
| `docs/product-plan.md` | Phase 0 step 4 now asserts the cap on both endpoint forms instead of assuming 7 days; Phase 1 drops chunking; Phase 1 row estimate replaced with the measured figure; Phase 6 exit check restored to expect a rising curve, with the coverage falloff above X=42 recorded. |

## Exit check

| Check | Result |
|---|---|
| Both feeds' resolutions stated with real rows as proof | yes — sections 1 and 2 of the output |
| Runs per day and largest publish gap for the whole month | 8 runs every day; gaps 2.0–4.0 h |
| Measured lead-time ceiling and coverage table | 46.5–66.5 h per run; table in section 4 |
| Date-range cap for both endpoint forms | paged 400, stream 200 |
| No delivery day missing from the actuals | 31 days, 48 rows each |
| No data files written, no app code | `backend/data/` still empty |
