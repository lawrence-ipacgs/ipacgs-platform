"""The scoring engine — `FW-OPBOH-005`: "domain scores, critical-control
failures... without averaging concealment."

Deliberately pure functions over plain dataclasses, not SQLAlchemy models —
this is the one part of Epic 3 that most benefits from being fully unit-
testable with no database at all, the same way `core/security.py`'s
maker-checker check is. The caller (the workflow layer, or eventually an API
route) is responsible for mapping ORM rows into `QuestionScore` /
`DomainInput` before calling in, and mapping the result back out.

The "no averaging concealment" principle, concretely: a domain's numeric
score is always reported, but it is never the only thing that decides
whether OPBOH is satisfied. Any critical-control failure is surfaced
explicitly, by name, alongside the number — a domain that averages to 0.95
because nine easy questions passed and one critical one failed still shows
that failure, not just the 0.95.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionScore:
    """One answered question, already reduced to what scoring needs."""

    question_id: str
    control_objective: str
    is_critical_control: bool
    pass_threshold: float
    score: float | None  # None = unanswered
    evidence_sufficient: bool | None


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
    overall_score: float
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


def _question_failure_reason(q: QuestionScore) -> str | None:
    if q.score is None:
        return "unanswered"
    if q.evidence_sufficient is False:
        return "evidence insufficient"
    if q.score < q.pass_threshold:
        return f"score {q.score:.2f} below pass threshold {q.pass_threshold:.2f}"
    return None


def score_domain(domain: DomainInput) -> DomainResult:
    answered = [q for q in domain.questions if q.score is not None]
    unanswered_count = len(domain.questions) - len(answered)

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
        # concrete: meets_threshold can be False even at a score of 1.0.
        meets_threshold=(domain_score >= domain.min_score_threshold) and not failures,
        critical_failures=tuple(failures),
        unanswered_count=unanswered_count,
    )


def score_assessment(domains: tuple[DomainInput, ...]) -> AssessmentResult:
    if not domains:
        return AssessmentResult(overall_score=0.0, domain_results=(), critical_failures=())

    domain_results = tuple(score_domain(d) for d in domains)

    total_weight = sum(d.weight for d in domains)
    overall_score = (
        sum(dr.score * d.weight for dr, d in zip(domain_results, domains, strict=True))
        / total_weight
        if total_weight > 0
        else 0.0
    )

    all_failures = tuple(f for dr in domain_results for f in dr.critical_failures)

    return AssessmentResult(
        overall_score=overall_score,
        domain_results=domain_results,
        critical_failures=all_failures,
    )
