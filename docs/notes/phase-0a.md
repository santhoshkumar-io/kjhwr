# Phase 0a — Scaffold: evidence

Date: 2026-10-27. Branch: `build`.

## Exit check results

### 1. Every path named in a build prompt exists

```text
ok   AGENTS.md
ok   CLAUDE.md
ok   README.md
ok   .gitignore
ok   .env.example
ok   task.md
ok   docs/product-plan.md
ok   docs/decisions/0001-buying-deadline.md
ok   docs/decisions/0002-date-range.md
ok   docs/decisions/0003-hosting-and-stack.md
ok   docs/decisions/0004-matching-times.md
ok   docs/decisions/0005-error-measures.md
ok   docs/decisions/0006-bias-correction.md
ok   docs/notes
```

### 2. No decision record is undecided

```text
$ grep -rn "TO DECIDE" docs/decisions/
ok  no record says TO DECIDE
```

The phrase does still appear in `docs/product-plan.md`, in the Phase 1 and Phase 2 build prompts'
guard clauses ("If 0004 still says TO DECIDE, stop and list the questions"). Those are defensive and
correct; the exit check is scoped to `docs/decisions/` for that reason.

### 3. `.env` is ignored, `.env.example` is not

```text
$ touch .env && git status --porcelain --ignored | grep -E '\.env'
?? .env.example
!! .env
```

`.vscode/` was also untracked and ignored: it is editor state, and Phase 9's README has to explain
every file in a public repo.

### 4. No app code was written

```text
$ find backend frontend api -type f | grep -v '\.gitkeep'
(no output)
```

Directories exist and are empty, as intended. Phase 0 writes the first script.

### 5. Hours still total 16

Parsed from the "Phases at a glance" table in `docs/product-plan.md`:

```text
phase 0a  1      phase  5  2
phase  0  0.5    phase  6  2
phase  1  1.5    phase  7  1
phase  2  2.5    phase  8  1
phase  3  1      phase  9  1
phase  4  1.5    phase 10  1
                 total   16.0
```

## What changed in the product plan, and why

`plan.md` became `docs/product-plan.md` with 17 asserted corrections plus the commit-policy change.
Each correction was applied by a script that fails loudly if its target text is not found exactly
once, so nothing was edited silently. The substantive ones:

| Change | Reason |
|---|---|
| New "Verified data facts" section | The plan was written before anyone looked at the data, and deferred that look to Phase 0. The look has now happened against the live API. |
| `0004` moved from "To decide in Phase 0" to Decided; `0006` added | WINDFOR is hourly and FUELHH is half-hourly, so the join had to be decided before Phase 2 could be specified at all. |
| Phase 2 gained the hold function, the hindcast filter, and bias metrics | All three come from real properties of the data; none were in the original plan. |
| Phase 0 cut from 1h to 0.5h; Phase 2 raised to 2.5h; Phase 10 cut to 1h | Phase 0's discovery is done, Phase 2 absorbed the bias work, and Phase 10's recording is the user's, not build time. Total stays 16h. |
| "Do not commit" replaced with a per-phase commit policy (10 occurrences) | Phase 8 scans *git history* for secrets and Phase 9 publishes the repo. With no commits there was no history to scan, and 16 hours of work would have sat in an unsaved working tree. |
| Phase 1 exit check now specifies raw hourly forecasts | The hold and the hindcast filter belong in Phase 2 where they are testable, not baked into the saved file. |
| Phase 6 exit check softened on the lead-time curve | Publish cadence is irregular and the horizon has a ceiling, so a monotonic rise cannot be assumed. |
| Reference section: WINDFOR marked hourly, no API key confirmed, date-range derivation recorded | The original said "confirm in docs" for facts that are now confirmed, and the 2 Jan - 1 Feb range needed its derivation written down before someone "fixed" it. |

## Open item carried into Phase 3

pandas on a Vercel Python function is unverified for bundle size and cold start
(`docs/decisions/0003-hosting-and-stack.md`). If it is tight, the server falls back to the standard
library `csv` module and pandas stays in scripts and tests.
