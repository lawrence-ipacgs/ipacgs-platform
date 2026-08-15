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
python -m ipacgs.scripts.seed_opboh_catalogue      # illustrative catalogue — see that file's docstring
python -m ipacgs.scripts.seed_stages               # illustrative S1-S4 sequence — see that file's docstring
python -m ipacgs.scripts.seed_framework_registry   # illustrative 29-framework metadata — see that file's docstring
python -m ipacgs.scripts.seed_gates                # illustrative Gate 0/1 — run after seed_stages, see that file's docstring
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
  `api/routes/evidence.py`). The catalogue content is still an
  **illustrative placeholder**, not KMI Africa's real OPBOH question bank —
  see `scripts/seed_opboh_catalogue.py`'s docstring. The *scoring* is real,
  though: a Yes/No/N-A response type, a 0-5 score, a per-response Evidence
  Sufficiency Factor (0.5-1.0), and a real Assurance Score formula
  (`weighted score x evidence factor`, banded >=80 Green / 60-79 Amber /
  <60 Red, any critical failure forcing automatic Red) — sourced from an
  OPBOH Full-Cycle Assessment Module v1.1 overview KMI shared (`docs/`).
  That's a summary infographic, not the full question bank, so a few
  specifics (how Y/N/N-A maps to score, how one evidence factor is
  determined) are this codebase's own documented interpretation — see
  `services/opboh_scoring.py`'s module docstring.
- **Epic 4 — Framework Registry**: a generic `Framework`/`FrameworkVersion`
  registry (`models/framework.py`, `services/framework_registry.py`,
  `api/routes/framework.py`) that OPBOH is now registered *into* rather than
  sitting outside of — so a second framework doesn't mean a second
  copy-pasted set of tables. OPBOH's own catalogue tables are unchanged;
  `OpbohFrameworkVersion` just gained a `framework_id` pointing at its
  registry entry (migration `0003_framework_registry`).
- **Epic 5 — Stage Engine**: the `Project` entity OPBOH's own model comments
  had been pointing at as a placeholder since Epic 3, plus the stage-gate
  mechanism PRN-001 depends on (`models/project.py`,
  `services/stage_engine.py`, `api/routes/project.py`). Stages are
  configuration (an ordered `Stage` table), not a hardcoded enum.
  `scripts/seed_stages.py` now seeds **real** content: UACOC's Phase 1
  (Intake & Screening) sequence — 7 stages (Project Submission →
  Registration → Sponsor and Ownership Verification → Integrity Screening
  → Minimum-Information Review → Classification and Prioritisation →
  Project Onboarding), sourced from their "Project Intake Full Process
  Map" document (`docs/`). That document's own overview describes a real
  5-phase, 22-step lifecycle; only Phase 1 has been shared in detail so
  far, so the seeded sequence stops at stage 7 until Phases 2-5 arrive.
  One honest known mismatch this surfaced: advancing a project's stage
  still unconditionally requires an accepted OPBOH assessment — the right
  rule for a compliance checkpoint, but not what UACOC's own document
  describes gating these particular seven administrative stages. See
  `services/stage_engine.py`'s module docstring for the detail; not fixed
  yet, since a real fix needs either per-stage configurable rules or
  confirmation from KMI/UACOC on what actually gates each step.
- **Epic 4/5 gap-closing**: the real ticket lists for Epics 4 and 5 turned
  out to be bigger than what those two epics originally shipped — see git
  history for the reconciliation. Closed since: illustrative metadata for
  the other 29 IPAC frameworks (`scripts/seed_framework_registry.py`, all
  `is_active=False` — "registered, not yet assessable"); a minimal
  sector-based applicability engine (`services/framework_applicability.py`,
  `GET /projects/{id}/applicable-frameworks`); stage reopening
  (`POST /projects/{id}/reopen-stage`, requires a reason, no supporting
  assessment — the opposite direction from PRN-001); RAG status computed
  from the existing OPBOH scoring engine (`GET /projects/{id}/rag`);
  owner/due-date assignment on the current stage
  (`POST /projects/{id}/assign`); and residual gaps surfaced via the
  existing `OpbohFinding` mechanism rather than a second one
  (`GET /projects/{id}/open-findings`). Still not attempted: jurisdiction/
  risk-based applicability (sector only), per-stage OPBOH domain-level
  entry criteria (still "needs an accepted assessment", not "needs domain
  X ≥ threshold"), and the UACOC intake-process mapping — that one's
  labelled a Spike in the ticket list, not a build task, and needs the
  actual 190-step document.
- **Epic 6 — Gate Engine (Gate 0 & Gate 1)**: gate definitions
  (`models/gate.py`), automatic readiness-pack assembly, authority/quorum/
  conflict-checked voting, decision-scope limited to proceed/hold,
  immutable content-hashed certificates, and suspend-on-reopen
  (`services/gate_engine.py`, `api/routes/gate.py`). The non-bypassable
  part is real, not just documented: `stage_engine.advance_stage` now
  refuses to move a project past a stage with an un-PROCEEDed gate
  attached — the one irreversible action this platform actually has is
  what's actually blocked. Gate definitions and authority/quorum rules
  are **illustrative** (`scripts/seed_gates.py`) — KMI's real Gate 0/1
  rules haven't been shared yet. "Signatures" on a certificate means the
  recorded identity of each voter, not a cryptographic signature — no
  PKI in this platform yet for anyone to actually sign with.
- **Epic 7 — Command Centre & Notifications (basic)**: a personal work
  queue (`GET /me/notifications`, scoped to the caller's own identity —
  no RBAC yet to safely offer anyone else's), a project health/stage-gate
  tracker view (`GET /projects`), and in-app notifications
  (`models/notification.py`, `services/notifications.py`) wired into
  stage assignment, finding assignment, and finding escalation. Two
  honest limits: there's no actual delivery mechanism (email/SMS/push) —
  a notification exists the moment something creates it, and a recipient
  finds out by asking (`GET /me/notifications`), not by being told; and
  there's no scheduler in this platform yet, so overdue-project scanning
  (`POST /notifications/scan-overdue`, WF-ESC-001…002) has to be
  triggered externally rather than running on its own.
- **Release pipeline**: `.github/workflows/release-dev.yml` builds and
  deploys a real image to `dev` on every push to `main`, OIDC-authenticated,
  no stored Azure credentials — see `infra/README.md` § Release pipeline.

See the architecture document's Section 4 (work breakdown) for the full ticket
list each epic implements, and Section 6 for what's next.
