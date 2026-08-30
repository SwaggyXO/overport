"""Parse claim-status HTML from the in-app legacy portal. Never invent amounts."""

from __future__ import annotations

import re
from typing import Any

ROW_RE = re.compile(
    r"<th[^>]*>(?P<label>[^<]+)</th>\s*<td[^>]*>(?P<value>[^<]*)</td>",
    re.IGNORECASE,
)


def parse_claim_html(html: str) -> dict[str, Any]:
    """Extract known cells. Missing billed amount is omitted, not zeroed."""
    rows: dict[str, str] = {}
    for match in ROW_RE.finditer(html):
        label = " ".join(match.group("label").split()).strip().lower()
        value = " ".join(match.group("value").split()).strip()
        rows[label] = value

    data: dict[str, Any] = {}
    warnings: list[str] = []
    if rows.get("claim id"):
        data["claim_id"] = rows["claim id"]
    if rows.get("status"):
        data["status"] = rows["status"]
    if rows.get("patient initials"):
        data["patient_initials"] = rows["patient initials"]
    if rows.get("as of"):
        data["as_of"] = rows["as of"]

    billed_raw = rows.get("billed") or rows.get("billed amount")
    if billed_raw:
        cents = _parse_dollars_to_cents(billed_raw)
        if cents is None:
            warnings.append("billed_cents_unparsed")
        else:
            data["billed_cents"] = cents
    else:
        warnings.append("billed_cents_missing")

    if "claim id" not in rows:
        warnings.append("claim_id_missing")
    return {"fields": data, "warnings": warnings}


def _parse_dollars_to_cents(raw: str) -> int | None:
    cleaned = raw.replace("$", "").replace(",", "").strip()
    if not cleaned:
        return None
    try:
        dollars = float(cleaned)
    except ValueError:
        return None
    return int(round(dollars * 100))
