from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw

from app.providers.stub import StubProvider
from app.store import store


@pytest.fixture(autouse=True)
def isolated_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "root", tmp_path / "jobs")
    store.root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("app.config.settings.meshy_api_key", "")
    monkeypatch.setattr("app.pipeline.get_provider", lambda: StubProvider())
    return store


def circle_png(size: int = 256) -> bytes:
    image = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(image)
    inset = size // 8
    draw.ellipse((inset, inset, size - inset, size - inset), outline="black", width=10)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
