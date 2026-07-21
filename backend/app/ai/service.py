from app.ai.client import request_structured_completion
from app.ai.classifier import (
    require_semantic_classification,
    semantic_moderation_is_configured,
)
from app.ai.errors import AIServiceError
from app.ai.prompts import APPROVED_TRANSLATION_SYSTEM_PROMPT, build_user_message
from app.ai.runtime_config import AIRuntimeConfig, get_ai_runtime_config
from app.ai.schemas import (
    ApprovedTranslationBundleAIResponse,
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
    cache_fill_lock,
    enforce_ai_rate_limit,
    get_cached_translations,
    question_digest,
    questions_are_similar,
    reserve_poll_question,
    translation_cache_key,
)
from app.config import settings


_POLITICAL_MODERATION_REASON = "political_or_uncertain"


def _political_source_error(provenance: str) -> AIServiceError:
    return AIServiceError(
        422,
        "POLITICAL_CONTENT_UNAVAILABLE",
        source_moderation_reason=_POLITICAL_MODERATION_REASON,
        source_moderation_provenance=provenance,
    )


async def ai_is_enabled() -> bool:
    runtime_config = await get_ai_runtime_config()
    return (
        runtime_config.enabled
        and semantic_moderation_is_configured(runtime_config)
        and runtime_config.provider_is_configured()
    )


async def _validate_request(
    *,
    text: str,
    additional_untrusted_text: list[str] | None = None,
) -> list[str]:
    if not await ai_is_enabled():
        raise AIServiceError(503, "AI_FEATURE_UNAVAILABLE")
    values = [text, *(additional_untrusted_text or [])]
    if sum(len(value) for value in values) > settings.AI_MAX_INPUT_CHARS:
        raise AIServiceError(422, "AI_INPUT_TOO_LONG")
    return values


async def _prepare_request(
    *,
    text: str,
    user_id: str,
    client_identifier: str,
    additional_untrusted_text: list[str] | None = None,
    skip_semantic_source_check: bool = False,
) -> None:
    values = await _validate_request(
        text=text,
        additional_untrusted_text=additional_untrusted_text,
    )
    await enforce_ai_rate_limit(user_id, client_identifier)
    if settings.AI_POLITICAL_CLASSIFIER_URL.strip() and not skip_semantic_source_check:
        await require_semantic_classification(
            values,
            source_moderation_reason=_POLITICAL_MODERATION_REASON,
        )


async def _request_completion(
    *,
    user_message: str,
    response_type,
    max_tokens: int,
    user_id: str,
    client_identifier: str,
    charge_rate_limit: bool = False,
    system_prompt: str | None = None,
):
    # Preflight charges the first attempt. Retries consume another unit.
    if charge_rate_limit:
        await enforce_ai_rate_limit(user_id, client_identifier)
    request_kwargs = {} if system_prompt is None else {"system_prompt": system_prompt}
    return await request_structured_completion(
        user_message=user_message,
        response_type=response_type,
        max_tokens=max_tokens,
        **request_kwargs,
    )


def _reject_political(status: str) -> None:
    if status != "non_political":
        raise _political_source_error("provider")


def _reject_political_output_status(status: str | None) -> None:
    if status != "non_political":
        raise AIServiceError(422, "AI_OUTPUT_BLOCKED")


async def _recheck_political_output(*values: str, force: bool = False) -> None:
    """Recheck generated output with the trusted local AI in production."""
    runtime_config = await get_ai_runtime_config()
    if settings.AI_POLITICAL_CLASSIFIER_URL.strip() or (
        force and semantic_moderation_is_configured(runtime_config)
    ):
        try:
            await require_semantic_classification(list(values))
        except AIServiceError as error:
            if error.code == "POLITICAL_CONTENT_UNAVAILABLE":
                raise AIServiceError(422, "AI_OUTPUT_BLOCKED") from error
            raise


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
    _reject_political_output_status(result.output_political_status)
    if result.summary is None:
        raise AIServiceError(502, "AI_UPSTREAM_INVALID_RESPONSE")
    await _recheck_political_output(result.summary)
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
    _reject_political_output_status(result.output_political_status)
    if result.translation is None:
        raise AIServiceError(502, "AI_UPSTREAM_INVALID_RESPONSE")
    await _recheck_political_output(result.translation)
    return TranslationResponse(translation=result.translation)


async def translate_bundle(
    data: TranslationBundleRequest,
    *,
    user_id: str,
    client_identifier: str,
    source_is_human_approved: bool = False,
) -> TranslationBundleResponse:
    source_fields = [(field.key, field.text) for field in data.fields]
    source_values = [field.text for field in data.fields]
    await _prepare_request(
        text="",
        additional_untrusted_text=source_values,
        user_id=user_id,
        client_identifier=client_identifier,
        skip_semantic_source_check=source_is_human_approved,
    )

    user_message = build_user_message(
        task=(
            "translate_approved_fields"
            if source_is_human_approved
            else "translate_fields"
        ),
        target_locale=data.target_locale,
        source_items=[
            {"key": field.key, "text": field.text} for field in data.fields
        ],
        content_context=data.context,
    )

    cache_key = translation_cache_key(
        fields=source_fields,
        target_locale=data.target_locale,
        context=data.context,
        user_prompt=user_message,
    )
    cached = await get_cached_translations(
        cache_key,
        expected_count=len(data.fields),
    )
    if cached is not None:
        if settings.uses_production_ai_provider() and not source_is_human_approved:
            await _recheck_political_output(*cached, force=True)
        return TranslationBundleResponse(
            fields=[
                TranslationFieldResponse(key=field.key, translation=translation)
                for field, translation in zip(data.fields, cached, strict=True)
            ],
            cached=True,
        )

    async with cache_fill_lock(cache_key):
        cached = await get_cached_translations(
            cache_key,
            expected_count=len(data.fields),
        )
        if cached is not None:
            if settings.uses_production_ai_provider() and not source_is_human_approved:
                await _recheck_political_output(*cached, force=True)
            return TranslationBundleResponse(
                fields=[
                    TranslationFieldResponse(key=field.key, translation=translation)
                    for field, translation in zip(data.fields, cached, strict=True)
                ],
                cached=True,
            )

        result = await _request_completion(
            user_message=user_message,
            response_type=(
                ApprovedTranslationBundleAIResponse
                if source_is_human_approved
                else TranslationBundleAIResponse
            ),
            max_tokens=16384,
            user_id=user_id,
            client_identifier=client_identifier,
            system_prompt=(
                APPROVED_TRANSLATION_SYSTEM_PROMPT
                if source_is_human_approved
                else None
            ),
        )
        if not source_is_human_approved:
            _reject_political(result.political_status)
            _reject_political_output_status(result.output_political_status)
        translations = result.translations
        if translations is None or len(translations) != len(data.fields):
            raise AIServiceError(502, "AI_UPSTREAM_INVALID_RESPONSE")
        if not source_is_human_approved:
            await _recheck_political_output(*translations)
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
    _reject_political_output_status(result.output_political_status)
    rewrites = result.rewrites
    if rewrites is None or len(rewrites) != len(data.fields):
        raise AIServiceError(502, "AI_UPSTREAM_INVALID_RESPONSE")
    await _recheck_political_output(*rewrites)
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
        _reject_political_output_status(result.output_political_status)
        question = result.question
        options = result.options
        if question is None or options is None:
            raise AIServiceError(502, "AI_UPSTREAM_INVALID_RESPONSE")
        await _recheck_political_output(question, *options)

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
