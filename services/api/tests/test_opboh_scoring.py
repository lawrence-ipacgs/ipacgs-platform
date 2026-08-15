"""The scoring engine — pure logic, no DB. The property that actually
matters here is "no averaging concealment": a domain can score well
numerically and still fail, if a critical control inside it failed.

Scale note: scores are 0-5 (the real Likert scale — see
services/opboh_scoring.py's module docstring), pass/domain thresholds are
on the same 0-5 scale, and evidence_sufficiency_factor is 0.5-1.0.
"""

from ipacgs.services.opboh_scoring import (
    DomainInput,
    QuestionScore,
    ResponseValue,
    score_assessment,
    score_domain,
)


def _q(
    qid: str,
    *,
    critical: bool = False,
    score: float | None = 5.0,
    threshold: float = 5.0,
    response_value: ResponseValue | None = ResponseValue.YES,
    evidence_sufficiency_factor: float | None = 1.0,
) -> QuestionScore:
    # An unanswered question (score=None) has no response_value either,
    # unless the caller explicitly wants to test some other combination.
    if score is None and response_value is ResponseValue.YES:
        response_value = None
    return QuestionScore(
        question_id=qid,
        control_objective=f"objective-{qid}",
        is_critical_control=critical,
        pass_threshold=threshold,
        response_value=response_value,
        score=score,
        evidence_sufficiency_factor=evidence_sufficiency_factor,
    )


def test_all_questions_pass_domain_meets_threshold() -> None:
    domain = DomainInput(
        domain_id="d1",
        name="Sponsor Readiness",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(_q("q1", score=5.0), _q("q2", score=4.0)),
    )
    result = score_domain(domain)
    assert result.meets_threshold is True
    assert result.critical_failures == ()
    assert result.score == 4.5


def test_high_score_does_not_conceal_a_critical_failure() -> None:
    """The exact property FW-OPBOH-005 calls for: nine easy passes and one
    failed critical control should not average its way to a clean domain."""
    questions = tuple(_q(f"easy-{i}", score=5.0) for i in range(9)) + (
        _q("critical-1", critical=True, score=0.0, threshold=5.0),
    )
    domain = DomainInput(
        domain_id="d1", name="Governance", weight=1.0, min_score_threshold=3.0, questions=questions
    )
    result = score_domain(domain)

    assert result.score == 4.5  # the number looks fine on its own
    assert result.meets_threshold is False  # but the domain still fails
    assert len(result.critical_failures) == 1
    assert result.critical_failures[0].question_id == "critical-1"


def test_unanswered_critical_control_counts_as_a_failure() -> None:
    domain = DomainInput(
        domain_id="d1",
        name="Site",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(_q("q1", critical=True, score=None),),
    )
    result = score_domain(domain)
    assert result.meets_threshold is False
    assert result.critical_failures[0].reason == "unanswered"
    assert result.unanswered_count == 1


def test_a_not_applicable_critical_control_is_excluded_not_failed() -> None:
    """Documented interpretation (services/opboh_scoring.py): NOT_APPLICABLE
    isn't specified by the source material either way — this module treats
    it as excluded from scoring entirely, even for a critical control."""
    domain = DomainInput(
        domain_id="d1",
        name="Site",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(
            _q(
                "q1",
                critical=True,
                score=0,
                response_value=ResponseValue.NOT_APPLICABLE,
            ),
        ),
    )
    result = score_domain(domain)
    assert result.critical_failures == ()
    assert result.unanswered_count == 0
    assert result.score == 0.0  # nothing scoreable to average


def test_insufficient_evidence_fails_a_critical_control_even_with_a_full_score() -> None:
    domain = DomainInput(
        domain_id="d1",
        name="Legal",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(_q("q1", critical=True, score=5.0, evidence_sufficiency_factor=0.5),),
    )
    result = score_domain(domain)
    assert result.meets_threshold is False
    assert "evidence" in result.critical_failures[0].reason


def test_domain_with_no_answered_questions_scores_zero_not_undefined() -> None:
    domain = DomainInput(
        domain_id="d1",
        name="Empty",
        weight=1.0,
        min_score_threshold=3.0,
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
        min_score_threshold=3.0,
        questions=(_q("q1", score=5.0),),
    )
    weak = DomainInput(
        domain_id="d2",
        name="Weak",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(_q("q2", score=0.0),),
    )
    result = score_assessment((strong, weak))
    # (5.0*3 + 0.0*1) / 4 = 3.75
    assert result.overall_score == 3.75


def test_assurance_score_applies_the_evidence_sufficiency_factor() -> None:
    domain = DomainInput(
        domain_id="d1",
        name="Domain",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(_q("q1", score=5.0, evidence_sufficiency_factor=0.8),),
    )
    result = score_assessment((domain,))
    assert result.overall_score == 5.0
    assert result.evidence_sufficiency_factor == 0.8
    # (5.0/5.0*100) * 0.8 = 80.0
    assert result.assurance_score == 80.0
    assert result.rag.value == "green"  # >=80 exactly


def test_assurance_score_bands_amber_between_60_and_80() -> None:
    domain = DomainInput(
        domain_id="d1",
        name="Domain",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(_q("q1", score=3.5, evidence_sufficiency_factor=1.0),),
    )
    result = score_assessment((domain,))
    # (3.5/5.0*100) * 1.0 = 70.0
    assert result.assurance_score == 70.0
    assert result.rag.value == "amber"


def test_a_critical_failure_forces_red_regardless_of_the_assurance_score() -> None:
    # Nine perfect scores and one failed critical control — the assurance
    # score alone would band Green (90 >= 80), same shape as
    # test_high_score_does_not_conceal_a_critical_failure above.
    questions = tuple(_q(f"easy-{i}", score=5.0) for i in range(9)) + (
        _q("critical", critical=True, score=0.0),
    )
    domain = DomainInput(
        domain_id="d1", name="Domain", weight=1.0, min_score_threshold=3.0, questions=questions
    )
    result = score_assessment((domain,))
    assert result.assurance_score == 90.0  # the number alone would band Green
    assert result.rag.value == "red"  # but the critical failure overrides it


def test_assessment_is_clean_only_with_no_failures_and_every_domain_over_threshold() -> None:
    good = DomainInput(
        domain_id="d1",
        name="Good",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(_q("q1", score=5.0),),
    )
    result = score_assessment((good,))
    assert result.is_clean is True
    assert result.has_critical_failure is False

    with_failure = DomainInput(
        domain_id="d2",
        name="Bad",
        weight=1.0,
        min_score_threshold=3.0,
        questions=(_q("q2", critical=True, score=0.0),),
    )
    dirty_result = score_assessment((good, with_failure))
    assert dirty_result.is_clean is False
    assert dirty_result.has_critical_failure is True
    assert len(dirty_result.critical_failures) == 1


def test_empty_assessment_scores_zero_but_is_vacuously_clean() -> None:
    result = score_assessment(())
    assert result.overall_score == 0.0
    assert result.assurance_score == 0.0
    assert result.is_clean is True  # vacuously — no domains means nothing failed
    assert result.domain_results == ()
