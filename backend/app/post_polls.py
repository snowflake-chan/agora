"""Shared persistence and response mapping for native post polls."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.post_poll import PostPoll, PostPollOption, PostPollVote
from app.schemas.post import (
    PollCreate,
    PollOptionRead,
    PollRead,
    poll_option_digest,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def create_post_poll(
    session: AsyncSession,
    *,
    post_id: UUID,
    data: PollCreate,
) -> PostPoll:
    """Create the poll and its validated options in the caller's transaction."""
    created_at = utcnow()
    poll = PostPoll(
        post_id=post_id,
        question=data.question,
        created_at=created_at,
        closes_at=created_at + timedelta(hours=data.duration_hours),
    )
    session.add(poll)
    await session.flush()
    session.add_all(
        PostPollOption(
            poll_id=poll.id,
            text=option,
            normalized_digest=poll_option_digest(option),
            position=position,
        )
        for position, option in enumerate(data.options)
    )
    return poll


async def load_post_polls(
    session: AsyncSession,
    post_ids: list[UUID],
    *,
    viewer_id: UUID | None = None,
) -> dict[UUID, PollRead]:
    """Load poll snapshots for a post page in a bounded number of queries."""
    if not post_ids:
        return {}

    poll_rows = (
        await session.execute(
            select(
                PostPoll,
                (PostPoll.closes_at <= func.clock_timestamp()).label("is_closed"),
            ).where(PostPoll.post_id.in_(post_ids))
        )
    ).all()
    polls = [poll for poll, _is_closed in poll_rows]
    if not polls:
        return {}

    poll_ids = [poll.id for poll in polls]
    option_rows = (
        await session.execute(
            select(
                PostPollOption.id,
                PostPollOption.poll_id,
                PostPollOption.text,
                PostPollOption.position,
                func.count(PostPollVote.id).label("vote_count"),
            )
            .outerjoin(PostPollVote, PostPollVote.option_id == PostPollOption.id)
            .where(PostPollOption.poll_id.in_(poll_ids))
            .group_by(
                PostPollOption.id,
                PostPollOption.poll_id,
                PostPollOption.text,
                PostPollOption.position,
            )
            .order_by(PostPollOption.poll_id, PostPollOption.position)
        )
    ).all()

    selected_by_poll: dict[UUID, UUID] = {}
    if viewer_id is not None:
        selected_by_poll = dict(
            (
                await session.execute(
                    select(PostPollVote.poll_id, PostPollVote.option_id).where(
                        PostPollVote.poll_id.in_(poll_ids),
                        PostPollVote.user_id == viewer_id,
                    )
                )
            ).all()
        )

    options_by_poll: dict[UUID, list[PollOptionRead]] = {
        poll.id: [] for poll in polls
    }
    totals_by_poll: dict[UUID, int] = {poll.id: 0 for poll in polls}
    for option_id, poll_id, text, _position, vote_count in option_rows:
        count = int(vote_count)
        options_by_poll[poll_id].append(
            PollOptionRead(id=option_id, text=text, vote_count=count)
        )
        totals_by_poll[poll_id] += count

    closed_by_poll = {poll.id: bool(is_closed) for poll, is_closed in poll_rows}
    return {
        poll.post_id: PollRead(
            id=poll.id,
            question=poll.question,
            closes_at=poll.closes_at,
            is_closed=closed_by_poll[poll.id],
            total_votes=totals_by_poll[poll.id],
            options=options_by_poll[poll.id],
            selected_option_id=selected_by_poll.get(poll.id),
        )
        for poll in polls
    }
