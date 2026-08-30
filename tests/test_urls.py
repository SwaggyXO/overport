import pytest
from app.urls import InvalidLinkedInProfileUrlError, parse_linkedin_profile_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.linkedin.com/in/jane-doe", "jane-doe"),
        ("http://linkedin.com/in/jane-doe", "jane-doe"),
        ("linkedin.com/in/jane-doe/", "jane-doe"),
        ("https://www.linkedin.com/in/jane-doe/", "jane-doe"),
        ("https://www.linkedin.com/in/jane-doe?trk=public_profile", "jane-doe"),
        ("https://linkedin.com/in/jane-doe?locale=en_US", "jane-doe"),
    ],
)
def test_parse_linkedin_profile_url_happy_cases(url: str, expected: str) -> None:
    assert parse_linkedin_profile_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "https://example.com/in/jane-doe",
        "https://www.linkedin.com/company/acme",
        "https://www.linkedin.com/school/mit",
        "https://www.linkedin.com/in/",
        "https://www.linkedin.com/in",
        "https://www.linkedin.com/jobs",
    ],
)
def test_parse_linkedin_profile_url_sad_cases(url: str) -> None:
    with pytest.raises(InvalidLinkedInProfileUrlError):
        parse_linkedin_profile_url(url)
