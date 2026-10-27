# Wind Forecast Checker — Build Plan

## What we are building (plain English)

A small website for the power-buying team at a UK energy company.

They buy electricity **one day early**. They must guess how much wind power will come tomorrow.
To guess, they use a wind forecast.

The website answers two questions for January 2026:

1. **What did the wind forecast say at the time they had to buy?**
2. **How wrong is that forecast usually?** (So they can buy a safety margin.)

**The one-sentence outcome:**
A buyer opens a web page and sees, for January 2026, what the wind forecast said before the
buying deadline, and how far it usually missed.

**Who it is for:**
- The day-ahead buying team (the "customer" in the video).
- The reviewers of this assignment. They watch the video first.

**Finish line:** Phase 10 — everything submitted, every link works in a private browser window.

**Time budget:** 16 hours in total. Hours per phase are listed below.

---

## Not building

These are outside the task. Building one of them is not a small thing:
stop, and write a decision record saying why.

| Not building | Why |
|---|---|
| Machine learning or our own forecast | We check the forecast; we do not make one |
| Any other data (weather, demand, prices) | The task says Elexon wind data only |
| Live data updates | Only January 2026 is needed. Saved once in Phase 1 |
| Login, user accounts | Nobody's private data is shown |
| Database | Two small saved files are enough |
| Request limits per visitor (rate limiting) | No paid service is behind the app; nothing to protect from overuse |

---

## Decisions a human makes

Each one has a short record in `docs/decisions/`. A phase that needs one will not start
until it is filled in.

| Decision | Record | Status |
|---|---|---|
| The buying deadline time | `0001-buying-deadline.md` | Decided |
| Which dates to cover | `0002-date-range.md` | Decided |
| Hosting and tools | `0003-hosting-and-stack.md` | Decided |
| How to match forecast times to real-wind times | `0004-matching-times.md` | Decided |
| Which error numbers to show | `0005-error-measures.md` | Decided |
| Whether to show bias-corrected error | `0006-bias-correction.md` | Decided |

---

## Phases at a glance

