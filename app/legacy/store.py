"""In-memory claim and note store for the toy HTML portal. Initials only, no PHI."""

from __future__ import annotations

from typing import Any

CLAIMS: dict[str, dict[str, Any]] = {
    "CLM-1001": {
        "claim_id": "CLM-1001",
        "status": "Paid",
        "billed_cents": 125000,
        "patient_initials": "J.D.",
        "as_of": "2026-01-15",
    },
    "CLM-1002": {
        "claim_id": "CLM-1002",
        "status": "Pending",
        "patient_initials": "J.D.",
        "as_of": "2026-02-01",
    },
}

NOTES: dict[str, list[str]] = {}


def get_claim(claim_id: str) -> dict[str, Any] | None:
    return CLAIMS.get(claim_id)


def add_note(claim_id: str, text: str) -> None:
    NOTES.setdefault(claim_id, []).append(text)


def notes_for(claim_id: str) -> list[str]:
    return list(NOTES.get(claim_id, []))
