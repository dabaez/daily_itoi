// Renders today.json. No randomness and no scraping here: the daily job decides
// everything, so every visitor sees the same scene.
(() => {
  "use strict";

  const STAGE_W = 256;
  const STAGE_H = 224;
  const LINE_H = 13;
  const FONT_PX = 12;
  const BOX_INNER_W = 224 - 16; // #box width minus horizontal padding
  // Like EarthBound: the box shows three lines, and each part (bullet to prompt)
  // fits in it, so the whole part is on screen when the arrow blinks.
  const VISIBLE_LINES = 3;
  const BULLET = "• ";
  // For today.json files from before the builder placed everyone: the NPC's feet, and
  // the party's (top-left of each 16x24 sprite), front to back.
  const OLD_SPOT = [128, 136];
  const OLD_PARTY_SLOTS = [[120, 142], [108, 158], [132, 172], [120, 188]];
  const CHAR_MS = 28;
  const SCROLL_MS = 80;
  const PAUSE_MS = { ".": 200, "!": 200, "?": 200, ",": 90, ";": 120, ":": 120 };

  // Parts end after a sentence where possible, else after a clause, else after any word.
  const CLOSERS = "”’\"')）」』";
  const SENTENCE_END = new RegExp(`[.!?‥…][${CLOSERS}]*$`);
  const CLAUSE_END = new RegExp(`[,;:、—–][${CLOSERS}]*$`);

  const $ = (id) => document.getElementById(id);
  const stage = $("stage");
  const box = $("box");
  const strip = $("strip");
  const arrow = $("arrow");
  const talk = $("talk");
  const sr = $("sr");

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let parts = []; // each part is its wrapped lines; the first one carries the bullet
  let indent = 0; // px width of the bullet, so wrapped lines line up under the text
  let partIdx = 0;
  let lineCount = 0; // lines written into the strip so far
  let typing = null; // {timer}
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

  // The stage is a fixed 256x224 canvas that only gets scaled, so wrapping depends on the
  // font alone, never on the screen. Load whichever font will be used before measuring.
  async function loadFonts(text) {
    const families = getComputedStyle(box).fontFamily.split(",")
      .map((f) => f.trim().replace(/^["']|["']$/g, ""))
      .filter((f) => !/^(ui-)?(monospace|sans-serif|serif)$/.test(f));
    await Promise.allSettled(families.map((f) => document.fonts.load(`${FONT_PX}px "${f}"`, text)));
  }

  function measurer() {
    const ctx = document.createElement("canvas").getContext("2d");
    ctx.font = `${FONT_PX}px ${getComputedStyle(box).fontFamily}`;
    const cache = new Map();
    return (s) => {
      if (!cache.has(s)) cache.set(s, ctx.measureText(s).width);
      return cache.get(s);
    };
  }

  // Break points: after spaces (the space is dropped) and after dashes (nothing dropped).
  function tokenize(text) {
    const tokens = [];
    for (const word of text.split(" ").filter(Boolean)) {
      word.replace(/([—–-])(?=.)/g, "$1\u0000").split("\u0000")
        .forEach((t, i) => tokens.push({ text: t, space: i === 0 && tokens.length > 0 }));
    }
    return tokens;
  }

  function wrap(tokens, width, measure) {
    const lines = [];
    let line = "";
    for (const tok of tokens) {
      const joined = line ? line + (tok.space ? " " : "") + tok.text : tok.text;
      if (!line || measure(joined) <= width) {
        line = joined;
      } else {
        lines.push(line);
        line = tok.text;
      }
    }
    if (line) lines.push(line);
    return lines;
  }

  // A word too wide for a whole line gets cut into pieces that fit.
  function splitLongTokens(tokens, width, measure) {
    return tokens.flatMap((tok) => {
      if (measure(tok.text) <= width) return [tok];
      const pieces = [];
      let cur = "";
      for (const ch of tok.text) {
        if (cur && measure(cur + ch) > width) {
          pieces.push(cur);
          cur = "";
        }
        cur += ch;
      }
      pieces.push(cur);
      return pieces.map((text, i) => ({ text, space: i === 0 && tok.space }));
    });
  }

  // Cuts a sentence too long for one part into parts that fit. Cuts after a clause beat
  // cuts between words, which beat cuts inside a quotation; an extra part is cheaper than
  // a bad cut; and parts of even length win ties, so no part is left holding two words.
  function cutSentence(tokens, width, measure) {
    const n = tokens.length;
    const quoted = []; // quoted[k]: is the text right after tokens[k] inside quotes?
    let curly = 0;
    let straight = false;
    for (const tok of tokens) {
      for (const ch of tok.text) {
        if (ch === "“") curly += 1;
        else if (ch === "”") curly = Math.max(0, curly - 1);
        else if (ch === "\"") straight = !straight;
      }
      quoted.push(curly > 0 || straight);
    }
    const best = new Array(n + 1).fill(null); // best[i]: cheapest way to lay out tokens[i..]
    best[n] = { cost: 0, next: n };
    for (let i = n - 1; i >= 0; i -= 1) {
      for (let j = i + 1; j <= n; j += 1) {
        const lines = wrap(tokens.slice(i, j), width, measure);
        if (lines.length > VISIBLE_LINES) break; // only gets longer from here
        const size = lines.length - 1 + measure(lines[lines.length - 1]) / width;
        let cost = 12 + size * size + best[j].cost;
        if (j < n && !CLAUSE_END.test(tokens[j - 1].text)) cost += 20;
        if (j < n && quoted[j - 1]) cost += 15;
        if (!best[i] || cost < best[i].cost) best[i] = { cost, next: j };
      }
    }
    const out = [];
    for (let i = 0; i < n; i = best[i].next) out.push(tokens.slice(i, best[i].next));
    return out;
  }

  // Splits one paragraph into parts of at most VISIBLE_LINES lines. Short sentences
  // share a part while they fit; a long one starts its own and is cut up as needed.
  function splitParagraph(text, width, measure) {
    const tokens = splitLongTokens(tokenize(text), width, measure);
    const sentences = [];
    let sentence = [];
    for (const tok of tokens) {
      sentence.push(tok);
      if (SENTENCE_END.test(tok.text)) {
        sentences.push(sentence);
        sentence = [];
      }
    }
    if (sentence.length) sentences.push(sentence);

    const fits = (toks) => wrap(toks, width, measure).length <= VISIBLE_LINES;
    const out = [];
    let part = [];
    for (const s of sentences) {
      if (fits([...part, ...s])) {
        part.push(...s);
        continue;
      }
      if (part.length) out.push(part);
      const pieces = fits(s) ? [s] : cutSentence(s, width, measure);
      out.push(...pieces.slice(0, -1));
      part = pieces[pieces.length - 1];
    }
    if (part.length) out.push(part);
    // Each part starts at the left edge, so drop the space that led into it.
    return out.map((p) => wrap([{ ...p[0], space: false }, ...p.slice(1)], width, measure));
  }

  function layout(paras) {
    const measure = measurer();
    indent = measure(BULLET);
    const width = BOX_INNER_W - indent - 1; // 1px of slack for canvas vs. DOM rounding
    return paras.flatMap((p) => splitParagraph(p, width, measure))
      .map(([first, ...rest]) => [BULLET + first, ...rest]);
  }

  // ---- text box ----

  function scrollTo(line, animate) {
    strip.style.transition = animate && !reduceMotion ? `transform ${SCROLL_MS}ms linear` : "none";
    strip.style.transform = `translateY(${-line * LINE_H}px)`;
  }

  // Adds an empty line under the last one. Returns true if the text had to scroll up.
  function newLine(isFirst, animate) {
    const el = document.createElement("div");
    el.className = "line";
    if (!isFirst) el.style.paddingLeft = `${indent}px`;
    strip.appendChild(el);
    lineCount += 1;
    if (lineCount <= VISIBLE_LINES) return false;
    scrollTo(lineCount - VISIBLE_LINES, animate);
    return true;
  }

  function resetBox() {
    stopTyping();
    strip.replaceChildren();
    lineCount = 0;
    scrollTo(0, false);
  }

  function showPart(i) {
    partIdx = i;
    closed = false;
    box.hidden = false;
    talk.hidden = true;
    arrow.classList.remove("on");
    stopTyping();
    const lines = parts[i];
    sr.textContent = lines.join(" ").slice(BULLET.length);
    if (reduceMotion) return finishPart();

    let li = 0;
    let el = null;
    let n = 0;
    const later = (ms) => {
      typing.timer = setTimeout(step, ms);
    };
    const step = () => {
      if (!el) {
        if (li >= lines.length) {
          typing = null;
          return partDone();
        }
        const scrolled = newLine(li === 0, true);
        el = strip.lastChild;
        n = 0;
        if (scrolled) return later(SCROLL_MS); // let the text scroll up before writing
      }
      const full = lines[li];
      n += 1;
      el.textContent = full.slice(0, n);
      const ch = full[n - 1];
      const next = full[n];
      const pause = PAUSE_MS[ch] && (next === undefined || next === " " || next === "”") ? PAUSE_MS[ch] : 0;
      if (n >= full.length) {
        el = null;
        li += 1;
      }
      later(CHAR_MS + pause);
    };
    typing = { lineStart: lineCount, timer: 0 };
    later(CHAR_MS);
  }

  // Writes out the rest of the current part at once.
  function finishPart() {
    const start = typing ? typing.lineStart : lineCount;
    stopTyping();
    const lines = parts[partIdx];
    // Drop whatever was half-typed and write the part out whole.
    while (lineCount > start) {
      strip.lastChild.remove();
      lineCount -= 1;
    }
    lines.forEach((line, i) => {
      newLine(i === 0, false);
      strip.lastChild.textContent = line;
    });
    scrollTo(Math.max(0, lineCount - VISIBLE_LINES), false);
    partDone();
  }

  function stopTyping() {
    if (typing) clearTimeout(typing.timer);
    typing = null;
  }

  function partDone() {
    arrow.classList.toggle("on", partIdx < parts.length - 1);
  }

  function closeBox() {
    stopTyping();
    closed = true;
    box.hidden = true;
    talk.hidden = false;
  }

  function advance() {
    if (!parts.length) return;
    if (closed) {
      resetBox();
      return showPart(0);
    }
    if (typing) return finishPart(); // first press finishes the part; the next one moves on
    if (partIdx < parts.length - 1) return showPart(partIdx + 1);
    closeBox();
  }

  async function start(paras) {
    const paragraphs = paras.map((p) => p.replace(/\s+/g, " ").trim()).filter(Boolean);
    await loadFonts(BULLET + paragraphs.join(" "));
    parts = layout(paragraphs);
    resetBox();
    showPart(0);
  }

  // ---- scene ----

  // Sprites stand on (x, y): it's the middle of their bottom edge (see .sprite).
  function stand(img, x, y) {
    img.style.left = `${x}px`;
    img.style.top = `${y}px`;
  }

  function sprite(src, x, y) {
    const img = new Image();
    img.className = "sprite";
    img.alt = "";
    img.draggable = false;
    img.src = src;
    stand(img, x, y);
    return img;
  }

  function renderScene(data) {
    $("room").src = data.room;
    $("npc").src = data.npc;
    stand($("npc"), ...(data.spot || OLD_SPOT));
    const members = (data.party || []).map((m, i) => typeof m === "string"
      ? { src: m, x: OLD_PARTY_SLOTS[i][0] + 8, y: OLD_PARTY_SLOTS[i][1] + 24 }
      : m);
    // Whoever is lower on screen is nearer the camera, so draw top to bottom.
    const party = $("party");
    party.replaceChildren(...members
      .filter((m) => m.x !== undefined)
      .sort((a, b) => a.y - b.y)
      .map((m) => {
        const img = sprite(m.src, m.x, m.y);
        if (m.state) img.dataset.state = m.state;
        return img;
      }));
  }

  function renderHeading(data) {
    const d = new Date(`${data.date}T00:00:00+09:00`);
    const pretty = d.toLocaleDateString("en-US", { timeZone: "Asia/Tokyo", weekday: "long", year: "numeric", month: "long", day: "numeric" });
    $("dateline").textContent = `Today's Darling · ${pretty}`;
    $("title").textContent = data.title_en ? `“${data.title_en}”` : "";
    $("title").hidden = !data.title_en;
    if (data.source_url) $("source").href = data.source_url;
  }

  // The same paragraphs as the dialogue, for reading straight through.
  function renderPlain(paras) {
    $("text-en").replaceChildren(...paras.map((p) => {
      const el = document.createElement("p");
      el.textContent = p;
      return el;
    }));
    $("plain").hidden = false;
  }

  // today.json files written before paragraphs_en existed carry pre-wrapped pages instead,
  // led by a "Today's Darling, <date>. “<title>”" header that the page now shows itself.
  function paragraphsFromPages(pages) {
    const paras = [];
    for (const line of pages.join("\n").split("\n")) {
      const text = line.trim();
      if (line.startsWith(BULLET) || !paras.length) {
        paras.push(line.startsWith(BULLET) ? line.slice(BULLET.length).trim() : text);
      } else if (text) {
        const last = paras.length - 1;
        paras[last] += (/\w-$/.test(paras[last]) ? "" : " ") + text;
      }
    }
    if (/^Today's Darling, /.test(paras[0] || "")) paras.shift();
    return paras.map((p) => p.replace(/^[◆◇]\s*/, ""));
  }

  function fail() {
    // No today.json (or a broken one): keep the page useful instead of blank.
    $("room").removeAttribute("src");
    start(["...Huh? The column seems to be taking a nap.", "Please come back a little later."]);
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
    .then((data) => {
      const paras = Array.isArray(data.paragraphs_en) ? data.paragraphs_en
        : Array.isArray(data.pages_en) ? paragraphsFromPages(data.pages_en) : [];
      if (!paras.length) throw new Error("today.json has no text");
      renderScene(data);
      renderHeading(data);
      renderPlain(paras);
      return start(paras);
    })
    .catch((err) => {
      console.error(err);
      fail();
    });
})();
