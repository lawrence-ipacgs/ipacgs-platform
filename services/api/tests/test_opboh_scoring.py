"""The scoring engine — pure logic, no DB. The property that actually
matters here is "no averaging concealment": a domain can score well
numerically and still fail, if a critical control inside it failed.
"""

from ipacgs.services.opboh_scoring import DomainInput, QuestionScore, score_assessment, score_domain


def _q(
    qid: str,
    *,
    critical: bool = False,
    score: float | None = 1.0,
    threshold: float = 1.0,
    evidence_sufficient: bool | None = True,
) -> QuestionScore:
    return QuestionScore(
        question_id=qid,
        control_objective=f"objective-{qid}",
        is_critical_control=critical,
        pass_threshold=threshold,
        score=score,
        evidence_sufficient=evidence_sufficient,
    )


def test_all_questions_pass_domain_meets_threshold() -> None:
    domain = DomainInput(
        domain_id="d1",
        name="Sponsor Readiness",
        weight=1.0,
        min_score_threshold=0.6,
        questions=(_q("q1", score=1.0), _q("q2", score=0.8)),
    )
    result = score_domain(domain)
    assert result.meets_threshold is True
    assert result.critical_failures == ()
    assert result.score == 0.9


def test_high_score_does_not_conceal_a_critical_failure() -> None:
    """The exact property FW-OPBOH-005 calls for: nine easy passes and one
    failed critical control should not average its way to a clean domain."""
    questions = tuple(_q(f"easy-{i}", score=1.0) for i in range(9)) + (
        _q("critical-1", critical=True, score=0.0, threshold=1.0),
    )
    domain = DomainInput(
        domain_id="d1", name="Governance", weight=1.0, min_score_threshold=0.6, questions=questions
    )
    result = score_domain(domain)

    assert result.score == 0.9  # the number looks fine on its own
    assert result.meets_threshold is False  # but the domain still fails
    assert len(result.critical_failures) == 1
    assert result.critical_failures[0].question_id == "critical-1"


def test_unanswered_critical_control_counts_as_a_failure() -> None:
    domain = DomainInput(
        domain_id="d1",
        name="Site",
        weight=1.0,
        min_score_threshold=0.6,
        questions=(_q("q1", critical=True, score=None),),
    )
    result = score_domain(domain)
    assert result.meets_threshold is False
    assert result.critical_failures[0].reason == "unanswered"
    assert result.unanswered_count == 1


def test_insufficient_evidence_fails_a_critical_control_even_with_a_full_score() -> None:
    domain = DomainInput(
        domain_id="d1",
        name="Legal",
        weight=1.0,
        min_score_threshold=0.6,
        questions=(_q("q1", critical=True, score=1.0, evidence_sufficient=False),),
    )
    result = score_domain(domain)
    assert result.meets_threshold is False
    assert result.critical_failures[0].reason == "evidence insufficient"


def test_domain_with_no_answered_questions_scores_zero_not_undefined() -> None:
    domain = DomainInput(
        domain_id="d1",
        name="Empty",
        weight=1.0,
        min_score_threshold=0.6,
        questions=(_q("q1", score=None),),
    )
    result = score_domain(domain)
    assert result.score == 0.0
    assert result.meets_threshold is False


def test_assessment_score_is_weighted_across_domains() -> None:
    strong = DomainInput(
        domain_id="d1",
        name="Strong",
        weight=3.0,
        min_score_threshold=0.6,
        questions=(_q("q1", score=1.0),),
    )
    weak = DomainInput(
        domain_id="d2",
        name="Weak",
        weight=1.0,
        min_score_threshold=0.6,
        questions=(_q("q2", score=0.0),),
    )
    result = score_assessment((strong, weak))
    # (1.0*3 + 0.0*1) / 4 = 0.75
    assert result.overall_score == 0.75


def test_assessment_is_clean_only_with_no_failures_and_every_domain_over_threshold() -> None:
    good = DomainInput(
        domain_id="d1",
        name="Good",
        weight=1.0,
        min_score_threshold=0.6,
        questions=(_q("q1", score=1.0),),
    )
    result = score_assessment((good,))
    assert result.is_clean is True
    assert result.has_critical_failure is False

    with_failure = DomainInput(
        domain_id="d2",
        name="Bad",
        weight=1.0,
        min_score_threshold=0.6,
        questions=(_q("q2", critical=True, score=0.0),),
    )
    dirty_result = score_assessment((good, with_failure))
    assert dirty_result.is_clean is False
    assert dirty_result.has_critical_failure is True
    assert len(dirty_result.critical_failures) == 1


def test_empty_assessment_scores_zero_but_is_vacuously_clean() -> None:
    result = score_assessment(())
    assert result.overall_score == 0.0
    assert result.is_clean is True  # vacuously — no domains means nothing failed
    assert result.domain_results == ()
