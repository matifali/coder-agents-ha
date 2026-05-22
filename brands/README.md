# Brand assets

Home Assistant fetches integration logos from the
[`home-assistant/brands`](https://github.com/home-assistant/brands) repo, **not**
from this repo. The PNG files under `custom_integrations/coder/` are staged here
so they can be PR'd upstream.

Source: [simpleicons.org Coder logo](https://simpleicons.org/?q=coder).

## How to submit

1. Fork [`home-assistant/brands`](https://github.com/home-assistant/brands).
2. Copy `custom_integrations/coder/icon.png` and `icon@2x.png` to the same path
   in the fork (`custom_integrations/coder/`).
3. Open a PR. After it's merged, restart your HA — the Coder logo will appear
   in Settings → Devices & Services.

Until that PR lands, HA falls back to a generic letter icon.

## Files

- `icon.png` — 256x256, used in the Devices & Services list
- `icon@2x.png` — 512x512, hi-DPI variant
- `coder.svg` — original source from simpleicons
- `coder.padded.svg` — padded variant used as PNG source
