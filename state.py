"""Persisted bot state: flavor-text level tracking + GitHub-watch dedup."""

import json


def load_state(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(path, state):
    with open(path, "w") as f:
        json.dump(state, f)


LEVEL_TIER_LINES = [
    (1, 10, "Still a baby, just getting started."),
    (11, 30, "Taking shape."),
    (31, 60, "Well underway."),
    (61, 79, "Almost max level."),
    (80, 999, "Max level, gg."),
]


def character_flavor(state_path, perso, bots_online):
    """Flavor text easter eggs, appended below character info. Updates state.json."""
    if not perso:
        return []
    st = load_state(state_path)
    key = perso["name"]
    lines = []

    last_level = st.get(key)
    if last_level is not None and perso["level"] > last_level:
        lines.append(f"🎉 Leveled up since last time ({last_level} → {perso['level']})!")
    st[key] = perso["level"]
    save_state(state_path, st)

    for lo, hi, line in LEVEL_TIER_LINES:
        if lo <= perso["level"] <= hi:
            lines.append(line)
            break

    if bots_online == 0:
        lines.append("Total solitude, even the bots have deserted.")

    return lines
