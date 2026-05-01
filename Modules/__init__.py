"""Modules — mixed legacy + adapter package.

Two distinct concerns live here. They look similar but follow different
rules; importing the wrong one mixes paradigms.

## Active mod adapters (use freely from `tools/` and dashboard)

- `mod_client.py`   — HTTP client for the BepInEx mod API on port 6790.
- `mod_heroes.py`   — hero shape adapter for `/all-heroes` payloads.
- `memory_reader.py` — pymem fallback for when the mod isn't available.
- `rtk_client.py`   — Raid Toolkit SDK WebSocket (alternative to mod).
- `account_intel.py` — account-level snapshot helpers.

These are the ones `tools/dashboard_server.py`, `tools/sell.py`,
`tools/daily_common.py`, etc. import. They obey CLAUDE.md's
"NEVER use UI/screen automation" rule — game actions go through
the mod API only.

## Legacy screen-automation cluster (DO NOT EXTEND)

- `hybrid_controller.py` — daily-automation entry point used by the
  VM scheduled task (see `docs/vm_deployment.md`).
- `PyAutoRaid.py`, `DailyQuests.py`, `PullMysteryShards.py`,
  `CreateTask.py` — pyautogui-driven scripts.
- `base.py`, `screen_state.py`, `game_state.py`, `win32_input.py` —
  screen / window automation primitives consumed by the above.

These violate CLAUDE.md's "NEVER use UI/screen automation" rule but
are kept because `hybrid_controller.py` is still the prod scheduled
task on the VM. A future refactor should migrate these to mod-API
equivalents under `tools/<feature>_daily.py`. Until then: don't
touch unless you're doing the migration.
"""
