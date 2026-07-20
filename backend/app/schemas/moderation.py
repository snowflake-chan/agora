from uuid import UUID

from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    content_id: UUID | None = None
    patch_id: UUID | None = None
    reason: str = Field(min_length=1, max_length=500)
