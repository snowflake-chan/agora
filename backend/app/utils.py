"""Shared utilities used across route modules."""


def calc_guild_level(member_count: int) -> int:
    """Map a guild member count to a level (1-5)."""
    if member_count >= 50:
        return 5
    if member_count >= 31:
        return 4
    if member_count >= 16:
        return 3
    if member_count >= 6:
        return 2
    return 1
