"""The web server.

Three endpoints: a health check (Phase 3) and the two data endpoints (Phase 4). This
file owns HTTP concerns only - reading settings off the query string, turning refusals
into status codes, and serialising the reply. Every number it returns is computed by the
pure modules from Phase 2, which it calls but does not duplicate (AGENTS.md rule 6).

The division of labour, so nothing analytical leaks in here:

    request_settings.parse_settings   validate the query string -> Settings or BadRequest
    forecast_selection.build_series   pick the forecast, pair it with the actual
    metrics.summarise                 the accuracy numbers
    serialisation.series_to_records   make the frame safe for json.dumps

Two things about this file are dictated by how Vercel Services route requests, and
both are easy to get wrong:

1. **The app must be named `app`** at a recognised entrypoint. Vercel looks for a
   `FastAPI` instance called `app` in `main.py` (among others), and `vercel.json`
   points at `app.main:app` relative to the `backend/` service root.

2. **Routes carry the `/api` prefix.** A service receives the *original* request
   path, so `GET /api/health` arrives here as `/api/health`, not `/health`. The local
   Vite dev proxy forwards `/api` without rewriting it for the same reason, so the
   page calls exactly the same URL in both environments.

Routing into a service is also final: if nothing here matches, Vercel does not fall
back to the other top-level rewrites, so this app owns its own 404 response.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.data_loading import load_actuals, load_forecasts
from app.forecast_selection import build_series
from app.metrics import summarise
from app.request_settings import BadRequest, Settings, parse_settings
from app.serialisation import series_to_records

# Where the saved CSVs live. An environment variable with a sensible default keeps
# the path out of the pure analysis modules (AGENTS.md rule 6) while still letting
# the container and Vercel override it.
DATA_DIR = Path(os.environ["DATA_DIR"]) if os.environ.get("DATA_DIR") else Path(__file__).resolve().parent.parent / "data"

app = FastAPI(
    title="Wind Forecast Checker",
    description="Day-ahead wind forecast accuracy for January 2026, from Elexon data.",
    version="0.4.0",
)

# Loaded once at import, not per request. On a serverless cold start this is the
# 165 ms measured in Phase 3; every subsequent request on a warm instance pays
# nothing. The files are small and never change at runtime, so there is no reason
# to re-read them.
_actuals = load_actuals(DATA_DIR / "actuals.csv")
_forecasts = load_forecasts(DATA_DIR / "forecasts.csv")

# The delivery days the API will accept, taken from the data rather than retyped from
# decision 0002. The accepted range is therefore the range we actually hold, and a date
# that would return an empty series is refused instead of answered with nothing.
DELIVERY_EARLIEST = _actuals["target_time"].min().date()
DELIVERY_LATEST = _actuals["target_time"].max().date()


def _settings(start: str | None, end: str | None, mode: str | None, hours: str | None) -> Settings:
    """Validate the query string against the delivery range actually held."""
    return parse_settings(
        start, end, mode, hours, earliest=DELIVERY_EARLIEST, latest=DELIVERY_LATEST
    )


def _series_for(settings: Settings):
    """The paired forecast-and-actual series for these settings.

    The actuals are narrowed to the requested days *before* `build_series` runs. That is
    not a shortcut: each cutoff is derived from its own target time, so removing target
    times outside the window cannot change which run is chosen for the ones left. It also
    means the bias used for the correction belongs to the selected range, which decision
    0006 requires, and that `points_requested` counts the days asked for.
    """
    window = _actuals[
        (_actuals["target_time"] >= settings.start)
        & (_actuals["target_time"] < settings.end_exclusive)
    ]
    return build_series(
        window,
        _forecasts,
        settings.mode,
        hours=settings.hours,
        deadline_hour_utc=settings.deadline_hour_utc,
    )


@app.get("/api/health")
def health() -> dict:
    """Row counts from the saved data.

    Phase 3's exit check is that the live page shows the same number as the local
    one, which is why this returns a real figure from the data rather than a
    hardcoded "ok" - a health check that cannot be wrong proves nothing.
    """
    return {
        "status": "ok",
        "actual_rows": int(len(_actuals)),
        "forecast_rows": int(len(_forecasts)),
        "delivery_from": _actuals["target_time"].min().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "delivery_to": _actuals["target_time"].max().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@app.get("/api/series")
def series(
    start: str | None = None,
    end: str | None = None,
    mode: str | None = None,
    hours: str | None = None,
) -> dict:
    """The chart rows: one per delivery half-hour in the requested range.

    Every setting is taken as a raw string so that `parse_settings` is the only thing
    that judges it. Declaring `hours: int` here would hand `hours=abc` to FastAPI's own
    validator, which answers 422 with a body describing the parameter structure - the
    exit check wants 400 and a sentence.

    A half-hour with no permitted forecast is still returned, with nulls: the gap is the
    finding, and Screen 1 needs the row in order to count what matched (AGENTS.md rule 3).
    """
    settings = _settings(start, end, mode, hours)
    frame = _series_for(settings)
    return {
        "applied": settings.applied(),
        "points_requested": int(len(frame)),
        "points_matched": int(frame["forecast_mw"].notna().sum()),
        "points": series_to_records(frame),
    }


@app.get("/api/metrics")
def metrics(
    start: str | None = None,
    end: str | None = None,
    mode: str | None = None,
    hours: str | None = None,
) -> dict:
    """The accuracy numbers for the same settings `/api/series` takes.

    This is `metrics.summarise` unaltered, so the figures here and the figures in the
    Phase 2 tests come from one function. It carries the raw and bias-corrected measure
    sets, each with its own `n`, and `bias_corrected.bias_used` is the mean bias actually
    subtracted - computed over the selected range and mode, as decision 0006 requires.
    """
    settings = _settings(start, end, mode, hours)
    return {"applied": settings.applied(), **summarise(_series_for(settings))}


@app.exception_handler(BadRequest)
async def bad_request(request: Request, exc: BadRequest) -> JSONResponse:
    """A rejected setting, as 400 and a sentence a person can act on.

    The message comes from `BadRequest` and names no file, no line and no internal
    structure. Phase 8 audits that properly.
    """
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.exception_handler(404)
async def not_found(request: Request, exc) -> JSONResponse:
    """This app owns its own 404, because routing into a service is final.

    The message names no file path and no code location - a rule Phase 8 checks,
    but there is no reason to write it the wrong way first.
    """
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "path": request.url.path},
    )
