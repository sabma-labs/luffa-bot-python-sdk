from __future__ import annotations
import asyncio
from typing import Awaitable, Callable, Iterable, List, Optional, Set
from .client import AsyncLuffaClient
from .models import IncomingEnvelope, IncomingMessage

Handler = Callable[[IncomingMessage, IncomingEnvelope, AsyncLuffaClient], Awaitable[None]]
Middleware = Callable[[IncomingMessage, IncomingEnvelope, Handler], Awaitable[None]]

async def _apply_middleware(middlewares: List[Middleware], handler: Handler, msg, env, client):
    async def call_chain(i: int):
        if i == len(middlewares):
            return await handler(msg, env, client)
        async def next_handler(m=msg, e=env):
            return await call_chain(i + 1)
        return await middlewares[i](msg, env, next_handler)
    return await call_chain(0)

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
):
    """
    Poll /receive forever at `interval` seconds; dispatch each message to `handler`.
    Tasks are limited by `concurrency`. Duplicate msgIds are dropped if `dedupe=True`.
    """
    sem = asyncio.Semaphore(concurrency)
    middlewares = middleware or []
    seen: Set[str] = set()

    async def process(msg: IncomingMessage, env: IncomingEnvelope):
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
                # default: print
                print(f"[luffa] handler error: {e}")

    while True:
        try:
            envelopes = await client.receive()
            tasks: List[asyncio.Task] = []
            for env in envelopes:
                for msg in env.messages:
                    if dedupe and msg.msgId:
                        if msg.msgId in seen:
                            continue
                        seen.add(msg.msgId)
                        if len(seen) > max_seen_ids:
                            seen.pop()
                    tasks.append(asyncio.create_task(process(msg, env)))
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=False)
        except Exception as e:
            if on_error:
                await on_error(e)
            else:
                print(f"[luffa] poll error: {e}")
        await asyncio.sleep(interval)
