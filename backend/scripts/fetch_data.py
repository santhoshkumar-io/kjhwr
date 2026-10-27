#!/usr/bin/env python3
"""Phase 1 - download January's Elexon data and save it as two CSV files.

Everything later in the project reads these files, so the live app never depends on
Elexon being reachable.

What this script deliberately does NOT do:

  * It does not apply the hourly-to-half-hourly hold from decision 0004.
  * It does not drop the hindcast rows (21% of the forecast feed, whose target time
    precedes their own publish time).
  * It does not fill, interpolate or guess anything.

All three belong in Phase 2, where they are unit-tested against hand-calculated
fixtures. Doing any of them here would bake a decision into the saved data and make
it impossible to test.

Phase 0 (backend/scripts/explore_sample.py) proved that /stream has no date-range cap,
so each feed is fetched in a single request - no chunking.

Usage:
    uv run python backend/scripts/fetch_data.py

Exits 0 on success, 1 if any check fails. Running it twice must produce
byte-identical files.
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

try:
    # Verify TLS against the OS trust store rather than OpenSSL's own bundle.
    # This network runs a TLS-inspecting proxy whose root CA lives in the macOS
    # keychain but not in /etc/ssl/cert.pem, which is what this interpreter reads.
    # Absent (e.g. in a container, with no such proxy), the default verification
    # is correct and nothing is needed.
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

BASE = "https://data.elexon.co.uk/bmrs/api/v1"

# Decision 0002: decisions made 1-31 Jan buy delivery for 2 Jan - 1 Feb.
ACTUALS_FROM = "2026-01-02"
ACTUALS_TO = "2026-02-01"

# Decision 0002: publish range starts 30 Dec so the 48h slider has runs to choose from.
FORECAST_FROM = "2025-12-30T00:00Z"
FORECAST_TO = "2026-02-02T00:00Z"

# Measured in Phase 0. Exact, not approximate - see docs/notes/phase-0.md.
EXPECTED_ACTUAL_ROWS = 1488  # 31 delivery days x 48 half-hours
EXPECTED_FORECAST_ROWS = 19856  # 272 runs x 73 hourly targets

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

_failures: list[str] = []


# --------------------------------------------------------------------------- helpers


def fetch_stream(dataset: str, **params) -> list[dict]:
    """GET /datasets/{dataset}/stream and return the parsed rows.

    The /stream form returns a BARE JSON ARRAY - there is no {"data": [...]} wrapper,
    unlike the paged form, and it has no 7-day range cap. Both facts are asserted in
    Phase 0's explore_sample.py. The shape is re-checked here so that an upstream
    change produces a clear error instead of a confusing pandas failure.
    """
    url = f"{BASE}/datasets/{dataset}/stream?" + urllib.parse.urlencode(params)
    print(f"  GET {url}")
    with urllib.request.urlopen(url, timeout=300) as response:
        body = json.load(response)
    if not isinstance(body, list):
        raise SystemExit(
            f"{dataset}/stream returned {type(body).__name__}, expected a bare list. "
            "If Elexon added a wrapper, fetch_stream() must change."
        )
    return body


def require(ok: bool, label: str, *, decision: str | None = None, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))
    if not ok:
        note = label
        if decision:
            note += f"  <-- invalidates decision {decision}"
        _failures.append(note)


def heading(text: str) -> None:
    print(f"\n{text}\n{'-' * len(text)}")


def check_times_are_utc(series: pd.Series, column: str) -> None:
    """Every timestamp must be ISO-8601 UTC with a trailing Z.

    The strings are stored exactly as Elexon sends them. Round-tripping through a
    local timezone is the classic way to introduce a silent one-hour error, and
    decision 0001 depends on these being UTC.
    """
    bad = series[~series.str.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")]
    require(
        bad.empty,
        f"every {column} is ISO-8601 UTC with trailing Z",
        decision="0001",
        detail=f"{len(bad)} malformed" if not bad.empty else "no timezone conversion needed",
    )


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    """Write deterministically, so two runs produce byte-identical files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n")
    print(f"  wrote {path.relative_to(DATA_DIR.parents[1])}  ({len(frame)} rows)")


# ---------------------------------------------------------------------------- stages


def build_actuals() -> pd.DataFrame:
    heading("1. Actuals - FUELHH, fuelType WIND")
    rows = fetch_stream(
        "FUELHH",
        settlementDateFrom=ACTUALS_FROM,
        settlementDateTo=ACTUALS_TO,
        fuelType="WIND",
    )
    print(f"  fetched {len(rows)} rows in one request")

    frame = pd.DataFrame(rows)
    # settlementDate and settlementPeriod are both derivable from target_time, so they
    # are not "needed fields" and are dropped.
    frame = frame[["startTime", "generation"]].rename(
        columns={"startTime": "target_time", "generation": "generation_mw"}
    )

    before = len(frame)
    frame = frame.drop_duplicates()
    removed = before - len(frame)
    frame = frame.sort_values("target_time", kind="stable").reset_index(drop=True)

    require(
        len(frame) == EXPECTED_ACTUAL_ROWS,
        f"exactly {EXPECTED_ACTUAL_ROWS} half-hourly rows",
        decision="0002",
        detail=f"got {len(frame)}",
    )
    require(
        not frame["target_time"].duplicated().any(),
        "no target time appears twice",
        detail=f"{int(frame['target_time'].duplicated().sum())} duplicates",
    )
    require(
        not frame.isna().to_numpy().any(),
        "no missing values",
        detail="nothing to fill, so nothing is filled",
    )
    check_times_are_utc(frame["target_time"], "target_time")
    report_missing_half_hours(frame["target_time"])
    print(f"  duplicate rows removed: {removed}")
    print(f"  range: {frame['target_time'].iloc[0]} .. {frame['target_time'].iloc[-1]}")
    return frame


