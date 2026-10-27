"""Turn a series frame into JSON that a browser can actually parse.

This module exists because of a trap that only appears on the settings where the
forecast horizon runs out. At `hours=48`, 279 of the 1,488 delivery half-hours have no
permitted forecast, so `build_series` leaves `NaN` in the numbers and `NaT` in
`publish_time`. Handing those to FastAPI goes wrong in two different ways:

- **`NaN` becomes a 500.** Starlette renders responses with `json.dumps(allow_nan=False)`,
  so a `NaN` anywhere in the payload raises `ValueError` and the request fails. Nothing
  about the failure points at the real cause.
- **`NaT` becomes the string `"NaT"`.** FastAPI's encoder treats it as a datetime, because
  `NaTType` really is a `datetime` subclass, and calls `isoformat()` on it. The client then
  receives `"publish_time": "NaT"`, which looks like data, survives transport, and only
  fails later as an `Invalid Date`. That is worse than a 500.

Neither shows up in deadline mode, where every row matches. A smoke test on the default
settings would pass and the bug would surface in Phase 5 as an empty chart.

So the conversion is explicit here rather than left to the framework, and unit-tested
without going through HTTP.

Two rules it enforces, both from AGENTS.md:

- **Missing stays missing (rule 3).** A gap serialises as `null` - never `0`, never an
  omitted key, never an omitted row. The row keeps its `target_time` and `actual_mw` so
  Screen 1 can draw a gap and still count "N of 1,488 points matched".
- **Timestamps keep the format the API already uses.** `/api/health` emits
  `2026-01-02T00:00:00Z` via `strftime`, and `test_health.py` asserts it. The encoder's
  default `isoformat()` would emit `+00:00` instead, forking the wire format inside one
  API, so the format is applied here deliberately.

Pure functions only: a DataFrame in, plain dicts out. No web framework, no file paths.
"""

from __future__ import annotations

import pandas as pd

# The format /api/health already uses, pinned by test_health.py. Not isoformat().
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# Fields converted by name, because the right JSON type depends on meaning rather than
# on the dtype pandas happens to have chosen for this particular series.
_TIME_FIELDS = ("target_time", "publish_time")
_BOOL_FIELDS = ("is_held",)
_FLOAT_FIELDS = ("lead_time_hours",)


def json_value(field: str, value: object) -> object:
    """One cell, converted to something `json.dumps` accepts.

    `pd.isna` is the single missing-value test: it covers `None`, `NaN` and `NaT`, which
    arrive from different columns of the same frame.
    """
    if value is None or pd.isna(value):
        return None
    if field in _TIME_FIELDS:
        return value.strftime(TIMESTAMP_FORMAT)
    if field in _BOOL_FIELDS:
        # Without this, an unmatched row would send a float. is_held is a flag, and
        # decision 0004 requires it to stay visible and unambiguous.
        return bool(value)
    if field in _FLOAT_FIELDS:
        return float(value)
    # MW values are whole numbers in the Elexon feed, but pandas widens the column to
    # float64 as soon as one row is unmatched. Normalising integral values back to int
    # keeps the wire type the same whether or not the series has gaps.
    number = float(value)
    return int(number) if number.is_integer() else number


def series_to_records(frame: pd.DataFrame) -> list[dict]:
    """One JSON-safe dict per row, in the frame's own column and row order.

    Every row of the input appears in the output. A row with no permitted forecast keeps
    its real `target_time` and `actual_mw` and nulls the rest.
    """
    return [
        {field: json_value(field, value) for field, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]
