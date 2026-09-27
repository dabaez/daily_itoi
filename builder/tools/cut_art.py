"""Cut the real EarthBound art out of The Spriters Resource sheets into web/art/.

The sheets are downloaded once into .art-cache/sheets/ (gitignored) and everything this
writes goes to web/art/ (gitignored too), so no Nintendo asset ever enters the repo.
Only this script, which says where to cut, is committed.

    uv run --group tools tools/cut_art.py            # (re)build web/art/
    uv run --group tools tools/cut_art.py --preview  # also write .art-cache/preview/

The preview draws every room with a full party and the widest and tallest NPCs standing
on its spot, so you can check nobody ends up on top of the furniture.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scene  # noqa: E402  (for the party layout the preview mirrors)

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
ART = WEB / "art"
CACHE = ROOT / ".art-cache"
SITE = "https://www.spriters-resource.com"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"

# Sheet name -> asset id on https://www.spriters-resource.com/snes/earthbound/
SHEETS = {
    "ness": 104953,
    "paula": 104954,
    "jeff": 104955,
    "poo": 104956,
    "npcs_people": 3153,
    "npcs_creatures": 146867,
    "mr_saturn": 146862,
    "overworld_enemies": 146874,
    "onett_ext": 3162,
    "onett_int": 3173,
    "twoson_ext": 146452,
    "twoson_int": 147616,
    "threed_ext": 3178,
    "fourside_ext": 20929,
    "summers_ext": 3177,
    "winters_ext": 3179,
    "winters_int": 146562,
    "scaraba_ext": 3165,
    "dalaam_ext": 3169,
    "dalaam_int": 146563,
    "saturn_valley": 3175,
    "happy_happy": 3170,
    "peaceful_rest": 146369,
    "tenda_village": 146451,
    "magicant": 3159,
    "moonside": 3160,
    "lost_underworld": 146459,
    "dusty_dunes": 146458,
}

# Background colours of each character sheet, made transparent when cutting.
BG = {
    "ness": [(0, 127, 127), (42, 83, 209)],  # sheet, and the box behind each frame
    "paula": [(200, 191, 231)],
    "jeff": [(200, 191, 231)],
    "poo": [(200, 191, 231)],
    "npcs_people": [(0, 162, 232)],
    "npcs_creatures": [(0, 162, 232)],
    "mr_saturn": [(0, 162, 232)],
    "overworld_enemies": [(0, 162, 232)],
}

# ---------------------------------------------------------------- party
# Standing frames facing up (away from the camera). (sheet, x, y, w, h); the M. Bison
# sheets have no frame boxes, so their rectangles are loose and get tightened.

NESS_FRAME = lambda col, y: ("ness", 1 + 17 * col, y, 16, 24)  # noqa: E731

PARTY = {
    "ness": {
        "alive": NESS_FRAME(8, 14),
        "ghost": NESS_FRAME(2, 131),
        "robot": NESS_FRAME(9, 210),
    },
    "paula": {
        "alive": ("paula", 34, 2, 19, 27),
        "ghost": ("paula", 302, 2, 18, 27),
        "robot": ("paula", 34, 29, 19, 27),
    },
    "jeff": {
        "alive": ("jeff", 34, 2, 19, 27),
        "ghost": ("jeff", 302, 2, 18, 27),
        "robot": ("jeff", 34, 29, 19, 27),
    },
    "poo": {
        "alive": ("poo", 34, 2, 19, 27),
        "ghost": ("poo", 302, 2, 18, 27),
        "robot": ("poo", 34, 29, 19, 27),
    },
}
# Diamondized: the game uses one statue for everybody. On the M. Bison sheets' last row
# it comes after the burned frame: facing down (grey face), then this one, facing up.
DIAMOND = ("jeff", 37, 66, 18, 27)

# ---------------------------------------------------------------- NPCs
# Standing frames facing down (toward the camera).

# The people sheet is a grid of 16 columns x 25 px rows. Each character takes a 4x2 block
# of cells whose bottom-left cell faces down; these are the exceptions.
PEOPLE_FRONT_OVERRIDES = {(5, 0): (4, 0), (21, 12): (21, 14)}
PEOPLE_BLOCK_ROWS = 23  # the last row is odds and ends

NPC_RECTS = {
    # sheet, loose rectangle around one frame
    "bird_man": ("npcs_creatures", 0, 25, 18, 25),
    "stone_cat": ("npcs_creatures", 68, 25, 19, 25),
    "shadow_bunny": ("npcs_creatures", 136, 25, 19, 25),
    "monkey": ("npcs_creatures", 0, 74, 18, 26),
    "monkey_girl": ("npcs_creatures", 67, 74, 20, 26),
    "chick": ("npcs_creatures", 0, 130, 18, 20),
    "sign_mouse": ("npcs_creatures", 66, 123, 22, 27),
    "white_dog": ("npcs_creatures", 0, 172, 20, 26),
    "cat": ("npcs_creatures", 94, 172, 22, 26),
    "flower": ("npcs_creatures", 106, 204, 21, 23),
    "cow": ("npcs_creatures", 0, 290, 32, 34),
    "mr_saturn": ("mr_saturn", 0, 27, 18, 23),
    "runaway_dog": ("overworld_enemies", 1, 25, 20, 26),
    "spiteful_crow": ("overworld_enemies", 93, 26, 20, 26),
    "coil_snake": ("overworld_enemies", 147, 27, 19, 24),
    "shadow_man": ("overworld_enemies", 1, 75, 20, 26),
    "pink_mouse": ("overworld_enemies", 70, 99, 17, 17),
    "evil_mushroom": ("overworld_enemies", 134, 79, 20, 22),
    "mobile_sprout": ("overworld_enemies", 204, 79, 22, 22),
    "helmet_zombie": ("overworld_enemies", 1, 143, 16, 28),
    "zombie_lady": ("overworld_enemies", 70, 142, 17, 29),
    "punk": ("overworld_enemies", 139, 142, 16, 29),
    "gray_zombie": ("overworld_enemies", 208, 142, 17, 29),
    "top_hat_zombie": ("overworld_enemies", 1, 191, 17, 31),
    "cop_zombie": ("overworld_enemies", 70, 191, 17, 31),
    "lil_ufo": ("overworld_enemies", 139, 192, 17, 25),
    "mighty_bear": ("overworld_enemies", 1, 248, 30, 36),
    "mole": ("overworld_enemies", 124, 266, 16, 16),
    "trash_can": ("overworld_enemies", 1, 306, 16, 22),
    "pumpkin_head": ("overworld_enemies", 123, 309, 16, 27),
    "gorilla": ("overworld_enemies", 195, 309, 17, 32),
    "lamp_ghost": ("overworld_enemies", 1, 378, 20, 27),
    "white_ghost": ("overworld_enemies", 94, 378, 22, 27),
    "mad_duck": ("overworld_enemies", 194, 378, 22, 28),
    "caveman": ("overworld_enemies", 1, 440, 30, 41),
    "ram": ("overworld_enemies", 136, 442, 27, 39),
    "crocodile": ("overworld_enemies", 2, 506, 24, 30),
    "bison": ("overworld_enemies", 137, 506, 28, 30),
    "cactus": ("overworld_enemies", 2, 556, 16, 32),
    "frog": ("overworld_enemies", 70, 564, 14, 24),
    "foppy": ("overworld_enemies", 87, 566, 16, 17),
    "ostrich": ("overworld_enemies", 1, 614, 26, 37),
    "mad_taxi": ("overworld_enemies", 124, 614, 34, 37),
    "boulder": ("overworld_enemies", 137, 649, 24, 30),
    "robot": ("overworld_enemies", 34, 704, 22, 27),
    "tangoo": ("overworld_enemies", 164, 704, 26, 27),
    "mummy": ("overworld_enemies", 1, 786, 17, 27),
    "petunia": ("overworld_enemies", 70, 796, 32, 25),
    "kiss_of_death": ("overworld_enemies", 137, 787, 17, 26),
    "chomposaur": ("overworld_enemies", 1, 858, 34, 38),
    "purple_dino": ("overworld_enemies", 134, 858, 32, 38),
    "starman": ("overworld_enemies", 1, 933, 18, 29),
    "antenna_alien": ("overworld_enemies", 69, 962, 28, 34),
    "green_slime": ("overworld_enemies", 1, 993, 34, 34),
    "red_slime": ("overworld_enemies", 69, 993, 34, 34),
    "stone_guardian": ("overworld_enemies", 134, 993, 32, 34),
}
NPC_MAX = (32, 44)  # anything bigger crowds the text box or the party

# ---------------------------------------------------------------- rooms
# (name, sheet, x, y[, options]): a 256x224 window whose top-left is x, y on the sheet.
# The NPC stands at scene.DEFAULT_SPOT unless options give a "spot" (in the window), and
# the party lines up below. Every spot was checked in the preview: NPC and party stand on
# open ground, clear of furniture, trees, signs and water. Anything outside the map, the
# sheet's own background, or outside an optional "clip" (x0, y0, x1, y1 on the sheet,
# for interiors packed next to each other) turns black, like around rooms in the game.
ROOMS: list[tuple] = [
    ("onett_town_sign", "onett_ext", 2000, 914),
    ("onett_block", "onett_ext", 1128, 770),
    ("onett_woods", "onett_ext", 2252, 1690),
    ("onett_road_end", "onett_ext", 2600, 1378),
    ("onett_path", "onett_ext", 1512, 1758),
    ("twoson_flowers", "twoson_ext", 616, 592),
    ("twoson_cliff", "twoson_ext", 800, 2556),
    ("twoson_town_sign", "twoson_ext", 1320, 1424),
    ("twoson_lawn", "twoson_ext", 2256, 1040),
    ("twoson_hospital", "twoson_ext", 1796, 112),
    ("twoson_clearing", "twoson_ext", 772, 40),
    ("threed_graveyard", "threed_ext", 1572, 240),
    ("threed_brick", "threed_ext", 1872, 560),
    ("threed_hotel", "threed_ext", 976, 560),
    ("threed_dead_trees", "threed_ext", 360, 1268),
    ("threed_alley", "threed_ext", 1936, 828),
    ("threed_brick_path", "threed_ext", 1168, 208),
    ("fourside_heliport", "fourside_ext", 1364, 296),
    ("fourside_corner", "fourside_ext", 852, 1364),
    ("fourside_park", "fourside_ext", 1328, 1028),
    ("fourside_yard", "fourside_ext", 1696, 708),
    ("fourside_museum", "fourside_ext", 1028, 1036),
    ("fourside_fire_escape", "fourside_ext", 1776, 1072),
    ("summers_promenade", "summers_ext", 2504, 180),
    ("summers_beach", "summers_ext", 2264, 272),
    ("winters_tent", "winters_ext", 532, 1140),
    ("winters_snowfield", "winters_ext", 376, 828),
    ("winters_ridge", "winters_ext", 760, 664),
    ("scaraba_pyramid", "scaraba_ext", 672, 1552),
    ("scaraba_oasis", "scaraba_ext", 52, 1344),
    ("dalaam_hut", "dalaam_ext", 128, 264),
    ("dalaam_path", "dalaam_ext", 400, 128),
    ("saturn_valley_cave", "saturn_valley", 1840, 104),
    ("saturn_valley_hills", "saturn_valley", 1948, 424),
    ("saturn_valley_meadow", "saturn_valley", 1392, 388),
    ("happy_happy_farm", "happy_happy", 100, 432),
    ("happy_happy_bushes", "happy_happy", 684, 512),
    ("happy_happy_sign", "happy_happy", 464, 156),
    ("happy_happy_canyon", "happy_happy", 704, 144),
    ("peaceful_rest_pines", "peaceful_rest", 288, 944),
    ("peaceful_rest_cabin", "peaceful_rest", 1480, 228),
    ("peaceful_rest_cliffs", "peaceful_rest", 1100, 484),
    ("tenda_village_mushrooms", "tenda_village", 180, 108),
    ("tenda_village_rocks", "tenda_village", 432, 176),
    ("magicant_shells", "magicant", 892, 420),
    ("magicant_loop", "magicant", 272, 100),
    ("magicant_bend", "magicant", 588, 228),
    ("lost_underworld_fence", "lost_underworld", 492, 176),
    ("lost_underworld_swamp", "lost_underworld", 944, 668),
    ("lost_underworld_pond", "lost_underworld", 576, 512),
    ("lost_underworld_rocks", "lost_underworld", 136, 496),
    ("dusty_dunes_cactus", "dusty_dunes", 1968, 1064),
    ("dusty_dunes_drugs", "dusty_dunes", 832, 1084),
    ("twoson_department_store", "twoson_int", 1264, 96),
    ("twoson_department_store_escalators", "twoson_int", 988, 320),
    ("twoson_chaos_theater", "twoson_int", 384, 26, {"clip": (256, 0, 768, 228)}),
    ("winters_lab", "winters_int", 184, 388, {"clip": (0, 324, 514, 584)}),
    ("dalaam_throne_room", "dalaam_int", 60, -12, {"spot": (128, 134), "clip": (0, 0, 384, 190)}),
    ("dalaam_palace_door", "dalaam_int", 172, -12, {"clip": (0, 0, 384, 190)}),
    ("dalaam_palace_hall", "dalaam_int", 462, -6, {"clip": (384, 0, 899, 190)}),
]
SHEET_BG = {"onett_int": [(128, 125, 198), (197, 193, 255)], "twoson_int": [(0, 162, 232)], "winters_int": [(0, 162, 232)], "dalaam_int": [(0, 162, 232)]}

STAGE = (256, 224)

# ---------------------------------------------------------------- sheets


def sheet(name: str) -> Image.Image:
    path = CACHE / "sheets" / f"{name}.png"
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        page = f"{SITE}/snes/earthbound/asset/{SHEETS[name]}/"
        html = requests.get(page, headers={"User-Agent": UA}, timeout=30).text
        m = re.search(rf"/media/assets/\d+/{SHEETS[name]}\.\w+(\?[^\"']*)?", html)
        if not m:
            raise RuntimeError(f"no image link on {page}")
        r = requests.get(SITE + m.group(0), headers={"User-Agent": UA, "Referer": page}, timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
        time.sleep(1)  # be gentle with the site
    return Image.open(path).convert("RGBA")


_sheets: dict[str, Image.Image] = {}


def get(name: str) -> Image.Image:
    if name not in _sheets:
        _sheets[name] = sheet(name)
    return _sheets[name]


def clear_bg(img: Image.Image, colors) -> Image.Image:
    img = img.copy()
    px = img.load()
    keys = {tuple(c[:3]) for c in colors}
    for y in range(img.height):
        for x in range(img.width):
            if px[x, y][:3] in keys:
                px[x, y] = (0, 0, 0, 0)
    return img


def drop_slivers(img: Image.Image) -> Image.Image:
    """Frames sit 1px apart on the sheets, so a loose rectangle catches bits of its
    neighbours. Drop small pieces that touch an edge."""
    px = img.load()
    w, h = img.size
    seen = set()
    pieces = []
    for sy in range(h):
        for sx in range(w):
            if (sx, sy) in seen or not px[sx, sy][3]:
                continue
            stack, piece = [(sx, sy)], []
            seen.add((sx, sy))
            while stack:
                x, y = stack.pop()
                piece.append((x, y))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        n = (x + dx, y + dy)
                        if 0 <= n[0] < w and 0 <= n[1] < h and n not in seen and px[n][3]:
                            seen.add(n)
                            stack.append(n)
            pieces.append(piece)
    biggest = max((len(p) for p in pieces), default=0)
    img = img.copy()
    px = img.load()
    for piece in pieces:
        at_edge = any(x in (0, w - 1) or y in (0, h - 1) for x, y in piece)
        if at_edge and len(piece) < biggest * 0.3:
            for p in piece:
                px[p] = (0, 0, 0, 0)
    return img


def cut(name: str, x: int, y: int, w: int, h: int, *, tighten: bool = True) -> Image.Image:
    img = clear_bg(get(name).crop((x, y, x + w, y + h)), BG[name])
    if tighten:
        img = drop_slivers(img)
        box = img.getbbox()
        if not box:
            raise ValueError(f"nothing at {name} {x},{y} {w}x{h}")
        img = img.crop(box)
    return img


def on_canvas(img: Image.Image, w: int, h: int) -> Image.Image:
    """Stand a sprite on the bottom middle of a w x h canvas."""
    out = Image.new("RGBA", (max(w, img.width), max(h, img.height)), (0, 0, 0, 0))
    out.paste(img, ((out.width - img.width) // 2, out.height - img.height))
    return out


def even_width(img: Image.Image) -> Image.Image:
    """Sprites are placed by their bottom middle; an even width keeps that on a whole pixel."""
    return on_canvas(img, img.width + img.width % 2, img.height)


# ---------------------------------------------------------------- build


def party_frame(spec) -> Image.Image:
    name, *rect = spec
    if name == "ness":
        return cut(name, *rect, tighten=False)
    return on_canvas(cut(name, *rect), 16, 24)


def people_cells() -> dict[str, Image.Image]:
    img = get("npcs_people")
    col_w = img.width / 16
    out = {}
    for br in range(PEOPLE_BLOCK_ROWS + 1):
        for bc in range(4):
            r, c = PEOPLE_FRONT_OVERRIDES.get((2 * br + 1, 4 * bc), (2 * br + 1, 4 * bc))
            if r >= 46:
                continue
            x0, x1 = round(c * col_w), round((c + 1) * col_w)
            spr = cut("npcs_people", x0, 25 * r, x1 - x0, 25)
            out[f"person_{r:02d}_{c:02d}"] = spr
    return out


def room(sheet_name: str, x: int, y: int, clip=None) -> Image.Image:
    src = get(sheet_name)
    if clip:
        src = src.crop(clip)
        x, y = x - clip[0], y - clip[1]
    part = src.crop((x, y, x + STAGE[0], y + STAGE[1]))
    part = clear_bg(part, SHEET_BG.get(sheet_name, []))
    out = Image.new("RGBA", STAGE, (0, 0, 0, 255))
    out.alpha_composite(part)
    return out.convert("RGB")


def write(img: Image.Image, rel: str) -> str:
    path = ART / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=True)
    return f"art/{rel}"


def build() -> dict:
    for sub in ("party", "npcs", "rooms"):  # so renamed or dropped art doesn't linger
        shutil.rmtree(ART / sub, ignore_errors=True)
    party = {}
    for member, frames in PARTY.items():
        party[member] = {state: write(party_frame(spec), f"party/{member}_{state}.png") for state, spec in frames.items()}
    diamond = write(party_frame(DIAMOND), "party/diamond.png")
    for frames in party.values():
        frames["diamond"] = diamond

    sprites = people_cells()
    for name, (sheet_name, *rect) in NPC_RECTS.items():
        sprites[name] = cut(sheet_name, *rect)
    npcs = []
    for name, spr in sprites.items():
        if spr.width > NPC_MAX[0] or spr.height > NPC_MAX[1]:
            print(f"skipping {name}: {spr.width}x{spr.height} is bigger than {NPC_MAX}", file=sys.stderr)
            continue
        npcs.append(write(even_width(spr), f"npcs/{name}.png"))

    rooms = []
    for name, sheet_name, x, y, *opts in ROOMS:
        opts = opts[0] if opts else {}
        src = write(room(sheet_name, x, y, opts.get("clip")), f"rooms/{name}.png")
        rooms.append({"src": src, "spot": list(opts["spot"])} if "spot" in opts else src)

    scenes = {"rooms": rooms, "npcs": npcs, "party": party}
    (ART / "scenes.json").write_text(json.dumps(scenes, indent=2) + "\n", encoding="utf-8")
    return scenes


# ---------------------------------------------------------------- preview


def place(stage: Image.Image, src: str, x: int, y: int) -> None:
    spr = Image.open(WEB / src).convert("RGBA")
    stage.alpha_composite(spr, (x - spr.width // 2, y - spr.height))


def preview(scenes: dict) -> None:
    out_dir = CACHE / "preview"
    out_dir.mkdir(parents=True, exist_ok=True)
    # The biggest NPC and a full party on every room's spot, 12 rooms to a page.
    npc_sizes = {p: Image.open(WEB / p).size for p in scenes["npcs"]}
    biggest = max(npc_sizes, key=lambda p: npc_sizes[p][0] * npc_sizes[p][1])
    members = list(scenes["party"])
    tiles = []
    for entry in scenes["rooms"]:
        r = scene.room_entry(entry)
        stage = Image.open(WEB / r["src"]).convert("RGBA")
        place(stage, biggest, *r["spot"])
        for member, (px, py) in zip(members, scene.party_feet(r["spot"], len(members))):
            place(stage, scenes["party"][member]["alive"], px, py)
        tiles.append((Path(r["src"]).stem, stage))
    for old in out_dir.glob("rooms*.png"):
        old.unlink()
    cols, per_page, z = 4, 12, 2
    for page in range(0, len(tiles), per_page):
        chunk = tiles[page:page + per_page]
        img = Image.new("RGB", (cols * STAGE[0] * z, ((len(chunk) + cols - 1) // cols) * (STAGE[1] * z + 14)), "white")
        d = ImageDraw.Draw(img)
        for i, (label, stage) in enumerate(chunk):
            X = (i % cols) * STAGE[0] * z
            Y = (i // cols) * (STAGE[1] * z + 14)
            d.text((X + 4, Y + 1), label, fill="black")
            img.paste(stage.resize((STAGE[0] * z, STAGE[1] * z), Image.NEAREST), (X, Y + 14))
        img.save(out_dir / f"rooms{page // per_page + 1}.png")

    # Every NPC and party frame, 3x.
    z = 3
    imgs = [(Path(p).stem, Image.open(WEB / p).convert("RGBA")) for p in scenes["npcs"]]
    imgs += [(f"{m}_{s}", Image.open(WEB / p).convert("RGBA")) for m, fr in scenes["party"].items() for s, p in fr.items()]
    cols = 12
    cw, ch = 36 * z, 42 * z + 14
    sprites = Image.new("RGB", (cols * cw, ((len(imgs) + cols - 1) // cols) * ch), (96, 128, 96))
    d = ImageDraw.Draw(sprites)
    for i, (label, img) in enumerate(imgs):
        X, Y = (i % cols) * cw, (i // cols) * ch
        big = img.resize((img.width * z, img.height * z), Image.NEAREST)
        sprites.paste(big, (X + (cw - big.width) // 2, Y + ch - 14 - big.height), big)
        d.text((X + 2, Y + ch - 12), label[:18], fill="white")
        d.line([(X, Y + ch - 1), (X + cw, Y + ch - 1)], fill=(70, 96, 70))
    sprites.save(out_dir / "sprites.png")
    print(f"previews in {out_dir}", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preview", action="store_true", help="also draw previews into .art-cache/preview/")
    args = ap.parse_args()
    scenes = build()
    print(f"wrote {len(scenes['rooms'])} rooms, {len(scenes['npcs'])} NPCs and the party to {ART}", file=sys.stderr)
    if args.preview:
        preview(scenes)


if __name__ == "__main__":
    main()
