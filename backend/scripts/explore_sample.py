#!/usr/bin/env python3
"""Phase 0 - confirm the shape of the Elexon data at month scale.

This script is a CHECK, not a fetcher. It writes no files; Phase 1 saves the data.

Every assumption that a later decision record depends on is asserted here, so that if
Elexon changes its behaviour we find out by this script failing rather than by a chart
being quietly wrong. Each failure message names the decision record it invalidates.

Standard library only, on purpose: this runs before any dependency is installed.

Usage:
    python3 backend/scripts/explore_sample.py

Exits 0 if every check passes, 1 otherwise.
"""

# Keeps the type hints lazy so this runs on the system Python 3.9 as well as the
# 3.12 the container uses (decision 0003). This script is meant to work before
# Docker exists, so it must not need a newer interpreter than the machine has.
from __future__ import annotations

import collections
import datetime as dt
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://data.elexon.co.uk/bmrs/api/v1"

# Delivery range, from decision 0002: decisions made 1-31 Jan buy delivery 2 Jan - 1 Feb.
ACTUALS_FROM = "2026-01-02"
ACTUALS_TO = "2026-02-01"

# Publish range, from decision 0002: starts 30 Dec so the 48h slider has runs to choose from.
FORECAST_FROM = "2025-12-30T00:00Z"
FORECAST_TO = "2026-02-02T00:00Z"

TS = "%Y-%m-%dT%H:%M:%SZ"
EXPECTED_HALF_HOURS = 1488  # 31 delivery days x 48
DEADLINE_HOUR_UTC = 11  # decision 0001: 11:00 London = 11:00 UTC in January

_failures: list[str] = []


# --------------------------------------------------------------------------- helpers


def _ts(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, TS)


def fetch_stream(dataset: str, **params) -> list[dict]:
    """GET /datasets/{dataset}/stream.

    The /stream form returns a BARE JSON ARRAY - there is no {"data": [...]} wrapper,
    unlike the paged form. It also has no 7-day range cap, which is why Phase 1 needs
    no chunking. Both facts are asserted in check_range_cap().
    """
    url = f"{BASE}/datasets/{dataset}/stream?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=300) as r:
        body = json.load(r)
    if not isinstance(body, list):
        raise AssertionError(
            f"{dataset}/stream returned {type(body).__name__}, expected a bare list. "
            "If Elexon added a wrapper, every caller of this helper must change."
        )
    return body


def http_status(path: str, **params) -> tuple[int, str]:
    """Return (status, body) for a request we expect to be rejected."""
    url = f"{BASE}{path}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            return r.status, r.read(400).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(400).decode("utf-8", "replace")


def require(ok: bool, label: str, *, decision: str | None = None, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))
    if not ok:
        note = label
        if decision:
            note += f"  <-- invalidates decision {decision}"
        _failures.append(note)


def heading(text: str) -> None:
    print(f"\n{text}\n{'-' * len(text)}")


# ---------------------------------------------------------------------------- checks


def check_actuals() -> list[dict]:
    heading("1. Actuals - FUELHH, fuelType WIND, one request for the whole delivery range")
    rows = fetch_stream(
        "FUELHH",
        settlementDateFrom=ACTUALS_FROM,
        settlementDateTo=ACTUALS_TO,
        fuelType="WIND",
    )
    print(f"  fetched {len(rows)} rows in ONE request ({ACTUALS_FROM} .. {ACTUALS_TO})")
    print(f"  fields: {sorted(rows[0])}")
    print("  first 3 rows by target time:")
    for r in sorted(rows, key=lambda r: r["startTime"])[:3]:
        print(f"    {r['startTime']}  sp={r['settlementPeriod']:>2}  {r['generation']:>6} MW")

    starts = [r["startTime"] for r in rows]
    days = collections.Counter(r["settlementDate"] for r in rows)
    off_grid = [s for s in starts if _ts(s).minute not in (0, 30) or _ts(s).second]
    wrong_count = {d: n for d, n in sorted(days.items()) if n != 48}

    require(
        len(rows) == EXPECTED_HALF_HOURS,
        f"exactly {EXPECTED_HALF_HOURS} half-hourly rows",
        decision="0002",
        detail=f"got {len(rows)}",
    )
    require(
        len(set(starts)) == len(starts),
        "no duplicate target times",
        detail=f"{len(starts) - len(set(starts))} duplicates",
    )
    require(len(days) == 31, "31 distinct delivery days", decision="0002", detail=f"got {len(days)}")
    require(
        not wrong_count,
        "every delivery day has exactly 48 half-hours",
        detail=f"offenders: {wrong_count}" if wrong_count else "no gaps, no DST break",
    )
    require(
        not off_grid,
        "every target time is on a 30-minute boundary",
        decision="0004",
        detail=f"{len(off_grid)} off-grid" if off_grid else "actuals are half-hourly",
    )
    require(
        all(s.endswith("Z") for s in starts),
        "all times are UTC (trailing Z)",
        decision="0001",
    )
    require(
        all(r["fuelType"] == "WIND" for r in rows),
        "fuelType filter returned WIND only",
    )
    return rows


