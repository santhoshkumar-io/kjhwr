"""Check what the client asked for, before any of it reaches the analysis code.

Every setting is validated here and nowhere else, which matters for two reasons.

**The status code.** The Phase 4 exit check requires `hours=abc` to come back as 400 with a
clear message. If `hours` were declared as a typed FastAPI query parameter, FastAPI would
reject it first and return **422** with a body describing the internal parameter structure.
So the routes take all four settings as raw strings and hand them straight to
`parse_settings`, which is the only thing that decides whether a request is valid.

**The message.** `BadRequest` carries text written to be shown to a person: no file path, no
code location, no traceback, and no echo of unvalidated input. Phase 8 audits this properly;
there is no reason to write it the wrong way first.

The allowed date range is **passed in, not hardcoded**. It comes from the saved actuals in
`main.py`, so the range the API accepts is by construction the range it actually holds data
for - the two cannot drift, and no date is typed by hand (AGENTS.md rule 2). The mode names
and the hours ceiling are imported from `forecast_selection` for the same reason.

Pure functions only: strings in, a frozen dataclass out. No web framework, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd

from app.forecast_selection import (
    DEADLINE_MODE,
    DEFAULT_DEADLINE_HOUR_UTC,
    HOURS_AHEAD_MODE,
    MAX_HOURS_AHEAD,
    MODES,
)

_DATE_FORMAT = "%Y-%m-%d"


class BadRequest(ValueError):
    """A client error whose message is safe to show as-is."""


@dataclass(frozen=True)
class Settings:
    """The validated settings, plus the half-open window to filter delivery times with."""

    start_date: date
    end_date: date
    mode: str
    hours: int | None
    deadline_hour_utc: int = DEFAULT_DEADLINE_HOUR_UTC

    @property
    def start(self) -> pd.Timestamp:
        """Midnight UTC at the start of the first delivery day."""
        return pd.Timestamp(self.start_date, tz="UTC")

    @property
    def end_exclusive(self) -> pd.Timestamp:
        """Midnight UTC after the last delivery day, so the whole day is included.

        A half-open window is used rather than comparing against 23:30, so the rule does
        not depend on the data's half-hourly resolution.
        """
        return pd.Timestamp(self.end_date + timedelta(days=1), tz="UTC")

    def applied(self) -> dict:
        """What the server actually used, for the client to echo back or display.

        `hours` reads `null` in deadline mode because that is the truth: the setting was
        accepted and then not used.
        """
        return {
            "mode": self.mode,
            "hours": self.hours,
            "deadline_hour_utc": self.deadline_hour_utc,
            "start": self.start_date.isoformat(),
            "end": self.end_date.isoformat(),
        }


def _parse_date(raw: str, field: str, earliest: date, latest: date) -> date:
    try:
        parsed = datetime.strptime(raw, _DATE_FORMAT).date()
    except (ValueError, TypeError):
        raise BadRequest(f"{field} must be a date in YYYY-MM-DD format") from None
    if not earliest <= parsed <= latest:
        raise BadRequest(
            f"{field} must be between {earliest.isoformat()} and {latest.isoformat()}"
        )
    return parsed


def _parse_hours(raw: str | None, mode: str) -> int | None:
    if mode == DEADLINE_MODE:
        # Accepted and discarded. Screen 1 keeps its slider mounted while the mode switch
        # says "deadline", so rejecting this would make the frontend special-case every
        # request. Normalising to None here is what lets `applied()` say so out loud
        # instead of leaving the client to assume the slider was honoured.
        return None
    if raw is None or raw == "":
        raise BadRequest(f"hours is required when mode is {HOURS_AHEAD_MODE}")
    try:
        hours = int(raw)
    except (ValueError, TypeError):
        raise BadRequest(
            f"hours must be a whole number between 0 and {MAX_HOURS_AHEAD}"
        ) from None
    if not 0 <= hours <= MAX_HOURS_AHEAD:
        raise BadRequest(f"hours must be between 0 and {MAX_HOURS_AHEAD}, got {hours}")
    return hours


def parse_settings(
    start: str | None,
    end: str | None,
    mode: str | None,
    hours: str | None,
    *,
    earliest: date,
    latest: date,
) -> Settings:
    """Validate the four query settings, or raise `BadRequest` with a showable message.

    `earliest` and `latest` are the first and last delivery days actually held, so the
    accepted range is the real one rather than a repeated constant.
    """
    mode = (mode or DEADLINE_MODE).strip()
    if mode not in MODES:
        raise BadRequest(f"mode must be one of: {', '.join(MODES)}")

    start_date = _parse_date(start, "start", earliest, latest) if start else earliest
    end_date = _parse_date(end, "end", earliest, latest) if end else latest
    if start_date > end_date:
        raise BadRequest("start must not be after end")

    return Settings(
        start_date=start_date,
        end_date=end_date,
        mode=mode,
        hours=_parse_hours(hours, mode),
    )
