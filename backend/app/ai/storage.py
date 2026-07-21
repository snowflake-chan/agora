import hashlib
import re
import unicodedata
from difflib import SequenceMatcher

from app.ai.errors import AIServiceError
from app.config import settings
from app.notifications.redis import get_redis


_INCREMENT_SCRIPT = """
local current = redis.call("INCR", KEYS[1])
if current == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end
return {current, redis.call("TTL", KEYS[1])}
"""


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_question(question: str) -> str:
    normalized = unicodedata.normalize("NFKC", question).casefold()
    compact = "".join(char for char in normalized if char.isalnum())
    if compact:
        return compact
    return re.sub(r"\s+", " ", normalized).strip()


def question_digest(question: str) -> str:
    return _digest(canonical_question(question))


def _question_tokens(question: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", question).casefold()
    return set(re.findall(r"[^\W_]+", normalized, flags=re.UNICODE))


def questions_are_similar(left: str, right: str) -> bool:
    """Reject exact duplicates and high-overlap paraphrases without storing text."""
    normalized_left = canonical_question(left)
    normalized_right = canonical_question(right)
    if normalized_left == normalized_right:
        return True
    if min(len(normalized_left), len(normalized_right)) < 10:
        return False
    if SequenceMatcher(None, normalized_left, normalized_right).ratio() >= 0.9:
        return True
    left_tokens = _question_tokens(left)
    right_tokens = _question_tokens(right)
    if min(len(left_tokens), len(right_tokens)) < 4:
        return False
    overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    return overlap >= 0.8


async def _increment_limit(
    *,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    try:
        redis = await get_redis()
        count, ttl = await redis.eval(
            _INCREMENT_SCRIPT,
            1,
            key,
            window_seconds,
        )
        count = int(count)
        ttl = int(ttl)
    except Exception as exc:
        raise AIServiceError(503, "AI_RATE_LIMIT_UNAVAILABLE") from exc

    if count > limit:
        raise AIServiceError(
            429,
            "AI_RATE_LIMITED",
            headers={"Retry-After": str(max(ttl, 1))},
        )


async def enforce_ai_rate_limit(user_id: str, client_identifier: str) -> None:
    """Apply user, network, and installation-wide budgets before provider use."""
    window = settings.AI_RATE_LIMIT_WINDOW_SECONDS
    await _increment_limit(
        key=f"ai:rate:user:{_digest(user_id)}",
        limit=settings.AI_RATE_LIMIT_REQUESTS,
        window_seconds=window,
    )
    await _increment_limit(
        key=f"ai:rate:ip:{_digest(client_identifier)}",
        limit=settings.AI_RATE_LIMIT_IP_REQUESTS,
        window_seconds=window,
    )
    await _increment_limit(
        key="ai:rate:global",
        limit=settings.AI_RATE_LIMIT_GLOBAL_REQUESTS,
        window_seconds=window,
    )
    await _increment_limit(
        key="ai:rate:global:day",
        limit=settings.AI_RATE_LIMIT_DAILY_GLOBAL_REQUESTS,
        window_seconds=86400,
    )


async def reserve_poll_question(question: str) -> bool:
    """Use a short-lived digest reservation to close concurrent generation races."""
    key = f"ai:poll:question:{question_digest(question)}"
    try:
        redis = await get_redis()
        reserved = await redis.set(
            key,
            "1",
            nx=True,
            ex=settings.AI_POLL_RESERVATION_TTL_SECONDS,
        )
    except Exception as exc:
        raise AIServiceError(503, "AI_POLL_RESERVATION_UNAVAILABLE") from exc
    return bool(reserved)
