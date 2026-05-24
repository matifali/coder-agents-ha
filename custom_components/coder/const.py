"""Constants for the Coder integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "coder"

CONF_URL = "url"
CONF_TOKEN = "token"
CONF_AUTH_METHOD = "auth_method"

AUTH_TOKEN = "token"
AUTH_OAUTH2 = "oauth2"

CONF_CLIENT_ID = "client_id"
CONF_AUTHORIZE_URL = "authorize_url"
CONF_TOKEN_URL = "token_url"

WELL_KNOWN_PATH = "/.well-known/oauth-authorization-server"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

ATTR_CHAT_ID = "chat_id"
ATTR_MESSAGE = "message"
ATTR_PROMPT = "prompt"
ATTR_WORKSPACE_ID = "workspace_id"
ATTR_SYSTEM_PROMPT = "system_prompt"

SERVICE_CREATE_CHAT = "create_chat"
SERVICE_SEND_CHAT_MESSAGE = "send_chat_message"
SERVICE_INTERRUPT_CHAT = "interrupt_chat"
SERVICE_ARCHIVE_CHAT = "archive_chat"
SERVICE_UNARCHIVE_CHAT = "unarchive_chat"
SERVICE_GET_CHAT = "get_chat"

EVENT_CHAT_CREATED = "coder_chat_created"
EVENT_CHAT_STATUS_CHANGED = "coder_chat_status_changed"

PLATFORMS = ["sensor"]
