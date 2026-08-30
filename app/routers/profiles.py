import threading
import time
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.linkedin.client import LinkedInClient
from app.linkedin.exceptions import (
    LinkedInClientNotWiredError,
    LinkedInError,
    LinkedInNotConfiguredError,
    LinkedInNotFoundError,
    LinkedInRateLimitError,
    LinkedInSessionError,
    LinkedInUpstreamError,
)
from app.models import ErrorDetail, ErrorResponse, ProfileResponse, profile_response_from_dict
from app.urls import InvalidLinkedInProfileUrlError, parse_linkedin_profile_url

router = APIRouter(prefix="/v1", tags=["profiles"])


class ProfilePostRequest(BaseModel):
    url: str = Field(..., min_length=1)


class _CacheEntry:
    __slots__ = ("payload", "expires_at")

    def __init__(self, payload: dict[str, Any], expires_at: float) -> None:
        self.payload = payload
        self.expires_at = expires_at


class ProfileCache:
    def __init__(self) -> None:
        self._entries: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, vanity: str) -> dict[str, Any] | None:
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(vanity)
            if entry is None:
                return None
            if entry.expires_at <= now:
                del self._entries[vanity]
                return None
            return entry.payload

    def set(self, vanity: str, payload: dict[str, Any], ttl_seconds: int) -> None:
        expires_at = time.monotonic() + ttl_seconds
        with self._lock:
            self._entries[vanity] = _CacheEntry(payload, expires_at)


_profile_cache = ProfileCache()


def get_linkedin_client(settings: Settings = Depends(get_settings)) -> LinkedInClient:
    return LinkedInClient(settings)


def _error_response(code: str, message: str) -> dict[str, dict[str, str]]:
    return ErrorResponse(error=ErrorDetail(code=code, message=message)).model_dump()


def _raise_for_linkedin_error(exc: LinkedInError) -> None:
    if isinstance(exc, LinkedInNotConfiguredError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_response(exc.code, exc.message),
        ) from exc
    if isinstance(exc, LinkedInClientNotWiredError):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=_error_response(exc.code, exc.message),
        ) from exc
    if isinstance(exc, LinkedInSessionError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_response(exc.code, exc.message),
        ) from exc
    if isinstance(exc, LinkedInNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_response(exc.code, exc.message),
        ) from exc
    if isinstance(exc, LinkedInRateLimitError):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_error_response(exc.code, exc.message),
        ) from exc
    if isinstance(exc, LinkedInUpstreamError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_error_response(exc.code, exc.message),
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=_error_response(exc.code, exc.message),
    ) from exc


def _resolve_vanity(
    *,
    url: str | None,
    vanity: str | None,
) -> tuple[str, str]:
    if url and vanity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_response(
                "invalid_request",
                "Provide either 'url' or 'vanity', not both.",
            ),
        )
    if not url and not vanity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_response(
                "invalid_request",
                "Provide either 'url' or 'vanity'.",
            ),
        )

    if url:
        try:
            parsed_vanity = parse_linkedin_profile_url(url)
        except InvalidLinkedInProfileUrlError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_error_response("invalid_linkedin_url", str(exc)),
            ) from exc
        return url, parsed_vanity

    assert vanity is not None
    normalized_vanity = vanity.strip()
    if not normalized_vanity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_response("invalid_vanity", "Vanity name must not be empty."),
        )
    return normalized_vanity, normalized_vanity


async def _fetch_profile(
    *,
    input_value: str,
    vanity: str,
    settings: Settings,
    client: LinkedInClient,
) -> ProfileResponse:
    cached = _profile_cache.get(vanity)
    if cached is not None:
        return profile_response_from_dict(cached)

    try:
        payload = await client.get_profile(vanity)
    except LinkedInError as exc:
        _raise_for_linkedin_error(exc)
        raise

    payload.setdefault("input", input_value)
    payload.setdefault("vanity_name", vanity)
    payload.setdefault("fetched_at", datetime.now(UTC).isoformat())

    sections = payload.get("sections_available") or {}
    about_ok = bool(sections.get("about") and payload.get("profile", {}).get("about"))
    if sections.get("experience") or sections.get("education") or about_ok:
        _profile_cache.set(vanity, payload, settings.cache_ttl_seconds)
    return profile_response_from_dict(payload)


@router.get(
    "/profiles",
    response_model=ProfileResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        501: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
async def get_profile(
    url: str | None = Query(default=None),
    vanity: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
    client: LinkedInClient = Depends(get_linkedin_client),
) -> ProfileResponse:
    input_value, resolved_vanity = _resolve_vanity(url=url, vanity=vanity)
    return await _fetch_profile(
        input_value=input_value,
        vanity=resolved_vanity,
        settings=settings,
        client=client,
    )


@router.post(
    "/profiles",
    response_model=ProfileResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        501: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
)
async def post_profile(
    body: ProfilePostRequest,
    settings: Settings = Depends(get_settings),
    client: LinkedInClient = Depends(get_linkedin_client),
) -> ProfileResponse:
    input_value, resolved_vanity = _resolve_vanity(url=body.url, vanity=None)
    return await _fetch_profile(
        input_value=input_value,
        vanity=resolved_vanity,
        settings=settings,
        client=client,
    )
