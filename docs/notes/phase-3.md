# Phase 3 — Put a tiny version online: evidence and deploy steps

Date: 2026-10-27. Branch: `build`.

```bash
docker compose up --build
# page:    http://localhost:5173
# backend: http://localhost:8000/api/health
```

## The product plan's Vercel approach was out of date

This is exactly why the plan front-loads deployment. Checked against the current Vercel docs
(last updated Aug 2026):

| The plan assumed | Actually |
|---|---|
| `api/index.py` + legacy `vercel.json` builds | That is Vercel's **back-compat** path. The documented way to run a Python backend beside a frontend in one project is now **Services**. |
| 250 MB function bundle limit | **500 MB** uncompressed |
| pandas might be too heavy | **76 MB** installed, **165 ms** to import and load all 21,344 rows. Keep it. |
| — | **Python 3.12 is Vercel's default** — the same version `0003` chose |

Had the plan been followed literally, Phase 3 would have produced a working-but-legacy setup, and
the discovery would have come at Phase 9 instead.

### The routing detail that would otherwise cost an afternoon

**A service receives the original request path.** `GET /api/health` arrives at FastAPI as
`/api/health`, not `/health`. Two consequences, both now locked down by tests:

- FastAPI routes carry the `/api` prefix.
- The local Vite proxy forwards `/api` **without rewriting** it.

So the page calls the identical URL locally and in production. `test_the_route_carries_the_api_prefix`
asserts `/api/health` is 200 and `/health` is 404, so a well-meaning "tidy-up" to `/health` fails
the suite instead of failing in production.

Also: *routing into a service is final.* If nothing matches inside the service, Vercel does not fall
back to the other rewrites, so this app returns its own JSON 404.

## What was built

| File | Role |
|---|---|
| `backend/app/main.py` | FastAPI app named `app`; `GET /api/health` only |
| `backend/requirements.txt` | Runtime only: fastapi, uvicorn, pandas |
| `backend/requirements-dev.txt` | Adds pytest, httpx, truststore — never bundled |
| `frontend/` | Vite + React; one page, three states |
| `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml` | `docker compose up` starts both |
| `vercel.json` | Two services plus the top-level rewrites |
| `backend/.python-version` | Pins 3.12 rather than relying on the default |
| `backend/tests/test_health.py` | 5 tests on the endpoint and the 404 |

Scope held: one endpoint. `/api/series` and `/api/metrics` are Phase 4; the charts are Phases 5–6.

## Verification

### Backend direct

```json
{"status":"ok","actual_rows":1488,"forecast_rows":19856,"delivery_from":"2026-01-02T00:00:00Z","delivery_to":"2026-02-01T23:30:00Z"}
```

### Through the Vite proxy — proves path parity with production

```json
{"status":"ok","actual_rows":1488,"forecast_rows":19856,"delivery_from":"2026-01-02T00:00:00Z","delivery_to":"2026-02-01T23:30:00Z"}
```

Identical. The page will call the same `/api/health` on Vercel.

### No dev packages leaked into the runtime image

```text
pandas 3.1.0
pytest: absent, correct
truststore: absent, correct
httpx: absent, correct
```

### The server-down path

```text
$ docker compose stop backend
$ curl -s -w "HTTP:%{http_code}" localhost:5173/api/health
HTTP:502
$ curl -o /dev/null -w "page HTTP:%{http_code}" localhost:5173/
page HTTP:200
$ grep -c "Could not load data" frontend/dist/assets/*.js
1
$ docker compose start backend && curl -o /dev/null -w "%{http_code}" localhost:5173/api/health
200
```

The proxy returns 502, which trips the `!response.ok` throw and puts the page into its error state.
The page shell itself still returns 200, so this is not a blank page at the network level, and the
error string is present in the shipped bundle.

**Honest limitation:** I verified this at the network and bundle level, not by looking at a rendered
browser window. The rendered text is one of the outstanding visual checks below.

### Test suite

```text
73 passed, 1 warning in 0.73s
```

