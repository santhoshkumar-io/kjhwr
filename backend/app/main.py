"""The web server.

Phase 3 deliberately exposes one endpoint only - a health check returning the saved
row counts - so that deployment is proven before any feature depends on it. The data
endpoints `/api/series` and `/api/metrics` arrive in Phase 4.

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

# Where the saved CSVs live. An environment variable with a sensible default keeps
# the path out of the pure analysis modules (AGENTS.md rule 6) while still letting
# the container and Vercel override it.
DATA_DIR = Path(os.environ["DATA_DIR"]) if os.environ.get("DATA_DIR") else Path(__file__).resolve().parent.parent / "data"

app = FastAPI(
    title="Wind Forecast Checker",
    description="Day-ahead wind forecast accuracy for January 2026, from Elexon data.",
    version="0.3.0",
)

# Loaded once at import, not per request. On a serverless cold start this is the
# 165 ms measured in Phase 3; every subsequent request on a warm instance pays
# nothing. The files are small and never change at runtime, so there is no reason
# to re-read them.
_actuals = load_actuals(DATA_DIR / "actuals.csv")
_forecasts = load_forecasts(DATA_DIR / "forecasts.csv")


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
