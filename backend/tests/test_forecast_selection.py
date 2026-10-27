"""Tests for forecast selection, on tiny fixtures whose answers are known on paper.

Every fixture is small enough to check by hand. That is the point: a test that merely
re-runs the implementation and compares it to itself proves nothing, whereas these pin
the rules a buyer is relying on.

Real publish times are used where the product plan calls for them, so the tests also
document how the January data actually behaves.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.forecast_selection import (
    DEADLINE_MODE,
    HOURS_AHEAD_MODE,
    build_series,
    deadline_cutoff,
    exclude_hindcasts,
    expand_hourly_to_half_hourly,
    select_forecasts,
)


def forecasts(rows: list[tuple[str, str, int]]) -> pd.DataFrame:
    """Build a raw hourly forecast frame from (target_time, publish_time, mw) tuples."""
    return pd.DataFrame(
        {
            "target_time": pd.to_datetime([r[0] for r in rows], utc=True),
            "publish_time": pd.to_datetime([r[1] for r in rows], utc=True),
            "generation_mw": [r[2] for r in rows],
        }
    )


def actuals(rows: list[tuple[str, int]]) -> pd.DataFrame:
    """Build a half-hourly actuals frame from (target_time, mw) tuples."""
    return pd.DataFrame(
        {
            "target_time": pd.to_datetime([r[0] for r in rows], utc=True),
            "generation_mw": [r[1] for r in rows],
        }
    )


def targets(stamps: list[str]) -> pd.Series:
    return pd.Series(pd.to_datetime(stamps, utc=True))


# --------------------------------------------------------------- the cutoff is a wall


def test_forecast_published_one_minute_after_the_cutoff_is_ignored():
    """The buyer had committed by 11:00. A run at 11:01 was not available to them.

    This is the rule that makes the whole analysis honest, so it is tested at the
    boundary rather than somewhere comfortably inside it.
    """
    frame = forecasts(
        [
            ("2026-01-15T18:00:00Z", "2026-01-14T09:30:00Z", 1000),
            ("2026-01-15T18:00:00Z", "2026-01-14T11:01:00Z", 9999),
        ]
    )
    selected = select_forecasts(
        expand_hourly_to_half_hourly(exclude_hindcasts(frame)),
        targets(["2026-01-15T18:00:00Z"]),
        DEADLINE_MODE,
    )

    assert selected.loc[0, "forecast_mw"] == 1000, "the newer 11:01 run must be ignored"
    assert selected.loc[0, "publish_time"] == pd.Timestamp("2026-01-14T09:30:00Z")


def test_forecast_published_exactly_on_the_cutoff_is_allowed():
    """Decision 0001 says published *at or before* the cutoff, so 11:00:00 counts."""
    frame = forecasts([("2026-01-15T18:00:00Z", "2026-01-14T11:00:00Z", 1234)])
    selected = select_forecasts(
        expand_hourly_to_half_hourly(exclude_hindcasts(frame)),
        targets(["2026-01-15T18:00:00Z"]),
        DEADLINE_MODE,
    )

    assert selected.loc[0, "forecast_mw"] == 1234


@pytest.mark.parametrize("mode,hours", [(DEADLINE_MODE, None), (HOURS_AHEAD_MODE, 0)])
def test_forecast_published_after_the_target_time_is_never_used(mode, hours):
    """A "forecast" for a period that has already happened is not a forecast.

    WINDFOR really contains these rows - 21% of the raw feed - so this filter is live,
    not hypothetical.
    """
    frame = forecasts([("2026-01-15T18:00:00Z", "2026-01-15T19:00:00Z", 5000)])
    selected = select_forecasts(
        expand_hourly_to_half_hourly(exclude_hindcasts(frame)),
        targets(["2026-01-15T18:00:00Z"]),
        mode,
        hours,
    )

    assert pd.isna(selected.loc[0, "forecast_mw"])


def test_target_with_no_allowed_forecast_is_missing_not_filled():
    """AGENTS.md rule 3: a gap stays a gap. The actual value is still reported."""
    frame = forecasts([("2026-01-15T18:00:00Z", "2026-01-14T12:00:00Z", 4321)])
    series = build_series(
        actuals([("2026-01-15T18:00:00Z", 7000)]), frame, DEADLINE_MODE
    )

    assert pd.isna(series.loc[0, "forecast_mw"]), "the only run is after the 11:00 cutoff"
    assert pd.isna(series.loc[0, "error_mw"])
    assert series.loc[0, "actual_mw"] == 7000


# ------------------------------------------------------- the deadline, on real times


def test_deadline_cutoff_is_eleven_hundred_on_the_day_before():
    cutoff = deadline_cutoff(targets(["2026-01-15T18:00:00Z"]))
    assert cutoff.iloc[0] == pd.Timestamp("2026-01-14T11:00:00Z")


def test_deadline_selects_the_0930_run_not_the_1130_run():
    """Real WINDFOR publish times for 14 Jan 2026, from docs/notes/phase-0.md.

    The 11:30 run is half an hour too late for an 11:00 deadline. Picking it would
    overstate the forecast the buyer actually had.
    """
    frame = forecasts(
        [
            ("2026-01-15T18:00:00Z", "2026-01-14T07:30:00Z", 100),
            ("2026-01-15T18:00:00Z", "2026-01-14T09:30:00Z", 200),
            ("2026-01-15T18:00:00Z", "2026-01-14T11:30:00Z", 300),
        ]
    )
    selected = select_forecasts(
        expand_hourly_to_half_hourly(exclude_hindcasts(frame)),
        targets(["2026-01-15T18:00:00Z"]),
        DEADLINE_MODE,
    )

    assert selected.loc[0, "forecast_mw"] == 200
    assert selected.loc[0, "publish_time"] == pd.Timestamp("2026-01-14T09:30:00Z")


# ----------------------------------------------------------------- the decision 0004 hold


def test_hold_produces_two_rows_per_forecast_hour_second_flagged():
    frame = forecasts([("2026-01-15T10:00:00Z", "2026-01-15T09:00:00Z", 500)])
    held = expand_hourly_to_half_hourly(frame)

    assert len(held) == 2
    assert list(held["target_time"]) == [
        pd.Timestamp("2026-01-15T10:00:00Z"),
        pd.Timestamp("2026-01-15T10:30:00Z"),
    ]
    assert list(held["is_held"]) == [False, True]
    # The held row must carry the same value and the same source run.
    assert list(held["generation_mw"]) == [500, 500]
    assert held["publish_time"].nunique() == 1


def test_hold_keeps_the_value_identical_so_it_is_traceable():
    """The held row is a repeat, not an interpolation. is_held makes that visible."""
    frame = forecasts(
        [
            ("2026-01-15T10:00:00Z", "2026-01-15T09:00:00Z", 500),
            ("2026-01-15T11:00:00Z", "2026-01-15T09:00:00Z", 900),
        ]
    )
    held = expand_hourly_to_half_hourly(frame)

    by_target = dict(zip(held["target_time"].astype(str), held["generation_mw"]))
    assert by_target["2026-01-15 10:30:00+00:00"] == 500, "10:30 holds the 10:00 value"
    assert by_target["2026-01-15 11:00:00+00:00"] == 900, "not interpolated towards 900"


# ------------------------------------------- ordering: hindcast filter before the hold


def test_hindcast_is_excluded_before_the_hold_not_after():
    """The ordering hazard, pinned.

    A run published at 10:30 forecasting the 10:00 hour is a hindcast. If the hold ran
    first, its :30 copy would have target_time 10:30 - no longer earlier than its own
    publish_time - so it would survive a filter applied afterwards and be served as the
    10:30 half-hour's forecast. Both half-hours must come back empty.
    """
    frame = forecasts([("2026-01-15T10:00:00Z", "2026-01-15T10:30:00Z", 777)])

    series = build_series(
        actuals([("2026-01-15T10:00:00Z", 100), ("2026-01-15T10:30:00Z", 200)]),
        frame,
        HOURS_AHEAD_MODE,
        hours=0,
    )

    assert series["forecast_mw"].isna().all(), "a hindcast must not reappear via the hold"

    # And demonstrate the hazard is real: in the wrong order the row survives.
    wrong_order = exclude_hindcasts(expand_hourly_to_half_hourly(frame))
    assert len(wrong_order) == 1, "expand-then-filter wrongly keeps the 10:30 copy"
    assert wrong_order.loc[0, "is_held"]


# ------------------------------------------------------------------- the horizon ceiling


def test_target_beyond_the_horizon_is_missing_at_48_hours():
    """At high hours-ahead settings the permitted run often does not reach the target.

    Each WINDFOR run's horizon ends at a fixed wall-clock point, so above about 42 hours
    coverage falls away. Those points are genuinely missing, not zero and not carried
    forward.
    """
    # The only run covering this target was published well after the X=48 cutoff of
    # 13 Jan 00:00, which is what "the horizon does not reach back far enough" looks like.
    frame = forecasts([("2026-01-15T00:00:00Z", "2026-01-14T09:30:00Z", 8000)])
    selected = select_forecasts(
        expand_hourly_to_half_hourly(exclude_hindcasts(frame)),
        targets(["2026-01-15T00:00:00Z"]),
        HOURS_AHEAD_MODE,
        hours=48,
    )

    assert pd.isna(selected.loc[0, "forecast_mw"])


def test_hours_ahead_picks_the_newest_run_within_the_cutoff():
    frame = forecasts(
        [
            ("2026-01-15T12:00:00Z", "2026-01-14T00:00:00Z", 10),
            ("2026-01-15T12:00:00Z", "2026-01-15T00:00:00Z", 20),  # exactly 12h ahead
            ("2026-01-15T12:00:00Z", "2026-01-15T06:00:00Z", 30),  # only 6h ahead
        ]
    )
    selected = select_forecasts(
        expand_hourly_to_half_hourly(exclude_hindcasts(frame)),
        targets(["2026-01-15T12:00:00Z"]),
        HOURS_AHEAD_MODE,
        hours=12,
    )

    assert selected.loc[0, "forecast_mw"] == 20
    assert selected.loc[0, "lead_time_hours"] == 12.0


# ---------------------------------------------------------------------- error and signs


def test_error_is_forecast_minus_actual():
    """Decision 0005's sign convention: positive means the forecast ran high."""
    frame = forecasts([("2026-01-15T10:00:00Z", "2026-01-14T09:30:00Z", 1200)])
    series = build_series(actuals([("2026-01-15T10:00:00Z", 1000)]), frame, DEADLINE_MODE)

    assert series.loc[0, "error_mw"] == 200

    under = build_series(actuals([("2026-01-15T10:00:00Z", 1500)]), frame, DEADLINE_MODE)
    assert under.loc[0, "error_mw"] == -300


