from __future__ import annotations

import httpx
import pytest

from app.providers.meshy import MeshyError, MeshyProvider


def _transport(responses: list[httpx.Response]) -> httpx.MockTransport:
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        if not queue:
            return httpx.Response(500, text="unexpected extra request")
        return queue.pop(0)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_meshy_create_poll_and_copy_glb():
    glb = b"glTF-fake-bytes"
    provider = MeshyProvider(
        api_key="test-key",
        poll_seconds=0,
        timeout_seconds=10,
        transport=_transport(
            [
                httpx.Response(200, json={"result": "task-1"}),
                httpx.Response(200, json={"status": "IN_PROGRESS", "progress": 40}),
                httpx.Response(
                    200,
                    json={
                        "status": "SUCCEEDED",
                        "progress": 100,
                        "model_urls": {"glb": "https://assets.meshy.ai/model.glb"},
                    },
                ),
                httpx.Response(200, content=glb),
            ]
        ),
    )
    result = await provider.generate(b"\xff\xd8fakejpeg", "image/jpeg")
    assert result.provider == "meshy"
    assert result.format == "glb"
    assert result.y_up is True
    assert result.data == glb


@pytest.mark.asyncio
async def test_meshy_failed_task():
    provider = MeshyProvider(
        api_key="test-key",
        poll_seconds=0,
        timeout_seconds=10,
        transport=_transport(
            [
                httpx.Response(200, json={"result": "task-1"}),
                httpx.Response(
                    200,
                    json={"status": "FAILED", "task_error": {"message": "bad image"}},
                ),
            ]
        ),
    )
    with pytest.raises(MeshyError, match="bad image"):
        await provider.generate(b"png", "image/png")
