# Today's Darling, EarthBound Edition

Shigesato Itoi's daily column *今日のダーリン* from [1101.com](https://www.1101.com/),
translated into English and delivered by an NPC in an EarthBound-style text box. The
room and NPC change every day, and they're the same for every visitor.

This is a non-commercial fan tribute. It shows only today's column and keeps no archive.
See [SPEC.md](SPEC.md) for the design.

```
builder/          daily job: scrape → translate → pick scene → today.json
  build.py        entry point (run by the daily timer)
  scrape.py       1101.com primary source + two "yesterday" fallbacks
  translate.py    the swappable translate() (TRANSLATOR=claude|passthrough)
  scene.py        date-seeded room/NPC picker (no repeats on consecutive days)
  pyproject.toml  dependencies (managed with uv; uv.lock pins them)
  scenes.json     the room / NPC / party arrays
  tools/make_placeholders.py   regenerates the placeholder art
web/              static site (serve this directory with any web server)
  art/            the real EarthBound art and font; gitignored, never committed
deploy/           systemd units for the daily job, env example
scripts/ship.sh   uploads a release to the droplet
```

## Run it locally

```sh
cd builder
export ANTHROPIC_API_KEY=sk-ant-...
uv run build.py            # installs deps on first run, writes ../web/today.json
uv run build.py --force    # rebuild even if the column hasn't changed
uv run build.py --shuffle  # random room, NPC and party for today.json; no scraping or API call

cd ../web && uv run python -m http.server 8000   # open http://localhost:8000
```

The scene comes from the column's date, so `--force` keeps the same one. `--shuffle` is
for trying out the art locally; the next real build puts the date's scene back.

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
  why the timer can run it three times a day for free.
- **Failures:** if scraping or translation fails, the old `today.json` stays in place and
  the site keeps showing the last good day. Details go to the log, and the exit code is 1.
- **Atomic writes:** the file goes to a temp file first and is renamed into place, so
  visitors never get a half-written JSON.
- **Translation:** Claude Sonnet 5 with a prompt that keeps Itoi's warm, run-on voice.
  Override the model with `CLAUDE_MODEL`. A declined or truncated translation counts as a
  failure, so the previous day stays up.

## Art: rooms, NPCs and party

The repo only carries original placeholder pixel art (`web/rooms/`, `web/npcs/`,
`web/party/`, listed in `builder/scenes.json`), so it has no Nintendo assets. The real
art, cut from The Spriters Resource sheets (non-commercial use), lives outside git in
`web/art/`, next to `today.json`, with its own list:

```
web/art/
  scenes.json     rooms, NPCs and party, paths like "art/rooms/onett_town_sign.png"
  rooms/          256×224 px (SNES resolution)
  npcs/           facing down, up to 32×44 px, transparent background
  party/          facing up: <member>_alive, _ghost, _robot, and diamond.png
  fonts/          mother.woff2 (see Font)
```

`tools/cut_art.py` builds all of it except the font. It downloads the sheets once into
`.art-cache/sheets/` (gitignored), cuts them where its tables say, and rewrites
`web/art/{rooms,npcs,party}` and `web/art/scenes.json`. Run it from `builder/`:

```sh
uv run --group tools tools/cut_art.py            # (re)build web/art/
uv run --group tools tools/cut_art.py --preview  # also draw .art-cache/preview/*.png
```

The preview puts the biggest NPC and a full party on every room, so you can check that
nobody stands on furniture, trees or water. To add a room, add a window to `ROOMS` in the
script; to add an NPC, add a rectangle to `NPC_RECTS`.

When `art/scenes.json` exists next to the `today.json` being written, the build uses it
instead of `builder/scenes.json`. If it lists a file that isn't there, the build logs an
error and falls back to the placeholders, so a typo never costs a day's column.

A room is a path, or `{"src": ..., "spot": [x, y]}`. The spot is where the NPC's feet
go (default `[128, 124]`); the party stands below it in a column, facing up. The picker
shuffles through all rooms and all NPCs before repeating, and changing an array's
length reshuffles the upcoming order.

### The party

Picked from the date, like everything else:

- 1 in 500 days, all four are there, as robots.
- Otherwise 1 to 4 members (each size equally likely), joining in story order: Ness,
  Ness and Paula, then Jeff, then Poo. Each one is
  unconscious 10% of the time: a ghost, or 1 time in 10 a diamond. If nobody is
  conscious, the party is picked again from scratch.
