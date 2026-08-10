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
**Nothing in this repo has been deployed to Azure yet** — `infra/bicep` is
infrastructure-as-code for review, not a record of what's live.

## Getting started (API)

```bash
cd services/api
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in local values — never commit .env
alembic upgrade head
uvicorn ipacgs.main:app --reload
```

## What's in Milestone 1.1

Tenant model, identity, secrets management, the base master-data schema
(Tenant / Organisation / Person·Party), and the CI/CD foundation everything else
gets built on. See Epic 0 in the architecture document's work breakdown for the
full ticket list this scaffold implements.
