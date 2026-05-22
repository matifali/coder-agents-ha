"""The Coder integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CoderApiError, CoderAuthError, CoderClient
from .const import CONF_TOKEN, CONF_URL, DOMAIN, PLATFORMS
from .coordinator import CoderCoordinator
from .services import async_setup_services, async_unload_services

type CoderConfigEntry = ConfigEntry[CoderCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: CoderConfigEntry) -> bool:
    """Set up Coder from a config entry."""
    session = async_get_clientsession(hass)
    client = CoderClient(
        session=session,
        url=entry.data[CONF_URL],
        token=entry.data[CONF_TOKEN],
    )

    coordinator = CoderCoordinator(hass, client, base_url=entry.data[CONF_URL])
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform(p) for p in PLATFORMS]
    )

    async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CoderConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [Platform(p) for p in PLATFORMS]
    )
    if unload_ok and not hass.config_entries.async_entries(DOMAIN):
        async_unload_services(hass)
    return unload_ok
