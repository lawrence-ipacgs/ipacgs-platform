"""SOD-001/002 — the maker-checker rule that Section 5 of the architecture
document flags as a real staffing constraint, not just a nice-to-have.
Pure logic, no DB or network needed.
"""

import pytest

from ipacgs.core.security import CurrentUser, MakerCheckerViolation, enforce_maker_checker


def _user(object_id: str) -> CurrentUser:
    return CurrentUser(object_id=object_id, display_name="Test User", roles=(), raw_claims={})


def test_same_person_cannot_review_their_own_work() -> None:
    preparer_id = "11111111-1111-1111-1111-111111111111"
    with pytest.raises(MakerCheckerViolation):
        enforce_maker_checker(preparer_id, _user(preparer_id))


def test_different_person_may_review() -> None:
    preparer_id = "11111111-1111-1111-1111-111111111111"
    reviewer = _user("22222222-2222-2222-2222-222222222222")
    enforce_maker_checker(preparer_id, reviewer)  # should not raise
