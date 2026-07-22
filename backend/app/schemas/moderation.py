from uuid import UUID

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ReportCreate(BaseModel):
    content_id: UUID | None = None
    patch_id: UUID | None = None
    reason: str = Field(min_length=1, max_length=500)


class ContentReviewDecision(BaseModel):
    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=500)
    revision_number: int | None = Field(default=None, ge=1)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def require_rejection_note(self):
        if self.decision == "reject" and self.note is None:
            raise ValueError("REJECTION_NOTE_REQUIRED")
        return self
