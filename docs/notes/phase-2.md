# Phase 2 — Pick the right forecast, measure the error: evidence

Date: 2026-10-27. Branch: `build`.

```bash
.venv/bin/python -m pytest -v
```

**68 tests, 68 passed, 0 skipped.**

## What was built

| File | Role |
|---|---|
| `backend/app/forecast_selection.py` | The pipeline: hindcast filter, the `0004` hold, cutoff rules, selection, join |
| `backend/app/metrics.py` | The `0005` measures, the `0006` correction, and the breakdowns |
| `backend/app/data_loading.py` | Typed CSV readers, path as an argument; Phase 4 reuses these |
| `backend/tests/test_forecast_selection.py` | 19 rule tests on hand-built fixtures |
| `backend/tests/test_metrics.py` | 27 arithmetic tests, every expected value derivable on paper |
| `backend/tests/test_january_golden.py` | 22 regression tests over the real committed data |
| `pytest.ini` | Makes `backend/app` importable as `app` |

## How the cutoff works, in plain English

**Deadline mode.** A buyer committing for delivery on 15 January had to act by 11:00 on
14 January (`0001`). So for every half-hour of 15 January, we keep only forecast runs published at
or before 14 Jan 11:00 and take the newest. On the real data that is the **09:30** run — the 11:30
run exists but was half an hour too late, and using it would overstate what the buyer knew.

**Hours-ahead mode.** For "a forecast made at least X hours before delivery", the cutoff is the
target time minus X hours, computed per half-hour.

In both modes a run published *after* the half-hour it describes is excluded outright, because a
forecast for a period that already happened is not a forecast. WINDFOR really contains those rows —
21% of the raw feed.

## The ordering that is easy to get wrong

```text
raw hourly forecasts
  1. exclude hindcasts            target_time < publish_time
  2. hold hourly -> half-hourly   decision 0004, adds is_held
  3. select newest run at or before the cutoff
  4. join to actuals, error = forecast - actual
```

Steps 1 and 2 **cannot** be swapped. Expanding changes `target_time`, which changes the result of
the hindcast test. A run published at 10:30 forecasting the 10:00 hour is a hindcast, but after
expansion its `:30` copy has `target_time` 10:30 — no longer earlier than its own `publish_time` —
so it would survive a filter applied afterwards and be served as the 10:30 forecast.

`test_hindcast_is_excluded_before_the_hold_not_after` pins both the correct behaviour and the fact
that the wrong order really does keep the row.

## A finding that changes Phase 6

The test suite caught something the plan had wrong. Bucketing a **deadline-mode** series by lead
time does not measure forecast staleness:

```text
correlation(lead_time_hours, hour of day) = 0.9993
distinct publish times used = 31, over 31 delivery days
```

Because the deadline is fixed at 11:00 the day before, exactly one run serves each delivery day, so
a target's lead time is just `14.5 h + its hour of day`. The buckets are hour-of-day buckets wearing
a lead-time label:

```text
bucket     n     MAE MW   really covers
12-18 h   217    2183     delivery hours 0-3
18-24 h   372    2238     delivery hours 3-9
24-30 h   372    1897     delivery hours 9-15
30-36 h   372    1870     delivery hours 15-21
36-42 h   155    1888     delivery hours 21-23
```

Built that way the chart **slopes the wrong way** — it looks as though older forecasts are better,
when it is really showing that overnight wind is harder to forecast than daytime wind.

The honest chart sweeps X in hours-ahead mode, which holds the hour-of-day mix constant. Then the
rise is real and attributable to staleness. `docs/product-plan.md` Phase 6 and the
`metrics_by_lead_time_bucket` docstring now both say so, and two tests pin it:
`test_lead_time_is_confounded_with_hour_of_day_in_deadline_mode` and
`test_error_rises_with_lead_time_when_x_is_swept_properly`.

## The January figures

These are the single source Phases 6 and 7 must quote.

