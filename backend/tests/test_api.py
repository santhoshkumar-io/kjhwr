"""Tests for the two Phase 4 data endpoints.

Three kinds of test here, and they are checking different things:

1. **The numbers are the Phase 2 numbers.** The endpoints must not quietly recompute or
   round anything, so the golden figures below are the same ones `test_january_golden.py`
   asserts against the pure functions. If an endpoint ever disagrees with the engine, one
   of these fails.
2. **Bad settings are refused with 400 and a sentence.** The Phase 4 exit check lists the
   cases; they are all here, including `hours=abc`, which is the one that would come back
   as FastAPI's 422 if the route ever declared a typed parameter.
3. **A partially matched series survives serialisation.** At `hours=48` a fifth of the
   rows have no permitted forecast. That path returns 500 if NaN reaches the renderer, and
   silently returns the string "NaT" if the framework's encoder handles the timestamps.

The golden figures come from `docs/notes/phase-2.md`, which records them as the single
source later phases quote.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Deadline mode over the whole delivery range, from docs/notes/phase-2.md.
JANUARY = {
    "n": 1488,
    "mae": 2016,
    "rmse": 2510,
    "bias": 1730,
    "p90": 4189,
    "corrected_mae": 1407,
    "corrected_p90": 3132,
    "below_actual": 234,
}

# The worst delivery day in the month, and the half of the series that is held.
WORST_DAY = "2026-01-28"
WORST_DAY_MAE = 5375
HELD_ROWS = 744


def test_series_returns_one_row_per_delivery_half_hour():
    body = client.get("/api/series?mode=deadline").json()

    assert body["points_requested"] == JANUARY["n"]
    assert body["points_matched"] == JANUARY["n"]
    assert len(body["points"]) == JANUARY["n"]


@pytest.mark.parametrize("measure", ["mae", "rmse", "bias", "p90"])
def test_metrics_match_the_recorded_january_figures(measure):
    """The endpoint must agree with the engine, not approximate it."""
    body = client.get("/api/metrics?mode=deadline").json()

    assert round(body["raw"][measure]) == JANUARY[measure]


def test_metrics_report_the_bias_corrected_set_beside_the_raw_one():
    """Decision 0006: both, side by side, with the bias that was removed stated."""
    body = client.get("/api/metrics?mode=deadline").json()

    assert round(body["bias_corrected"]["mae"]) == JANUARY["corrected_mae"]
    assert round(body["bias_corrected"]["p90"]) == JANUARY["corrected_p90"]
    assert round(body["bias_corrected"]["bias_used"]) == JANUARY["bias"]
    assert body["raw"]["n"] == body["bias_corrected"]["n"]


def test_coverage_and_direction_are_visible():
    body = client.get("/api/metrics?mode=deadline").json()

    assert body["points_requested"] == JANUARY["n"]
    assert body["points_matched"] == JANUARY["n"]
    assert body["forecast_below_actual"] == JANUARY["below_actual"]


def test_one_chosen_day_matches_a_figure_derived_a_different_way():
    """The exit check's cross-check, and a strong one.

    A single-day request is computed from a 48-row window. The same day also appears in
    `worst_days` of the whole-month summary, computed from the 1,488-row series by
    grouping. Two different code paths over two different inputs must agree.
    """
    day = client.get(f"/api/metrics?start={WORST_DAY}&end={WORST_DAY}").json()
    month = client.get("/api/metrics?mode=deadline").json()

    assert day["raw"]["n"] == 48
    assert round(day["raw"]["mae"]) == WORST_DAY_MAE

    worst = month["worst_days"][0]
    assert worst["day"] == WORST_DAY
    assert round(worst["mae"]) == round(day["raw"]["mae"])
    assert worst["n"] == day["raw"]["n"]


def test_a_narrowed_range_narrows_the_series_too():
    body = client.get(f"/api/series?start={WORST_DAY}&end={WORST_DAY}").json()

    assert body["points_requested"] == 48
    assert body["applied"]["start"] == WORST_DAY
    assert body["applied"]["end"] == WORST_DAY
    assert all(p["target_time"].startswith(WORST_DAY) for p in body["points"])


def test_half_the_deadline_series_is_held():
    """Decision 0004's hold must stay visible in the reply, not be smoothed away."""
    points = client.get("/api/series?mode=deadline").json()["points"]

    assert sum(1 for p in points if p["is_held"] is True) == HELD_ROWS
    assert sum(1 for p in points if p["is_held"] is False) == HELD_ROWS


@pytest.mark.parametrize("hours,expected_matched", [(0, 1488), (42, 1488), (48, 1209)])
def test_hours_ahead_coverage_matches_the_measured_horizon(hours, expected_matched):
    body = client.get(f"/api/series?mode=hours_ahead&hours={hours}").json()

    assert body["points_requested"] == 1488
    assert body["points_matched"] == expected_matched


