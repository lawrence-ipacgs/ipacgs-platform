"""The scoring engine — `FW-OPBOH-005`: "domain scores, critical-control
failures... without averaging concealment." Also carries `baseline_opinion`
(`FW-OPBOH-014`) — the deterministic prose reading of an `AssessmentResult`
that `services/opboh_report.py`'s bill-of-health report (`FW-OPBOH-010`)
is built around.

Deliberately pure functions over plain dataclasses, not SQLAlchemy models —
this is the one part of Epic 3 that most benefits from being fully unit-
testable with no database at all, the same way `core/security.py`'s
maker-checker check is. The caller (the workflow layer, or eventually an API
route) is responsible for mapping ORM rows into `QuestionScore` /
`DomainInput` before calling in, and mapping the result back out.

The "no averaging concealment" principle, concretely: a domain's numeric
score is always reported, but it is never the only thing that decides
whether OPBOH is satisfied. Any critical-control failure is surfaced
explicitly, by name, alongside the number — a domain that averages to 4.7
because nine easy questions passed and one critical one failed still shows
that failure, not just the 4.7.

Real formula, sourced from an OPBOH Full-Cycle Assessment Module v1.1
overview KMI shared (`docs/IMG-20260814-WA0011.jpg` — a summary infographic,
not the full question bank):

    Assurance Score (0-100) = Weighted Score Achieved (0-100, i.e. the
    weighted domain average rescaled from 0-5) x Evidence Sufficiency
    Factor (0.5-1.0)

banded >=80 Green/Proceed, 60-79 Amber/Proceed with Conditions, <60 Red/Do
Not Proceed — with any critical-control failure forcing an automatic Red
regardless of the number, which is this module's existing "no averaging
concealment" rule, now backed by the real spec rather than just this
codebase's own principle. What the source material does NOT specify, and
this module therefore decides for itself (documented at each site below):
how a NOT_APPLICABLE response affects scoring, what happens when a
response's evidence factor hasn't been set yet, and how per-response
evidence factors aggregate into one assessment-level figure.
"""

from dataclasses import dataclass
from enum import StrEnum

MAX_RESPONSE_SCORE = 5.0
EVIDENCE_FACTOR_FLOOR = 0.5
ASSURANCE_GREEN_THRESHOLD = 80.0
ASSURANCE_AMBER_THRESHOLD = 60.0


class ResponseValue(StrEnum):
    """Mirrors `models.opboh.OpbohResponseValue` — kept as this module's own
    enum rather than importing the ORM one, same reasoning as the rest of
    this file staying free of any database dependency."""

    YES = "yes"
    NO = "no"
    NOT_APPLICABLE = "not_applicable"


class RagBand(StrEnum):
    RED = "red"
    AMBER = "amber"
    GREEN = "green"


@dataclass(frozen=True)
class QuestionScore:
    """One answered question, already reduced to what scoring needs."""

    question_id: str
    control_objective: str
    is_critical_control: bool
    pass_threshold: float
    response_value: ResponseValue | None  # None = unanswered
    score: float | None  # 0-5. None = unanswered
    evidence_sufficiency_factor: float | None  # 0.5-1.0. None = not yet reviewed


@dataclass(frozen=True)
class DomainInput:
    domain_id: str
    name: str
    weight: float
    min_score_threshold: float
    questions: tuple[QuestionScore, ...]


@dataclass(frozen=True)
class CriticalFailure:
    question_id: str
    control_objective: str
    reason: str


@dataclass(frozen=True)
class DomainResult:
    domain_id: str
    name: str
    score: float
    meets_threshold: bool
    critical_failures: tuple[CriticalFailure, ...]
    unanswered_count: int


