from __future__ import annotations

from app.config import settings
from app.providers.base import Provider
from app.providers.meshy import MeshyProvider
from app.providers.stub import StubProvider


def get_provider() -> Provider:
    key = (settings.meshy_api_key or "").strip()
    if key:
        return MeshyProvider(
            api_key=key,
            base_url=settings.meshy_base_url,
            poll_seconds=settings.meshy_poll_seconds,
            timeout_seconds=settings.meshy_timeout_seconds,
        )
    return StubProvider()
