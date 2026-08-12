"""State-graph and segregation-of-duties checks in the OPBOH workflow.
No database needed: every check here (`_require_legal`, `_require_distinct`,
the FW-OPBOH-015 fatal-flaw block) raises before `begin_assessment` /
`independently_review` / `decide` ever touch the session — so the failure
paths are testable the same way test_security.py's maker-checker tests are.
Success paths (an allowed transition that actually persists) need a real
session and belong with the DB-touching test suite instead.
"""

import uuid
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.core.security import MakerCheckerViolation
from ipacgs.models.opboh import OpbohAssessment, OpbohAssessmentStatus
from ipacgs.services.opboh_workflow import (
    IllegalTransition,
    begin_assessment,
    decide,
    independently_review,
)

_NO_SESSION = cast(AsyncSession, None)


def _assessment(
    status: OpbohAssessmentStatus,
    *,
    prepared_by: str = "preparer",
    assessed_by: str | None = None,
    reviewed_by: str | None = None,
) -> OpbohAssessment:
    return OpbohAssessment(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        framework_version_id=uuid.uuid4(),
        organisation_id=uuid.uuid4(),
        status=status,
        prepared_by=prepared_by,
        assessed_by=assessed_by,
        reviewed_by=reviewed_by,
        created_by=prepared_by,
        updated_by=prepared_by,
    )


async def test_begin_assessment_rejects_illegal_source_state() -> None:
    assessment = _assessment(OpbohAssessmentStatus.DRAFT)  # can't jump straight to under_assessment
    with pytest.raises(IllegalTransition):
        await begin_assessment(
            _NO_SESSION, assessment, actor="assessor", correlation_id=uuid.uuid4()
        )


async def test_begin_assessment_rejects_the_preparer_as_assessor() -> None:
    assessment = _assessment(OpbohAssessmentStatus.SUBMITTED, prepared_by="alice")
    with pytest.raises(MakerCheckerViolation):
        await begin_assessment(_NO_SESSION, assessment, actor="alice", correlation_id=uuid.uuid4())


async def test_independently_review_rejects_the_assessor_as_reviewer() -> None:
    assessment = _assessment(
        OpbohAssessmentStatus.UNDER_ASSESSMENT, prepared_by="alice", assessed_by="bob"
    )
    with pytest.raises(MakerCheckerViolation):
        await independently_review(
            _NO_SESSION, assessment, actor="bob", correlation_id=uuid.uuid4()
        )


async def test_independently_review_rejects_the_preparer_as_reviewer_too() -> None:
    """Independence means neither the preparer NOR the assessor — not just
    "not the assessor"."""
    assessment = _assessment(
        OpbohAssessmentStatus.UNDER_ASSESSMENT, prepared_by="alice", assessed_by="bob"
    )
    with pytest.raises(MakerCheckerViolation):
        await independently_review(
            _NO_SESSION, assessment, actor="alice", correlation_id=uuid.uuid4()
        )


async def test_independently_review_accepts_a_genuinely_new_person() -> None:
    """Confirms the check is discriminating, not just always-raise —
    reaches the point where it would touch the session, which is where we
    stop for a pure-logic test."""
    assessment = _assessment(
        OpbohAssessmentStatus.UNDER_ASSESSMENT, prepared_by="alice", assessed_by="bob"
    )
    with pytest.raises(AttributeError):
        # NoneType session — proves _require_legal/_require_distinct both
        # passed and execution reached record_audit_event(), not that the
        # transition "succeeded" (it can't, with no real session).
        await independently_review(
            _NO_SESSION, assessment, actor="carol", correlation_id=uuid.uuid4()
        )


async def test_decide_rejects_accept_with_an_unresolved_critical_failure() -> None:
    """FW-OPBOH-015 — the fatal-flaw block. This is the mechanism, not a
    policy statement: ACCEPTED is simply not a reachable state here."""
    assessment = _assessment(
        OpbohAssessmentStatus.INDEPENDENTLY_REVIEWED,
        prepared_by="alice",
        assessed_by="bob",
        reviewed_by="carol",
    )
    with pytest.raises(IllegalTransition):
        await decide(
            _NO_SESSION,
            assessment,
            decision=OpbohAssessmentStatus.ACCEPTED,
            actor="dave",
            has_critical_failure=True,
            overall_score=0.95,  # a high score does not rescue this
            decision_summary=None,
            correlation_id=uuid.uuid4(),
        )


async def test_decide_allows_conditional_accept_with_a_critical_failure() -> None:
    assessment = _assessment(
        OpbohAssessmentStatus.INDEPENDENTLY_REVIEWED,
        prepared_by="alice",
        assessed_by="bob",
        reviewed_by="carol",
    )
    with pytest.raises(AttributeError):  # reaches record_audit_event — see note above
        await decide(
            _NO_SESSION,
            assessment,
            decision=OpbohAssessmentStatus.CONDITIONALLY_ACCEPTED,
            actor="dave",
            has_critical_failure=True,
            overall_score=0.95,
            decision_summary="Pending remediation of X.",
            correlation_id=uuid.uuid4(),
        )


async def test_decide_rejects_the_reviewer_as_approver() -> None:
    assessment = _assessment(
        OpbohAssessmentStatus.INDEPENDENTLY_REVIEWED,
        prepared_by="alice",
        assessed_by="bob",
        reviewed_by="carol",
    )
    with pytest.raises(MakerCheckerViolation):
        await decide(
            _NO_SESSION,
            assessment,
            decision=OpbohAssessmentStatus.REJECTED,
            actor="carol",
            has_critical_failure=False,
            overall_score=0.4,
            decision_summary=None,
            correlation_id=uuid.uuid4(),
        )
