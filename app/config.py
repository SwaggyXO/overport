from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    linkedin_li_at: SecretStr = Field(default=SecretStr(""), alias="LINKEDIN_LI_AT")
    linkedin_jsessionid: SecretStr = Field(
        default=SecretStr(""),
        alias="LINKEDIN_JSESSIONID",
    )
    linkedin_user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
        ),
        alias="LINKEDIN_USER_AGENT",
    )
    request_timeout_seconds: int = Field(default=20, alias="REQUEST_TIMEOUT_SECONDS")
    rate_limit_per_minute: int = Field(default=4, alias="RATE_LIMIT_PER_MINUTE")
    cache_ttl_seconds: int = Field(default=900, alias="CACHE_TTL_SECONDS")
    legacy_portal_user: SecretStr = Field(default=SecretStr("clerk"), alias="LEGACY_PORTAL_USER")
    legacy_portal_password: SecretStr = Field(
        default=SecretStr("clerk"),
        alias="LEGACY_PORTAL_PASSWORD",
    )

    def linkedin_session_present(self) -> bool:
        return bool(
            self.linkedin_li_at.get_secret_value().strip() and self.linkedin_jsessionid.get_secret_value().strip()
        )

    def safe_repr(self) -> dict[str, object]:
        return {
            "linkedin_session_present": self.linkedin_session_present(),
            "linkedin_user_agent": self.linkedin_user_agent,
            "request_timeout_seconds": self.request_timeout_seconds,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "cache_ttl_seconds": self.cache_ttl_seconds,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
