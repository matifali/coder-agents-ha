"""Aggregate chat sensors for the Coder deployment.

We intentionally do NOT create one device/entity per chat — chats are
ephemeral. Use the services (create_chat, send_chat_message, etc.) and
the coder_chat_created / coder_chat_status_changed events for automation.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CoderConfigEntry
from .entity import CoderDeploymentEntity

CHAT_STATUSES = [
    "waiting",
    "pending",
    "running",
    "paused",
    "completed",
    "error",
    "requires_action",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CoderConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            TotalChatsSensor(coordinator, entry),
            RunningChatsSensor(coordinator, entry),
            RequiresActionChatsSensor(coordinator, entry),
            LastChatSensor(coordinator, entry),
        ]
    )


def _non_archived(chats: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in chats.values() if not c.get("archived")]


class TotalChatsSensor(CoderDeploymentEntity, SensorEntity):
    _attr_translation_key = "total_chats"
    _attr_icon = "mdi:chat"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_total_chats"
        self._attr_name = "Total chats"

    @property
    def native_value(self) -> int:
        return len(_non_archived(self.coordinator.data.chats))


class RunningChatsSensor(CoderDeploymentEntity, SensorEntity):
    _attr_translation_key = "running_chats"
    _attr_icon = "mdi:robot"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_running_chats"
        self._attr_name = "Running chats"

    @property
    def native_value(self) -> int:
        return sum(
            1
            for c in _non_archived(self.coordinator.data.chats)
            if c.get("status") == "running"
        )


class RequiresActionChatsSensor(CoderDeploymentEntity, SensorEntity):
    _attr_translation_key = "requires_action_chats"
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_requires_action_chats"
        self._attr_name = "Chats requiring action"

    @property
    def native_value(self) -> int:
        return sum(
            1
            for c in _non_archived(self.coordinator.data.chats)
            if c.get("status") == "requires_action"
        )


class LastChatSensor(CoderDeploymentEntity, SensorEntity):
    """Most recently updated chat — state is its status, attributes carry the rest."""

    _attr_translation_key = "last_chat"
    _attr_device_class = "enum"
    _attr_options = CHAT_STATUSES
    _attr_icon = "mdi:chat-processing"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_chat"
        self._attr_name = "Last chat"

    def _latest(self) -> dict[str, Any] | None:
        chats = _non_archived(self.coordinator.data.chats)
        if not chats:
            return None
        return max(chats, key=lambda c: c.get("updated_at") or "")

    @property
    def native_value(self) -> str | None:
        chat = self._latest()
        return chat.get("status") if chat else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        chat = self._latest()
        if not chat:
            return {}
        return {
            "chat_id": chat.get("id"),
            "title": chat.get("title"),
            "workspace_id": chat.get("workspace_id"),
            "agent_id": chat.get("agent_id"),
            "updated_at": chat.get("updated_at"),
            "has_unread": chat.get("has_unread"),
        }
