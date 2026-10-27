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

## Resolved in Phase 3: keep pandas

The open question was whether pandas was too heavy for a serverless function. Measured:

| Measurement | Result | Limit |
|---|---|---|
| Runtime dependencies installed | **76 MB** (pandas 52, numpy 23, rest ~1) | Vercel bundle limit is **500 MB** uncompressed |
| `import pandas` + load all 21,344 rows | **165 ms** | Paid once per cold start, not per request |

Comfortable on both counts, so pandas stays and no stdlib fallback is needed. The data is loaded
once at module import in `backend/app/main.py`, so warm requests pay nothing.

Two related corrections to earlier assumptions, both in our favour:

- The bundle limit is **500 MB**, not the 250 MB assumed when this record was written.
- **Python 3.12 is Vercel's default runtime** — the same version this record chose, so there is no
  version wrangling. `backend/.python-version` pins it anyway rather than relying on the default.

Dev-only packages (`pytest`, `httpx`, `truststore`) were split into `backend/requirements-dev.txt`
so they are never bundled. Verified in the running container: `pytest` and `truststore` are absent.

## Deployment shape, settled in Phase 3

The approach assumed by the original plan — `api/index.py` plus a legacy `vercel.json` — is now
Vercel's **back-compat** path. The current documented way to run a Python backend beside a frontend
in one project is **Vercel Services**, which is what `vercel.json` uses: a `web` service rooted at
`frontend/` and an `api` service rooted at `backend/` with entrypoint `app.main:app`.

The routing detail that matters: **a service receives the original request path.** `GET /api/health`
arrives at FastAPI as `/api/health`, not `/health`. So routes carry the `/api` prefix and the local
Vite proxy forwards without rewriting — identical URLs in both environments. Routing into a service
is also final, so the backend owns its own 404.

Services is marked Beta on all plans. The official `vite-fastapi-starter` template uses it.
