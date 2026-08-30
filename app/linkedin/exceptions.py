class LinkedInError(Exception):
    """Base error for LinkedIn client failures."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code

    @property
    def default_code(self) -> str:
        return "linkedin_error"


class LinkedInSessionError(LinkedInError):
    """Session cookies are invalid or expired."""

    @property
    def default_code(self) -> str:
        return "linkedin_session_error"


class LinkedInNotFoundError(LinkedInError):
    """Requested profile was not found."""

    @property
    def default_code(self) -> str:
        return "linkedin_not_found"


class LinkedInRateLimitError(LinkedInError):
    """LinkedIn rate limit exceeded."""

    @property
    def default_code(self) -> str:
        return "linkedin_rate_limit"


class LinkedInUpstreamError(LinkedInError):
    """Unexpected upstream LinkedIn failure."""

    @property
    def default_code(self) -> str:
        return "linkedin_upstream_error"


class LinkedInNotConfiguredError(LinkedInError):
    """Required LinkedIn session cookies are missing."""

    @property
    def default_code(self) -> str:
        return "linkedin_not_configured"


class LinkedInClientNotWiredError(LinkedInError):
    """Client stub has not been wired from a captured HAR yet."""

    @property
    def default_code(self) -> str:
        return "linkedin_client_not_wired"
