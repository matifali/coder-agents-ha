"""Constants for the Coder integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "coder"

CONF_URL = "url"
CONF_TOKEN = "token"

# Changes arrive over the /chats/watch websocket; the poll is only a
# safety resync for anything the socket missed.
DEFAULT_SCAN_INTERVAL = timedelta(minutes=10)
WATCH_RECONNECT_MIN = 1
WATCH_RECONNECT_MAX = 60

ATTR_CHAT_ID = "chat_id"
ATTR_MESSAGE = "message"
ATTR_PROMPT = "prompt"
ATTR_WORKSPACE_ID = "workspace_id"
ATTR_SYSTEM_PROMPT = "system_prompt"
ATTR_TITLE = "title"
ATTR_LABELS = "labels"

SERVICE_CREATE_CHAT = "create_chat"
SERVICE_SEND_CHAT_MESSAGE = "send_chat_message"
SERVICE_INTERRUPT_CHAT = "interrupt_chat"
SERVICE_ARCHIVE_CHAT = "archive_chat"
SERVICE_UNARCHIVE_CHAT = "unarchive_chat"
SERVICE_GET_CHAT = "get_chat"

EVENT_CHAT_CREATED = "coder_chat_created"
EVENT_CHAT_STATUS_CHANGED = "coder_chat_status_changed"
EVENT_CHAT_TURN_FINISHED = "coder_chat_turn_finished"
EVENT_CHAT_ERROR = "coder_chat_error"
EVENT_CHAT_SUMMARY_UPDATED = "coder_chat_summary_updated"

PLATFORMS = ["sensor"]
