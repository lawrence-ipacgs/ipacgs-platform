"""Seeds the REAL OPBOH catalogue — 37 domains, 222 questions — replacing
the illustrative 4-domain/8-question placeholder (`seed_opboh_catalogue.py`,
left in place, now deactivated by this script) as the active version.

Sourced from two KMI-shared controlled registers (`docs/`), both version
1.1, shared 2026-08-16:

- `OPBOH_37_Stages_Work_Packages_Master_Register_v1.1.xlsx` — the real
  37-work-package full-cycle architecture (WP01-WP37, six lifecycle
  clusters) and its 222 controlled "focus fields", six per work package.
- `OPBOH_827_Explicit_Module_Fields_Master_Register_v1.1.xlsx` — confirms
  the same 37/222/3,700 structure from the field-dictionary side.

**What's real here, and what isn't** — read this before trusting a field:

- Domain `code`/`name` (WP01..WP37 and their real titles) and each
  question's `control_objective` (the real Focus Field name) are sourced
  verbatim from the register, with two categories of correction, both
  documented in full in this repo's history rather than silently applied:
  (1) light acronym-casing fixes (the register's own export renders e.g.
  "Nema Triggers", "Sg Diagram" — corrected to NEMA/SG etc., wording
  unchanged); (2) **generalisation of project-identifying content**. The
  register's own "Source & Control" sheet names its question-bank source as
  a specific real development (a retail/filling-station complex) — most of
  the 222 focus fields are genuinely generic, but 12 named that project's
  actual anchor retailer, fuel brand, road number or site size directly
  (e.g. "Boxer Superstores Anchor Alignment", "Totalenergies Standards",
  "R567 Entrance", "3 Ha Site Extent"). Those 12 are generalised to their
  role instead (anchor retailer -> "Anchor Tenant", fuel brand -> "Fuel
  Partner", the road reference -> "Site Entrance"/"Road Frontage Exposure",
  the hectare figure dropped from the field name entirely — the field still
  exists to capture whatever the real site's own extent is).
  `domain.description` is deliberately left blank: the register's "Stage
  Purpose" column (the obvious source for it) turned out to be far more
  project-specific than the focus fields themselves, naming real tenants,
  brands and site figures in nearly every one of the 37 entries — not
  salvageable by generalisation the way the 12 fields above were.
- `question_text` is **not** KMI's own question wording. The register's
  real 3,700-question bank is itself generated per-project (each question
  literally names the source project throughout) — this script deliberately
  does not import it. Every `question_text` here is this codebase's own
  synthesis over the real, sourced field name: `"Is there current, accepted
  and traceable evidence for '{field name}' at this stage?"` — a
  documented interpretation, not confirmed spec, same pattern
  `opboh_scoring.py`'s own docstring already uses for its scoring-formula
  gaps.
- `is_critical_control` marks exactly the first focus field of each of the
  37 domains (37 critical controls total). The register never marks
  question-level criticality anywhere — that is genuinely an
  assessment-time judgement in the real spec (see `SCR-004`/`SCR-005` in
  the 827-field register), not a static catalogue attribute. This is a
  simple, systematic placeholder so `FW-OPBOH-015`'s fatal-flaw mechanism
  stays live on the real catalogue, not a claim that these particular 37
  controls are the ones KMI would actually flag as fatal-flaw.
- `evidence_type_hint` is the register's own real "Data Type / Allowed
  Values" text for that field, unchanged.
- `weight`/`min_score_threshold` stay this model's own defaults (1.0 / 3.0)
  — the register gives no explicit numeric weighting per domain, so there
  was nothing to source these from.

Run with:
    python -m ipacgs.scripts.seed_opboh_real_catalogue

Idempotent — checks for an existing catalogue at REAL_VERSION_LABEL before
inserting. Also deactivates the illustrative catalogue
(`seed_opboh_catalogue.ILLUSTRATIVE_VERSION_LABEL`) if it's currently
active, fulfilling the promise that script's own docstring already made:
mark the real version active and the illustrative one inactive rather than
deleting it — existing assessments still reference it by ID.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select

from ipacgs.core.db import async_session_factory, engine
from ipacgs.models.framework import Framework
from ipacgs.models.opboh import OpbohDomain, OpbohFrameworkVersion, OpbohQuestion
from ipacgs.scripts.seed_opboh_catalogue import ILLUSTRATIVE_VERSION_LABEL

REAL_VERSION_LABEL = "1.1"
SEED_ACTOR = "seed-script"
# Matches migration 0003_framework_registry's own OPBOH row — same
# get-or-create reasoning seed_opboh_catalogue.py already documents.
_OPBOH_FRAMEWORK_CODE = "OPBOH"


@dataclass(frozen=True)
class SeedQuestion:
    control_objective: str
    question_text: str
    is_critical_control: bool
    pass_threshold: float
    evidence_type_hint: str | None = None


@dataclass(frozen=True)
class SeedDomain:
    code: str
    name: str
    weight: float
    min_score_threshold: float
    questions: tuple[SeedQuestion, ...]


CATALOGUE: tuple[SeedDomain, ...] = (
    SeedDomain(
        code="WP01",
        name="Strategic Inception and Project Mandate",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Project Vision",
                question_text="Is evidence accepted and current for 'Project Vision'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Scope Mandate",
                question_text="Is evidence accepted and current for 'Scope Mandate'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Decision Authority",
                question_text="Is evidence accepted and current for 'Decision Authority'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
            SeedQuestion(
                control_objective="Developer Appointment",
                question_text="Is evidence accepted and current for 'Developer Appointment'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Client Objectives",
                question_text="Is evidence accepted and current for 'Client Objectives'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Governance Structure",
                question_text="Is evidence accepted and current for 'Governance Structure'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP02",
        name="Site Identification and Opportunity Discovery",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Road Frontage Exposure",
                question_text="Is evidence accepted and current for 'Road Frontage Exposure'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Site Extent",
                question_text="Is evidence accepted and current for 'Site Extent'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Market Gap",
                question_text="Is evidence accepted and current for 'Market Gap'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Community Catchment",
                question_text="Is evidence accepted and current for 'Community Catchment'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Mobility Flows",
                question_text="Is evidence accepted and current for 'Mobility Flows'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Competitive Landscape",
                question_text="Is evidence accepted and current for 'Competitive Landscape'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP03",
        name="Preliminary Site Screening",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Ownership Confirmation",
                question_text="Is evidence accepted and current for 'Ownership Confirmation'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Servitudes",
                question_text="Is evidence accepted and current for 'Servitudes'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Basic Zoning Position",
                question_text="Is evidence accepted and current for 'Basic Zoning Position'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Status + authority/reference + dates/conditions",
            ),
            SeedQuestion(
                control_objective="Environmental Sensitivity",
                question_text="Is evidence accepted and current for 'Environmental Sensitivity'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Access Constraints",
                question_text="Is evidence accepted and current for 'Access Constraints'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Bulk Services Proximity",
                question_text="Is evidence accepted and current for 'Bulk Services Proximity'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP04",
        name="Sponsor and Entity Readiness",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Client Capacity",
                question_text="Is evidence accepted and current for 'Client Capacity'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Corporate Documentation",
                question_text="Is evidence accepted and current for 'Corporate Documentation'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Tax Status",
                question_text="Is evidence accepted and current for 'Tax Status'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Decision-Making Mandate",
                question_text="Is evidence accepted and current for 'Decision-Making Mandate'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Funding Preparedness",
                question_text="Is evidence accepted and current for 'Funding Preparedness'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Legal Authority",
                question_text="Is evidence accepted and current for 'Legal Authority'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
        ),
    ),
    SeedDomain(
        code="WP05",
        name="Land Security and Site Control",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Title Deed",
                question_text="Is evidence accepted and current for 'Title Deed'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Landowner Consent",
                question_text="Is evidence accepted and current for 'Landowner Consent'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Status + authority/reference + dates/conditions",
            ),
            SeedQuestion(
                control_objective="Lease or Purchase Rights",
                question_text="Is evidence accepted and current for 'Lease or Purchase Rights'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Status + authority/reference + dates/conditions",
            ),
            SeedQuestion(
                control_objective="Site Boundaries",
                question_text="Is evidence accepted and current for 'Site Boundaries'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="SG Diagram",
                question_text="Is evidence accepted and current for 'SG Diagram'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Wayleaves",
                question_text="Is evidence accepted and current for 'Wayleaves'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Status + authority/reference + dates/conditions",
            ),
        ),
    ),
    SeedDomain(
        code="WP06",
        name="Feasibility Studies and Market Demand",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Retail Demand",
                question_text="Is evidence accepted and current for 'Retail Demand'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Fuel Demand",
                question_text="Is evidence accepted and current for 'Fuel Demand'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Anchor Tenant Viability",
                question_text="Is evidence accepted and current for 'Anchor Tenant Viability'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
            SeedQuestion(
                control_objective="Line-Shop Demand",
                question_text="Is evidence accepted and current for 'Line-Shop Demand'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Fast-Food Demand",
                question_text="Is evidence accepted and current for 'Fast-Food Demand'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Traffic Volumes",
                question_text="Is evidence accepted and current for 'Traffic Volumes'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
        ),
    ),
    SeedDomain(
        code="WP07",
        name="Traffic, Access and Mobility Feasibility",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Site Entrance",
                question_text="Is evidence accepted and current for 'Site Entrance'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Turning Lanes",
                question_text="Is evidence accepted and current for 'Turning Lanes'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Sight Distances",
                question_text="Is evidence accepted and current for 'Sight Distances'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Heavy Vehicle Movement",
                question_text="Is evidence accepted and current for 'Heavy Vehicle Movement'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Pedestrian Safety",
                question_text="Is evidence accepted and current for 'Pedestrian Safety'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Public Transport Interface",
                question_text="Is evidence accepted and current for 'Public Transport Interface'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP08",
        name="Bulk Services and Infrastructure Feasibility",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Water Supply",
                question_text="Is evidence accepted and current for 'Water Supply'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Sewer Capacity",
                question_text="Is evidence accepted and current for 'Sewer Capacity'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Stormwater Discharge",
                question_text="Is evidence accepted and current for 'Stormwater Discharge'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Electrical Capacity",
                question_text="Is evidence accepted and current for 'Electrical Capacity'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Fire Water",
                question_text="Is evidence accepted and current for 'Fire Water'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="ICT Services",
                question_text="Is evidence accepted and current for 'ICT Services'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP09",
        name="Environmental Screening and Scoping",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="NEMA Triggers",
                question_text="Is evidence accepted and current for 'NEMA Triggers'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Wetland Sensitivity",
                question_text="Is evidence accepted and current for 'Wetland Sensitivity'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Biodiversity Risk",
                question_text="Is evidence accepted and current for 'Biodiversity Risk'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Heritage Risk",
                question_text="Is evidence accepted and current for 'Heritage Risk'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Groundwater Risk",
                question_text="Is evidence accepted and current for 'Groundwater Risk'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Noise Sources",
                question_text="Is evidence accepted and current for 'Noise Sources'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP10",
        name="Land Use Rights and Zoning",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Current Agricultural Zoning",
                question_text="Is evidence accepted and current for 'Current Agricultural Zoning'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Status + authority/reference + dates/conditions",
            ),
            SeedQuestion(
                control_objective="Rezoning Pathway",
                question_text="Is evidence accepted and current for 'Rezoning Pathway'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Status + authority/reference + dates/conditions",
            ),
            SeedQuestion(
                control_objective="Consent Use",
                question_text="Is evidence accepted and current for 'Consent Use'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Status + authority/reference + dates/conditions",
            ),
            SeedQuestion(
                control_objective="Site Development Plan",
                question_text="Is evidence accepted and current for 'Site Development Plan'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Parking Compliance",
                question_text="Is evidence accepted and current for 'Parking Compliance'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="FAR and Coverage",
                question_text="Is evidence accepted and current for 'FAR and Coverage'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
        ),
    ),
    SeedDomain(
        code="WP11",
        name="Environmental Authorisation - Estimated 10 Months",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Screening Report",
                question_text="Is evidence accepted and current for 'Screening Report'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Specialist Studies",
                question_text="Is evidence accepted and current for 'Specialist Studies'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Draft BAR or EIA",
                question_text="Is evidence accepted and current for 'Draft BAR or EIA'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Public Participation",
                question_text="Is evidence accepted and current for 'Public Participation'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Authority Comments",
                question_text="Is evidence accepted and current for 'Authority Comments'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
            SeedQuestion(
                control_objective="EMPr",
                question_text="Is evidence accepted and current for 'EMPr'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
        ),
    ),
    SeedDomain(
        code="WP12",
        name="Stakeholder Mapping and Public Participation",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Municipality",
                question_text="Is evidence accepted and current for 'Municipality'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Road Authority",
                question_text="Is evidence accepted and current for 'Road Authority'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
            SeedQuestion(
                control_objective="DMRE",
                question_text="Is evidence accepted and current for 'DMRE'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Environmental Authority",
                question_text="Is evidence accepted and current for 'Environmental Authority'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
            SeedQuestion(
                control_objective="Community Leaders",
                question_text="Is evidence accepted and current for 'Community Leaders'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
            SeedQuestion(
                control_objective="Neighbouring Landowners",
                question_text="Is evidence accepted and current for 'Neighbouring Landowners'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
        ),
    ),
    SeedDomain(
        code="WP13",
        name="Concept Development",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Site Layout",
                question_text="Is evidence accepted and current for 'Site Layout'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Anchor Store Placement",
                question_text="Is evidence accepted and current for 'Anchor Store Placement'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
            SeedQuestion(
                control_objective="Fuel Forecourt Interface",
                question_text="Is evidence accepted and current for 'Fuel Forecourt Interface'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Line-Shop Frontage",
                question_text="Is evidence accepted and current for 'Line-Shop Frontage'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="QSR Positioning",
                question_text="Is evidence accepted and current for 'QSR Positioning'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Parking Concept",
                question_text="Is evidence accepted and current for 'Parking Concept'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP14",
        name="Retail Masterplanning and GLA Strategy",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Anchor GLA",
                question_text="Is evidence accepted and current for 'Anchor GLA'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Line-Shop GLA",
                question_text="Is evidence accepted and current for 'Line-Shop GLA'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="QSR GLA",
                question_text="Is evidence accepted and current for 'QSR GLA'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Forecourt Convenience Offer",
                question_text="Is evidence accepted and current for 'Forecourt Convenience Offer'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Back-of-House Allocation",
                question_text="Is evidence accepted and current for 'Back-of-House Allocation'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Loading Areas",
                question_text="Is evidence accepted and current for 'Loading Areas'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP15",
        name="Anchor Tenant Alignment",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Anchor Tenant Specs",
                question_text="Is evidence accepted and current for 'Anchor Tenant Specs'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
            SeedQuestion(
                control_objective="Anchor Lease Principles",
                question_text="Is evidence accepted and current for 'Anchor Lease Principles'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Loading Requirements",
                question_text="Is evidence accepted and current for 'Loading Requirements'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Store Footprint",
                question_text="Is evidence accepted and current for 'Store Footprint'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Service Yard",
                question_text="Is evidence accepted and current for 'Service Yard'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Delivery Windows",
                question_text="Is evidence accepted and current for 'Delivery Windows'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Date / duration / schedule status",
            ),
        ),
    ),
    SeedDomain(
        code="WP16",
        name="Tenant Acquisition Strategy",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Target Tenant List",
                question_text="Is evidence accepted and current for 'Target Tenant List'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
            SeedQuestion(
                control_objective="Leasing Brochure",
                question_text="Is evidence accepted and current for 'Leasing Brochure'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Anchor-Led Positioning",
                question_text="Is evidence accepted and current for 'Anchor-Led Positioning'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Rental Assumptions",
                question_text="Is evidence accepted and current for 'Rental Assumptions'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Tenant Due Diligence",
                question_text="Is evidence accepted and current for 'Tenant Due Diligence'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
            SeedQuestion(
                control_objective="Letters of Intent",
                question_text="Is evidence accepted and current for 'Letters of Intent'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP17",
        name="Line-Shop Tenant Mix and Leasing",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Pharmacy Option",
                question_text="Is evidence accepted and current for 'Pharmacy Option'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Cellular Tenant",
                question_text="Is evidence accepted and current for 'Cellular Tenant'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
            SeedQuestion(
                control_objective="Banking/ATM",
                question_text="Is evidence accepted and current for 'Banking/ATM'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Bakery or Deli",
                question_text="Is evidence accepted and current for 'Bakery or Deli'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Local Enterprise",
                question_text="Is evidence accepted and current for 'Local Enterprise'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Beauty or Personal Care",
                question_text="Is evidence accepted and current for 'Beauty or Personal Care'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP18",
        name="Fast-Food Chain Restaurant Acquisition",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Brand Targeting",
                question_text="Is evidence accepted and current for 'Brand Targeting'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Drive-Through Feasibility",
                question_text="Is evidence accepted and current for 'Drive-Through Feasibility'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Kitchen Extraction",
                question_text="Is evidence accepted and current for 'Kitchen Extraction'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Grease Traps",
                question_text="Is evidence accepted and current for 'Grease Traps'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Delivery Access",
                question_text="Is evidence accepted and current for 'Delivery Access'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Seating Areas",
                question_text="Is evidence accepted and current for 'Seating Areas'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP19",
        name="Fuel Partner and Forecourt Coordination",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Fuel Partner Standards",
                question_text="Is evidence accepted and current for 'Fuel Partner Standards'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Forecourt Layout",
                question_text="Is evidence accepted and current for 'Forecourt Layout'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Tank Farm",
                question_text="Is evidence accepted and current for 'Tank Farm'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Fuel Logistics",
                question_text="Is evidence accepted and current for 'Fuel Logistics'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="C-Store Integration",
                question_text="Is evidence accepted and current for 'C-Store Integration'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Brand Signage",
                question_text="Is evidence accepted and current for 'Brand Signage'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP20",
        name="Development Design",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Architectural Design",
                question_text="Is evidence accepted and current for 'Architectural Design'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Civil Design",
                question_text="Is evidence accepted and current for 'Civil Design'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Structural Design",
                question_text="Is evidence accepted and current for 'Structural Design'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="MEP Design",
                question_text="Is evidence accepted and current for 'MEP Design'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Fire Strategy",
                question_text="Is evidence accepted and current for 'Fire Strategy'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Landscaping",
                question_text="Is evidence accepted and current for 'Landscaping'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP21",
        name="Engineering Design and Technical Documentation",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Bulk Earthworks",
                question_text="Is evidence accepted and current for 'Bulk Earthworks'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Stormwater Design",
                question_text="Is evidence accepted and current for 'Stormwater Design'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Road Pavements",
                question_text="Is evidence accepted and current for 'Road Pavements'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Water Reticulation",
                question_text="Is evidence accepted and current for 'Water Reticulation'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Sewer Reticulation",
                question_text="Is evidence accepted and current for 'Sewer Reticulation'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Electrical Reticulation",
                question_text="Is evidence accepted and current for 'Electrical Reticulation'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP22",
        name="Cost Planning and Financial Modelling",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Capex Estimate",
                question_text="Is evidence accepted and current for 'Capex Estimate'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Professional Fees",
                question_text="Is evidence accepted and current for 'Professional Fees'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Approval Costs",
                question_text="Is evidence accepted and current for 'Approval Costs'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Tenant Fit-Out Allowances",
                question_text="Is evidence accepted and current for 'Tenant Fit-Out Allowances'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Contingency",
                question_text="Is evidence accepted and current for 'Contingency'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Rental Income",
                question_text="Is evidence accepted and current for 'Rental Income'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
        ),
    ),
    SeedDomain(
        code="WP23",
        name="Capital Structuring and Funding Readiness",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Equity Contribution",
                question_text="Is evidence accepted and current for 'Equity Contribution'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Debt Funding",
                question_text="Is evidence accepted and current for 'Debt Funding'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Drawdown Plan",
                question_text="Is evidence accepted and current for 'Drawdown Plan'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Security Package",
                question_text="Is evidence accepted and current for 'Security Package'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Funder Due Diligence",
                question_text="Is evidence accepted and current for 'Funder Due Diligence'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Term Sheet",
                question_text="Is evidence accepted and current for 'Term Sheet'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP24",
        name="Procurement Strategy and Tender Documentation",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Procurement Route",
                question_text="Is evidence accepted and current for 'Procurement Route'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Tender Pack",
                question_text="Is evidence accepted and current for 'Tender Pack'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="BOQ",
                question_text="Is evidence accepted and current for 'BOQ'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Contract Conditions",
                question_text="Is evidence accepted and current for 'Contract Conditions'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Bid Evaluation",
                question_text="Is evidence accepted and current for 'Bid Evaluation'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Supplier Strategy",
                question_text="Is evidence accepted and current for 'Supplier Strategy'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
        ),
    ),
    SeedDomain(
        code="WP25",
        name="Contractor Due Diligence and Appointment",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Contractor Capacity",
                question_text="Is evidence accepted and current for 'Contractor Capacity'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Financial Strength",
                question_text="Is evidence accepted and current for 'Financial Strength'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Similar Project Experience",
                question_text="Is evidence accepted and current for 'Similar Project Experience'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="HSE Record",
                question_text="Is evidence accepted and current for 'HSE Record'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Quality Systems",
                question_text="Is evidence accepted and current for 'Quality Systems'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Programme Credibility",
                question_text="Is evidence accepted and current for 'Programme Credibility'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
        ),
    ),
    SeedDomain(
        code="WP26",
        name="Regulatory Permitting and Building Plan Approval",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Building Plans",
                question_text="Is evidence accepted and current for 'Building Plans'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Fire Approval",
                question_text="Is evidence accepted and current for 'Fire Approval'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Status + authority/reference + dates/conditions",
            ),
            SeedQuestion(
                control_objective="Health Approval",
                question_text="Is evidence accepted and current for 'Health Approval'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Status + authority/reference + dates/conditions",
            ),
            SeedQuestion(
                control_objective="Road Access Approval",
                question_text="Is evidence accepted and current for 'Road Access Approval'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Status + authority/reference + dates/conditions",
            ),
            SeedQuestion(
                control_objective="Water Connection",
                question_text="Is evidence accepted and current for 'Water Connection'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Sewer Connection",
                question_text="Is evidence accepted and current for 'Sewer Connection'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP27",
        name="Construction Mobilisation",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Site Handover",
                question_text="Is evidence accepted and current for 'Site Handover'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Site Camp",
                question_text="Is evidence accepted and current for 'Site Camp'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Survey Setting Out",
                question_text="Is evidence accepted and current for 'Survey Setting Out'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="HSE File",
                question_text="Is evidence accepted and current for 'HSE File'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Environmental Controls",
                question_text="Is evidence accepted and current for 'Environmental Controls'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Baseline Programme",
                question_text="Is evidence accepted and current for 'Baseline Programme'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
        ),
    ),
    SeedDomain(
        code="WP28",
        name="Civil Works, Earthworks and Access Construction",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Clearing and Grubbing",
                question_text="Is evidence accepted and current for 'Clearing and Grubbing'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Bulk Earthworks",
                question_text="Is evidence accepted and current for 'Bulk Earthworks'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Platforms",
                question_text="Is evidence accepted and current for 'Platforms'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Site Entrance Works",
                question_text="Is evidence accepted and current for 'Site Entrance Works'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Stormwater Structures",
                question_text="Is evidence accepted and current for 'Stormwater Structures'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Internal Roads",
                question_text="Is evidence accepted and current for 'Internal Roads'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP29",
        name="Building Shells and Services Installation",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Anchor Tenant Shell",
                question_text="Is evidence accepted and current for 'Anchor Tenant Shell'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
            SeedQuestion(
                control_objective="Line-Shop Shells",
                question_text="Is evidence accepted and current for 'Line-Shop Shells'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="QSR Shells",
                question_text="Is evidence accepted and current for 'QSR Shells'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Roofing",
                question_text="Is evidence accepted and current for 'Roofing'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Shopfronts",
                question_text="Is evidence accepted and current for 'Shopfronts'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Water Services",
                question_text="Is evidence accepted and current for 'Water Services'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP30",
        name="Tenant Fit-Out Coordination",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Anchor Tenant Fit-Out",
                question_text="Is evidence accepted and current for 'Anchor Tenant Fit-Out'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
            SeedQuestion(
                control_objective="Line-Shop Fit-Out",
                question_text="Is evidence accepted and current for 'Line-Shop Fit-Out'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Fast-Food Fit-Out",
                question_text="Is evidence accepted and current for 'Fast-Food Fit-Out'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Handover Dates",
                question_text="Is evidence accepted and current for 'Handover Dates'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Date / duration / schedule status",
            ),
            SeedQuestion(
                control_objective="Fit-Out Rules",
                question_text="Is evidence accepted and current for 'Fit-Out Rules'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Tenant Utilities",
                question_text="Is evidence accepted and current for 'Tenant Utilities'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
        ),
    ),
    SeedDomain(
        code="WP31",
        name="Quality Assurance, HSE and Compliance Control",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Quality Inspections",
                question_text="Is evidence accepted and current for 'Quality Inspections'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="HSE Audits",
                question_text="Is evidence accepted and current for 'HSE Audits'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Environmental Monitoring",
                question_text="Is evidence accepted and current for 'Environmental Monitoring'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Material Approvals",
                question_text="Is evidence accepted and current for 'Material Approvals'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Status + authority/reference + dates/conditions",
            ),
            SeedQuestion(
                control_objective="Variation Control",
                question_text="Is evidence accepted and current for 'Variation Control'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Payment Certification",
                question_text="Is evidence accepted and current for 'Payment Certification'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP32",
        name="Commissioning and Testing",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Electrical Testing",
                question_text="Is evidence accepted and current for 'Electrical Testing'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Water Pressure Testing",
                question_text="Is evidence accepted and current for 'Water Pressure Testing'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Fire System Testing",
                question_text="Is evidence accepted and current for 'Fire System Testing'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Stormwater Checks",
                question_text="Is evidence accepted and current for 'Stormwater Checks'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="HVAC Testing",
                question_text="Is evidence accepted and current for 'HVAC Testing'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="ICT Testing",
                question_text="Is evidence accepted and current for 'ICT Testing'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP33",
        name="Handover to Operators and Tenants",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Handover Manuals",
                question_text="Is evidence accepted and current for 'Handover Manuals'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="As-Built Drawings",
                question_text="Is evidence accepted and current for 'As-Built Drawings'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Warranty Register",
                question_text="Is evidence accepted and current for 'Warranty Register'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Tenant Certificates",
                question_text="Is evidence accepted and current for 'Tenant Certificates'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Status + authority/reference + dates/conditions",
            ),
            SeedQuestion(
                control_objective="Maintenance Plans",
                question_text="Is evidence accepted and current for 'Maintenance Plans'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Operator Training",
                question_text="Is evidence accepted and current for 'Operator Training'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP34",
        name="Operational Ramp-Up",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Soft Opening",
                question_text="Is evidence accepted and current for 'Soft Opening'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Anchor Tenant Opening",
                question_text="Is evidence accepted and current for 'Anchor Tenant Opening'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
            SeedQuestion(
                control_objective="Tenant Trading Readiness",
                question_text="Is evidence accepted and current for 'Tenant Trading Readiness'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
            SeedQuestion(
                control_objective="Traffic Management",
                question_text="Is evidence accepted and current for 'Traffic Management'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Customer Service",
                question_text="Is evidence accepted and current for 'Customer Service'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Operations Dashboard",
                question_text="Is evidence accepted and current for 'Operations Dashboard'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP35",
        name="Operations Management",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Property Management",
                question_text="Is evidence accepted and current for 'Property Management'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Lease Administration",
                question_text="Is evidence accepted and current for 'Lease Administration'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Tenant Relations",
                question_text="Is evidence accepted and current for 'Tenant Relations'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Linked party / engagement / due-diligence status",
            ),
            SeedQuestion(
                control_objective="Security Operations",
                question_text="Is evidence accepted and current for 'Security Operations'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Cleaning Operations",
                question_text="Is evidence accepted and current for 'Cleaning Operations'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Parking Control",
                question_text="Is evidence accepted and current for 'Parking Control'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP36",
        name="Maintenance Management",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="Preventive Maintenance",
                question_text="Is evidence accepted and current for 'Preventive Maintenance'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Reactive Maintenance",
                question_text="Is evidence accepted and current for 'Reactive Maintenance'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Roof and Gutters",
                question_text="Is evidence accepted and current for 'Roof and Gutters'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Electrical Systems",
                question_text="Is evidence accepted and current for 'Electrical Systems'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Plumbing Systems",
                question_text="Is evidence accepted and current for 'Plumbing Systems'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Fire Equipment",
                question_text="Is evidence accepted and current for 'Fire Equipment'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
        ),
    ),
    SeedDomain(
        code="WP37",
        name="Sustainable Impact, Performance Monitoring and Future Expansion",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            SeedQuestion(
                control_objective="ESG Reporting",
                question_text="Is evidence accepted and current for 'ESG Reporting'?",
                is_critical_control=True,
                pass_threshold=5.0,
                evidence_type_hint="Document / version / review and approval status",
            ),
            SeedQuestion(
                control_objective="Job Creation",
                question_text="Is evidence accepted and current for 'Job Creation'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Local Procurement",
                question_text="Is evidence accepted and current for 'Local Procurement'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Community Benefit",
                question_text="Is evidence accepted and current for 'Community Benefit'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Structured value + evidence + status",
            ),
            SeedQuestion(
                control_objective="Energy Efficiency",
                question_text="Is evidence accepted and current for 'Energy Efficiency'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
            SeedQuestion(
                control_objective="Water Performance",
                question_text="Is evidence accepted and current for 'Water Performance'?",
                is_critical_control=False,
                pass_threshold=5.0,
                evidence_type_hint="Numeric / percentage / currency with unit and period",
            ),
        ),
    ),
)


async def seed() -> None:
    async with async_session_factory() as session:
        existing = await session.execute(
            select(OpbohFrameworkVersion).where(
                OpbohFrameworkVersion.version_label == REAL_VERSION_LABEL
            )
        )
        if existing.scalars().first() is not None:
            print(f"Real OPBOH catalogue {REAL_VERSION_LABEL!r} already seeded.")
            return

        # Get-or-create rather than assuming migration 0003 already
        # registered OPBOH — same reasoning seed_opboh_catalogue.py's own
        # get-or-create already documents.
        framework_result = await session.execute(
            select(Framework).where(Framework.code == _OPBOH_FRAMEWORK_CODE)
        )
        framework = framework_result.scalars().first()
        if framework is None:
            framework = Framework(
                id=uuid.uuid4(),
                code=_OPBOH_FRAMEWORK_CODE,
                name="Organisational and Project Bill of Health",
                description="IPAC rule 1001-008-01 — FW-OPBOH-001…015. See models/opboh.py.",
                is_active=True,
                created_by=SEED_ACTOR,
                updated_by=SEED_ACTOR,
            )
            session.add(framework)
            await session.flush()

        # Only one version should be active for new assessments at a time
        # (create_assessment's "no active version" check in
        # api/routes/opboh.py) — deactivate the illustrative one rather
        # than deleting it, exactly as its own docstring already promised.
        illustrative_result = await session.execute(
            select(OpbohFrameworkVersion).where(
                OpbohFrameworkVersion.version_label == ILLUSTRATIVE_VERSION_LABEL,
                OpbohFrameworkVersion.is_active.is_(True),
            )
        )
        illustrative = illustrative_result.scalars().first()
        if illustrative is not None:
            illustrative.is_active = False
            illustrative.updated_by = SEED_ACTOR

        version = OpbohFrameworkVersion(
            id=uuid.uuid4(),
            framework_id=framework.id,
            version_label=REAL_VERSION_LABEL,
            effective_from=date.today(),
            is_active=True,
            created_by=SEED_ACTOR,
            updated_by=SEED_ACTOR,
        )
        session.add(version)
        await session.flush()

        question_count = 0
        for sequence, seed_domain in enumerate(CATALOGUE):
            domain = OpbohDomain(
                id=uuid.uuid4(),
                framework_version_id=version.id,
                code=seed_domain.code,
                name=seed_domain.name,
                sequence=sequence,
                weight=seed_domain.weight,
                min_score_threshold=seed_domain.min_score_threshold,
            )
            session.add(domain)
            await session.flush()

            for q_sequence, seed_question in enumerate(seed_domain.questions):
                session.add(
                    OpbohQuestion(
                        id=uuid.uuid4(),
                        domain_id=domain.id,
                        control_objective=seed_question.control_objective,
                        question_text=seed_question.question_text,
                        sequence=q_sequence,
                        is_critical_control=seed_question.is_critical_control,
                        pass_threshold=seed_question.pass_threshold,
                        evidence_required=True,
                        evidence_type_hint=seed_question.evidence_type_hint,
                    )
                )
                question_count += 1

        await session.commit()
        print(
            f"Seeded real OPBOH catalogue {REAL_VERSION_LABEL!r}: "
            f"{len(CATALOGUE)} domains, {question_count} questions. "
            f"Illustrative catalogue deactivated: {illustrative is not None}."
        )


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
