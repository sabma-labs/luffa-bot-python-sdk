from __future__ import annotations
import asyncio
from collections import deque
from typing import Awaitable, Callable, List, Optional, Set

from .client import AsyncLuffaClient
from .models import IncomingEnvelope, IncomingMessage

# Handler invoked by the runner
Handler = Callable[[IncomingMessage, IncomingEnvelope, AsyncLuffaClient], Awaitable[None]]

# The "next" function passed into middleware; same shape as the handler
NextFn = Callable[[IncomingMessage, IncomingEnvelope, AsyncLuffaClient], Awaitable[None]]

# Middleware sees (msg, env, client, next)
Middleware = Callable[[IncomingMessage, IncomingEnvelope, AsyncLuffaClient, NextFn], Awaitable[None]]


async def _apply_middleware(
    middlewares: List[Middleware],
    handler: Handler,
    msg: IncomingMessage,
    env: IncomingEnvelope,
    client: AsyncLuffaClient,
) -> None:
    """
    Apply middlewares in order, then call the handler.
    Each middleware receives a 'next' function with signature NextFn.
    """

    async def call_chain(i: int, m: IncomingMessage, e: IncomingEnvelope) -> None:
        # If we've exhausted middlewares, call the final handler
        if i == len(middlewares):
            await handler(m, e, client)
            return

        # Define the 'next' function passed to this middleware
        async def next_handler(m2: IncomingMessage, e2: IncomingEnvelope, c2: AsyncLuffaClient) -> None:
            # We expect c2 to be the same as 'client'; ignore or assert as needed
            await call_chain(i + 1, m2, e2)

        # Invoke the i-th middleware
        await middlewares[i](m, e, client, next_handler)

    await call_chain(0, msg, env)


async def run(
    client: AsyncLuffaClient,
    *,
    handler: Handler,
    interval: float = 1.0,
    concurrency: int = 1,
    middleware: Optional[List[Middleware]] = None,
    on_error: Optional[Callable[[Exception], Awaitable[None]]] = None,
    dedupe: bool = True,
    max_seen_ids: int = 10_000,
) -> None:
    """
    Poll /receive forever at `interval` seconds; dispatch each message to `handler`.
    Features:
      - Concurrency limit via a semaphore
      - Dedupe by msgId with capped memory
      - Middleware pipeline and error hook
    """
    sem = asyncio.Semaphore(concurrency)
    middlewares = middleware or []
    seen: Set[str] = set()
    seen_order: deque[str] = deque()

    async def process(msg: IncomingMessage, env: IncomingEnvelope) -> None:
        try:
            async with sem:
                if middlewares:
                    await _apply_middleware(middlewares, handler, msg, env, client)
                else:
                    await handler(msg, env, client)
        except Exception as e:
            if on_error:
                await on_error(e)
            else:
                # Default: print to stdout; in production, wire to logging
                print(f"[luffa] handler error: {e}")

    while True:
        try:
            envelopes = await client.receive()
            tasks: List[asyncio.Task[None]] = []
            for env in envelopes:
                for msg in env.messages:
                    if dedupe and msg.msgId:
                        if msg.msgId in seen:
                            continue
                        seen.add(msg.msgId)
                        seen_order.append(msg.msgId)
                        if len(seen) > max_seen_ids:
                            # Evict oldest entry to prevent unbounded growth
                            seen.discard(seen_order.popleft())
                    tasks.append(asyncio.create_task(process(msg, env)))
            if tasks:
                await asyncio.gather(*tasks)
        except Exception as e:
            if on_error:
                await on_error(e)
            else:
                print(f"[luffa] poll error: {e}")
        await asyncio.sleep(interval)
