import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from chronocanvas.imaging.base import ImageGenerator, ImageResult


class MockFaceSwapClient(ImageGenerator):
    """Mock face swap: overlays the source face as a thumbnail on the target image.

    Produces a visually distinct output so the UI shows something changed,
    making the end-to-end flow testable without a real FaceFusion server.
    """

    name = "mock_face_swap"

    async def generate(
        self,
        prompt: str,
        output_dir: Path,
        width: int = 512,
        height: int = 512,
        source_image: str | None = None,
        target_image: str | None = None,
        **kwargs,
    ) -> ImageResult:
        output_dir.mkdir(parents=True, exist_ok=True)

        # Open target (generated portrait) as the base
        if target_image and Path(target_image).exists():
            base = Image.open(target_image).convert("RGB")
        else:
            base = Image.new("RGB", (width, height), (200, 200, 200))

        base = base.resize((width, height))
        result_img = base.copy()
        draw = ImageDraw.Draw(result_img)

        # Overlay source face as a thumbnail in the top-right corner
        if source_image and Path(source_image).exists():
            try:
                face = Image.open(source_image).convert("RGBA")
                thumb_size = width // 4
                face.thumbnail((thumb_size, thumb_size))
                offset = (width - thumb_size - 8, 8)
                result_img.paste(face.convert("RGB"), offset)
                # Draw a border around the face thumbnail
                draw.rectangle(
                    [offset[0] - 2, offset[1] - 2,
                     offset[0] + thumb_size + 2, offset[1] + thumb_size + 2],
                    outline=(255, 200, 0),
                    width=2,
                )
            except Exception:
                pass

        # Label so it's obvious this is a mock swap
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

        draw.rectangle([0, height - 22, width, height], fill=(0, 0, 0, 180))
        draw.text((4, height - 20), "[MOCK FACE SWAP] source face shown top-right", fill="yellow", font=font)

        filename = f"swapped_{uuid.uuid4().hex}.png"
        filepath = output_dir / filename
        result_img.save(filepath, "PNG")

        return ImageResult(
            file_path=str(filepath),
            width=width,
            height=height,
            provider=self.name,
            generation_params={"source": source_image, "target": target_image},
        )

    async def is_available(self) -> bool:
        return True
