"""The Coder integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CoderClient
from .const import (
    AUTH_OAUTH2,
    CONF_AUTH_METHOD,
    CONF_AUTHORIZE_URL,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_TOKEN,
    CONF_TOKEN_URL,
    CONF_URL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import CoderCoordinator
from .services import async_setup_services, async_unload_services

type CoderConfigEntry = ConfigEntry[CoderCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: CoderConfigEntry) -> bool:
    """Set up Coder from a config entry."""
    session = async_get_clientsession(hass)
    url = entry.data[CONF_URL]

    if entry.data.get(CONF_AUTH_METHOD) == AUTH_OAUTH2:
        impl = config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce(
            hass,
            DOMAIN,
            entry.data[CONF_CLIENT_ID],
            authorize_url=entry.data[CONF_AUTHORIZE_URL],
            token_url=entry.data[CONF_TOKEN_URL],
            client_secret=entry.data[CONF_CLIENT_SECRET],
        )
        config_entry_oauth2_flow.async_register_implementation(hass, DOMAIN, impl)

        oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, impl)
        await oauth_session.async_ensure_token_valid()

        async def _refresh() -> str:
            await oauth_session.async_ensure_token_valid()
            return oauth_session.token["access_token"]

        client = CoderClient(
            session=session,
            url=url,
            bearer_token=oauth_session.token["access_token"],
            refresh=_refresh,
        )
    else:
        client = CoderClient(session=session, url=url, token=entry.data[CONF_TOKEN])

    coordinator = CoderCoordinator(hass, client, base_url=url)
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