```text
DEADLINE MODE, January 2026
  matched 1488 of 1488
  MAE 2016  RMSE 2510  bias +1730  P90 4189
  bias-corrected  MAE 1407  P90 3132  (bias removed +1730)
  forecast below actual: 234 (16%)

WORST 5 DAYS (by MAE)
  2026-01-28  MAE    5375 MW  bias   +5375 MW  n=48
  2026-01-12  MAE    4901 MW  bias   +4901 MW  n=48
  2026-01-11  MAE    4897 MW  bias   +4897 MW  n=48
  2026-01-21  MAE    3843 MW  bias   +3843 MW  n=48
  2026-01-27  MAE    3477 MW  bias   +3477 MW  n=48

HOURS-AHEAD SWEEP
   X    matched   MAE    bias
   0     1488    1691   +1473
   6     1488    1766   +1562
  12     1488    1804   +1594
  24     1488    1945   +1733
  36     1488    2154   +1831
  42     1488    2226   +1848
  44     1457    2266   +1853
  46     1333    2316   +1861
  48     1209    2316   +1810
```

Note that all five worst days have MAE equal to bias — on each of them *every* half-hour's forecast
was too high. That is the curtailment signature from `0006` showing up at day level.

## Verification

### Spot-check against the raw CSVs

```text
  selected run : 2026-01-14 09:30:00+00:00  (expect 2026-01-14 09:30)
  forecast     : 9053 MW
  actual       : 7672 MW
  error        : +1381 MW  (= forecast - actual)
  lead time    : 32.5 h
  is_held      : False
  candidate runs at/before cutoff in the raw CSV: 12, newest = 2026-01-14 09:30:00+00:00
  -> matches: the newest permitted run is the one selected
```

This is the same half-hour used in the very first API probe of the project, which reported forecast
9,053 MW against actual 7,672 MW for an error of +1,381 MW. The app code agrees.

### Three independent agreements on the same numbers

| Source | Method |
|---|---|
| Phase 0 | Direct from the live Elexon API, inside `explore_sample.py` |
| Phase 1 | From the saved CSVs with a separate stdlib `csv` reader, not pandas |
| Phase 2 | The real app code: `build_series` + `summarise` |

All three give MAE 2,016 / RMSE 2,510 / bias +1,730 / P90 4,189 / corrected 1,407 / 234 below
actual. The implementations were written separately, so the agreement is a genuine cross-check
rather than a tautology.

### The P90 method is now specified

`0005` originally said only "90th percentile", which is ambiguous. Nearest rank gives **4,189 MW**;
linear interpolation, the numpy and pandas default, gives **4,196.8 MW**. Nearest rank was chosen
and is now recorded in `0005`, because the number carries the claim *"9 times out of 10 the miss was
under this"* and that should be true of errors which actually happened. A reviewer recomputing with
`Series.quantile(0.9)` will see the 8 MW difference; it is this choice, not a bug.

### Purity

```text
$ grep -n "open(\|read_csv\|/Users/\|fastapi\|flask" backend/app/forecast_selection.py backend/app/metrics.py
  (no matches)
```

No I/O, no hardcoded paths, no web framework in the logic (`AGENTS.md` rule 6). CSV reading lives in
`data_loading.py`, which takes the path as an argument.

## Full pytest output

