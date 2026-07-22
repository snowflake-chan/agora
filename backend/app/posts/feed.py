from datetime import datetime, timezone
from math import exp, log1p
from typing import Literal
from uuid import UUID

from app.schemas.post import FeedItem

FeedMode = Literal["recommended", "trending", "following", "latest"]


def _age_hours(created_at: datetime, now: datetime) -> float:
    created = created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    current = now
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return max(0.0, (current - created).total_seconds() / 3600)


def _interaction_count(item: FeedItem) -> int:
    poll_votes = item.poll.total_votes if item.poll else 0
    return (
        item.like_count
        + item.reply_count
        + poll_votes
        + item.for_count
        + item.against_count
        + item.abstain_count
    )


def _engagement_points(item: FeedItem) -> float:
    if item.type == "post":
        poll_votes = item.poll.total_votes if item.poll else 0
        return item.like_count * 1.5 + item.reply_count * 2.5 + poll_votes
    votes = item.for_count + item.against_count + item.abstain_count
    return item.reply_count * 2.5 + votes * 1.25


def _freshness(item: FeedItem, now: datetime) -> float:
    return 2 ** (-_age_hours(item.created_at, now) / 72)


def recommendation_score(
    item: FeedItem,
    *,
    now: datetime,
    following_author_ids: set[UUID],
    interest_tags: set[str],
) -> float:
    freshness = _freshness(item, now)
    engagement = 1 - exp(-_engagement_points(item) / 8)
    relationship = 1.0 if item.author_id in following_author_ids else 0.0
    shared_tags = {
        tag.casefold()
        for tag in item.tags or []
        if tag.casefold() in interest_tags
    }
    affinity = min(1.0, len(shared_tags) / 2)
    governance = (
        1.0
        if item.status == "voting"
        else 0.5
        if item.status in {"passed", "merged"}
        else 0.0
    )
    return (
        freshness * 0.40
        + engagement * 0.25
        + relationship * 0.20
        + affinity * 0.10
        + governance * 0.05
    )


def trending_score(item: FeedItem, *, now: datetime) -> float:
    age_days = _age_hours(item.created_at, now) / 24
    activity = 1 + _engagement_points(item)
    governance = 0.25 if item.status == "voting" else 0.0
    return log1p(activity) / ((age_days + 1.5) ** 0.72) + governance


def _recommendation_reason(
    item: FeedItem,
    *,
    following_author_ids: set[UUID],
    interest_tags: set[str],
) -> str:
    if item.author_id in following_author_ids:
        return "followed_author"
    shared_tags = [
        tag for tag in item.tags or [] if tag.casefold() in interest_tags
    ]
    if shared_tags:
        return f"topic:{shared_tags[0]}"
    if item.status == "voting":
        return "community_voting"
    if _interaction_count(item) >= 2:
        return "rising"
    return "recent"


def _diversify(items: list[FeedItem]) -> list[FeedItem]:
    remaining = list(items)
    ranked: list[FeedItem] = []
    while remaining:
        pick = 0
        if (
            len(ranked) >= 2
            and ranked[-1].author_id == ranked[-2].author_id
        ):
            alternative = next(
                (
                    index
                    for index, item in enumerate(remaining)
                    if item.author_id != ranked[-1].author_id
                ),
                None,
            )
            if alternative is not None:
                pick = alternative
        ranked.append(remaining.pop(pick))
    return ranked


def rank_feed_items(
    items: list[FeedItem],
    *,
    mode: FeedMode,
    following_author_ids: set[UUID] | None = None,
    interest_tags: set[str] | None = None,
    now: datetime | None = None,
) -> list[FeedItem]:
    following = following_author_ids or set()
    interests = {tag.casefold() for tag in interest_tags or set()}
    current = now or datetime.now(timezone.utc)

    if mode == "following":
        filtered = [item for item in items if item.author_id in following]
        return [
            item.model_copy(update={"ranking_reason": "followed_author"})
            for item in sorted(
                filtered, key=lambda item: item.created_at, reverse=True
            )
        ]

    if mode == "latest":
        return [
            item.model_copy(update={"ranking_reason": "latest"})
            for item in sorted(
                items, key=lambda item: item.created_at, reverse=True
            )
        ]

    if mode == "trending":
        scored = sorted(
            items,
            key=lambda item: (
                trending_score(item, now=current),
                item.created_at,
            ),
            reverse=True,
        )
        return _diversify([
            item.model_copy(
                update={
                    "ranking_reason": (
                        f"trending:{_interaction_count(item)}"
                        if _interaction_count(item)
                        else "recent"
                    )
                }
            )
            for item in scored
        ])

    scored = sorted(
        items,
        key=lambda item: (
            recommendation_score(
                item,
                now=current,
                following_author_ids=following,
                interest_tags=interests,
            ),
            item.created_at,
        ),
        reverse=True,
    )
    return _diversify([
        item.model_copy(
            update={
                "ranking_reason": _recommendation_reason(
                    item,
                    following_author_ids=following,
                    interest_tags=interests,
                )
            }
        )
        for item in scored
    ])
