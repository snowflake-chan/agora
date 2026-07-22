"""Shared utilities used across route modules."""


def calc_guild_level(proposal_score: int) -> int:
    """Map a guild proposal_score to a level (1-5)."""
    if proposal_score >= 50:
        return 5
    if proposal_score >= 30:
        return 4
    if proposal_score >= 15:
        return 3
    if proposal_score >= 5:
        return 2
    return 1
