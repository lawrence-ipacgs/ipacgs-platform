"""Evidence review's Human Review Gate (Figure 2) — the failure paths are
pure logic, same pattern as test_opboh_workflow.py: both checks raise
before accept_evidence/reject_evidence ever touch the session.
"""

import uuid
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.core.security import MakerCheckerViolation
from ipacgs.models.evidence import EvidenceDocument, EvidenceStatus
from ipacgs.services.evidence import IllegalEvidenceTransition, accept_evidence, reject_evidence

_NO_SESSION = cast(AsyncSession, None)


def _evidence(status: EvidenceStatus, *, submitted_by: str | None = "alice") -> EvidenceDocument:
    return EvidenceDocument(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        title="Certificate of Incorporation",
        status=status,
        submitted_by=submitted_by,
        created_by=submitted_by or "system",
        updated_by=submitted_by or "system",
    )


async def test_cannot_review_evidence_that_was_never_submitted() -> None:
    evidence = _evidence(EvidenceStatus.REQUESTED, submitted_by=None)
    with pytest.raises(IllegalEvidenceTransition):
        await accept_evidence(_NO_SESSION, evidence, reviewer="bob", correlation_id=uuid.uuid4())


async def test_submitter_cannot_accept_their_own_evidence() -> None:
    evidence = _evidence(EvidenceStatus.SUBMITTED, submitted_by="alice")
    with pytest.raises(MakerCheckerViolation):
        await accept_evidence(_NO_SESSION, evidence, reviewer="alice", correlation_id=uuid.uuid4())


async def test_submitter_cannot_reject_their_own_evidence_either() -> None:
    """The gate applies to both outcomes of review, not just the favourable
    one — self-rejection would be just as much a broken control."""
    evidence = _evidence(EvidenceStatus.SUBMITTED, submitted_by="alice")
    with pytest.raises(MakerCheckerViolation):
        await reject_evidence(
            _NO_SESSION, evidence, reviewer="alice", reason="test", correlation_id=uuid.uuid4()
        )


async def test_a_different_reviewer_clears_both_checks() -> None:
    evidence = _evidence(EvidenceStatus.SUBMITTED, submitted_by="alice")
    with pytest.raises(
        AttributeError
    ):  # reaches record_audit_event with no real session — see note above
        await accept_evidence(_NO_SESSION, evidence, reviewer="bob", correlation_id=uuid.uuid4())
