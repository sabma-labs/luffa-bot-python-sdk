from __future__ import annotations
import hashlib
import ast
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
    def _coerce_to_dict(raw: Any) -> dict | None:
        """
        Robustly convert a raw message item into a dict.
        Handles:
          - dict directly
          - JSON string (once or twice encoded)
          - single-quoted dict-like strings (ast.literal_eval fallback)
        """
        if isinstance(raw, dict):
            return raw

        if isinstance(raw, bytes):
            try:
                raw = raw.decode("utf-8", errors="replace")
            except Exception:
                return None

        if isinstance(raw, str):
            s = raw.strip()

            # Try json.loads once or twice
            for _ in range(2):
                try:
                    obj = json.loads(s)
                    if isinstance(obj, dict):
                        return obj
                    # Sometimes first loads returns another JSON string
                    if isinstance(obj, str):
                        s = obj
                        continue
                    # If it’s a list with a single dict
                    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                        return obj[0]
                except Exception:
                    break

            # Last resort: single-quoted Python dict strings
            try:
                obj2 = ast.literal_eval(s)
                if isinstance(obj2, dict):
                    return obj2
            except Exception:
                return None

        return None

    @staticmethod
    def _extract_text(obj: dict) -> str:
        # Primary
        text = obj.get("text")
        if text:
            return str(text)
        # Fallbacks some deployments use
        for key in ("msg", "content", "message"):
            v = obj.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        # If urlLink is present and text missing, surface it
        url = obj.get("urlLink")
        if isinstance(url, str) and url.strip():
            return url.strip()
        return ""

    @staticmethod
    def _extract_msg_id(obj: dict, raw_fingerprint: str) -> str:
        # Primary and common variants
        for key in ("msgId", "msgid", "mid", "message_id", "id"):
            v = obj.get(key)
            if v is not None and str(v).strip():
                return str(v)
        # Synthesize a stable id if missing so dedupe still works
        return hashlib.sha1(raw_fingerprint.encode("utf-8")).hexdigest()

    @staticmethod
    def _fingerprint_for_dedupe(obj: dict) -> str:
        try:
            return json.dumps(obj, sort_keys=True, ensure_ascii=False)
        except Exception:
            return repr(obj)

    @staticmethod
    def _parse_messages(raw_messages: List[Any]) -> List[IncomingMessage]:
        parsed: List[IncomingMessage] = []
        for raw in (raw_messages or []):
            obj = AsyncLuffaClient._coerce_to_dict(raw)
            if not isinstance(obj, dict):
                # skip unparseable entries
                continue

            fp = AsyncLuffaClient._fingerprint_for_dedupe(obj)
            text = AsyncLuffaClient._extract_text(obj)
            msg_id = AsyncLuffaClient._extract_msg_id(obj, fp)

            parsed.append(
                IncomingMessage(
                    atList=obj.get("atList", []) or [],
                    text=text,
                    urlLink=obj.get("urlLink"),
                    msgId=str(msg_id),
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
