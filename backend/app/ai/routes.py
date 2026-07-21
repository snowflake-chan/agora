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
    TranslationResponse,
)
from app.ai.service import ai_is_enabled, generate_poll, summarize, translate
from app.db import get_session
from app.db.models.user import User
from app.db.models.post_poll import PostPoll
from app.deps import check_not_banned
from app.users.deps import current_user
from app.users.rate_limit import client_ip


router = APIRouter()


async def ai_eligible_user(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Require a signed-in account that is not globally restricted."""
    await check_not_banned(user.id, session)
    return user


async def published_poll_questions(
    session: AsyncSession = Depends(get_session),
) -> list[str]:
    """Use durable published polls as the long-lived duplicate source."""
    return list((await session.scalars(select(PostPoll.question))).all())


def _http_error(error: AIServiceError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail=error.code,
        headers=error.headers,
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
