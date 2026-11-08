"""DataUpdateCoordinator for Coder.

Chats are kept current by the /api/v2/chats/watch websocket, the same
feed the Coder Agents UI uses. A full list fetch runs whenever the socket
(re)connects and on a slow interval as a safety resync.

Only root chats are tracked; subagent chats are ignored. Workspaces are
intentionally out of scope: each chat carries its ``workspace_id`` for
users who need to link the two in their own automations.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import CoderApiError, CoderAuthError, CoderClient
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_CHAT_ERROR,
    EVENT_CHAT_STATUS_CHANGED,
    EVENT_CHAT_SUMMARY_UPDATED,
    EVENT_CHAT_TURN_FINISHED,
    WATCH_RECONNECT_MAX,
    WATCH_RECONNECT_MIN,
)

_LOGGER = logging.getLogger(__name__)

# Mirrors the Agents UI: a turn completes in "waiting", or in "paused" when
# the queue head is under edit. A turn that ends in "error" did not complete.
TURN_FINISHED_STATUSES = frozenset({"waiting", "paused"})


@dataclass
class CoderData:
    """Snapshot of Coder chats, keyed by ID."""

    chats: dict[str, dict[str, Any]] = field(default_factory=dict)


def _ts(chat: dict[str, Any], key: str) -> datetime | None:
    value = chat.get(key)
    return dt_util.parse_datetime(value) if isinstance(value, str) else None


def _merge_watched_chat(
    cached: dict[str, Any], watched: dict[str, Any], kind: str
) -> dict[str, Any]:
    """Merge a watch event's chat into the cached one, scoped by event kind.

    Follows the Agents UI's mergeWatchedChatSummary: each event carries a
    full chat snapshot, but only some of its fields are current. Status
    comes only from status_change, title only from title_change, and each
    summary only from its own event. Row fields are ordered by updated_at.
    """
    merged = dict(cached)
    if kind == "title_change":
        cached_at, watched_at = _ts(cached, "title_updated_at"), _ts(watched, "title_updated_at")
        if cached_at is None or watched_at is None or cached_at < watched_at:
            for key in ("title", "title_source", "title_updated_at"):
                merged[key] = watched.get(key)
        return merged
    if kind == "summary_change":
        merged["last_turn_summary"] = watched.get("last_turn_summary")
        return merged
    if kind == "chat_summary_change":
        merged["summary"] = watched.get("summary")
        return merged

    cached_at, watched_at = _ts(cached, "updated_at"), _ts(watched, "updated_at")
    if cached_at is not None and watched_at is not None and watched_at < cached_at:
        return merged
    merged["updated_at"] = watched.get("updated_at")
    merged["workspace_id"] = watched.get("workspace_id") or cached.get("workspace_id")
    merged["last_error"] = watched.get("last_error")
    if kind == "status_change":
        merged["status"] = watched.get("status")
        # The UI marks a chat unread on every status event; the next full
        # list fetch reconciles it with the server's read cursor.
        merged["has_unread"] = True
    elif kind == "project_change":
        merged["project_id"] = watched.get("project_id")
    return merged


class CoderCoordinator(DataUpdateCoordinator[CoderData]):
    """Tracks chats via the watch websocket; fires chat events."""

    default_organization_id: str | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry | None,
        client: CoderClient,
        base_url: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self.base_url = base_url.rstrip("/")
        self._previous_statuses: dict[str, str] = {}

    def chat_url(self, chat_id: str | None) -> str | None:
        if not chat_id:
            return None
        return f"{self.base_url}/agents/{chat_id}"

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
        # Forget chats that were archived while we weren't watching, so an
        # unarchive later starts fresh instead of firing a stale transition.
        for chat_id in self._previous_statuses.keys() - chats.keys():
            del self._previous_statuses[chat_id]
        for chat in chats.values():
            self._observe_status(chat)
        return CoderData(chats=chats)

    async def async_watch(self) -> None:
        """Consume the chat watch stream forever, reconnecting with backoff."""
        backoff = WATCH_RECONNECT_MIN
        while True:
            try:
                async for event in self.client.watch_chats(on_open=self.async_refresh):
                    backoff = WATCH_RECONNECT_MIN
                    self._handle_watch_event(event)
                _LOGGER.debug("Chat watch stream closed; reconnecting")
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "Chat watch stream failed (%s); retrying in %ss", err, backoff
                )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, WATCH_RECONNECT_MAX)

    def _handle_watch_event(self, event: dict[str, Any]) -> None:
        kind = event.get("kind")
        chat = event.get("chat") or {}
        chat_id = chat.get("id")
        if not kind or not chat_id or chat.get("parent_chat_id") or self.data is None:
            return

        chats = dict(self.data.chats)
        cached = chats.get(chat_id)

        if kind == "deleted":
            # The server sends "deleted" when a chat is archived.
            if chats.pop(chat_id, None) is None:
                return
            self._previous_statuses.pop(chat_id, None)
        elif cached is None:
            # "created" also fires on unarchive. Other kinds land here when
            # the chat appeared between our last list fetch and now.
            if chat.get("archived"):
                return
            chats[chat_id] = chat
            self._observe_status(chat)
        else:
            merged = _merge_watched_chat(cached, chat, kind)
            if merged == cached:
                return
            chats[chat_id] = merged
            if kind == "status_change":
                self._observe_status(merged)
            elif kind == "summary_change" and merged.get("last_turn_summary"):
                self._fire(EVENT_CHAT_SUMMARY_UPDATED, merged, summary=merged["last_turn_summary"])

        self.async_set_updated_data(CoderData(chats=chats))

    def _observe_status(self, chat: dict[str, Any]) -> None:
        chat_id = chat["id"]
        status = chat.get("status")
        if status is None:
            return
        previous = self._previous_statuses.get(chat_id)
        self._previous_statuses[chat_id] = status
        if previous is None or previous == status:
            return
        self._fire(EVENT_CHAT_STATUS_CHANGED, chat, **{"from": previous, "to": status})
        if previous == "running" and status in TURN_FINISHED_STATUSES:
            self._fire(EVENT_CHAT_TURN_FINISHED, chat, status=status)
        elif status == "error":
            last_error = chat.get("last_error") or {}
            self._fire(EVENT_CHAT_ERROR, chat, error=last_error.get("message"))

    def _fire(self, event_type: str, chat: dict[str, Any], **extra: Any) -> None:
        chat_id = chat.get("id")
        self.hass.bus.async_fire(
            event_type,
            {
                "chat_id": chat_id,
                "chat_url": self.chat_url(chat_id),
                "title": chat.get("title"),
                "workspace_id": chat.get("workspace_id"),
                **extra,
            },
        )
