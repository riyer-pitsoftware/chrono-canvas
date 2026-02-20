import asyncio
import logging
import random
import uuid
from pathlib import Path

import httpx

from historylens.config import settings
from historylens.imaging.base import ImageGenerator, ImageResult

logger = logging.getLogger(__name__)


def _build_sdxl_workflow(
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    seed: int,
    checkpoint: str,
) -> dict:
    """Build a ComfyUI workflow for SDXL checkpoint-based text-to-image."""
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": checkpoint,
            },
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": ["1", 1],
            },
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["1", 1],
            },
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1,
            },
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": 30,
                "cfg": 7.0,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["5", 0],
                "vae": ["1", 2],
            },
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "historylens",
                "images": ["6", 0],
            },
        },
    }


def _build_flux_workflow(
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    seed: int,
) -> dict:
    """Build a ComfyUI workflow for FLUX.1-dev GGUF text-to-image."""
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": 20,
                "cfg": 3.5,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "4": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {
                "unet_name": "flux1-dev-Q4_K_S.gguf",
            },
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1,
            },
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": ["10", 0],
            },
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["10", 0],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["3", 0],
                "vae": ["9", 0],
            },
        },
        "9": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "ae.safetensors",
            },
        },
        "10": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": "clip_l.safetensors",
                "clip_name2": "t5xxl_fp8_e4m3fn.safetensors",
                "type": "flux",
            },
        },
        "11": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": "historylens",
                "images": ["8", 0],
            },
        },
    }


class ComfyUIClient(ImageGenerator):
    name = "comfyui"

    def __init__(self):
        self.base_url = settings.comfyui_api_url

    async def generate(
        self,
        prompt: str,
        output_dir: Path,
        width: int = 768,
        height: int = 768,
        negative_prompt: str = "",
        seed: int | None = None,
        **kwargs,
    ) -> ImageResult:
        output_dir.mkdir(parents=True, exist_ok=True)

        if seed is None:
            seed = random.randint(0, 2**32 - 1)

        model = settings.comfyui_model
        if model == "sdxl":
            workflow = _build_sdxl_workflow(
                prompt, negative_prompt, width, height, seed,
                settings.comfyui_sdxl_checkpoint,
            )
        else:
            workflow = _build_flux_workflow(
                prompt, negative_prompt, width, height, seed,
            )

        payload = {"prompt": workflow}

        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post(f"{self.base_url}/prompt", json=payload)
            resp.raise_for_status()
            prompt_id = resp.json()["prompt_id"]

            image_data = await self._poll_and_download(client, prompt_id)

        filename = f"{uuid.uuid4().hex}.png"
        filepath = output_dir / filename
        filepath.write_bytes(image_data)

        return ImageResult(
            file_path=str(filepath),
            width=width,
            height=height,
            provider=self.name,
            generation_params={
                "prompt": prompt,
                "width": width,
                "height": height,
                "model": model,
                "seed": seed,
            },
        )

    async def _poll_and_download(
        self, client: httpx.AsyncClient, prompt_id: str
    ) -> bytes:
        """Poll /history until the prompt completes, then download the image."""
        timeout = 600.0
        interval = 1.0
        elapsed = 0.0

        while elapsed < timeout:
            resp = await client.get(f"{self.base_url}/history/{prompt_id}")
            resp.raise_for_status()
            history = resp.json()

            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node_output in outputs.values():
                    images = node_output.get("images", [])
                    if images:
                        img = images[0]
                        return await self._download_image(
                            client,
                            img["filename"],
                            img.get("subfolder", ""),
                            img.get("type", "output"),
                        )

            await asyncio.sleep(interval)
            elapsed += interval

        raise TimeoutError(
            f"ComfyUI prompt {prompt_id} did not complete within {timeout}s"
        )

    async def _download_image(
        self,
        client: httpx.AsyncClient,
        filename: str,
        subfolder: str,
        img_type: str,
    ) -> bytes:
        """Download a generated image from ComfyUI."""
        resp = await client.get(
            f"{self.base_url}/view",
            params={"filename": filename, "subfolder": subfolder, "type": img_type},
        )
        resp.raise_for_status()
        return resp.content

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/system_stats")
                return resp.status_code == 200
        except Exception:
            return False
