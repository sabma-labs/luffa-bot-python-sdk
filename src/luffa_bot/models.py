from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Literal

# -------- Incoming --------

@dataclass
class IncomingMessage:
    atList: List[Dict[str, Any]]
    text: str
    urlLink: Optional[str]
    msgId: str
    uid: Optional[str] = None   # present in group payloads as sender id sometimes

@dataclass
class IncomingEnvelope:
    uid: str           # user or group id (depends on 'type')
    count: int
    messages: List[IncomingMessage]
    type: Literal[0, 1]  # 0 single chat, 1 group chat

# -------- Outgoing --------

@dataclass
class TextMessagePayload:
    text: str
    atList: Optional[List[Dict[str, Any]]] = None

@dataclass
class ConfirmButton:
    name: str
    selector: str
    type: Literal["destructive", "default"] = "default"
    isHidden: Literal[0, 1] = 0

@dataclass
class SimpleButton:
    name: str
    selector: str
    isHidden: Literal[0, 1] = 0

@dataclass
class AtMention:
    name: str
    did: str
    length: int
    location: int
    userType: Literal[0] = 0

@dataclass
class GroupMessagePayload(TextMessagePayload):
    confirm: Optional[List[ConfirmButton]] = None
    button: Optional[List[SimpleButton]] = None
    dismissType: Optional[Literal["select", "dismiss"]] = None
