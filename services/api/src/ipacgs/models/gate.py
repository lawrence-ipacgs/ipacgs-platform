"""Epic 6 — Gate Engine (Gate 0 & Gate 1).

Ticket references throughout are GATE-0[0-1]-NNN from the architecture
document's Section 4. Two honesty notes worth reading before the rest:

1. `Gate` is configuration (a DB table), not a hardcoded enum — same
   reasoning as `Stage`/`Framework`: KMI's real gate list (Gate 0-10 per
   the SRS) isn't confirmed source material yet. Outcomes are NOT
   similarly configurable, though — they're hardcoded to proceed/hold
   (`GateVoteOutcome`, `GateDecisionStatus`) because the architecture
   document's own evidence-gate diagram states every gate in S1-S21/
   Gate 0-10 runs the identical two-outcome shape ("Every gate ... runs
   this same two-check shape") — that's matching what the source
   material itself says is universal, not a scope cut dressed up as one.
2. `GateCertificate`'s "signatures" (GATE-0[0-1]-007) means the recorded
   identity of every authorized voter behind a decision (`GateVote`), not
   a cryptographic signature — there's no PKI/HSM in this platform for a
   voter to actually sign with yet. `content_hash` is a real SHA-256 over
   a canonical snapshot of the decision (services/gate_engine.py), which
   does make the certificate tamper-evident — any edit to the underlying
   rows changes the hash — just not signed in the sense the ticket's
   wording might otherwise suggest.

Non-bypassability (GATE-0[0-1]-006) isn't implemented here at all — it's
enforced in `services/stage_engine.advance_stage`, which now refuses to
move a project past a stage that has an un-PROCEEDed gate attached. A
"blocks irreversible action" rule only means something if it's wired
into the one irreversible action this platform actually has.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ipacgs.models.base import AuditedMixin, Base, TenantScopedMixin

_VALUES_CALLABLE = lambda enum_cls: [e.value for e in enum_cls]  # noqa: E731


class Gate(Base, AuditedMixin):
    """Not tenant-scoped — same reasoning as `Stage`/`Framework`: the gate
    definitions themselves are shared platform configuration."""

    __tablename__ = "gates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    # GATE-0[0-1]-001 "trigger" — which stage's completion opens this
    # gate. Looked up by exact stage_id equality everywhere it's used
    # (services/stage_engine.py, services/gate_engine.py), deliberately —
    # never by an ambient "find the likely/lowest matching row" scan. The
    # last three CI failures in this repo all came from exactly that
    # pattern (a query with no fixed reference point, picking up whatever
    # row an unrelated test happened to leave committed); an exact match
    # on a randomly-generated stage id can't repeat it.
    trigger_stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stages.id"), nullable=False
    )

    # GATE-0[0-1]-004 "authority / quorum" — how many distinct proceed
    # votes are needed to pass. There's no real Entra ID role list yet
    # (see infra/scripts/create-app-registrations.sh, still not run), so
    # "authority" for now just means "a distinct person voted" — role-
    # gating who's eligible to vote at all is a follow-up once RBAC
    # exists, not attempted here.
    required_quorum: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class GateVoteOutcome(StrEnum):
    PROCEED = "proceed"
    HOLD = "hold"


class GateDecisionStatus(StrEnum):
    PENDING = "pending"
    PROCEED = "proceed"
    HOLD = "hold"
    SUSPENDED = "suspended"


class GateDecision(Base, TenantScopedMixin, AuditedMixin):
    __tablename__ = "gate_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    gate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gates.id"), nullable=False
    )
    status: Mapped[GateDecisionStatus] = mapped_column(
        Enum(GateDecisionStatus, name="gate_decision_status", values_callable=_VALUES_CALLABLE),
        nullable=False,
        default=GateDecisionStatus.PENDING,
    )
    opened_by: Mapped[str] = mapped_column(String(36), nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # GATE-0[0-1]-009 — reopen/suspend on evidence withdrawal or fraud
    # indicator. Only ever applies to a PROCEED decision (services/
    # gate_engine.py enforces this) — the certificate already issued for
    # it is deliberately left in place, not deleted, as the historical
    # record that a PROCEED decision genuinely existed before it was
    # suspended.
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_by: Mapped[str | None] = mapped_column(String(36))
    suspension_reason: Mapped[str | None] = mapped_column(Text)

    votes: Mapped[list["GateVote"]] = relationship(
        back_populates="decision", order_by="GateVote.voted_at"
    )
    certificate: Mapped["GateCertificate | None"] = relationship(
        back_populates="decision", uselist=False
    )


class GateVote(Base):
    """No tenant/audit mixins — a vote is an immutable event scoped
    entirely by its parent decision, same reasoning as `StageGateDecision`
    not carrying `updated_at`/`updated_by`."""

    __tablename__ = "gate_votes"
    __table_args__ = (
        UniqueConstraint("gate_decision_id", "voter", name="uq_gate_vote_one_per_voter"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gate_decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gate_decisions.id"), nullable=False
    )
    decision: Mapped["GateDecision"] = relationship(back_populates="votes")
    voter: Mapped[str] = mapped_column(String(36), nullable=False)
    outcome: Mapped[GateVoteOutcome] = mapped_column(
        Enum(GateVoteOutcome, name="gate_vote_outcome", values_callable=_VALUES_CALLABLE),
        nullable=False,
    )
    voted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class GateCertificate(Base):
    """See the module docstring re: what "signatures" means here."""

    __tablename__ = "gate_certificates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gate_decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gate_decisions.id"), nullable=False, unique=True
    )
    decision: Mapped["GateDecision"] = relationship(back_populates="certificate")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
