"""Deterministic, date-seeded choice of room, NPC and party.

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

MEMBERS = ("ness", "paula", "jeff", "poo")  # also the order they walk in
STATES = ("alive", "ghost", "diamond", "robot")

# Where the NPC's feet are on the 256x224 stage, unless a room says otherwise. The party
# stands below in a column facing up, the leader's feet LEAD px under the NPC's and
# each follower STEP px behind the one before.
DEFAULT_SPOT = (128, 124)
LEAD = 18
STEP = 16

P_ROBOTS = 1 / 500
P_UNCONSCIOUS = 0.2
P_DIAMOND = 0.1  # of those unconscious


def room_entry(entry) -> dict:
    """A room is a path, or {"src": path, "spot": [x, y]}."""
    if isinstance(entry, str):
        return {"src": entry, "spot": list(DEFAULT_SPOT)}
    return {"src": entry["src"], "spot": list(entry.get("spot", DEFAULT_SPOT))}


def party_frames(party) -> dict:
    """{member: {state: path}}. A plain list (the placeholders) is Ness, Paula, Jeff, Poo
    with one picture each. A missing state falls back to the member's "alive" picture."""
    if isinstance(party, list):
        party = {m: {"alive": p} for m, p in zip(MEMBERS, party)}
    frames = {}
    for m in MEMBERS:
        if m not in party or "alive" not in party[m]:
            raise ValueError(f"party: no 'alive' picture for {m}")
        frames[m] = {s: party[m].get(s, party[m]["alive"]) for s in STATES}
    return frames


def load_scenes(path: Path = SCENES_FILE, root: Path | None = None) -> dict:
    """Read a scenes file. With `root` (the web root), also check every image exists there."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    for key in ("rooms", "npcs", "party"):
        if not raw.get(key):
            raise ValueError(f"{path}: '{key}' must not be empty")
    scenes = {
        "rooms": [room_entry(r) for r in raw["rooms"]],
        "npcs": raw["npcs"],
        "party": party_frames(raw["party"]),
    }
    if root is not None:
        paths = [r["src"] for r in scenes["rooms"]] + scenes["npcs"]
        paths += [p for frames in scenes["party"].values() for p in frames.values()]
        missing = sorted({p for p in paths if not (root / p).is_file()})
        if missing:
            raise ValueError(f"{path}: not found under {root}: {', '.join(missing)}")
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


def pick_party(rng: random.Random) -> list[tuple[str, str]]:
    """[(member, state)] in walking order.

    Once in a while everybody is a robot. Otherwise 1 to 4 members, each size equally
    likely, joining in story order (Ness, then Paula, Jeff, Poo); each member may be
    unconscious (a ghost, or now and then a diamond). Somebody has to be conscious, so an
    all-down party is drawn again from scratch. As in the game, the conscious members
    walk in front.
    """
    if rng.random() < P_ROBOTS:
        return [(m, "robot") for m in MEMBERS]
    while True:
        chosen = MEMBERS[:rng.randint(1, len(MEMBERS))]
        states = {}
        for m in chosen:
            if rng.random() >= P_UNCONSCIOUS:
                states[m] = "alive"
            else:
                states[m] = "diamond" if rng.random() < P_DIAMOND else "ghost"
        if "alive" in states.values():
            break
    ordered = [m for m in MEMBERS if m in states]
    return [(m, states[m]) for m in ordered if states[m] == "alive"] + \
        [(m, states[m]) for m in ordered if states[m] != "alive"]


def party_feet(spot, n: int) -> list[tuple[int, int]]:
    """Where each party member's feet go (bottom middle of the sprite), leader first."""
    x, y = spot
    return [(x, y + LEAD + i * STEP) for i in range(n)]


def pick_scene(date_str: str, scenes: dict, rng: random.Random | None = None) -> dict:
    """The scene for a date. With `rng`, a random scene instead (for trying out art)."""
    date = dt.date.fromisoformat(date_str)
    if rng:
        room, npc = rng.choice(scenes["rooms"]), rng.choice(scenes["npcs"])
    else:
        room, npc = pick(scenes["rooms"], date, "room"), pick(scenes["npcs"], date, "npc")
    party = pick_party(rng or random.Random(f"party:{date_str}"))
    feet = party_feet(room["spot"], len(party))
    return {
        "room": room["src"],
        "spot": room["spot"],
        "npc": npc,
        "party": [
            {"name": m, "state": s, "src": scenes["party"][m][s], "x": x, "y": y}
            for (m, s), (x, y) in zip(party, feet)
        ],
    }
