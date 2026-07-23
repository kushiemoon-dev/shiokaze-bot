"""Runnable self-check for commands.py. No framework, no fixtures.
Run: python3 test_commands.py
"""

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

import commands
from config import Config


def make_cfg(state_path, **overrides):
    defaults = dict(
        matrix_homeserver_url="http://homeserver.test", matrix_access_token="tok",
        matrix_realm_room_id="!realm:test", matrix_events_room_id="!events:test",
        matrix_owner_id="@kushie:matrix.kushie.dev",
        proxmox_host="pve.test", proxmox_token_id="tok_id", proxmox_token_secret="tok_secret",
        proxmox_ca_path="/dev/null",
        realm_node="pve-datacenter3", realm_vmid="120", realm_host="192.168.1.228",
        world_port=8085, start_timeout=1, stop_timeout=1,
        mysql_user="u", mysql_pass="p", main_character="Kushette",
        state_path=state_path, backup_key_path="/dev/null", backup_timeout=1,
        gh_repo="owner/repo", gh_branch="main",
    )
    defaults.update(overrides)
    return Config(**defaults)


def make_send():
    sent = []

    async def send(text):
        sent.append(text)

    return sent, send


def run(coro):
    return asyncio.run(coro)


def with_temp_state(fn):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        fn(path)
    finally:
        os.unlink(path)


def test_cmd_start_boots_stopped_vm_and_waits_for_port():
    def body(path):
        cfg = make_cfg(path)
        calls = {"start": 0}

        original_status = commands.pve.vm_status
        original_start = commands.pve.vm_start
        original_wait = commands.wait_for_port
        commands.pve.vm_status = lambda cfg: {"status": "stopped"}
        commands.pve.vm_start = lambda cfg: calls.__setitem__("start", calls["start"] + 1)

        async def fake_wait(host, port, timeout):
            return True

        commands.wait_for_port = fake_wait
        try:
            sent, send = make_send()
            run(commands.cmd_start(cfg, send))
        finally:
            commands.pve.vm_status = original_status
            commands.pve.vm_start = original_start
            commands.wait_for_port = original_wait

        assert calls["start"] == 1, calls
        assert any("starting" in s for s in sent), sent
        assert any("Realm ready" in s for s in sent), sent

    with_temp_state(body)


def test_cmd_start_already_running_skips_vm_start():
    def body(path):
        cfg = make_cfg(path)
        calls = {"start": 0}

        original_status = commands.pve.vm_status
        original_start = commands.pve.vm_start
        original_wait = commands.wait_for_port
        commands.pve.vm_status = lambda cfg: {"status": "running"}
        commands.pve.vm_start = lambda cfg: calls.__setitem__("start", calls["start"] + 1)

        async def fake_wait(host, port, timeout):
            return True

        commands.wait_for_port = fake_wait
        try:
            sent, send = make_send()
            run(commands.cmd_start(cfg, send))
        finally:
            commands.pve.vm_status = original_status
            commands.pve.vm_start = original_start
            commands.wait_for_port = original_wait

        assert calls["start"] == 0, calls
        assert any("already on" in s for s in sent), sent

    with_temp_state(body)


def test_cmd_start_timeout_warns():
    def body(path):
        cfg = make_cfg(path)
        original_status = commands.pve.vm_status
        original_wait = commands.wait_for_port
        commands.pve.vm_status = lambda cfg: {"status": "running"}

        async def fake_wait(host, port, timeout):
            return False

        commands.wait_for_port = fake_wait
        try:
            sent, send = make_send()
            run(commands.cmd_start(cfg, send))
        finally:
            commands.pve.vm_status = original_status
            commands.wait_for_port = original_wait

        assert any("Still not ready" in s for s in sent), sent

    with_temp_state(body)


def test_cmd_stop_already_off():
    def body(path):
        cfg = make_cfg(path)
        original_status = commands.pve.vm_status
        commands.pve.vm_status = lambda cfg: {"status": "stopped"}
        try:
            sent, send = make_send()
            run(commands.cmd_stop(cfg, send))
        finally:
            commands.pve.vm_status = original_status

        assert sent == ["Already off."], sent

    with_temp_state(body)


def test_cmd_stop_confirms_clean_shutdown():
    def body(path):
        cfg = make_cfg(path)
        statuses = iter([{"status": "running"}, {"status": "stopped"}])
        original_status = commands.pve.vm_status
        original_shutdown = commands.pve.vm_shutdown
        commands.pve.vm_status = lambda cfg: next(statuses)
        commands.pve.vm_shutdown = lambda cfg: None
        try:
            sent, send = make_send()
            run(commands.cmd_stop(cfg, send))
        finally:
            commands.pve.vm_status = original_status
            commands.pve.vm_shutdown = original_shutdown

        assert any("stopped cleanly" in s for s in sent), sent

    with_temp_state(body)


