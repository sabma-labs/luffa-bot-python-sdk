import pytest
import respx
import httpx
from luffa_bot.client import AsyncLuffaClient
from luffa_bot.client import RECEIVE_URL

pytestmark = pytest.mark.asyncio

@respx.mock
async def test_receive_parses_json_string_messages():
    sample = [
        {
            "uid": "user-123",
            "count": "1",
            "message": ['{"atList":[],"text":"hello","urlLink":null,"msgId":"m1"}'],
            "type": "0",
        }
    ]
    route = respx.post(RECEIVE_URL).mock(return_value=httpx.Response(200, json=sample))

    client = AsyncLuffaClient("secret")
    envs = await client.receive()

    assert route.called
    assert len(envs) == 1
    env = envs[0]
    assert env.uid == "user-123"
    assert env.type == 0
    assert env.messages[0].text == "hello"
    assert env.messages[0].msgId == "m1"
