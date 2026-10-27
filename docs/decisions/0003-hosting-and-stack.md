# 0003 — Hosting and tools

**Status:** Decided (2026-10-27)

## Context

`task.md` requires React for the front end, Python for the back end, Docker, and deployment to
**Vercel or Heroku**.

## Decision

| Part | Choice |
|---|---|
| Back end | Python 3.12, FastAPI, pandas |
| Tests | pytest |
| Front end | React + Vite, Recharts |
| Local dev | `docker-compose.yml` with `backend` and `frontend` services |
| Hosting | **Vercel** — static React build + Python serverless function |
| Security tooling | gitleaks, pip-audit, npm audit |

## The Docker honesty note

Vercel does not build our `Dockerfile`; it builds a serverless Python function from `api/index.py`.
So Docker satisfies the brief at the **development environment** level: it is how the app is run
locally and how a stranger starts it from the README.

State this plainly in the README and in the tech-lead video. A reviewer will notice, and it reads
as a considered trade-off if we say it first and as an oversight if they find it.

Heroku's container deploy would have run the actual Dockerfile in production. Vercel was chosen
anyway for the simpler single-project React + Python integration.

## Open item for Phase 3

pandas on a Vercel Python function must be checked for bundle size and cold-start time before we
rely on it. The data is tiny (1,488 + ~20k rows), so if it is tight the server reads the CSVs with
the standard library `csv` module and pandas stays in the scripts and tests only. Decide this in
Phase 3 and record the measurement here — not in Phase 9.