def check_forecasts() -> list[dict]:
    heading("2. Forecasts - WINDFOR, one request for the whole publish range")
    rows = fetch_stream(
        "WINDFOR",
        publishDateTimeFrom=FORECAST_FROM,
        publishDateTimeTo=FORECAST_TO,
    )
    print(f"  fetched {len(rows)} rows in ONE request ({FORECAST_FROM} .. {FORECAST_TO})")
    print(f"  fields: {sorted(rows[0])}")
    print("  first 3 rows of the earliest run:")
    for r in sorted(rows, key=lambda r: (r["publishTime"], r["startTime"]))[:3]:
        print(f"    pub {r['publishTime']}  target {r['startTime']}  {r['generation']:>6} MW")

    runs = sorted({r["publishTime"] for r in rows})
    per_day = collections.Counter(p[:10] for p in runs)
    by_run = collections.defaultdict(list)
    for r in rows:
        by_run[r["publishTime"]].append(r["startTime"])

    gaps = [(_ts(b) - _ts(a)).total_seconds() / 3600 for a, b in zip(runs, runs[1:])]
    leads = [(_ts(max(v)) - _ts(p)).total_seconds() / 3600 for p, v in by_run.items()]
    targets_per_run = {len(v) for v in by_run.values()}
    off_hour = [r["startTime"] for r in rows if _ts(r["startTime"]).minute or _ts(r["startTime"]).second]
    hindcast = [r for r in rows if r["startTime"] < r["publishTime"]]
    pairs = [(r["startTime"], r["publishTime"]) for r in rows]

    print(f"  runs: {len(runs)} over {len(per_day)} publish days")
    print(f"  publish gap: {min(gaps):.1f}h .. {max(gaps):.1f}h")
    print(f"  max lead per run: {min(leads):.1f}h .. {max(leads):.1f}h")

    require(
        not off_hour,
        "every forecast target time is on a whole hour",
        decision="0004",
        detail=f"{len(off_hour)} off-hour" if off_hour else "forecasts are HOURLY, actuals are half-hourly",
    )
    require(
        set(per_day.values()) == {8},
        "exactly 8 runs published every day",
        detail=f"per-day counts seen: {sorted(set(per_day.values()))}",
    )
    require(
        targets_per_run == {73},
        "every run carries exactly 73 hourly targets",
        detail=f"sizes seen: {sorted(targets_per_run)}",
    )
    require(
        2.0 <= min(gaps) and max(gaps) <= 4.0,
        "gaps between runs stay within 2-4 hours",
        detail=f"{min(gaps):.1f}h .. {max(gaps):.1f}h - cadence is irregular, so a cutoff can sit mid-gap",
    )
    require(
        46.0 <= min(leads) and max(leads) <= 67.0,
        "max lead per run is ~46.5-66.5h (horizon ends at a fixed wall-clock point)",
        decision="0006",
        detail=f"{min(leads):.1f}h .. {max(leads):.1f}h - this is why coverage falls off near X=48",
    )
    require(
        bool(hindcast),
        "runs really do contain hindcast rows (target before publish)",
        detail=f"{len(hindcast)} of {len(rows)} = {100 * len(hindcast) / len(rows):.0f}%, so the filter is load-bearing",
    )
    require(
        len(set(pairs)) == len(pairs),
        "no duplicate (target, publish) pair",
        detail=f"{len(pairs) - len(set(pairs))} duplicates",
    )
    return rows


def check_range_cap() -> None:
    heading("3. Date-range cap - the assumption that lets Phase 1 skip chunking")
    paged_status, paged_body = http_status(
        "/datasets/FUELHH",
        settlementDateFrom=ACTUALS_FROM,
        settlementDateTo=ACTUALS_TO,
        fuelType="WIND",
        format="json",
    )
    stream_status, _ = http_status(
        "/datasets/FUELHH/stream",
        settlementDateFrom=ACTUALS_FROM,
        settlementDateTo=ACTUALS_TO,
        fuelType="WIND",
    )
    print(f"  paged form, 31-day range  -> HTTP {paged_status}")
    print(f"  stream form, 31-day range -> HTTP {stream_status}")
    if paged_status == 400:
        print(f"  paged rejection says: {paged_body[:200]}")

    require(
        paged_status == 400,
        "the paged form rejects a range over 7 days",
        detail=f"HTTP {paged_status}; '7 days' in body: {'7 days' in paged_body}",
    )
    require(
        stream_status == 200,
        "the /stream form accepts the full range (no cap)",
        detail="so Phase 1 needs no chunking; task.md links to /stream anyway",
    )