def test_build_series_returns_one_row_per_actual_half_hour_in_time_order():
    frame = forecasts([("2026-01-15T10:00:00Z", "2026-01-14T09:30:00Z", 1200)])
    series = build_series(
        actuals([("2026-01-15T10:30:00Z", 900), ("2026-01-15T10:00:00Z", 1000)]),
        frame,
        DEADLINE_MODE,
    )

    assert len(series) == 2
    assert list(series["target_time"]) == [
        pd.Timestamp("2026-01-15T10:00:00Z"),
        pd.Timestamp("2026-01-15T10:30:00Z"),
    ]
    # Both half-hours take the 10:00 forecast; the second is the held copy.
    assert list(series["forecast_mw"]) == [1200, 1200]
    assert list(series["is_held"]) == [False, True]


# ------------------------------------------------------------------ input validation


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError, match="mode must be one of"):
        select_forecasts(
            expand_hourly_to_half_hourly(forecasts([("2026-01-15T10:00:00Z", "2026-01-14T09:00:00Z", 1)])),
            targets(["2026-01-15T10:00:00Z"]),
            "xyz",
        )


@pytest.mark.parametrize("hours", [-5, 49])
def test_hours_outside_zero_to_fortyeight_is_rejected(hours):
    with pytest.raises(ValueError, match="hours must be between 0 and 48"):
        select_forecasts(
            expand_hourly_to_half_hourly(forecasts([("2026-01-15T10:00:00Z", "2026-01-14T09:00:00Z", 1)])),
            targets(["2026-01-15T10:00:00Z"]),
            HOURS_AHEAD_MODE,
            hours,
        )


def test_hours_ahead_mode_requires_hours():
    with pytest.raises(ValueError, match="hours is required"):
        select_forecasts(
            expand_hourly_to_half_hourly(forecasts([("2026-01-15T10:00:00Z", "2026-01-14T09:00:00Z", 1)])),
            targets(["2026-01-15T10:00:00Z"]),
            HOURS_AHEAD_MODE,
        )


def test_exclude_hindcasts_keeps_a_run_published_exactly_at_the_target():
    """Published at the target moment is a zero-lead-time forecast, not a hindcast."""
    frame = forecasts([("2026-01-15T10:00:00Z", "2026-01-15T10:00:00Z", 42)])
    assert len(exclude_hindcasts(frame)) == 1
