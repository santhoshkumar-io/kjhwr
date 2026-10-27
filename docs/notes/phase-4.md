# Phase 4 — Server sends real data: evidence

Date: 2026-10-28. Branch: `build`.

Two addresses, `/api/series` and `/api/metrics`, both reading the saved January data through the
Phase 2 functions. No screen, no chart, no frontend change.

```bash
docker compose up --build
curl 'localhost:8000/api/metrics?start=2026-01-28&end=2026-01-28'
```

## What this phase actually is

It computes nothing. `build_series` and `summarise` already existed and were already tested against
the real data in Phase 2. Phase 4 is **a validation and serialisation layer** — which turned out to
be where the real hazards live.

| File | Role |
|---|---|
| `backend/app/request_settings.py` | validate the query string → `Settings`, or `BadRequest` |
| `backend/app/serialisation.py` | make a series frame safe for `json.dumps` |
| `backend/app/main.py` | HTTP only: read settings, call the engine, set status codes |

`forecast_selection.py`, `metrics.py` and `data_loading.py` were **not touched**. AGENTS.md rule 6
keeps them free of web-framework and path awareness, and the two new modules are pure as well, so
the serialisation rules are unit-tested without going through HTTP at all.

## Three traps, found by measurement rather than by luck

All three only appear on a **partially matched** series. At `hours=48` the forecast horizon runs out
and 279 of the 1,488 delivery half-hours have no permitted run. Deadline mode matches every row, so
a smoke test on the default settings passes and none of this surfaces until Phase 5 draws an empty
chart.

### 1. A `NaN` in the payload is a 500, not a bad number

Starlette renders responses with `json.dumps(allow_nan=False)`:

```
ValueError: Out of range float values are not JSON compliant: nan
```

So returning the frame as-is fails the request outright, with nothing in the error pointing at the
cause.

### 2. A `NaT` is silently encoded as the string `"NaT"`

Worse than the 500, because it succeeds. `NaTType` really is a `datetime` subclass, so FastAPI's
encoder calls `isoformat()` on it:

```python
jsonable_encoder({'v': pd.NaT})   # -> {'v': 'NaT'}
```

The client receives `"publish_time": "NaT"`, which looks like data, survives transport, and only
fails later as an `Invalid Date`.

### 3. The encoder would have forked the timestamp format

`/api/health` has emitted `2026-01-02T00:00:00Z` since Phase 3, via `strftime`, and
`test_health.py` asserts it. FastAPI's encoder emits `+00:00` instead. Letting it handle timestamps
would have produced two different formats inside one API.

Two smaller ones, both from pandas rather than from FastAPI:

- **`is_held` degrades to an `object` column** holding a float `nan` as soon as one row is unmatched,
  so without an explicit rule the hold flag arrives as a number. Decision 0004 requires it to stay
  visible and unambiguous.
- **`forecast_mw` and `error_mw` are `int64` at full coverage and `float64` when partial**, so the
  wire type would have changed with the settings. Integral values are normalised back to `int`.

`serialisation.py` handles all five explicitly, and `test_serialisation.py` pins each rule to the
reason it exists. `summarise` needed none of this — it already returns native Python scalars and no
NaN, which was verified rather than assumed.

## The 400-vs-422 decision

The exit check requires `hours=abc` to answer **400**. A typed FastAPI parameter (`hours: int`)
answers **422** with a body describing the internal parameter structure — neither the right status
nor a message anyone can act on.

So all four settings are declared as `str | None` and handed straight to `parse_settings`, which is
the only thing that judges a request. That is why the routes look untyped: it is deliberate, and
`test_bad_settings_are_refused_with_400_and_a_sentence` would fail if someone "fixed" it.

The accepted date range is **not** retyped from decision 0002. It is derived from the loaded
actuals:

```python
DELIVERY_EARLIEST = _actuals["target_time"].min().date()
DELIVERY_LATEST = _actuals["target_time"].max().date()
```

