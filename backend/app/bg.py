"""Tracked fire-and-forget tasks for governance and notifications."""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger("agora.bg")
_background_tasks: set[asyncio.Task[Any]] = set()


def spawn(coro: Coroutine[Any, Any, Any], *, name: str | None = None) -> asyncio.Task[Any]:
    """Keep a strong reference to a background task until it finishes."""
    task = asyncio.create_task(coro, name=name)
    _background_tasks.add(task)
    task.add_done_callback(_on_done)
    return task


def _on_done(task: asyncio.Task[Any]) -> None:
    _background_tasks.discard(task)
    if task.cancelled():
        return
    exception = task.exception()
    if exception is not None:
        logger.error(
            "background task %s failed: %s",
            task.get_name(),
            exception,
            exc_info=(type(exception), exception, exception.__traceback__),
        )