def test_cmd_status_realm_off():
    def body(path):
        cfg = make_cfg(path)
        original_status = commands.pve.vm_status
        commands.pve.vm_status = lambda cfg: {"status": "stopped"}
        try:
            sent, send = make_send()
            run(commands.cmd_status(cfg, send))
        finally:
            commands.pve.vm_status = original_status

        assert sent == ["🔴 Realm off."], sent

    with_temp_state(body)


def test_cmd_status_realm_online_shows_character_and_bots():
    def body(path):
        cfg = make_cfg(path)
        original_status = commands.pve.vm_status
        original_fetch = commands.db.fetch_character
        original_count = commands.db.count_online
        commands.pve.vm_status = lambda cfg: {"status": "running", "uptime": 120}
        commands.db.fetch_character = lambda cfg, name: {
            "name": "Kushette", "level": 42, "money": 123456, "zone": "Elwynn Forest", "totaltime": 7200,
        }
        commands.db.count_online = lambda cfg: 3
        try:
            sent, send = make_send()
            run(commands.cmd_status(cfg, send))
        finally:
            commands.pve.vm_status = original_status
            commands.db.fetch_character = original_fetch
            commands.db.count_online = original_count

        assert len(sent) == 1, sent
        text = sent[0]
        assert "Kushette" in text, text
        assert "level 42" in text, text
        assert "Bots/players online: 3" in text, text

    with_temp_state(body)


def test_cmd_alt_character_not_found():
    def body(path):
        cfg = make_cfg(path)
        original_status = commands.pve.vm_status
        original_fetch = commands.db.fetch_character
        original_count = commands.db.count_online
        commands.pve.vm_status = lambda cfg: {"status": "running"}
        commands.db.fetch_character = lambda cfg, name: None
        commands.db.count_online = lambda cfg: 0
        try:
            sent, send = make_send()
            run(commands.cmd_alt(cfg, send, "Ghost"))
        finally:
            commands.pve.vm_status = original_status
            commands.db.fetch_character = original_fetch
            commands.db.count_online = original_count

        assert 'Character "Ghost" not found.' in sent, sent

    with_temp_state(body)


def test_cmd_backup_success():
    def body(path):
        cfg = make_cfg(path)

        async def fake_trigger(cfg):
            return "42M", "/backups/realm.tar.gz"

        original = commands.backup_mod.trigger_backup
        commands.backup_mod.trigger_backup = fake_trigger
        try:
            sent, send = make_send()
            run(commands.cmd_backup(cfg, send))
        finally:
            commands.backup_mod.trigger_backup = original

        assert any("Backup in progress" in s for s in sent), sent
        assert any("Backup done" in s and "/backups/realm.tar.gz" in s for s in sent), sent

    with_temp_state(body)


def test_cmd_backup_failure():
    def body(path):
        cfg = make_cfg(path)

        async def fake_trigger(cfg):
            raise RuntimeError("ssh exit 255")

        original = commands.backup_mod.trigger_backup
        commands.backup_mod.trigger_backup = fake_trigger
        try:
            sent, send = make_send()
            run(commands.cmd_backup(cfg, send))
        finally:
            commands.backup_mod.trigger_backup = original

        assert any("Backup failed" in s and "ssh exit 255" in s for s in sent), sent

    with_temp_state(body)


def test_cmd_health_reports_vm_and_host():
    def body(path):
        cfg = make_cfg(path)
        original_status = commands.pve.vm_status
        original_node = commands.pve.node_status
        commands.pve.vm_status = lambda cfg: {"status": "running", "mem": 512, "maxmem": 1024, "cpu": 0.1}
        commands.pve.node_status = lambda cfg: {"memory": {"used": 90, "total": 100}}
        try:
            sent, send = make_send()
            run(commands.cmd_health(cfg, send))
        finally:
            commands.pve.vm_status = original_status
            commands.pve.node_status = original_node

        text = sent[0]
        assert "VM 120" in text, text
        assert "50% RAM" in text, text
        assert "above 85%" in text, text  # host at 90% triggers the warning

    with_temp_state(body)


if __name__ == "__main__":
    test_cmd_start_boots_stopped_vm_and_waits_for_port()
    test_cmd_start_already_running_skips_vm_start()
    test_cmd_start_timeout_warns()
    test_cmd_stop_already_off()
    test_cmd_stop_confirms_clean_shutdown()
    test_cmd_status_realm_off()
    test_cmd_status_realm_online_shows_character_and_bots()
    test_cmd_alt_character_not_found()
    test_cmd_backup_success()
    test_cmd_backup_failure()
    test_cmd_health_reports_vm_and_host()
    print("OK")
