import pytest
import respx
import httpx
import asyncio
from luffa.client import AsyncLuffaClient, RECEIVE_URL
from luffa.polling import run

pytestmark = pytest.mark.asyncio

@respx.mock
async def test_run_invokes_handler_once(monkeypatch):
    # one poll returns one envelope/message, second poll empty then we stop
    responses = [
        httpx.Response(200, json=[{
            "uid": "user-123",
            "count": "1",
            "message": ['{"atList":[],"text":"ping","urlLink":null,"msgId":"x1"}'],
            "type": "0",
        }]),
        httpx.Response(200, json=[]),
    ]
    route = respx.post(RECEIVE_URL).mock(side_effect=responses)

    client = AsyncLuffaClient("secret")
    seen = []

    async def handler(msg, env, cl):
        seen.append((msg.text, env.uid))
        # stop after first handle by cancelling outer task
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await run(
            client,
            handler=handler,
            interval=0.01,
            concurrency=1,
            dedupe=True,
        )
    assert route.called
    assert seen == [("ping", "user-123")]
