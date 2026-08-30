import httpx
import pytest
from app.config import Settings
from app.linkedin.client import LinkedInClient
from app.linkedin.exceptions import LinkedInUpstreamError
from pydantic import SecretStr


def _settings() -> Settings:
    return Settings(
        linkedin_li_at=SecretStr("test-li-at"),
        linkedin_jsessionid=SecretStr("ajax:1"),
        rate_limit_per_minute=600,
        request_timeout_seconds=5,
        cache_ttl_seconds=1,
    )


MEMBER_ID = "ACoAAabcdefghijklmnopqrstuvwxyz12345678"


def _rsc_body(vanity: str) -> str:
    return (
        '1:"$Sreact.fragment"\n'
        f'2:{{"firstName":"Ada","lastName":"Lovelace","vanityName":"{vanity}",'
        f'"entityUrn":"urn:li:fsd_profile:{MEMBER_ID}"}}\n'
        '3:{"headline":"Mathematician"}\n'
        f'4:"{MEMBER_ID}"\n'
    )


@pytest.mark.asyncio
async def test_get_profile_uses_skip_redirect_and_survives_post_500() -> None:
    vanity = "ada-lovelace"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == f"/in/{vanity}/":
            return httpx.Response(200, text=_rsc_body(vanity))
        if path == f"/flagship-web/in/{vanity}/":
            return httpx.Response(200, text=_rsc_body(vanity))
        if path == "/flagship-web/rsc-action/actions/component":
            return httpx.Response(500, text="nope")
        raise AssertionError(f"unexpected path {path}")

    client = LinkedInClient(_settings(), transport=httpx.MockTransport(handler))
    payload = await client.get_profile(vanity)
    assert payload["profile"]["first_name"] == "Ada"
    assert payload["vanity_name"] == vanity
    assert any(hop["skipped"] and hop["name"] == "experience" for hop in payload["meta"]["hops"])
    await client.aclose()


@pytest.mark.asyncio
async def test_get_profile_falls_back_to_flagship_when_html() -> None:
    vanity = "example-vanity"

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == f"/in/{vanity}/":
            return httpx.Response(200, text="<!doctype html><html><body>app</body></html>")
        if path == f"/flagship-web/in/{vanity}/":
            return httpx.Response(200, text=_rsc_body(vanity))
        if path == "/flagship-web/rsc-action/actions/component":
            return httpx.Response(200, text="1:{}\n")
        raise AssertionError(f"unexpected path {path}")

    client = LinkedInClient(_settings(), transport=httpx.MockTransport(handler))
    payload = await client.get_profile(vanity)
    assert payload["profile"]["full_name"] == "Ada Lovelace"
    await client.aclose()


@pytest.mark.asyncio
async def test_get_profile_posts_each_card_with_component_id() -> None:
    vanity = "example-vanity"
    posted: list[str] = []
    bodies: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == f"/in/{vanity}/":
            return httpx.Response(200, text=_rsc_body(vanity))
        if path == f"/flagship-web/in/{vanity}/":
            return httpx.Response(200, text=_rsc_body(vanity))
        if path == "/flagship-web/rsc-action/actions/component":
            posted.append(str(request.url))
            bodies.append(request.content.decode())
            return httpx.Response(200, text="1:{}\n")
        raise AssertionError(f"unexpected path {path}")

    client = LinkedInClient(_settings(), transport=httpx.MockTransport(handler))
    await client.get_profile(vanity)
    await client.aclose()
    assert len(posted) == 6
    joined = "\n".join(posted)
    assert "profileCardsAboveActivity" in joined
    assert "profileCardsExperienceOnly" in joined
    assert "parentSpanId=" in joined
    assert all(MEMBER_ID in body for body in bodies)


@pytest.mark.asyncio
async def test_flagship_500_includes_hop_in_message() -> None:
    vanity = "example-vanity"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="broken")

    client = LinkedInClient(_settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(LinkedInUpstreamError, match="GET /in/example-vanity"):
        await client.get_profile(vanity)
    await client.aclose()
