# SPEC.md — "Today's Darling, EarthBound Edition"

A static website that displays Shigesato Itoi's daily column *今日のダーリン* ("Today's
Darling") from 1101.com, translated into English, presented as an **EarthBound text
box**: a random NPC in a random room delivering the column to the party. The random
NPC/room is chosen **once per day, server-side**, so every visitor on a given day sees
the same scene (not randomized per visit).

---

## 1. Core architecture

Split into two parts:

- **Daily build job** — runs daily on a timer. Does all the work: scrape → translate
  → deterministically pick room + NPC → write `today.json`.
- **Dumb static frontend** — reads `today.json` and renders/animates it. Contains **no**
  randomness and **no** scraping/translation logic.

Why this split:
- Guarantees "same scene for everyone that day."
- One translation API call per day (cheap).
- Trivial to serve and cache: the site is just static files.

**Do not randomize the NPC/room on the frontend** — that would give each visitor a
different scene. All randomness lives in the daily job, seeded by the date.

---

## 2. Decisions locked in for this build

- **The column is intentionally ephemeral.** Itoi does not archive *今日のダーリン*; it
  disappears the next day. Therefore:
  - The job **must** run daily or entries are missed.
  - Keep this a **non-commercial fan tribute**. Show **only "today"** — do **not** build a
    searchable public archive of translated past entries.
- **EarthBound assets are Nintendo IP.** Non-commercial fan use only. Source sprites/
  backgrounds from The Spriters Resource; use a community recreation of the Mother/
  EarthBound font.
- **Translation engine:** use an LLM (e.g. Claude) rather than plain machine translation,
  to preserve Itoi's warm, casual, run-on voice. The column is short, so cost is
  negligible. Keep the engine behind a single swappable function so it can be changed.

---

## 3. Components

### 3.1 Daily build job
Runs ~once/day. Steps:

1. **Scrape today's column.**
   - Primary source (cleanest to parse): `https://www.1101.com/m/recent/darling.html`
   - Fallbacks if primary fails or a day was missed:
     - `https://www.1101.com/darling_column/yesterday.html`
     - `https://www.1101.com/m/recent/yesterdays_darling.html`
   - Extract the column body text as clean Japanese plain text.
2. **Translate** JA → EN via the swappable translation function.
3. **Deterministically pick** one room and one NPC:
   - Seed the RNG with the date string (e.g. `YYYY-MM-DD` in JST) so the pick is
     reproducible and identical for all visitors.
4. **Write `today.json`** to the web root, with the English text as plain paragraphs.
5. **Be defensive:**
   - On scrape/translate failure, **keep the previous `today.json`** rather than blanking
     the site.
   - Log all failures.
   - Use JST for "today" (the site is Japanese).

### 3.2 Static frontend
- Fetch `today.json`.
- Render, back to front: room background → party sprite(s) at bottom → NPC sprite →
  EarthBound text box.
- **Text box** must reproduce the EarthBound look: blue gradient border, Mother font,
  typewriter character reveal, blinking "next" arrow.
- **Dialogue flow, as in the game:** the box shows 3 lines. The text is cut into parts of
  at most 3 lines (at a sentence end where possible, else a comma, else between words);
  each part starts with a bullet and ends at the blinking arrow. Click / spacebar
  continues, and the next part is written on the following line, the box scrolling up
  one line at a time. Wrapping and splitting happen in the browser, measured with the
  font actually in use (the stage is fixed-size and scaled, so screen size never changes
  the wrap); the translation step doesn't know about the box.
- Show the date and the English title above the scene, not in the dialogue.
- Include a small credit/footer linking the original column and noting it's a fan tribute,
  with a collapsed option to read the whole translation as plain text. The Japanese
  original isn't shown; the footer links to it.

### 3.3 Assets
- `rooms/` — array of background images.
- `npcs/` — array of NPC sprites, facing down.
- `party/` — Ness, Paula, Jeff and Poo facing up, alive, as ghosts, as robots, and the
  diamond statue. The job picks who's in the party and in what state (see README).
- Font file for the EarthBound/Mother font.
- Rooms and NPCs are just arrays the daily job indexes into — adding more later should be
  trivial (no code changes beyond dropping files in and extending the array).

### 3.4 Deploy
- Pushing to `main` uploads a release to a server over SSH (see README, "Deploy").
  Releases carry the committed `web/` as is; nothing is built.
- The build job runs as a **systemd timer** on the server, a few times a day at JST
  times, and writes `today.json` outside the releases.
- The API key and the real EarthBound art live only on the server, never in the repo.
- Hosting, DNS and any CDN in front of the site are set up outside this repo.

---

## 4. `today.json` shape (rough)

```json
{
  "date": "2026-09-21",
  "source_url": "https://www.1101.com/m/recent/darling.html",
  "text_ja": "……",
  "title_en": "Title",
  "paragraphs_en": [
    "First paragraph of translated text…",
    "…"
  ],
  "room": "art/rooms/onett_town_sign.png",
  "spot": [128, 124],
  "npc": "art/npcs/mr_saturn.png",
  "party": [
    {"name": "ness", "state": "alive", "src": "art/party/ness_alive.png", "x": 128, "y": 142},
    {"name": "paula", "state": "ghost", "src": "art/party/paula_ghost.png", "x": 128, "y": 158}
  ]
}
```

The job sends plain paragraphs; the frontend lays them out, because only the browser
knows the exact width of the font it ends up using.

---

## 5. Suggested repo layout

```
/builder        # the daily job: scrape + translate + pick + write today.json
/web            # static site
  /rooms        # background images
  /npcs         # NPC sprites
  /fonts        # EarthBound/Mother font
  index.html
  app.js
  styles.css
  today.json    # generated by the build job
/deploy         # systemd timer + service for the daily job, env example
README.md
```

---

## 6. Build order (suggested)

1. Frontend with a hardcoded `today.json` (get the EarthBound text box + pagination
   feeling right first).
2. Scraper against the primary source, with the two fallbacks.
3. Translation function (swappable).
4. Deterministic date-seeded room/NPC picker + text pagination → write `today.json`.
5. Wire the daily job end to end.
6. Deploy: timer that runs the build.
7. Add more rooms/NPCs to the arrays.

## 7. Definition of done
- Visiting the site shows today's column in English, in an EarthBound text box, with a
  room + NPC that is the same for all visitors that day and different from yesterday.
- If scraping fails on a given day, the site still shows the last good day rather than
  breaking.