So the range the API accepts is by construction the range it holds data for, and no date is typed by
hand (rule 2). The mode names and the 48-hour ceiling are imported from `forecast_selection` for the
same reason.

## `hours` in deadline mode: accepted, ignored, and said out loud

`build_series` ignores `hours` when the mode is `deadline`. Phase 5's Screen 1 has both a mode
switch and a 0–48 slider, so it will send `hours` while in deadline mode; refusing that would force
the frontend to special-case every request.

So the request is accepted and the reply states what was actually used. The `applied` block is on
both endpoints:

```json
"applied": {"mode":"deadline","hours":null,"deadline_hour_utc":11,
            "start":"2026-01-02","end":"2026-02-01"}
```

`hours: null` is the truth — accepted, then not used. The client can never silently believe the
slider was honoured.

## Real requests and replies

### `GET /api/series?mode=deadline`

```json
{
  "applied": {"mode":"deadline","hours":null,"deadline_hour_utc":11,
              "start":"2026-01-02","end":"2026-02-01"},
  "points_requested": 1488,
  "points_matched": 1488,
  "points": [
    {"target_time":"2026-01-02T00:00:00Z","actual_mw":15228,"forecast_mw":18699,
     "error_mw":3471,"publish_time":"2026-01-01T09:30:00Z","is_held":false,
     "lead_time_hours":14.5},
    {"target_time":"2026-01-02T00:30:00Z","actual_mw":15505,"forecast_mw":18699,
     "error_mw":3194,"publish_time":"2026-01-01T09:30:00Z","is_held":true,
     "lead_time_hours":15.0}
  ]
}
```

Those first two rows are decision 0004 visible in the data: same `forecast_mw`, same
`publish_time`, `is_held` false then true. The hold is traceable, not hidden.

### `GET /api/series?mode=hours_ahead&hours=48`

```
points_requested 1488 | points_matched 1209 | null rows 279
```

```json
{"target_time":"2026-01-02T00:00:00Z","actual_mw":15228,"forecast_mw":null,
 "error_mw":null,"publish_time":null,"is_held":null,"lead_time_hours":null}
```

The row is **present**, not omitted, and keeps the metered generation it still knows. A missing
forecast does not make the actual wind missing (rule 3), and Phase 5 cannot count "N of 1,488
matched" from rows that were dropped.

### `GET /api/metrics?start=2026-01-28&end=2026-01-28`

```
applied: {'mode': 'deadline', 'hours': None, 'deadline_hour_utc': 11,
          'start': '2026-01-28', 'end': '2026-01-28'}
raw:     {'n': 48, 'mae': 5374.8, 'rmse': 5402.5, 'bias': 5374.8, 'p90': 6018.0}
matched: 48 of 48
```

### Every refusal, as the server really answers

```
400 ?start=2025-12-01                   {"error":"start must be between 2026-01-02 and 2026-02-01"}
400 ?end=2026-03-01                     {"error":"end must be between 2026-01-02 and 2026-02-01"}
400 ?start=10-01-2026                   {"error":"start must be a date in YYYY-MM-DD format"}
400 ?start=2026-01-10&end=2026-01-05    {"error":"start must not be after end"}
400 ?mode=xyz                           {"error":"mode must be one of: deadline, hours_ahead"}
400 ?mode=hours_ahead                   {"error":"hours is required when mode is hours_ahead"}
400 ?mode=hours_ahead&hours=-5          {"error":"hours must be between 0 and 48, got -5"}
400 ?mode=hours_ahead&hours=49          {"error":"hours must be between 0 and 48, got 49"}
400 ?mode=hours_ahead&hours=abc         {"error":"hours must be a whole number between 0 and 48"}
```

No reply contains a file path, a line number, a traceback or a module name — asserted across every
error body by `test_no_error_reply_leaks_a_path_or_a_code_location`.

## The exit check's cross-check, done the strong way

> *"For one chosen day, the numbers from `/api/metrics` match a Phase 2 test calculation."*

A single-day request computes from a 48-row window. The same day also appears in `worst_days` of the
whole-month summary, computed from the 1,488-row series by grouping. **Two code paths, two different
inputs, same answer:**

