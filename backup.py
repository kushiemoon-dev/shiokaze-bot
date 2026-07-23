"""Remote DB+patches+config backup via a restricted SSH forced-command key,
unchanged by this port. The "backup" argument is ignored server-side but
required by the ssh client."""

import asyncio


async def trigger_backup(cfg):
    """Returns (size, path)."""
    proc = await asyncio.create_subprocess_exec(
        "ssh", "-i", cfg.backup_key_path,
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=10",
        f"root@{cfg.realm_host}", "backup",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=cfg.backup_timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("timed out")

    if proc.returncode != 0:
        raise RuntimeError(stderr.decode().strip() or f"ssh exit {proc.returncode}")

    lines = stdout.decode().strip().splitlines()
    size = lines[0] if len(lines) > 0 else "?"
    path = lines[1] if len(lines) > 1 else "?"
    return size, path
