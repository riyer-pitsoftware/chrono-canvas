#!/usr/bin/env python3
"""Verify all model imports and basic schema sanity without requiring env/config.

Usage:
    python scripts/verify_imports.py
    # or from backend/:
    python -m scripts.verify_imports

Exit 0 = all checks pass, Exit 1 = failure with details.
"""
import sys
import traceback

CHECKS: list[tuple[str, callable]] = []


def check(name: str):
    def decorator(fn):
        CHECKS.append((name, fn))
        return fn
    return decorator


# ── Agent state ──────────────────────────────────────────────────────────

@check("AgentState imports")
def _():
    from chronocanvas.agents.state import (
        AgentState, ExtractionState, ResearchState, PromptState,
        ImageState, ValidationState, FaceState, CompositingState, ExportState,
    )
    # ResearchState uses citations (not research_sources)
    rs = ResearchState(
        historical_context="test",
        citations=[{"title": "Wikipedia", "confidence": 0.8}],
        research_cache_hit=False,
    )
    assert "citations" in rs, "ResearchState missing 'citations' field"
    assert isinstance(rs["citations"], list)


# ── Citation schema ──────────────────────────────────────────────────────

@check("Citation Pydantic model")
def _():
    from chronocanvas.api.schemas.generation import Citation

    c = Citation(title="Wikipedia", url="https://en.wikipedia.org", confidence=0.9)
    d = c.model_dump()
    assert d["title"] == "Wikipedia"
    assert d["confidence"] == 0.9
    assert "publisher" in d  # optional fields present

    # Minimal citation (title only)
    c2 = Citation(title="Britannica")
    assert c2.url is None


# ── State projector ──────────────────────────────────────────────────────

@check("State projector includes citations")
def _():
    from chronocanvas.services.state_projector import RequestStateProjector

    proj = RequestStateProjector()
    result = proj.project(
        {
            "research": {
                "historical_context": "A leader",
                "clothing_details": "Robes",
                "physical_description": "Tall",
                "art_style_reference": "Oil painting",
                "citations": [{"title": "Source A"}],
            },
            "agent_trace": [],
            "llm_calls": [],
        },
        "research",
    )
    rd = result["research_data"]
    assert "citations" in rd, "State projector not persisting citations to DB"
    assert rd["citations"] == [{"title": "Source A"}]
    assert "art_style_reference" in rd, "State projector not persisting art_style_reference"


# ── Neo models ───────────────────────────────────────────────────────────

@check("Neo SQLAlchemy models")
def _():
    from chronocanvas.db.models import (
        NeoStory, NeoCharacter, NeoScene, NeoImage, NeoFaceSwap,
    )
    # Verify table names
    assert NeoStory.__tablename__ == "neo_stories"
    assert NeoCharacter.__tablename__ == "neo_characters"
    assert NeoScene.__tablename__ == "neo_scenes"
    assert NeoImage.__tablename__ == "neo_images"
    assert NeoFaceSwap.__tablename__ == "neo_face_swaps"

    # Verify unique constraints exist
    char_constraints = [c.name for c in NeoCharacter.__table__.constraints if hasattr(c, "name")]
    assert "uq_neo_characters_story_slug" in char_constraints

    scene_constraints = [c.name for c in NeoScene.__table__.constraints if hasattr(c, "name")]
    assert "uq_neo_scenes_character_key" in scene_constraints


# ── Alembic migration file ───────────────────────────────────────────────

@check("Alembic 009 migration exists")
def _():
    from pathlib import Path
    migration = Path(__file__).resolve().parent.parent / "backend/alembic/versions/009_neo_models.py"
    assert migration.exists(), f"Migration not found at {migration}"
    content = migration.read_text()
    assert "neo_stories" in content
    assert "neo_characters" in content
    assert "neo_scenes" in content
    assert "neo_images" in content
    assert "neo_face_swaps" in content
    assert 'down_revision: Union[str, None] = "008"' in content


# ── API schemas ──────────────────────────────────────────────────────────

@check("GenerationResponse schema")
def _():
    from chronocanvas.api.schemas.generation import GenerationResponse, Citation
    fields = GenerationResponse.model_fields
    assert "research_data" in fields


# ── CI config ────────────────────────────────────────────────────────────

@check("CI enforces formatting")
def _():
    from pathlib import Path
    ci = Path(__file__).resolve().parent.parent / ".github/workflows/ci.yml"
    content = ci.read_text()
    assert "ruff format --check" in content, "CI missing ruff format check"
    assert "prettier --check" in content, "CI missing prettier check"


@check("Prettier config exists")
def _():
    from pathlib import Path
    prettierrc = Path(__file__).resolve().parent.parent / "frontend/.prettierrc"
    assert prettierrc.exists(), ".prettierrc not found"


# ── Runner ───────────────────────────────────────────────────────────────

def main() -> int:
    passed = 0
    failed = 0
    for name, fn in CHECKS:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {name}: {e}")
            traceback.print_exc(limit=2)
            failed += 1

    print(f"\n{'='*50}")
    print(f"  {passed} passed, {failed} failed, {passed + failed} total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
