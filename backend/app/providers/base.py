from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class MeshBytes:
    """Raw mesh returned by an image-to-3D provider."""

    data: bytes
    format: str  # glb | stl | obj
    y_up: bool = True
    provider: str = "unknown"


class Provider(Protocol):
    name: str

    async def generate(self, image_bytes: bytes, content_type: str) -> MeshBytes:
        """Turn a drawing bitmap into a 3D mesh of the depicted object."""