| Phase | Goal | Hours |
|---|---|---|
| 0a | Scaffold the repo, write the decision records | 1 |
| 0 | Confirm the data shape at month scale | 0.5 |
| 1 | Save January's data | 1.5 |
| 2 | Pick the right forecast, measure the error and the bias | 2.5 |
| 3 | Put a tiny version online | 1 |
| 4 | Server sends real data | 1.5 |
| 5 | Screen 1: forecast vs real wind | 2 |
| 6 | Screen 2: how accurate is the forecast | 2 |
| 7 | Polish and write the findings | 1 |
| 8 | Security checks | 1 |
| 9 | Final deploy and README | 1 |
| 10 | Video script (recording and submitting are the user's) | 1 |
| | **Total** | **16** |

Why this order:
- **The core logic (Phase 2) comes before any screen.** A pretty chart on wrong numbers is worse than no chart.
- **The app goes online in Phase 3, not at the end.** Deploy problems found early are cheap.
- **Security (Phase 8) comes before the repo goes public (Phase 9).** After that, mistakes are visible to everyone.
- **Phase 0a exists because every build prompt below reads files that have to exist first.** `AGENTS.md`
  and the six decision records are prerequisites, not paperwork.
- **Phase 0 is short because its discovery work was already done** against the live API before this
  plan was finalised. See "Verified data facts" below. Phase 0 now confirms those facts hold for the
  whole month rather than discovering them.

---

## Phase 0a — Scaffold the repo

### Outcome
Every file the later build prompts read exists, and all six decisions are written down.

### Why now
Every build prompt below says "Read AGENTS.md, docs/product-plan.md and docs/decisions/...". None of
those existed. Phase 0 could not have started. This phase is a prerequisite, not paperwork.

### Steps (for the builder)
1. Move `plan.md` to `docs/product-plan.md` and fold in the corrections from the pre-build data
   check, so the spec and the code can never disagree.
2. Write `AGENTS.md` (and `CLAUDE.md` pointing at it): repo map, the non-negotiable rules, and the
   commit policy.
3. **Commit policy**, replacing the "Do not commit" line that used to end every build prompt: work
   on a branch, one commit per phase, message `phase-N: <goal>`. The old instruction was a mistake —
   Phase 8 scans *git history* for secrets and Phase 9 publishes the repo, so a history has to exist.
4. `.gitignore` (`.env`, `__pycache__`, `node_modules`, `dist`, `.vercel`) and `.env.example` with no
   real values.
5. Write `docs/decisions/0001` through `0006`. Create `docs/notes/` and a placeholder `README.md`
   (Phase 9 writes it properly).

### Exit check
- Every path named in any build prompt below exists.
- `grep -r "TO DECIDE" docs/decisions/` returns nothing. (Scope it to `decisions/`: the build
  prompts below legitimately mention the phrase in their guard clauses.)
- `.env` is ignored by git; `.env.example` is not.
- No app code was written.

**Time:** 1 hour

---

## Verified data facts

Checked against the live API before building, with read-only `GET`s to
`https://data.elexon.co.uk/bmrs/api/v1`. **No API key is needed.** Phase 0 re-confirms these at
month scale; it does not rediscover them.

| Fact | Result |
|---|---|
| `FUELHH` (fuelType WIND) | **Half-hourly**, 48 rows/day. Fields `startTime`, `settlementDate`, `settlementPeriod`, `generation` (MW), `publishTime`. Times UTC. |
| `WINDFOR` | **Hourly** targets. Fields `startTime`, `publishTime`, `generation` (MW). Times UTC. |
| Publish cadence | **Irregular**, ~8 runs/day. On 14 Jan: 02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30, 22:30 UTC. Gaps up to 4 hours. |
| Horizon | 73 hourly targets per run, spanning ~-1 day to +2 days. The horizon ends at a **fixed wall-clock point**, not publish+Nh: all 8 runs on 14 Jan stop at 16 Jan 21:00. So the 02:30 run reaches +66.5h but the 22:30 run only +46.5h. |
| Hindcast rows | Every run contains targets **in the past** relative to its own `publishTime`. These must be excluded — a live filter, not a hypothetical one. |
| Scale | The two feeds **do not measure the same quantity**. See below. |

### The scale finding — read this before Phase 2

For 15 Jan 2026 under the `0001` deadline (cutoff 14 Jan 11:00 UTC, so the 09:30 run):

```text
n = 24 hourly targets
mean bias = +1,094 MW
MAE       =  1,094 MW
```

They are identical because **all 24 errors were positive**, from +113 MW to +2,386 MW. WINDFOR
forecasts *available* wind; FUELHH meters *delivered* wind after curtailment. A persistent positive
gap is therefore expected and is largely **not forecast error**. This drives decision `0006`, and it
is the most interesting thing in the data.

### What this means for the 0-48 hour slider

Because each run's horizon ends at a fixed wall-clock point, at X near 48 the newest permitted run
often does not reach the target at all. Those points are legitimately missing and must render as
gaps. Coverage falls off above roughly 44 hours. Screen 1 shows a matched-point count so this is
visible rather than silent.

---

## Phase 0 — Confirm the data shape at month scale

### Outcome
The facts in "Verified data facts" are confirmed to hold across the whole date range, and the
slider's useful ceiling is measured.

### Why now
Every later phase depends on the data's shape. The single-day facts are established; what is not
yet known is whether they hold for all 31 delivery days.

### Steps (for the builder)
1. Write `backend/scripts/explore_sample.py`. The known facts become **assertions**, not
   discoveries: it should fail loudly if FUELHH is not half-hourly or WINDFOR is not hourly.
2. Across 2 Jan - 1 Feb, confirm: actuals are 48 per day with no gap in the day count; WINDFOR
   stays hourly; count the runs per day and the largest gap between runs.
3. Confirm the fixed-wall-clock horizon, and measure the **effective maximum lead time** per target.
   This is the real evidence for where the 0-48 slider stops being useful.
4. Assert the date-range cap on **both** endpoint forms, because Phase 1 depends on it:
   the paged form `/datasets/{ds}` returns **400** for a range over 7 days, while
   `/datasets/{ds}/stream` has **no cap** and returns the whole range in one request. Note that
   `/stream` returns a **bare JSON array** — there is no `{"data": [...]}` wrapper. This is the
   most likely thing to break a naive parser.
5. Write all of it into `docs/notes/phase-0.md` with the real rows as proof.

### Exit check
- `docs/notes/phase-0.md` states the time step of each feed, with the real rows that prove it.
- Runs per day and the largest publish gap, for the whole month, not one day.
- The measured lead-time ceiling.
- The date-range cap result for both endpoint forms, including the deliberate 400.
- No delivery day is entirely missing from the actuals.

### Build prompt
```text
Read AGENTS.md and docs/product-plan.md. Do Phase 0 only: Look at the real data.

Before coding, explain which pages of the Elexon API docs you will read and what you need
to learn from each feed.

Write backend/scripts/explore_sample.py. It asserts the facts in the "Verified data facts"
section and checks they hold across 2 Jan - 1 Feb 2026: resolutions, runs per day, largest
publish gap, the fixed-wall-clock horizon, the effective max lead time, and the API's
per-request date-range cap.
Do not save data files yet — that is Phase 1. Do not write app code.

Create docs/notes/phase-0.md with the real output.
Commit this phase on the branch (see AGENTS.md). Do not start Phase 1.
```

**Time:** 0.5 hours

---

## Phase 1 — Save January's data

### Outcome
All the data the app needs is saved in the project as two clean files.

### Why now
Every later phase reads these files. Saving them also means the live app never depends on Elexon being up.

### Decision gate
`0002-date-range.md` and `0004-matching-times.md` must be filled in.

### Steps (for the builder)
1. Write `backend/scripts/fetch_data.py`. Download real wind (FUELHH, fuelType WIND) for the target
   range in `0002` in **one `/stream` request** — Phase 0 proved there is no range cap on that
   endpoint form, so no chunking is needed. Remember `/stream` returns a bare JSON array.
2. Download WINDFOR forecasts for the publish range in `0002`, likewise in one request.
3. Remove repeated rows. Keep only the needed fields. Make all times UTC.
4. Save to `backend/data/actuals.csv` and `backend/data/forecasts.csv`.
5. Print a summary: row counts, first and last time, number of missing half-hours, number of duplicates removed.

### Exit check
- Real wind has **1,488 rows** (31 delivery days × 48 half-hours), or the summary lists every
  missing half-hour individually.
- The forecast file holds the **raw hourly** rows: no hold applied, no hindcast rows dropped. Both
  of those belong in Phase 2 so they stay testable. Expect **19,856 rows** (272 runs × 73 targets),
  the figure measured in Phase 0; explain any deviation.
- No target time appears twice in the real-wind file.
- No (target time, publish time) pair appears twice in the forecast file.
- Running the script twice gives files with identical content (check with a file hash).

### Build prompt
```text
Read AGENTS.md, docs/product-plan.md, docs/decisions/0002-date-range.md,
docs/decisions/0004-matching-times.md and docs/notes/phase-0.md.
If 0004 still says TO DECIDE, stop and list the questions.

Do Phase 1 only: Save January's data.
Use one /stream request per feed; Phase 0 proved there is no range cap there.

Write backend/scripts/fetch_data.py and save backend/data/actuals.csv and
backend/data/forecasts.csv as described in the plan. Use only FUELHH (WIND) and WINDFOR.
Do not fill missing values. Do not write app or server code.

Create docs/notes/phase-1.md with the real summary output and the hash of both files
from two runs. Commit this phase on the branch (see AGENTS.md). Do not start Phase 2.
```

**Time:** 1.5 hours

---

## Phase 2 — Pick the right forecast, measure the error

### Outcome
For every half hour in range, the code finds the forecast the buyer could really see, and the error.

### Why now
This is the heart of the project. The screens and the video findings all depend on it.
The reviewer will read this code first.

### Decision gate
`0001-buying-deadline.md`, `0004-matching-times.md` and `0005-error-measures.md` must be filled in.

### Steps (for the builder)
1. In `backend/app/forecast_selection.py`, write `expand_hourly_to_half_hourly(...)`: the `0004`
   zero-order hold, as its own named function so a reviewer can read it in isolation. Each output
   row carries the source run's `publishTime` and an `is_held` flag (true for the `:30` row).
2. Exclude rows where `startTime < publishTime`. WINDFOR really contains these.
3. For each target time, keep forecasts published at or before the cutoff and pick the newest.
   Two modes:
   - **Deadline mode:** cutoff = 11:00 UTC on the day before the delivery day (see `0001`).
   - **Hours-ahead mode:** cutoff = target time minus X hours (X from 0 to 48). Where the newest
     permitted run does not reach the target, the point is **missing** — never substituted.
4. Join the picked forecast to real wind. Missing on either side stays missing.
5. In `backend/app/metrics.py`, calculate the measures in `0005`, plus the bias-corrected set in
   `0006`. Every metric also returns `n`, the number of points used, so coverage is never invisible.
6. Also calculate: error by lead-time bucket, error by hour of day, the 5 worst days.
7. Write tests in `backend/tests/` with tiny made-up data where the right answer is known by hand.

### Exit check
- A test proves a forecast published **one minute after** the cutoff is ignored, even when it is newer.
- A test proves a forecast published **after the target time** is never used, in either mode.
- A test proves a target time with no allowed forecast is marked missing, not filled.
- A test proves the deadline for target 15 Jan 18:00 UTC is 14 Jan 11:00 UTC, and that this selects
  the 09:30 run and not the 11:30 one (use the real publish times from the facts section).
- A test proves the hold produces exactly two rows per forecast hour, the second flagged `is_held`.
- A test proves that at X=48, a target beyond the newest permitted run's horizon is missing, not
  filled.
- A test on a fixture with a known constant offset gives a bias-corrected MAE of exactly zero.
- A test checks each error measure against numbers worked out by hand.
- The test run shows the count of passed tests and zero skipped.
- The notes record the real January-wide bias and MAE, so Phases 6 and 7 quote one source.

### Build prompt
```text
Read AGENTS.md, docs/product-plan.md, decisions 0001, 0004, 0005, and docs/notes/phase-1.md.
If any of those decisions says TO DECIDE, stop and list the questions.

Do Phase 2 only: Pick the right forecast, measure the error.

Before coding, explain in plain English, with one worked example using real times, how
the cutoff is found in each mode and how the newest allowed forecast is picked.

Write backend/app/forecast_selection.py, backend/app/metrics.py and tests in
backend/tests/. Pure functions only: no web server, no file paths hard-coded inside the
logic. Never fill or guess missing values. Never use a forecast published after the cutoff.

Create docs/notes/phase-2.md with the full real pytest output.
Commit this phase on the branch (see AGENTS.md). Do not start Phase 3.
```

**Time:** 2.5 hours

---

## Phase 3 — Put a tiny version online

### Outcome
A simple page is live on the internet and shows one real number from the Python server.

### Why now
Deploying for the first time at the end is the biggest risk in the plan. Finding Vercel
problems now costs minutes; finding them on day 3 costs hours.

### Decision gate
`0003-hosting-and-stack.md` is filled in. The user has a Vercel account and has linked the GitHub repo
(the user does this, not the builder).

### Steps (for the builder)
1. Create the Python server (`backend/app/main.py`) with a health address that returns the number of real-wind rows.
2. Create the React page (`frontend/`) that calls it and shows the number.
3. Write `backend/Dockerfile`, `frontend/Dockerfile` and `docker-compose.yml` so one command starts both.
4. Add the Vercel setup (`vercel.json` and `api/index.py`) so the React page and the Python server deploy as one project.
5. Write the deploy steps for the user in `docs/notes/phase-3.md`.

### Exit check
- `docker compose up` starts both, and the page shows the row count from Phase 1.
- The live Vercel link shows the same number.
- The live link works in a private (incognito) browser window.
- Stopping the server makes the page show "Could not load data", not a blank page.

### Build prompt
```text
Read AGENTS.md, docs/product-plan.md, decision 0003 and docs/notes/phase-2.md.

Do Phase 3 only: Put a tiny version online.

Before coding, check the current Vercel docs for running a Python (FastAPI) function
next to a static React (Vite) build in one project. Explain the folder layout and how a
request from the page reaches the Python code, both locally (Docker) and on Vercel.

Implement the five steps. The server only exposes a health address for now.
Do not build the chart or other addresses — that is Phases 4 and 5.
Do not deploy. Write the exact deploy steps for me in docs/notes/phase-3.md.
Commit this phase on the branch (see AGENTS.md). Do not start Phase 4.
```

**Time:** 1 hour

---

## Phase 4 — Server sends real data

### Outcome
The Python server sends chart data and accuracy numbers for any valid date range and setting.

### Why now
Screens 1 and 2 need these addresses before they can be built.

### Steps (for the builder)
1. Load the saved files once when the server starts.
2. Add `GET /api/series` — settings: start date, end date, mode (deadline or hours-ahead), hours.
   Returns target time, forecast, real wind, error, the picked run's publish time, the `is_held`
   flag, and the lead time in hours.
3. Add `GET /api/metrics` — same settings. Returns the raw and bias-corrected measure sets from
   Phase 2, each with `n`, plus the mean bias actually used for the correction.
4. Check every setting on the server (dates inside range, start before end, hours 0–48, mode one of two).

### Exit check
- A date outside the range in `0002` gets a clear message and status 400, not a crash.
- `hours=-5`, `hours=abc` and `mode=xyz` each get a clear message and status 400.
- For one chosen day, the numbers from `/api/metrics` match a Phase 2 test calculation.
- No error reply contains a file path or code line.

### Build prompt
```text
Read AGENTS.md, docs/product-plan.md and docs/notes/phase-3.md.

Do Phase 4 only: Server sends real data.

Before coding, show the exact settings and reply shape of each address.

Add the two addresses to backend/app/main.py. Reuse the Phase 2 functions; do not copy
the logic. Validate all settings on the server. Add tests for every bad-input case in
the exit check. Do not build any screen.

Create docs/notes/phase-4.md with real requests and replies (good and bad) and the full
test output. Commit this phase on the branch (see AGENTS.md). Do not start Phase 5.
```

**Time:** 1.5 hours

---

## Phase 5 — Screen 1: forecast vs real wind

### Outcome
The buyer sees, for any days in January, what the forecast said before buying and what really came.

### Why now
This answers the customer's first question. It is the first thing shown in the video.

### Steps (for the builder)
1. A date range picker limited to the range in `0002`.
2. A mode switch: "Day-ahead deadline" (default) or "Forecast made at least X hours before" with a slider (0–48).
3. A line chart with two lines: forecast and real wind, in MW. Times labelled UTC.
4. Missing values show as a gap in the line. Never connect across a gap.
5. Hovering shows: time, forecast, real wind, when the forecast was made, the lead time, and whether
   the forecast value is held from the hour (`is_held`).
6. A visible "N of 1,488 points matched" readout, so gaps caused by the slider are honest rather
   than invisible.

### Exit check
- Moving the slider changes the forecast line; the real-wind line does not change.
- A day with a known missing half-hour (from Phase 1 notes) shows a visible gap.
- The page cannot choose a date outside the range.
- Hover text shows the forecast's publish time, and it is always before the cutoff.

### Build prompt
```text
Read AGENTS.md, docs/product-plan.md and docs/notes/phase-4.md.
Read the frontend-design guidance if available.

Do Phase 5 only: Screen 1.

Before coding, describe the layout in words and which address each part calls.

Build the screen in frontend/src. Use Recharts. Never connect a line across missing
values. Do not build the accuracy screen — that is Phase 6.

Create docs/notes/phase-5.md with screenshots or a description of each exit-check test
and its result. Commit this phase on the branch (see AGENTS.md). Do not start Phase 6.
```

**Time:** 2 hours

---

## Phase 6 — Screen 2: how accurate is the forecast

### Outcome
The buyer sees, in plain numbers, how far the forecast usually misses and which way.

### Why now
This answers the customer's second question. It is the part that turns a chart into a decision tool.

### Steps (for the builder)
1. Four big numbers (MAE, RMSE, mean bias, P90 — see `0005`), each with a one-line plain sentence
   underneath. Example: "9 times out of 10, the forecast missed by less than 2,400 MW." (number from
   the data). Each sentence is phrased as a **procurement consequence** — what the buyer does
   differently — not as a statistics definition.
2. A clearly labelled bias-corrected panel (`0006`) beside the raw numbers, plus one short
   plain-English paragraph on why the forecast runs high.
2. A chart: average miss vs how many hours ahead the forecast was made. **Build this by sweeping
   the hours-ahead setting and comparing whole series — never by bucketing a deadline-mode series
   by lead time.** In deadline mode one run serves each delivery day, so lead time is a proxy for
   hour of day (they correlate at 0.9993 on the real data) and such a chart would relabel overnight
   wind behaviour as forecast staleness. It even slopes the wrong way. Measured in Phase 2; see
   `docs/notes/phase-2.md`.
3. A chart: average miss by hour of the day.
4. A table: the 5 worst days, with their average miss.
5. All of it follows the same date range and mode as Screen 1.

### Exit check
- A person who has never seen the app can explain each big number from its sentence alone.
- The hours-ahead chart shows bigger misses for forecasts made earlier, **when built by sweeping X**:
  MAE goes from **1,691 MW at 0 h** to **2,320 MW at 46 h**. If the chart does not show that, check
  first that it is sweeping X rather than bucketing a single deadline-mode series by lead time —
  that mistake produces a chart that slopes the wrong way for a reason that has nothing to do with
  forecasting.
- Above about 42 hours the comparison stops being like-for-like, because the point set shrinks
  (100% coverage to X=42, then 98% / 90% / 85% / 81% at 44 / 46 / 47 / 48). The matched-point
  readout must make that visible, and the notes must say it.
- Changing the date range changes all four numbers.
- Every number on the screen matches `/api/metrics` for the same settings.

### Build prompt
```text
Read AGENTS.md, docs/product-plan.md, decision 0005 and docs/notes/phase-5.md.

Do Phase 6 only: Screen 2.

Before coding, write the plain sentence for each of the four numbers and show it to me.

Build the screen in frontend/src. Every number comes from the server. No number is
typed into the page by hand. Do not add new measures beyond decision 0005.

Create docs/notes/phase-6.md with evidence for each exit-check line.
Commit this phase on the branch (see AGENTS.md). Do not start Phase 7.
```

**Time:** 2 hours

---

## Phase 7 — Polish and write the findings

### Outcome
The app looks clean on a laptop and a phone, and there are 3 findings with real numbers for the video.

### Why now
The reviewers start with the customer demo. First impression decides how they read the rest.

### Steps (for the builder)
1. Clean layout: clear titles, spacing, readable on a phone (no sideways scrolling).
2. Loading message while data loads; friendly message if the server fails.
3. Write `backend/scripts/findings.py` that prints the key findings from the data.
4. Save its output to `docs/findings.md`: 3 findings, each with a number and what it means for buying.

### Exit check
- On a phone-sized screen (about 380 px wide) nothing scrolls sideways.
- Stopping the server shows the friendly message.
- Every number in `docs/findings.md` comes from the script output, and the notes include that output.

### Build prompt
```text
Read AGENTS.md, docs/product-plan.md and docs/notes/phase-6.md.

Do Phase 7 only: Polish and write the findings.

Before coding, list the layout problems you see on a phone-sized screen.

Fix the layout and the loading/error states. Write backend/scripts/findings.py and
create docs/findings.md from its real output. Do not type numbers by hand.
Do not add new features.

Create docs/notes/phase-7.md. Commit this phase on the branch (see AGENTS.md). Do not start Phase 8.
```

**Time:** 1 hour

---

## Phase 8 — Security checks

### Outcome
Nothing secret is in the code or its history, and bad requests cannot break the app or reveal its insides.

### Why now
The repo becomes public in Phase 9. After that, any leak is permanent.

### Steps (for the builder)
1. **Secrets:** Scan the code and the full git history (gitleaks). `.gitignore` and `.env.example`
   were created in Phase 0a — verify they are still correct rather than creating them now. This
   scan is meaningful only because Phase 0a established a real commit history.
2. **Weak packages:** Run `pip-audit` and `npm audit`. Update anything rated high or critical.
3. **Who may call the server:** Allow only the app's own address (CORS setting), from an environment variable.
4. **Safe errors and headers:** Debug mode off in production. Errors show a short message only. Add basic safety headers in `vercel.json`
   (no content-type guessing, no framing by other sites, referrer policy).
5. **Docker:** Both containers run as a normal user, not root. Use pinned base image versions.

### Exit check
- gitleaks finds nothing in the code or history.
- `pip-audit` and `npm audit` show no high or critical issues (any remaining issue is listed with a reason).
- A request from another website's address is refused by the browser (CORS), shown with a real test.
- A bad request returns a short message with no file path or code line.
- `docker compose exec backend whoami` does not print `root`.
- The safety headers appear in the live site's response (checked with curl).

### Build prompt
```text
Read AGENTS.md, docs/product-plan.md and docs/notes/phase-7.md.

Do Phase 8 only: Security checks.

Before changing anything, run all scans and list every finding with its risk in plain English.

Fix the findings using the five steps. Do not add login or rate limiting (on the
Not building list). Do not deploy.

Create docs/notes/phase-8.md with the full real output of every scan, before and after.
Commit this phase on the branch (see AGENTS.md). Do not start Phase 9.
```

**Time:** 1 hour

---

## Phase 9 — Final deploy and README

### Outcome
The final app is live, the repo is public with a random name, and the README lets a stranger run it.

### Why now
The video shows both the live app and the repo. They must be final before recording.

### Steps (for the builder)
1. Write `README.md`: what it does (plain), every folder and file explained, how to start with Docker, how to run tests,
   live link, the assumptions from the decision records, and a section **"Use of AI tools"**
   (Claude and Claude Code helped plan, write code, and review).
2. Add a simple diagram of how data moves (Elexon → saved files → Python server → React page).
3. Give the user the final deploy steps and the steps to make the repo public with a random name.

### Exit check
- Following only the README, a fresh copy of the repo starts with one command.
- The README states that AI tools were used.
- The live link, the repo, and the README links all open in a private (incognito) window.
- The repo name is a random string (e.g. `kjhwr`), with no company or personal name.

### Build prompt
```text
Read AGENTS.md, docs/product-plan.md, all decision records and docs/notes/phase-8.md.

Do Phase 9 only: Final deploy and README.

Before writing, list every folder and file that the README must explain.

Write README.md as described, in simple English. Test the "how to start" steps in a
fresh clone in a temp folder. Do not deploy or make the repo public yourself — write the
exact steps for me.

Create docs/notes/phase-9.md with the real output of the fresh-clone test.
Commit this phase on the branch (see AGENTS.md). Do not start Phase 10.
```

**Time:** 1 hour

---

## Phase 10 — Video and submit

### Outcome
A video under 10 minutes is on YouTube (unlisted), and the form is submitted.

### Why now
The reviewers start with the video. No video means no review.

### Steps
1. Ask Claude Code to draft `docs/video-script.md` (two parts, 5 minutes each).
2. **Part 1 — customer (max 5 min):** their problem in one sentence; live demo of both screens; the 3 findings; how to use the error range as a safety margin; next steps (e.g. adding weather data).
3. **Part 2 — tech lead (max 5 min):** the data-flow diagram; folder tour; the forecast-picking code and its tests; Docker and deploy; security checks; how AI tools were used; trade-offs.
4. Practise twice. Record. Upload as **unlisted**.
5. Fill in the submission form.

### Exit check
- Video length is under 10:00.
- Video, repo and live app all open in a private (incognito) window.
- Form submitted.

### Build prompt
```text
Read AGENTS.md, docs/product-plan.md, docs/findings.md, README.md and all notes.

Do Phase 10 step 1 only: draft docs/video-script.md.
Part 1 (customer, max 5 minutes, about 650 words) and Part 2 (tech lead, max 5 minutes,
about 650 words). Simple spoken English, short sentences. Use only numbers from
docs/findings.md. Mark where to switch screens.
Commit this phase on the branch (see AGENTS.md).
```

**Time:** 1 hour of build time. Recording, uploading and submitting are the user's and sit outside
the build budget.

---

## Reference for the builder

Exact technical details. Check each one against the live docs in Phase 0.

**Data feeds**
- Real wind: https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream — keep `fuelType = "WIND"`; fields `startTime`, `generation` (MW). **Half-hourly.**
- Forecast: https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream — fields `startTime`, `publishTime`, `generation` (MW). **Hourly.**
- Base address: `https://data.elexon.co.uk/bmrs/api/v1` — confirmed working, **no key needed**.

**Numbers and where they come from**
- 1,488 real-wind rows = 31 delivery days (2 Jan – 1 Feb 2026) × 48 half-hours. That delivery range
  is **derived** from the brief's "decisions made in January 2026": decisions on 1–31 Jan buy
  delivery for 2 Jan – 1 Feb. See `0002`; do not "simplify" it to 1–31 Jan.
- 744 forecast hours over the same range, held to 1,488 comparison points by `0004`.
- Hours-ahead slider 0–48: the earliest target (2 Jan 00:00) minus 48 h = 31 Dec 00:00; forecasts are downloaded from 30 Dec to cover it.
- Buying deadline time: see `0001`.

**Tools**
- Server: Python 3.12, FastAPI, pandas. Tests: pytest.
- Page: React with Vite, Recharts.
- Local start: `docker-compose.yml` with `backend` and `frontend` services.
- Hosting: Vercel (static React build + Python function).
- Security: gitleaks, pip-audit, npm audit.

**Expected folder layout**
```text
backend/
  app/        main.py, forecast_selection.py, metrics.py
  scripts/    explore_sample.py, fetch_data.py, findings.py
  data/       actuals.csv, forecasts.csv
  tests/
  Dockerfile
frontend/
  src/
  Dockerfile
api/index.py          (Vercel entry, imports backend app)
docker-compose.yml
vercel.json
docs/                 product-plan.md, decisions/, notes/, findings.md, video-script.md
AGENTS.md, CLAUDE.md, README.md
```