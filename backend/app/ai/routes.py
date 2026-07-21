import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.errors import AIServiceError
from app.ai.schemas import (
    AIStatusResponse,
    PollGenerateRequest,
    PollResponse,
    SummaryResponse,
    TextRequest,
    TranslationBundleRequest,
    TranslationBundleResponse,
    TranslationResponse,
    WritingAssistRequest,
    WritingAssistResponse,
)
from app.ai.service import (
    ai_is_enabled,
    generate_poll,
    summarize,
    translate,
    translate_bundle,
    assist_writing,
)
from app.content_moderation import (
    content_href,
    hold_translation_source_for_review,
)
from app.db import get_session
from app.db.models.user import User
from app.db.models.post_poll import PostPoll
from app.deps import check_not_banned
from app.moderation_delivery import deliver_moderation_effects
from app.users.deps import current_user
from app.users.rate_limit import client_ip


router = APIRouter()
logger = logging.getLogger(__name__)


async def ai_eligible_user(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Require a signed-in account that is not globally restricted."""
    await check_not_banned(user.id, session)
    # expire_on_commit=False keeps the authenticated scalar fields available,
    # while ending the read transaction before a potentially slow provider call.
    await session.commit()
    return user


async def published_poll_questions(
    session: AsyncSession = Depends(get_session),
) -> list[str]:
    """Use durable published polls as the long-lived duplicate source."""
    questions = list((await session.scalars(select(PostPoll.question))).all())
    await session.commit()
    return questions


def _http_error(error: AIServiceError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail=error.code,
        headers=error.headers,
    )


async def _deliver_translation_moderation_hold(content) -> None:
    """Attempt durable delivery; the reconciler retries an interrupted attempt."""
    try:
        await deliver_moderation_effects(content.id)
    except Exception as exc:
        logger.warning(
            "AI moderation delivery failed content_id=%s type=%s",
            content.id,
            type(exc).__name__,
        )


@router.get("/status", response_model=AIStatusResponse)
async def get_ai_status() -> AIStatusResponse:
    """Report local readiness without probing or identifying the provider."""
    return AIStatusResponse(enabled=ai_is_enabled())


@router.post("/summarize", response_model=SummaryResponse)
async def summarize_text(
    data: TextRequest,
    request: Request,
    user: User = Depends(ai_eligible_user),
) -> SummaryResponse:
    try:
        return await summarize(
            data,
            user_id=str(user.id),
            client_identifier=client_ip(request),
        )
    except AIServiceError as error:
        raise _http_error(error) from error


@router.post("/translate", response_model=TranslationResponse)
async def translate_text(
    data: TextRequest,
    request: Request,
    user: User = Depends(ai_eligible_user),
) -> TranslationResponse:
    try:
        return await translate(
            data,
            user_id=str(user.id),
            client_identifier=client_ip(request),
        )
    except AIServiceError as error:
        raise _http_error(error) from error


@router.post("/translate/fields", response_model=TranslationBundleResponse)
async def translate_fields(
    data: TranslationBundleRequest,
    request: Request,
    user: User = Depends(ai_eligible_user),
    session: AsyncSession = Depends(get_session),
) -> TranslationBundleResponse:
    """Translate related fields together so titles, bodies, and options keep context."""
    try:
        return await translate_bundle(
            data,
            user_id=str(user.id),
            client_identifier=client_ip(request),
        )
    except AIServiceError as error:
        held_content = None
        if (
            error.source_moderation_reason is not None
            and error.source_moderation_provenance is not None
            and data.source_content_id is not None
            and data.source_revision_number is not None
        ):
            held_content = await hold_translation_source_for_review(
                session,
                content_id=data.source_content_id,
                revision_number=data.source_revision_number,
                context=data.context,
                fields=[(field.key, field.text) for field in data.fields],
                reason=error.source_moderation_reason,
                verdict_provenance=error.source_moderation_provenance,
                actor_id=user.id,
                actor_is_staff=getattr(user, "role", None)
                in ("moderator", "super_admin"),
            )
        if held_content is not None:
            await _deliver_translation_moderation_hold(held_content)
            headers = dict(error.headers or {})
            headers.update(
                {
                    "X-Agora-Moderation-Status": "pending_review",
                    "X-Agora-Moderation-Reason": error.source_moderation_reason,
                    "X-Agora-Content-Id": str(held_content.id),
                    "X-Agora-Revision-Number": str(
                        held_content.revision_number
                    ),
                    "X-Agora-Target-Href": content_href(held_content),
                }
            )
            error = AIServiceError(
                422,
                "POLITICAL_CONTENT_REVIEW_PENDING",
                headers=headers,
            )
        raise _http_error(error) from error


@router.post("/writing/assist", response_model=WritingAssistResponse)
async def improve_draft(
    data: WritingAssistRequest,
    request: Request,
    user: User = Depends(ai_eligible_user),
) -> WritingAssistResponse:
    """Return a field-preserving draft suggestion; applying it remains a user action."""
    try:
        return await assist_writing(
            data,
            user_id=str(user.id),
            client_identifier=client_ip(request),
        )
    except AIServiceError as error:
        raise _http_error(error) from error


@router.post("/polls/generate", response_model=PollResponse)
async def generate_opinion_poll(
    data: PollGenerateRequest,
    request: Request,
    user: User = Depends(ai_eligible_user),
    existing_questions: list[str] = Depends(published_poll_questions),
) -> PollResponse:
    try:
        return await generate_poll(
            data,
            user_id=str(user.id),
            client_identifier=client_ip(request),
            published_questions=existing_questions,
        )
    except AIServiceError as error:
        raise _http_error(error) from error
