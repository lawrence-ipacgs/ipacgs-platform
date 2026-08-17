# Web

A real Next.js frontend against the real `services/api` backend — not a
mockup. Every screen calls the actual routes: the real 37-domain/
222-question OPBOH catalogue, the real scoring engine and fatal-flaw block,
the real seven-stage UACOC intake pipeline and its checklist engine.

## What it covers

- `/` — Command Centre: organisations, start a new OPBOH assessment, recent
  assessments, the project pipeline.
- `/opboh/[id]` — the OPBOH assessment workspace: answer the real catalogue
  (with a "quick-fill" button for speed), then walk the real state machine
  (submit → begin-assessment → independently-review → decide), switching
  the "Acting as" identity in the top bar between steps the same way
  `services/opboh_workflow.py`'s segregation-of-duties rule actually
  requires a different real person at each step.
- `/opboh/[id]/report` — the real Bill-of-Health report: assurance score,
  RAG, the deterministic baseline opinion, domain scores, open findings.
- `/projects/new`, `/projects/[id]` — create a project, answer a stage's
  real exit criteria, record a stage decision, advance.

## Running it locally

Needs the API running first (`services/api/README.md`'s own "Getting
started" section), with `ENVIRONMENT=local` set — that's what turns on
both mechanisms this app depends on, neither of which exist outside a
developer's own machine:

- **CORS** for `localhost:3000` (`main.py`) — off in every deployed
  environment.
- **The dev-auth bypass** (`core/security.py`'s `get_current_user`) — no
  Entra ID app registration exists yet
  (`infra/scripts/create-app-registrations.sh` is still a pending manual
  step), so this app sends a plain name in an `X-Dev-User` header instead
  of a real bearer token. Typing a different name in the top bar's
  "Acting as" field is a real actor change — real audit events, real
  segregation-of-duties enforcement, just not a real signed-in identity.

```bash
# terminal 1 — API
cd services/api
source .venv/bin/activate
export ENVIRONMENT=local
export DATABASE_URL=postgresql+asyncpg://<user>:<pass>@localhost:5432/<db>
alembic upgrade head
python -m ipacgs.scripts.seed_stages
python -m ipacgs.scripts.seed_stage_checklists
python -m ipacgs.scripts.seed_opboh_catalogue
python -m ipacgs.scripts.seed_opboh_real_catalogue
uvicorn ipacgs.main:app --port 8000

# terminal 2 — web
cd apps/web
npm install
npm run dev
```

Then open `http://localhost:3000`. `.env.local` already points
`NEXT_PUBLIC_API_URL` at `http://localhost:8000`.

## Honest gaps

- No real sign-in — see the dev-auth bypass above. Real Entra ID/MSAL
  integration is real work for once the app registration exists.
- No RBAC on either side yet — same platform-wide gap every route's own
  docstring already documents.
- No "list assessments" endpoint exists yet, so recently-created
  assessments are only remembered in this browser's `localStorage`
  (`lib/recent.ts`) — a real list view needs a real route first.
- Error handling is minimal — enough to surface what the API actually
  says (e.g. `FW-OPBOH-015`'s fatal-flaw block message verbatim), not a
  polished empty/loading-state system.
