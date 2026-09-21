"""JA -> EN translation, behind one swappable function.

Pick the engine with the TRANSLATOR env var ("claude" by default). To add an engine,
write a function `(title_ja, body_ja) -> Translation` and register it in ENGINES.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

log = logging.getLogger(__name__)


class TranslationError(Exception):
    pass


@dataclass
class Translation:
    title: str
    paragraphs: list[str]
    engine: str


SYSTEM_PROMPT = """\
You translate Shigesato Itoi's daily column 今日のダーリン ("Today's Darling") from \
Japanese into English for a small, non-commercial fan site.

Itoi writes like he talks: warm, casual, meandering, lots of run-on sentences, \
little asides, gentle self-deprecation, and "boku" (ぼく) as a soft, boyish "I". \
Keep that voice. Prefer a natural, relaxed English sentence over a literal one, \
but don't add ideas, jokes, or explanations that aren't in the original. Keep \
his run-on rhythm rather than chopping everything into short sentences.

Details:
- The first line you receive is the column's title; the rest is the body.
- Keep the paragraph structure: one English paragraph per Japanese paragraph.
- Paragraphs starting with ・ are Itoi's normal bullet; drop the ・ itself.
- Keep proper nouns recognisable (e.g. "Hobonichi" for ほぼ日). Translate the \
text inside 「」 and use ordinary double quotes.
- Render ‥‥ as an ellipsis.
- (中略) marks an omission in the mobile edition; render it as "(...)".

Output format, nothing else:
Line 1: the English title.
Then a blank line, then the body paragraphs separated by single blank lines.
No preamble, no notes, no markdown."""

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")


def _translate_claude(title_ja: str, body_ja: str) -> Translation:
    import anthropic

    client = anthropic.Anthropic()  # credentials from ANTHROPIC_API_KEY
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            output_config={"effort": "medium"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"{title_ja}\n\n{body_ja}"}],
        )
    except TypeError as e:
        # The SDK raises a bare TypeError when it finds no credentials at all.
        if "authentication" not in str(e):
            raise
        raise TranslationError(
            "no Anthropic credentials: set ANTHROPIC_API_KEY (exported, or in the env file "
            "passed to `uv run --env-file`, or /etc/todays-darling.env when run via cron)"
        ) from e
    except anthropic.AuthenticationError as e:
        raise TranslationError(f"Anthropic rejected the API key: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise TranslationError(f"could not reach the Claude API: {e}") from e
    except anthropic.RateLimitError as e:
        raise TranslationError(f"rate limited: {e}") from e
    except anthropic.APIStatusError as e:
        raise TranslationError(f"Claude API error {e.status_code}: {e.message}") from e

    if resp.stop_reason == "refusal":
        raise TranslationError(f"translation declined: {resp.stop_details}")
    if resp.stop_reason == "max_tokens":
        raise TranslationError("translation truncated (max_tokens)")

    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    log.info(
        "translated with %s (in=%s out=%s tokens)",
        resp.model, resp.usage.input_tokens, resp.usage.output_tokens,
    )
    return _split(text, engine=f"claude:{resp.model}")


def _translate_passthrough(title_ja: str, body_ja: str) -> Translation:
    """No-op engine for testing the pipeline offline: returns the Japanese untouched."""
    return Translation(title=title_ja, paragraphs=body_ja.split("\n\n"), engine="passthrough")


def _split(text: str, engine: str) -> Translation:
    blocks = [" ".join(b.split()) for b in text.replace("\r", "").split("\n\n")]
    blocks = [b for b in blocks if b]
    if len(blocks) < 2:
        raise TranslationError(f"unexpected translation shape ({len(blocks)} block(s))")
    return Translation(title=blocks[0], paragraphs=blocks[1:], engine=engine)


ENGINES = {
    "claude": _translate_claude,
    "passthrough": _translate_passthrough,
}


def translate(title_ja: str, body_ja: str) -> Translation:
    name = os.environ.get("TRANSLATOR", "claude")
    if name not in ENGINES:
        raise TranslationError(f"unknown TRANSLATOR {name!r}; choose from {sorted(ENGINES)}")
    return ENGINES[name](title_ja, body_ja)
