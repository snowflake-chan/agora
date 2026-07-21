from app.ai.client import request_structured_completion
from app.ai.classifier import require_trusted_local_classification
from app.ai.errors import AIServiceError
from app.ai.politics import contains_political_signals
from app.ai.prompts import build_user_message
from app.ai.schemas import (
    PollAIResponse,
    PollGenerateRequest,
    PollResponse,
    SummaryAIResponse,
    SummaryResponse,
    TextRequest,
    TranslationAIResponse,
    TranslationResponse,
)
from app.ai.storage import (
    enforce_ai_rate_limit,
    question_digest,
    questions_are_similar,
    reserve_poll_question,
)
from app.config import settings


def ai_is_enabled() -> bool:
    classifier_ready = (
        not settings.uses_production_ai_provider()
        or bool(settings.AI_POLITICAL_CLASSIFIER_URL.strip())
    )
    return (
        settings.AI_FEATURES_ENABLED
        and classifier_ready
        and bool(settings.resolved_ai_api_key().strip())
        and bool(settings.resolved_ai_base_url().strip())
        and bool(settings.resolved_ai_model().strip())
    )


async def _prepare_request(
    *,
    text: str,
    user_id: str,
    client_identifier: str,
    additional_untrusted_text: list[str] | None = None,
) -> None:
    if not ai_is_enabled():
        raise AIServiceError(503, "AI_FEATURE_UNAVAILABLE")
    if len(text) > settings.AI_MAX_INPUT_CHARS:
        raise AIServiceError(422, "AI_INPUT_TOO_LONG")
    values = [text, *(additional_untrusted_text or [])]
    if any(contains_political_signals(value) for value in values):
        raise AIServiceError(422, "POLITICAL_CONTENT_UNAVAILABLE")
    await enforce_ai_rate_limit(user_id, client_identifier)
    if settings.AI_POLITICAL_CLASSIFIER_URL.strip():
        await require_trusted_local_classification(values)


async def _request_completion(
    *,
    user_message: str,
    response_type,
    max_tokens: int,
    user_id: str,
    client_identifier: str,
    charge_rate_limit: bool = False,
):
    # Preflight charges the first attempt. Retries consume another unit.
    if charge_rate_limit:
        await enforce_ai_rate_limit(user_id, client_identifier)
    return await request_structured_completion(
        user_message=user_message,
        response_type=response_type,
        max_tokens=max_tokens,
    )


def _reject_political(status: str) -> None:
    if status != "non_political":
        raise AIServiceError(422, "POLITICAL_CONTENT_UNAVAILABLE")


async def _reject_political_output(*values: str) -> None:
    """Recheck provider output locally instead of trusting its classification."""
    if any(contains_political_signals(value) for value in values):
        raise AIServiceError(422, "POLITICAL_CONTENT_UNAVAILABLE")
    if settings.AI_POLITICAL_CLASSIFIER_URL.strip():
        await require_trusted_local_classification(list(values))


async def summarize(
    data: TextRequest,
    *,
    user_id: str,
    client_identifier: str,
) -> SummaryResponse:
    await _prepare_request(
        text=data.text,
        user_id=user_id,
        client_identifier=client_identifier,
    )
    result = await _request_completion(
        user_message=build_user_message(
            task="summarize",
            text=data.text,
            target_locale=data.target_locale,
        ),
        response_type=SummaryAIResponse,
        max_tokens=1024,
        user_id=user_id,
        client_identifier=client_identifier,
    )
    _reject_political(result.political_status)
    if result.summary is None:
        raise AIServiceError(502, "AI_UPSTREAM_INVALID_RESPONSE")
    await _reject_political_output(result.summary)
    return SummaryResponse(summary=result.summary)


async def translate(
    data: TextRequest,
    *,
    user_id: str,
    client_identifier: str,
) -> TranslationResponse:
    await _prepare_request(
        text=data.text,
        user_id=user_id,
        client_identifier=client_identifier,
    )
    result = await _request_completion(
        user_message=build_user_message(
            task="translate",
            text=data.text,
            target_locale=data.target_locale,
        ),
        response_type=TranslationAIResponse,
        max_tokens=16384,
        user_id=user_id,
        client_identifier=client_identifier,
    )
    _reject_political(result.political_status)
    if result.translation is None:
        raise AIServiceError(502, "AI_UPSTREAM_INVALID_RESPONSE")
    await _reject_political_output(result.translation)
    return TranslationResponse(translation=result.translation)


async def generate_poll(
    data: PollGenerateRequest,
    *,
    user_id: str,
    client_identifier: str,
    published_questions: list[str] | None = None,
) -> PollResponse:
    await _prepare_request(
        text=data.text,
        user_id=user_id,
        client_identifier=client_identifier,
        additional_untrusted_text=list(data.exclude_questions),
    )
    excluded_questions = list(data.exclude_questions)
    excluded_digests = {question_digest(item) for item in excluded_questions}
    published_questions = published_questions or []
    published_digests = {question_digest(item) for item in published_questions}

    for attempt in range(2):
        result = await _request_completion(
            user_message=build_user_message(
                task="poll",
                text=data.text,
                target_locale=data.target_locale,
                exclude_questions=excluded_questions,
            ),
            response_type=PollAIResponse,
            max_tokens=1024,
            user_id=user_id,
            client_identifier=client_identifier,
            charge_rate_limit=attempt > 0,
        )
        _reject_political(result.political_status)
        question = result.question
        options = result.options
        if question is None or options is None:
            raise AIServiceError(502, "AI_UPSTREAM_INVALID_RESPONSE")
        await _reject_political_output(question, *options)

        digest = question_digest(question)
        duplicate = digest in excluded_digests or digest in published_digests
        if not duplicate:
            duplicate = any(
                questions_are_similar(question, existing)
                for existing in [*excluded_questions, *published_questions]
            )
        if not duplicate:
            duplicate = not await reserve_poll_question(question)
        if not duplicate:
            return PollResponse(question=question, options=options)

        excluded_questions.append(question)
        excluded_digests.add(digest)
        if attempt == 1:
            raise AIServiceError(409, "AI_POLL_DUPLICATE")

    raise AIServiceError(409, "AI_POLL_DUPLICATE")