def build_forecasts() -> pd.DataFrame:
    heading("2. Forecasts - WINDFOR (raw: hold and hindcast filter are Phase 2's job)")
    rows = fetch_stream(
        "WINDFOR",
        publishDateTimeFrom=FORECAST_FROM,
        publishDateTimeTo=FORECAST_TO,
    )
    print(f"  fetched {len(rows)} rows in one request")

    frame = pd.DataFrame(rows)
    frame = frame[["startTime", "publishTime", "generation"]].rename(
        columns={
            "startTime": "target_time",
            "publishTime": "publish_time",
            "generation": "generation_mw",
        }
    )

    before = len(frame)
    frame = frame.drop_duplicates()
    removed = before - len(frame)
    # Sorted the way Phase 2 reads it: all runs for one target, oldest publish first.
    frame = frame.sort_values(["target_time", "publish_time"], kind="stable").reset_index(drop=True)

    require(
        len(frame) == EXPECTED_FORECAST_ROWS,
        f"exactly {EXPECTED_FORECAST_ROWS} hourly rows",
        decision="0002",
        detail=f"got {len(frame)}",
    )
    require(
        not frame.duplicated(subset=["target_time", "publish_time"]).any(),
        "no (target time, publish time) pair appears twice",
        detail=f"{int(frame.duplicated(subset=['target_time', 'publish_time']).sum())} duplicates",
    )
    require(
        not frame.isna().to_numpy().any(),
        "no missing values",
    )
    check_times_are_utc(frame["target_time"], "target_time")
    check_times_are_utc(frame["publish_time"], "publish_time")

    hindcast = int((frame["target_time"] < frame["publish_time"]).sum())
    require(
        hindcast > 0,
        "hindcast rows are still present (not filtered here)",
        decision="0004",
        detail=f"{hindcast} of {len(frame)} = {100 * hindcast / len(frame):.0f}%, Phase 2 filters them",
    )
    on_the_hour = frame["target_time"].str.endswith(":00:00Z").all()
    require(
        bool(on_the_hour),
        "forecast target times are all on the hour (raw hourly, no hold applied)",
        decision="0004",
        detail="actuals are half-hourly; Phase 2 holds these across the hour",
    )
    print(f"  duplicate rows removed: {removed}")
    print(f"  distinct runs: {frame['publish_time'].nunique()}")
    print(f"  target range: {frame['target_time'].min()} .. {frame['target_time'].max()}")
    return frame


def report_missing_half_hours(target_times: pd.Series) -> None:
    """List every missing half-hour individually, as the product plan requires."""
    stamps = pd.to_datetime(target_times, format="%Y-%m-%dT%H:%M:%SZ", utc=True)
    expected = pd.date_range(stamps.min(), stamps.max(), freq="30min", tz="UTC")
    missing = expected.difference(pd.DatetimeIndex(stamps))
    require(
        len(missing) == 0,
        "no missing half-hours in the delivery range",
        detail=f"{len(missing)} missing" if len(missing) else "complete, and January has no DST break",
    )
    for stamp in missing:
        print(f"    MISSING {stamp.strftime('%Y-%m-%dT%H:%M:%SZ')}")


def check_integer_generation(frame: pd.DataFrame, name: str) -> None:
    """Generation must stay integral.

    Elexon returns whole MW. If a null ever appeared, pandas would silently widen the
    column to float and write 15228.0, which changes the file hash and breaks the
    idempotency check for a reason that is hard to spot.
    """
    require(
        pd.api.types.is_integer_dtype(frame["generation_mw"]),
        f"{name}: generation_mw is an integer column",
        detail=f"dtype {frame['generation_mw'].dtype}",
    )


def main() -> int:
    print("Phase 1 - save January's data")
    print(f"base: {BASE}  (no API key required)")

    actuals = build_actuals()
    forecasts = build_forecasts()

    heading("3. Integer check")
    check_integer_generation(actuals, "actuals")
    check_integer_generation(forecasts, "forecasts")

    if _failures:
        heading("Summary")
        print(f"  {len(_failures)} CHECK(S) FAILED - nothing written:")
        for failure in _failures:
            print(f"    - {failure}")
        return 1

    heading("4. Writing files")
    write_csv(actuals, DATA_DIR / "actuals.csv")
    write_csv(forecasts, DATA_DIR / "forecasts.csv")

    heading("Summary")
    print(f"  actuals:   {len(actuals)} rows, {actuals['target_time'].iloc[0]} .. {actuals['target_time'].iloc[-1]}")
    print(f"  forecasts: {len(forecasts)} rows, {forecasts['publish_time'].nunique()} runs")
    print("  missing half-hours: 0")
    print("  all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
