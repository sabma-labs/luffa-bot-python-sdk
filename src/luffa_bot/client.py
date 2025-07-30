from __future__ import annotations
import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Literal, cast
import httpx
from .models import (
    IncomingEnvelope, IncomingMessage,
    TextMessagePayload, GroupMessagePayload
)
from .exceptions import LuffaError

BASE = "https://apibot.luffa.im/robot"
RECEIVE_URL = f"{BASE}/receive"
SEND_URL = f"{BASE}/send"
SEND_GROUP_URL = f"{BASE}/sendGroup"

class AsyncLuffaClient:
    def __init__(self, robot_key: str, *, timeout: float = 15.0):
        self.robot_key = robot_key
        self._client = httpx.AsyncClient(timeout=timeout, headers={"Content-Type": "application/json"})

    async def aclose(self):
        await self._client.aclose()

    async def _post(self, url: str, body: Dict[str, Any]) -> httpx.Response:
        resp = await self._client.post(url, json=body)
        return resp

    @staticmethod
    def _parse_messages(raw_messages: List[Any]) -> List[IncomingMessage]:
        parsed: List[IncomingMessage] = []
        for raw in raw_messages:
            try:
                obj = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                try:
                    obj = json.loads(json.loads(raw))
                except Exception:
                    continue
            parsed.append(
                IncomingMessage(
                    atList=obj.get("atList", []),
                    text=obj.get("text", ""),
                    urlLink=obj.get("urlLink"),
                    msgId=str(obj.get("msgId", "")),
                    uid=obj.get("uid"),
                )
            )
        return parsed

    async def receive(self) -> List[IncomingEnvelope]:
        resp = await self._post(RECEIVE_URL, {"secret": self.robot_key})
        if resp.status_code != 200:
            raise LuffaError(f"receive failed: {resp.status_code} - {resp.text}")

        try:
            data = resp.json()
        except Exception as e:
            raise LuffaError(f"invalid JSON from receive: {e}") from e

        if isinstance(data, dict) and "data" in data:
            data = data["data"]

        envelopes: List[IncomingEnvelope] = []
        for raw_item in (data or []):
            # If the API returned a string, parse it into a dict
            if isinstance(raw_item, str):
                try:
                    item = json.loads(raw_item)
                except Exception:
                    # Skip if it's not valid JSON
                    continue
            else:
                item = raw_item

            if not isinstance(item, dict):
                continue  # Skip if it's still not a dict

            uid = str(item.get("uid", ""))
            count = int(item.get("count", 0))

            # Narrow the type field to Literal[0,1] if using strict typing
            typ_raw = int(item.get("type", 0))
            typ: Literal[0, 1] = 0 if typ_raw == 0 else 1

            raw_msgs = item.get("message", []) or []
            messages = self._parse_messages(raw_msgs)

            envelopes.append(
                IncomingEnvelope(uid=uid, count=count, messages=messages, type=typ)
            )
        return envelopes

    async def send_to_user(self, uid: str, payload: str | TextMessagePayload) -> None:
        # Convert payload to a plain dict ready for JSON encoding
        if isinstance(payload, str):
            msg_obj = {"text": payload}
        elif is_dataclass(payload):
            # asdict handles nested dataclasses automatically
            msg_obj = {k: v for k, v in asdict(payload).items() if v is not None}
        else:
            # Fallback (shouldn't be needed if you always pass dataclass or str)
            msg_obj = {k: v for k, v in payload.__dict__.items() if v is not None}

        body = {"secret": self.robot_key, "uid": str(uid), "msg": json.dumps(msg_obj)}
        resp = await self._post(SEND_URL, body)
        if resp.status_code != 200:
            raise LuffaError(f"send_to_user failed: {resp.status_code} - {resp.text}")

    async def send_to_group(
        self,
        uid: str,
        payload: str | GroupMessagePayload,
        *,
        message_type: int = 1,
    ) -> None:
        if isinstance(payload, str):
            msg_obj = {"text": payload}
        else:
            # Enforce exclusivity before serializing
            if getattr(payload, "confirm", None) and getattr(payload, "button", None):
                raise ValueError("Only one of 'confirm' or 'button' may be set.")

            if is_dataclass(payload):
                msg_obj = {k: v for k, v in asdict(payload).items() if v is not None}
            else:
                msg_obj = {k: v for k, v in payload.__dict__.items() if v is not None}

        body = {
            "secret": self.robot_key,
            "uid": str(uid),
            "msg": json.dumps(msg_obj),
            "type": str(int(message_type)),
        }
        resp = await self._post(SEND_GROUP_URL, body)
        if resp.status_code != 200:
            raise LuffaError(f"send_to_group failed: {resp.status_code} - {resp.text}")
