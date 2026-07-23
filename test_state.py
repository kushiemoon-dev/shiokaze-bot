"""Runnable self-check for state.py. No framework, no fixtures.
Run: python3 test_state.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

import state


def test_load_state_missing_file_returns_empty_dict():
    result = state.load_state("/tmp/shiokaze-test-does-not-exist.json")
    assert result == {}, result


def test_save_then_load_roundtrip():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        state.save_state(path, {"gh_last_sha": "abc123"})
        assert state.load_state(path) == {"gh_last_sha": "abc123"}
    finally:
        os.unlink(path)


def test_character_flavor_detects_level_up():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        state.save_state(path, {"Kushette": 10})
        perso = {"name": "Kushette", "level": 15}
        lines = state.character_flavor(path, perso, bots_online=3)
        assert any("Leveled up" in line for line in lines), lines
        assert "10 → 15" in "".join(lines), lines
        assert state.load_state(path)["Kushette"] == 15
    finally:
        os.unlink(path)


def test_character_flavor_no_prior_level_no_levelup_message():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        perso = {"name": "NewChar", "level": 5}
        lines = state.character_flavor(path, perso, bots_online=1)
        assert not any("Leveled up" in line for line in lines), lines
    finally:
        os.unlink(path)


def test_character_flavor_tier_line_selection():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        perso = {"name": "Solo", "level": 80}
        lines = state.character_flavor(path, perso, bots_online=1)
        assert "Max level, gg." in lines, lines
    finally:
        os.unlink(path)


def test_character_flavor_solitude_message_when_zero_bots():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        perso = {"name": "Alone", "level": 1}
        lines = state.character_flavor(path, perso, bots_online=0)
        assert "Total solitude, even the bots have deserted." in lines, lines
    finally:
        os.unlink(path)


def test_character_flavor_none_character_returns_empty():
    lines = state.character_flavor("/tmp/unused.json", None, bots_online=5)
    assert lines == [], lines


if __name__ == "__main__":
    test_load_state_missing_file_returns_empty_dict()
    test_save_then_load_roundtrip()
    test_character_flavor_detects_level_up()
    test_character_flavor_no_prior_level_no_levelup_message()
    test_character_flavor_tier_line_selection()
    test_character_flavor_solitude_message_when_zero_bots()
    test_character_flavor_none_character_returns_empty()
    print("OK")
