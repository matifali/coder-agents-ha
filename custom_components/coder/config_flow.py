"""Config flow for Coder."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CoderApiError, CoderAuthError, CoderClient
from .const import CONF_TOKEN, CONF_URL, DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_TOKEN): str,
    }
)


class CoderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Coder.

    TODO: implement async_step_reauth before this leaves v0.1 — session
    tokens expire and the coordinator otherwise loops on UpdateFailed.
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            token = user_input[CONF_TOKEN]

            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = CoderClient(session=session, url=url, token=token)
            try:
                user = await client.get_authenticated_user()
            except CoderAuthError:
                errors["base"] = "invalid_auth"
            except CoderApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user.get("username") or url,
                    data={CONF_URL: url, CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )
