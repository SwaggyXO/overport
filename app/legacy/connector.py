"""Browserless client for the in-app HTML portal."""

from __future__ import annotations

import httpx

from app.config import Settings
from app.connectors.base import ConnectorResult, Hop
from app.legacy.parse import parse_claim_html


class LegacyPortalConnector:
    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http

    async def get_claim(self, claim_id: str) -> ConnectorResult:
        hops: list[Hop] = []
        await self._login(hops)
        response = await self._http.get(f"/legacy/claims/{claim_id}")
        hops.append(_hop("claim_status", "GET", response))
        parsed = parse_claim_html(response.text or "")
        fields = parsed["fields"]
        warnings = list(parsed["warnings"])
        if response.status_code == 401:
            warnings.append("legacy_session_rejected")
        if response.status_code == 404:
            warnings.append("claim_not_found")
        data = {
            "schema_version": "1.0",
            "claim_id": fields.get("claim_id") or claim_id,
            "status": fields.get("status"),
            "billed_cents": fields.get("billed_cents"),
            "patient_initials": fields.get("patient_initials"),
            "as_of": fields.get("as_of"),
            "warnings": warnings,
            "meta": {"hops": [hop.as_dict() for hop in hops]},
        }
        return ConnectorResult(data=data, warnings=warnings, hops=hops)

    async def submit_note(self, claim_id: str, text: str) -> ConnectorResult:
        hops: list[Hop] = []
        await self._login(hops)
        response = await self._http.post(
            "/legacy/notes",
            data={"claim_id": claim_id, "text": text},
        )
        hops.append(_hop("note_submit", "POST", response))
        warnings: list[str] = []
        accepted = response.status_code < 400
        if response.status_code == 404:
            warnings.append("claim_not_found")
        elif not accepted:
            warnings.append("note_rejected")
        data = {
            "schema_version": "1.0",
            "accepted": accepted,
            "claim_id": claim_id,
            "warnings": warnings,
            "meta": {"hops": [hop.as_dict() for hop in hops]},
        }
        return ConnectorResult(data=data, warnings=warnings, hops=hops)

    async def _login(self, hops: list[Hop]) -> None:
        response = await self._http.post(
            "/legacy/login",
            data={
                "username": self._settings.legacy_portal_user.get_secret_value(),
                "password": self._settings.legacy_portal_password.get_secret_value(),
            },
        )
        hops.append(_hop("login", "POST", response))


def _hop(name: str, method: str, response: httpx.Response) -> Hop:
    return Hop(
        name=name,
        method=method,
        status=response.status_code,
        bytes=len(response.text or ""),
        skipped=response.status_code >= 400,
    )
