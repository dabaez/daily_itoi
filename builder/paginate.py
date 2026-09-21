"""Split the English text into EarthBound text-box pages.

Each paragraph starts on a fresh page with a bullet, and wrapped lines are indented
under it, the way EarthBound's dialogue boxes do it. Pages are newline-joined lines.
"""

from __future__ import annotations

import textwrap

BULLET = "• "  # "• "
COLS = 32  # characters per line
LINES = 4  # lines per text box


def wrap_paragraph(text: str, cols: int = COLS) -> list[str]:
    return textwrap.wrap(
        text,
        width=cols,
        initial_indent=BULLET,
        subsequent_indent=" " * len(BULLET),
        break_long_words=True,
        break_on_hyphens=True,
    )


def paginate(paragraphs: list[str], cols: int = COLS, lines: int = LINES) -> list[str]:
    pages = []
    for para in paragraphs:
        wrapped = wrap_paragraph(para, cols)
        for i in range(0, len(wrapped), lines):
            pages.append("\n".join(wrapped[i : i + lines]))
    return pages
