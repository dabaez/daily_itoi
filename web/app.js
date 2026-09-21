// Renders today.json. No randomness and no scraping here: the daily job decides
// everything, so every visitor sees the same scene.
(() => {
  "use strict";

  const STAGE_W = 256;
  const STAGE_H = 224;
  const LINE_H = 13;
  const MAX_FONT_PX = 12;
  const BOX_INNER_W = 224 - 16; // #box width minus horizontal padding
  // Where the party stands, front to back (top-left of each 16x24 sprite).
  const PARTY_SLOTS = [[120, 142], [108, 158], [132, 172], [120, 188]];
  const CHAR_MS = 28;
  const PAUSE_MS = { ".": 200, "!": 200, "?": 200, ",": 90, ";": 120, ":": 120 };

  const $ = (id) => document.getElementById(id);
  const stage = $("stage");
  const box = $("box");
  const textEl = $("text");
  const arrow = $("arrow");
  const talk = $("talk");

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let pages = [];
  let pageIdx = 0;
  let typing = null; // {timer, full}
  let closed = false;

  // ---- layout ----

  function fitStage() {
    const availW = Math.max(160, document.documentElement.clientWidth - 32);
    const availH = Math.max(160, window.innerHeight * 0.72);
    let scale = Math.min(availW / STAGE_W, availH / STAGE_H);
    if (scale >= 2) scale = Math.floor(scale); // whole-pixel scaling when there's room
    stage.style.transform = `scale(${scale})`;
    const vp = $("viewport");
    vp.style.width = `${STAGE_W * scale}px`;
    vp.style.height = `${STAGE_H * scale}px`;
  }

  // The pages are pre-wrapped by the build job for a fixed column count. If the font in
  // use runs wider than expected, shrink it until the longest line fits.
  function fitFont() {
    const family = getComputedStyle(textEl).fontFamily;
    const ctx = document.createElement("canvas").getContext("2d");
    ctx.font = `${MAX_FONT_PX}px ${family}`;
    let widest = 0;
    for (const page of pages) {
      for (const line of page.split("\n")) widest = Math.max(widest, ctx.measureText(line).width);
    }
    const size = widest > BOX_INNER_W ? Math.floor((MAX_FONT_PX * BOX_INNER_W * 10) / widest) / 10 : MAX_FONT_PX;
    textEl.style.fontSize = `${size}px`;
  }

  // ---- text box ----

  function showPage(i) {
    pageIdx = i;
    closed = false;
    box.hidden = false;
    talk.hidden = true;
    arrow.classList.remove("on");
    stopTyping();
    const full = pages[i];
    if (reduceMotion) {
      textEl.textContent = full;
      pageDone();
      return;
    }
    let n = 0;
    textEl.textContent = "";
    const step = () => {
      n += 1;
      textEl.textContent = full.slice(0, n);
      if (n >= full.length) {
        typing = null;
        pageDone();
        return;
      }
      const ch = full[n - 1];
      const next = full[n];
      const pause = PAUSE_MS[ch] && (next === " " || next === "\n" || next === "”") ? PAUSE_MS[ch] : 0;
      typing.timer = setTimeout(step, CHAR_MS + pause);
    };
    typing = { full, timer: setTimeout(step, CHAR_MS) };
  }

  function stopTyping() {
    if (typing) clearTimeout(typing.timer);
    typing = null;
  }

  function pageDone() {
    arrow.classList.toggle("on", pageIdx < pages.length - 1);
  }

  function closeBox() {
    stopTyping();
    closed = true;
    box.hidden = true;
    talk.hidden = false;
  }

  function advance() {
    if (!pages.length) return;
    if (closed) return showPage(0);
    if (typing) {
      // First press finishes the page; the next one turns it.
      stopTyping();
      textEl.textContent = pages[pageIdx];
      return pageDone();
    }
    if (pageIdx < pages.length - 1) return showPage(pageIdx + 1);
    closeBox();
  }

  // ---- scene ----

  function sprite(src, x, y) {
    const img = new Image();
    img.className = "sprite";
    img.alt = "";
    img.draggable = false;
    img.src = src;
    img.style.left = `${x}px`;
    img.style.top = `${y}px`;
    return img;
  }

  function renderScene(data) {
    $("room").src = data.room;
    $("npc").src = data.npc;
    const party = $("party");
    party.replaceChildren();
    // Draw back to front so the leader overlaps the followers.
    (data.party || []).slice(0, PARTY_SLOTS.length).map((src, i) => [src, PARTY_SLOTS[i]])
      .reverse()
      .forEach(([src, [x, y]]) => party.appendChild(sprite(src, x, y)));

    const lines = (data.box && data.box.lines) || 4;
    textEl.style.height = `${lines * LINE_H}px`;
  }

  function renderFooter(data) {
    const d = new Date(`${data.date}T00:00:00+09:00`);
    const pretty = d.toLocaleDateString("en-US", { timeZone: "Asia/Tokyo", weekday: "long", year: "numeric", month: "long", day: "numeric" });
    $("dateline").textContent = `${pretty} (JST)${data.title_en ? ` — “${data.title_en}”` : ""}`;
    if (data.source_url) $("source").href = data.source_url;
    const ja = $("text-ja");
    ja.replaceChildren(...(data.text_ja || "").split(/\n\s*\n/).filter(Boolean).map((p) => {
      const el = document.createElement("p");
      el.textContent = p;
      return el;
    }));
    $("original").hidden = !data.text_ja;
  }

  function fail() {
    // No today.json (or a broken one): keep the page useful instead of blank.
    pages = ["• ...Huh? The column seems to be\n  taking a nap.\n• Please come back a little later."];
    textEl.style.height = `${4 * LINE_H}px`;
    $("room").removeAttribute("src");
    $("original").hidden = true;
    showPage(0);
  }

  // ---- input ----

  stage.addEventListener("click", advance);
  document.addEventListener("keydown", (e) => {
    if (e.target.closest && e.target.closest("summary, a, input, textarea")) return;
    if (e.key === " " || e.key === "Enter" || e.key === "z" || e.key === "Z") {
      e.preventDefault();
      advance();
    }
  });

  window.addEventListener("resize", fitStage);
  fitStage();

  fetch("today.json", { cache: "no-cache" })
    .then((r) => {
      if (!r.ok) throw new Error(`today.json: HTTP ${r.status}`);
      return r.json();
    })
    .then(async (data) => {
      if (!Array.isArray(data.pages_en) || !data.pages_en.length) throw new Error("today.json has no pages");
      pages = data.pages_en;
      renderScene(data);
      renderFooter(data);
      await document.fonts.ready;
      fitFont();
      showPage(0);
    })
    .catch((err) => {
      console.error(err);
      fail();
    });
})();
