from __future__ import annotations

from fastapi import BackgroundTasks, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.config import settings
from app.pipeline import clamp_size, create_job, export_at_size, run_job
from app.schemas import JobCreateResponse, JobStatusResponse
from app.store import store

STUDIO_NOTE = (
    "Open the 3MF in Bambu Studio on a computer. Set printer to "
    "Bambu Lab P2S 0.4 nozzle, PLA, 0.20 mm Standard. Bambu Handy cannot slice this file."
)

app = FastAPI(
    title="Drawing to Print",
    version="0.1.0",
    description="Upload a drawing, generate a 3D object mesh, download a printable 3MF.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    provider = "meshy" if (settings.meshy_api_key or "").strip() else "stub"
    return {"status": "ok", "provider": provider}


@app.post("/v1/jobs", response_model=JobCreateResponse, status_code=201)
async def post_job(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(..., description="Cropped JPEG or PNG of one drawing"),
    target_size_mm: float | None = Form(default=None),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
) -> JobCreateResponse:
    del x_device_id  # Prototype: anonymous device id is accepted, not stored as an account.
    content_type = image.content_type or "application/octet-stream"
    if content_type not in {"image/jpeg", "image/jpg", "image/png", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Upload a JPEG or PNG image")
    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty image upload")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Image exceeds 20 MB")
    record = create_job(data, content_type, target_size_mm)
    background_tasks.add_task(run_job, record.id)
    return JobCreateResponse(
        id=record.id,
        status=record.status,  # type: ignore[arg-type]
        provider=record.provider,
        target_size_mm=record.target_size_mm,
    )


@app.get("/v1/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str) -> JobStatusResponse:
    record = store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown job")
    payload = record.to_public()
    payload["studio_note"] = STUDIO_NOTE
    return JobStatusResponse(**payload)


@app.get("/v1/jobs/{job_id}/preview.mesh.json")
def get_preview_json(
    job_id: str,
    size_mm: float | None = Query(default=None),
) -> Response:
    return _export(job_id, size_mm, "json", "application/json", "preview.mesh.json")


@app.get("/v1/jobs/{job_id}/preview.glb")
def get_preview_glb(
    job_id: str,
    size_mm: float | None = Query(default=None),
) -> Response:
    return _export(job_id, size_mm, "glb", "model/gltf-binary", "preview.glb")


@app.get("/v1/jobs/{job_id}/export.3mf")
def get_export_3mf(
    job_id: str,
    size_mm: float | None = Query(default=None),
) -> Response:
    return _export(job_id, size_mm, "3mf", "model/3mf", "drawing.3mf")


@app.get("/v1/jobs/{job_id}/export.stl")
def get_export_stl(
    job_id: str,
    size_mm: float | None = Query(default=None),
) -> Response:
    return _export(job_id, size_mm, "stl", "model/stl", "drawing.stl")


def _export(job_id: str, size_mm: float | None, fmt: str, media: str, filename: str) -> Response:
    record = store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Unknown job")
    if record.status == "failed":
        raise HTTPException(status_code=409, detail=record.error or "Job failed")
    if record.status != "ready":
        raise HTTPException(status_code=409, detail="Job is not ready")
    try:
        data = export_at_size(job_id, size_mm, fmt)
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if size_mm is not None:
        headers["X-Target-Size-MM"] = f"{clamp_size(size_mm):.1f}"
    return Response(content=data, media_type=media, headers=headers)
