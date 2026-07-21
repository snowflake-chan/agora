"""Generate one safe, idempotent community question per UTC day."""

import asyncio
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select

from app.ai.errors import AIServiceError
from app.ai.runtime_config import get_ai_runtime_config
from app.ai.schemas import PollGenerateRequest
from app.ai.service import generate_poll
from app.content_moderation import announce_content_published, assess_content_moderation_after_read
from app.db import async_session
from app.db.models.content import Content
from app.db.models.post_poll import PostPoll
from app.db.models.user import User
from app.notifications.redis import get_redis
from app.post_polls import create_post_poll
from app.schemas.post import PollCreate
from app.config import settings

logger = logging.getLogger(__name__)

_BLOCKED_PATTERNS = (
    r"\bporn(?:ography)?\b",
    r"\bexplicit sexual",
    r"\bsexual exploitation",
    r"\bchild sexual",
    r"\bminor sexual",
    r"\bsex trafficking",
    r"色情",
    r"成人视频",
    r"未成年.*性",
    r"性交易",
)


def _contains_disallowed_material(*values: str) -> bool:
    haystack = " ".join(values).casefold()
    return any(re.search(pattern, haystack, re.IGNORECASE) for pattern in _BLOCKED_PATTERNS)


async def generate_daily_question() -> bool:
    if not settings.DAILY_QUESTION_ENABLED:
        return False
    runtime = await get_ai_runtime_config()
    if not runtime.enabled or not runtime.provider_is_configured():
        return False

    now = datetime.now(timezone.utc)
    date_key = now.date().isoformat()
    redis = await get_redis()
    done_key = f"ai:daily-question:done:{date_key}"
    lock_key = f"ai:daily-question:lock:{date_key}"
    if await redis.exists(done_key):
        return False
    if not await redis.set(lock_key, "1", nx=True, ex=600):
        return False

    try:
        async with async_session() as session:
            author = await session.scalar(
                select(User).where(User.role == "super_admin").order_by(User.created_at.asc()).limit(1)
            )
            if author is None:
                logger.warning("daily question skipped: no administrator author")
                return False
            existing_questions = list((await session.scalars(select(PostPoll.question))).all())
            prompt = (
                f"Generate the daily community question for {date_key}. Explore a new subject "
                "from science, technology, work, education, culture, ethics, design, cities, "
                "media, relationships, or the future. Use context from the date only when useful. "
                "A strong disagreement is welcome, but keep it safe and answerable."
            )
            result = await generate_poll(
                PollGenerateRequest(
                    text=prompt,
                    target_locale="en",
                    exclude_questions=[],
                ),
                user_id=str(author.id),
                client_identifier="daily-question",
                published_questions=existing_questions,
                task="daily_poll",
            )
            if _contains_disallowed_material(result.question, *result.options):
                logger.warning("daily question discarded by sexual-safety filter")
                return False

            title = f"Daily question · {date_key}"
            body = "An AI-generated question for broad, respectful community discussion."
            moderation = await assess_content_moderation_after_read(
                session, title, body, result.question, *result.options
            )
            if moderation.status != "published":
                logger.warning("daily question held by moderation: %s", moderation.reason)
                return False

            post = Content(
                type="post",
                title=title,
                content=body,
                tags=["daily-question", "ai-generated"],
                author_id=author.id,
                moderation_status="published",
                published_at=now,
            )
            session.add(post)
            await session.flush()
            await create_post_poll(
                session,
                post_id=post.id,
                data=PollCreate(
                    question=result.question,
                    options=result.options,
                    duration_hours=168,
                ),
            )
            await session.commit()
            await redis.set(done_key, str(post.id), ex=172800)
            await announce_content_published(post, session=session)
            logger.info("daily question published date=%s post_id=%s", date_key, post.id)
            return True
    except AIServiceError as error:
        logger.warning("daily question generation failed code=%s", error.code)
        return False
    except Exception:
        logger.exception("daily question generation failed unexpectedly")
        return False
    finally:
        await redis.delete(lock_key)


async def run_daily_question_scheduler() -> None:
    while True:
        now = datetime.now(timezone.utc)
        if now.hour == settings.DAILY_QUESTION_HOUR_UTC:
            await generate_daily_question()
        await asyncio.sleep(300)
