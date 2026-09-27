"""Daily job: scrape -> translate -> pick scene -> write today.json.

Safe to run several times a day. It skips translation when the column hasn't changed,
and on any failure it leaves the existing today.json alone so the site keeps showing
the last good day.

Exit codes: 0 = wrote a new today.json or nothing to do, 1 = failed (old file kept).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import random
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

import scene
import scrape
import translate

JST = ZoneInfo("Asia/Tokyo")
DEFAULT_OUT = Path(__file__).resolve().parent.parent / "web" / "today.json"

log = logging.getLogger("build")


def today_jst() -> str:
    return dt.datetime.now(JST).date().isoformat()


def load_previous(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception as e:
        log.warning("could not read existing %s: %s", path, e)
        return None


def write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".today.", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)  # readers see either the old file or the new one, never half
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def load_scenes(out: Path) -> dict:
    """The real art isn't in the repo. It lives in art/ next to today.json, with its own
    scenes.json; without it (or if it lists a missing file) the placeholder art is used."""
    art_scenes = out.parent / "art" / "scenes.json"
    if art_scenes.is_file():
        try:
            scenes = scene.load_scenes(art_scenes, root=out.parent)
            log.info("using scenes from %s", art_scenes)
            return scenes
        except Exception as e:
            log.error("can't use %s, falling back to the placeholder art: %s", art_scenes, e)
    return scene.load_scenes()


def build(out: Path, force: bool = False) -> int:
    prev = load_previous(out)
    today = today_jst()

    try:
        col = scrape.scrape_best()
    except scrape.ScrapeError as e:
        log.error("scrape failed; keeping previous today.json: %s", e)
        return 1

    if col.date != today:
        log.warning("column date %s is not today (JST %s); source %s", col.date, today, col.source_url)

    if prev and not force:
        if prev.get("date", "") > col.date:
            log.info("have %s already, source only offers older %s; nothing to do", prev["date"], col.date)
            return 0
        if prev.get("date") == col.date and prev.get("text_ja") == col.text_ja:
            log.info("column for %s unchanged; nothing to do", col.date)
            return 0

    try:
        tr = translate.translate(col.title, col.body)
    except Exception as e:
        log.error("translation failed; keeping previous today.json: %s", e)
        return 1

    scenes = load_scenes(out)
    picked = scene.pick_scene(col.date, scenes)

    data = {
        "date": col.date,
        "source_url": col.source_url,
        "title_ja": col.title,
        "title_en": tr.title,
        "text_ja": col.text_ja,
        "paragraphs_en": tr.paragraphs,
        "room": picked["room"],
        "spot": picked["spot"],
        "npc": picked["npc"],
        "party": picked["party"],
        "translator": tr.engine,
        "generated_at": dt.datetime.now(JST).isoformat(timespec="seconds"),
    }
    write_atomic(out, data)
    party = " ".join(f"{p['name']}({p['state']})" for p in data["party"])
    log.info("wrote %s: %s, %d paragraphs, room=%s npc=%s party=%s", out, col.date, len(tr.paragraphs), data["room"], data["npc"], party)
    return 0


def shuffle(out: Path) -> int:
    """Give the existing today.json a random scene. No scraping, no API call."""
    data = load_previous(out)
    if not data:
        log.error("no %s to shuffle; build it first", out)
        return 1
    picked = scene.pick_scene(data["date"], load_scenes(out), rng=random.Random())
    data.update(room=picked["room"], spot=picked["spot"], npc=picked["npc"], party=picked["party"])
    write_atomic(out, data)
    party = " ".join(f"{p['name']}({p['state']})" for p in data["party"])
    log.info("shuffled %s: room=%s npc=%s party=%s", out, data["room"], data["npc"], party)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path(os.environ.get("TODAY_JSON", DEFAULT_OUT)))
    ap.add_argument("--force", action="store_true", help="rebuild even if the column is unchanged")
    ap.add_argument("--shuffle", action="store_true",
                    help="only give the existing today.json a random scene, to try out the art "
                         "(the next real build puts back the date's scene)")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        return shuffle(args.out) if args.shuffle else build(args.out, force=args.force)
    except Exception:
        log.exception("unexpected failure; previous today.json left in place")
        return 1


if __name__ == "__main__":
    sys.exit(main())
