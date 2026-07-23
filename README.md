# shiokaze-bot

Matrix bot for a solo+bots AzerothCore realm hosted on Proxmox: remote
power on/off, DB status, RAM/CPU pre-flight check, on-demand backup,
upstream update watcher.

All commands are locked to a single owner (`MATRIX_OWNER_ID`); the bot never
posts on its own initiative except the update-watcher notice. Matrix has no ephemeral-reply
equivalent to Discord's — replies are visible to whoever is in the room.

## Commands

Plain-text messages in room `AzerothCore bot`:

- `!realm start` — starts the VM, waits for the world to finish loading, confirms once it's playable
- `!realm stop` — graceful shutdown (saves the DB before power-off)
- `!realm status` — up/down, main character, bots online
- `!realm alt <name>` — same, for any character in the roster
- `!realm health` — VM and Proxmox host RAM/CPU, warns if it's getting tight
- `!realm backup` — triggers a remote DB+patches+config backup

Background task: checks once a week whether the tracked fork has a new
commit, posts into room `Realm events` only if it does.

## Config (environment variables)

| Variable | Description |
|---|---|
| `MATRIX_HOMESERVER_URL` | Synapse homeserver base URL |
| `MATRIX_ACCESS_TOKEN` | `@shiokaze:matrix.kushie.dev`'s access token |
| `MATRIX_REALM_ROOM_ID` | Room where `!realm` commands are read + answered |
| `MATRIX_EVENTS_ROOM_ID` | Room where the GitHub-watch notice is posted |
| `MATRIX_OWNER_ID` | Only Matrix user ID allowed to trigger commands |
| `PROXMOX_HOST` | Proxmox node address (API) |
| `PROXMOX_TOKEN_ID` / `PROXMOX_TOKEN_SECRET` | Scoped API token (power+audit on the VM, audit on the node) |
| `PROXMOX_CA_PATH` | Pinned Proxmox self-signed cert (no `verify=False`) |
| `REALM_NODE` / `REALM_VMID` | Realm's node + VMID |
| `REALM_HOST` | VM IP (world-port poll + MySQL) |
| `REALM_WORLD_PORT` | Worldserver port (default 8085) |
| `REALM_MAIN_CHARACTER` | Default character for `!realm status` |
| `MYSQL_RO_USER` / `MYSQL_RO_PASS` | Read-only MySQL user (SELECT only) |
| `REALM_BACKUP_KEY_PATH` | Dedicated SSH key, restricted by a server-side forced command |
| `REALM_GH_REPO` / `REALM_GH_BRANCH` | Fork/branch tracked by the update watcher |

No secret is hardcoded in the code — everything comes from the environment.

## Deployment

Runs as a systemd service inside a dedicated Python venv (see `pymysql`,
`requests` as dependencies). The backup script (`run-backup.sh`)
and its restricted SSH key live on the realm server itself, not in this repo.
