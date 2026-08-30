from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
from typing import Any

import httpx

from app.config import Settings
from app.connectors.base import Hop
from app.linkedin.exceptions import (
    LinkedInNotConfiguredError,
    LinkedInNotFoundError,
    LinkedInRateLimitError,
    LinkedInSessionError,
    LinkedInUpstreamError,
)
from app.linkedin.mapper import CARD_TAGS, map_profile
from app.linkedin.rsc import most_common_member_id

PROFILE_SCREEN_ID = "com.linkedin.sdui.flagshipnav.profile.Profile"
COMPONENT_PATH = "/flagship-web/rsc-action/actions/component"
COMPONENT_IMPL_PREFIX = "com.linkedin.sdui.generated.profile.dsl.impl."
PUBLIC_PROFILE_PATH = "/in/{vanity}/"
FLAGSHIP_PROFILE_PATH = "/flagship-web/in/{vanity}/"
# Same JSON body is reused; LinkedIn selects the card via query params.
# Skip activity / PYMK / browsemap. Those showed up in capture and are not profile data.
PROFILE_CARD_COMPONENTS = (
    "profileCardsAboveActivity",
    "profileCardsExperienceOnly",
    "profileCardsBelowActivityPart1WithoutExp",
    "profileCardsBelowActivityPart7",
    "profileCardsBelowActivityPart3",
    "profileCardsBelowActivityPart4",
)

_MIN_INTERVAL_SECONDS = 2.5
_last_request_at = 0.0
_gate = asyncio.Lock()
logger = logging.getLogger(__name__)


def _jsessionid_token(raw: str) -> str:
    return raw.strip().strip('"')


def _page_instance(page_key: str) -> tuple[str, str]:
    token = base64.b64encode(os.urandom(16)).decode("ascii")
    return f"urn:li:page:{page_key};{token}", token


def _looks_like_rsc(text: str) -> bool:
    head = text.lstrip()[:200]
    return head.startswith(("1:", "0:", "2:")) or "$Sreact" in head or "proto.sdui" in text[:4000]


def _build_component_payload(vanity: str, profile_id: str, *, is_self_view: bool) -> dict[str, Any]:
    def binding(suffix: str) -> dict[str, Any]:
        return {
            "type": "com.linkedin.sdui.components.core.BindingImpl",
            "value": {
                "key": f"ProfileComponentState{suffix}{vanity}ProfileComponentState",
                "namespace": "MemoryNamespace",
            },
        }

    return {
        "clientArguments": {
            "payload": {
                "isSelfView": is_self_view,
                "vanityName": vanity,
                "replaceableSectionArgs": {
                    "vanityName": vanity,
                    "hideCardsForGoldenGate": False,
                    "shouldSetupReplaceableComponent": True,
                    "vieweeProfileId": profile_id,
                    "isSelfView": is_self_view,
                    "isSelfViewResolved": is_self_view,
                },
                "profileComponentState": {
                    "profileId": vanity,
                    "shouldRefreshScreenOnReappear": binding("ShouldRefreshScreen"),
                    "shouldFetchFromCache": binding("FetchFromCache"),
                    "loadedSections": binding("LoadedProfileSections"),
                    "shouldDisplayTabAnchors": binding("ShouldDisplayTabAnchors"),
                    "shouldReloadTopCardOnReappear": binding("ShouldReloadTopCardOnReappear"),
                    "deferredTopCardReloadProfileId": binding("DeferredTopCardReloadProfileId"),
                    "shouldDisplayStickyHeader": binding("ShouldDisplayStickyHeader"),
                    "shouldRefreshLanguageDetailScreen": binding("ShouldRefreshLanguageDetailScreen"),
                    "lastPerformedActionRef": binding("LastPerformedActionRef"),
                    "shouldFocusOnReappear": binding("ShouldFocusOnReappear"),
                    "shouldFocusFeaturedOnReappear": binding("ShouldFocusFeaturedOnReappear"),
                    "lastFeaturedActionRef": binding("LastFeaturedActionRef"),
                    "shouldHideProfileCards": binding("ProfileHideCards"),
                },
            },
            "states": [],
            "requestMetadata": {"$type": "proto.sdui.common.RequestMetadata"},
            "screenId": PROFILE_SCREEN_ID,
            "knownTemplateIds": [],
        }
    }


