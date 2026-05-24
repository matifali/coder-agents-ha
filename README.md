# Coder for Home Assistant

A Home Assistant custom integration for [Coder](https://coder.com) that lets you
drive **Coder chats (AI agents)** from automations.

The primary use case is automation-driven: an automation creates a chat with a
prompt and (optionally) a workspace and system prompt, then chains on the
returned `chat_id` or listens for the `coder_chat_created` /
`coder_chat_status_changed` events. There's also a small set of aggregate
sensors so dashboards can show how many chats are running.

## Status

v0.2 — early. Distributable as a custom HACS repo. Workspaces are intentionally
out of scope for this version; each chat carries its `workspace_id` as a sensor
attribute so you can join them yourself if needed.

## Sensors

A single device per Coder deployment, with four sensors:

- **Total chats** — count of non-archived chats
- **Running chats** — count with status `running`
- **Chats requiring action** — count with status `requires_action`
- **Last chat** — status of the most recently updated chat. Attributes include
  `chat_id`, `title`, `workspace_id`, `agent_id`, `updated_at`, `has_unread`.

## Services

| Service | Returns | Description |
|---|---|---|
| `coder.create_chat` | ✅ `chat_id`, `chat_url`, `title`, `status`, `workspace_id` | Create a new chat with `prompt` (and optional `workspace_id` / `system_prompt`). Also fires `coder_chat_created`. |
| `coder.send_chat_message` | — | Post a `message` to an existing `chat_id`. |
| `coder.interrupt_chat` | — | Interrupt a running chat. |
| `coder.archive_chat` | — | Archive a chat. |
| `coder.unarchive_chat` | — | Restore an archived chat. |
| `coder.get_chat` | ✅ `chat_id`, `chat_url`, `title`, `status`, `workspace_id`, `archived`, `has_unread`, `updated_at` | Fetch current status/metadata for a chat. |

`chat_url` points at the chat in the Coder UI (`<base_url>/agents/<chat_id>`) so
automations can deep-link straight to it.

**Coder's REST API does not expose hard chat deletion** — archive is the
closest equivalent.

## Events

- `coder_chat_created` — fired when `coder.create_chat` succeeds. Payload: `chat_id`, `chat_url`, `title`, `workspace_id`, `status`.
- `coder_chat_status_changed` — fired on each poll when a chat's status changes. Payload: `chat_id`, `chat_url`, `title`, `workspace_id`, `from`, `to`.

## Example automation

```yaml
automation:
  - alias: Run nightly deps audit
    triggers:
      - trigger: time
        at: "03:00:00"
    actions:
      - action: coder.create_chat
        data:
          prompt: >-
            Review my open dependabot PRs and summarise risk in 3 bullets.
          system_prompt: Be terse. Bullet points only.
        response_variable: chat
      - action: notify.mobile_app
        data:
          message: "Started Coder chat {{ chat.title }} — {{ chat.chat_url }}"

  - alias: Notify when Coder chat needs me
    triggers:
      - trigger: event
        event_type: coder_chat_status_changed
        event_data:
          to: requires_action
    actions:
      - action: notify.mobile_app
        data:
          message: >-
            Chat {{ trigger.event.data.title }} needs your input.
            {{ trigger.event.data.chat_url }}
```

A more complete worked example (a weekday DevEx audit with helpers and a
"notify when done" automation) lives under [`examples/devex_audit/`](examples/devex_audit).

## Install (HACS, custom repository)

1. HACS → ⋮ → Custom repositories → add `https://github.com/matifali/coder-agents-ha`, category **Integration**.
2. Install **Coder** from HACS, restart Home Assistant.
3. Settings → Devices & Services → **Add Integration** → **Coder**.
4. Enter your Coder URL (e.g. `https://coder.example.com`) and a session token
   (Coder → Account → Tokens).

## Polling

Chats are polled every 30 seconds. After any user-triggered service call the
integration requests an immediate refresh.

## Roadmap

- `async_step_reauth` for expired session tokens
- Split the REST client into a separate PyPI package before upstream submission
- Model selection on `create_chat`
- Tests + `quality_scale.yaml`

## License

MIT.
