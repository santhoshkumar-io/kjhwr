"""Golden regression test over the real committed January 2026 data.

The unit tests pin each rule on tiny fixtures, but they cannot catch a pipeline-level
mistake that is internally self-consistent - a swapped join, a lost filter, a re-sort
that changes which run gets selected. This test can, because the expected numbers were
produced twice already, independently of this implementation:

  1. Phase 0 computed them directly from the live Elexon API
     (backend/scripts/explore_sample.py, recorded in docs/notes/phase-0.md)
  2. Phase 1 reproduced them from the saved CSVs with a separate stdlib `csv` reader,
     not pandas (recorded in docs/notes/phase-1.md)

A third agreement from the real app code is therefore meaningful rather than circular.
If these figures drift, the meaning of the pipeline changed and the findings, the
screens and the video are all affected.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.data_loading import load_actuals, load_forecasts
from app.forecast_selection import DEADLINE_MODE, HOURS_AHEAD_MODE, build_series
from app.metrics import summarise

DATA = Path(__file__).resolve().parents[1] / "data"

# From docs/notes/phase-0.md and docs/notes/phase-1.md. Deadline mode, cutoff 11:00 UTC
# the day before delivery (0001), hourly forecast held across the hour (0004).
EXPECTED = {
    "n": 1488,
    "mae": 2016,
    "rmse": 2510,
    "bias": 1730,
    "p90": 4189,
    "corrected_mae": 1407,
    "corrected_p90": 3132,
    "below_actual": 234,
}


@pytest.fixture(scope="module")
def january_summary() -> dict:
    actuals = load_actuals(DATA / "actuals.csv")
    forecasts = load_forecasts(DATA / "forecasts.csv")
    series = build_series(actuals, forecasts, DEADLINE_MODE)
    return summarise(series)


def test_the_saved_data_is_the_expected_shape():
    """Guards the test itself: if the CSVs changed, the figures below mean nothing."""
    assert len(load_actuals(DATA / "actuals.csv")) == 1488
    assert len(load_forecasts(DATA / "forecasts.csv")) == 19856


def test_deadline_mode_covers_every_half_hour(january_summary):
    """100% coverage at the real buying deadline - no gaps to explain away."""
    assert january_summary["points_requested"] == EXPECTED["n"]
    assert january_summary["points_matched"] == EXPECTED["n"]


@pytest.mark.parametrize("measure", ["mae", "rmse", "bias", "p90"])
def test_raw_measures_match_the_recorded_figures(january_summary, measure):
    assert round(january_summary["raw"][measure]) == EXPECTED[measure]


def test_bias_corrected_measures_match_the_recorded_figures(january_summary):
    corrected = january_summary["bias_corrected"]
    assert round(corrected["mae"]) == EXPECTED["corrected_mae"]
    assert round(corrected["p90"]) == EXPECTED["corrected_p90"]
    assert round(corrected["bias_used"]) == EXPECTED["bias"]


def test_bias_correction_cuts_the_typical_miss_by_about_thirty_percent(january_summary):
    """The size of the prize in decision 0006, as a property rather than a constant."""
    raw_mae = january_summary["raw"]["mae"]
    corrected_mae = january_summary["bias_corrected"]["mae"]
    reduction = 1 - corrected_mae / raw_mae

    assert 0.25 < reduction < 0.35


def test_the_forecast_is_high_most_of_the_time_but_not_always(january_summary):
    """Decision 0006 was corrected once for overstating this. Pin it so it stays honest.

    A single day (15 Jan) had every error positive, which is what made the first draft
    of 0006 claim a universal positive gap. Month-wide, 16% of half-hours came in the
    other direction.
    """
    below = january_summary["forecast_below_actual"]
    assert below == EXPECTED["below_actual"]
    assert 0.10 < below / EXPECTED["n"] < 0.25, "systematic, but not absolute"


def test_lead_time_is_confounded_with_hour_of_day_in_deadline_mode():
    """A trap worth pinning, because the obvious chart would be misleading.

    In deadline mode the cutoff is fixed at 11:00 the day before, so exactly one run is
    used per delivery day and a target's lead time is determined by its hour of day:
    lead = 14.5 h for 00:00, rising to 38.0 h for 23:30. The correlation is 0.9993.

    So bucketing a deadline-mode series by lead time does NOT measure forecast
    staleness - it measures overnight-versus-daytime wind behaviour with a lead-time
    label on it. The "12-18 h" bucket is delivery hours 0-3; the "36-42 h" bucket is
    hours 21-23. Built that way, the chart even slopes the wrong way.

    Phase 6's hours-ahead chart must therefore come from sweeping X in hours_ahead mode
    (see the next test), where the hour of day varies within every X.
    """
    actuals = load_actuals(DATA / "actuals.csv")
    forecasts = load_forecasts(DATA / "forecasts.csv")
    series = build_series(actuals, forecasts, DEADLINE_MODE)

    correlation = series["lead_time_hours"].corr(series["target_time"].dt.hour)
    assert correlation > 0.99, "deadline-mode lead time is a proxy for hour of day"
    assert series["publish_time"].nunique() == 31, "one run per delivery day"


def test_error_rises_with_lead_time_when_x_is_swept_properly():
    """The Phase 6 expectation, measured the only way that isolates staleness.

    Sweeping X holds the hour-of-day mix constant across every setting, so the rise is
    attributable to the forecast being older. Phase 0 measured 1,691 MW at X=0 rising to
    2,316 MW at X=48.
    """
    actuals = load_actuals(DATA / "actuals.csv")
    forecasts = load_forecasts(DATA / "forecasts.csv")

    maes = []
    for hours in (0, 12, 24, 36):
        series = build_series(actuals, forecasts, HOURS_AHEAD_MODE, hours=hours)
        maes.append(summarise(series)["raw"]["mae"])

    assert maes == sorted(maes), f"MAE should rise with lead time, got {maes}"


def test_every_breakdown_reports_its_own_n(january_summary):
    """Coverage must never be invisible, in any breakdown."""
    for group in ("by_lead_time", "by_hour_of_day", "worst_days"):
        rows = january_summary[group]
        assert rows, f"{group} is empty"
        assert all(row["n"] > 0 for row in rows)


def test_hour_of_day_covers_all_twenty_four_hours(january_summary):
    hours = {row["hour_utc"] for row in january_summary["by_hour_of_day"]}
    assert hours == set(range(24))


def test_worst_days_returns_five_real_january_dates(january_summary):
    worst = january_summary["worst_days"]
    assert len(worst) == 5
    assert all(day["day"].startswith("2026-01") or day["day"] == "2026-02-01" for day in worst)
    # Worst first.
    maes = [day["mae"] for day in worst]
    assert maes == sorted(maes, reverse=True)


# ------------------------------------------------- the slider, against the Phase 0 table


@pytest.mark.parametrize(
    "hours,expected_matched",
    [(0, 1488), (24, 1488), (42, 1488), (44, 1457), (46, 1333), (48, 1209)],
)
def test_slider_coverage_matches_the_measured_horizon_ceiling(hours, expected_matched):
    """Coverage falls off above ~42 h because each run's horizon ends at a fixed
    wall-clock point. These counts come from the Phase 0 measurement table."""
    actuals = load_actuals(DATA / "actuals.csv")
    forecasts = load_forecasts(DATA / "forecasts.csv")
    series = build_series(actuals, forecasts, HOURS_AHEAD_MODE, hours=hours)

    assert int(pd.Series(series["error_mw"]).notna().sum()) == expected_matched


@pytest.mark.parametrize("hours,expected_mae", [(0, 1691), (24, 1945), (48, 2316)])
def test_slider_error_matches_the_measured_figures(hours, expected_mae):
    actuals = load_actuals(DATA / "actuals.csv")
    forecasts = load_forecasts(DATA / "forecasts.csv")
    series = build_series(actuals, forecasts, HOURS_AHEAD_MODE, hours=hours)

    assert round(summarise(series)["raw"]["mae"]) == expected_mae


def test_zero_lead_time_still_shows_a_large_positive_bias():
    """The strongest evidence that the gap is structural, not forecasting skill.

    A forecast published at the delivery moment cannot be wrong by 1,473 MW because the
    weather was hard to predict. WINDFOR forecasts available wind; FUELHH meters
    delivered wind after curtailment. This is the core argument of decision 0006 and the
    most interesting finding in the data, so it is pinned.
    """
    actuals = load_actuals(DATA / "actuals.csv")
    forecasts = load_forecasts(DATA / "forecasts.csv")
    series = build_series(actuals, forecasts, HOURS_AHEAD_MODE, hours=0)

    assert round(summarise(series)["raw"]["bias"]) == 1473


def test_held_rows_are_exactly_half_the_series():
    """Decision 0004: one published hourly value serves two half-hours.

    If this drifts, either the hold broke or the forecast feed stopped being hourly -
    both of which invalidate 0004.
    """
    actuals = load_actuals(DATA / "actuals.csv")
    forecasts = load_forecasts(DATA / "forecasts.csv")
    series = build_series(actuals, forecasts, DEADLINE_MODE)

    assert int(series["is_held"].sum()) == 744
    assert int((~series["is_held"].astype(bool)).sum()) == 744
