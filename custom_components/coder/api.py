"""Async REST client for the Coder API.

Co-located here for v0.1; the long-term plan is to split this into a
standalone PyPI package (`coder-sdk-py`) before submitting upstream.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import aiohttp


class CoderAuthError(Exception):
    """Raised when the Coder API rejects the session token."""


class CoderApiError(Exception):
    """Raised for non-auth API errors."""


class CoderClient:
    """Thin async wrapper around the Coder REST API."""

    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        self._session = session
        self._base = url.rstrip("/") + "/"
        self._headers = {
            "Coder-Session-Token": token,
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = urljoin(self._base, path.lstrip("/"))
        async with self._session.request(
            method, url, headers=self._headers, json=json, params=params
        ) as resp:
            if resp.status == 401:
                raise CoderAuthError("Invalid Coder session token")
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
