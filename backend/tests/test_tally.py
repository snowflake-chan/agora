"""Pure tests for governance outcome and deadline boundaries."""

from datetime import datetime, timedelta, timezone

from app.patches.routes import _decide_vote_outcome, _deadline_passed


def _counts(for_: int = 0, against: int = 0, abstain: int = 0) -> dict[str, int]:
    return {"for": for_, "against": against, "abstain": abstain}


def test_empty_or_non_majority_ballots_are_rejected():
    assert _decide_vote_outcome(_counts()) == "rejected"
    assert _decide_vote_outcome(_counts(for_=2, against=2)) == "rejected"
    assert _decide_vote_outcome(_counts(for_=2, against=1, abstain=1)) == "rejected"


def test_strict_majority_and_abstention_rule():
    assert _decide_vote_outcome(_counts(for_=3, against=2)) == "passed"
    assert _decide_vote_outcome(_counts(for_=1)) == "passed"
    assert _decide_vote_outcome(_counts(abstain=5)) == "rejected"


def test_deadline_is_inclusive_and_handles_naive_legacy_values():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert _deadline_passed(None, now=now) is False
    assert _deadline_passed(now, now=now) is True
    assert _deadline_passed(now + timedelta(hours=1), now=now) is False
    assert _deadline_passed(datetime(2026, 1, 1, 11, 0), now=now) is True
