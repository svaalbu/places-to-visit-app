from __future__ import annotations

import zipfile
from io import BytesIO
from xml.etree import ElementTree as ET

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import circle_png

client = TestClient(app)
NS = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}


def _wait_ready(job_id: str, attempts: int = 50):
    last = None
    for _ in range(attempts):
        response = client.get(f"/v1/jobs/{job_id}")
        last = response.json()
        if last["status"] in {"ready", "failed"}:
            return last
    return last


def test_health_uses_stub_without_key():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["provider"] == "stub"


def test_create_poll_download_3mf():
    files = {"image": ("circle.png", circle_png(), "image/png")}
    created = client.post("/v1/jobs", files=files, data={"target_size_mm": "80"})
    assert created.status_code == 201, created.text
    job = created.json()
    assert job["status"] == "queued"
    assert job["provider"] == "stub"
    assert job["target_size_mm"] == 80

    ready = _wait_ready(job["id"])
    assert ready is not None
    assert ready["status"] == "ready", ready
    assert ready["is_watertight"] is True
    assert ready["preview_available"] is True
    assert ready["export_3mf_available"] is True
    assert "Bambu Studio" in ready["studio_note"]
    assert "Handy" in ready["studio_note"]
    longest = max(ready["bbox_mm"].values())
    assert abs(longest - 80) < 0.2

    preview = client.get(f"/v1/jobs/{job['id']}/preview.mesh.json")
    assert preview.status_code == 200
    mesh = preview.json()
    assert mesh["units"] == "millimeter"
    assert len(mesh["vertices"]) > 10
    assert len(mesh["faces"]) > 10

    export = client.get(f"/v1/jobs/{job['id']}/export.3mf")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("model/3mf")
    with zipfile.ZipFile(BytesIO(export.content)) as zf:
        xml = zf.read("3D/3dmodel.model")
    root = ET.fromstring(xml)
    assert root.attrib.get("unit") == "millimeter"

    stl = client.get(f"/v1/jobs/{job['id']}/export.stl")
    assert stl.status_code == 200
    assert len(stl.content) > 80


def test_size_query_rescales_export():
    files = {"image": ("circle.png", circle_png(), "image/png")}
    created = client.post("/v1/jobs", files=files)
    job_id = created.json()["id"]
    ready = _wait_ready(job_id)
    assert ready["status"] == "ready"

    export = client.get(f"/v1/jobs/{job_id}/export.3mf", params={"size_mm": 120})
    assert export.status_code == 200
    with zipfile.ZipFile(BytesIO(export.content)) as zf:
        xml = zf.read("3D/3dmodel.model")
    root = ET.fromstring(xml)
    verts = root.findall(".//m:vertex", NS)
    xs = [float(v.attrib["x"]) for v in verts]
    ys = [float(v.attrib["y"]) for v in verts]
    zs = [float(v.attrib["z"]) for v in verts]
    longest = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    assert abs(longest - 120) < 0.5
    assert min(zs) >= -0.05


def test_unknown_job_404():
    response = client.get("/v1/jobs/not-a-real-id")
    assert response.status_code == 404


def test_empty_upload_rejected():
    files = {"image": ("empty.png", b"", "image/png")}
    response = client.post("/v1/jobs", files=files)
    assert response.status_code == 400


def test_clamps_size_on_create():
    files = {"image": ("circle.png", circle_png(), "image/png")}
    tiny = client.post("/v1/jobs", files=files, data={"target_size_mm": "1"})
    huge = client.post("/v1/jobs", files=files, data={"target_size_mm": "900"})
    assert tiny.json()["target_size_mm"] == 20
    assert huge.json()["target_size_mm"] == 240
