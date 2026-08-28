"""Entry point: long-polls Matrix for owner-only !realm commands and runs
the periodic GitHub watcher."""

import asyncio

import commands
import github_watch
import matrix_client
from config import load_config


def _since_path(cfg):
    return cfg.state_path + ".sync_since"


def _load_since(cfg):
    try:
        with open(_since_path(cfg)) as f:
            token = f.read().strip()
            return token or None
    except FileNotFoundError:
        return None


def _save_since(cfg, since):
    with open(_since_path(cfg), "w") as f:
        f.write(since)


def parse_command(body):
    """Returns (subcommand, arg) or None if body isn't a !realm command."""
    text = body.strip()
    if not text.lower().startswith("!realm"):
        return None
    rest = text[len("!realm"):].strip()
    if not rest:
        return None
    parts = rest.split(maxsplit=1)
    sub = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else None
    return sub, arg


async def dispatch(cfg, send, sub, arg):
    if sub == "start":
        await commands.cmd_start(cfg, send)
    elif sub == "stop":
        await commands.cmd_stop(cfg, send)
    elif sub == "status":
        await commands.cmd_status(cfg, send)
    elif sub == "alt" and arg:
        await commands.cmd_alt(cfg, send, arg)
    elif sub == "backup":
        await commands.cmd_backup(cfg, send)
    elif sub == "health":
        await commands.cmd_health(cfg, send)


async def receiver_loop(cfg, stop):
    since = _load_since(cfg)

    async def send(text):
        await asyncio.to_thread(
            matrix_client.send_text, cfg.matrix_homeserver_url, cfg.matrix_access_token,
            cfg.matrix_realm_room_id, text,
        )

    if since is None:
        # First run ever: establish a starting point, don't replay room history as commands.
        since, _initial = await asyncio.to_thread(
            matrix_client.sync, cfg.matrix_homeserver_url, cfg.matrix_access_token, None, 0,
        )
        _save_since(cfg, since)

    while not stop.is_set():
        try:
            next_batch, messages = await asyncio.to_thread(
                matrix_client.sync, cfg.matrix_homeserver_url, cfg.matrix_access_token, since, 30000,
            )
            since = next_batch
            _save_since(cfg, since)

            for room_id, event in messages:
                if room_id != cfg.matrix_realm_room_id:
                    continue
                if event.get("sender") != cfg.matrix_owner_id:
                    continue
                body = event.get("content", {}).get("body", "")
                parsed = parse_command(body)
                if not parsed:
                    continue
                sub, arg = parsed
                await dispatch(cfg, send, sub, arg)
        except Exception as e:
            print(f"[receiver_loop] error: {e}")


async def main():
    cfg = load_config()
    stop = asyncio.Event()
    await asyncio.gather(
        receiver_loop(cfg, stop),
        github_watch.run_loop(cfg, stop),
    )


if __name__ == "__main__":
    asyncio.run(main())
