"""Pick the forecast the buyer could really have seen, and pair it with what happened.

This is the heart of the project. Everything on screen comes from here.

The pipeline, in this order:

    raw hourly forecasts
      1. exclude_hindcasts          drop runs published after the hour they forecast
      2. expand_hourly_to_half_hourly   decision 0004 hold, adds is_held
      3. select_forecasts           newest run published at or before the cutoff
      4. build_series               join to actuals, compute error

**The order of steps 1 and 2 is not interchangeable.** Expanding changes target_time,
which changes the result of the hindcast test. A run published at 10:30 forecasting the
10:00 hour is a hindcast: it describes a period already under way. After expansion its
:30 copy has target_time 10:30, which is no longer earlier than its publish_time of
10:30, so it would survive a hindcast filter applied afterwards and could be selected
for the 10:30 half-hour. Filtering first means the hold only ever propagates forecasts
that were genuinely forward-looking for the hour they describe.

Pure functions only: DataFrames in, DataFrames out. No I/O, no file paths, no web
framework (AGENTS.md rule 6). Nothing is ever filled or guessed - a target time with no
permitted forecast stays missing (rule 3).

Error sign convention, set once in decision 0005: error = forecast - actual, so a
positive number means the forecast was too high.
"""

from __future__ import annotations

import pandas as pd

DEADLINE_MODE = "deadline"
HOURS_AHEAD_MODE = "hours_ahead"
MODES = (DEADLINE_MODE, HOURS_AHEAD_MODE)

# Decision 0001: 11:00 London on the day before delivery. Every delivery day in scope
# falls in January, when London is UTC, so no timezone conversion is needed. Kept as a
# parameter rather than a literal so tests can probe the boundary without magic numbers.
DEFAULT_DEADLINE_HOUR_UTC = 11

MAX_HOURS_AHEAD = 48