```text
============================= test session starts ==============================
platform darwin -- Python 3.12.15, pytest-9.1.1, pluggy-1.7.0 -- /Users/santhosh.kumar/Documents/weather-forcast-checker/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/santhosh.kumar/Documents/weather-forcast-checker
configfile: pytest.ini
testpaths: backend/tests
collecting ... collected 68 items

backend/tests/test_forecast_selection.py::test_forecast_published_one_minute_after_the_cutoff_is_ignored PASSED [  1%]
backend/tests/test_forecast_selection.py::test_forecast_published_exactly_on_the_cutoff_is_allowed PASSED [  2%]
backend/tests/test_forecast_selection.py::test_forecast_published_after_the_target_time_is_never_used[deadline-None] PASSED [  4%]
backend/tests/test_forecast_selection.py::test_forecast_published_after_the_target_time_is_never_used[hours_ahead-0] PASSED [  5%]
backend/tests/test_forecast_selection.py::test_target_with_no_allowed_forecast_is_missing_not_filled PASSED [  7%]
backend/tests/test_forecast_selection.py::test_deadline_cutoff_is_eleven_hundred_on_the_day_before PASSED [  8%]
backend/tests/test_forecast_selection.py::test_deadline_selects_the_0930_run_not_the_1130_run PASSED [ 10%]
backend/tests/test_forecast_selection.py::test_hold_produces_two_rows_per_forecast_hour_second_flagged PASSED [ 11%]
backend/tests/test_forecast_selection.py::test_hold_keeps_the_value_identical_so_it_is_traceable PASSED [ 13%]
backend/tests/test_forecast_selection.py::test_hindcast_is_excluded_before_the_hold_not_after PASSED [ 14%]
backend/tests/test_forecast_selection.py::test_target_beyond_the_horizon_is_missing_at_48_hours PASSED [ 16%]
backend/tests/test_forecast_selection.py::test_hours_ahead_picks_the_newest_run_within_the_cutoff PASSED [ 17%]
backend/tests/test_forecast_selection.py::test_error_is_forecast_minus_actual PASSED [ 19%]
backend/tests/test_forecast_selection.py::test_build_series_returns_one_row_per_actual_half_hour_in_time_order PASSED [ 20%]
backend/tests/test_forecast_selection.py::test_unknown_mode_is_rejected PASSED [ 22%]
backend/tests/test_forecast_selection.py::test_hours_outside_zero_to_fortyeight_is_rejected[-5] PASSED [ 23%]
backend/tests/test_forecast_selection.py::test_hours_outside_zero_to_fortyeight_is_rejected[49] PASSED [ 25%]
backend/tests/test_forecast_selection.py::test_hours_ahead_mode_requires_hours PASSED [ 26%]
backend/tests/test_forecast_selection.py::test_exclude_hindcasts_keeps_a_run_published_exactly_at_the_target PASSED [ 27%]
backend/tests/test_january_golden.py::test_the_saved_data_is_the_expected_shape PASSED [ 29%]
backend/tests/test_january_golden.py::test_deadline_mode_covers_every_half_hour PASSED [ 30%]
backend/tests/test_january_golden.py::test_raw_measures_match_the_recorded_figures[mae] PASSED [ 32%]
backend/tests/test_january_golden.py::test_raw_measures_match_the_recorded_figures[rmse] PASSED [ 33%]
backend/tests/test_january_golden.py::test_raw_measures_match_the_recorded_figures[bias] PASSED [ 35%]
backend/tests/test_january_golden.py::test_raw_measures_match_the_recorded_figures[p90] PASSED [ 36%]
backend/tests/test_january_golden.py::test_bias_corrected_measures_match_the_recorded_figures PASSED [ 38%]
backend/tests/test_january_golden.py::test_bias_correction_cuts_the_typical_miss_by_about_thirty_percent PASSED [ 39%]
backend/tests/test_january_golden.py::test_the_forecast_is_high_most_of_the_time_but_not_always PASSED [ 41%]
backend/tests/test_january_golden.py::test_lead_time_is_confounded_with_hour_of_day_in_deadline_mode PASSED [ 42%]
backend/tests/test_january_golden.py::test_error_rises_with_lead_time_when_x_is_swept_properly PASSED [ 44%]
backend/tests/test_january_golden.py::test_every_breakdown_reports_its_own_n PASSED [ 45%]
backend/tests/test_january_golden.py::test_hour_of_day_covers_all_twenty_four_hours PASSED [ 47%]
backend/tests/test_january_golden.py::test_worst_days_returns_five_real_january_dates PASSED [ 48%]
backend/tests/test_january_golden.py::test_slider_coverage_matches_the_measured_horizon_ceiling[0-1488] PASSED [ 50%]
backend/tests/test_january_golden.py::test_slider_coverage_matches_the_measured_horizon_ceiling[24-1488] PASSED [ 51%]
backend/tests/test_january_golden.py::test_slider_coverage_matches_the_measured_horizon_ceiling[42-1488] PASSED [ 52%]
backend/tests/test_january_golden.py::test_slider_coverage_matches_the_measured_horizon_ceiling[44-1457] PASSED [ 54%]
backend/tests/test_january_golden.py::test_slider_coverage_matches_the_measured_horizon_ceiling[46-1333] PASSED [ 55%]
backend/tests/test_january_golden.py::test_slider_coverage_matches_the_measured_horizon_ceiling[48-1209] PASSED [ 57%]
backend/tests/test_january_golden.py::test_slider_error_matches_the_measured_figures[0-1691] PASSED [ 58%]
backend/tests/test_january_golden.py::test_slider_error_matches_the_measured_figures[24-1945] PASSED [ 60%]
backend/tests/test_january_golden.py::test_slider_error_matches_the_measured_figures[48-2316] PASSED [ 61%]
backend/tests/test_january_golden.py::test_zero_lead_time_still_shows_a_large_positive_bias PASSED [ 63%]
backend/tests/test_january_golden.py::test_held_rows_are_exactly_half_the_series PASSED [ 64%]
backend/tests/test_metrics.py::test_mae_matches_hand_calculation PASSED  [ 66%]
backend/tests/test_metrics.py::test_bias_matches_hand_calculation PASSED [ 67%]
backend/tests/test_metrics.py::test_rmse_matches_hand_calculation PASSED [ 69%]
backend/tests/test_metrics.py::test_p90_matches_hand_calculation PASSED  [ 70%]
backend/tests/test_metrics.py::test_n_is_reported PASSED                 [ 72%]
backend/tests/test_metrics.py::test_rmse_is_at_least_mae PASSED          [ 73%]
backend/tests/test_metrics.py::test_percentile_nearest_rank_returns_an_observed_value PASSED [ 75%]
backend/tests/test_metrics.py::test_percentile_nearest_rank_never_interpolates PASSED [ 76%]
backend/tests/test_metrics.py::test_percentile_of_empty_is_an_error_not_a_guess PASSED [ 77%]
backend/tests/test_metrics.py::test_bias_corrected_mae_of_a_constant_offset_is_exactly_zero PASSED [ 79%]
backend/tests/test_metrics.py::test_bias_corrected_reports_the_bias_it_subtracted PASSED [ 80%]
backend/tests/test_metrics.py::test_bias_corrected_bias_is_zero_by_construction PASSED [ 82%]
backend/tests/test_metrics.py::test_bias_correction_reduces_mae_when_a_real_offset_exists PASSED [ 83%]
backend/tests/test_metrics.py::test_missing_errors_are_dropped_not_filled PASSED [ 85%]
backend/tests/test_metrics.py::test_empty_series_reports_zero_n_and_no_numbers PASSED [ 86%]
backend/tests/test_metrics.py::test_bias_corrected_empty_series_is_safe PASSED [ 88%]
backend/tests/test_metrics.py::test_lead_time_buckets_group_by_width PASSED [ 89%]
backend/tests/test_metrics.py::test_hour_of_day_groups_by_utc_hour PASSED [ 91%]
backend/tests/test_metrics.py::test_worst_days_are_ranked_by_mae_worst_first PASSED [ 92%]
backend/tests/test_metrics.py::test_worst_days_ranks_by_absolute_miss_not_bias PASSED [ 94%]
backend/tests/test_metrics.py::test_worst_days_limit_is_respected PASSED [ 95%]
backend/tests/test_metrics.py::test_summarise_keeps_raw_and_corrected_side_by_side PASSED [ 97%]
backend/tests/test_metrics.py::test_summarise_exposes_coverage_so_gaps_cannot_hide PASSED [ 98%]
backend/tests/test_metrics.py::test_summarise_counts_how_often_the_forecast_was_below_actual PASSED [100%]

============================== 68 passed in 0.65s ==============================
```

