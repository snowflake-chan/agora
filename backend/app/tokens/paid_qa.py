"""Paid Q&A service."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PaidQuestion, User
from app.tokens import service as token_service

logger = logging.getLogger("agora.paid_qa")

# Sentinel used to distinguish "viewer_id not supplied by caller" from an
# explicit ``None`` (an anonymous public visitor).
_NOT_SET = object()


async def ask_question(
    session: AsyncSession,
    from_user_id: UUID,
    to_user_id: UUID,
    question_text: str,
    amount: int,
    is_anonymous: bool = False,
) -> PaidQuestion:
    """Ask a paid question. Deducts AGC from asker immediately."""
    if from_user_id == to_user_id:
        raise ValueError("Cannot ask yourself")

    if amount <= 0:
        raise ValueError("Amount must be positive")

    if not question_text or not question_text.strip():
        raise ValueError("Question text is required")

    # Verify target user exists
    target = await session.get(User, to_user_id)
    if target is None:
        raise ValueError("Target user not found")

    # Deduct from asker
    await token_service.spend(session, from_user_id, amount, "paid_question")

    q = PaidQuestion(
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        question_text=question_text.strip(),
        amount=amount,
        is_anonymous=is_anonymous,
    )
    session.add(q)
    await session.flush()

    # Notify the recipient that a paid question arrived. The message never
    # reveals the asker's identity (anonymous questions stay anonymous).
    # Imported lazily to avoid a potential import cycle with the notifications
    # service, and wrapped so a notification failure can never break the ask.
    try:
        from app.notifications.service import create_notification

        await create_notification(
            recipient_id=to_user_id,
            type="paid_question",
            title="New paid question",
            message=f"Someone asked you a paid question ({amount} AGC)",
            link=f"/users/{to_user_id}",
        )
    except Exception:
        logger.exception("failed to notify question recipient")

    return q


async def answer_question(
    session: AsyncSession,
    question_id: UUID,
    answerer_id: UUID,
    answer_text: str,
) -> PaidQuestion:
    """Answer a paid question. Transfers AGC to the answerer."""
    q = await session.get(PaidQuestion, question_id)
    if q is None:
        raise ValueError("Question not found")
    if q.to_user_id != answerer_id:
        raise ValueError("Not your question to answer")
    if q.is_answered:
        raise ValueError("Already answered")
    if not answer_text.strip():
        raise ValueError("Answer text is required")

    q.answer_text = answer_text.strip()
    q.is_answered = True
    q.is_paid = True
    q.answered_at = datetime.now(timezone.utc)

    # Transfer AGC to answerer
    await token_service.earn(
        session, answerer_id, q.amount, "paid_question_answer", bypass_cap=True
    )

    await session.flush()
    return q


async def list_questions_for_user(
    session: AsyncSession,
    user_id: UUID,
    as_asker: bool = False,
    page: int = 1,
    page_size: int = 20,
    answered_only: bool = False,
    viewer_id: UUID | None | object = _NOT_SET,
) -> tuple[list[dict], int]:
    """List paid questions for a user (as answerer or asker).

    ``viewer_id`` controls access to anonymous question content:

    * ``_NOT_SET`` (default): the caller did not specify a viewer. This is
      used by the authenticated ``my_inbox`` / ``my_sent_questions`` routes,
      where ``user_id`` IS the viewer's own id, so the viewer is always a
      participant and may see the original content.
    * ``None``: an anonymous public visitor. Anonymous question text is
      masked.
    * a UUID: only the asker (``from_user_id``) or the answerer
      (``to_user_id``) may read the original anonymous ``question_text``;
      everyone else sees a masked placeholder.
    """
    if as_asker:
        q = select(PaidQuestion).where(PaidQuestion.from_user_id == user_id)
    else:
        q = select(PaidQuestion).where(PaidQuestion.to_user_id == user_id)

    # Compute the effective viewer early so we can use it in the query filter.
    if viewer_id is _NOT_SET:
        effective_viewer = user_id
    else:
        effective_viewer = viewer_id

    if answered_only:
        # Non-owners see only answered questions, but if the viewer is the
        # asker of an unanswered question to this user, include it too so
        # they can track its status.
        if effective_viewer is not None and effective_viewer != user_id:
            q = q.where(
                or_(
                    PaidQuestion.is_answered == True,
                    PaidQuestion.from_user_id == effective_viewer,
                )
            )
        else:
            q = q.where(PaidQuestion.is_answered == True)

    q = q.order_by(PaidQuestion.created_at.desc())

    total = (
        await session.execute(
            select(func.count()).select_from(q.subquery())
        )
    ).scalar_one()

    rows = (
        await session.execute(q.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()

    items = []
    for r in rows:
        from_user = await session.get(User, r.from_user_id)
        to_user = await session.get(User, r.to_user_id)

        viewer_authorized = (
            effective_viewer is not None
            and (effective_viewer == r.from_user_id or effective_viewer == r.to_user_id)
        )

        # Anonymous question AND answer text are only revealed to the asker
        # and the answerer; everyone else (including anonymous public
        # visitors) gets a masked placeholder so the raw content cannot be
        # scraped via devtools.
        if r.is_anonymous and not viewer_authorized:
            question_text = "Anonymous question (content hidden)"
            answer_text_val = "Reply content hidden" if r.is_answered else None
        else:
            question_text = r.question_text
            answer_text_val = r.answer_text if r.is_answered else None

        items.append({
            "id": str(r.id),
            "from_user": {
                "id": str(r.from_user_id),
                "username": from_user.username if from_user else "unknown",
                "nickname": from_user.nickname if from_user else None,
            } if (not r.is_anonymous or as_asker or (effective_viewer == r.from_user_id)) else None,
            "to_user": {
                "id": str(r.to_user_id),
                "username": to_user.username if to_user else "unknown",
                "nickname": to_user.nickname if to_user else None,
            },
            "question_text": question_text,
            "amount": r.amount,
            "is_anonymous": r.is_anonymous,
            "is_answered": r.is_answered,
            "answer_text": answer_text_val,
            "created_at": r.created_at.isoformat(),
            "answered_at": r.answered_at.isoformat() if r.answered_at else None,
        })

    return items, total


async def get_question_count(
    session: AsyncSession,
    user_id: UUID,
) -> dict:
    """Get Q&A counts for a user."""
    received = (
        await session.execute(
            select(func.count())
            .select_from(PaidQuestion)
            .where(PaidQuestion.to_user_id == user_id)
        )
    ).scalar_one()

    answered = (
        await session.execute(
            select(func.count())
            .select_from(PaidQuestion)
            .where(
                PaidQuestion.to_user_id == user_id,
                PaidQuestion.is_answered == True,
            )
        )
    ).scalar_one()

    asked = (
        await session.execute(
            select(func.count())
            .select_from(PaidQuestion)
            .where(PaidQuestion.from_user_id == user_id)
        )
    ).scalar_one()

    return {
        "questions_received": received,
        "questions_answered": answered,
        "questions_asked": asked,
    }