def report_lead_time_ceiling(actuals: list[dict], forecasts: list[dict]) -> None:
    """Coverage and error against lead time.

    The selection logic here is deliberately throwaway. Phase 2 reimplements it properly,
    with tests, in backend/app/forecast_selection.py. Agreement between the two is a
    meaningful independent cross-check precisely because they were written separately.
    """
    heading("4. Slider coverage and the lead-time ceiling (reference figures for Phase 2)")

    act = {_ts(r["startTime"]): r["generation"] for r in actuals}
    by_target = collections.defaultdict(list)
    for r in forecasts:
        if r["startTime"] >= r["publishTime"]:  # drop hindcast rows
            by_target[_ts(r["startTime"])].append((_ts(r["publishTime"]), r["generation"]))
    for v in by_target.values():
        v.sort()

    def newest_allowed(hour: dt.datetime, cutoff: dt.datetime):
        best = None
        for pub, gen in by_target.get(hour, ()):
            if pub <= cutoff:
                best = gen
            else:
                break
        return best

    targets = sorted(act)

    # Deadline mode (decision 0001). The hourly value is held across the hour (decision 0004):
    # both the :00 and :30 half-hours take the forecast published for that hour.
    errors = []
    for t in targets:
        cutoff = dt.datetime.combine(t.date() - dt.timedelta(days=1), dt.time(DEADLINE_HOUR_UTC))
        gen = newest_allowed(t.replace(minute=0), cutoff)
        if gen is not None:
            errors.append(gen - act[t])

    n = len(errors)
    absolute = sorted(abs(e) for e in errors)
    mae = sum(absolute) / n
    bias = sum(errors) / n
    rmse = (sum(e * e for e in errors) / n) ** 0.5
    p90 = absolute[int(0.9 * (n - 1))]
    corrected = sorted(abs(e - bias) for e in errors)
    below = sum(1 for e in errors if e < 0)

    print(f"  DEADLINE MODE (cutoff {DEADLINE_HOUR_UTC:02d}:00Z the day before):")
    print(f"    matched {n} of {EXPECTED_HALF_HOURS} half-hours ({100 * n / EXPECTED_HALF_HOURS:.0f}%)")
    print(f"    MAE  {mae:7.0f} MW      RMSE {rmse:7.0f} MW")
    print(f"    bias {bias:+7.0f} MW      P90  {p90:7.0f} MW")
    print(f"    bias-corrected: MAE {sum(corrected) / n:.0f} MW   P90 {corrected[int(0.9 * (n - 1))]:.0f} MW")
    print(f"    forecast was BELOW actual in {below} of {n} half-hours ({100 * below / n:.0f}%)")

    print("\n    X(h)   matched/1488      MAE MW   bias MW")
    for x in (0, 6, 12, 24, 36, 42, 44, 46, 47, 48):
        errs = []
        for t in targets:
            gen = newest_allowed(t.replace(minute=0), t - dt.timedelta(hours=x))
            if gen is not None:
                errs.append(gen - act[t])
        if errs:
            m = sum(abs(e) for e in errs) / len(errs)
            b = sum(errs) / len(errs)
            pct = 100 * len(errs) / EXPECTED_HALF_HOURS
            print(f"    {x:>3}    {len(errs):>5} ({pct:>3.0f}%)     {m:>7.0f}   {b:>+7.0f}")
        else:
            print(f"    {x:>3}        0 (  0%)           -         -")

    require(
        n == EXPECTED_HALF_HOURS,
        "deadline mode covers every half-hour (no gaps at the real buying deadline)",
        decision="0001",
        detail=f"{n}/{EXPECTED_HALF_HOURS}",
    )
    require(
        below > 0,
        "the forecast is not always high - bias is systematic, not absolute",
        decision="0006",
        detail=f"below actual in {100 * below / n:.0f}% of half-hours",
    )


def main() -> int:
    print(__doc__.strip().splitlines()[0])
    print(f"base: {BASE}  (no API key required)")

    actuals = check_actuals()
    forecasts = check_forecasts()
    check_range_cap()
    report_lead_time_ceiling(actuals, forecasts)

    heading("Summary")
    if _failures:
        print(f"  {len(_failures)} CHECK(S) FAILED:")
        for f in _failures:
            print(f"    - {f}")
        print("\n  A failure here means a decision record is now wrong. Fix the record,")
        print("  then the code that relied on it - in that order.")
        return 1
    print("  all checks passed; the decision records in docs/decisions/ still hold")
    return 0


if __name__ == "__main__":
    sys.exit(main())
