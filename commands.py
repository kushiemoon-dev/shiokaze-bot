"""Realm control commands, ported from Discord app_commands to plain async
functions. Owner-lock and command parsing live in main.py, not here."""

import asyncio

import backup as backup_mod
import db
import pve
import state as state_mod

HOST_WARN_PCT = 85


def format_money(copper):
    gold, rem = divmod(copper, 10000)
    silver, copper = divmod(rem, 100)
    return f"{gold}g {silver}s {copper}c"


async def wait_for_port(host, port, timeout):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, asyncio.TimeoutError):
            await asyncio.sleep(5)
    return False


async def cmd_start(cfg, send):
    status = await asyncio.to_thread(pve.vm_status, cfg)
    if status["status"] != "running":
        await asyncio.to_thread(pve.vm_start, cfg)
        await send("VM starting, waiting for the world to load (~5 min)...")
    else:
        await send("VM already on, waiting for the world to be ready...")

    ready = await wait_for_port(cfg.realm_host, cfg.world_port, cfg.start_timeout)
    if ready:
        await send("🟢 Realm ready, log in!")
    else:
        await send("⚠️ Still not ready after the timeout, check manually.")


async def cmd_stop(cfg, send):
    status = await asyncio.to_thread(pve.vm_status, cfg)
    if status["status"] != "running":
        await send("Already off.")
        return

    await asyncio.to_thread(pve.vm_shutdown, cfg)
    deadline = asyncio.get_event_loop().time() + cfg.stop_timeout
    while asyncio.get_event_loop().time() < deadline:
        s = await asyncio.to_thread(pve.vm_status, cfg)
        if s["status"] == "stopped":
            await send("🔴 Realm stopped cleanly.")
            return
        await asyncio.sleep(5)
    await send("⚠️ Shutdown in progress but not confirmed within the timeout, check manually.")


async def _character_lines(cfg, name):
    """Returns (lines_or_None, bots_online)."""
    perso = await asyncio.to_thread(db.fetch_character, cfg, name)
    bots_online = await asyncio.to_thread(db.count_online, cfg)
    if not perso:
        return None, bots_online
    lines = [
        f"**{perso['name']}**: level {perso['level']}, "
        f"{format_money(perso['money'])}, zone {perso['zone']}, "
        f"{perso['totaltime'] // 3600}h played"
    ]
    lines.extend(state_mod.character_flavor(cfg.state_path, perso, bots_online))
    return lines, bots_online


async def cmd_status(cfg, send):
    status = await asyncio.to_thread(pve.vm_status, cfg)
    if status["status"] != "running":
        await send("🔴 Realm off.")
        return

    lines = [f"🟢 Realm online (uptime {status.get('uptime', 0) // 60} min)"]
    try:
        perso_lines, bots_online = await _character_lines(cfg, cfg.main_character)
        if perso_lines:
            lines.extend(perso_lines)
        lines.append(f"Bots/players online: {bots_online}")
    except Exception as e:
        lines.append(f"(DB unavailable: {e})")

    await send("\n".join(lines))


async def cmd_alt(cfg, send, name):
    status = await asyncio.to_thread(pve.vm_status, cfg)
    if status["status"] != "running":
        await send("🔴 Realm off.")
        return

    try:
        perso_lines, _bots_online = await _character_lines(cfg, name)
    except Exception as e:
        await send(f"(DB unavailable: {e})")
        return

    if not perso_lines:
        await send(f'Character "{name}" not found.')
        return

    await send("\n".join(perso_lines))


async def cmd_backup(cfg, send):
    await send("Backup in progress (~1-2 min)...")
    try:
        size, path = await backup_mod.trigger_backup(cfg)
        await send(f"✅ Backup done: `{path}` ({size})")
    except Exception as e:
        await send(f"⚠️ Backup failed: {e}")


async def cmd_health(cfg, send):
    vm = await asyncio.to_thread(pve.vm_status, cfg)
    node = await asyncio.to_thread(pve.node_status, cfg)

    lines = []
    if vm["status"] == "running" and vm.get("maxmem"):
        vm_pct = vm["mem"] / vm["maxmem"] * 100
        lines.append(f"VM {cfg.realm_vmid}: {vm_pct:.0f}% RAM, CPU {vm.get('cpu', 0) * 100:.0f}%")
    else:
        lines.append(f"VM {cfg.realm_vmid}: off (no live stats)")

    host_mem = node["memory"]
    host_pct = host_mem["used"] / host_mem["total"] * 100
    warn = f" ⚠️ above {HOST_WARN_PCT}%, check bot count before starting" if host_pct > HOST_WARN_PCT else ""
    lines.append(f"Host {cfg.realm_node}: {host_pct:.0f}% RAM{warn}")

    await send("\n".join(lines))