- Conscious members walk in front, then the unconscious ones, each group in the order
  Ness, Paula, Jeff, Poo.

`today.json` lists them in walking order with their state and where their feet go.

To regenerate the placeholders, run this from `builder/`:
`uv run --group tools tools/make_placeholders.py > scenes.json`. It overwrites both the
placeholder PNGs and `builder/scenes.json`.

## Font

Put a community recreation of the EarthBound/MOTHER font in `web/art/fonts/` as
`mother.woff2`, `mother.woff` or `mother.ttf` and the site uses it automatically.
Until then it falls back to DotGothic16 from Google Fonts. The browser wraps the text by
measuring whichever font is in use, then cuts it into EarthBound-style parts of at most
three lines, so any font fits.

## Deploy

The site runs on the DigitalOcean droplet as the `darling` site of
[dabaez/droplet-infra](https://github.com/dabaez/droplet-infra) (the "static plus jobs on
the droplet" kind in its `NEW-SITE.md`). Pushing to `main` deploys, through
[deploy.yml](.github/workflows/deploy.yml) and [scripts/ship.sh](scripts/ship.sh).

```
/srv/sites/darling/
  darling.env           ANTHROPIC_API_KEY, 600, darling:darling (never in git or GitHub)
  venv/                 the builder's venv, shared by every release
  published/
    today.json          written by the daily job
    art/                the real art, pushed by hand with rsync (below)
  releases/<id>/
    public/             the committed web/, plus two links:
      today.json -> ../../../published/today.json
      art        -> ../../../published/art
    app/                the repo, for the daily job and its systemd units
  current -> releases/<id>
```

- **Releases** hold only committed files. `ship.sh` takes `web/` from git, so a local
  `web/today.json` or `web/art/` never ships.
- **The daily job** is [darling-build.service](deploy/systemd/darling-build.service),
  started by its timer at 00:10, 06:10 and 12:10 JST. `receive-site` installs both on
  every deploy. It runs `build.py` from the live release with `TODAY_JSON` pointing at
  `~/published/today.json`, which is outside releases, so deploys and rollbacks keep
  today's column. It needs uv installed system-wide in `/usr/local/bin`.
- **The API key** is only on the droplet, in `~/darling.env` (see
  [darling.env.example](deploy/darling.env.example)). CI never calls the API, so GitHub
  doesn't have it.
- **The art** is only on the droplet and your machine. It isn't part of a release, so
  push it with your own login (the deploy key can only run `receive-site`):

  ```sh
  rsync -a --delete --chmod=D755,F644 --chown=darling:darling --rsync-path="sudo rsync" \
    web/art/ <you>@<droplet>:/srv/sites/darling/published/art/
  ```

  No deploy is needed; the next new column uses it. Today's scene keeps the room and NPC it
  picked, so don't delete those two files until the day turns. Otherwise, rerun the build
  with `--force` (one API call).

Day to day, from your machine (with a `darling-deploy` host in `~/.ssh/config`):

```sh
DEPLOY_TARGET=darling-deploy scripts/ship.sh            # upload a release
DEPLOY_TARGET=darling-deploy scripts/ship.sh build      # run the daily job now
DEPLOY_TARGET=darling-deploy scripts/ship.sh rollback   # previous release goes live
DEPLOY_TARGET=darling-deploy scripts/ship.sh releases   # list releases, * is live
```

Logs and timers, as root on the droplet:

```sh
journalctl _SYSTEMD_USER_UNIT=darling-build.service
systemctl --user -M darling@ list-timers
```

nginx serves `/srv/sites/darling/current/public` with no `try_files … /index.html`
fallback. A missing `today.json` has to be a 404, so the page shows "come back later"
instead of failing to parse HTML as JSON.

## Controls

Click, tap, Space, Enter or Z. The first press finishes the page that's typing; the
next one turns the page. After the last page the box closes, and pressing again starts
from the beginning.

## Credits

*今日のダーリン* © Shigesato Itoi / Hobonichi. EarthBound / MOTHER © Nintendo, Ape Inc.
and HAL Laboratory. This is an unofficial, non-commercial fan project, not affiliated
with either.
