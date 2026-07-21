from dataclasses import dataclass


@dataclass(slots=True)
class AIServiceError(Exception):
    """A client-safe AI error that never contains provider response details."""

    status_code: int
    code: str
    headers: dict[str, str] | None = None
