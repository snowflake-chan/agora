"""Unauthenticated, cache-friendly public syndication feeds."""

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime
from uuid import UUID
from xml.etree import ElementTree

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content_moderation import PUBLIC_MODERATION_STATUSES
from app.config import settings
from app.db import get_session
from app.db.models.content import Content
from app.db.models.patch import Patch


router = APIRouter()


@dataclass(frozen=True)
class PublicFeedEntry:
    id: UUID
    kind: str
    title: str
    content: str
    revision_number: int
    username: str
    published_at: datetime
    updated_at: datetime


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _base_url(request: Request) -> str:
    configured = settings.PUBLIC_SITE_URL.strip()
    return (configured or str(request.base_url)).rstrip("/")


def _entry_url(request: Request, entry: PublicFeedEntry) -> str:
    collection = "posts" if entry.kind == "post" else "patches"
    return f"{_base_url(request)}/{collection}/{entry.id}"


async def _load_entries(
    session: AsyncSession,
    *,
    limit: int,
) -> list[PublicFeedEntry]:
    posts = (
        await session.execute(
            select(Content)
            .where(
                Content.type == "post",
                Content.moderation_status.in_(PUBLIC_MODERATION_STATUSES),
            )
            .order_by(func.coalesce(Content.published_at, Content.created_at).desc())
            .limit(limit)
        )
    ).scalars().all()
    patches = (
        await session.execute(
            select(Patch)
            .where(Patch.status != "draft")
            .order_by(Patch.created_at.desc(), Patch.id.desc())
            .limit(limit)
        )
    ).scalars().all()

    entries = [
        PublicFeedEntry(
            id=post.id,
            kind="post",
            title=post.title or "Untitled post",
            content=post.content,
            revision_number=post.revision_number,
            username=post.author.username,
            published_at=_aware(post.published_at or post.created_at),
            updated_at=_aware(post.updated_at),
        )
        for post in posts
    ]
    entries.extend(
        PublicFeedEntry(
            id=patch.id,
            kind="patch",
            title=patch.title,
            content=patch.content,
            revision_number=patch.revision_number,
            username=patch.author.username,
            published_at=_aware(patch.created_at),
            updated_at=_aware(patch.updated_at),
        )
        for patch in patches
    )
    entries.sort(key=lambda item: (item.published_at, str(item.id)), reverse=True)
    return entries[:limit]


def _etag(entries: list[PublicFeedEntry]) -> str:
    identity = "\n".join(
        f"{entry.kind}:{entry.id}:v{entry.revision_number}:"
        f"{entry.updated_at.isoformat()}" for entry in entries
    )
    return f'"{hashlib.sha256(identity.encode("utf-8")).hexdigest()}"'


def _cache_headers(etag: str) -> dict[str, str]:
    return {
        "Cache-Control": "public, max-age=60, stale-while-revalidate=300",
        "ETag": etag,
    }


def _not_modified(request: Request, etag: str) -> Response | None:
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=_cache_headers(etag))
    return None


@router.get("/rss.xml")
async def rss_feed(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> Response:
    entries = await _load_entries(session, limit=limit)
    etag = _etag(entries)
    cached = _not_modified(request, etag)
    if cached is not None:
        return cached

    creator_namespace = "http://purl.org/dc/elements/1.1/"
    ElementTree.register_namespace("dc", creator_namespace)
    rss = ElementTree.Element("rss", {"version": "2.0"})
    channel = ElementTree.SubElement(rss, "channel")
    ElementTree.SubElement(channel, "title").text = "Agora public activity"
    ElementTree.SubElement(channel, "link").text = _base_url(request)
    ElementTree.SubElement(channel, "description").text = (
        "Public posts and community change proposals from Agora."
    )
    ElementTree.SubElement(channel, "language").text = "en"
    if entries:
        ElementTree.SubElement(channel, "lastBuildDate").text = format_datetime(
            max(entry.updated_at for entry in entries)
        )

    for entry in entries:
        item = ElementTree.SubElement(channel, "item")
        url = _entry_url(request, entry)
        ElementTree.SubElement(item, "title").text = entry.title
        ElementTree.SubElement(item, "link").text = url
        ElementTree.SubElement(item, "guid", {"isPermaLink": "true"}).text = url
        ElementTree.SubElement(item, "description").text = entry.content
        ElementTree.SubElement(
            item,
            f"{{{creator_namespace}}}creator",
        ).text = entry.username
        ElementTree.SubElement(item, "category").text = entry.kind
        ElementTree.SubElement(item, "pubDate").text = format_datetime(
            entry.published_at
        )

    payload = ElementTree.tostring(rss, encoding="utf-8", xml_declaration=True)
    return Response(
        content=payload,
        media_type="application/rss+xml; charset=utf-8",
        headers=_cache_headers(etag),
    )


@router.get("/feed.json")
async def json_feed(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> Response:
    entries = await _load_entries(session, limit=limit)
    etag = _etag(entries)
    cached = _not_modified(request, etag)
    if cached is not None:
        return cached

    base_url = _base_url(request)
    payload = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "Agora public activity",
        "home_page_url": base_url,
        "feed_url": f"{base_url}/api/v1/public/feed.json",
        "items": [
            {
                "id": f"{entry.kind}:{entry.id}",
                "url": _entry_url(request, entry),
                "title": entry.title,
                "content_text": entry.content,
                "date_published": entry.published_at.isoformat(),
                "date_modified": entry.updated_at.isoformat(),
                "authors": [{"name": entry.username}],
                "tags": [entry.kind],
            }
            for entry in entries
        ],
    }
    return JSONResponse(payload, headers=_cache_headers(etag))
