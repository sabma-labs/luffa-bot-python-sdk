import json
import pytest
import respx
import httpx
import json 
from luffa_bot.client import AsyncLuffaClient, SEND_GROUP_URL
from luffa_bot.models import GroupMessagePayload, SimpleButton

pytestmark = pytest.mark.asyncio

@respx.mock
async def test_send_group_with_buttons():
    route = respx.post(SEND_GROUP_URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    client = AsyncLuffaClient("secret")
    payload = GroupMessagePayload(
        text="Choose:",
        button=[SimpleButton(name="OK", selector="ok", isHidden=0)],
        # dismissType optional
    )
    await client.send_to_group("group-1", payload, message_type=2)
    assert route.called
    req = route.calls.last.request
    body = json.loads(req.content.decode())
    assert body["type"] == "2"
    inner = json.loads(body["msg"])
    assert inner["text"] == "Choose:"
    assert inner["button"][0]["name"] == "OK"
