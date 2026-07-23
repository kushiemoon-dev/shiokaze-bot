"""Runnable self-check for main.py. No framework, no fixtures.
Run: python3 test_main.py
"""

import asyncio
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(__file__))

# Mock pymysql before importing main (which imports commands, which imports db)
sys.modules['pymysql'] = MagicMock()
sys.modules['pymysql.cursors'] = MagicMock()

import main


def run(coro):
    return asyncio.run(coro)


def test_parse_command_basic():
    assert main.parse_command("!realm status") == ("status", None)


def test_parse_command_with_arg():
    assert main.parse_command("!realm alt Kushette") == ("alt", "Kushette")


def test_parse_command_case_insensitive_and_trimmed():
    assert main.parse_command("  !REALM Start  ") == ("start", None)


def test_parse_command_not_a_command_returns_none():
    assert main.parse_command("hello there") is None


def test_parse_command_bare_prefix_returns_none():
    assert main.parse_command("!realm") is None
    assert main.parse_command("!realm   ") is None


def test_dispatch_routes_to_matching_command():
    calls = []

    async def fake_start(cfg, send):
        calls.append("start")

    async def fake_alt(cfg, send, name):
        calls.append(("alt", name))

    original_start = main.commands.cmd_start
    original_alt = main.commands.cmd_alt
    main.commands.cmd_start = fake_start
    main.commands.cmd_alt = fake_alt
    try:
        run(main.dispatch(cfg=None, send=None, sub="start", arg=None))
        run(main.dispatch(cfg=None, send=None, sub="alt", arg="Ghost"))
    finally:
        main.commands.cmd_start = original_start
        main.commands.cmd_alt = original_alt

    assert calls == ["start", ("alt", "Ghost")], calls


def test_dispatch_alt_without_arg_does_nothing():
    calls = []

    async def fake_alt(cfg, send, name):
        calls.append(name)

    original = main.commands.cmd_alt
    main.commands.cmd_alt = fake_alt
    try:
        run(main.dispatch(cfg=None, send=None, sub="alt", arg=None))
    finally:
        main.commands.cmd_alt = original

    assert calls == [], calls


def test_dispatch_unknown_subcommand_does_nothing():
    # Should not raise even though no command matches.
    run(main.dispatch(cfg=None, send=None, sub="nonsense", arg=None))


if __name__ == "__main__":
    test_parse_command_basic()
    test_parse_command_with_arg()
    test_parse_command_case_insensitive_and_trimmed()
    test_parse_command_not_a_command_returns_none()
    test_parse_command_bare_prefix_returns_none()
    test_dispatch_routes_to_matching_command()
    test_dispatch_alt_without_arg_does_nothing()
    test_dispatch_unknown_subcommand_does_nothing()
    print("OK")
