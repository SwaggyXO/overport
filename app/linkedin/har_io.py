"""Load tagged flagship RSC hops from a captured HAR (offline fixtures only)."""

from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.linkedin.mapper import tag_from_component_id


def _decode_content(content: dict) -> str:
    text = content.get("text") or ""
    encoding = content.get("encoding")
    if encoding == "base64":
        data = base64.b64decode(text)
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        return data.decode("utf-8", errors="replace")
    return text


def load_profile_rsc_bodies(har_path: Path) -> list[tuple[str, str]]:
    """Return tagged GET shell + profile-card RSC bodies, skipping feed/media."""
    har = json.loads(har_path.read_text(encoding="utf-8", errors="replace"))
    tagged: list[tuple[str, str]] = []
    for entry in har.get("log", {}).get("entries", []):
        request = entry.get("request") or {}
        url = request.get("url") or ""
        method = request.get("method") or ""
        if "linkedin.com" not in url:
            continue
        if "/flagship-web/in/" in url and method == "GET":
            tagged.append(("shell", _decode_content((entry.get("response") or {}).get("content") or {})))
            continue
        if "/flagship-web/rsc-action/actions/component" not in url:
            continue
        post = (request.get("postData") or {}).get("text") or ""
        if "flagshipnav.home.Home" in post:
            continue
        if "flagshipnav.profile.Profile" not in post:
            continue
        body = _decode_content((entry.get("response") or {}).get("content") or {})
        if "pymkRecommendedEntitySection" in body:
            continue
        if "browsemapRecommendedEntitySection" in body:
            continue
        if "productRecommendedEntitySection" in body:
            continue
        query = parse_qs(urlparse(url).query)
        component = (query.get("componentId") or [""])[0]
        tag = tag_from_component_id(component)
        if tag is None:
            continue
        tagged.append((tag, body))
    return tagged
