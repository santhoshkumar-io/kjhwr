# Wind Forecast Checker

A web app for a UK power-buying team. It answers the two questions a buyer has when committing to
the day-ahead market:

1. **What did the wind forecast say at the moment I had to commit?**
2. **How wrong is that forecast usually, so how much cover should I buy?**

It uses national wind data from Elexon only — `WINDFOR` for forecasts, `FUELHH` (fuel type `WIND`)
for metered output — covering purchase decisions made in January 2026.

**Live: https://kjhwr-opal.vercel.app**

The app shows the forecast a buyer **could actually have seen** before the deadline. A forecast
published after the deadline is never used, even though the raw feed contains such rows.

---

## How the data moves

```mermaid
flowchart LR
    E["Elexon BMRS API<br/>WINDFOR + FUELHH"]
    S["backend/scripts/fetch_data.py<br/>(run once)"]
    C[("backend/data/<br/>actuals.csv<br/>forecasts.csv")]
    P["backend/app/<br/>forecast_selection.py<br/>metrics.py"]
    A["FastAPI<br/>/api/series<br/>/api/metrics"]
    R["React + Recharts<br/>Screen 1 and Screen 2"]

    E --> S --> C --> P --> A --> R
```

The two CSVs are **committed to this repo**, so the running app never depends on Elexon being
reachable, and a fresh clone works without a network fetch.

---

## Start it

One command. You need Docker, and nothing else — no Python, no Node, no `.env` file.

```bash
git clone https://github.com/santhoshkumar-io/kjhwr.git
cd kjhwr
docker compose up --build
```

Then open:

| | |
|---|---|
| The app | http://localhost:5173 |
| The API health check | http://localhost:8000/api/health |

To stop: `Ctrl-C`, then `docker compose down`.

### Run the tests

The tests are **not** in the container — `backend/Dockerfile` copies only `app/` and `data/`, to
keep the deployed function small. So running them needs Python 3.12 on the host.

