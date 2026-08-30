"""Shared result type for browserless upstream connectors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Hop:
    """One HTTP hop against an upstream. Never includes cookies or body text."""

    name: str
    method: str
    status: int
    bytes: int
    skipped: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "method": self.method,
            "status": self.status,
            "bytes": self.bytes,
            "skipped": self.skipped,
        }


@dataclass
class ConnectorResult:
    data: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    hops: list[Hop] = field(default_factory=list)
