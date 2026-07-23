"""Runnable self-check for github_watch.py. No framework, no fixtures.
Run: python3 test_github_watch.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

import github_watch
import requests
import state


class _FakeCfg:
    def __init__(self, state_path, gh_repo="owner/repo", gh_branch="main"):
        self.state_path = state_path
        self.gh_repo = gh_repo
        self.gh_branch = gh_branch


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_check_github_update_first_check_reports_changed():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    os.unlink(path)  # start with no state file at all
    try:
        def fake_get(url, headers=None, timeout=10):
            return _FakeResponse({"sha": "abc123", "commit": {"author": {"date": "2026-07-23T00:00:00Z"}}})

        original = requests.get
        requests.get = fake_get
        try:
            changed, sha, date = github_watch.check_github_update(_FakeCfg(path))
        finally:
            requests.get = original

        assert changed is True, changed
        assert sha == "abc123", sha
        assert state.load_state(path)["gh_last_sha"] == "abc123"
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_check_github_update_same_sha_reports_unchanged():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        state.save_state(path, {"gh_last_sha": "abc123"})

        def fake_get(url, headers=None, timeout=10):
            return _FakeResponse({"sha": "abc123", "commit": {"author": {"date": "2026-07-23T00:00:00Z"}}})

        original = requests.get
        requests.get = fake_get
        try:
            changed, sha, date = github_watch.check_github_update(_FakeCfg(path))
        finally:
            requests.get = original

        assert changed is False, changed
    finally:
        os.unlink(path)


def test_check_github_update_different_sha_reports_changed_and_updates_state():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        state.save_state(path, {"gh_last_sha": "old_sha"})

        def fake_get(url, headers=None, timeout=10):
            return _FakeResponse({"sha": "new_sha", "commit": {"author": {"date": "2026-07-23T00:00:00Z"}}})

        original = requests.get
        requests.get = fake_get
        try:
            changed, sha, date = github_watch.check_github_update(_FakeCfg(path))
        finally:
            requests.get = original

        assert changed is True, changed
        assert sha == "new_sha", sha
        assert state.load_state(path)["gh_last_sha"] == "new_sha"
    finally:
        os.unlink(path)


if __name__ == "__main__":
    test_check_github_update_first_check_reports_changed()
    test_check_github_update_same_sha_reports_unchanged()
    test_check_github_update_different_sha_reports_changed_and_updates_state()
    print("OK")
