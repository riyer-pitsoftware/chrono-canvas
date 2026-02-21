"""Content moderation for generation requests.

Default-on keyword-based input validation. Blocks clearly inappropriate
requests before any expensive processing begins.

Optional LLM-based moderation can be layered on top in future by checking
settings.content_moderation_llm_enabled.
"""
from __future__ import annotations

import re

from chronocanvas.config import settings

# ---------------------------------------------------------------------------
# Blocklist patterns
# ---------------------------------------------------------------------------
# Each entry is a raw regex pattern (case-insensitive, word-boundary matched).
# Aim for high-precision over high-recall — ambiguous historical terms are
# intentionally excluded to avoid blocking legitimate educational queries.

_BLOCKLIST_PATTERNS: list[str] = [
    # Explicit sexual content
    r"\bporn(ography)?\b",
    r"\bpornographic\b",
    r"\bxxx\b",
    r"\bnaked\s+(sexual|erotic)\b",
    r"\bsexual(ly)?\s+(explicit|graphic|act)\b",
    r"\bexplicit\s+(nude|naked|sex)\b",
    r"\berotic\s+(image|portrait|photo|nude)\b",
    r"\bfetish\b",
    r"\bonlyfans\b",
    r"\bsex\s+(scene|video|image|photo|act)\b",
    # Content involving minors
    r"\bchild\s+(porn|sex|nude|naked|erotic)\b",
    r"\bminor\s+(porn|sex|nude|naked|erotic)\b",
    r"\bunderage\s+(nude|naked|sex|erotic|porn)\b",
    r"\bloli\b",
    r"\bshota\b",
    r"\bcsam\b",
    # Non-consensual imagery
    r"\bnon[-\s]?consensual\b",
    r"\brevenge\s+porn\b",
    r"\bdeepfake\s+(porn|nude|sex)\b",
    # Targeted harassment / hate imagery
    r"\bhate\s+(image|portrait|propaganda)\b",
    r"\bracist\s+(caricature|propaganda|image)\b",
    # Requests clearly outside historical/educational purpose
    r"\bgenerate\s+(fake\s+id|fake\s+passport|forged\s+document)\b",
]

_COMPILED: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in _BLOCKLIST_PATTERNS
]

POLICY_SUMMARY = (
    "This tool is for historical and educational portrait generation only. "
    "Requests must relate to real historical figures from the public record. "
    "Explicit, sexual, or non-consensual content is not permitted."
)


def _find_violation(text: str) -> str | None:
    """Return the first matching pattern description, or None if clean."""
    for pattern in _COMPILED:
        if pattern.search(text):
            return pattern.pattern
    return None


def check_input(text: str) -> tuple[bool, str]:
    """Check ``text`` for policy violations.

    Returns ``(is_safe, reason)``.  ``is_safe=True`` means the input passed.
    When ``is_safe=False``, ``reason`` is a human-readable explanation.
    """
    if not settings.content_moderation_enabled:
        return True, ""

    if not text or not text.strip():
        return False, "Input text is empty."

    violation = _find_violation(text)
    if violation:
        return False, (
            "Your request was blocked by the content policy. "
            + POLICY_SUMMARY
        )

    return True, ""
