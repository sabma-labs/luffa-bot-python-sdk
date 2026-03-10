"""
Luffa Bot Python SDK (Async)

This SDK is designed for building bots for the Luffa messaging platform,
mirroring the ergonomics of the `openai` package.

Usage:
    import luffa_bot

    luffa_bot.robot_key = "YOUR_SECRET"

    # Receive messages
    envelopes = await luffa_bot.receive()

    # Send a message
    await luffa_bot.send_to_user("<UID>", "Hello")

    # Run a bot loop
    await luffa_bot.run(handler=your_handler)
"""

from .client import AsyncLuffaClient
from .polling import run as _run
from ._globals import get_default_client, set_robot_key
from .models import (
    IncomingEnvelope,
    IncomingMessage,
    TextMessagePayload,
    GroupMessagePayload,
    ConfirmButton,
    SimpleButton,
    AtMention,
)
from .exceptions import LuffaError

__version__ = "0.1.2"

robot_key: str | None = None  #: Global API key, similar to `openai.api_key`


def _ensure_client() -> AsyncLuffaClient:
    """Return a global AsyncLuffaClient, ensuring `robot_key` is configured."""
    global robot_key
    if robot_key is not None:
        set_robot_key(robot_key)
    return get_default_client()


async def receive():
    """
    Poll once for messages from the Luffa robot API.

    Returns:
        List[IncomingEnvelope]: envelopes containing messages.
    """
    client = _ensure_client()
    return await client.receive()


async def send_to_user(uid: str, payload: str | TextMessagePayload):
    """
    Send a message directly to a user.

    Args:
        uid: User ID.
        payload: Text message or TextMessagePayload object.
    """
    client = _ensure_client()
    return await client.send_to_user(uid, payload)


async def send_to_group(uid: str, payload: str | GroupMessagePayload, message_type: int = 1):
    """
    Send a message to a group.

    Args:
        uid: Group ID.
        payload: Text message or GroupMessagePayload.
        message_type: 1 for text, 2 for buttons/advanced.
    """
    client = _ensure_client()
    return await client.send_to_group(uid, payload, message_type=message_type)


async def run(
    handler,
    *,
    interval: float = 1.0,
    concurrency: int = 1,
    middleware=None,
    on_error=None,
    dedupe: bool = True,
    max_seen_ids: int = 10_000,
):
    """
    Run the bot backend in a continuous polling loop.

    Args:
        handler: async function (msg, env, client)
        interval: polling interval (default: 1.0s)
        concurrency: max concurrent handlers
        middleware: optional list of async middlewares
        on_error: async error handler
        dedupe: drop messages with duplicate msgId
        max_seen_ids: cap dedupe memory
    """
    client = _ensure_client()
    return await _run(
        client,
        handler=handler,
        interval=interval,
        concurrency=concurrency,
        middleware=middleware,
        on_error=on_error,
        dedupe=dedupe,
        max_seen_ids=max_seen_ids,
    )


__all__ = [
    "__version__",
    "AsyncLuffaClient",
    "LuffaError",
    "IncomingEnvelope",
    "IncomingMessage",
    "TextMessagePayload",
    "GroupMessagePayload",
    "ConfirmButton",
    "SimpleButton",
    "AtMention",
    "receive",
    "send_to_user",
    "send_to_group",
    "run",
    "robot_key",
]
