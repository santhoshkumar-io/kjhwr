# Phase 8 — Security checks: evidence

Date: 2026-10-28. Branch: `build`.

All scans were run **before** anything changed, as the build prompt asks, then again after.

## The phase's premise was already overtaken

`docs/product-plan.md:564` says *"The repo becomes public in Phase 9. After that, any leak is
permanent."* The repo has been **public since the Phase 7 window** — it was pushed early because
seven hours of work existed only on one laptop, and backing it up was worth more than the delay.

So this scan was **overdue rather than preventive**. Nothing it found changes that judgement, but
the ordering should be recorded rather than quietly skipped: for a few hours the project was public
and unscanned.

## Findings, before any change

| Scan | Result |
|---|---|
| `gitleaks` — git history | **16 commits scanned, no leaks found** |
| `gitleaks` — working tree incl. untracked | **1 finding**, analysed below |
| `pip-audit` — runtime + dev requirements | **No known vulnerabilities found** |
| `npm audit` | **found 0 vulnerabilities** |

### The one finding, and why it is not a leak

```
Finding:     VERCEL_OIDC_TOKEN="REDACTED"
RuleID:      jwt
Entropy:     5.816821
File:        /repo/.env.local
Line:        2
```

That is a genuine credential — a short-lived Vercel OIDC JWT, written by `vercel link`. It is
**untracked and ignored**, which the scan result then proves rather than assumes:

```
$ git ls-files --error-unmatch .env.local
error: pathspec '.env.local' did not match any file(s) known to git

$ git check-ignore -v .env.local
.gitignore:18:*.local	.env.local
```

So the right reading is the opposite of alarming: the only secret on this machine is exactly the
one the ignore rules were written to catch, and the history scan confirms it never reached a commit.
No fix — the action is to keep it untracked.

`.gitignore` and `.env.example` were **verified, not rewritten**, as step 1 requires. `.env.example`
holds no credential: an `ALLOWED_ORIGINS` localhost default and the public Elexon base URL.

## The history purge

The `refs/original` backups from the Phase 3 author-email rewrite still held the pre-rewrite commits
carrying a work address. Phase 8's outcome covers "the code **or its history**", so they were purged
here:

```
before:  build branch : santhoshkumars1903@gmail.com
         every ref    : santhosh.kumar@omc.com  +  santhoshkumars1903@gmail.com

after:   every ref    : santhoshkumars1903@gmail.com
         45c6ea5 is gone from the local object store
         commits reachable: 11 (was 18)
```

Visible in the scan itself — gitleaks walked **16 commits before** the purge and **10 after**, the
difference being the backup refs.

**The honest limit:** those objects were pushed to GitHub before the repo was renamed. Purging
locally makes them unreachable here; GitHub collects its own copies on its own schedule. This is
cleaned, not scrubbed.

## What changed

### CORS, from an environment variable

`ALLOWED_ORIGINS` already existed in `.env.example` and was read by no code. It now drives
`CORSMiddleware`, and `docker-compose.yml` passes it to the backend.

Two things worth being straight about rather than overclaiming:

- **The app never makes a cross-origin request.** On Vercel the page and API share an origin;
  locally the Vite proxy does the same. This exists only to refuse *other* sites.
- **With no middleware at all, browsers already refuse**, because no `Access-Control-Allow-Origin`
  comes back. What the middleware adds is an explicit, configurable allowlist — and the real risk of
  adding CORS is configuring it *looser*, which is why a test asserts the list is never `*` and
  never empty.

The exit check, demonstrated against the running container:

```
--- from an allowed origin (the app itself) ---
  HTTP/1.1 200 OK
  access-control-allow-origin: http://localhost:5173
--- from another site ---
  HTTP/1.1 200 OK
  (no access-control-allow-origin = the browser refuses to hand the body over)
```

Note the status is 200 in both cases. CORS never changes the status code — the refusal is the
browser's, caused by the missing header. A test asserting a status would pass even against a
wide-open API, so the tests assert the header's absence instead.

### The docs UI is off

