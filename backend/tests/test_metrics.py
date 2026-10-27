"""Tests for the error measures, checked against arithmetic done by hand.

The fixture used throughout the headline tests is:

    errors        =  [1, -2, 3, -4, 10]      (forecast minus actual, decision 0005)
    absolute      =  [1,  2, 3,  4, 10]      sum 20
    n             =  5
    MAE           =  20 / 5                  =  4
    bias          =  (1 - 2 + 3 - 4 + 10) / 5 = 8 / 5 = 1.6
    RMSE          =  sqrt((1 + 4 + 9 + 16 + 100) / 5) = sqrt(26)
    P90           =  sorted_abs[int(0.9 * 4)] = sorted_abs[3] = 4

Every expected value above is derivable without running the code.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from app.metrics import (
    bias_corrected_metrics,
    error_metrics,
    metrics_by_hour_of_day,
    metrics_by_lead_time_bucket,
    percentile_nearest_rank,
    summarise,
    worst_days,
)

ERRORS = pd.Series([1, -2, 3, -4, 10], dtype="float64")


# ------------------------------------------------------------------ the four measures


def test_mae_matches_hand_calculation():
    assert error_metrics(ERRORS)["mae"] == pytest.approx(4.0)


def test_bias_matches_hand_calculation():
    assert error_metrics(ERRORS)["bias"] == pytest.approx(1.6)


def test_rmse_matches_hand_calculation():
    assert error_metrics(ERRORS)["rmse"] == pytest.approx(math.sqrt(26.0))


def test_p90_matches_hand_calculation():
    # int(0.9 * (5 - 1)) = int(3.6) = 3 -> the fourth smallest absolute error.
    assert error_metrics(ERRORS)["p90"] == pytest.approx(4.0)


def test_n_is_reported():
    assert error_metrics(ERRORS)["n"] == 5


def test_rmse_is_at_least_mae():
    """A property that holds for any data, and catches a swapped-formula mistake."""
    result = error_metrics(ERRORS)
    assert result["rmse"] >= result["mae"]


# -------------------------------------------------------------- the percentile method


def test_percentile_nearest_rank_returns_an_observed_value():
    """Decision 0005 chose nearest rank so the number is an error that really happened."""
    values = pd.Series([1.0, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    # int(0.9 * 9) = 8 -> the ninth smallest.
    assert percentile_nearest_rank(values) == 9.0


def test_percentile_nearest_rank_never_interpolates():
    """With two points the result is one of them, not the midpoint."""
    assert percentile_nearest_rank(pd.Series([10.0, 20.0])) in (10.0, 20.0)


def test_percentile_of_empty_is_an_error_not_a_guess():
    with pytest.raises(ValueError, match="cannot take a percentile of no values"):
        percentile_nearest_rank(pd.Series([], dtype="float64"))


# ------------------------------------------------------- decision 0006, bias correction


def test_bias_corrected_mae_of_a_constant_offset_is_exactly_zero():
    """The point of decision 0006.

    If every error is the same, the whole miss is a predictable offset: a buyer can
    subtract it before buying, and nothing unpredictable remains.
    """
    corrected = bias_corrected_metrics(pd.Series([5.0, 5.0, 5.0]))

    assert corrected["mae"] == pytest.approx(0.0)
    assert corrected["rmse"] == pytest.approx(0.0)
    assert corrected["p90"] == pytest.approx(0.0)
    assert corrected["bias_used"] == pytest.approx(5.0)


def test_bias_corrected_reports_the_bias_it_subtracted():
    """The page must be able to show what was removed, so it is never hidden."""
    assert bias_corrected_metrics(ERRORS)["bias_used"] == pytest.approx(1.6)


def test_bias_corrected_bias_is_zero_by_construction():
    assert bias_corrected_metrics(ERRORS)["bias"] == pytest.approx(0.0)


def test_bias_correction_reduces_mae_when_a_real_offset_exists():
    """errors [0, 10] -> bias 5 -> corrected [-5, +5] -> MAE 5, down from 5... equal.

    Use an asymmetric set where the reduction is unambiguous:
    errors [8, 10, 12] -> MAE 10, bias 10, corrected [-2, 0, 2] -> MAE 4/3.
    """
    raw = error_metrics(pd.Series([8.0, 10.0, 12.0]))
    corrected = bias_corrected_metrics(pd.Series([8.0, 10.0, 12.0]))

    assert raw["mae"] == pytest.approx(10.0)
    assert corrected["mae"] == pytest.approx(4.0 / 3.0)
    assert corrected["mae"] < raw["mae"]


# ----------------------------------------------------------------- missing data policy


def test_missing_errors_are_dropped_not_filled():
    """AGENTS.md rule 3. A NaN must not become a zero, which would flatter the result."""
    with_gap = pd.Series([1.0, float("nan"), 3.0])
    result = error_metrics(with_gap)

    assert result["n"] == 2, "n must reflect only the points actually used"
    assert result["mae"] == pytest.approx(2.0)  # (1 + 3) / 2, not (1 + 0 + 3) / 3


def test_empty_series_reports_zero_n_and_no_numbers():
    result = error_metrics(pd.Series([], dtype="float64"))
    assert result["n"] == 0
    assert result["mae"] is None


def test_bias_corrected_empty_series_is_safe():
    result = bias_corrected_metrics(pd.Series([], dtype="float64"))
    assert result["n"] == 0
    assert result["bias_used"] is None


# --------------------------------------------------------------------- the breakdowns


def series_fixture() -> pd.DataFrame:
    """Two delivery days, known errors, known lead times."""
    return pd.DataFrame(
        {
            "target_time": pd.to_datetime(
                [
                    "2026-01-15T00:00:00Z",
                    "2026-01-15T00:30:00Z",
                    "2026-01-16T12:00:00Z",
                    "2026-01-16T12:30:00Z",
                ],
                utc=True,
            ),
            "error_mw": [10.0, 10.0, 1.0, 1.0],
            "lead_time_hours": [2.0, 8.0, 2.0, 20.0],
        }
    )


def test_lead_time_buckets_group_by_width():
    buckets = metrics_by_lead_time_bucket(series_fixture(), width_hours=6)
    by_start = {b["lead_time_from_hours"]: b for b in buckets}

    assert set(by_start) == {0, 6, 18}
    assert by_start[0]["n"] == 2  # the two 2-hour leads
    assert by_start[0]["mae"] == pytest.approx(5.5)  # (10 + 1) / 2
    assert by_start[6]["n"] == 1
    assert by_start[6]["lead_time_to_hours"] == 12


def test_hour_of_day_groups_by_utc_hour():
    rows = metrics_by_hour_of_day(series_fixture())
    by_hour = {r["hour_utc"]: r for r in rows}

    assert set(by_hour) == {0, 12}
    assert by_hour[0]["mae"] == pytest.approx(10.0)
    assert by_hour[12]["mae"] == pytest.approx(1.0)
    assert by_hour[0]["n"] == 2


def test_worst_days_are_ranked_by_mae_worst_first():
    worst = worst_days(series_fixture())

    assert [row["day"] for row in worst] == ["2026-01-15", "2026-01-16"]
    assert worst[0]["mae"] == pytest.approx(10.0)


def test_worst_days_ranks_by_absolute_miss_not_bias():
    """A day wrong in both directions is still a bad day for a buyer.

    Day A: errors +10 and -10 -> bias 0 but MAE 10.
    Day B: errors +2 and +2   -> bias 2  but MAE 2.
    Day A must rank worse.
    """
    frame = pd.DataFrame(
        {
            "target_time": pd.to_datetime(
                [
                    "2026-01-15T00:00:00Z",
                    "2026-01-15T00:30:00Z",
                    "2026-01-16T00:00:00Z",
                    "2026-01-16T00:30:00Z",
                ],
                utc=True,
            ),
            "error_mw": [10.0, -10.0, 2.0, 2.0],
            "lead_time_hours": [12.0, 12.0, 12.0, 12.0],
        }
    )

    worst = worst_days(frame)
    assert worst[0]["day"] == "2026-01-15"
    assert worst[0]["bias"] == pytest.approx(0.0)
    assert worst[0]["mae"] == pytest.approx(10.0)


def test_worst_days_limit_is_respected():
    assert len(worst_days(series_fixture(), k=1)) == 1


# ------------------------------------------------------------------------- summarise


def test_summarise_keeps_raw_and_corrected_side_by_side():
    """Decision 0006: raw stays primary, corrected sits beside it clearly labelled."""
    result = summarise(series_fixture())

    assert set(result) >= {"raw", "bias_corrected", "points_matched", "points_requested"}
    assert result["raw"]["n"] == 4
    assert result["bias_corrected"]["bias_used"] == pytest.approx(5.5)


def test_summarise_exposes_coverage_so_gaps_cannot_hide():
    frame = series_fixture()
    frame.loc[0, "error_mw"] = float("nan")

    result = summarise(frame)
    assert result["points_requested"] == 4
    assert result["points_matched"] == 3


def test_summarise_counts_how_often_the_forecast_was_below_actual():
    """The number that stops decision 0006's bias claim being overstated."""
    frame = series_fixture()
    frame["error_mw"] = [10.0, -1.0, -2.0, 3.0]

    assert summarise(frame)["forecast_below_actual"] == 2
