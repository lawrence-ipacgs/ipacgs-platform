"""Bridges the database to `services/opboh_scoring.py`'s pure functions.

Kept separate from the scoring engine itself on purpose — the engine stays
importable and unit-testable with zero DB dependency (see its own
docstring), and this module is the one place that knows how to turn
`OpbohAssessment`/`OpbohResponse`/`OpbohQuestion`/`OpbohDomain` rows into
the plain dataclasses it operates on.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ipacgs.models.opboh import OpbohAssessment, OpbohDomain, OpbohResponse
from ipacgs.services.opboh_scoring import (
    AssessmentResult,
    DomainInput,
    QuestionScore,
    score_assessment,
)


async def compute_assessment_score(
    session: AsyncSession, assessment: OpbohAssessment
) -> AssessmentResult:
    """Loads every domain in the assessment's framework version, every
    question in each domain, and whatever response exists so far for each
    question (there may be none yet — unanswered questions score as such,
    not as an error), then hands it all to the pure scoring engine."""
    domains_result = await session.execute(
        select(OpbohDomain)
        .options(selectinload(OpbohDomain.questions))
        .where(OpbohDomain.framework_version_id == assessment.framework_version_id)
        .order_by(OpbohDomain.sequence)
    )
    domains = domains_result.scalars().unique().all()

    responses_result = await session.execute(
        select(OpbohResponse).where(OpbohResponse.assessment_id == assessment.id)
    )
    responses_by_question: dict[uuid.UUID, OpbohResponse] = {
        r.question_id: r for r in responses_result.scalars().all()
    }

    domain_inputs: list[DomainInput] = []
    for domain in domains:
        question_scores: list[QuestionScore] = []
        # domain.questions is already ordered — the relationship declares
        # order_by="OpbohQuestion.sequence" (models/opboh.py).
        for question in domain.questions:
            response = responses_by_question.get(question.id)
            question_scores.append(
                QuestionScore(
                    question_id=str(question.id),
                    control_objective=question.control_objective,
                    is_critical_control=question.is_critical_control,
                    pass_threshold=question.pass_threshold,
                    score=response.score if response else None,
                    evidence_sufficient=response.evidence_sufficient if response else None,
                )
            )
        domain_inputs.append(
            DomainInput(
                domain_id=str(domain.id),
                name=domain.name,
                weight=domain.weight,
                min_score_threshold=domain.min_score_threshold,
                questions=tuple(question_scores),
            )
        )

    return score_assessment(tuple(domain_inputs))
