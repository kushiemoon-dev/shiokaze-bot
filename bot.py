"""Shiokaze Discord bot — remote power on/off + status for the realm.

All commands are locked to a single owner (DISCORD_OWNER_ID) and reply
ephemerally: nothing is ever posted to a channel on the bot's own
initiative, except the weekly update-watcher DM.
"""

import asyncio
import json
import os

import discord
import pymysql
import requests
from discord import app_commands
from discord.ext import tasks

# --- config (everything comes from the environment, nothing hardcoded) ---
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
OWNER_ID = int(os.environ["DISCORD_OWNER_ID"])
GUILD_ID = int(os.environ["DISCORD_GUILD_ID"])

PROXMOX_HOST = os.environ["PROXMOX_HOST"]
PROXMOX_TOKEN_ID = os.environ["PROXMOX_TOKEN_ID"]
PROXMOX_TOKEN_SECRET = os.environ["PROXMOX_TOKEN_SECRET"]
# Proxmox self-signed cert, pinned (no verify=False) — see deployment notes.
PROXMOX_CA_PATH = os.environ.get("PROXMOX_CA_PATH", "/etc/shiokaze-bot/proxmox-ca.pem")
REALM_NODE = os.environ["REALM_NODE"]
REALM_VMID = os.environ["REALM_VMID"]

REALM_HOST = os.environ["REALM_HOST"]
WORLD_PORT = int(os.environ.get("REALM_WORLD_PORT", "8085"))
START_TIMEOUT = int(os.environ.get("REALM_START_TIMEOUT", "420"))  # ~5min observed boot time + margin
STOP_TIMEOUT = int(os.environ.get("REALM_STOP_TIMEOUT", "90"))

MYSQL_USER = os.environ["MYSQL_RO_USER"]
MYSQL_PASS = os.environ["MYSQL_RO_PASS"]
MAIN_CHARACTER = os.environ.get("REALM_MAIN_CHARACTER", "Kushette")

STATE_PATH = os.environ.get("REALM_STATE_PATH", "/opt/shiokaze-bot/state.json")
HOST_WARN_PCT = 85

# Key restricted by a forced command (authorized_keys): can ONLY run
# /root/run-backup.sh on the VM, no matter what's requested — see deployment.
BACKUP_KEY_PATH = os.environ.get("REALM_BACKUP_KEY_PATH", "/etc/shiokaze-bot/backup_key")
BACKUP_TIMEOUT = int(os.environ.get("REALM_BACKUP_TIMEOUT", "300"))

GH_REPO = os.environ.get("REALM_GH_REPO", "mod-playerbots/azerothcore-wotlk")
GH_BRANCH = os.environ.get("REALM_GH_BRANCH", "Playerbot")

PROXMOX_API = f"https://{PROXMOX_HOST}:8006/api2/json"
PROXMOX_HEADERS = {"Authorization": f"PVEAPIToken={PROXMOX_TOKEN_ID}={PROXMOX_TOKEN_SECRET}"}


def _pve_get(path):
    r = requests.get(f"{PROXMOX_API}{path}", headers=PROXMOX_HEADERS, verify=PROXMOX_CA_PATH, timeout=10)
    r.raise_for_status()
    return r.json()["data"]


def _pve_post(path):
    r = requests.post(f"{PROXMOX_API}{path}", headers=PROXMOX_HEADERS, verify=PROXMOX_CA_PATH, timeout=10)
    r.raise_for_status()
    return r.json()["data"]


def vm_status():
    """{'status': 'running'|'stopped', 'uptime': int}"""
    return _pve_get(f"/nodes/{REALM_NODE}/qemu/{REALM_VMID}/status/current")


def vm_start():
    return _pve_post(f"/nodes/{REALM_NODE}/qemu/{REALM_VMID}/status/start")


def vm_shutdown():
    return _pve_post(f"/nodes/{REALM_NODE}/qemu/{REALM_VMID}/status/shutdown")


def node_status():
    """Global RAM/CPU for the Proxmox host (read-only, Sys.Audit)."""
    return _pve_get(f"/nodes/{REALM_NODE}/status")


