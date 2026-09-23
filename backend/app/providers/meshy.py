from __future__ import annotations

import base64
import asyncio
from typing import Any

import httpx

from app.providers.base import MeshBytes


class MeshyError(RuntimeError):
    pass


class MeshyProvider:
    name = "meshy"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.meshy.ai",
        poll_seconds: float = 4.0,
        timeout_seconds: float = 180.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def generate(self, image_bytes: bytes, content_type: str) -> MeshBytes:
        mime = content_type.split(";")[0].strip() if content_type else "image/jpeg"
        if mime not in {"image/jpeg", "image/jpg", "image/png"}:
            mime = "image/png"
        data_uri = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        payload: dict[str, Any] = {
            "image_url": data_uri,
            "ai_model": "latest",
            "should_texture": False,
            "should_remesh": True,
            "topology": "triangle",
            "target_polycount": 40_000,
        }

        timeout = httpx.Timeout(60.0, read=120.0)
        async with httpx.AsyncClient(timeout=timeout, transport=self.transport) as client:
            created = await client.post(
                f"{self.base_url}/openapi/v1/image-to-3d",
                json=payload,
                headers=self._headers(),
            )
            if created.status_code >= 400:
                raise MeshyError(f"Meshy create failed ({created.status_code}): {created.text[:500]}")
            body = created.json()
            task_id = body.get("result") or body.get("id")
            if not task_id:
                raise MeshyError(f"Meshy create response missing task id: {body!r}")

            elapsed = 0.0
            task: dict[str, Any] = {}
            while elapsed <= self.timeout_seconds:
                polled = await client.get(
                    f"{self.base_url}/openapi/v1/image-to-3d/{task_id}",
                    headers=self._headers(),
                )
                if polled.status_code >= 400:
                    raise MeshyError(f"Meshy poll failed ({polled.status_code}): {polled.text[:500]}")
                task = polled.json()
                status = str(task.get("status", "")).upper()
                if status == "SUCCEEDED":
                    break
                if status in {"FAILED", "CANCELED", "CANCELLED"}:
                    err = task.get("task_error") or {}
                    message = err.get("message") if isinstance(err, dict) else str(err)
                    raise MeshyError(message or f"Meshy task {status.lower()}")
                await asyncio.sleep(self.poll_seconds)
                elapsed += self.poll_seconds
            else:
                raise MeshyError("Meshy task timed out")

            urls = task.get("model_urls") or {}
            glb_url = urls.get("glb") or task.get("model_url")
            if not glb_url:
                raise MeshyError("Meshy succeeded but returned no GLB URL")
            # Signed URLs expire quickly — copy bytes immediately.
            mesh = await client.get(glb_url)
            if mesh.status_code >= 400:
                raise MeshyError(f"Meshy GLB download failed ({mesh.status_code})")
            return MeshBytes(data=mesh.content, format="glb", y_up=True, provider=self.name)
