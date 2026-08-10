"""Import every model here so Alembic's autogenerate (and `Base.metadata`
generally) sees the full schema from a single import of this package."""

from ipacgs.models.audit_event import AuditAction, AuditEvent
from ipacgs.models.base import Base
from ipacgs.models.organisation import Organisation, OrganisationDuplicateCheck
from ipacgs.models.person import Person
from ipacgs.models.tenant import Tenant, TenantStatus

__all__ = [
    "AuditAction",
    "AuditEvent",
    "Base",
    "Organisation",
    "OrganisationDuplicateCheck",
    "Person",
    "Tenant",
    "TenantStatus",
]
