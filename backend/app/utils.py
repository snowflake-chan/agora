"""Shared utilities used across route modules."""


def calc_guild_level(points: int) -> int:
    """Map guild points to a level (1-10).
    
    Points are earned only through merged patches (10 pts each).
    Level curve is designed to be engaging early but require
    sustained contribution at higher levels — no inflation.
    """
    if points >= 1500:
        return 10
    if points >= 1000:
        return 9
    if points >= 700:
        return 8
    if points >= 500:
        return 7
    if points >= 350:
        return 6
    if points >= 200:
        return 5
    if points >= 100:
        return 4
    if points >= 50:
        return 3
    if points >= 20:
        return 2
    return 1
