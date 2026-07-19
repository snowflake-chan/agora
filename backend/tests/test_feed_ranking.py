from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.posts.feed import rank_feed_items
from app.schemas.post import FeedItem


NOW = datetime(2026, 7, 20, tzinfo=timezone.utc)


def _item(
    *,
    author_id: UUID | None = None,
    hours_old: int = 1,
    likes: int = 0,
    replies: int = 0,
    tags: list[str] | None = None,
    title: str = "Item",
) -> FeedItem:
    return FeedItem(
        id=uuid4(),
        type="post",
        title=title,
        content="content",
        author_id=author_id or uuid4(),
        author_username="author",
        created_at=NOW - timedelta(hours=hours_old),
        tags=tags,
        like_count=likes,
        reply_count=replies,
    )


def test_recommended_feed_boosts_followed_authors():
    followed_author = uuid4()
    followed = _item(
        author_id=followed_author,
        hours_old=6,
        title="Followed",
    )
    fresh = _item(hours_old=1, title="Fresh")

    ranked = rank_feed_items(
        [fresh, followed],
        mode="recommended",
        following_author_ids={followed_author},
        now=NOW,
    )

    assert ranked[0].id == followed.id
    assert ranked[0].ranking_reason == "followed_author"


def test_trending_feed_rewards_recent_engagement():
    engaged = _item(hours_old=24, replies=5, likes=3, title="Engaged")
    quiet = _item(hours_old=1, title="Quiet")

    ranked = rank_feed_items(
        [quiet, engaged],
        mode="trending",
        now=NOW,
    )

    assert ranked[0].id == engaged.id
    assert ranked[0].ranking_reason == "trending:8"


def test_following_feed_filters_and_uses_chronological_order():
    followed_author = uuid4()
    newest = _item(author_id=followed_author, hours_old=1, title="Newest")
    older = _item(author_id=followed_author, hours_old=8, title="Older")
    unrelated = _item(hours_old=0, title="Unrelated")

    ranked = rank_feed_items(
        [older, unrelated, newest],
        mode="following",
        following_author_ids={followed_author},
        now=NOW,
    )

    assert [item.id for item in ranked] == [newest.id, older.id]


def test_ranked_feeds_limit_same_author_to_two_consecutive_items():
    dominant_author = uuid4()
    dominant = [
        _item(
            author_id=dominant_author,
            likes=20 - index,
            title=f"Dominant {index}",
        )
        for index in range(3)
    ]
    alternative = _item(likes=1, title="Alternative")

    ranked = rank_feed_items(
        [*dominant, alternative],
        mode="trending",
        now=NOW,
    )

    assert ranked[0].author_id == dominant_author
    assert ranked[1].author_id == dominant_author
    assert ranked[2].author_id != dominant_author
