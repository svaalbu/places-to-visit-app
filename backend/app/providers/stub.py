from __future__ import annotations

import io

import numpy as np
from PIL import Image
import trimesh

from app.providers.base import MeshBytes


class StubProvider:
    """Deterministic image-to-mesh stand-in when MESHY_API_KEY is unset.

    Produces a watertight 3D object (ellipsoid), not a plaque or heightmap
    extrusion. Aspect comes from the drawing's ink bounds so different
    photos are distinguishable in a demo, while the pipeline stays printable.
    """

    name = "stub"

    async def generate(self, image_bytes: bytes, content_type: str) -> MeshBytes:
        mesh = ellipse_from_drawing(image_bytes)
        glb = trimesh.exchange.gltf.export_glb(mesh)
        return MeshBytes(data=glb, format="glb", y_up=False, provider=self.name)


def ellipse_from_drawing(image_bytes: bytes) -> trimesh.Trimesh:
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("L")
    except Exception:
        return trimesh.creation.icosphere(subdivisions=3, radius=1.0)

    arr = np.asarray(image, dtype=np.float32) / 255.0
    ink = arr < 0.85
    if not ink.any():
        return trimesh.creation.icosphere(subdivisions=3, radius=1.0)

    rows = np.any(ink, axis=1)
    cols = np.any(ink, axis=0)
    y_idx = np.where(rows)[0]
    x_idx = np.where(cols)[0]
    height = max(int(y_idx[-1] - y_idx[0] + 1), 1)
    width = max(int(x_idx[-1] - x_idx[0] + 1), 1)
    aspect = width / height

    rx = 1.0 if aspect >= 1 else max(aspect, 0.35)
    ry = 1.0 if aspect <= 1 else max(1 / aspect, 0.35)
    # Depth is independent of the paper (true 3D object, not an extrusion).
    rz = float(np.clip(np.sqrt(rx * ry), 0.45, 1.0))

    sphere = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
    sphere.apply_scale([rx, ry, rz])
    return sphere
