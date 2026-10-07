from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import trimesh

from app.config import settings


@dataclass
class PreparedMesh:
    mesh: trimesh.Trimesh
    target_size_mm: float
    is_watertight: bool
    warnings: List[Dict[str, str]]
    used_voxel_fallback: bool


def load_mesh(data: bytes, file_type: str) -> trimesh.Trimesh:
    ext = file_type.lstrip(".").lower()
    loaded = trimesh.load(io.BytesIO(data), file_type=ext, force="mesh")
    if isinstance(loaded, trimesh.Scene):
        geoms = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not geoms:
            raise ValueError("No triangle mesh in provider output")
        loaded = trimesh.util.concatenate(geoms)
    if not isinstance(loaded, trimesh.Trimesh):
        raise ValueError(f"Unsupported mesh type: {type(loaded)!r}")
    return loaded


def _drop_dust(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    if mesh.body_count <= 1:
        return mesh
    parts = mesh.split(only_watertight=False)
    if not parts:
        return mesh

    def volume_of(part: trimesh.Trimesh) -> float:
        if part.is_volume:
            return abs(float(part.volume))
        try:
            return abs(float(part.convex_hull.volume))
        except Exception:
            return float(part.area)

    volumes = [volume_of(p) for p in parts]
    peak = max(volumes) if volumes else 0.0
    if peak <= 0:
        return mesh
    keep = [p for p, v in zip(parts, volumes) if v >= peak * 0.01]
    if not keep:
        keep = [parts[int(np.argmax(volumes))]]
    if len(keep) == 1:
        return keep[0]
    return trimesh.util.concatenate(keep)


def _try_repair(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    mesh = mesh.copy()
    mesh.merge_vertices()
    if hasattr(mesh, "unique_faces"):
        mesh.update_faces(mesh.unique_faces())
    if hasattr(mesh, "nondegenerate_faces"):
        mesh.update_faces(mesh.nondegenerate_faces())
    elif hasattr(mesh, "remove_degenerate_faces"):
        mesh.remove_degenerate_faces()
    mesh.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(mesh)
    trimesh.repair.fill_holes(mesh)
    mesh.process(validate=False)
    return mesh


def _voxel_remesh(mesh: trimesh.Trimesh, cells: int = 64) -> trimesh.Trimesh:
    longest = float(mesh.extents.max()) if mesh.extents.max() > 0 else 1.0
    pitch = longest / float(cells)
    voxel = mesh.voxelized(pitch)
    filled = voxel.fill()
    remeshed = filled.marching_cubes
    if remeshed is None or len(remeshed.faces) == 0:
        raise ValueError("Voxel remesh produced an empty mesh")
    return remeshed


def _cap_faces(mesh: trimesh.Trimesh, max_faces: int) -> trimesh.Trimesh:
    if len(mesh.faces) <= max_faces:
        return mesh
    try:
        simplified = mesh.simplify_quadric_decimation(face_count=max_faces)
        if simplified is not None and len(simplified.faces) > 0:
            return simplified
    except Exception:
        pass
    # Coarser voxel remesh as a last resort to bound triangle count.
    cells = 48 if len(mesh.faces) > max_faces * 2 else 56
    return _voxel_remesh(mesh, cells=cells)


def prepare_for_print(
    mesh: trimesh.Trimesh,
    *,
    target_size_mm: float,
    y_up: bool = False,
) -> PreparedMesh:
    warnings: List[Dict[str, str]] = []
    used_voxel = False

    size = float(np.clip(target_size_mm, settings.min_size_mm, settings.max_size_mm))
    work = mesh.copy()
    work.process(validate=False)
    if y_up:
        # glTF Y-up → printer Z-up
        work.apply_transform(
            trimesh.transformations.rotation_matrix(np.radians(90.0), [1.0, 0.0, 0.0])
        )

    work = _drop_dust(work)
    work = _try_repair(work)

    if not work.is_watertight:
        try:
            work = _voxel_remesh(work)
            used_voxel = True
            work = _try_repair(work)
            warnings.append(
                {
                    "code": "voxel_remesh",
                    "message": "The generated mesh was not watertight; it was remeshed so it can slice.",
                }
            )
        except Exception as exc:
            raise ValueError(f"Could not make the mesh watertight: {exc}") from exc

    if not work.is_watertight:
        raise ValueError("Mesh is still open after repair; refusing export")

    volume = float(work.volume)
    if volume <= 0:
        work.invert()
        volume = float(work.volume)
    if volume <= 0:
        raise ValueError("Mesh has zero or negative volume")

    work = _cap_faces(work, settings.max_export_faces)

    longest = float(work.extents.max())
    if longest <= 0:
        raise ValueError("Mesh has no size")
    work.apply_scale(size / longest)

    bounds = work.bounds
    translation = [
        -(bounds[0][0] + bounds[1][0]) / 2.0,
        -(bounds[0][1] + bounds[1][1]) / 2.0,
        -bounds[0][2],
    ]
    work.apply_translation(translation)

    min_extent = float(work.extents.min())
    if min_extent < settings.thin_feature_mm:
        warnings.append(
            {
                "code": "thin_features",
                "message": (
                    f"Shortest bounding edge is {min_extent:.1f} mm. On a 0.4 mm P2S nozzle, "
                    "features under about 0.8–1.2 mm may not print. Scale up if you can."
                ),
            }
        )

    return PreparedMesh(
        mesh=work,
        target_size_mm=size,
        is_watertight=bool(work.is_watertight),
        warnings=warnings,
        used_voxel_fallback=used_voxel,
    )


def rescale_prepared(mesh: trimesh.Trimesh, target_size_mm: float) -> trimesh.Trimesh:
    """Scale an already-ground mesh so the longest edge matches target_size_mm."""
    size = float(np.clip(target_size_mm, settings.min_size_mm, settings.max_size_mm))
    work = mesh.copy()
    longest = float(work.extents.max())
    if longest <= 0:
        return work
    work.apply_scale(size / longest)
    bounds = work.bounds
    work.apply_translation(
        [
            -(bounds[0][0] + bounds[1][0]) / 2.0,
            -(bounds[0][1] + bounds[1][1]) / 2.0,
            -bounds[0][2],
        ]
    )
    return work


def preview_payload(mesh: trimesh.Trimesh, max_faces: Optional[int] = None) -> Dict[str, Any]:
    cap = max_faces or settings.max_preview_faces
    preview = mesh
    if len(mesh.faces) > cap:
        try:
            preview = mesh.simplify_quadric_decimation(face_count=cap)
        except Exception:
            preview = mesh
    vertices = np.asarray(preview.vertices, dtype=float).tolist()
    faces = np.asarray(preview.faces, dtype=int).tolist()
    return {
        "units": "millimeter",
        "vertices": vertices,
        "faces": faces,
    }