@dataclass(frozen=True)
class AssessmentResult:
    overall_score: float  # 0-5, weighted across domains — same scale as a single response
    evidence_sufficiency_factor: float  # 0.5-1.0, aggregated across every answered question
    assurance_score: float  # 0-100 — the real, formal figure. See module docstring.
    domain_results: tuple[DomainResult, ...]
    critical_failures: tuple[CriticalFailure, ...]

    @property
    def has_critical_failure(self) -> bool:
        return len(self.critical_failures) > 0

    @property
    def all_domains_meet_threshold(self) -> bool:
        return all(d.meets_threshold for d in self.domain_results)

    @property
    def is_clean(self) -> bool:
        """True only if there's nothing standing between this assessment
        and an unconditional ACCEPTED — no critical failures, and every
        domain clears its own floor. Doesn't mean it necessarily gets
        accepted; that's still a human decision (see services/opboh.py) —
        this just says whether the numbers alone would block it."""
        return not self.has_critical_failure and self.all_domains_meet_threshold

    @property
    def rag(self) -> RagBand:
        """The real Assurance Score banding: any critical failure is an
        automatic Red regardless of the number (this module's "no averaging
        concealment" rule, now backed by the real spec), otherwise
        >=80 Green, 60-79 Amber, <60 Red."""
        if self.has_critical_failure:
            return RagBand.RED
        if self.assurance_score >= ASSURANCE_GREEN_THRESHOLD:
            return RagBand.GREEN
        if self.assurance_score >= ASSURANCE_AMBER_THRESHOLD:
            return RagBand.AMBER
        return RagBand.RED


def _question_failure_reason(q: QuestionScore) -> str | None:
    if q.response_value is None or q.score is None:
        return "unanswered"
    if q.response_value == ResponseValue.NOT_APPLICABLE:
        # Not specified by the source material either way — documented
        # interpretation: a critical control marked N/A is excluded from
        # scoring like any other N/A response, not treated as a failure.
        # This module doesn't currently ask for a justification when a
        # critical control is marked N/A; that's a real gap if KMI's real
        # workflow expects one.
        return None
    factor = q.evidence_sufficiency_factor
    if factor is None or factor <= EVIDENCE_FACTOR_FLOOR:
        return (
            "evidence insufficient"
            if factor is None
            else f"evidence sufficiency factor {factor:.2f} at or below the floor "
            f"({EVIDENCE_FACTOR_FLOOR})"
        )
    if q.score < q.pass_threshold:
        return f"score {q.score:.1f} below pass threshold {q.pass_threshold:.1f}"
    return None


def _scoreable(q: QuestionScore) -> bool:
    """Answered and applicable — NOT_APPLICABLE responses are excluded from
    both the domain average and the evidence-factor aggregate entirely,
    same documented interpretation as `_question_failure_reason`."""
    return q.score is not None and q.response_value != ResponseValue.NOT_APPLICABLE


def score_domain(domain: DomainInput) -> DomainResult:
    answered = [q for q in domain.questions if _scoreable(q)]
    unanswered_count = len(
        [q for q in domain.questions if q.response_value != ResponseValue.NOT_APPLICABLE]
    ) - len(answered)

    domain_score = (
        (sum(q.score for q in answered if q.score is not None) / len(answered)) if answered else 0.0
    )

    failures: list[CriticalFailure] = []
    for q in domain.questions:
        if not q.is_critical_control:
            continue
        reason = _question_failure_reason(q)
        if reason is not None:
            failures.append(
                CriticalFailure(
                    question_id=q.question_id, control_objective=q.control_objective, reason=reason
                )
            )

    return DomainResult(
        domain_id=domain.domain_id,
        name=domain.name,
        score=domain_score,
        # A critical failure fails the domain outright, regardless of the
        # numeric score — this is the "no averaging concealment" rule made
        # concrete: meets_threshold can be False even at the top score.
        meets_threshold=(domain_score >= domain.min_score_threshold) and not failures,
        critical_failures=tuple(failures),
        unanswered_count=unanswered_count,
    )


