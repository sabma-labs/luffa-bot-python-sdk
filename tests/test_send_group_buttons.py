import json
import pytest
import respx
import httpx
from luffa.client import AsyncLuffaClient, SEND_GROUP_URL
from luffa.models import GroupMessagePayload, SimpleButton

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
    body = route.calls.last.request.json()
    assert body["type"] == "2"
    inner = json.loads(body["msg"])
    assert inner["text"] == "Choose:"
    assert inner["button"][0]["name"] == "OK"
