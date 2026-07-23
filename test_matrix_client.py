"""Runnable self-check for matrix_client.py. No framework, no fixtures.
Run: python3 test_matrix_client.py
"""

import io
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))

import matrix_client


class _FakeResponse:
    def __init__(self, body=b""):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_send_text_puts_message():
    calls = []

    def fake_urlopen(req, timeout=15):
        calls.append(req)
        return _FakeResponse()

    original = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    try:
        matrix_client.send_text("http://homeserver.test", "tok", "!room:test", "hello world")
    finally:
        urllib.request.urlopen = original

    assert len(calls) == 1, calls
    assert calls[0].get_method() == "PUT", calls[0].get_method()
    assert "%21room%3Atest" in calls[0].full_url, calls[0].full_url
    assert calls[0].get_header("Authorization") == "Bearer tok", calls[0].get_header("Authorization")
    body = json.loads(calls[0].data.decode())
    assert body == {"msgtype": "m.text", "body": "hello world"}, body


def test_send_text_retries_once_on_429():
    calls = []

    def fake_urlopen(req, timeout=15):
        calls.append(req)
        if len(calls) == 1:
            error_fp = io.BytesIO(json.dumps({"errcode": "M_LIMIT_EXCEEDED", "retry_after_ms": 0}).encode())
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", hdrs={}, fp=error_fp)
        return _FakeResponse()

    original = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    try:
        matrix_client.send_text("http://homeserver.test", "tok", "!room:test", "hi")
    finally:
        urllib.request.urlopen = original

    assert len(calls) == 2, calls


def test_sync_first_call_omits_since_and_returns_next_batch():
    calls = []

    def fake_urlopen(req, timeout=40):
        calls.append(req)
        payload = {"next_batch": "s1", "rooms": {"join": {}}}
        return _FakeResponse(json.dumps(payload).encode())

    original = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    try:
        next_batch, messages = matrix_client.sync("http://homeserver.test", "tok")
    finally:
        urllib.request.urlopen = original

    assert len(calls) == 1, calls
    assert "since=" not in calls[0].full_url, calls[0].full_url
    assert "timeout=30000" in calls[0].full_url, calls[0].full_url
    assert next_batch == "s1", next_batch
    assert messages == [], messages


def test_sync_includes_since_when_provided():
    calls = []

    def fake_urlopen(req, timeout=40):
        calls.append(req)
        payload = {"next_batch": "s2", "rooms": {"join": {}}}
        return _FakeResponse(json.dumps(payload).encode())

    original = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    try:
        matrix_client.sync("http://homeserver.test", "tok", since="s1", timeout_ms=0)
    finally:
        urllib.request.urlopen = original

    assert "since=s1" in calls[0].full_url, calls[0].full_url
    assert "timeout=0" in calls[0].full_url, calls[0].full_url


def test_sync_extracts_room_message_events_only():
    def fake_urlopen(req, timeout=40):
        payload = {
            "next_batch": "s3",
            "rooms": {
                "join": {
                    "!room1:test": {
                        "timeline": {
                            "events": [
                                {"type": "m.room.message", "sender": "@kushie:matrix.kushie.dev",
                                 "content": {"body": "!realm status"}},
                                {"type": "m.room.member", "sender": "@kushie:matrix.kushie.dev",
                                 "content": {"membership": "join"}},
                            ]
                        }
                    },
                    "!room2:test": {"timeline": {"events": []}},
                }
            },
        }
        return _FakeResponse(json.dumps(payload).encode())

    original = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    try:
        next_batch, messages = matrix_client.sync("http://homeserver.test", "tok", since="s2")
    finally:
        urllib.request.urlopen = original

    assert next_batch == "s3", next_batch
    assert len(messages) == 1, messages
    room_id, event = messages[0]
    assert room_id == "!room1:test", room_id
    assert event["content"]["body"] == "!realm status", event


if __name__ == "__main__":
    test_send_text_puts_message()
    test_send_text_retries_once_on_429()
    test_sync_first_call_omits_since_and_returns_next_batch()
    test_sync_includes_since_when_provided()
    test_sync_extracts_room_message_events_only()
    print("OK")
