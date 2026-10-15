"""Web app: type a name, preview the puzzle, download a P2S 3MF."""

from __future__ import annotations

import logging
import re
import shutil
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from puzzle import PuzzleError, cadquery_hint, cadquery_ready, generate, sanitize_name

ROOT = Path(__file__).resolve().parent
JOB_ROOT = Path("/tmp/name-puzzles")
STATIC = ROOT / "static"
FONTS = ROOT / "fonts"
_ID = re.compile(r"[a-f0-9]{12}")

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
_generate_lock = threading.Lock()

app = FastAPI(title="Name puzzle")
app.add_middleware(GZipMiddleware, minimum_size=1000)
log = logging.getLogger("namepuzzle")


class NameIn(BaseModel):
    name: str
    magnets: bool = False


def _public(job: dict) -> dict:
    payload = {
        "id": job["id"],
        "name": job["name"],
        "status": job["status"],
        "message": job["message"],
        "error": job["error"],
    }
    if job.get("summary") is not None:
        payload["summary"] = job["summary"]
    return payload


def _job_dir(job_id: str) -> Path:
    if _ID.fullmatch(job_id) is None:
        raise HTTPException(status_code=404, detail="That puzzle is not here.")
    return JOB_ROOT / job_id


def _forget_old_jobs() -> None:
    if len(_jobs) <= 8:
        return
    finished = [job for job in _jobs.values() if job["status"] != "running"]
    finished.sort(key=lambda job: job["created"])
    for job in finished[: len(_jobs) - 8]:
        _jobs.pop(job["id"], None)
        shutil.rmtree(JOB_ROOT / job["id"], ignore_errors=True)


def _run(job: dict) -> None:
    out = _job_dir(job["id"])

    def progress(message: str) -> None:
        job["message"] = message

    with _generate_lock:
        try:
            job["summary"] = generate(job["name"], out, progress, magnets=bool(job["magnets"]))
            job["status"] = "done"
            job["message"] = "Ready"
        except PuzzleError as exc:
            job["status"] = "error"
            job["error"] = str(exc)
            job["message"] = str(exc)
            log.warning("puzzle %s failed: %s", job["id"], exc)
        except Exception:
            log.exception("puzzle %s failed", job["id"])
            job["status"] = "error"
            job["error"] = "Something went wrong while building that puzzle."
            job["message"] = job["error"]


@app.get("/api/health")
def health() -> dict:
    ready = cadquery_ready()
    payload: dict = {"ok": True, "cadquery": ready}
    if not ready:
        payload["hint"] = cadquery_hint()
    return payload


@app.post("/api/puzzles")
def create_puzzle(body: NameIn) -> dict:
    try:
        name = sanitize_name(body.name)
    except PuzzleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id,
        "name": name,
        "status": "running",
        "message": "Starting",
        "error": None,
        "summary": None,
        "magnets": bool(body.magnets),
        "created": time_now(),
    }
    with _jobs_lock:
        _forget_old_jobs()
        _jobs[job_id] = job
    threading.Thread(target=_run, args=(job,), daemon=True, name=f"puzzle-{job_id}").start()
    return _public(job)


@app.get("/api/puzzles/{job_id}")
def puzzle_status(job_id: str) -> dict:
    _job_dir(job_id)
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="That puzzle is not here.")
    return _public(job)


@app.get("/api/puzzles/{job_id}/model")
def puzzle_model(job_id: str) -> FileResponse:
    path = _job_dir(job_id) / "model.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That preview is not ready.")
    return FileResponse(path, media_type="application/json")


@app.get("/api/puzzles/{job_id}/puzzle.3mf")
def puzzle_file(job_id: str) -> FileResponse:
    directory = _job_dir(job_id)
    path = directory / "puzzle.3mf"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="That file is not ready.")
    summary_path = directory / "summary.json"
    name = "name"
    if summary_path.is_file():
        try:
            import json

            name = json.loads(summary_path.read_text(encoding="utf-8")).get("name") or name
        except (OSError, ValueError):
            name = "name"
    return FileResponse(path, media_type="model/3mf", filename=f"{name}_name_puzzle.3mf")


def time_now() -> float:
    import time

    return time.time()


# Routes above win. These mounts only serve the page, the viewer, and the font.
app.mount("/fonts", StaticFiles(directory=FONTS), name="fonts")
app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
