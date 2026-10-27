# AGENTS.md — how to work in this repo

Read this first, then `docs/product-plan.md`.

## What this is

A web app for a UK energy utility's day-ahead power-buying team. It answers two questions for
purchase decisions made in January 2026:

1. What did the wind forecast say at the moment the buyer had to commit?
2. How wrong is that forecast usually, so they can size a safety margin?

Data is Elexon only: `FUELHH` (fuelType WIND) for actuals, `WINDFOR` for forecasts. The original
client brief is `task.md`.

## Repo map

```
backend/
  app/        main.py, forecast_selection.py, metrics.py
  scripts/    explore_sample.py, fetch_data.py, findings.py
  data/       actuals.csv, forecasts.csv
  tests/
  Dockerfile
frontend/
  src/
  Dockerfile
api/index.py          Vercel entry, imports the backend app
docker-compose.yml
vercel.json
docs/
  product-plan.md     the phase plan — the spec
  decisions/          0001-0006, the human decisions
  notes/              phase-N.md, the evidence each phase produced
  findings.md         generated, never hand-typed
  video-script.md
AGENTS.md, CLAUDE.md, README.md, task.md
```

## Rules that are not negotiable

1. **One phase at a time.** Do the phase asked for, nothing beyond it. Each phase has an exit check
   in `docs/product-plan.md`; produce `docs/notes/phase-N.md` with the real output that proves it.
2. **No number is ever typed by hand.** Every figure in `docs/findings.md`, in the README, and on
   screen comes from code output. If a number appears in prose, the script that produced it must be
   in the repo and its output in the notes.
3. **Never invent data.** A target time with no permitted forecast stays missing, and renders as a
   gap. No interpolation, no forward-fill, no zero-substitution. The one deliberate exception is the
   hourly-to-half-hourly hold in `docs/decisions/0004-matching-times.md`, which is flagged in the
   data as `is_held` and must stay visible.
4. **Never use a forecast the buyer could not have seen.** Runs published after the cutoff are
   excluded, in both modes. Runs published after the target time are excluded always — note that
   WINDFOR genuinely contains such rows, so this is a live filter and not a hypothetical one.
5. **Decision gates are real.** If a record in `docs/decisions/` says TO DECIDE, stop and ask. Do
   not guess a decision that belongs to a human.
6. **Pure logic stays pure.** `forecast_selection.py` and `metrics.py` take data in and return data
   out: no web framework, no hardcoded file paths, no I/O. That is what makes them testable.
7. **Error sign convention is forecast minus actual.** Positive means the forecast was too high.
   Set once in `0005`; never flipped.

## Commit policy

Work on a branch. **Commit at the end of each phase**, message `phase-N: <goal>`.

This replaces the "do not commit" line that appeared in the original build prompts. That
instruction was a mistake: Phase 8 scans *git history* for leaked secrets, and Phase 9 publishes the
repo — both need a real history to exist. Committing per phase also means a failed experiment in
Phase 6 cannot destroy Phase 2's work.

Never commit `.env`, real credentials, or anything in `.env.example` replaced with a real value.

## Testing

`pytest backend/tests -v`. Fixtures are tiny and hand-calculated, so the expected answer is known
independently of the code. A test that merely re-runs the implementation and compares to itself is
worthless here — the whole point is that a reviewer can check the arithmetic on paper.