def fetch_character(name):
    """Read-only (SELECT-only MySQL user). Returns the character row or None."""
    conn = pymysql.connect(
        host=REALM_HOST, user=MYSQL_USER, password=MYSQL_PASS,
        database="acore_characters", connect_timeout=5,
    )
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT name, level, money, zone, totaltime FROM characters WHERE name=%s",
                (name,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def count_online():
    conn = pymysql.connect(
        host=REALM_HOST, user=MYSQL_USER, password=MYSQL_PASS,
        database="acore_characters", connect_timeout=5,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM characters WHERE online=1")
            return cur.fetchone()[0]
    finally:
        conn.close()


def _load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f)


LEVEL_TIER_LINES = [
    (1, 10, "Still a baby, just getting started."),
    (11, 30, "Taking shape."),
    (31, 60, "Well underway."),
    (61, 79, "Almost max level."),
    (80, 999, "Max level, gg."),
]


def character_flavor(perso, bots_online):
    """Flavor text easter eggs, appended below character info. Updates state.json."""
    if not perso:
        return []
    state = _load_state()
    key = perso["name"]
    lines = []

    last_level = state.get(key)
    if last_level is not None and perso["level"] > last_level:
        lines.append(f"🎉 Leveled up since last time ({last_level} → {perso['level']})!")
    state[key] = perso["level"]
    _save_state(state)

    for lo, hi, line in LEVEL_TIER_LINES:
        if lo <= perso["level"] <= hi:
            lines.append(line)
            break

    if bots_online == 0:
        lines.append("Total solitude, even the bots have deserted.")

    return lines


async def trigger_backup():
    """SSH using the restricted key (forced command server-side); the
    "backup" argument is ignored by the server but required by the ssh
    client. Returns (size, path)."""
    proc = await asyncio.create_subprocess_exec(
        "ssh", "-i", BACKUP_KEY_PATH,
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=10",
        f"root@{REALM_HOST}", "backup",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=BACKUP_TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("timed out")

    if proc.returncode != 0:
        raise RuntimeError(stderr.decode().strip() or f"ssh exit {proc.returncode}")

    lines = stdout.decode().strip().splitlines()
    size = lines[0] if len(lines) > 0 else "?"
    path = lines[1] if len(lines) > 1 else "?"
    return size, path


def check_github_update():
    """Returns (changed, sha, date) and updates state.json if it changed
    (or if this is the very first check)."""
    r = requests.get(
        f"https://api.github.com/repos/{GH_REPO}/commits/{GH_BRANCH}",
        headers={"User-Agent": "shiokaze-bot"}, timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    sha = data["sha"]
    date = data["commit"]["author"]["date"]

    state = _load_state()
    last_sha = state.get("gh_last_sha")
    changed = last_sha != sha
    if changed:
        state["gh_last_sha"] = sha
        _save_state(state)
    return changed, sha, date


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


def format_money(copper):
    gold, rem = divmod(copper, 10000)
    silver, copper = divmod(rem, 100)
    return f"{gold}g {silver}s {copper}c"


class RealmGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="realm", description="Control the Shiokaze realm")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("Not for you.", ephemeral=True)
            return False
        return True

    @app_commands.command(description="Starts the realm and pings you when it's playable")
    async def start(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        status = await asyncio.to_thread(vm_status)
        if status["status"] != "running":
            await asyncio.to_thread(vm_start)
            await interaction.followup.send("VM starting, waiting for the world to load (~5 min)...", ephemeral=True)
        else:
            await interaction.followup.send("VM already on, waiting for the world to be ready...", ephemeral=True)

        ready = await wait_for_port(REALM_HOST, WORLD_PORT, START_TIMEOUT)
        if ready:
            await interaction.followup.send("🟢 Realm ready, log in!", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ Still not ready after the timeout, check manually.", ephemeral=True)

    @app_commands.command(description="Stops the realm gracefully (saves the DB before shutdown)")
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        status = await asyncio.to_thread(vm_status)
        if status["status"] != "running":
            await interaction.followup.send("Already off.", ephemeral=True)
            return

        await asyncio.to_thread(vm_shutdown)
        deadline = asyncio.get_event_loop().time() + STOP_TIMEOUT
        while asyncio.get_event_loop().time() < deadline:
            s = await asyncio.to_thread(vm_status)
            if s["status"] == "stopped":
                await interaction.followup.send("🔴 Realm stopped cleanly.", ephemeral=True)
                return
            await asyncio.sleep(5)
        await interaction.followup.send("⚠️ Shutdown in progress but not confirmed within the timeout, check manually.", ephemeral=True)

    @app_commands.command(description="Realm status: up/down, character, bots online")
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        status = await asyncio.to_thread(vm_status)

        if status["status"] != "running":
            await interaction.followup.send("🔴 Realm off.", ephemeral=True)
            return

        lines = [f"🟢 Realm online (uptime {status.get('uptime', 0) // 60} min)"]
        try:
            perso = await asyncio.to_thread(fetch_character, MAIN_CHARACTER)
            bots_online = await asyncio.to_thread(count_online)
            if perso:
                lines.append(
                    f"**{perso['name']}** — level {perso['level']}, "
                    f"{format_money(perso['money'])}, zone {perso['zone']}, "
                    f"{perso['totaltime'] // 3600}h played"
                )
                lines.extend(character_flavor(perso, bots_online))
            lines.append(f"Bots/players online: {bots_online}")
        except Exception as e:
            lines.append(f"(DB unavailable: {e})")

        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @app_commands.command(description="Info on any character in the roster")
    @app_commands.describe(name="Character name to look up")
    async def alt(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        status = await asyncio.to_thread(vm_status)
        if status["status"] != "running":
            await interaction.followup.send("🔴 Realm off.", ephemeral=True)
            return

        try:
            perso = await asyncio.to_thread(fetch_character, name)
            bots_online = await asyncio.to_thread(count_online)
        except Exception as e:
            await interaction.followup.send(f"(DB unavailable: {e})", ephemeral=True)
            return

        if not perso:
            await interaction.followup.send(f"Character \"{name}\" not found.", ephemeral=True)
            return

        lines = [
            f"**{perso['name']}** — level {perso['level']}, "
            f"{format_money(perso['money'])}, zone {perso['zone']}, "
            f"{perso['totaltime'] // 3600}h played"
        ]
        lines.extend(character_flavor(perso, bots_online))
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @app_commands.command(description="Triggers a remote DB+patches+config backup")
    async def backup(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("Backup in progress (~1-2 min)...", ephemeral=True)
        try:
            size, path = await trigger_backup()
            await interaction.followup.send(f"✅ Backup done: `{path}` ({size})", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ Backup failed: {e}", ephemeral=True)

    @app_commands.command(description="Pre-flight RAM/CPU check (VM + host)")
    async def health(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        vm = await asyncio.to_thread(vm_status)
        node = await asyncio.to_thread(node_status)

        lines = []
        if vm["status"] == "running" and vm.get("maxmem"):
            vm_pct = vm["mem"] / vm["maxmem"] * 100
            lines.append(f"VM 120: {vm_pct:.0f}% RAM, CPU {vm.get('cpu', 0) * 100:.0f}%")
        else:
            lines.append("VM 120: off (no live stats)")

        host_mem = node["memory"]
        host_pct = host_mem["used"] / host_mem["total"] * 100
        warn = f" ⚠️ above {HOST_WARN_PCT}%, check bot count before starting" if host_pct > HOST_WARN_PCT else ""
        lines.append(f"Host {REALM_NODE}: {host_pct:.0f}% RAM{warn}")

        await interaction.followup.send("\n".join(lines), ephemeral=True)


class ShiokazeClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.tree.add_command(RealmGroup(), guild=discord.Object(id=GUILD_ID))
        await self.tree.sync(guild=discord.Object(id=GUILD_ID))


client = ShiokazeClient()


@tasks.loop(hours=168)
async def github_watch():
    try:
        changed, sha, date = await asyncio.to_thread(check_github_update)
    except Exception as e:
        print(f"[github_watch] error: {e}")
        return
    if changed:
        try:
            owner = await client.fetch_user(OWNER_ID)
            await owner.send(
                f"🔔 New commit on `{GH_REPO}` ({GH_BRANCH}): `{sha[:10]}` ({date})"
            )
        except Exception as e:
            print(f"[github_watch] DM failed: {e}")


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    if not github_watch.is_running():
        github_watch.start()


client.run(DISCORD_TOKEN)