| Source | n | MAE |
|---|---|---|
| `/api/metrics?start=2026-01-28&end=2026-01-28` → `raw` | 48 | 5375 |
| `/api/metrics?mode=deadline` → `worst_days[0]` | 48 | 5375 |

This is a better check than comparing against a recorded constant, because an error in the range
filter would move one and not the other.

## Numbers the tests pin

| Request | Figures |
|---|---|
| `/api/metrics?mode=deadline` | n 1488, MAE 2016, RMSE 2510, bias +1730, P90 4189 |
| — bias-corrected | MAE 1407, P90 3132, `bias_used` +1730 |
| — coverage and direction | 1488 of 1488 matched; forecast below actual 234 |
| `/api/series?mode=deadline` | 744 rows `is_held: true`, 744 `false` — exactly half |
| `/api/series?mode=hours_ahead&hours=48` | 1488 requested, 1209 matched, 279 null |
| `/api/series?mode=hours_ahead&hours=0` and `42` | 1488 matched |

All agree with `docs/notes/phase-2.md`, which remains the single source the later phases quote.

## Payload size and cost

Measured over the wire from the container:

```
series  ?mode=deadline                251067 bytes
series  ?mode=hours_ahead&hours=48    245869 bytes
metrics ?mode=deadline                  4450 bytes
```

`build_series` + `summarise` is **11 ms**, and a 25-point sweep of the hours-ahead setting costs
**267 ms in total**. So Phase 6's "average miss vs hours-ahead" chart can be built by calling
`/api/metrics` repeatedly, and **no sweep endpoint is needed** — which is why none was added.

## Tests

```
155 passed in 1.44s

backend/tests/test_api.py                  62 passed
backend/tests/test_forecast_selection.py   19 passed
backend/tests/test_health.py                5 passed
backend/tests/test_january_golden.py       25 passed
backend/tests/test_metrics.py              24 passed
backend/tests/test_serialisation.py        20 passed
```

73 before this phase, 82 added. The Phase 2 engine and its tests are untouched.

The two tests most worth knowing about:

- `test_a_partially_matched_series_is_still_valid_json` — the one that would have caught the 500.
- `test_the_two_endpoints_agree_on_what_matched` — the count of non-null forecasts in `/api/series`
  equals `points_matched` in `/api/metrics`, for three different settings. If they ever diverge, a
  screen would contradict itself.

## Verified in Docker and through the Vite proxy

```
backend direct   /api/metrics?start=2026-01-28&end=2026-01-28   raw mae 5374.8  n 48
via Vite proxy   /api/metrics?start=2026-01-28&end=2026-01-28   raw mae 5374.8  n 48
```

Identical through both, so the `/api` path parity that Phase 3 established still holds with the new
routes. `test_the_new_routes_carry_the_api_prefix` asserts `/series` and `/metrics` are 404 without
the prefix.

## Scope held

No screen and no frontend change — Phase 4's build prompt says *"Do not build any screen."* The page
still shows only the Phase 3 health number. CORS from an environment variable remains Phase 8.

Not deployed: Phase 3 proved the deployment pipeline and closed its live checks, so `vercel --prod`
waits until there is a screen to look at.

## Carried into Phase 5

- `/api/series` is ready for Screen 1: `points_requested` and `points_matched` are what the
  "N of 1,488 points matched" readout should quote, and a gap is a row with `forecast_mw: null`
  rather than a missing row.
- The chart must **not connect across nulls**. The data now makes gaps representable; Recharts will
  join them anyway unless told not to.
- `applied.hours` is `null` in deadline mode. Screen 1 can keep the slider mounted and read this
  back rather than tracking what it sent.
- Phase 5's exit check asks for "a day with a known missing half-hour (from Phase 1 notes)" to show
  a gap. **There is no such day** — Phase 1 recorded zero missing half-hours in the delivery range.
  The only real gaps come from the horizon fall-off above X≈42, so that check has to be met with
  `hours=48`, not with a date.
