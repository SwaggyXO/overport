from app.config import get_settings
from app.main import app
from fastapi.testclient import TestClient


def test_health_ok() -> None:
    get_settings.cache_clear()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "overport"
    assert "linkedin_session_present" in body
    assert "li_at" not in str(body).lower()


def test_home_page() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Overport" in response.text
    assert "li_at" not in response.text.lower()


def test_profile_invalid_url_error_envelope() -> None:
    get_settings.cache_clear()
    client = TestClient(app)
    response = client.get(
        "/v1/profiles",
        params={"url": "https://www.linkedin.com/company/acme"},
    )
    assert response.status_code == 400
    body = response.json()
    assert "detail" not in body
    assert body["error"]["code"] == "invalid_linkedin_url"


def test_profile_missing_cookies_is_401(monkeypatch) -> None:
    monkeypatch.setenv("LINKEDIN_LI_AT", "")
    monkeypatch.setenv("LINKEDIN_JSESSIONID", "")
    get_settings.cache_clear()
    client = TestClient(app)
    response = client.get("/v1/profiles", params={"vanity": "jane-doe"})
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "linkedin_not_configured"