With [uv](https://docs.astral.sh/uv/), which is what this project used:

```bash
uv venv --python 3.12 .venv
uv pip install -r backend/requirements-dev.txt
.venv/bin/python -m pytest -q
```

Or with plain Python:

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
.venv/bin/python -m pytest -q
```

### Regenerate things

```bash
# Re-download January's data from Elexon (overwrites the two CSVs)
.venv/bin/python backend/scripts/fetch_data.py

# Re-generate the findings document from the data
.venv/bin/python backend/scripts/findings.py > docs/findings.md
```

---

## What is in here

### Top level

| File | What it is |
|---|---|
| `README.md` | This file |
| `AGENTS.md` | The working rules for this repo — seven non-negotiables, commit policy, testing |
| `CLAUDE.md` | A short pointer to `AGENTS.md` for AI tooling |
| `task.md` | The original client brief |
| `docker-compose.yml` | Starts the backend and frontend together |
| `vercel.json` | Production config: two Vercel Services, routing, and the security headers |
| `pytest.ini` | Makes `backend/app` importable as `app` without installing it |
| `.env.example` | Template for `.env`. There is no API key — Elexon needs none |
| `.gitignore` | Ignores secrets, virtualenvs, `node_modules`, build output |

### `backend/` — the Python server

| File | What it does |
|---|---|
| `app/main.py` | The FastAPI server. Three endpoints, CORS, and the error handlers |
| `app/forecast_selection.py` | **The heart of the project.** Picks the newest forecast the buyer was allowed to see, and pairs it with what actually happened |
| `app/metrics.py` | The error measures — MAE, RMSE, bias, P90 — raw and bias-corrected |
| `app/request_settings.py` | Validates the query string, so a bad setting is a 400 and a sentence |
| `app/serialisation.py` | Turns the result into JSON a browser can parse, with missing values as `null` |
| `app/data_loading.py` | Reads the two CSVs with the right types |
| `data/actuals.csv` | Metered wind generation, half-hourly |
| `data/forecasts.csv` | Raw hourly wind forecasts, every published run |
| `scripts/fetch_data.py` | Downloads both feeds and writes the CSVs. Run once |
| `scripts/explore_sample.py` | Checks the live API still behaves as the decisions assume. Writes nothing |
| `scripts/findings.py` | Prints `docs/findings.md`. No figure in that file is typed by hand |
| `tests/` | Six test files — see below |
| `Dockerfile` | Python 3.12, runs as a non-root user |
| `requirements.txt` | What the server needs: FastAPI, uvicorn, pandas |
| `requirements-dev.txt` | The above plus pytest, httpx, truststore |

**The three endpoints**

| Endpoint | Returns |
|---|---|
| `GET /api/health` | Row counts and the delivery range actually held |
| `GET /api/series` | One row per delivery half-hour: forecast, real wind, error, when the forecast was published, its lead time, and whether it was held from the hour |
| `GET /api/metrics` | The accuracy numbers for the same settings, raw and bias-corrected |

All three take the same settings: `start`, `end`, `mode` (`deadline` or `hours_ahead`), and `hours`.

**The tests**

| File | What it checks |
|---|---|
| `tests/test_forecast_selection.py` | The selection rules, on tiny fixtures worked out on paper |
| `tests/test_metrics.py` | The four measures against hand arithmetic |
| `tests/test_serialisation.py` | Missing values stay missing through JSON |
| `tests/test_api.py` | The endpoints, including every bad-input case |
| `tests/test_health.py` | The health endpoint and the `/api` prefix |
| `tests/test_january_golden.py` | The real January numbers, as a regression guard |

### `frontend/` — the React page

| File | What it does |
|---|---|
| `src/App.jsx` | The shell, and the owner of the shared settings both screens follow |
| `src/components/Controls.jsx` | The one filter row: date range, mode, hours-ahead slider |
| `src/components/Screen1.jsx` | "What the forecast said, and what came" |
| `src/components/ForecastChart.jsx` | The two-line chart, with gaps left as gaps |
| `src/components/SeriesTable.jsx` | The chart's table twin, so no value is hover-only |
| `src/components/Screen2.jsx` | "How accurate is the forecast" |
| `src/components/StatTiles.jsx` | The four numbers, and the bias-corrected set beside them |
| `src/components/SweepChart.jsx` | Typical miss against how far ahead the forecast was made |
| `src/components/HourOfDayChart.jsx` | Typical miss by delivery hour |
| `src/components/WorstDaysTable.jsx` | The five worst delivery days |
| `src/lib/format.js` | All formatting, pinned to UTC |
| `src/lib/seriesUrl.js` | Settings to and from the URL, so a view can be shared |
| `src/lib/useFetch.js` | The shared fetch pattern both screens use |
| `src/index.css` | All styling, light and dark, including the phone layout |
| `vite.config.js` | Dev server, and the `/api` proxy that mirrors production routing |
| `Dockerfile` | Node 22, runs as a non-root user |

### `docs/`

| Path | What it is |
|---|---|
| `product-plan.md` | The phase-by-phase build plan this project followed |
| `findings.md` | **Generated** by `scripts/findings.py` — three findings with real numbers |
| `decisions/0001`–`0006` | The six judgement calls, each with its reasoning |
| `notes/phase-0.md` … `phase-9.md` | The evidence each phase produced, including screenshots |

### Not in a fresh clone

Created locally, never committed: `.env`, `.env.local`, `.venv/`, `frontend/node_modules/`,
`frontend/dist/`, `.vercel/`. None are needed for `docker compose up`.

---

## The assumptions

Six decisions shape every number the app shows. Each has a record explaining the reasoning and the
alternatives.

| Decision | What was decided |
|---|---|
| [0001](docs/decisions/0001-buying-deadline.md) | The buying deadline is **11:00 London time the day before delivery** — day-ahead gate closure. In January, London is UTC |
| [0002](docs/decisions/0002-date-range.md) | Decisions made 1–31 January mean **delivery days 2 January – 1 February**. Not the same month, and not a simplification worth making |
| [0003](docs/decisions/0003-hosting-and-stack.md) | Python 3.12 + FastAPI + pandas, React + Vite + Recharts, Docker locally, Vercel in production |
| [0004](docs/decisions/0004-matching-times.md) | Forecasts are hourly, actuals half-hourly. The forecast is **held across the hour**, and every held row is flagged `is_held` so it stays visible |
| [0005](docs/decisions/0005-error-measures.md) | Four measures: MAE, RMSE, mean bias, and P90 by **nearest rank**. Error is always **forecast minus actual** |
| [0006](docs/decisions/0006-bias-correction.md) | Report raw **and** bias-corrected numbers side by side, because much of the gap is not forecast error |

### Why the forecast runs high

The two feeds measure different things. `WINDFOR` forecasts the wind generation that will be
**available**; `FUELHH` meters what was actually **delivered**, after curtailment and balancing
actions reduced it. In GB wind is curtailed regularly, so a forecast above actual is expected, and a
large part of that gap was never a forecasting failure.

That is why the app shows both sets of numbers. The raw figures are what the feeds say; the
corrected ones isolate the part that is genuinely unpredictable, which is the number worth sizing a
safety margin against. It is a lean, not a rule — the forecast still came in below actual on a
meaningful share of half-hours, so it cannot be treated as a guaranteed one-way offset.

The three findings, with their numbers, are in **[docs/findings.md](docs/findings.md)**. Every
figure there is the output of `backend/scripts/findings.py`; none was typed by hand.

---

## About Docker and Vercel

Worth saying plainly rather than leaving for a reviewer to notice: **Vercel does not build these
Dockerfiles.** It builds a static React bundle and a Python function from the same source.

So Docker here is the **development environment** — it is how the app runs locally and how a
stranger starts it from this README. Heroku's container deploy would have run the Dockerfile in
production; Vercel was chosen anyway for the simpler single-project React + Python integration. The
reasoning is in [decision 0003](docs/decisions/0003-hosting-and-stack.md).

In production, `vercel.json` defines two **Vercel Services** — a `web` service rooted at
`frontend/` and an `api` service rooted at `backend/`. A service receives the **original request
path**, which is why the FastAPI routes carry the `/api` prefix and the local Vite proxy forwards
without rewriting: the page calls exactly the same URL in both environments.

---

## Use of AI tools

**Yes — AI tools were used throughout, and heavily.**

This project was built with **Claude Code** (Anthropic's Claude, model Opus). Specifically, it:

- planned each phase before writing code, and wrote the plan down first;
- wrote the application code, the tests, the scripts and this README;
- ran the scans and the checks, and captured the evidence in `docs/notes/`;
- reviewed its own output and corrected it — several defects recorded in the notes were found by
  rendering the page and looking at it, not by writing more code.

What a human did: made every judgement call recorded in `docs/decisions/`, chose between approaches
at each phase boundary, and ran the actions that touch the public internet — deploying, and
publishing the repo.

The evidence trail is deliberate. `docs/notes/phase-N.md` records what was actually run and what it
actually printed for every phase, including the mistakes: a measurement method that turned out to be
wrong, a documentation error found and not propagated, and defects that only showed up when the
rendered page was examined.
