from __future__ import annotations
import os
from .client import AsyncLuffaClient

_default_client: AsyncLuffaClient | None = None
_robot_key: str | None = None

def set_robot_key(key: str | None):
    global _robot_key, _default_client
    if key != _robot_key:
        _robot_key = key
        _default_client = None  # reset so we re-create with new key

def get_default_client() -> AsyncLuffaClient:
    global _default_client, _robot_key
    if _default_client is None:
        key = _robot_key or os.getenv("LUFFA_ROBOT_SECRET")
        if not key:
            raise ValueError(
                "Please set luffa.robot_key or LUFFA_ROBOT_SECRET before calling the API."
            )
        _default_client = AsyncLuffaClient(robot_key=key)
    return _default_client
