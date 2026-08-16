"""The Bill-of-Health report — `FW-OPBOH-010` (the report) and
`FW-OPBOH-014` (the baseline opinion it carries), the two tickets left open
on Epic 3's own list after everything else in this package landed.

Composes what already exists rather than computing anything new:
`opboh_query.compute_assessment_score` for the numbers,
`opboh_scoring.baseline_opinion` for the system's own deterministic reading
of them, and this assessment's own still-unresolved findings — the same
"what needs attention" a human reading the report would otherwise have to
gather from three separate calls.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ipacgs.models.opboh import FindingStatus, OpbohAssessment, OpbohFinding
from ipacgs.services.opboh_query import compute_assessment_score
from ipacgs.services.opboh_scoring import AssessmentResult, BaselineOpinion, baseline_opinion

# Deliberately wider than stage_engine._OPEN_FINDING_STATES (OPEN,
# IN_PROGRESS only, since that set exists to answer "does this block a
# stage advance"). An ESCALATED finding is still unresolved by definition,
# and a report whose whole job is "what still needs attention on this
# assessment" silently dropping escalated findings would be worse than not
# filtering at all.
_UNRESOLVED_FINDING_STATES = frozenset(
    {FindingStatus.OPEN, FindingStatus.IN_PROGRESS, FindingStatus.ESCALATED}
)


@dataclass(frozen=True)
class BillOfHealthReport:
    assessment_id: uuid.UUID
    organisation_id: uuid.UUID
    project_id: uuid.UUID | None
    status: str
    prepared_by: str
    assessed_by: str | None
    reviewed_by: str | None
    approved_by: str | None
    decision_summary: str | None
    score: AssessmentResult
    opinion: BaselineOpinion
    open_findings: tuple[OpbohFinding, ...]


async def build_bill_of_health(
    session: AsyncSession, assessment: OpbohAssessment
) -> BillOfHealthReport:
    score = await compute_assessment_score(session, assessment)
    opinion = baseline_opinion(score)

    findings_result = await session.execute(
        select(OpbohFinding).where(
            OpbohFinding.assessment_id == assessment.id,
            OpbohFinding.status.in_(_UNRESOLVED_FINDING_STATES),
        )
    )
    open_findings = tuple(findings_result.scalars().all())

    return BillOfHealthReport(
        assessment_id=assessment.id,
        organisation_id=assessment.organisation_id,
        project_id=assessment.project_id,
        status=assessment.status.value,
        prepared_by=assessment.prepared_by,
        assessed_by=assessment.assessed_by,
        reviewed_by=assessment.reviewed_by,
        approved_by=assessment.approved_by,
        decision_summary=assessment.decision_summary,
        score=score,
        opinion=opinion,
        open_findings=open_findings,
    )
