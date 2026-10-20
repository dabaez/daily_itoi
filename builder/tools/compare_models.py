"""Translate the same columns with several model/effort setups and write a blind
side-by-side page, to compare translations by reading them rather than by vibes.

    cd builder
    uv run --env-file ../.env tools/compare_models.py                # today's live column
    uv run --env-file ../.env tools/compare_models.py ../web/today.json old/*.json --lang es

Inputs are today.json files (anything with title_ja and text_ja); with none given, it
scrapes today's column. Each run also saves the Japanese it used to --keep (default
compare/columns/), so a small private test set builds up over the days; pass that
folder's files back in to rerun them. Nothing here is published.

The page shows the Japanese next to each setup's translation as A, B, C... in a
shuffled order per column; the key, timings and token counts sit in a closed box
under each column, so read and pick a favourite before opening it.
"""

from __future__ import annotations

import argparse
import html
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import translate  # noqa: E402

DEFAULT_SETUPS = [
    "claude-sonnet-5:medium",  # what ran before the switch
    "claude-sonnet-5-5:medium",  # what runs now
    "claude-sonnet-5-5:high",  # Sonnet 5.5's own default; its effort levels were recalibrated
]
OUT_DIR = Path(__file__).resolve().parent.parent / "compare"


def load_columns(paths: list[Path]) -> list[dict]:
    if not paths:
        import scrape

        col = scrape.scrape_best()
        return [{"date": col.date, "title_ja": col.title, "body_ja": col.body}]
    cols = []
    for p in paths:
        d = json.loads(p.read_text(encoding="utf-8"))
        title, _, body = d["text_ja"].partition("\n\n")
        cols.append({"date": d.get("date", p.stem), "title_ja": d.get("title_ja", title), "body_ja": body})
    return cols


def keep(cols: list[dict], folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for c in cols:
        f = folder / f"{c['date']}.json"
        if not f.exists():
            data = {"date": c["date"], "title_ja": c["title_ja"], "text_ja": f"{c['title_ja']}\n\n{c['body_ja']}"}
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(cols: list[dict], setups: list[str], langs: list[str]) -> list[dict]:
    results = []
    for c in cols:
        for lang in langs:
            row = {**c, "lang": lang, "outputs": []}
            for setup in setups:
                model, _, effort = setup.partition(":")
                effort = effort or translate.EFFORT
                print(f"{c['date']} {lang} {model} @ {effort} ...", file=sys.stderr, flush=True)
                t0 = time.monotonic()
                try:
                    tr = translate._translate_claude(c["title_ja"], c["body_ja"], lang, model=model, effort=effort)
                    out = {"title": tr.title, "paragraphs": tr.paragraphs, "output_tokens": tr.output_tokens}
                except translate.TranslationError as e:
                    out = {"error": str(e)}
                out |= {"setup": f"{model} @ {effort}", "seconds": round(time.monotonic() - t0, 1)}
                row["outputs"].append(out)
            results.append(row)
    return results


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def page(results: list[dict], seed: int) -> str:
    rng = random.Random(seed)
    sections = []
    for r in results:
        outs = r["outputs"][:]
        rng.shuffle(outs)
        jp = "".join(f"<p>{esc(p)}</p>" for p in r["body_ja"].split("\n\n"))
        cols = [f'<div class="col ja"><h3>{esc(r["title_ja"])}</h3>{jp}</div>']
        key = []
        for label, o in zip("ABCDEFGH", outs):
            if "error" in o:
                body = f'<p class="err">{esc(o["error"])}</p>'
                title = "(failed)"
            else:
                body = "".join(f"<p>{esc(p)}</p>" for p in o["paragraphs"])
                title = o["title"]
            cols.append(f'<div class="col"><div class="tag">{label}</div><h3>{esc(title)}</h3>{body}</div>')
            key.append(
                f"<li><b>{label}</b> = {esc(o['setup'])} · {o['seconds']}s"
                f" · {o.get('output_tokens') or '?'} output tokens</li>"
            )
        sections.append(
            f'<section><h2>{esc(r["date"])} · {r["lang"].upper()}</h2>'
            f'<div class="grid" style="--n:{len(cols)}">{"".join(cols)}</div>'
            f'<details><summary>Reveal which is which</summary><ul>{"".join(key)}</ul></details></section>'
        )
    return f"""<!doctype html><meta charset="utf-8"><title>Translation comparison</title>
<style>
body{{font:15px/1.6 system-ui,sans-serif;margin:16px;background:#fafafa;color:#222}}
.grid{{display:grid;grid-template-columns:repeat(var(--n),minmax(260px,1fr));gap:12px;overflow-x:auto}}
.col{{background:#fff;border:1px solid #ddd;border-radius:6px;padding:8px 14px;position:relative}}
.ja{{background:#f3f3f0}} .tag{{position:absolute;top:6px;right:10px;font-weight:700;color:#888}}
h3{{font-size:15px;margin:6px 24px 6px 0}} details{{margin:10px 0 32px}} .err{{color:#b00}}
</style>
<h1>Translation comparison</h1>
<p>Each column's translations are shuffled. Read, pick a favourite, then open the box below it.</p>
{"".join(sections)}"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("inputs", nargs="*", type=Path, help="today.json-style files (default: scrape today's)")
    ap.add_argument("--setup", action="append", help=f"model:effort, repeatable (default: {' '.join(DEFAULT_SETUPS)})")
    ap.add_argument("--lang", action="append", choices=translate.LANGS, help="repeatable (default: en)")
    ap.add_argument("--keep", type=Path, default=OUT_DIR / "columns", help="where to save the Japanese used")
    ap.add_argument("--out", type=Path, default=OUT_DIR / "compare.html")
    ap.add_argument("--seed", type=int, default=None, help="shuffle seed (default: random)")
    a = ap.parse_args()

    cols = load_columns(a.inputs)
    keep(cols, a.keep)
    results = run(cols, a.setup or DEFAULT_SETUPS, a.lang or ["en"])
    seed = a.seed if a.seed is not None else random.randrange(1 << 30)

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(page(results, seed), encoding="utf-8")
    a.out.with_suffix(".json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {a.out} (and .json with the raw results)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
