"""Thin LinkedIn connector wrapping the HAR-wired HTTP client."""

from __future__ import annotations

from app.config import Settings
from app.connectors.base import ConnectorResult, Hop
from app.linkedin.client import LinkedInClient


class LinkedInConnector:
    def __init__(self, settings: Settings, *, transport=None) -> None:
        self._client = LinkedInClient(settings, transport=transport)

    async def fetch_profile(self, vanity: str) -> ConnectorResult:
        data = await self._client.get_profile(vanity)
        hops = [Hop(**item) for item in (data.get("meta") or {}).get("hops") or []]
        return ConnectorResult(data=data, warnings=list(data.get("warnings") or []), hops=hops)

    async def aclose(self) -> None:
        await self._client.aclose()
