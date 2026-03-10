"""
examples/dev_bot.py

End-to-end test runner for luffa-bot-python-sdk using a real Luffa robot key.

Features
- Runs a polling loop using luffa_bot.polling.run(...)
- Handles commands in DMs and groups:
    /help
    /ping
    /echo <text>
    /dm <uid> <text>
    /g <group_id> <text>
    /buttons
    /mention <uid> <name>
    /whoami

- Middleware that logs and measures handler latency.
- Optional startup messages to a test user/group to verify sending.
- DEBUG mode that logs every HTTP request/response and per-poll summaries.

Usage:
  pip install -e .[dev]

  # Windows (cmd)
  set LUFFA_ROBOT_SECRET=your_secret

  # macOS/Linux
  export LUFFA_ROBOT_SECRET=your_secret

  python examples/dev_bot.py --interval 1.0 --concurrency 3 \
      --test-user <USER_UID> \
      --test-group <GROUP_UID> \
      --debug
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from typing import List, Optional

import luffa_bot
from luffa_bot.client import AsyncLuffaClient
from luffa_bot.models import (
    GroupMessagePayload,
    SimpleButton,
    AtMention,
    TextMessagePayload,
)
from luffa_bot.polling import run as polling_run

# -------- Logging setup --------
logger = logging.getLogger("dev_bot")
_stream = logging.StreamHandler(sys.stdout)
_stream.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s"))
logger.addHandler(_stream)
logger.setLevel(logging.INFO)


# -------- Middleware examples --------
async def logging_middleware(msg, env, client: AsyncLuffaClient, nxt):
    logger.info("RX: type=%s uid=%s msgId=%s text=%r", env.type, env.uid, msg.msgId, msg.text)
    await nxt(msg, env, client)
    logger.info("TX: handled msgId=%s", msg.msgId)


async def timing_middleware(msg, env, client: AsyncLuffaClient, nxt):
    start = asyncio.get_running_loop().time()
    try:
        await nxt(msg, env, client)
    finally:
        dur = (asyncio.get_running_loop().time() - start) * 1000.0
        logger.info("Handled in %.1f ms", dur)


# -------- Command helpers --------
def _split_args(text: str) -> List[str]:
    return text.strip().split()


async def _send_help(env_uid: str, client: AsyncLuffaClient, is_group: bool):
    help_text = (
        "Commands:\n"
        "/help\n"
        "/ping\n"
        "/echo <text>\n"
        "/dm <user_uid> <text>\n"
        "/g <group_uid> <text>\n"
        "/buttons (group only)\n"
        "/mention <uid> <name> (group only)\n"
        "/whoami\n"
    )
    if is_group:
        await client.send_to_group(env_uid, help_text, message_type=1)
    else:
        await client.send_to_user(env_uid, help_text)


async def _handle_buttons(env_uid: str, client: AsyncLuffaClient):
    payload = GroupMessagePayload(
        text="Pick one:",
        button=[
            SimpleButton(name="OK", selector="ok", isHidden=0),
            SimpleButton(name="More", selector="more", isHidden=0),
        ],
    )
    await client.send_to_group(env_uid, payload, message_type=2)


async def _handle_mention(env_uid: str, client: AsyncLuffaClient, did: str, display_name: str):
    at_text = f"@{display_name}"
    text = f"Mentioning {at_text} in this message."
    at = AtMention(
        name=display_name,
        did=did,
        length=len(at_text),
        location=text.index(at_text),
        userType=0,
    )
    payload = GroupMessagePayload(text=text, atList=[at.__dict__])
    await client.send_to_group(env_uid, payload, message_type=1)


# -------- Main message handler --------
async def handler(msg, env, client: AsyncLuffaClient):
    text = (msg.text or "").strip()
    parts = _split_args(text)
    is_group = (env.type == 1)

    # Button selectors echo back
    if text in {"ok", "more"} and is_group:
        await client.send_to_group(env.uid, f"Button '{text}' received.", message_type=1)
        return

    if not parts:
        await _send_help(env.uid, client, is_group=is_group)
        return

    cmd = parts[0].lower()

    if cmd == "/help":
        await _send_help(env.uid, client, is_group=is_group)
        return

    if cmd == "/ping":
        reply = "pong"
        if is_group:
            await client.send_to_group(env.uid, reply, message_type=1)
        else:
            await client.send_to_user(env.uid, reply)
        return

    if cmd == "/whoami":
        who = f"Context: {'group' if is_group else 'dm'} | env.uid={env.uid}"
        if is_group:
            await client.send_to_group(env.uid, who, message_type=1)
        else:
            await client.send_to_user(env.uid, who)
        return

    if cmd == "/echo":
        payload = " ".join(parts[1:]) or "(nothing)"
        if is_group:
            await client.send_to_group(env.uid, f"echo: {payload}", message_type=1)
        else:
            await client.send_to_user(env.uid, f"echo: {payload}")
        return

    if cmd == "/dm" and len(parts) >= 3:
        target_uid = parts[1]
        payload = " ".join(parts[2:])
        await client.send_to_user(target_uid, payload or "(empty)")
        if is_group:
            await client.send_to_group(env.uid, f"Sent DM to {target_uid}", message_type=1)
        else:
            await client.send_to_user(env.uid, f"Sent DM to {target_uid}")
        return

    if cmd == "/g" and len(parts) >= 3:
        target_gid = parts[1]
        payload = " ".join(parts[2:])
        await client.send_to_group(target_gid, payload or "(empty)", message_type=1)
        if is_group:
            await client.send_to_group(env.uid, f"Sent to group {target_gid}", message_type=1)
        else:
            await client.send_to_user(env.uid, f"Sent to group {target_gid}")
        return

    if cmd == "/buttons":
        if not is_group:
            await client.send_to_user(env.uid, "This command is group-only.")
            return
        await _handle_buttons(env.uid, client)
        return

    if cmd == "/mention" and is_group and len(parts) >= 3:
        did, display_name = parts[1], " ".join(parts[2:])
        await _handle_mention(env.uid, client, did, display_name)
        return

    # default fallback
    if is_group:
        await client.send_to_group(env.uid, "Unknown command. Try /help", message_type=1)
    else:
        await client.send_to_user(env.uid, "Unknown command. Try /help")


# -------- Error hook --------
async def on_error(exc: Exception):
    logger.error("Error in poll/handler: %s", exc, exc_info=False)


# -------- Startup self-test (optional) --------
async def send_startup_tests(client: AsyncLuffaClient, test_user: Optional[str], test_group: Optional[str]):
    logger.info(f"Trying startup message to user={test_user}, group={test_group}")
    if test_user:
        await client.send_to_user(test_user, TextMessagePayload(text="✅ Bot online (DM)."))
        logger.info("Startup DM sent to %s", test_user)
    if test_group:
        await client.send_to_group(test_group, "✅ Bot online (group).", message_type=1)
        logger.info("Startup group message sent to %s", test_group)


# -------- Debug wrappers --------
def wrap_client_with_debug(client: AsyncLuffaClient, enable_debug: bool) -> AsyncLuffaClient:
    """
    Wrap AsyncLuffaClient._post and .receive with debug logging.
    """
    if not enable_debug:
        return client

    orig_post = client._post
    async def _post_debug(url, body):
        try:
            logger.debug("HTTP POST %s payload=%s", url, json.dumps(body, ensure_ascii=False))
        except Exception:
            logger.debug("HTTP POST %s payload=<unserializable>", url)
        resp = await orig_post(url, body)
        try:
            j = resp.json()
            logger.debug("HTTP RESP %s status=%s json=%s", url, resp.status_code, json.dumps(j, ensure_ascii=False))
        except Exception:
            try:
                text = (await resp.aread()).decode(errors="replace")
            except Exception:
                text = "<non-text response>"
            logger.debug("HTTP RESP %s status=%s text=%s", url, resp.status_code, text)
        return resp
    client._post = _post_debug  # type: ignore[attr-defined]

    orig_receive = client.receive
    async def _receive_debug():
        envs = await orig_receive()
        total_msgs = sum(len(e.messages) for e in envs)
        logger.debug("POLL SUMMARY -> %d envelopes, %d messages", len(envs), total_msgs)
        for i, e in enumerate(envs):
            logger.debug("  env[%d]: uid=%s type=%s count=%s msgs=%d", i, e.uid, e.type, e.count, len(e.messages))
            for j, m in enumerate(e.messages):
                logger.debug("    msg[%d]: id=%s text=%r", j, m.msgId, m.text)
        return envs
    client.receive = _receive_debug  # type: ignore[assignment]
    return client


# -------- Entrypoint --------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser("dev-bot", description="Real-bot E2E test for luffa-bot-python-sdk")
    p.add_argument("--secret", help="Robot secret key (or set LUFFA_ROBOT_SECRET).")
    p.add_argument("--interval", type=float, default=1.0, help="Polling interval seconds (default 1).")
    p.add_argument("--concurrency", type=int, default=3, help="Concurrent handler tasks (default 3).")
    p.add_argument("--test-user", help="Optional: send a startup message to this user UID.")
    p.add_argument("--test-group", help="Optional: send a startup message to this group UID.")
    p.add_argument("--debug", action="store_true", help="Enable verbose HTTP and polling logs.")
    return p.parse_args()


async def amain():
    args = parse_args()

    # Logging level
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("DEBUG logging enabled")

    # Configure global SDK key (OpenAI-style)
    luffa_bot.robot_key = args.secret or os.getenv("LUFFA_ROBOT_SECRET")
    if not luffa_bot.robot_key:
        raise SystemExit("Please provide --secret or set LUFFA_ROBOT_SECRET")

    # Build a client and wrap it with debug
    client = AsyncLuffaClient(luffa_bot.robot_key)
    client = wrap_client_with_debug(client, enable_debug=args.debug)

    # Smoke test: send startup messages (optional)
    await send_startup_tests(client, args.test_user, args.test_group)

    # One-time smoke receive BEFORE loop so you immediately see what's coming back right now
    try:
        envs = await client.receive()
        total_msgs = sum(len(e.messages) for e in envs)
        logger.info("Initial receive -> %d envelopes, %d messages", len(envs), total_msgs)
    except Exception as e:
        logger.error("Initial receive failed: %s", e)

    logger.info("Starting bot loop: interval=%.2fs concurrency=%d", args.interval, args.concurrency)

    # Use the polling runner directly so our debug-wrapped client is used
    try:
        await polling_run(
            client,
            handler=handler,
            interval=args.interval,
            concurrency=args.concurrency,
            middleware=[logging_middleware, timing_middleware],
            on_error=on_error,
            dedupe=True,
            max_seen_ids=20_000,
        )
    except KeyboardInterrupt:
        logger.info("Shutting down (Ctrl+C).")


if __name__ == "__main__":
    asyncio.run(amain())
