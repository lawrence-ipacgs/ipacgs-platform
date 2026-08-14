"""Import every model here so Alembic's autogenerate (and `Base.metadata`
generally) sees the full schema from a single import of this package."""

from ipacgs.models.audit_event import AuditAction, AuditEvent
from ipacgs.models.base import Base
from ipacgs.models.evidence import EvidenceDocument, EvidenceStatus
from ipacgs.models.framework import Framework, FrameworkApplicabilityRule, FrameworkVersion
from ipacgs.models.opboh import (
    FindingSeverity,
    FindingStatus,
    OpbohAssessment,
    OpbohAssessmentStatus,
    OpbohDomain,
    OpbohFinding,
    OpbohFrameworkVersion,
    OpbohQuestion,
    OpbohResponse,
    OpbohResponseEvidence,
)
from ipacgs.models.organisation import Organisation, OrganisationDuplicateCheck
from ipacgs.models.person import Person
from ipacgs.models.project import (
    Project,
    ProjectStatus,
    Stage,
    StageGateDecision,
    StageGateDecisionKind,
)
from ipacgs.models.tenant import Tenant, TenantStatus

__all__ = [
    "AuditAction",
    "AuditEvent",
    "Base",
    "EvidenceDocument",
    "EvidenceStatus",
    "FindingSeverity",
    "FindingStatus",
    "Framework",
    "FrameworkApplicabilityRule",
    "FrameworkVersion",
    "OpbohAssessment",
    "OpbohAssessmentStatus",
    "OpbohDomain",
    "OpbohFinding",
    "OpbohFrameworkVersion",
    "OpbohQuestion",
    "OpbohResponse",
    "OpbohResponseEvidence",
    "Organisation",
    "OrganisationDuplicateCheck",
    "Person",
    "Project",
    "ProjectStatus",
    "Stage",
    "StageGateDecision",
    "StageGateDecisionKind",
    "Tenant",
    "TenantStatus",
]
