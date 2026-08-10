"""Natural persons who can hold a role against a project — sponsors,
assessors, independent reviewers, gate authorities. `FR-MDM-001`.

`entra_object_id` links a Person to the Entra ID identity that authenticates
as them, when they have platform access (not every Person does — a
beneficial owner named in a disclosure may never log in). This is the join
point between `core/security.py`'s `CurrentUser.object_id` and a row someone
can actually be held accountable against — including for
`enforce_maker_checker`, which compares object IDs, not Person rows directly,
precisely so that check works before this table is even queried.
"""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ipacgs.models.base import AuditedMixin, Base, TenantScopedMixin


class Person(Base, TenantScopedMixin, AuditedMixin):
    __tablename__ = "people"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))

    primary_organisation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisations.id")
    )

    entra_object_id: Mapped[str | None] = mapped_column(
        String(36),
        unique=True,
        doc="Entra ID 'oid' claim — set once this person has platform access. "
        "Null for people who exist only as records (e.g. a disclosed "
        "beneficial owner who never signs in).",
    )
