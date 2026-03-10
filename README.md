# Luffa Bot Python SDK

[![PyPI version](https://img.shields.io/pypi/v/luffa-bot-python-sdk.svg)](https://pypi.org/project/luffa-bot-python-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/luffa-bot-python-sdk.svg)](https://pypi.org/project/luffa-bot-python-sdk/)
[![License](https://img.shields.io/pypi/l/luffa-bot-python-sdk.svg)](https://github.com/sabma-labs/luffa-bot-python-sdk/blob/main/LICENSE)

Async, OpenAI-style SDK for building bots for the **Luffa messaging platform**.

## Features

* Fully **async** (based on `httpx` and `asyncio`)
* **OpenAI-style interface** (`luffa_bot.robot_key = "..."`)
* Simple APIs: `receive()`, `send_to_user()`, `send_to_group()`, and `run()`
* Advanced **group messages** with buttons, confirms, and @mentions
* Built-in **deduplication**, **concurrency control**, and **middleware support**
* CLI for quick bot setup

---

## Installation

```bash
pip install luffa-bot-python-sdk
```

Requires Python 3.9+.

---

## Quickstart

```python
import asyncio
import luffa_bot

# Set the robot secret key (or use LUFFA_ROBOT_SECRET env var)
luffa_bot.robot_key = "YOUR_ROBOT_SECRET"

async def main():
    # Poll once for messages
    envelopes = await luffa_bot.receive()
    for env in envelopes:
        for msg in env.messages:
            if env.type == 0:
                await luffa_bot.send_to_user(env.uid, f"You said: {msg.text}")
            else:
                await luffa_bot.send_to_group(env.uid, f"[group] {msg.text}")

asyncio.run(main())
```

---

## Running a Bot Loop

Use the built-in `run()` method to continuously poll and handle messages.

```python
import asyncio
import luffa_bot

luffa_bot.robot_key = "YOUR_ROBOT_SECRET"

async def handler(msg, env, client):
    if "help" in msg.text.lower():
        await client.send_to_user(env.uid, "How can I help?")
    else:
        await client.send_to_user(env.uid, f"Echo: {msg.text}")

asyncio.run(luffa_bot.run(handler, interval=1.0, concurrency=5))
```

### Features of `run()`

* Automatic deduplication by `msgId` (FIFO-capped memory)
* Configurable polling interval
* Concurrency limit (process multiple messages at once)
* Middleware and error hook support

---

## Sending Group Messages with Buttons

```python
from luffa_bot.models import GroupMessagePayload, SimpleButton

payload = GroupMessagePayload(
    text="Pick an option:",
    button=[SimpleButton(name="OK", selector="ok")]
)

await luffa_bot.send_to_group("GROUP_ID", payload, message_type=2)
```

* `message_type=1` → Text only
* `message_type=2` → Buttons/advanced messages

---

## Environment Variables

* `LUFFA_ROBOT_SECRET`: Default robot key if not set via `luffa_bot.robot_key`.

---

## CLI

A CLI is included for quick bot testing:

```bash
export LUFFA_ROBOT_SECRET="..."

# Run an echo bot
luffa-bot run --interval 1.0

# Send DM to a user
luffa-bot send --uid <USER_ID> --text "Hello"

# Send message to a group with buttons
luffa-bot send-group --uid <GROUP_ID> --text "Hi group" --with-buttons
```

---

## Development

```bash
pip install -e ".[dev]"
```

* **Tests:** `pytest`
* **Lint:** `ruff check .`
* **Type-check:** `mypy .`

---

## Changelog

### 0.1.2 (2026-03-10)

* **Fix:** `_ensure_client()` was recreating the `httpx.AsyncClient` (and leaking the old connection pool) on every API call. Connection pooling now works correctly across calls.
* **Fix:** Dedupe eviction used `set.pop()` (arbitrary removal). Now uses FIFO eviction via `deque` so oldest IDs are dropped first.
* **Fix:** CLI `send` and `send-group` commands now properly close the HTTP client on exit.
* **Fix:** GitHub Actions workflow directory renamed from `workflow/` to `workflows/` — CI/CD was silently not running.
* **Security:** Removed unused dependencies `anyio` and `pydantic` from `install_requires` (unnecessary install footprint).
* **Compat:** Replaced deprecated `asyncio.get_event_loop()` with `asyncio.get_running_loop()` in example bot.
* Added `__version__` export (`luffa_bot.__version__`).

### 0.1.1

* Minor fixes and improvements.

### 0.1.0 (initial release)

* Initial async SDK with `receive()`, `send_to_user()`, `send_to_group()`, and `run()`.
* Middleware pipeline, deduplication, concurrency control.
* CLI entry point (`luffa-bot`).

---

## Author

**Niraj Kulkarni** *(Sabma Labs, University of Surrey)*

---

## License

Apache License 2.0
