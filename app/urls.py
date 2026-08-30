from urllib.parse import urlparse

LINKEDIN_HOSTS = frozenset({"linkedin.com", "www.linkedin.com"})


class InvalidLinkedInProfileUrlError(ValueError):
    """Raised when a URL is not a valid LinkedIn /in/{vanity} profile URL."""


def parse_linkedin_profile_url(url: str) -> str:
    """Extract the vanity slug from a LinkedIn profile URL."""
    if not url or not url.strip():
        raise InvalidLinkedInProfileUrlError("Profile URL must not be empty.")

    normalized = url.strip()
    if "://" not in normalized:
        normalized = f"https://{normalized}"

    parsed = urlparse(normalized)

    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    if host not in LINKEDIN_HOSTS:
        raise InvalidLinkedInProfileUrlError(f"Unsupported host '{parsed.netloc or host}'; expected linkedin.com.")

    path = parsed.path.strip("/")
    if not path:
        raise InvalidLinkedInProfileUrlError("Profile URL path must not be empty.")

    segments = path.split("/")

    if len(segments) >= 2 and segments[0] in {"company", "school"}:
        raise InvalidLinkedInProfileUrlError(f"Unsupported LinkedIn path '/{segments[0]}/'; expected '/in/{{vanity}}'.")

    if segments[0] != "in":
        raise InvalidLinkedInProfileUrlError(f"Unsupported LinkedIn path '/{segments[0]}/'; expected '/in/{{vanity}}'.")

    if len(segments) < 2 or not segments[1].strip():
        raise InvalidLinkedInProfileUrlError("Vanity name is missing from the LinkedIn profile URL.")

    vanity = segments[1].strip()
    if not vanity:
        raise InvalidLinkedInProfileUrlError("Vanity name is missing from the LinkedIn profile URL.")

    return vanity
