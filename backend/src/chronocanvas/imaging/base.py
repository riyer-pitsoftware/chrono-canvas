from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field


class ImageResult(BaseModel):
    file_path: str
    width: int
    height: int
    provider: str
    generation_params: dict = Field(default_factory=dict)


class ImageGenerator(ABC):
    name: str

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        output_dir: Path,
        width: int = 512,
        height: int = 512,
        **kwargs,
    ) -> ImageResult:
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        ...