68 from Phase 2 plus 5 new. The analysis engine is untouched.

The one warning is cosmetic: Starlette now prefers `httpx2` over `httpx` for its `TestClient`.
Installing `httpx2` was blocked by this environment's permission policy, so `httpx` stays pinned and
the warning remains. It affects tests only, never the deployed function, which has neither package.

## It is live

**https://kjhwr-opal.vercel.app**

Deployed 2026-10-27 after you logged in. Verified anonymously with `curl`, which sends no cookies
or session and is therefore the incognito equivalent at the network level:

```
GET /api/health   200  {"status":"ok","actual_rows":1488,"forecast_rows":19856,
                        "delivery_from":"2026-01-02T00:00:00Z","delivery_to":"2026-02-01T23:30:00Z"}
GET /             200  <!doctype html> ... <title>Wind Forecast Checker</title>
GET /assets/index-DcbmnML_.js
                  200  221,274 bytes, and the string "/api/health" is present in it
```

`actual_rows: 1488` is identical to the local figure and to the Phase 1 saved data. The exit check
is met.

### The routing contract holds in production, not just in tests

| Request | Response | What it proves |
|---|---|---|
| `/api/health` | `200` + real JSON | The `/api` prefix reaches FastAPI with the path intact |
| `/api/nope` | `404` `{"error":"Not found","path":"/api/nope"}` | **Our** handler answered — routing into a service really is final |
| `/health` | `404` Vercel edge page | No prefix means the request never reaches the backend |

The middle row is the one worth noting: the JSON body proves Vercel did not fall back to the `web`
service when nothing matched inside `api`. That was a documentation claim in the plan; it is now an
observed behaviour.

### Deployment Protection gates deployment URLs, not the production alias

The project has `vercel_authentication` enabled, and it behaves differently per URL kind:

| URL kind | Anonymous result |
|---|---|
| Production alias — `kjhwr-opal.vercel.app` | **200**, public |
| Deployment-specific — `kjhwr-1g2tqort7-...vercel.app` | **302** → *"Protected by Vercel Authentication"* |

**Only ever submit the production alias.** A deployment-specific URL would pass a quick check in a
logged-in browser and then fail the brief's incognito requirement, which is precisely the trap that
check exists to catch. This matters again at Phases 4–9: previews are gated, so verification of new
work must use the alias after `vercel --prod`.

### The web service needed its framework stated

`vercel link` warned:

> WARNING! Multiple frameworks detected in project root: Vite, Container.
> Specify "framework" explicitly in services.

`frontend/` contains both a Vite project and a `Dockerfile`, so detection was ambiguous. `vercel.json`
now pins `"framework": "vite"` on the `web` service rather than relying on whichever Vercel guesses.

### `vercel link` also edited `.gitignore`, and the edit was reverted

It appended `.vercel` and `.env*`. Both are redundant — `.vercel/` and `*.local` were already there,
which is what actually covers the `.env.local` it created. The `.env*` line was also appended *after*
`!.env.example`, and last match wins, so it shadowed that negation. `.env.example` is already tracked
and so unaffected today, but the rule was wrong and is reverted rather than left to bite later.

## The first production deploy was rejected, and the reason mattered

```
The deployment was blocked because the commit email santhosh.kumar@omc.com
could not be matched to a GitHub account.
```

`~/.gitconfig` already said `santhoshkumars1903@gmail.com`, and no `GIT_*` environment variable or
repo-local override set anything else. That is the trap: **git bakes author identity into each commit
at the moment it is created**, so correcting the config fixes future commits and does nothing to past
ones. All seven existing commits still carried the work address, and `HEAD` is what Vercel reads.

### The anonymity problem was the bigger one

The brief requires a **public repo under an anonymous name**. Renaming it to `kjhwr` hides the
subject, but every commit would still have shown an `@omc.com` address — the employer's domain, in
the one artefact a reviewer clones and reads. The deploy block and the anonymity leak had the same
fix, so the rejection was useful rather than merely annoying.

