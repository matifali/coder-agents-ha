"""Base entity for the Coder deployment device."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CoderCoordinator


class CoderDeploymentEntity(CoordinatorEntity[CoderCoordinator]):
    """Entity bound to a single Coder deployment (one config entry)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CoderCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Coder",
            model="Coder deployment",
            configuration_url=entry.data.get("url"),
        )
