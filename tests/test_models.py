from datetime import UTC, datetime

from app.models import ProfileResponse, empty_profile_response


def test_profile_response_empty_defaults() -> None:
    response = empty_profile_response(
        input_value="jane-doe",
        vanity_name="jane-doe",
        fetched_at=datetime(2026, 8, 27, 0, 0, tzinfo=UTC),
    )

    assert response.experience == []
    assert response.education == []
    assert response.skills == []
    assert response.certifications == []
    assert response.languages == []
    assert response.profile.full_name is None
    assert response.images.profile_url is None


def test_profile_response_serializes_with_empty_lists() -> None:
    response = empty_profile_response(
        input_value="https://www.linkedin.com/in/jane-doe",
        vanity_name="jane-doe",
        fetched_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )

    payload = response.model_dump(mode="json")

    assert payload["experience"] == []
    assert payload["education"] == []
    assert payload["skills"] == []
    assert payload["certifications"] == []
    assert payload["languages"] == []
    assert payload["profile"]["full_name"] is None
    assert payload["sections_available"]["experience"] is False

    round_trip = ProfileResponse.model_validate(payload)
    assert round_trip.vanity_name == "jane-doe"


def test_profile_response_json_round_trip() -> None:
    response = ProfileResponse(
        input="https://www.linkedin.com/in/jane-doe",
        vanity_name="jane-doe",
        fetched_at=datetime(2026, 8, 27, 0, 0, tzinfo=UTC),
    )

    serialized = response.model_dump(mode="json")
    restored = ProfileResponse.model_validate(serialized)

    assert restored.input == response.input
    assert restored.fetched_at == response.fetched_at
    assert restored.sections_available == {}