class LinkedInClient:
    """Browserless LinkedIn client wired from captured flagship-web HAR traffic.

    Live path:
    1. GET /in/{vanity}/?skipRedirect=true
    2. GET /flagship-web/in/{vanity}/ with a generated profile page-instance
    3. POST each profile card with componentId/sduiid query params (same body)
    If a card POST fails, keep whatever the GETs and other cards returned.
    """

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._settings = settings
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        self._application_instance = base64.b64encode(os.urandom(16)).decode("ascii")

    @property
    def is_configured(self) -> bool:
        return self._settings.linkedin_session_present()

    async def get_profile(self, vanity: str) -> dict[str, Any]:
        if not self.is_configured:
            raise LinkedInNotConfiguredError(
                "LinkedIn session cookies are not configured. "
                "Set LINKEDIN_LI_AT and LINKEDIN_JSESSIONID in the environment."
            )

        await self._throttle_profile()
        client = await self._http()
        tagged: list[tuple[str, str]] = []
        hops: list[Hop] = []
        forest_id = os.urandom(16).hex()
        page_urn, tracking = _page_instance("d_flagship3_profile_view_base")
        profile_headers = self._headers(
            vanity,
            page_key="d_flagship3_profile_view_base",
            page_urn=page_urn,
            tracking=tracking,
            forest_id=forest_id,
        )

        public_response = await client.get(
            PUBLIC_PROFILE_PATH.format(vanity=vanity),
            params={"skipRedirect": "true"},
            headers=self._headers(vanity, forest_id=forest_id),
        )
        public_text = self._raise_for_status(public_response, vanity, hop=f"GET /in/{vanity}/?skipRedirect=true")
        tagged.append(("shell", public_text))
        hops.append(self._hop("shell", "GET", public_response))

        try:
            await self._pause()
            flagship_response = await client.get(
                FLAGSHIP_PROFILE_PATH.format(vanity=vanity),
                headers=profile_headers,
            )
            flagship_text = self._raise_for_status(
                flagship_response,
                vanity,
                hop=f"GET /flagship-web/in/{vanity}/",
            )
            tagged.append(("shell", flagship_text))
            hops.append(self._hop("shell", "GET", flagship_response))
        except LinkedInUpstreamError:
            logger.warning("Skipping flagship GET")
            hops.append(Hop(name="shell", method="GET", status=500, bytes=0, skipped=True))

        combined_gets = "\n".join(text for _, text in tagged)
        profile_id = most_common_member_id(combined_gets)
        if not (profile_id and profile_id.startswith("ACoAA") and len(profile_id) == 39):
            logger.warning("Skipping profile component POSTs: no member id in GET bodies")
        else:
            payload = _build_component_payload(vanity, profile_id, is_self_view=False)
            for card in PROFILE_CARD_COMPONENTS:
                await self._pause()
                component_id = f"{COMPONENT_IMPL_PREFIX}{card}"
                tag = CARD_TAGS[card]
                try:
                    post_response = await client.post(
                        COMPONENT_PATH,
                        params={
                            "componentId": component_id,
                            "sduiid": component_id,
                            "parentSpanId": base64.b64encode(os.urandom(8)).decode("ascii"),
                        },
                        headers=self._headers(
                            vanity,
                            json_body=True,
                            page_key="d_flagship3_profile_view_base",
                            page_urn=page_urn,
                            tracking=tracking,
                            forest_id=forest_id,
                        ),
                        json=payload,
                    )
                    post_text = self._raise_for_status(
                        post_response,
                        vanity,
                        hop=f"POST {COMPONENT_PATH}?componentId={card}",
                    )
                    tagged.append((tag, post_text))
                    hops.append(self._hop(tag, "POST", post_response))
                except (LinkedInUpstreamError, LinkedInRateLimitError) as exc:
                    status = 429 if isinstance(exc, LinkedInRateLimitError) else 500
                    logger.warning("Skipping profile component POST %s", card)
                    hops.append(Hop(name=tag, method="POST", status=status, bytes=0, skipped=True))

        mapped = map_profile(vanity=vanity, input_value=vanity, tagged=tagged, hops=hops)
        if not mapped["sections_available"].get("profile") and not mapped["experience"]:
            raise LinkedInUpstreamError(
                "LinkedIn returned a payload that did not contain a readable profile. "
                "Re-export cookies from the dummy Chromium profile and retry once."
            )
        return mapped

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> LinkedInClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.aclose()

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            token = _jsessionid_token(self._settings.linkedin_jsessionid.get_secret_value())
            cookies = {
                "li_at": self._settings.linkedin_li_at.get_secret_value().strip(),
                "JSESSIONID": f'"{token}"',
            }
            self._client = httpx.AsyncClient(
                base_url="https://www.linkedin.com",
                cookies=cookies,
                timeout=self._settings.request_timeout_seconds,
                follow_redirects=True,
                transport=self._transport,
                headers={"accept-language": "en-US,en;q=0.9"},
            )
        return self._client

    def _headers(
        self,
        vanity: str,
        *,
        json_body: bool = False,
        page_key: str | None = None,
        page_urn: str | None = None,
        tracking: str | None = None,
        forest_id: str | None = None,
    ) -> dict[str, str]:
        token = _jsessionid_token(self._settings.linkedin_jsessionid.get_secret_value())
        span_id = os.urandom(8).hex()
        headers = {
            "accept": "*/*",
            "csrf-token": token,
            "origin": "https://www.linkedin.com",
            "user-agent": self._settings.linkedin_user_agent,
            "referer": f"https://www.linkedin.com/in/{vanity}/?skipRedirect=true",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-li-rsc-stream": "true",
            "x-li-application-version": "0.2.6951",
            "x-li-application-instance": self._application_instance,
            "x-li-track": json.dumps(
                {
                    "clientVersion": "0.2.6951",
                    "mpVersion": "0.2.6951",
                    "osName": "web",
                    "mpName": "web",
                    "deviceFormFactor": "DESKTOP",
                    "displayDensity": 1,
                    "displayWidth": 1920,
                    "displayHeight": 1080,
                }
            ),
        }
        if forest_id:
            headers["x-li-pageforestid"] = forest_id
            headers["x-li-traceparent"] = f"00-{forest_id}-{span_id}-00"
            headers["x-li-tracestate"] = f"LinkedIn={span_id}"
        if page_key:
            headers["x-li-anchor-page-key"] = page_key
        if page_urn:
            headers["x-li-page-instance"] = page_urn
        if tracking:
            headers["x-li-page-instance-tracking-id"] = tracking
        if json_body:
            headers["content-type"] = "application/json"
        return headers

    def _raise_for_status(self, response: httpx.Response, vanity: str, *, hop: str) -> str:
        status = response.status_code
        text = response.text or ""
        logger.info("linkedin %s -> %s (%s bytes)", hop, status, len(text))
        if status in {401, 403} or "checkpoint/challenge" in str(response.url):
            raise LinkedInSessionError("LinkedIn session expired or was challenged. Re-export cookies from Chromium.")
        if status in {429, 999}:
            raise LinkedInRateLimitError("LinkedIn rate-limited the session. Wait before retrying.")
        if status == 404:
            raise LinkedInNotFoundError(f"LinkedIn profile '{vanity}' was not found.")
        if status == 400:
            raise LinkedInSessionError(f"LinkedIn rejected {hop} (HTTP 400). Cookies or csrf-token are likely stale.")
        if status >= 400:
            logger.warning("linkedin %s HTTP %s", hop.split("?")[0], status)
            raise LinkedInUpstreamError(f"LinkedIn returned HTTP {status} for {hop}.")
        lowered = text[:800].lower()
        if "sign in" in lowered and "linkedin" in lowered and not _looks_like_rsc(text):
            raise LinkedInSessionError("LinkedIn returned a sign-in page. Re-export cookies.")
        return text

    def _hop(self, name: str, method: str, response: httpx.Response) -> Hop:
        return Hop(
            name=name,
            method=method,
            status=response.status_code,
            bytes=len(response.text or ""),
        )

    async def _pause(self) -> None:
        if self._transport is not None:
            return
        await asyncio.sleep(_MIN_INTERVAL_SECONDS)

    async def _throttle_profile(self) -> None:
        if self._transport is not None:
            return
        global _last_request_at
        interval = 60.0 / max(self._settings.rate_limit_per_minute, 1)
        async with _gate:
            now = time.monotonic()
            wait_for = interval - (now - _last_request_at)
            if wait_for > 0:
                await asyncio.sleep(wait_for)
            _last_request_at = time.monotonic()
