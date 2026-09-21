"""Deterministic, date-seeded choice of room and NPC.

The pick depends only on the column date and the asset lists, so every visitor (and
every rerun of the job) gets the same scene for a given day.

Rather than an independent random draw each day (which repeats yesterday's pick 1/n of
the time), days are grouped into cycles of n days. Each cycle is a seeded shuffle of
all n items, so everything shows up once before anything repeats, and the seam between
two cycles is patched so the same item never appears two days running.
"""

from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path

EPOCH = dt.date(2024, 1, 1)
SCENES_FILE = Path(__file__).with_name("scenes.json")


def load_scenes(path: Path = SCENES_FILE) -> dict:
    scenes = json.loads(path.read_text(encoding="utf-8"))
    for key in ("rooms", "npcs", "party"):
        if not scenes.get(key):
            raise ValueError(f"{path}: '{key}' must be a non-empty list")
    return scenes


def _cycle_order(n: int, salt: str, cycle: int) -> list[int]:
    order = list(range(n))
    random.Random(f"{salt}:{cycle}").shuffle(order)
    return order


def _order_for(n: int, salt: str, cycle: int) -> list[int]:
    order = _cycle_order(n, salt, cycle)
    # Swapping the first two never touches the last slot (n >= 3), so the previous
    # cycle's last item can be read from its raw shuffle.
    if order[0] == _cycle_order(n, salt, cycle - 1)[-1]:
        order[0], order[1] = order[1], order[0]
    return order


def pick(items: list, date: dt.date, salt: str):
    n = len(items)
    day = (date - EPOCH).days
    if n == 1:
        return items[0]
    if n == 2:
        return items[day % 2]
    cycle, pos = divmod(day, n)
    return items[_order_for(n, salt, cycle)[pos]]


def pick_scene(date_str: str, scenes: dict) -> dict:
    date = dt.date.fromisoformat(date_str)
    return {
        "room": pick(scenes["rooms"], date, "room"),
        "npc": pick(scenes["npcs"], date, "npc"),
        "party": scenes["party"],
    }
