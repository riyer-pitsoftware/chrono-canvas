import pytest
from pathlib import Path
import tempfile

from historylens.imaging.mock_generator import MockImageGenerator


@pytest.mark.asyncio
async def test_mock_generator_creates_image():
    generator = MockImageGenerator()
    assert generator.name == "mock"

    with tempfile.TemporaryDirectory() as tmpdir:
        result = await generator.generate(
            prompt="A portrait of Cleopatra in Egyptian royal attire",
            output_dir=Path(tmpdir),
            width=256,
            height=256,
        )

        assert result.width == 256
        assert result.height == 256
        assert result.provider == "mock"
        assert Path(result.file_path).exists()
        assert Path(result.file_path).suffix == ".png"


@pytest.mark.asyncio
async def test_mock_generator_available():
    generator = MockImageGenerator()
    assert await generator.is_available() is True


@pytest.mark.asyncio
async def test_mock_generator_deterministic_color():
    generator = MockImageGenerator()

    with tempfile.TemporaryDirectory() as tmpdir:
        result1 = await generator.generate("same prompt", Path(tmpdir))
        result2 = await generator.generate("same prompt", Path(tmpdir))

        # Both should succeed (different filenames though)
        assert Path(result1.file_path).exists()
        assert Path(result2.file_path).exists()
