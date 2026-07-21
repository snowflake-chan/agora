import asyncio

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
    TranslationBundleAIResponse,
    TranslationBundleRequest,
    TranslationBundleResponse,
    TranslationFieldResponse,
    TranslationResponse,
    WritingAssistAIResponse,
    WritingAssistRequest,
    WritingAssistResponse,
)
from app.ai.storage import (
    cache_translations,
    enforce_ai_rate_limit,
    get_cached_translations,
    question_digest,
    questions_are_similar,
    reserve_poll_question,
    translation_cache_key,
)
from app.config import settings


_provider_semaphore = asyncio.Semaphore(settings.AI_MAX_CONCURRENT_REQUESTS)


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


def _validate_request(
    *,
    text: str,
    additional_untrusted_text: list[str] | None = None,
) -> list[str]:
    if not ai_is_enabled():
        raise AIServiceError(503, "AI_FEATURE_UNAVAILABLE")
    values = [text, *(additional_untrusted_text or [])]
    if sum(len(value) for value in values) > settings.AI_MAX_INPUT_CHARS:
        raise AIServiceError(422, "AI_INPUT_TOO_LONG")
    if any(contains_political_signals(value) for value in values):
        raise AIServiceError(422, "POLITICAL_CONTENT_UNAVAILABLE")
    return values


async def _prepare_request(
    *,
    text: str,
    user_id: str,
    client_identifier: str,
    additional_untrusted_text: list[str] | None = None,
) -> None:
    values = _validate_request(
        text=text,
        additional_untrusted_text=additional_untrusted_text,
    )
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
    async with _provider_semaphore:
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


async def translate_bundle(
    data: TranslationBundleRequest,
    *,
    user_id: str,
    client_identifier: str,
) -> TranslationBundleResponse:
    source_fields = [(field.key, field.text) for field in data.fields]
    source_values = [field.text for field in data.fields]
    _validate_request(text="", additional_untrusted_text=source_values)
    if settings.AI_POLITICAL_CLASSIFIER_URL.strip():
        # Cache hits still pass the current trusted classifier. A result cached in a
        # development environment must never bypass production's semantic gate.
        await require_trusted_local_classification(source_values)

    cache_key = translation_cache_key(
        fields=source_fields,
        target_locale=data.target_locale,
        context=data.context,
    )
    cached = await get_cached_translations(
        cache_key,
        expected_count=len(data.fields),
    )
    if cached is not None:
        return TranslationBundleResponse(
            fields=[
                TranslationFieldResponse(key=field.key, translation=translation)
                for field, translation in zip(data.fields, cached, strict=True)
            ],
            cached=True,
        )

    await enforce_ai_rate_limit(user_id, client_identifier)

    result = await _request_completion(
        user_message=build_user_message(
            task="translate_fields",
            target_locale=data.target_locale,
            source_items=[
                {"key": field.key, "text": field.text} for field in data.fields
            ],
            content_context=data.context,
        ),
        response_type=TranslationBundleAIResponse,
        max_tokens=16384,
        user_id=user_id,
        client_identifier=client_identifier,
    )
    _reject_political(result.political_status)
    translations = result.translations
    if translations is None or len(translations) != len(data.fields):
        raise AIServiceError(502, "AI_UPSTREAM_INVALID_RESPONSE")
    await _reject_political_output(*translations)
    await cache_translations(cache_key, translations)
    return TranslationBundleResponse(
        fields=[
            TranslationFieldResponse(key=field.key, translation=translation)
            for field, translation in zip(data.fields, translations, strict=True)
        ],
        cached=False,
    )


async def assist_writing(
    data: WritingAssistRequest,
    *,
    user_id: str,
    client_identifier: str,
) -> WritingAssistResponse:
    source_values = [field.text for field in data.fields]
    await _prepare_request(
        text="",
        additional_untrusted_text=source_values,
        user_id=user_id,
        client_identifier=client_identifier,
    )
    result = await _request_completion(
        user_message=build_user_message(
            task="write_assist",
            target_locale=data.target_locale,
            source_items=[
                {"key": field.key, "text": field.text} for field in data.fields
            ],
            content_context=data.context,
            writing_action=data.action,
        ),
        response_type=WritingAssistAIResponse,
        max_tokens=16384,
        user_id=user_id,
        client_identifier=client_identifier,
    )
    _reject_political(result.political_status)
    rewrites = result.rewrites
    if rewrites is None or len(rewrites) != len(data.fields):
        raise AIServiceError(502, "AI_UPSTREAM_INVALID_RESPONSE")
    await _reject_political_output(*rewrites)
    return WritingAssistResponse(
        fields=[
            TranslationFieldResponse(key=field.key, translation=rewrite)
            for field, rewrite in zip(data.fields, rewrites, strict=True)
        ],
    )


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