### The rewrite, and the proof it changed nothing else

```bash
git filter-branch -f --env-filter '
  OLD="santhosh.kumar@omc.com"; NEW="santhoshkumars1903@gmail.com"
  [ "$GIT_AUTHOR_EMAIL"    = "$OLD" ] && export GIT_AUTHOR_EMAIL="$NEW"
  [ "$GIT_COMMITTER_EMAIL" = "$OLD" ] && export GIT_COMMITTER_EMAIL="$NEW"
' --tag-name-filter cat -- --all
```

A history rewrite can silently alter file content, so the check is not "does it look right" but a
comparison of **tree hashes**, which are content addresses:

| Check | Result |
|---|---|
| All 7 tree hashes vs the 7 recorded before the rewrite | **identical** — not one byte of content moved |
| Author and committer email on all 7 commits | `santhoshkumars1903@gmail.com` |
| Test suite | **73 passed** |
| Working tree | clean |

Redeployed from the corrected history: accepted, and verified again anonymously (below).

An aside worth keeping: the earlier `vercel deploy --prod` was still running in the background when
this was diagnosed. It had been launched *before* the rewrite, so it carried the old metadata and
would have failed identically. It was stopped and the process confirmed gone before relaunching, so
only one deploy was ever in flight.

### Still to do: destroy the backup refs

`filter-branch` keeps the pre-rewrite commits so the operation is undoable:

```
refs/original/refs/heads/build          26caeac
refs/original/refs/heads/main           45c6ea5
refs/original/refs/remotes/origin/main  45c6ea5
```

These still contain the work email. They are local-only and `git push` does not send them, but they
should be gone before the repo is public:

```bash
git for-each-ref --format='%(refname)' refs/original | xargs -n1 git update-ref -d
git reflog expire --expire=now --all
git gc --prune=now
```

That is irreversible, which is why it is listed for you rather than already done.

### `main` has diverged from the remote

`main` was rewritten too, so the first push after the repo rename needs
`git push --force-with-lease`. A plain push will be rejected, and that rejection is correct.

Note also that the local `origin/main` tracking ref was itself rewritten, so it currently reads
`158cf34` while the real remote is still at `45c6ea5`. A `git fetch` corrects the tracking ref and
reveals the true divergence.

## Outstanding — these need you

| Check | Status |
|---|---|
| `docker compose up` shows the Phase 1 row count | **done** |
| Server down shows a friendly message, not a blank page | **done** at network level; visual check outstanding |
| The live Vercel link shows the same number | **done** — 1,488 at the URL above |
| The live link works in an incognito window | **done** at network level; your browser check outstanding |

Two things still need you, neither blocking Phase 4:

1. **Rename the GitHub repo**, per Step 1 below. `kjhwr` still does not exist, so `vercel git connect`
   failed during linking and `origin` is dangling. The deploy did not need it — `vercel deploy`
   uploads the working directory — but the brief requires a public repo, and auto-deploy on push
   needs the connection. The first push needs `--force-with-lease`, per the divergence note above.
2. **Open the live URL in a real incognito window** and confirm the number renders, plus the
   "Could not load data" message. `curl` proves the bytes arrive; it does not prove React painted
   them.
3. **Destroy the `refs/original` backups**, per the commands above, so the work email is unreachable
   before the repo goes public.

### Step 1 — rename the repo first

The brief requires *"an anonymous repo name e.g. a random string like kjhwr"*. The remote is
currently `santhoshkumar-io/weather-forecast-checker`, which is both descriptive and personal.

Doing this **before** linking Vercel matters: the Vercel project and live URL derive from the repo,
and the README and video will both quote that URL. Renaming afterwards means redoing the link and
reissuing the URL.

1. On GitHub: **Settings → General → Repository name** → a random string, e.g. `kjhwr`.
2. Locally:

```bash
git remote set-url origin https://github.com/santhoshkumar-io/kjhwr.git
GIT_TERMINAL_PROMPT=0 git ls-remote --heads origin   # must list refs, not "Repository not found"
```

