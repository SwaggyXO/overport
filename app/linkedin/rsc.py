"""Parse LinkedIn flagship RSC (React Server Components) flight streams."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from typing import Any

ACO_RE = re.compile(r"ACoAA[A-Za-z0-9_-]{20,60}")
IMAGE_RE = re.compile(r"https://media\.licdn\.com/dms/image/[^\s\"\\]+")


def _stitch_split_media_url(prefix: str, suffix: str) -> str | None:
    """Join LinkedIn's split displayphoto URLs into one path.

    prefix: .../profile-displayphoto-shrink_
    suffix: 800_800/profile-displayphoto-shrink_800_800/0/{id}
    result: .../profile-displayphoto-shrink_800_800/0/{id}
    """
    match = re.match(r"^(\d+_\d+)/.*?shrink_\1/(.+)$", suffix)
    if not match:
        return None
    return f"{prefix}{match.group(1)}/{match.group(2)}"


DATE_RANGE_RE = re.compile(
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{4}\s*[-–—·•]\s*"
    r"(?:Present|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)\s+\d{4})",
    re.IGNORECASE,
)


def iter_rsc_values(text: str) -> Iterator[Any]:
    """Yield JSON values from an RSC flight stream (`id:{json}` per line)."""
    for line in text.splitlines():
        if ":" not in line:
            continue
        rest = line.split(":", 1)[1].strip()
        if not rest or rest[0] not in "{[":
            continue
        try:
            yield json.loads(rest)
        except json.JSONDecodeError:
            continue


def walk(obj: Any) -> Iterator[Any]:
    yield obj
    if isinstance(obj, dict):
        for value in obj.values():
            yield from walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk(value)


def iter_dicts(text: str) -> Iterator[dict[str, Any]]:
    for value in iter_rsc_values(text):
        for node in walk(value):
            if isinstance(node, dict):
                yield node


def collect_strings(text: str, *, min_len: int = 2, max_len: int = 4000) -> list[str]:
    found: list[str] = []
    for node in walk_from_text(text):
        if isinstance(node, str) and min_len <= len(node) <= max_len:
            found.append(node)
    return found


def react_child_strings(obj: Any) -> Iterator[str]:
    """Yield visible strings from nested React `children`, including `$` element tuples."""
    if obj is None or obj is False:
        return
    if isinstance(obj, str):
        if obj and obj not in {"$", "$undefined"}:
            yield obj
        return
    if isinstance(obj, dict):
        kids = obj.get("children")
        if kids is not None:
            yield from react_child_strings(kids)
        return
    if isinstance(obj, list):
        if obj and obj[0] == "$":
            if len(obj) >= 4:
                yield from react_child_strings(obj[3])
            return
        for item in obj:
            yield from react_child_strings(item)


def leaf_texts(text: str) -> list[str]:
    """Visible copy LinkedIn puts in React `children` / `textProps.children` arrays."""
    found: list[str] = []
    for node in iter_dicts(text):
        containers = [node]
        props = node.get("textProps")
        if isinstance(props, dict):
            containers.append(props)
        for container in containers:
            kids = container.get("children")
            if not isinstance(kids, list) or not kids:
                continue
            if all(isinstance(item, str) for item in kids):
                value = "".join(kids).replace("\xa0", " ").strip()
                if value:
                    found.append(value)
                continue
            chunks = [item.replace("\xa0", " ").strip() for item in react_child_strings(kids)]
            joined = "\n".join(chunk for chunk in chunks if chunk)
            if joined:
                found.append(joined)
    return found


def walk_from_text(text: str) -> Iterator[Any]:
    for value in iter_rsc_values(text):
        yield from walk(value)


def most_common_member_id(text: str) -> str | None:
    counts: dict[str, int] = {}
    for match in ACO_RE.findall(text):
        counts[match] = counts.get(match, 0) + 1
    if not counts:
        return None
    # Prefer the canonical 39-char member id when present.
    ranked = sorted(
        counts.items(),
        key=lambda item: (
            item[0].startswith("ACoAA") and len(item[0]) == 39,
            item[1],
            -len(item[0]),
        ),
        reverse=True,
    )
    return ranked[0][0]


def image_urls(text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    def add(url: str) -> None:
        cleaned = url.split("?")[0]
        if cleaned in seen or "licdn.com" not in cleaned:
            return
        seen.add(cleaned)
        urls.append(cleaned)

    strings = [node for node in walk_from_text(text) if isinstance(node, str)]
    for index, value in enumerate(strings):
        if value.startswith("https://media.licdn.com/") and "shrink_" in value:
            add(value)
            if value.endswith("shrink_") and index + 1 < len(strings):
                nxt = strings[index + 1].split("?")[0]
                stitched = _stitch_split_media_url(value, nxt)
                if stitched:
                    add(stitched)
        elif value.startswith("https://") and "licdn.com" in value:
            add(value)

    for raw in IMAGE_RE.findall(text):
        add(raw)
    return urls


def date_ranges(text: str) -> list[str]:
    return [match.group(0) for match in DATE_RANGE_RE.finditer(text)]


def has_any_marker(text: str, markers: Iterable[str]) -> bool:
    return any(marker in text for marker in markers)
