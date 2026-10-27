# Phase 1 — Save January's data: evidence

Date: 2026-10-27. Branch: `build`. Script: `backend/scripts/fetch_data.py`.

```bash
uv venv --python 3.12 .venv
uv pip install -r backend/requirements.txt
.venv/bin/python backend/scripts/fetch_data.py
```

## Environment

| Component | Version |
|---|---|
| Python | 3.12.15 (uv-managed; `uv venv --python 3.12`) |
| pandas | 3.1.0 |
| pytest | 9.1.1 |
| truststore | 0.10.5 |

Two interpreters exist on this machine: uv-managed **CPython 3.12.15** and the macOS system
**3.9.6** at `/usr/bin/python3`. Decision `0003` targets 3.12, so the project venv uses it. Nothing
is installed into the system interpreter.

## A problem worth recording: TLS behind an inspecting proxy

The first run failed on every HTTPS call:

```text
ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED]
certificate verify failed: self-signed certificate in certificate chain
```

The cause is a TLS-inspecting corporate proxy:

```text
subject=/CN=*.elexon.co.uk
issuer=/C=GB/ST=GB/L=London/O=TBWA UK LTD/.../CN=ca.oss.de.goskope.com/emailAddress=certadmin@netskope.com
```

Netskope re-signs every certificate. Its root CA is installed in the **macOS keychain**, which is
why `curl` and the system Python 3.9 work. But the uv-managed 3.12 verifies against OpenSSL's own
bundle at `/etc/ssl/cert.pem`, which does not contain it — so setting
`SSL_CERT_FILE=/etc/ssl/cert.pem` does not help either (tested; still fails).

**Fix:** `truststore`, which makes Python verify against the OS trust store. Both scripts import it
inside `try/except ImportError`, so they still run where it is absent — on the bare system 3.9, and
in a container, which has no such proxy in front of it. Verified on both interpreters: exit 0.

This is a local network condition, not a property of the data or of Elexon. It is recorded here
because the next person to run this on a corporate laptop will hit it, and the error message does
not suggest the cause.

## What was saved

| File | Rows | Columns |
|---|---|---|
| `backend/data/actuals.csv` | 1,488 | `target_time`, `generation_mw` |
| `backend/data/forecasts.csv` | 19,856 | `target_time`, `publish_time`, `generation_mw` |

`startTime` was renamed to `target_time` because "start time" reads as the start of a forecast run
rather than the delivery half-hour it actually means, and one consistent name across both files
makes the Phase 2 join obvious. `settlementDate` and `settlementPeriod` were dropped: both are
derivable from `target_time`, so they are not needed fields.

### What was deliberately NOT done

The files hold the **raw** feeds:

- the hourly-to-half-hourly hold (`0004`) is **not** applied — forecast target times are all on the
  hour, asserted by the script;
- the 4,081 hindcast rows (21%) are **not** removed — their presence is asserted, so a future change
  that silently filtered them would fail here;
- nothing is filled, interpolated or guessed.

All three belong in Phase 2, where they are unit-tested against hand-calculated fixtures. Doing any
of them here would bake a decision into the data and make it untestable.

## Full output