`/docs`, `/redoc` and `/openapi.json` were fully live on the backend container. They were
unreachable in production only because Vercel's catch-all rewrite sends `/docs` to the frontend —
an accident of routing, not a decision. Now off in the app itself, so routing cannot re-expose them:

```
  /docs          http 404
  /redoc         http 404
  /openapi.json  http 404
```

### Errors

Already in good shape — `test_api.py` has asserted since Phase 4 that no reply contains `Traceback`,
`.py`, `/srv`, `/Users` or `line `. Re-confirmed:

```
$ curl 'http://localhost:8000/api/series?mode=xyz'
  http 400  {"error":"mode must be one of: deadline, hours_ahead"}
```

Added a generic 500 handler. This is **not** closing a leak: Starlette's default already returns a
bare "Internal Server Error" with the traceback going to logs only. It makes the guarantee explicit
and gives unexpected errors the same JSON shape as every other error.

`debug` was never set and so was already `False`, and uvicorn runs without `--reload`. Verified,
not fixed.

### Headers

Added to `vercel.json`, applying to every path:

```
  X-Content-Type-Options     nosniff
  X-Frame-Options            DENY
  Referrer-Policy            strict-origin-when-cross-origin
  applies to                 /(.*)
```

**This exit-check line cannot close in this phase.** It asks for the headers curled from the live
site, but the build prompt says *"Do not deploy"*, and `vercel.json` headers have no effect locally —
neither Docker nor Vite reads that file. The live site currently returns only
`strict-transport-security`, which Vercel adds itself. Configured here, **curled in Phase 9** after
its deploy.

### Containers

Both ran as root. Both now do not:

```
  backend  whoami: appuser
  backend  id    : uid=10001(appuser) gid=10001(appuser) groups=10001(appuser)
  frontend whoami: node
  frontend id    : uid=1000(node) gid=1000(node) groups=1000(node)
```

Base images were pinned to floating minor tags that move whenever upstream publishes a patch; now
pinned to the exact versions in use, `python:3.12.16-slim` and `node:22.23.4-slim`.

**Framing, per decision 0003:** Vercel never builds these Dockerfiles — it builds a Python function
from the same source. So this hardens the development environment and satisfies the brief's Docker
requirement. It is not what protects production, and saying otherwise would overclaim.

## Exit check

| Check | Result |
|---|---|
| gitleaks finds nothing in code or history | **Met** — 10 commits, no leaks. The one working-tree finding is the gitignored `.env.local`, never committed |
| `pip-audit` / `npm audit` show no high or critical | **Met** — both clean, before and after |
| A request from another website's address is refused | **Met** — no `access-control-allow-origin` for a foreign origin; 4 tests plus the curl above |
| A bad request returns a short message with no path | **Met** — 400 with one sentence; asserted by test |
| `docker compose exec backend whoami` ≠ `root` | **Met** — `appuser` |
| Safety headers on the live site | **Outstanding by design** — configured; closes with Phase 9's deploy |

## Scans after the changes

```
gitleaks history     : 10 commits scanned, no leaks found
gitleaks working tree: 1 finding (the gitignored .env.local, unchanged)
pip-audit            : No known vulnerabilities found
npm audit            : found 0 vulnerabilities
163 tests passed      (155 before, 8 added)
```

## Deliberately not done

**No login and no rate limiting.** Both are on the plan's "Not building" list
(`docs/product-plan.md:39,41`) and the build prompt names them. Nothing scanned recommended either;
recording the decision so a reviewer sees it was a choice.

**No CI workflow.** There is none today, the five steps do not ask for one, and adding it would be
scope creep. The consequence is real and worth stating: these scans are manual, so they are only as
current as the last time someone ran them.

## Carried into Phase 9

- Curl the three headers from the live site immediately after deploying, and record the output —
  that is the one open exit-check line from this phase.
- `ALLOWED_ORIGINS` must be set in the Vercel project environment to the production origin.
  Unset, the backend falls back to `http://localhost:5173`, which would refuse a genuine
  cross-origin caller — harmless for the app itself, since it is same-origin in production, but
  wrong if anyone expects the API to be callable.
- The README should carry decision 0003's Docker honesty note: the Dockerfiles are the development
  environment; Vercel builds a function from the same source.
