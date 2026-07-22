from collections.abc import Iterable

from app.config import settings


def validate_moderation_input_size(texts: Iterable[str | None]) -> None:
    """Reject a semantic-review document before it reaches an AI provider."""
    total = sum(len(text.strip()) for text in texts if text and text.strip())
    if total > settings.AI_MAX_INPUT_CHARS:
        raise ValueError("AI_INPUT_TOO_LONG")
