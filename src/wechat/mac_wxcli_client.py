"""macOS wx-cli data client.

Read path backed by the local ``wx`` CLI (wx-cli daemon) instead of WeFlow's
WCDB dylib. The daemon owns incremental state and per-shard decryption; this
client only shells out, normalizes messages into the same source-row shape
``MacHybridBackend`` already consumes, and drops self/system group traffic
the way ``mac_weflow_client`` drops ``is_send == 1`` rows.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 200


class MacWxCliClient:
    """Read new WeChat messages through the wx CLI's daemon transport."""

    def __init__(self, bin_path: str | None = None, timeout: float = 30.0):
        self.bin_path = str(bin_path or os.getenv("MAC_WXCLI_BIN", "wx")).strip() or "wx"
        try:
            self.timeout = float(os.getenv("MAC_WXCLI_TIMEOUT", "") or timeout)
        except ValueError:
            self.timeout = timeout
        self._last_error = ""

    def health(self) -> bool:
        try:
            self._run(["sessions", "--json", "--limit", "1"])
            return True
        except Exception as exc:
            self._last_error = str(exc)
            logger.debug("wx-cli health failed: %s", exc)
            return False

    def get_new_messages(
        self,
        state: dict[str, int] | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> dict:
        """Fetch messages appended since wx-cli's own last check.

        ``state`` is accepted for interface parity; the wx daemon persists its
        own incremental state in ``~/.wx-cli/last_check.json``, so the
        returned ``new_state`` is what the caller should keep passing back.
        """
        del state
        safe_limit = max(1, int(limit or DEFAULT_LIMIT))
        payload = self._run(["new-messages", "--json", "--limit", str(safe_limit)])
        messages = []
        for raw in payload.get("messages") or []:
            if not isinstance(raw, dict):
                continue
            normalized = _normalize_message(raw)
            if normalized:
                messages.append(normalized)
        messages.sort(key=lambda item: int(item.get("timestamp") or 0))
        new_state = payload.get("new_state")
        return {
            "count": len(messages),
            "messages": messages,
            "new_state": new_state if isinstance(new_state, dict) else {},
        }

    def close(self) -> None:
        return None

    def _run(self, args: list[str]) -> dict:
        try:
            result = subprocess.run(
                [self.bin_path, *args],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"wx CLI ({self.bin_path}) failed: {exc}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(
                f"wx {' '.join(args)} exited {result.returncode}: {detail[:300]}"
            )
        return _parse_json_object(result.stdout)


def _parse_json_object(text: str) -> dict:
    """Parse the first JSON object, skipping daemon-start banner lines."""
    start = text.find("{")
    if start < 0:
        raise RuntimeError(f"wx CLI printed no JSON: {text.strip()[:200]}")
    try:
        payload = json.loads(text[start:])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"wx CLI printed invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("wx CLI JSON payload is not an object")
    return payload


def _normalize_message(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Map one wx-cli message into the mac_hybrid source-row shape."""
    username = str(raw.get("username") or "").strip()
    content = str(raw.get("content") or "").strip()
    if not username or not content:
        return None
    is_group = bool(raw.get("is_group")) or username.endswith("@chatroom")
    sender_id = str(raw.get("sender_username") or "").strip()
    sender_label = str(raw.get("sender") or "").strip()
    if is_group and not sender_id:
        # wx-cli does not filter self/system traffic: group messages without a
        # resolvable sender are our own sends or system entries. Replying to
        # those would loop, so they are dropped here.
        return None
    if not is_group and not sender_label:
        # Private messages carry no sender_username; an empty sender label
        # means our own send (the peer always resolves to a display name).
        return None
    sender_display = (
        sender_label
        or str(raw.get("sender_contact_display") or "").strip()
        or sender_id
        or "unknown"
    )
    return {
        "timestamp": _to_int(raw.get("timestamp")),
        "sender": sender_display,
        "sender_name": sender_display,
        "sender_id": sender_id or sender_display,
        "type": str(raw.get("type") or "文本").strip(),
        "content": content,
        "local_id": _to_int(raw.get("local_id")),
        "chat": str(raw.get("chat") or username),
        "username": username,
        "is_group": is_group,
        "chat_type": str(raw.get("chat_type") or ("group" if is_group else "private")),
    }


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
