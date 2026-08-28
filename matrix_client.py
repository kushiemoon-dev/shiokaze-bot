"""Matrix Client-Server API: send + receive. stdlib only."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


def send_text(homeserver_url, access_token, room_id, text):
    """Send a plain-text message to a Matrix room."""
    body = json.dumps({"msgtype": "m.text", "body": text}).encode()
    txn_id = uuid.uuid4().hex
    url = f"{homeserver_url}/_matrix/client/v3/rooms/{urllib.parse.quote(room_id, safe='')}/send/m.room.message/{txn_id}"
    req = urllib.request.Request(url, data=body, method="PUT")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {access_token}")
    try:
        with urllib.request.urlopen(req, timeout=15):
            pass
    except urllib.error.HTTPError as e:
        if e.code != 429:
            raise
        try:
            retry_after = json.loads(e.read()).get("retry_after_ms", 1000) / 1000
        except ValueError:
            retry_after = 1
        time.sleep(retry_after)
        with urllib.request.urlopen(req, timeout=15):
            pass


def sync(homeserver_url, access_token, since=None, timeout_ms=30000):
    """Long-poll /sync. Returns (next_batch, [(room_id, event), ...]) for every
    m.room.message event across all joined rooms since the last call."""
    params = {"timeout": timeout_ms}
    if since:
        params["since"] = since
    url = f"{homeserver_url}/_matrix/client/v3/sync?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {access_token}")
    with urllib.request.urlopen(req, timeout=(timeout_ms / 1000) + 10) as resp:
        data = json.loads(resp.read())

    messages = []
    for room_id, room_data in data.get("rooms", {}).get("join", {}).items():
        for event in room_data.get("timeline", {}).get("events", []):
            if event.get("type") == "m.room.message":
                messages.append((room_id, event))
    return data["next_batch"], messages