```text
Phase 1 - save January's data
base: https://data.elexon.co.uk/bmrs/api/v1  (no API key required)

1. Actuals - FUELHH, fuelType WIND
----------------------------------
  GET https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream?settlementDateFrom=2026-01-02&settlementDateTo=2026-02-01&fuelType=WIND
  fetched 1488 rows in one request
  [PASS] exactly 1488 half-hourly rows  (got 1488)
  [PASS] no target time appears twice  (0 duplicates)
  [PASS] no missing values  (nothing to fill, so nothing is filled)
  [PASS] every target_time is ISO-8601 UTC with trailing Z  (no timezone conversion needed)
  [PASS] no missing half-hours in the delivery range  (complete, and January has no DST break)
  duplicate rows removed: 0
  range: 2026-01-02T00:00:00Z .. 2026-02-01T23:30:00Z

2. Forecasts - WINDFOR (raw: hold and hindcast filter are Phase 2's job)
------------------------------------------------------------------------
  GET https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream?publishDateTimeFrom=2025-12-30T00%3A00Z&publishDateTimeTo=2026-02-02T00%3A00Z
  fetched 19856 rows in one request
  [PASS] exactly 19856 hourly rows  (got 19856)
  [PASS] no (target time, publish time) pair appears twice  (0 duplicates)
  [PASS] no missing values
  [PASS] every target_time is ISO-8601 UTC with trailing Z  (no timezone conversion needed)
  [PASS] every publish_time is ISO-8601 UTC with trailing Z  (no timezone conversion needed)
  [PASS] hindcast rows are still present (not filtered here)  (4081 of 19856 = 21%, Phase 2 filters them)
  [PASS] forecast target times are all on the hour (raw hourly, no hold applied)  (actuals are half-hourly; Phase 2 holds these across the hour)
  duplicate rows removed: 0
  distinct runs: 272
  target range: 2025-12-29T21:00:00Z .. 2026-02-03T21:00:00Z

3. Integer check
----------------
  [PASS] actuals: generation_mw is an integer column  (dtype int64)
  [PASS] forecasts: generation_mw is an integer column  (dtype int64)

4. Writing files
----------------
  wrote backend/data/actuals.csv  (1488 rows)
  wrote backend/data/forecasts.csv  (19856 rows)

Summary
-------
  actuals:   1488 rows, 2026-01-02T00:00:00Z .. 2026-02-01T23:30:00Z
  forecasts: 19856 rows, 272 runs
  missing half-hours: 0
  all checks passed
```

## Exit check

### Row counts

```text
    1489 backend/data/actuals.csv
   19857 backend/data/forecasts.csv
   21346 total
```

1,489 and 19,857 lines = 1,488 and 19,856 data rows plus a header each.

### Idempotency — two runs, byte-identical

```text
run 1:
7ae290eb5d7bafdf504e90c1c836c2610f935432da5a6d7d64423e8db3189477  backend/data/actuals.csv
e90792bb0f90224309aa3ccd2f8ab8fea56cc8c47b19229b3b4520b0317bdcb9  backend/data/forecasts.csv
run 2:
7ae290eb5d7bafdf504e90c1c836c2610f935432da5a6d7d64423e8db3189477  backend/data/actuals.csv
e90792bb0f90224309aa3ccd2f8ab8fea56cc8c47b19229b3b4520b0317bdcb9  backend/data/forecasts.csv
```

Identical. This is the check that catches accidental nondeterminism — unstable sort order, float
formatting drift, dict ordering. `generation_mw` is asserted to be an integer column precisely
because a single null would widen it to float, write `15228.0`, and change the hash for a reason
that is hard to spot.

### Independent re-derivation of the Phase 0 reference figures

The strongest available check before Phase 2 exists: recompute Phase 0's numbers from the **saved
CSVs alone**, with a separate reader (stdlib `csv`, not pandas) and no network access. If a rename,
sort or dtype change had corrupted the files, this would not reproduce.

```text
read 1488 actuals, 19856 forecast rows from CSV

matched 1488 of 1488
MAE     2016 MW   (Phase 0: 2016)
RMSE    2510 MW   (Phase 0: 2510)
bias   +1730 MW   (Phase 0: +1730)
P90     4189 MW   (Phase 0: 4189)
bias-corrected MAE 1407 MW  (Phase 0: 1407)
bias-corrected P90 3132 MW  (Phase 0: 3132)
below actual 234 of 1488  (Phase 0: 234)

RESULT: MATCHES Phase 0 exactly
```

### Exit-check summary

| Check | Result |
|---|---|
| `actuals.csv` has exactly 1,488 rows | yes |
| Missing half-hours listed individually | none to list — the range is complete |
| `forecasts.csv` holds raw hourly rows, 19,856 | yes; hold not applied, hindcast rows kept |
| No `target_time` twice in actuals | yes, 0 duplicates |
| No `(target_time, publish_time)` pair twice in forecasts | yes, 0 duplicates |
| Two runs give identical content (hash) | yes, both files |
| No app or server code written | `backend/app/` still empty |

## Carried into Phase 2

- Reproduce the reference figures above from `backend/app/forecast_selection.py` and
  `backend/app/metrics.py`, written independently with hand-calculated tests. Agreement with the
  throwaway verifier is meaningful because the two were written separately.
- `pytest 9.1.1` is already installed, so Phase 2 needs no environment work.
