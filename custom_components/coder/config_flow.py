"""Config flow for Coder."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .api import CoderApiError, CoderAuthError, CoderClient
from .const import (
    AUTH_OAUTH2,
    AUTH_TOKEN,
    CONF_AUTH_METHOD,
    CONF_AUTHORIZE_URL,
    CONF_CLIENT_ID,
    CONF_TOKEN,
    CONF_TOKEN_URL,
    CONF_URL,
    DOMAIN,
)
from .oauth import OAuthError, discover, register_client

_LOGGER = logging.getLogger(__name__)

STEP_URL_SCHEMA = vol.Schema({vol.Required(CONF_URL): str})
STEP_TOKEN_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): str})


class CoderConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Coder config flow.

    Prefers OAuth2 + DCR when the Coder server advertises RFC 8414 metadata
    and HA has an HTTPS-reachable URL; otherwise falls back to a session
    token form. The OAuth2 path is invisible to users whose deployments do
    not meet both prerequisites.
    """

    DOMAIN = DOMAIN
    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self._url: str | None = None
        self._client_id: str | None = None
        self._metadata: dict[str, Any] | None = None

    @property
    def logger(self) -> logging.Logger:
        return _LOGGER

    @property
    def extra_data(self) -> dict[str, Any]:
        """Persisted alongside the OAuth2 token at entry creation."""
        assert self._url is not None
        assert self._client_id is not None
        assert self._metadata is not None
        return {
            CONF_URL: self._url,
            CONF_AUTH_METHOD: AUTH_OAUTH2,
            CONF_CLIENT_ID: self._client_id,
            CONF_AUTHORIZE_URL: self._metadata["authorization_endpoint"],
            CONF_TOKEN_URL: self._metadata["token_endpoint"],
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_URL_SCHEMA
            )

        url = user_input[CONF_URL].rstrip("/")
        await self.async_set_unique_id(url)
        self._abort_if_unique_id_configured()
        self._url = url

        session = async_get_clientsession(self.hass)
        try:
            metadata = await discover(session, url)
        except OAuthError as err:
            _LOGGER.debug("Discovery failed for %s: %s", url, err)
            metadata = None

        redirect_uri = self._oauth_redirect_uri()

        if metadata is None or redirect_uri is None:
            return await self.async_step_token()

        try:
            client_id = await register_client(
                session,
                metadata["registration_endpoint"],
                redirect_uri,
                client_name="Home Assistant — Coder Agents",
            )
        except OAuthError as err:
            _LOGGER.warning("DCR failed for %s: %s", url, err)
            return self.async_abort(reason="dcr_failed")

        self._metadata = metadata
        self._client_id = client_id

        impl = config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce(
            self.hass,
            DOMAIN,
            client_id,
            authorize_url=metadata["authorization_endpoint"],
            token_url=metadata["token_endpoint"],
        )
        config_entry_oauth2_flow.async_register_implementation(
            self.hass, DOMAIN, impl
        )

        return await super().async_step_pick_implementation(
            user_input={"implementation": DOMAIN}
        )

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._url is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            token = user_input[CONF_TOKEN]
            session = async_get_clientsession(self.hass)
            client = CoderClient(session=session, url=self._url, token=token)
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
                    title=user.get("username") or self._url,
                    data={
                        CONF_URL: self._url,
                        CONF_AUTH_METHOD: AUTH_TOKEN,
                        CONF_TOKEN: token,
                    },
                )

        return self.async_show_form(
            step_id="token", data_schema=STEP_TOKEN_SCHEMA, errors=errors
        )

    async def async_oauth_create_entry(
        self, data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Finalize OAuth2 entry — verify token works, then persist."""
        assert self._url is not None
        session = async_get_clientsession(self.hass)
        client = CoderClient(
            session=session,
            url=self._url,
            bearer_token=data["token"]["access_token"],
        )
        try:
            user = await client.get_authenticated_user()
        except (CoderAuthError, CoderApiError) as err:
            _LOGGER.warning("OAuth2 token rejected by Coder: %s", err)
            return self.async_abort(reason="oauth2_failed")

        return self.async_create_entry(
            title=user.get("username") or self._url,
            data={**data, **self.extra_data},
        )

    def _oauth_redirect_uri(self) -> str | None:
        """Return a callback URL Coder will accept, or None.

        Coder DCR accepts either an HTTPS redirect_uri (any host) or a
        loopback HTTP one (127.0.0.1, ::1, localhost). We try HTTPS
        first; if HA has no HTTPS URL we fall back to plain HTTP only
        when the resolved host is loopback.
        """
        try:
            base = get_url(
                self.hass,
                allow_internal=False,
                require_current_request=True,
                require_ssl=True,
                require_standard_port=True,
            )
            return f"{base}/auth/external/callback"
        except NoURLAvailableError:
            pass

        try:
            base = get_url(
                self.hass,
                require_current_request=True,
                require_ssl=False,
            )
        except NoURLAvailableError:
            return None

        from urllib.parse import urlparse

        host = urlparse(base).hostname
        if host in ("localhost", "127.0.0.1", "::1"):
            return f"{base}/auth/external/callback"
        return None
