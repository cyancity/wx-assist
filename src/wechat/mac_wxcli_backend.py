"""macOS hybrid backend reading through the wx CLI.

Same read/write split as ``mac_hybrid_backend``: messages come from the local
WeChat databases (via wx-cli's daemon instead of WeFlow's WCDB dylib, so no
``libWCDB.dylib`` or ``all_keys.json`` placement is required on the wx-assist
side), replies go out through the Accessibility automation in
``mac_ui_backend``.
"""

from __future__ import annotations

import logging

from .mac_hybrid_backend import MacHybridBackend
from .mac_wxcli_client import MacWxCliClient

logger = logging.getLogger(__name__)


class MacWxCliBackend(MacHybridBackend):
    """MacHybridBackend with the wx-cli daemon as the read transport."""

    def __init__(
        self,
        groups: list[str] | None = None,
        poll_sec: float = 1.0,
        store=None,
        client=None,
        automation=None,
        limit: int = 200,
    ):
        super().__init__(
            groups=groups,
            poll_sec=poll_sec,
            store=store,
            client=client or MacWxCliClient(),
            automation=automation,
            limit=limit,
        )

    def health_status(self) -> str:
        if self._service_error:
            return "wxcli_down"
        return "wxcli_ok" if self._client.health() else "wxcli_down"
