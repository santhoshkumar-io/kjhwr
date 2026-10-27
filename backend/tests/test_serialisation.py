"""Tests for the JSON-safety layer.

These are unit tests on a tiny hand-made frame rather than endpoint tests, because the
rules they pin are the ones that only bite on a partially matched series. Going through
HTTP would test them too, but it would not make it obvious *why* each rule exists.

The frame below deliberately mixes a matched row with an unmatched one, which is what
pandas does to the dtypes in real life: `forecast_mw` widens to float64 and `is_held`
degrades to an object column holding a float `nan`.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from app.serialisation import TIMESTAMP_FORMAT, json_value, series_to_records


def frame_with_a_gap() -> pd.DataFrame:
    """One matched half-hour and one with no permitted forecast."""
    return pd.DataFrame(
        {
            "target_time": pd.to_datetime(
                ["2026-01-02T00:00:00Z", "2026-01-02T00:30:00Z"]
            ),
            "actual_mw": [15228, 15000],
            "forecast_mw": [18699.0, float("nan")],
            "error_mw": [3471.0, float("nan")],
            "publish_time": pd.to_datetime(["2026-01-01T09:30:00Z", None]),
            "is_held": [False, float("nan")],
            "lead_time_hours": [14.5, float("nan")],
        }
    )


def test_timestamps_use_the_same_format_as_the_health_endpoint():
    """`/api/health` emits ...Z via strftime, and test_health.py pins it.

    FastAPI's own encoder would emit +00:00 here instead, forking the wire format inside
    one API. The format is applied deliberately, so pin it.
    """
    value = json_value("target_time", pd.Timestamp("2026-01-02T00:30:00Z"))

    assert value == "2026-01-02T00:30:00Z"
    assert value.endswith("Z")
    assert "+00:00" not in value


@pytest.mark.parametrize("missing", [None, float("nan"), pd.NaT])
@pytest.mark.parametrize("field", ["forecast_mw", "publish_time", "is_held", "lead_time_hours"])
def test_every_kind_of_missing_becomes_null(field, missing):
    """NaN, NaT and None arrive from different columns of the same frame.

    AGENTS.md rule 3: missing stays missing. Not zero, not a filled value.
    """
    assert json_value(field, missing) is None


def test_is_held_is_never_a_float():
    """Decision 0004 requires the hold flag to stay visible and unambiguous.

    On an unmatched row the column holds a float nan, so without an explicit rule the
    client would receive a number where it expects a flag.
    """
    assert json_value("is_held", True) is True
    assert json_value("is_held", False) is False
    assert json_value("is_held", float("nan")) is None


def test_whole_megawatt_values_stay_integers_even_when_pandas_widens_them():
    """A gap anywhere in the series turns the MW columns float64.

    Normalising integral values back to int keeps the wire type the same whether or not
    the requested settings happen to have full coverage.
    """
    assert json_value("forecast_mw", 18699.0) == 18699
    assert isinstance(json_value("forecast_mw", 18699.0), int)


def test_lead_time_stays_a_float_so_half_hours_survive():
    """Lead time is genuinely fractional - 14.5 hours is normal, not a rounding artefact."""
    assert json_value("lead_time_hours", 14.5) == 14.5
    assert isinstance(json_value("lead_time_hours", 14.0), float)


def test_a_row_with_no_forecast_is_returned_not_dropped():
    """The gap is the finding. Screen 1 cannot count "N of 1,488" from omitted rows."""
    records = series_to_records(frame_with_a_gap())

    assert len(records) == 2
    gap = records[1]
    assert gap["target_time"] == "2026-01-02T00:30:00Z"
    assert gap["actual_mw"] == 15000
    assert gap["forecast_mw"] is None
    assert gap["error_mw"] is None
    assert gap["publish_time"] is None
    assert gap["is_held"] is None
    assert gap["lead_time_hours"] is None


def test_the_matched_row_keeps_every_real_value():
    matched = series_to_records(frame_with_a_gap())[0]

    assert matched == {
        "target_time": "2026-01-02T00:00:00Z",
        "actual_mw": 15228,
        "forecast_mw": 18699,
        "error_mw": 3471,
        "publish_time": "2026-01-01T09:30:00Z",
        "is_held": False,
        "lead_time_hours": 14.5,
    }


def test_the_output_survives_a_strict_json_encoder():
    """This is the test that would have caught the 500.

    Starlette renders with allow_nan=False, so a NaN left in the payload raises and the
    request fails with no clue as to why. `json.dumps` with the same setting is the same
    check, one layer down.
    """
    records = series_to_records(frame_with_a_gap())

    body = json.dumps(records, allow_nan=False)

    assert "NaN" not in body
    assert "NaT" not in body
    assert body.count("null") == 5


def test_the_timestamp_format_constant_is_the_one_actually_used():
    """Guards against the format drifting away from the constant that documents it."""
    assert pd.Timestamp("2026-01-02T00:00:00Z").strftime(TIMESTAMP_FORMAT) == (
        "2026-01-02T00:00:00Z"
    )
