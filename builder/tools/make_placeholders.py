"""Generate original placeholder art in an EarthBound-ish style.

These stand in until you drop real sprites/backgrounds into web/rooms, web/npcs and
web/party (and list them in builder/scenes.json). Everything here is drawn from
scratch, so the repo carries no Nintendo assets by default.

Rooms are 256x224 (SNES resolution); characters are 16x24.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
OUTLINE = (24, 16, 32, 255)

# ---------------------------------------------------------------- characters


def outline(img: Image.Image) -> Image.Image:
    """Add a 1px dark outline around every opaque pixel (the SNES sprite look)."""
    w, h = img.size
    src = img.load()
    out = img.copy()
    dst = out.load()
    for y in range(h):
        for x in range(w):
            if src[x, y][3]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and src[nx, ny][3]:
                    dst[x, y] = OUTLINE
                    break
    return out


def person(skin, hair, shirt, pants, shoes, *, style="short", back=False, extra=None) -> Image.Image:
    img = Image.new("RGBA", (16, 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    shade = tuple(max(0, c - 40) for c in shirt[:3]) + (255,)
    # legs + shoes
    d.rectangle((5, 19, 6, 21), fill=pants)
    d.rectangle((9, 19, 10, 21), fill=pants)
    d.rectangle((4, 22, 6, 22), fill=shoes)
    d.rectangle((9, 22, 11, 22), fill=shoes)
    # torso + arms
    d.rectangle((4, 12, 11, 18), fill=shirt)
    d.rectangle((4, 17, 11, 18), fill=pants)
    d.rectangle((3, 13, 3, 16), fill=shade)
    d.rectangle((12, 13, 12, 16), fill=shade)
    d.point((3, 17), fill=skin)
    d.point((12, 17), fill=skin)
    # head
    d.ellipse((3, 1, 12, 11), fill=skin)
    if back:
        d.ellipse((3, 1, 12, 10), fill=hair)
        d.rectangle((4, 13, 11, 16), fill=shade)  # backpack-ish shading
    else:
        if style == "short":
            d.chord((3, 0, 12, 9), 180, 360, fill=hair)
            d.rectangle((3, 4, 4, 6), fill=hair)
            d.rectangle((11, 4, 12, 6), fill=hair)
        elif style == "cap":
            d.chord((3, 0, 12, 9), 180, 360, fill=hair)
            d.rectangle((2, 4, 13, 4), fill=hair)
        elif style == "long":
            d.chord((3, 0, 12, 9), 180, 360, fill=hair)
            d.rectangle((2, 3, 4, 13), fill=hair)
            d.rectangle((11, 3, 13, 13), fill=hair)
        elif style == "bun":
            d.ellipse((6, -1, 9, 2), fill=hair)
            d.chord((3, 1, 12, 9), 180, 360, fill=hair)
        elif style == "bald":
            d.rectangle((3, 5, 3, 7), fill=hair)
            d.rectangle((12, 5, 12, 7), fill=hair)
        # eyes
        d.point((6, 7), fill=OUTLINE)
        d.point((9, 7), fill=OUTLINE)
        d.point((6, 6), fill=OUTLINE)
        d.point((9, 6), fill=OUTLINE)
    if extra:
        extra(d)
    return outline(img)


SKIN = [(248, 208, 168, 255), (224, 168, 120, 255), (176, 112, 72, 255)]


def c(r, g, b):
    return (r, g, b, 255)


def mustache(d):
    d.rectangle((6, 9, 9, 9), fill=c(232, 232, 232))


def apron(d):
    d.rectangle((5, 13, 10, 18), fill=c(248, 248, 248))


def tie(d):
    d.rectangle((7, 12, 8, 16), fill=c(200, 32, 48))


NPCS = {
    "shopkeeper": person(SKIN[0], c(96, 56, 32), c(64, 120, 200), c(56, 48, 64), c(40, 32, 32), extra=apron),
    "old_man": person(SKIN[1], c(216, 216, 216), c(144, 112, 80), c(88, 72, 56), c(48, 40, 32), style="bald", extra=mustache),
    "lady": person(SKIN[0], c(168, 72, 40), c(224, 104, 152), c(224, 104, 152), c(120, 40, 72), style="long"),
    "kid": person(SKIN[2], c(32, 24, 24), c(248, 200, 48), c(64, 96, 176), c(200, 48, 48), style="cap"),
    "businessman": person(SKIN[0], c(40, 40, 48), c(232, 232, 240), c(64, 64, 88), c(24, 24, 32), extra=tie),
    "grandma": person(SKIN[0], c(200, 200, 216), c(120, 152, 104), c(96, 120, 80), c(72, 56, 48), style="bun"),
    "cook": person(SKIN[1], c(248, 248, 248), c(248, 248, 248), c(72, 72, 80), c(40, 40, 40), style="cap"),
    "hippie": person(SKIN[1], c(208, 160, 64), c(88, 168, 96), c(48, 80, 160), c(96, 64, 40), style="long"),
}

PARTY = {
    "hero": person(SKIN[0], c(56, 40, 32), c(232, 64, 64), c(56, 72, 152), c(200, 40, 40), back=True),
    "girl": person(SKIN[0], c(248, 216, 96), c(240, 144, 184), c(240, 144, 184), c(200, 64, 120), back=True),
    "nerd": person(SKIN[0], c(232, 200, 120), c(64, 128, 88), c(96, 80, 64), c(72, 48, 32), back=True),
    "prince": person(SKIN[1], c(24, 24, 40), c(216, 192, 120), c(216, 192, 120), c(120, 88, 40), back=True),
}

# ---------------------------------------------------------------- rooms

W, H = 256, 224
LEFT, RIGHT, TOP, WALL_BOTTOM, BOTTOM = 24, 232, 16, 104, 216


def tile_floor(d, a, b, size=16):
    for y in range(WALL_BOTTOM, BOTTOM, size // 2):
        for x in range(LEFT, RIGHT, size):
            odd = ((x - LEFT) // size + (y - WALL_BOTTOM) // (size // 2)) % 2
            d.rectangle((x, y, min(x + size, RIGHT) - 1, y + size // 2 - 1), fill=a if odd else b)


def plank_floor(d, a, b):
    for i, y in enumerate(range(WALL_BOTTOM, BOTTOM, 6)):
        d.rectangle((LEFT, y, RIGHT - 1, y + 5), fill=a)
        d.line((LEFT, y + 5, RIGHT - 1, y + 5), fill=b)
        for x in range(LEFT + (i * 23) % 48, RIGHT, 48):
            d.line((x, y, x, y + 5), fill=b)


def walls(d, wall, stripe, trim):
    d.rectangle((LEFT, TOP, RIGHT - 1, WALL_BOTTOM - 1), fill=wall)
    for x in range(LEFT + 4, RIGHT, 12):
        d.line((x, TOP, x, WALL_BOTTOM - 8), fill=stripe)
    d.rectangle((LEFT, WALL_BOTTOM - 8, RIGHT - 1, WALL_BOTTOM - 1), fill=trim)
    d.line((LEFT, WALL_BOTTOM - 8, RIGHT - 1, WALL_BOTTOM - 8), fill=OUTLINE)


def frame(d):
    # side walls seen in 3/4 view, plus the doorway gap at the bottom
    d.rectangle((LEFT - 8, TOP, LEFT - 1, BOTTOM + 7), fill=c(56, 48, 72))
    d.rectangle((RIGHT, TOP, RIGHT + 7, BOTTOM + 7), fill=c(56, 48, 72))
    d.rectangle((LEFT - 8, BOTTOM, 112, BOTTOM + 7), fill=c(56, 48, 72))
    d.rectangle((144, BOTTOM, RIGHT + 7, BOTTOM + 7), fill=c(56, 48, 72))
    d.rectangle((LEFT - 8, TOP - 8, RIGHT + 7, TOP - 1), fill=c(56, 48, 72))


def window(d, x, y, w=32, h=24, sky=c(120, 200, 248)):
    d.rectangle((x - 2, y - 2, x + w + 1, y + h + 1), fill=c(248, 248, 240), outline=OUTLINE)
    d.rectangle((x, y, x + w - 1, y + h - 1), fill=sky)
    d.line((x + w // 2, y, x + w // 2, y + h - 1), fill=c(248, 248, 240))
    d.line((x, y + h // 2, x + w - 1, y + h // 2), fill=c(248, 248, 240))


def shelf(d, x, y, w, h, wood, items):
    d.rectangle((x, y, x + w, y + h), fill=wood, outline=OUTLINE)
    for row in range(y + 4, y + h - 2, 10):
        d.line((x + 1, row + 7, x + w - 1, row + 7), fill=OUTLINE)
        for i, ix in enumerate(range(x + 3, x + w - 4, 6)):
            d.rectangle((ix, row, ix + 3, row + 6), fill=items[(i + row) % len(items)], outline=OUTLINE)


def counter(d, x, y, w, top, front):
    d.rectangle((x, y, x + w, y + 6), fill=top, outline=OUTLINE)
    d.rectangle((x, y + 7, x + w, y + 22), fill=front, outline=OUTLINE)


def rug(d, x, y, w, h, a, b):
    d.rectangle((x, y, x + w, y + h), fill=a, outline=OUTLINE)
    d.rectangle((x + 4, y + 3, x + w - 4, y + h - 3), outline=b)


def plant(d, x, y):
    d.rectangle((x + 2, y + 12, x + 11, y + 20), fill=c(192, 104, 56), outline=OUTLINE)
    d.ellipse((x, y, x + 13, y + 13), fill=c(64, 160, 72), outline=OUTLINE)
    d.point((x + 5, y + 4), fill=c(136, 216, 112))
    d.point((x + 8, y + 7), fill=c(136, 216, 112))


def table(d, x, y, w, cloth):
    d.rectangle((x + 2, y + 10, x + 4, y + 20), fill=c(96, 64, 40), outline=OUTLINE)
    d.rectangle((x + w - 4, y + 10, x + w - 2, y + 20), fill=c(96, 64, 40), outline=OUTLINE)
    d.rectangle((x, y, x + w, y + 10), fill=cloth, outline=OUTLINE)


def new_room() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (W, H), c(0, 0, 0))
    return img, ImageDraw.Draw(img)


def room_drugstore():
    img, d = new_room()
    walls(d, c(248, 232, 176), c(240, 216, 152), c(168, 120, 72))
    tile_floor(d, c(232, 232, 232), c(184, 200, 216))
    shelf(d, 32, 24, 72, 70, c(176, 128, 80), [c(232, 64, 64), c(72, 136, 232), c(248, 216, 72), c(96, 200, 120)])
    shelf(d, 152, 24, 72, 70, c(176, 128, 80), [c(248, 152, 200), c(248, 248, 248), c(120, 88, 200)])
    counter(d, 164, 150, 56, c(232, 200, 136), c(176, 120, 72))
    frame(d)
    return img


def room_diner():
    img, d = new_room()
    walls(d, c(200, 64, 64), c(184, 48, 56), c(248, 248, 248))
    tile_floor(d, c(248, 248, 248), c(40, 40, 48))
    window(d, 48, 32)
    window(d, 176, 32)
    counter(d, 88, 60, 80, c(216, 216, 224), c(72, 184, 200))
    table(d, 40, 150, 32, c(248, 248, 248))
    table(d, 184, 150, 32, c(248, 248, 248))
    frame(d)
    return img


def room_living_room():
    img, d = new_room()
    walls(d, c(168, 200, 136), c(152, 184, 120), c(120, 88, 56))
    plank_floor(d, c(200, 144, 88), c(152, 96, 56))
    window(d, 112, 28, 40, 32)
    rug(d, 72, 128, 112, 56, c(200, 72, 88), c(248, 216, 120))
    plant(d, 36, 76)
    plant(d, 206, 76)
    # couch
    d.rectangle((40, 40, 96, 72), fill=c(96, 120, 200), outline=OUTLINE)
    d.rectangle((44, 58, 92, 72), fill=c(120, 144, 224), outline=OUTLINE)
    frame(d)
    return img


def room_hotel_lobby():
    img, d = new_room()
    walls(d, c(232, 216, 248), c(216, 200, 240), c(160, 120, 176))
    tile_floor(d, c(216, 176, 120), c(184, 144, 96))
    rug(d, 96, 104, 64, 112, c(176, 40, 56), c(248, 200, 72))
    counter(d, 160, 56, 60, c(232, 216, 176), c(128, 80, 136))
    plant(d, 32, 76)
    plant(d, 72, 76)
    # stairs hint
    for i in range(6):
        d.rectangle((32, 24 + i * 7, 88, 30 + i * 7), fill=c(200, 184, 216), outline=OUTLINE)
    frame(d)
    return img


def room_arcade():
    img, d = new_room()
    walls(d, c(40, 32, 88), c(64, 48, 120), c(248, 72, 168))
    tile_floor(d, c(56, 40, 104), c(32, 24, 64))
    for i, x in enumerate(range(32, 224, 40)):
        body = [c(232, 64, 64), c(72, 136, 232), c(248, 200, 48), c(96, 200, 120), c(200, 96, 232)][i % 5]
        d.rectangle((x, 30, x + 28, 94), fill=body, outline=OUTLINE)
        d.rectangle((x + 4, 36, x + 24, 56), fill=c(16, 16, 24), outline=OUTLINE)
        d.rectangle((x + 7, 42, x + 13, 48), fill=c(120, 248, 168))
        d.rectangle((x + 4, 62, x + 24, 70), fill=c(40, 40, 48), outline=OUTLINE)
    frame(d)
    return img


def room_library():
    img, d = new_room()
    walls(d, c(120, 80, 48), c(104, 64, 40), c(72, 48, 32))
    plank_floor(d, c(168, 112, 64), c(120, 80, 48))
    books = [c(176, 40, 40), c(40, 88, 160), c(56, 128, 72), c(208, 168, 64), c(120, 56, 120)]
    for x in (28, 88, 156):
        shelf(d, x, 22, 56, 74, c(96, 56, 32), books)
    table(d, 164, 160, 56, c(56, 112, 72))
    frame(d)
    return img


ROOMS = {
    "drugstore": room_drugstore,
    "diner": room_diner,
    "living_room": room_living_room,
    "hotel_lobby": room_hotel_lobby,
    "arcade": room_arcade,
    "library": room_library,
}


def main():
    for sub in ("rooms", "npcs", "party"):
        (WEB / sub).mkdir(parents=True, exist_ok=True)
    rooms, npcs, party = [], [], []
    for name, fn in ROOMS.items():
        path = f"rooms/{name}.png"
        fn().convert("RGB").save(WEB / path, optimize=True)
        rooms.append(path)
    for name, img in NPCS.items():
        path = f"npcs/{name}.png"
        img.save(WEB / path, optimize=True)
        npcs.append(path)
    for name, img in PARTY.items():
        path = f"party/{name}.png"
        img.save(WEB / path, optimize=True)
        party.append(path)
    print(json.dumps({"rooms": rooms, "npcs": npcs, "party": party}, indent=2))


if __name__ == "__main__":
    main()
