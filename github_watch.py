"""Weekly GitHub commit watcher, posts to the Matrix events room instead of
a Discord DM to the owner."""

import asyncio

import requests

import matrix_client
import state


def check_github_update(cfg):
    """Returns (changed, sha, date) and updates state.json if it changed
    (or if this is the very first check)."""
    r = requests.get(
        f"https://api.github.com/repos/{cfg.gh_repo}/commits/{cfg.gh_branch}",
        headers={"User-Agent": "shiokaze-bot"}, timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    sha = data["sha"]
    date = data["commit"]["author"]["date"]

    st = state.load_state(cfg.state_path)
    last_sha = st.get("gh_last_sha")
    changed = last_sha != sha
    if changed:
        st["gh_last_sha"] = sha
        state.save_state(cfg.state_path, st)
    return changed, sha, date


async def run_loop(cfg, stop):
    """Checks immediately, then every 168h, until `stop` is set: mirrors the
    original tasks.loop(hours=168) semantics (fires once as soon as started)."""
    while not stop.is_set():
        try:
            changed, sha, date = await asyncio.to_thread(check_github_update, cfg)
            if changed:
                matrix_client.send_text(
                    cfg.matrix_homeserver_url, cfg.matrix_access_token, cfg.matrix_events_room_id,
                    f"🔔 New commit on `{cfg.gh_repo}` ({cfg.gh_branch}): `{sha[:10]}` ({date})",
                )
        except Exception as e:
            print(f"[github_watch] error: {e}")
        try:
            await asyncio.wait_for(stop.wait(), timeout=168 * 3600)
        except asyncio.TimeoutError:
            pass
