"""Paid Q&A API routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.db.models import User
from app.db.models.paid_question import PaidQuestion
from app.notifications.service import create_notification
from app.tokens import paid_qa as qa_service
from app.users.deps import current_user, optional_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qa", tags=["paid_qa"])

class AskRequest(BaseModel):
    to_user_id: UUID
    question_text: str
    amount: int
    is_anonymous: bool = False


class AnswerRequest(BaseModel):
    question_id: UUID
    answer_text: str


@router.post("/ask")
async def ask_question(
    body: AskRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Ask a paid question. Deducts AGC from asker."""
    try:
        q = await qa_service.ask_question(
            session, user.id, body.to_user_id,
            body.question_text, body.amount, body.is_anonymous,
        )
        await session.commit()
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    return {
        "ok": True,
        "question": {
            "id": str(q.id),
            "amount": q.amount,
            "is_anonymous": q.is_anonymous,
            "created_at": q.created_at.isoformat(),
        },
    }


@router.post("/answer")
async def answer_question(
    body: AnswerRequest,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """Answer a paid question addressed to you. Transfers AGC to answerer."""
    try:
        q = await qa_service.answer_question(
            session, body.question_id, user.id, body.answer_text,
        )
        await session.commit()
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc))

    try:
        await create_notification(
            recipient_id=q.from_user_id,
            type="qa_answered",
            title="Question answered",
            message="Your paid question has been answered",
            link=f"/users/{q.to_user_id}",
        )
    except Exception:
        logger.exception("Failed to notify asker %s of answer", q.from_user_id)

    return {
        "ok": True,
        "question": {
            "id": str(q.id),
            "is_answered": q.is_answered,
            "answered_at": q.answered_at.isoformat() if q.answered_at else None,
        },
    }


async def _serialize_question(
    r: PaidQuestion,
    session: AsyncSession,
    viewer_id_str: str | None,
) -> dict:
    """Serialize a PaidQuestion row with viewer-aware masking."""
    from_user = await session.get(User, r.from_user_id)
    to_user = await session.get(User, r.to_user_id)

    from_id_str = str(r.from_user_id)
    to_id_str = str(r.to_user_id)

    viewer_authorized = (
        viewer_id_str is not None
        and (viewer_id_str == from_id_str or viewer_id_str == to_id_str)
    )

    if r.is_anonymous and not viewer_authorized:
        question_text = "Anonymous question (content hidden)"
        answer_text = "Reply content hidden" if r.is_answered else None
    else:
        question_text = r.question_text
        answer_text = r.answer_text if r.is_answered else None

    show_from_user = (
        not r.is_anonymous
        or viewer_id_str == from_id_str
    )

    return {
        "id": str(r.id),
        "from_user": (
            {
                "id": from_id_str,
                "username": from_user.username if from_user else "unknown",
                "nickname": from_user.nickname if from_user else None,
            }
            if show_from_user
            else None
        ),
        "to_user": {
            "id": to_id_str,
            "username": to_user.username if to_user else "unknown",
            "nickname": to_user.nickname if to_user else None,
        },
        "question_text": question_text,
        "amount": r.amount,
        "is_anonymous": r.is_anonymous,
        "is_answered": r.is_answered,
        "answer_text": answer_text,
        "created_at": r.created_at.isoformat(),
        "answered_at": r.answered_at.isoformat() if r.answered_at else None,
    }


@router.get("/user/{user_id}")
async def list_user_questions(
    user_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User | None = Depends(optional_current_user),
):
    """List questions for a user.

    * Profile owner: sees ALL questions (answered + unanswered).
    * Authenticated non-owner: sees answered questions + their own unanswered.
    * Anonymous visitor: sees only answered questions.
    """
    viewer_id = user.id if user else None
    viewer_id_str = str(viewer_id) if viewer_id else None
    user_id_str = str(user_id)
    is_self = viewer_id_str is not None and viewer_id_str == user_id_str

    logger.info(
        "list_user_questions: user_id=%s viewer_id=%s is_self=%s",
        user_id_str, viewer_id_str, is_self,
    )

    q = select(PaidQuestion).where(PaidQuestion.to_user_id == user_id)

    if not is_self:
        # Non-owners: only answered + their own unanswered
        if viewer_id is not None:
            q = q.where(
                or_(
                    PaidQuestion.is_answered == True,  # noqa: E712
                    PaidQuestion.from_user_id == viewer_id,
                )
            )
        else:
            q = q.where(PaidQuestion.is_answered == True)  # noqa: E712

    q = q.order_by(PaidQuestion.created_at.desc())

    total = (
        await session.execute(
            select(func.count()).select_from(q.subquery())
        )
    ).scalar_one()

    rows = (
        await session.execute(
            q.offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()

    logger.info(
        "list_user_questions: total=%d rows=%d", total, len(rows),
    )

    items = [
        await _serialize_question(r, session, viewer_id_str)
        for r in rows
    ]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/inbox")
async def my_inbox(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """List questions received by the current user (including unanswered)."""
    items, total = await qa_service.list_questions_for_user(
        session, user.id, as_asker=False, page=page, page_size=page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/sent")
async def my_sent_questions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_user),
):
    """List questions asked by the current user."""
    items, total = await qa_service.list_questions_for_user(
        session, user.id, as_asker=True, page=page, page_size=page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/count/{user_id}")
async def question_count(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get Q&A counts for a user."""
    return await qa_service.get_question_count(session, user_id)