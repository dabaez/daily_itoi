# Today's Darling, EarthBound Edition

Shigesato Itoi's daily column *今日のダーリン* from [1101.com](https://www.1101.com/),
translated into English and delivered by an NPC in an EarthBound-style text box. The
room and NPC change every day, and they're the same for every visitor.

This is a non-commercial fan tribute. It shows only today's column and keeps no archive.
See [SPEC.md](SPEC.md) for the design.

```
builder/          daily job: scrape → translate → pick scene → today.json
  build.py        entry point (run this from cron)
  scrape.py       1101.com primary source + two "yesterday" fallbacks
  translate.py    the swappable translate() (TRANSLATOR=claude|passthrough)
  scene.py        date-seeded room/NPC picker (no repeats on consecutive days)
  cloudflare.py   optional purge of today.json after each build
  pyproject.toml  dependencies (managed with uv; uv.lock pins them)
  scenes.json     the room / NPC / party arrays
  tools/make_placeholders.py   regenerates the placeholder art
web/              static site served by nginx
deploy/           nginx config, crontab, cron wrapper, env example, Cloudflare notes
```

## Run it locally

```sh
cd builder
export ANTHROPIC_API_KEY=sk-ant-...
uv run build.py            # installs deps on first run, writes ../web/today.json
uv run build.py --force    # rebuild even if the column hasn't changed

cd ../web && python3 -m http.server 8000   # open http://localhost:8000
```

`TRANSLATOR=passthrough` runs the whole pipeline without an API key. The pages come out in
Japanese, but it's handy for checking scraping and layout.

`web/today.json` is generated and gitignored (the column is meant to be ephemeral, so
it never goes into version control). Until the first build, the page shows a "come back
later" message.

## How the daily job behaves

- **Today** means today in JST, whatever timezone the server runs in.
- **Sources:** it tries the mobile column page first, then the two "yesterday" pages.
  It only replaces `today.json` with a newer column (or the same day with changed text),
  so a fallback never overwrites today with yesterday.
- **Idempotent:** if the column hasn't changed, it exits without calling the API. That's
  why cron can run it three times a day for free.
- **Failures:** if scraping or translation fails, the old `today.json` stays in place and
  the site keeps showing the last good day. Details go to the log, and the exit code is 1.
- **Atomic writes:** the file goes to a temp file first and is renamed into place, so
  visitors never get a half-written JSON.
- **Translation:** Claude Sonnet 5 with a prompt that keeps Itoi's warm, run-on voice.
  Override the model with `CLAUDE_MODEL`. A declined or truncated translation counts as a
  failure, so the previous day stays up.

## Adding rooms and NPCs

1. Drop images into `web/rooms/` (256×224 px, SNES resolution) or `web/npcs/` (16×24 px,
   front-facing, transparent background).
2. Add their paths to the arrays in `builder/scenes.json`.

That's it. The picker indexes into those arrays and shuffles through all of them before
repeating. Changing an array's length reshuffles the upcoming order.

The art that ships with the repo is original placeholder pixel art, so the repo carries
no Nintendo assets. To regenerate it, run this from `builder/`:
`uv run --group tools tools/make_placeholders.py > scenes.json`. For the real look, get
sprites and backgrounds from The Spriters Resource (non-commercial use), then update
`scenes.json`. Rerunning the placeholder script overwrites both the
placeholder PNGs and `scenes.json`.

Party sprites (`web/party/`, back-facing, 16×24) come from the `party` array and are
drawn front to back.

## Font

Put a community recreation of the EarthBound/MOTHER font in `web/fonts/` as
`mother.woff2`, `mother.woff` or `mother.ttf` and the site uses it automatically.
Until then it falls back to DotGothic16 from Google Fonts. The browser wraps the text by
measuring whichever font is in use, then cuts it into EarthBound-style parts of at most
three lines, so any font fits.

## Deploy (DigitalOcean droplet + Cloudflare)

```sh
# on the droplet, as the deploy user
sudo mkdir -p /srv/todays-darling /var/log/todays-darling && sudo chown $USER /srv/todays-darling /var/log/todays-darling
curl -LsSf https://astral.sh/uv/install.sh | sh     # installs uv to ~/.local/bin
rsync -a --exclude .venv ./ droplet:/srv/todays-darling/
cd /srv/todays-darling/builder && uv sync --frozen --no-dev

sudo cp deploy/todays-darling.env.example /etc/todays-darling.env   # fill in the key
sudo chown $USER /etc/todays-darling.env && chmod 600 /etc/todays-darling.env

sudo apt install nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/todays-darling   # set server_name
sudo ln -s ../sites-available/todays-darling /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

deploy/run-build.sh            # first build by hand; check /var/log/todays-darling/build.log
crontab deploy/crontab         # 00:10, 06:10, 12:10 JST
```

The deploy user needs write access to `web/` (the job writes `web/today.json`), and
nginx needs read access. Cloudflare setup (DNS, origin cert, cache rule for `today.json`,
purge token) is in [deploy/cloudflare.md](deploy/cloudflare.md).

## Controls

Click, tap, Space, Enter or Z. The first press finishes the page that's typing; the
next one turns the page. After the last page the box closes, and pressing again starts
from the beginning.

## Credits

*今日のダーリン* © Shigesato Itoi / Hobonichi. EarthBound / MOTHER © Nintendo, Ape Inc.
and HAL Laboratory. This is an unofficial, non-commercial fan project, not affiliated
with either.
