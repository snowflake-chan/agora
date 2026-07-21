import re
import unicodedata
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


Locale = Literal["en", "ja", "zh-TW"]
PoliticalStatus = Literal["non_political", "political", "uncertain"]
TranslationContext = Literal["post", "comment", "patch", "guild", "composer", "poll"]
WritingAction = Literal["polish", "shorten", "clarify"]

InputText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=12000),
]
ExcludedQuestion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=160),
]


def normalize_display_text(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TextRequest(StrictModel):
    text: InputText
    target_locale: Locale


class TranslationField(StrictModel):
    key: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=64,
            pattern=r"^[a-z][a-z0-9_]*$",
        ),
    ]
    text: InputText


class TranslationBundleRequest(StrictModel):
    fields: list[TranslationField] = Field(min_length=1, max_length=8)
    target_locale: Locale
    context: TranslationContext = "post"

    @model_validator(mode="after")
    def validate_fields(self):
        keys = [field.key for field in self.fields]
        if len(set(keys)) != len(keys):
            raise ValueError("translation field keys must be unique")
        if sum(len(field.text) for field in self.fields) > 12000:
            raise ValueError("translation input is too long")
        return self


class WritingAssistRequest(StrictModel):
    fields: list[TranslationField] = Field(min_length=1, max_length=3)
    target_locale: Locale
    context: TranslationContext = "composer"
    action: WritingAction

    @model_validator(mode="after")
    def validate_fields(self):
        keys = [field.key for field in self.fields]
        if len(set(keys)) != len(keys):
            raise ValueError("writing field keys must be unique")
        if sum(len(field.text) for field in self.fields) > 12000:
            raise ValueError("writing input is too long")
        return self


class PollGenerateRequest(TextRequest):
    exclude_questions: list[ExcludedQuestion] = Field(
        default_factory=list,
        max_length=12,
    )


class AIStatusResponse(StrictModel):
    enabled: bool


class SummaryResponse(StrictModel):
    summary: str


class TranslationResponse(StrictModel):
    translation: str


class TranslationFieldResponse(StrictModel):
    key: str
    translation: str


class TranslationBundleResponse(StrictModel):
    fields: list[TranslationFieldResponse]
    cached: bool


class WritingAssistResponse(StrictModel):
    fields: list[TranslationFieldResponse]


class PollResponse(StrictModel):
    question: str
    options: list[str]


class SummaryAIResponse(StrictModel):
    political_status: PoliticalStatus
    summary: str | None = None

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not 1 <= len(value) <= 4000:
            raise ValueError("summary length is invalid")
        return value

    @model_validator(mode="after")
    def require_non_political_result(self):
        if self.political_status == "non_political" and self.summary is None:
            raise ValueError("summary is required for non-political content")
        return self


class TranslationAIResponse(StrictModel):
    political_status: PoliticalStatus
    translation: str | None = None

    @field_validator("translation")
    @classmethod
    def validate_translation(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not 1 <= len(value) <= 24000:
            raise ValueError("translation length is invalid")
        return value

    @model_validator(mode="after")
    def require_non_political_result(self):
        if self.political_status == "non_political" and self.translation is None:
            raise ValueError("translation is required for non-political content")
        return self


class TranslationBundleAIResponse(StrictModel):
    political_status: PoliticalStatus
    translations: list[str] | None = None

    @field_validator("translations")
    @classmethod
    def validate_translations(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [translation.strip() for translation in value]
        if any(not translation or len(translation) > 24000 for translation in normalized):
            raise ValueError("translation is invalid")
        if sum(len(translation) for translation in normalized) > 48000:
            raise ValueError("translations are too long")
        return normalized

    @model_validator(mode="after")
    def require_non_political_result(self):
        if self.political_status == "non_political" and self.translations is None:
            raise ValueError("translations are required for non-political content")
        return self


class WritingAssistAIResponse(StrictModel):
    political_status: PoliticalStatus
    rewrites: list[str] | None = None

    @field_validator("rewrites")
    @classmethod
    def validate_rewrites(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [rewrite.strip() for rewrite in value]
        if any(not rewrite or len(rewrite) > 24000 for rewrite in normalized):
            raise ValueError("rewrite is invalid")
        if sum(len(rewrite) for rewrite in normalized) > 48000:
            raise ValueError("rewrites are too long")
        return normalized

    @model_validator(mode="after")
    def require_non_political_result(self):
        if self.political_status == "non_political" and self.rewrites is None:
            raise ValueError("rewrites are required for non-political content")
        return self


class PollAIResponse(StrictModel):
    political_status: PoliticalStatus
    question: str | None = None
    options: list[str] | None = None

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = normalize_display_text(value)
        if not 5 <= len(value) <= 160 or not any(char.isalnum() for char in value):
            raise ValueError("question is invalid")
        return value

    @field_validator("options")
    @classmethod
    def normalize_options(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not 2 <= len(value) <= 6:
            raise ValueError("poll must contain between 2 and 6 options")

        normalized = [normalize_display_text(option) for option in value]
        if any(not option or len(option) > 80 for option in normalized):
            raise ValueError("poll option is invalid")
        identities = [option.casefold() for option in normalized]
        if len(set(identities)) != len(identities):
            raise ValueError("poll options must be unique")
        return normalized

    @model_validator(mode="after")
    def require_non_political_result(self):
        if self.political_status == "non_political" and (
            self.question is None or self.options is None
        ):
            raise ValueError("poll is required for non-political content")
        return self


class CompletionMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    content: str


class CompletionChoice(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    finish_reason: str
    message: CompletionMessage


class CompletionEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    choices: list[CompletionChoice] = Field(min_length=1)
