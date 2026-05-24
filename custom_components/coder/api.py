"""Async REST client for the Coder API.

Co-located here for v0.1; the long-term plan is to split this into a
standalone PyPI package (`coder-sdk-py`) before submitting upstream.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urljoin

import aiohttp


class CoderAuthError(Exception):
    """Raised when the Coder API rejects the current credential."""


class CoderApiError(Exception):
    """Raised for non-auth API errors."""


TokenRefresher = Callable[[], Awaitable[str]]


class CoderClient:
    """Thin async wrapper around the Coder REST API.

    Supports two auth modes:
      - Session token (Coder-Session-Token header) — long-lived user token.
      - OAuth2 bearer token — pass `bearer_token` plus an optional
        `refresh` coroutine that returns a fresh access token; on 401 the
        client calls `refresh()` once and retries the request.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        *,
        token: str | None = None,
        bearer_token: str | None = None,
        refresh: TokenRefresher | None = None,
    ) -> None:
        if (token is None) == (bearer_token is None):
            raise ValueError("Provide exactly one of token or bearer_token")
        self._session = session
        self._base = url.rstrip("/") + "/"
        self._token = token
        self._bearer = bearer_token
        self._refresh = refresh

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._token is not None:
            headers["Coder-Session-Token"] = self._token
        else:
            headers["Authorization"] = f"Bearer {self._bearer}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        _retry: bool = True,
    ) -> Any:
        url = urljoin(self._base, path.lstrip("/"))
        async with self._session.request(
            method, url, headers=self._headers(), json=json, params=params
        ) as resp:
            if resp.status == 401:
                if _retry and self._bearer is not None and self._refresh is not None:
                    self._bearer = await self._refresh()
                    return await self._request(
                        method, path, json=json, params=params, _retry=False
                    )
                raise CoderAuthError("Coder rejected the current credential")
            if resp.status >= 400:
                body = await resp.text()
                raise CoderApiError(f"{method} {path} -> {resp.status}: {body}")
            if resp.status == 204 or not resp.content_length:
                return None
            return await resp.json()

    async def get_authenticated_user(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v2/users/me")

    async def list_chats(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/api/experimental/chats")
        return data if isinstance(data, list) else []

    async def get_chat(self, chat_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/experimental/chats/{chat_id}")

    async def create_chat(
        self,
        *,
        organization_id: str,
        prompt: str,
        workspace_id: str | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "organization_id": organization_id,
            "content": [{"type": "text", "text": prompt}],
        }
        if workspace_id:
            body["workspace_id"] = workspace_id
        if system_prompt:
            body["system_prompt"] = system_prompt
        return await self._request("POST", "/api/experimental/chats", json=body)

    async def post_chat_message(self, chat_id: str, message: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/experimental/chats/{chat_id}/messages",
            json={"content": [{"type": "text", "text": message}]},
        )

    async def update_chat(
        self,
        chat_id: str,
        *,
        archived: bool | None = None,
        title: str | None = None,
    ) -> None:
        body: dict[str, Any] = {}
        if archived is not None:
            body["archived"] = archived
        if title is not None:
            body["title"] = title
        await self._request(
            "PATCH", f"/api/experimental/chats/{chat_id}", json=body
        )

    async def interrupt_chat(self, chat_id: str) -> None:
        await self._request(
            "POST", f"/api/experimental/chats/{chat_id}/interrupt"
        )
