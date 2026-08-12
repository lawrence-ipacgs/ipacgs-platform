# IPAC Governance Systems — Platform

Milestone 1.1 of Release 1: the OPBOH™ assurance engine, running on the seven-layer
architecture described in the [IPAC Governance Systems Architecture](https://claude.ai/code/artifact/d83ff694-460c-45ff-9f57-45ff2c22e413)
document. That document is the source of truth for *what* this repo builds and *why* —
this README covers *how the repo itself is laid out*.

## Repository ownership

This repository is owned by the organisation, not by any individual contributor.
Branch protection on `main` requires review before merge; see [`CODEOWNERS`](./CODEOWNERS).
No force-pushes to `main`, no direct commits — everything lands through a reviewed PR.
(`DEV-IP-001…002`)

## Layout

```
ipacgs-platform/
├── infra/bicep/       Infrastructure as code (Azure) — Epic 0
├── services/api/      Python backend — FastAPI, SQLAlchemy, Alembic
├── apps/web/          Frontend — Next.js (scaffolded when Layer/Epic 7 UI work starts)
├── docs/              Setup notes, environment guide
└── .github/workflows/ CI — lint, test, build, security scan
```

## Environments

Three environments, isolated at the resource-group level: `dev`, `test`, `prod`.
See [`infra/README.md`](./infra/README.md) for the naming convention and how to deploy.
`dev` is live — see that doc for what's actually running there. `test`/`prod`
are still infrastructure-as-code only, not deployed.

## Getting started (API)

```bash
cd services/api
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in local values — never commit .env
alembic upgrade head
python -m ipacgs.scripts.seed_opboh_catalogue   # illustrative catalogue — see that file's docstring
uvicorn ipacgs.main:app --reload
```

Interactive API docs once it's running: `http://localhost:8000/docs`.

## What's built so far

- **Epic 0 — Platform Foundation**: tenant model, identity, secrets management,
  the base master-data schema (Tenant / Organisation / Person·Party), audit trail,
  CI/CD.
- **Epic 3 — OPBOH Framework Engine**, plus the Evidence slice it depends on:
  the versioned/configurable catalogue, the scoring engine
  (`services/opboh_scoring.py`), the assessment state machine and
  segregation-of-duties enforcement (`services/opboh_workflow.py`), findings,
  and 19 HTTP routes exposing all of it (`api/routes/opboh.py`,
  `api/routes/evidence.py`). The catalogue currently loaded is an
  **illustrative placeholder**, not KMI Africa's real OPBOH content — see
  `scripts/seed_opboh_catalogue.py`'s docstring.

See the architecture document's Section 4 (work breakdown) for the full ticket
list each epic implements, and Section 6 for what's next.
