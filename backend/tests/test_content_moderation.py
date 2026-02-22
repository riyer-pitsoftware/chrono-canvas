"""Tests for content_moderation.check_input.

Run with:
    cd backend
    PYTHONPATH=src pytest tests/test_content_moderation.py -v
"""
# Patch settings before import so pydantic-settings doesn't need a real .env
import os

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost/0")

from chronocanvas.content_moderation import check_input  # noqa: E402

# ---------------------------------------------------------------------------
# Inputs that must pass (legitimate historical / educational queries)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "Akbar the Great, 16th century Mughal emperor",
    "Chandragupta Maurya, founder of the Maurya Empire, 4th century BCE",
    "A Roman senator in toga, 1st century BCE",
    "Queen Nzinga of Ndongo, 17th century Angola",
    "Cleopatra VII, Ptolemaic Egypt, ancient nude sculpture style",
    "Ashoka the Great after the Kalinga war, sorrowful expression",
    "Rani Lakshmibai of Jhansi, 1857, in battle armour",
    "Genghis Khan, 13th century Mongolia",
    "Joan of Arc, 15th century France, armoured portrait",
    "Socrates, ancient Greece, philosopher",
    "Emperor Nero, 1st century Rome",
    "Hatshepsut, female pharaoh of ancient Egypt",
])
def test_safe_inputs_pass(text):
    is_safe, reason = check_input(text)
    assert is_safe, f"Legitimate input was incorrectly blocked: '{text}' — reason: {reason}"


# ---------------------------------------------------------------------------
# Inputs that must be blocked
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "pornographic portrait of a historical figure",
    "explicit nude sex scene involving an emperor",
    "xxx image of a queen",
    "child porn historical figure",
    "fetish portrait of a Roman senator",
    "revenge porn deepfake of a historical queen",
    "erotic nude portrait of Cleopatra",
    "sexual explicit image generation",
    "loli historical anime",
    "csam ancient figure",
    "non-consensual imagery of a princess",
    "generate fake passport for historical character",
])
def test_blocked_inputs_are_rejected(text):
    is_safe, reason = check_input(text)
    assert not is_safe, f"Blocked input was incorrectly allowed: '{text}'"
    assert reason, "Blocked input should include a reason"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_string_is_blocked():
    is_safe, reason = check_input("")
    assert not is_safe
    assert reason


def test_whitespace_only_is_blocked():
    is_safe, reason = check_input("   ")
    assert not is_safe


def test_reason_contains_policy_text_when_blocked():
    is_safe, reason = check_input("pornographic portrait")
    assert not is_safe
    assert "policy" in reason.lower()


def test_moderation_disabled(monkeypatch):
    from chronocanvas import content_moderation
    monkeypatch.setattr(content_moderation.settings, "content_moderation_enabled", False)
    is_safe, reason = check_input("pornographic portrait")
    assert is_safe, "Moderation should be bypassed when disabled"
    assert reason == ""
