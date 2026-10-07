from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import trimesh

from app.config import settings
from app.mesh.prepare import load_mesh, prepare_for_print, preview_payload, rescale_prepared
from app.mesh.threemf import write_3mf
from app.providers.factory import get_provider
from app.store import JobRecord, store


def clamp_size(size_mm: Optional[float]) -> float:
    value = settings.default_size_mm if size_mm is None else float(size_mm)
    return max(settings.min_size_mm, min(settings.max_size_mm, value))


def create_job(image_bytes: bytes, content_type: str, target_size_mm: Optional[float]) -> JobRecord:
    job_id = str(uuid.uuid4())
    provider = get_provider()
    record = JobRecord(
        id=job_id,
        status="queued",
        provider=provider.name,
        target_size_mm=clamp_size(target_size_mm),
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        source_ext="jpg",
    )
    suffix = "png" if "png" in (content_type or "") else "jpg"
    record.source_ext = suffix
    store.save(record)
    store.write_bytes(job_id, f"input.{suffix}", image_bytes)
    store.write_bytes(job_id, "content_type.txt", (content_type or "image/jpeg").encode("utf-8"))
    return record


async def run_job(job_id: str) -> None:
    record = store.get(job_id)
    if record is None:
        return
    image = store.read_bytes(job_id, f"input.{record.source_ext}")
    if image is None:
        store.update(job_id, status="failed", error="Uploaded image is missing")
        return
    content_type = (store.read_bytes(job_id, "content_type.txt") or b"image/jpeg").decode("utf-8")
    provider = get_provider()
    try:
        store.update(job_id, status="generating", provider=provider.name)
        result = await provider.generate(image, content_type)
        store.write_bytes(job_id, f"source.{result.format}", result.data)
        store.update(job_id, status="repairing", y_up_source=result.y_up)

        mesh = load_mesh(result.data, result.format)
        prepared = prepare_for_print(
            mesh,
            target_size_mm=record.target_size_mm,
            y_up=result.y_up,
        )
        _write_artifacts(job_id, prepared.mesh, prepared.target_size_mm)
        extents = prepared.mesh.extents
        store.update(
            job_id,
            status="ready",
            provider=provider.name,
            prepared_size_mm=prepared.target_size_mm,
            warnings=prepared.warnings,
            bbox_mm={"x": float(extents[0]), "y": float(extents[1]), "z": float(extents[2])},
            min_extent_mm=float(extents.min()),
            is_watertight=prepared.is_watertight,
            triangle_count=int(len(prepared.mesh.faces)),
            error=None,
        )
    except Exception as exc:
        store.update(job_id, status="failed", error=str(exc))


def _write_artifacts(job_id: str, mesh: trimesh.Trimesh, size_mm: float) -> None:
    stl = mesh.export(file_type="stl")
    if not isinstance(stl, (bytes, bytearray)):
        stl = bytes(stl)
    store.write_bytes(job_id, "export.stl", stl)
    store.write_bytes(job_id, "export.3mf", write_3mf(mesh, object_name="Drawing"))
    store.write_bytes(
        job_id,
        "preview.mesh.json",
        json.dumps(preview_payload(mesh)).encode("utf-8"),
    )
    glb = trimesh.exchange.gltf.export_glb(mesh)
    store.write_bytes(job_id, "preview.glb", glb)
    store.write_bytes(job_id, "prepared_size.txt", f"{size_mm:.6f}".encode("utf-8"))
    store.write_bytes(job_id, "prepared.stl", stl)


def export_at_size(job_id: str, size_mm: Optional[float], fmt: str) -> bytes:
    record = store.get(job_id)
    if record is None or record.status != "ready":
        raise KeyError(job_id)
    target = clamp_size(size_mm if size_mm is not None else record.target_size_mm)
    ply = store.read_bytes(job_id, "prepared.stl")
    if ply is None:
        raise FileNotFoundError("prepared mesh missing")
    mesh = load_mesh(ply, "stl")
    current = record.prepared_size_mm or float(mesh.extents.max())
    if abs(current - target) > 0.05:
        mesh = rescale_prepared(mesh, target)
        extents = mesh.extents
        store.update(
            job_id,
            target_size_mm=target,
            prepared_size_mm=target,
            bbox_mm={"x": float(extents[0]), "y": float(extents[1]), "z": float(extents[2])},
            min_extent_mm=float(extents.min()),
            triangle_count=int(len(mesh.faces)),
        )
        _write_artifacts(job_id, mesh, target)
    name = {"3mf": "export.3mf", "stl": "export.stl", "glb": "preview.glb", "json": "preview.mesh.json"}[fmt]
    data = store.read_bytes(job_id, name)
    if data is None:
        raise FileNotFoundError(name)
    return data
