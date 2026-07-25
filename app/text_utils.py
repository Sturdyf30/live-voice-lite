from __future__ import annotations

import html
import re

_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
_URL_RE = re.compile(r"https?://\S+")
_MARKDOWN_RE = re.compile(r"(^|\s)[#>*_~-]+(?=\S)")
_WHITESPACE_RE = re.compile(r"\s+")


def text_for_speech(text: str, max_chars: int) -> str:
    """Make an assistant response pleasant for TTS without altering the UI transcript."""

    cleaned = html.unescape(text)
    cleaned = _CODE_BLOCK_RE.sub(" I put the code in the transcript. ", cleaned)
    cleaned = _LINK_RE.sub(r"\1", cleaned)
    cleaned = _INLINE_CODE_RE.sub(r"\1", cleaned)
    cleaned = _URL_RE.sub("link", cleaned)
    cleaned = _MARKDOWN_RE.sub(r"\1", cleaned)
    cleaned = cleaned.replace("•", ". ").replace("→", " to ")
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()

    if len(cleaned) <= max_chars:
        return cleaned

    clipped = cleaned[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:")
    return f"{clipped}. The rest is in the transcript."
