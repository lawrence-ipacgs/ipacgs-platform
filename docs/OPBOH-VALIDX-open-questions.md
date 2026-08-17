# OPBOH / V.A.L.I.D-X — open reconciliation questions for KMI/UACOC

Three different real, KMI-shared structures for the OPBOH/V.A.L.I.D-X framework
family now exist in this repo's `docs/`, and none of them obviously reduces to
one of the others. This repo has already built against the first one (real
37-domain catalogue, `services/api/src/ipacgs/scripts/seed_opboh_real_catalogue.py`,
merged 2026-08-17). Before building further, the questions below need an answer
from KMI/UACOC — guessing would mean asserting something about their own
framework that isn't actually confirmed, which is exactly what this codebase's
existing documentation discipline tries to avoid.

## The three structures, side by side

| | Source | Organised by | Scale | Size |
|---|---|---|---|---|
| **A. Lifecycle catalogue** (already built) | `OPBOH_37_Stages_Work_Packages_Master_Register_v1.1.xlsx`, `OPBOH_827_Explicit_Module_Fields_Master_Register_v1.1.xlsx` | Project lifecycle stage (WP01–WP37, "Strategic Inception" → "Sustainable Impact") | 0–5 score per question (`OpbohResponse.score`) | 37 domains, 222 real fields |
| **B. Role-based compliance checklist** (not yet built) | `OPBOH ASSESSMENT QUESTIONNAIRE -MANKWENG.pdf` | Project party/role (Project Owner, Land Preparations, Development Design, Documentation & Procurement, Construction, Project Closure, Developer/Infrastructure Delivery, Filling Station Operator, Shopping Complex Operator, Anchor Tenant) | **Score (1/0)** per question, per that document's own table header | 10 sections × 150 questions = ~1,500 questions |
| **C. 21-section integrated report** (not yet built) | `OPBOH REPORT STRUCTURE.png` | Neither of the above directly — its own section list (Executive Summary, Project Description, OPBOH Organisational Assessment, OPBOH Project Health Assessment, Market/Technical/Financial/Legal/Environmental/Risk Assessment, VALID-X Viability/Architecture/Leadership/Implementation/Decision/Execution findings, Conditions Register, Corrective-Action Plan, Final Scorecard, Recommendation) | 0–5 score, RAG banded **directly on that raw score**: Red 0–2, Amber 2–3, Green 4–5 | 21 report sections |

## Open questions

1. **Does structure B (the 1,500-question role-based checklist) replace,
   supplement, or run alongside structure A (the 37-work-package lifecycle
   catalogue)?** They organise the same underlying assurance area completely
   differently — by *who* (Project Owner, Filling Station Operator, …) versus
   by *when* (WP01 → WP37). A project presumably needs both answered at some
   point, but which one actually gates stage/gate progression in the platform,
   and which is a deeper compliance record kept alongside it?

2. **Is the 1/0 binary scoring in structure B a distinct compliance-checklist
   tier sitting underneath the 0–5 domain-maturity tier in structures A/C, or
   a genuine conflict?** A plausible reading: individual factual compliance
   checks ("Is the Project Owner legally constituted?") are naturally binary,
   and roll up into the coarser 0–5 domain rating used elsewhere — but that's
   this session's own inference, not confirmed by either source document.

3. **Is RAG banded on the raw 0–5 score (structure C's poster: Red 0–2 /
   Amber 2–3 / Green 4–5) or on the derived 0–100 Assurance Score (what
   `services/api/src/ipacgs/services/opboh_scoring.py` currently implements:
   Green ≥80 / Amber 60–79 / Red <60)?** Both could be legitimate — one a
   per-question/domain view, the other an assessment-level rollup — but
   that's not stated anywhere shared so far.

4. **Do structure C's 21 report sections map onto structure A's domains,
   a different set of V.A.L.I.D-X-specific domains, or a combination of
   both frameworks' outputs into one report?** The poster separates an
   "OPBOH" column (organisational + project-health assessment) from a
   "VALID-X" column (viability, architecture, leadership/governance,
   implementation, decision assurance, execution authorisation) — worth
   confirming whether V.A.L.I.D-X's own domain catalogue is a completely
   separate framework registration (`models/framework.py`) from OPBOH's, the
   way the architecture document's 25-framework wheel originally implied, or
   whether "OPBOH V.A.L.I.D-X" (the MANKWENG document's own consistent
   naming) means the two have effectively merged into one instrument in
   practice.

## Not attempted until these are answered

- Modelling structure B (the role-based checklist) as catalogue content —
  it's real, substantial (~1,500 questions), and clearly usable, but
  building it against the wrong mental model of how it relates to structure
  A would mean redoing real schema/seed work, not just editing text.
- Any change to the RAG banding logic in `opboh_scoring.py` based on
  structure C's poster — plausible it's just a different, valid view of the
  same underlying number, but banding thresholds are exactly the kind of
  thing this codebase has been careful not to silently reinterpret from a
  second source without being sure it's describing the same mechanism.
- Registering V.A.L.I.D-X as its own `Framework` — reasonable next step once
  question 4 is answered, not before.
