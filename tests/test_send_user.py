import json
import pytest
import respx
import httpx
from luffa_bot.client import AsyncLuffaClient, SEND_URL

pytestmark = pytest.mark.asyncio

@respx.mock
async def test_send_to_user_sends_json_string_msg():
    route = respx.post(SEND_URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    client = AsyncLuffaClient("secret")
    await client.send_to_user("user-1", "Hi")
    assert route.called
    req = route.calls.last.request
    payload = json.loads(req.content.decode())
    assert payload["secret"] == "secret"
    assert payload["uid"] == "user-1"
    inner = json.loads(payload["msg"])
    assert inner["text"] == "Hi"
