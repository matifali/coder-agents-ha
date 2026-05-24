"""Coder OAuth2 discovery + Dynamic Client Registration helpers.

Kept minimal: HA's config_entry_oauth2_flow framework owns PKCE, the
authorization-code dance, token storage, and refresh. We only need to
probe RFC 8414 metadata and register a public client via RFC 7591.
"""

from __future__ import annotations

from typing import Any

import aiohttp

from .const import WELL_KNOWN_PATH


class OAuthError(Exception):
    """Raised when discovery or DCR fails."""


async def discover(
    session: aiohttp.ClientSession, base_url: str
) -> dict[str, Any] | None:
    """Fetch RFC 8414 metadata. Returns None if discovery is absent.

    Returns None on 404 or when the response lacks the endpoints we need
    for DCR + authorization-code flow; raises OAuthError on transport or
    non-404 HTTP errors so the caller can decide whether to surface them.
    """
    url = base_url.rstrip("/") + WELL_KNOWN_PATH
    try:
        async with session.get(url, allow_redirects=True) as resp:
            if resp.status == 404:
                return None
            if resp.status != 200:
                raise OAuthError(f"discovery {resp.status}")
            data = await resp.json()
    except aiohttp.ClientError as err:
        raise OAuthError(f"discovery failed: {err}") from err
    if "registration_endpoint" not in data or "authorization_endpoint" not in data:
        return None
    return data


async def register_client(
    session: aiohttp.ClientSession,
    registration_endpoint: str,
    redirect_uri: str,
    client_name: str,
) -> str:
    """Dynamically register a public PKCE client; returns the new client_id.

    Coder issues a client_secret even when we request
    `token_endpoint_auth_method: "none"`, but the negotiated auth method
    is still "none" so we never send the secret on subsequent requests.
    """
    body = {
        "redirect_uris": [redirect_uri],
        "client_name": client_name,
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
    }
    try:
        async with session.post(registration_endpoint, json=body) as resp:
            data = await resp.json()
            if resp.status >= 400:
                raise OAuthError(
                    f"DCR {resp.status}: {data.get('error_description') or data}"
                )
    except aiohttp.ClientError as err:
        raise OAuthError(f"DCR failed: {err}") from err
    client_id = data.get("client_id")
    if not client_id:
        raise OAuthError("DCR response missing client_id")
    return client_id