## Exit check

| Check | Result |
|---|---|
| Run published one minute after the cutoff is ignored | `test_forecast_published_one_minute_after_the_cutoff_is_ignored` |
| Run published after the target time never used, either mode | parametrized over both modes |
| Target with no permitted run is missing, not filled | `test_target_with_no_allowed_forecast_is_missing_not_filled` |
| Deadline for 15 Jan 18:00 is 14 Jan 11:00 and picks 09:30 not 11:30 | `test_deadline_selects_the_0930_run_not_the_1130_run` |
| Hold gives two rows per hour, second flagged `is_held` | `test_hold_produces_two_rows_per_forecast_hour_second_flagged` |
| At X=48 a target beyond the horizon is missing, not filled | `test_target_beyond_the_horizon_is_missing_at_48_hours` |
| Constant offset gives bias-corrected MAE of exactly zero | `test_bias_corrected_mae_of_a_constant_offset_is_exactly_zero` |
| Each measure checked against hand arithmetic | `test_metrics.py`, fixture documented in its module docstring |
| Pass count shown, zero skipped | 68 passed, 0 skipped |
| Notes record the January bias and MAE | above |

## Carried into Phase 3

- `backend/requirements.txt` needs `fastapi` and `uvicorn` added when the server first exists.
- The open item in `0003` is still open: measure pandas' bundle size and cold start on a Vercel
  Python function before relying on it. `data_loading.py` is the only module that needs pandas for
  I/O, so a stdlib fallback would be contained if the measurement comes out badly.
