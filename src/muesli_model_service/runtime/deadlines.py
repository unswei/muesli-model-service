import asyncio
from collections.abc import Awaitable


async def with_deadline[T](awaitable: Awaitable[T], deadline_ms: int | None) -> T:
    if deadline_ms is None:
        return await awaitable
    return await asyncio.wait_for(awaitable, timeout=deadline_ms / 1000)
