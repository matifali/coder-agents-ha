"""DataUpdateCoordinator for Coder.

Polls only chats; workspaces are intentionally out of scope. Workspace
information surfaces as chat metadata (``workspace_id``) for users who
need to link chats to workspaces in their own automations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CoderApiError, CoderAuthError, CoderClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, EVENT_CHAT_STATUS_CHANGED

_LOGGER = logging.getLogger(__name__)


@dataclass
class CoderData:
    """Snapshot of Coder chats, keyed by ID."""

    chats: dict[str, dict[str, Any]] = field(default_factory=dict)


class CoderCoordinator(DataUpdateCoordinator[CoderData]):
    """Polls chats; fires status-change events."""

    default_organization_id: str | None = None

    def __init__(self, hass: HomeAssistant, client: CoderClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self._previous_statuses: dict[str, str] = {}

    async def _async_setup(self) -> None:
        """Cache the user's primary organization for create_chat."""
        try:
            user = await self.client.get_authenticated_user()
        except (CoderAuthError, CoderApiError) as err:
            raise UpdateFailed(f"Initial auth failed: {err}") from err
        org_ids = user.get("organization_ids") or []
        if org_ids:
            self.default_organization_id = org_ids[0]

    async def _async_update_data(self) -> CoderData:
        try:
            chats_list = await self.client.list_chats()
        except CoderAuthError as err:
            raise UpdateFailed(f"Auth failed: {err}") from err
        except CoderApiError as err:
            raise UpdateFailed(str(err)) from err

        chats = {chat["id"]: chat for chat in chats_list if "id" in chat}
        self._fire_status_changes(chats)
        return CoderData(chats=chats)

    def _fire_status_changes(self, chats: dict[str, dict[str, Any]]) -> None:
        for chat_id, chat in chats.items():
            status = chat.get("status")
            if status is None:
                continue
            previous = self._previous_statuses.get(chat_id)
            if previous is not None and previous != status:
                self.hass.bus.async_fire(
                    EVENT_CHAT_STATUS_CHANGED,
                    {
                        "chat_id": chat_id,
                        "title": chat.get("title"),
                        "workspace_id": chat.get("workspace_id"),
                        "from": previous,
                        "to": status,
                    },
                )
            self._previous_statuses[chat_id] = status