**That local command is only a pointer change.** `git remote set-url` renames nothing on GitHub, so
running it before the rename above leaves `origin` dangling and every push fails with
*"Repository not found"*. The `ls-remote` line is what distinguishes the two cases: if it errors,
the GitHub rename has not happened yet.

There is no `gh` CLI on this machine, so step 1 is a web-UI action.

Note the **owner handle stays visible** — only a separate GitHub account could hide that, which the
brief does not ask for. Only the repo name is anonymised.

### If `vercel login` fails with a self-signed certificate error

The same corporate TLS-inspecting proxy (Netskope) that broke Python in Phase 1 also breaks Node:

```
Error: self-signed certificate in certificate chain
    at TLSSocket.onConnectSecure (node:internal/tls/wrap)
```

Python was fixed with `truststore`. Node has no equivalent, so it needs the proxy's CA passed in
explicitly via `NODE_EXTRA_CA_CERTS`. The CA chain has been exported from the macOS keychain to
`~/.certs/netskope-ca.pem` (root `caadmin.netskope.com` plus the `ca.oss.de.goskope.com`
intermediates):

```bash
export NODE_EXTRA_CA_CERTS=~/.certs/netskope-ca.pem
vercel login
```

Add that `export` line to `~/.zshrc` to make it permanent. It is inert when the proxy is not
intercepting, so it is safe to leave set.

**The interception is intermittent.** Measured on 2026-10-27, after the failure above, Node reached
`api.vercel.com`, `vercel.com`, `login.vercel.com` and `registry.npmjs.org` with no CA override at
all, and `vercel whoami` returned a clean *"Logged out."* So a plain retry may simply work; the
override is the fix for when it does not.

This is a **local network condition, not a project problem**. Vercel builds on Vercel's own
infrastructure, so it never sees this proxy — nothing here affects the deployed app, and a reviewer
on a normal network will not hit it.

### Step 2 — deploy (done)

For the record, what was actually run:

```bash
export NODE_EXTRA_CA_CERTS=~/.certs/netskope-ca.pem
vercel link --yes --project kjhwr   # project name, not the repo, is what the URL derives from
vercel deploy
```

The project is named `kjhwr` so the live URL does not reveal the subject either. Vercel assigned the
first deployment straight to production and aliased it to `kjhwr-opal.vercel.app` — it appends a
random word of its own, which is no help to anonymity but no harm to it either.

Later phases deploy with `vercel --prod`, because from now on a bare `vercel deploy` creates a
*preview*, and previews are behind Vercel Authentication (see above).

The final production deploy was made after the commit-identity rewrite described above, and pinning
`"framework": "vite"` demonstrably changed the build: the served HTML arrives minified
(`<!doctype html><html lang="en">` on one line) where the pre-pin deploy served it pretty-printed.
So the redeploy was not merely bookkeeping — the live site now corresponds to the committed
`vercel.json` rather than to a config one line different.

Because `vercel.json` uses Services, both halves build from this one repo in one project — there is
nothing to configure in the dashboard.

### Step 3 — confirm

```bash
curl https://<your-url>/api/health
```

It must return the same `actual_rows: 1488` as local. Then open the URL in an **incognito window**,
which the brief requires for every submitted link.

## A note on Docker and Vercel

Vercel does not build these Dockerfiles; it builds a Python function and a static frontend. So
Docker satisfies the brief's requirement at the **development environment** level — it is how the
app runs locally and how a stranger starts it from the README.

This is stated plainly in `0003` and should be said out loud in the tech-lead video. A reviewer will
notice; it reads as a considered trade-off if we raise it first and as an oversight if they find it.

## Carried into Phase 4

- `/api/series` and `/api/metrics`, reusing `build_series` and `summarise` from Phase 2 — not
  reimplementing the logic.
- Server-side validation of every parameter, with 400s that leak no file path.
- CORS from an environment variable is Phase 8, not now.
