"""Service registration for the Coder integration.

These services are the primary way to interact with chats from automations.
create_chat additionally fires a coder_chat_created event so that other
automations can trigger on chat creation without round-tripping.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import (
    ATTR_CHAT_ID,
    ATTR_MESSAGE,
    ATTR_PROMPT,
    ATTR_SYSTEM_PROMPT,
    ATTR_WORKSPACE_ID,
    DOMAIN,
    EVENT_CHAT_CREATED,
    SERVICE_ARCHIVE_CHAT,
    SERVICE_CREATE_CHAT,
    SERVICE_GET_CHAT,
    SERVICE_INTERRUPT_CHAT,
    SERVICE_SEND_CHAT_MESSAGE,
    SERVICE_UNARCHIVE_CHAT,
)
from .coordinator import CoderCoordinator

CREATE_CHAT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PROMPT): str,
        vol.Optional(ATTR_WORKSPACE_ID): str,
        vol.Optional(ATTR_SYSTEM_PROMPT): str,
    }
)

CHAT_ID_SCHEMA = vol.Schema({vol.Required(ATTR_CHAT_ID): str})

SEND_MESSAGE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_CHAT_ID): str, vol.Required(ATTR_MESSAGE): str}
)


def _first_coordinator(hass: HomeAssistant) -> CoderCoordinator:
    """Return the (typically single) Coder coordinator, raising if none.

    Today users have at most one Coder deployment in HA. If multi-deployment
    support is needed, add a `deployment` selector to the service schemas.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    for entry in entries:
        coordinator = getattr(entry, "runtime_data", None)
        if coordinator is not None:
            return coordinator
    raise HomeAssistantError("No Coder deployment is configured.")


def _coordinator_for_chat(hass: HomeAssistant, chat_id: str) -> CoderCoordinator:
    for entry in hass.config_entries.async_entries(DOMAIN):
        coordinator = getattr(entry, "runtime_data", None)
        if coordinator and chat_id in coordinator.data.chats:
            return coordinator
    # Fall back to first deployment — covers chats not yet in cache.
    return _first_coordinator(hass)


def async_setup_services(hass: HomeAssistant) -> None:
    """Register Coder services. Safe to call multiple times."""

    async def _create_chat(call: ServiceCall) -> ServiceResponse:
        coordinator = _first_coordinator(hass)
        org_id = coordinator.default_organization_id
        if not org_id:
            raise HomeAssistantError(
                "Coder integration has no cached organization ID; reload the entry."
            )
        chat = await coordinator.client.create_chat(
            organization_id=org_id,
            prompt=call.data[ATTR_PROMPT],
            workspace_id=call.data.get(ATTR_WORKSPACE_ID),
            system_prompt=call.data.get(ATTR_SYSTEM_PROMPT),
        )
        hass.bus.async_fire(
            EVENT_CHAT_CREATED,
            {
                "chat_id": chat.get("id"),
                "title": chat.get("title"),
                "workspace_id": chat.get("workspace_id"),
                "status": chat.get("status"),
            },
        )
        await coordinator.async_request_refresh()
        return {
            "chat_id": chat.get("id"),
            "title": chat.get("title"),
            "workspace_id": chat.get("workspace_id"),
            "status": chat.get("status"),
        }

    async def _send_message(call: ServiceCall) -> None:
        chat_id = call.data[ATTR_CHAT_ID]
        coordinator = _coordinator_for_chat(hass, chat_id)
        await coordinator.client.post_chat_message(chat_id, call.data[ATTR_MESSAGE])
        await coordinator.async_request_refresh()

    async def _interrupt(call: ServiceCall) -> None:
        chat_id = call.data[ATTR_CHAT_ID]
        coordinator = _coordinator_for_chat(hass, chat_id)
        await coordinator.client.interrupt_chat(chat_id)
        await coordinator.async_request_refresh()

    async def _archive(call: ServiceCall) -> None:
        chat_id = call.data[ATTR_CHAT_ID]
        coordinator = _coordinator_for_chat(hass, chat_id)
        await coordinator.client.update_chat(chat_id, archived=True)
        await coordinator.async_request_refresh()

    async def _unarchive(call: ServiceCall) -> None:
        chat_id = call.data[ATTR_CHAT_ID]
        coordinator = _coordinator_for_chat(hass, chat_id)
        await coordinator.client.update_chat(chat_id, archived=False)
        await coordinator.async_request_refresh()

    async def _get_chat(call: ServiceCall) -> ServiceResponse:
        chat_id = call.data[ATTR_CHAT_ID]
        coordinator = _coordinator_for_chat(hass, chat_id)
        chat = await coordinator.client.get_chat(chat_id)
        return {
            "chat_id": chat.get("id"),
            "title": chat.get("title"),
            "status": chat.get("status"),
            "workspace_id": chat.get("workspace_id"),
            "archived": chat.get("archived"),
            "has_unread": chat.get("has_unread"),
            "updated_at": chat.get("updated_at"),
        }

    registrations: list[tuple[str, Any, Any, SupportsResponse]] = [
        (SERVICE_CREATE_CHAT, _create_chat, CREATE_CHAT_SCHEMA, SupportsResponse.OPTIONAL),
        (SERVICE_SEND_CHAT_MESSAGE, _send_message, SEND_MESSAGE_SCHEMA, SupportsResponse.NONE),
        (SERVICE_INTERRUPT_CHAT, _interrupt, CHAT_ID_SCHEMA, SupportsResponse.NONE),
        (SERVICE_ARCHIVE_CHAT, _archive, CHAT_ID_SCHEMA, SupportsResponse.NONE),
        (SERVICE_UNARCHIVE_CHAT, _unarchive, CHAT_ID_SCHEMA, SupportsResponse.NONE),
        (SERVICE_GET_CHAT, _get_chat, CHAT_ID_SCHEMA, SupportsResponse.OPTIONAL),
    ]

    for name, handler, schema, supports_response in registrations:
        if hass.services.has_service(DOMAIN, name):
            continue
        hass.services.async_register(
            DOMAIN, name, handler, schema=schema, supports_response=supports_response
        )


def async_unload_services(hass: HomeAssistant) -> None:
    for service in (
        SERVICE_CREATE_CHAT,
        SERVICE_SEND_CHAT_MESSAGE,
        SERVICE_INTERRUPT_CHAT,
        SERVICE_ARCHIVE_CHAT,
        SERVICE_UNARCHIVE_CHAT,
        SERVICE_GET_CHAT,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
