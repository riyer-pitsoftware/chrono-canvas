import json
import tempfile
from pathlib import Path

import pytest

from historylens.agents.nodes.export import export_node


@pytest.mark.asyncio
async def test_export_copies_swapped_image(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr("historylens.agents.nodes.export.settings.output_dir", tmpdir)

        # Create fake images
        gen_image = Path(tmpdir) / "generated.png"
        gen_image.write_bytes(b"original image bytes")
        swapped_image = Path(tmpdir) / "swapped.png"
        swapped_image.write_bytes(b"swapped image bytes")
        original_copy = Path(tmpdir) / "original_generated.png"
        original_copy.write_bytes(b"original image bytes copy")

        state = {
            "request_id": "test-export-1",
            "figure_name": "Caesar",
            "time_period": "1st century BC",
            "region": "Rome",
            "occupation": "Dictator",
            "historical_context": "Roman leader",
            "image_prompt": "A portrait of Caesar",
            "validation_score": 85.0,
            "image_provider": "comfyui",
            "image_path": str(gen_image),
            "swapped_image_path": str(swapped_image),
            "original_image_path": str(original_copy),
            "agent_trace": [],
        }

        result = await export_node(state)

        export_dir = Path(result["export_path"])
        assert export_dir.exists()

        # Original image was copied
        assert (export_dir / "generated.png").exists()

        # Swapped image was copied
        assert (export_dir / "swapped.png").exists()

        # Metadata includes both paths
        metadata = json.loads((export_dir / "metadata.json").read_text())
        assert metadata["swapped_image_path"] != ""
        assert metadata["original_image_path"] == str(original_copy)


@pytest.mark.asyncio
async def test_export_without_face_swap(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr("historylens.agents.nodes.export.settings.output_dir", tmpdir)

        gen_image = Path(tmpdir) / "generated.png"
        gen_image.write_bytes(b"original image bytes")

        state = {
            "request_id": "test-export-2",
            "figure_name": "Napoleon",
            "time_period": "19th century",
            "region": "France",
            "occupation": "Emperor",
            "historical_context": "French leader",
            "image_prompt": "A portrait of Napoleon",
            "validation_score": 90.0,
            "image_provider": "mock",
            "image_path": str(gen_image),
            "agent_trace": [],
        }

        result = await export_node(state)

        export_dir = Path(result["export_path"])
        metadata = json.loads((export_dir / "metadata.json").read_text())

        # Swapped path should be empty when no face swap
        assert metadata["swapped_image_path"] == ""
        assert metadata["original_image_path"] == ""