def exclude_hindcasts(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Drop rows whose target time precedes their own publish time.

    WINDFOR really contains these - 21% of the raw feed (see docs/notes/phase-0.md),
    because every run carries roughly a day of history alongside its forecast. A buyer
    could not have used a "forecast" for a period that had already happened, and
    AGENTS.md rule 4 forbids it.

    Must run before expand_hourly_to_half_hourly. See the module docstring.
    """
    keep = forecasts["target_time"] >= forecasts["publish_time"]
    return forecasts.loc[keep].reset_index(drop=True)


def expand_hourly_to_half_hourly(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Apply the decision 0004 zero-order hold.

    WINDFOR publishes hourly; FUELHH meters half-hourly. A forecast for "the 10:00 hour"
    is a statement about the whole hour, so it applies to both 10:00 and 10:30.

    Each input row becomes two output rows:

        target 10:00, is_held=False   the published target time
        target 10:30, is_held=True    the same value, held across the hour

    This is the one deliberate exception to "never invent data" (AGENTS.md rule 3), which
    is why `is_held` travels with the row all the way to the API and the hover text.
    Nothing downstream can mistake a held value for an independently published one.
    """
    on_the_hour = forecasts.copy()
    on_the_hour["is_held"] = False

    held = forecasts.copy()
    held["target_time"] = held["target_time"] + pd.Timedelta(minutes=30)
    held["is_held"] = True

    combined = pd.concat([on_the_hour, held], ignore_index=True)
    return combined.sort_values(["target_time", "publish_time"], kind="stable").reset_index(drop=True)


def deadline_cutoff(
    target_times: pd.Series, deadline_hour_utc: int = DEFAULT_DEADLINE_HOUR_UTC
) -> pd.Series:
    """Decision 0001: the buying deadline, on the day before the delivery day.

    For any target time on 15 Jan the cutoff is 14 Jan 11:00 UTC. Against the real
    publish times that selects the 09:30 run; the 11:30 run is half an hour too late.
    """
    delivery_day = target_times.dt.normalize()
    return delivery_day - pd.Timedelta(days=1) + pd.Timedelta(hours=deadline_hour_utc)


def hours_ahead_cutoff(target_times: pd.Series, hours: int) -> pd.Series:
    """Cutoff for "a forecast made at least X hours before delivery"."""
    return target_times - pd.Timedelta(hours=hours)


def cutoffs_for_mode(
    target_times: pd.Series,
    mode: str,
    hours: int | None = None,
    deadline_hour_utc: int = DEFAULT_DEADLINE_HOUR_UTC,
) -> pd.Series:
    """Dispatch to the right cutoff rule, validating the mode and hours."""
    if mode == DEADLINE_MODE:
        return deadline_cutoff(target_times, deadline_hour_utc)
    if mode == HOURS_AHEAD_MODE:
        if hours is None:
            raise ValueError("hours is required in hours_ahead mode")
        if not 0 <= hours <= MAX_HOURS_AHEAD:
            raise ValueError(f"hours must be between 0 and {MAX_HOURS_AHEAD}, got {hours}")
        return hours_ahead_cutoff(target_times, hours)
    raise ValueError(f"mode must be one of {MODES}, got {mode!r}")


def select_forecasts(
    forecasts: pd.DataFrame,
    target_times: pd.Series,
    mode: str,
    hours: int | None = None,
    deadline_hour_utc: int = DEFAULT_DEADLINE_HOUR_UTC,
) -> pd.DataFrame:
    """For each target time, the newest forecast published at or before the cutoff.

    `forecasts` must already have been through exclude_hindcasts and
    expand_hourly_to_half_hourly.

    Returns one row per requested target time, with `forecast_mw` left as NaN where no
    permitted run exists. That happens for real at high hours-ahead settings: each run's
    horizon ends at a fixed wall-clock point, so above about 42 hours the newest run
    allowed by the cutoff often does not reach the target at all. Those points are
    genuinely missing and are never substituted (AGENTS.md rule 3).
    """
    targets = pd.DataFrame({"target_time": pd.Series(target_times).reset_index(drop=True)})
    targets["cutoff"] = cutoffs_for_mode(targets["target_time"], mode, hours, deadline_hour_utc)

    # merge_asof requires BOTH frames sorted by the key it scans - globally, not merely
    # within each `by` group. Sorting only within groups fails quietly, with wrong
    # matches rather than an error.
    left = targets.sort_values("cutoff", kind="stable")
    right = forecasts.sort_values("publish_time", kind="stable")

    # direction="backward" takes the latest publish_time <= cutoff. allow_exact_matches
    # stays at its default True because decision 0001 says published *at or before* the
    # cutoff, so a run published exactly on the deadline is usable.
    matched = pd.merge_asof(
        left,
        right[["target_time", "publish_time", "generation_mw", "is_held"]],
        left_on="cutoff",
        right_on="publish_time",
        by="target_time",
        direction="backward",
        allow_exact_matches=True,
    )

    matched = matched.rename(columns={"generation_mw": "forecast_mw"})
    matched["lead_time_hours"] = (
        matched["target_time"] - matched["publish_time"]
    ).dt.total_seconds() / 3600.0

    return (
        matched[["target_time", "cutoff", "publish_time", "forecast_mw", "is_held", "lead_time_hours"]]
        .sort_values("target_time", kind="stable")
        .reset_index(drop=True)
    )


def build_series(
    actuals: pd.DataFrame,
    forecasts: pd.DataFrame,
    mode: str,
    hours: int | None = None,
    deadline_hour_utc: int = DEFAULT_DEADLINE_HOUR_UTC,
) -> pd.DataFrame:
    """The whole pipeline: raw inputs to one row per delivery half-hour.

    `actuals` has columns target_time, generation_mw (half-hourly).
    `forecasts` has columns target_time, publish_time, generation_mw (raw hourly).

    Returns target_time, actual_mw, forecast_mw, error_mw, publish_time, is_held,
    lead_time_hours - one row per actual half-hour, in time order. Missing on either
    side stays missing, so error_mw is NaN wherever no permitted forecast exists.
    """
    forward_looking = exclude_hindcasts(forecasts)
    held = expand_hourly_to_half_hourly(forward_looking)

    actual_series = actuals.sort_values("target_time", kind="stable").reset_index(drop=True)
    selected = select_forecasts(
        held, actual_series["target_time"], mode, hours, deadline_hour_utc
    )

    series = actual_series.rename(columns={"generation_mw": "actual_mw"}).merge(
        selected, on="target_time", how="left"
    )
    # Decision 0005: forecast minus actual, so positive means the forecast was too high.
    series["error_mw"] = series["forecast_mw"] - series["actual_mw"]

    return series[
        [
            "target_time",
            "actual_mw",
            "forecast_mw",
            "error_mw",
            "publish_time",
            "is_held",
            "lead_time_hours",
        ]
    ]