def _evidence_sufficiency_factor(domains: tuple[DomainInput, ...]) -> float:
    """Assessment-level aggregate: the mean of every answered, applicable
    question's own evidence_sufficiency_factor, substituting the floor
    (0.5) for an answered question whose evidence hasn't been reviewed yet
    — not specified by the source material, but consistent with this
    module's existing default-to-conservative pattern (an unanswered
    question already scores the domain as if it contributed 0, not as if
    it were simply excluded). Defaults to 1.0 (no penalty) only when there
    is nothing answered anywhere to aggregate — with overall_score also 0
    in that case, the resulting assurance_score is 0 either way."""
    # `or` is safe here (not just `is not None`): every real value in this
    # field's valid range (0.5-1.0) is truthy, so the only case `or` can
    # substitute the floor for is the actual None case being handled.
    factors = [
        q.evidence_sufficiency_factor or EVIDENCE_FACTOR_FLOOR
        for d in domains
        for q in d.questions
        if _scoreable(q)
    ]
    return (sum(factors) / len(factors)) if factors else 1.0


def score_assessment(domains: tuple[DomainInput, ...]) -> AssessmentResult:
    if not domains:
        return AssessmentResult(
            overall_score=0.0,
            evidence_sufficiency_factor=1.0,
            assurance_score=0.0,
            domain_results=(),
            critical_failures=(),
        )

    domain_results = tuple(score_domain(d) for d in domains)

    total_weight = sum(d.weight for d in domains)
    overall_score = (
        sum(dr.score * d.weight for dr, d in zip(domain_results, domains, strict=True))
        / total_weight
        if total_weight > 0
        else 0.0
    )

    evidence_factor = _evidence_sufficiency_factor(domains)
    weighted_score_pct = (overall_score / MAX_RESPONSE_SCORE) * 100
    assurance_score = weighted_score_pct * evidence_factor

    all_failures = tuple(f for dr in domain_results for f in dr.critical_failures)

    return AssessmentResult(
        overall_score=overall_score,
        evidence_sufficiency_factor=evidence_factor,
        assurance_score=assurance_score,
        domain_results=domain_results,
        critical_failures=all_failures,
    )


@dataclass(frozen=True)
class BaselineOpinion:
    """`FW-OPBOH-014` — the bill-of-health report's baseline opinion: the
    system's own reading of `AssessmentResult` alone, independent of
    whatever a human approver ultimately decides
    (`opboh_workflow.decide`). The report (`services/opboh_report.py`)
    shows this next to the actual recorded decision so a reader can see
    whether the two agree, rather than only ever seeing whichever one was
    recorded last."""

    rag: RagBand
    headline: str
    narrative: str
    recommendation: str


_RECOMMENDATION_BY_RAG: dict[RagBand, str] = {
    RagBand.GREEN: "Proceed",
    RagBand.AMBER: "Proceed with Conditions",
    RagBand.RED: "Do Not Proceed",
}


def baseline_opinion(result: AssessmentResult) -> BaselineOpinion:
    """Deterministic, not generative — every word here traces back to a
    field already on `result`, the same "no averaging concealment"
    principle applied to prose instead of a number. A critical failure is
    named explicitly rather than folded into "some issues were found"."""
    recommendation = _RECOMMENDATION_BY_RAG[result.rag]
    headline = f"{result.rag.value.capitalize()} — {recommendation}"

    if result.has_critical_failure:
        objectives = ", ".join(f.control_objective for f in result.critical_failures)
        narrative = (
            f"Automatic Red: {len(result.critical_failures)} unresolved critical-control "
            f"failure(s) — {objectives}. This stands regardless of the "
            f"{result.assurance_score:.1f}/100 assurance score; no averaging conceals it."
        )
    elif not result.all_domains_meet_threshold:
        failing = ", ".join(d.name for d in result.domain_results if not d.meets_threshold)
        narrative = (
            f"Assurance score {result.assurance_score:.1f}/100 ({result.rag.value}) — "
            f"below its own threshold in: {failing}."
        )
    else:
        narrative = (
            f"Assurance score {result.assurance_score:.1f}/100 ({result.rag.value}) — "
            "every domain at or above its own threshold, no critical-control failures."
        )

    return BaselineOpinion(
        rag=result.rag, headline=headline, narrative=narrative, recommendation=recommendation
    )
