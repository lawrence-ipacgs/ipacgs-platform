# Architecture reference

The full architecture — the seven-layer system diagram, the evidence-to-gate
mechanism, Milestone 1.1's scope, the epic work breakdown, team/ownership,
and the release roadmap — lives in the published artifact, not duplicated
here:

**https://claude.ai/code/artifact/d83ff694-460c-45ff-9f57-45ff2c22e413**

If that link ever moves, regenerate it from the planning conversation rather
than letting this repo's docs drift into a second, competing copy of the
same information.

## What this repo implements against that document

- **Layer 2** (Master data & evidence) — `services/api/src/ipacgs/models/`
- **Layer 3** (Framework assurance engines) — not yet started; OPBOH's
  catalogue/scoring engine is the next major piece of work after this
  foundation lands.
- **Foundation** (Security/Identity/Storage/Observability rail) —
  `infra/bicep/`, `services/api/src/ipacgs/core/security.py`,
  `core/audit.py`.

Epic 0's ticket list (Section 4 of the architecture document) is the closest
thing to a spec for what's in this repo right now — each model, module and
IaC resource here traces back to one of its tickets.