def test_a_partially_matched_series_is_still_valid_json():
    """The test that would have caught the 500.

    Starlette renders with allow_nan=False, so one NaN in the payload fails the request.
    `response.json()` succeeding is the proof; the text assertions catch the other
    failure mode, where NaT is silently encoded as the string "NaT".
    """
    response = client.get("/api/series?mode=hours_ahead&hours=48")

    assert response.status_code == 200
    body = response.json()
    assert "NaN" not in response.text
    assert "NaT" not in response.text

    gaps = [p for p in body["points"] if p["forecast_mw"] is None]
    assert len(gaps) == 1488 - 1209
    assert all(p["publish_time"] is None and p["is_held"] is None for p in gaps)


def test_a_gap_keeps_the_real_wind_it_still_knows():
    """A missing forecast does not make the metered generation missing too."""
    points = client.get("/api/series?mode=hours_ahead&hours=48").json()["points"]
    gaps = [p for p in points if p["forecast_mw"] is None]

    assert all(isinstance(p["actual_mw"], int) for p in gaps)
    assert all(p["target_time"].endswith("Z") for p in gaps)


def test_is_held_is_only_ever_true_false_or_null():
    """Across both modes, including the one where pandas degrades the column to object."""
    for url in ["/api/series?mode=deadline", "/api/series?mode=hours_ahead&hours=48"]:
        for point in client.get(url).json()["points"]:
            assert point["is_held"] in (True, False, None)


def test_timestamps_match_the_health_endpoint_format():
    series = client.get("/api/series?mode=deadline").json()["points"][0]
    health = client.get("/api/health").json()

    assert series["target_time"].endswith("Z")
    assert series["publish_time"].endswith("Z")
    assert health["delivery_from"].endswith("Z")
    assert "+00:00" not in client.get("/api/series?mode=deadline").text


def test_the_two_endpoints_agree_on_what_matched():
    """One number, two addresses. If they diverge, a screen will contradict itself."""
    for query in ["mode=deadline", "mode=hours_ahead&hours=48", f"start={WORST_DAY}&end={WORST_DAY}"]:
        series = client.get(f"/api/series?{query}").json()
        metrics = client.get(f"/api/metrics?{query}").json()

        counted = sum(1 for p in series["points"] if p["forecast_mw"] is not None)
        assert counted == metrics["points_matched"] == series["points_matched"]


def test_hours_is_accepted_in_deadline_mode_and_reported_as_unused():
    """Screen 1 keeps its slider mounted while the mode switch says deadline.

    Rejecting this would force the frontend to special-case every request. Accepting it
    silently would let the client believe the slider was honoured, so the reply says.
    """
    body = client.get("/api/series?mode=deadline&hours=12").json()

    assert body["applied"]["hours"] is None
    assert body["applied"]["mode"] == "deadline"
    assert body["points_matched"] == JANUARY["n"]


def test_defaults_cover_the_whole_delivery_range_in_deadline_mode():
    body = client.get("/api/series").json()

    assert body["applied"] == {
        "mode": "deadline",
        "hours": None,
        "deadline_hour_utc": 11,
        "start": "2026-01-02",
        "end": "2026-02-01",
    }


@pytest.mark.parametrize("endpoint", ["/api/series", "/api/metrics"])
@pytest.mark.parametrize(
    "query,expected_message",
    [
        ("start=2025-12-01", "start must be between 2026-01-02 and 2026-02-01"),
        ("end=2026-03-01", "end must be between 2026-01-02 and 2026-02-01"),
        ("start=10-01-2026", "start must be a date in YYYY-MM-DD format"),
        ("start=2026-01-10&end=2026-01-05", "start must not be after end"),
        ("mode=xyz", "mode must be one of: deadline, hours_ahead"),
        ("mode=hours_ahead", "hours is required when mode is hours_ahead"),
        ("mode=hours_ahead&hours=-5", "hours must be between 0 and 48, got -5"),
        ("mode=hours_ahead&hours=49", "hours must be between 0 and 48, got 49"),
        ("mode=hours_ahead&hours=abc", "hours must be a whole number between 0 and 48"),
        ("mode=hours_ahead&hours=12.5", "hours must be a whole number between 0 and 48"),
    ],
)
def test_bad_settings_are_refused_with_400_and_a_sentence(endpoint, query, expected_message):
    """Not 422. A typed FastAPI parameter would answer `hours=abc` with 422 and a body
    describing the parameter structure, which is neither the status the exit check wants
    nor a message anyone can act on."""
    response = client.get(f"{endpoint}?{query}")

    assert response.status_code == 400
    assert response.json() == {"error": expected_message}


@pytest.mark.parametrize(
    "url",
    [
        "/api/series?mode=xyz",
        "/api/series?mode=hours_ahead&hours=abc",
        "/api/metrics?start=2025-12-01",
        "/api/does-not-exist",
    ],
)
@pytest.mark.parametrize("leak", ["Traceback", ".py", "/srv", "/Users", "line "])
def test_no_error_reply_leaks_a_path_or_a_code_location(url, leak):
    assert leak not in client.get(url).text


@pytest.mark.parametrize("path", ["/api/series", "/api/metrics"])
def test_the_new_routes_carry_the_api_prefix(path):
    """A Vercel service receives the ORIGINAL path, so /api is part of the route itself."""
    assert client.get(path).status_code == 200
    assert client.get(path.removeprefix("/api")).status_code == 404
