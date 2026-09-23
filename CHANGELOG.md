# Changelog

## v0.2.0 (2026-08-28)

### Changed
- **Ported the bot from Discord to Matrix**: the Discord client was decommissioned, replaced with a stdlib based Matrix send/long poll receive loop, wired into command dispatch, realm control, and the GitHub commit watcher (which now posts into the Matrix Realm events room). Configuration moved to an env driven `Config`.
- Realm control, Proxmox VM control, character DB queries, SSH backup triggering, and state persistence were extracted out of the main script into their own modules (`pve.py`, `db.py`, `backup.py`, `state.py`), each parametrized via config instead of hardcoded.

### Fixes
- `receiver_loop` now catches exceptions instead of letting a transient error crash the bot.
- Corrected a stray `/realm` reference to `!realm` in the README's config table.

## v0.1.0 (2026-07-06)

### Features
- Initial release: Discord bot for a solo+bots AzerothCore realm.
