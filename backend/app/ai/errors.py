from dataclasses import dataclass


@dataclass(slots=True)
class AIServiceError(Exception):
    """A client-safe AI error that never contains provider response details."""

    status_code: int
    code: str
    headers: dict[str, str] | None = None
    # Set only when the rejected source itself needs the durable content
    # moderation state machine. Provider/output filtering must leave this unset.
    source_moderation_reason: str | None = None
    source_moderation_provenance: str | None = None
