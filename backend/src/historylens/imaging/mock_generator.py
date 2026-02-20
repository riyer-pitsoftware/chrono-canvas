import hashlib
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from historylens.imaging.base import ImageGenerator, ImageResult


class MockImageGenerator(ImageGenerator):
    name = "mock"

    async def generate(
        self,
        prompt: str,
        output_dir: Path,
        width: int = 512,
        height: int = 512,
        **kwargs,
    ) -> ImageResult:
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create a deterministic color from the prompt
        color_hash = hashlib.md5(prompt.encode()).hexdigest()
        bg_color = (
            int(color_hash[:2], 16),
            int(color_hash[2:4], 16),
            int(color_hash[4:6], 16),
        )

        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        # Draw a simple portrait placeholder
        cx, cy = width // 2, height // 2

        # Head (oval)
        head_w, head_h = width // 4, height // 3
        draw.ellipse(
            [cx - head_w, cy - head_h - 20, cx + head_w, cy + head_h // 2 - 20],
            fill=(240, 210, 180),
            outline=(100, 80, 60),
            width=2,
        )

        # Body (trapezoid)
        draw.polygon(
            [
                (cx - head_w - 20, height),
                (cx + head_w + 20, height),
                (cx + head_w, cy + head_h // 2),
                (cx - head_w, cy + head_h // 2),
            ],
            fill=(bg_color[0] // 2, bg_color[1] // 2, bg_color[2] // 2),
        )

        # Add prompt text at bottom
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

        short_prompt = prompt[:60] + "..." if len(prompt) > 60 else prompt
        draw.text((10, height - 30), f"[MOCK] {short_prompt}", fill="white", font=font)
        draw.text((10, 10), "HistoryLens Mock", fill="white", font=font)

        filename = f"{uuid.uuid4().hex}.png"
        filepath = output_dir / filename
        img.save(filepath, "PNG")

        return ImageResult(
            file_path=str(filepath),
            width=width,
            height=height,
            provider=self.name,
            generation_params={"prompt": prompt},
        )

    async def is_available(self) -> bool:
        return True
