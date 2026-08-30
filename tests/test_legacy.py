from pathlib import Path

from app.config import get_settings
from app.legacy.parse import parse_claim_html
from app.main import app
from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_paid_claim_fixture() -> None:
    html = (FIXTURES / "claim_paid.html").read_text(encoding="utf-8")
    parsed = parse_claim_html(html)
    assert parsed["fields"]["claim_id"] == "CLM-1001"
    assert parsed["fields"]["status"] == "Paid"
    assert parsed["fields"]["billed_cents"] == 125000
    assert parsed["fields"]["patient_initials"] == "J.D."
    assert "billed_cents_missing" not in parsed["warnings"]


def test_parse_missing_billed_does_not_invent_zero() -> None:
    html = (FIXTURES / "claim_missing_billed.html").read_text(encoding="utf-8")
    parsed = parse_claim_html(html)
    assert "billed_cents" not in parsed["fields"]
    assert parsed["fields"]["status"] == "Pending"
    assert "billed_cents_missing" in parsed["warnings"]


def test_v1_claim_paid_through_html_portal() -> None:
    get_settings.cache_clear()
    client = TestClient(app)
    response = client.get("/v1/claims/CLM-1001")
    assert response.status_code == 200
    body = response.json()
    assert body["claim_id"] == "CLM-1001"
    assert body["status"] == "Paid"
    assert body["billed_cents"] == 125000
    assert body["patient_initials"] == "J.D."
    assert any(hop["name"] == "login" for hop in body["meta"]["hops"])
    assert "li_at" not in str(body).lower()


def test_v1_claim_omits_missing_amount() -> None:
    get_settings.cache_clear()
    client = TestClient(app)
    response = client.get("/v1/claims/CLM-1002")
    assert response.status_code == 200
    body = response.json()
    assert body["billed_cents"] is None
    assert "billed_cents_missing" in body["warnings"]
    assert body["billed_cents"] != 0


def test_v1_claim_unknown_is_404() -> None:
    get_settings.cache_clear()
    client = TestClient(app)
    response = client.get("/v1/claims/CLM-9999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "claim_not_found"


def test_v1_note_posts_html_form() -> None:
    get_settings.cache_clear()
    client = TestClient(app)
    response = client.post(
        "/v1/notes",
        json={"claim_id": "CLM-1001", "text": "Follow-up visit documented."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert any(hop["name"] == "note_submit" and hop["method"] == "POST" for hop in body["meta"]["hops"])


def test_v1_note_rejects_empty_text() -> None:
    get_settings.cache_clear()
    client = TestClient(app)
    response = client.post("/v1/notes", json={"claim_id": "CLM-1001", "text": "   "})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_note"
