from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class ProfileCore(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    headline: str | None = None
    location: str | None = None
    about: str | None = None
    connection_degree: str | None = None


class Images(BaseModel):
    profile_url: str | None = None
    background_url: str | None = None


class Experience(BaseModel):
    title: str | None = None
    company: str | None = None
    company_url: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool | None = None
    description: str | None = None


class Education(BaseModel):
    school: str | None = None
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class Skill(BaseModel):
    name: str
    endorsement_count: int | None = None


class Certification(BaseModel):
    name: str | None = None
    issuer: str | None = None
    issued_on: str | None = None
    expires_on: str | None = None
    credential_id: str | None = None
    url: str | None = None


class Language(BaseModel):
    name: str
    proficiency: str | None = None


class HopRecord(BaseModel):
    name: str
    method: str
    status: int
    bytes: int
    skipped: bool = False


class ConnectorMeta(BaseModel):
    hops: list[HopRecord] = Field(default_factory=list)


class ProfileResponse(BaseModel):
    schema_version: str = "1.0"
    input: str
    vanity_name: str
    linkedin_url: str | None = None
    fetched_at: datetime
    profile: ProfileCore = Field(default_factory=ProfileCore)
    images: Images = Field(default_factory=Images)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    sections_available: dict[str, bool] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    meta: ConnectorMeta = Field(default_factory=ConnectorMeta)


class ClaimResponse(BaseModel):
    schema_version: str = "1.0"
    claim_id: str
    status: str | None = None
    billed_cents: int | None = None
    patient_initials: str | None = None
    as_of: str | None = None
    warnings: list[str] = Field(default_factory=list)
    meta: ConnectorMeta = Field(default_factory=ConnectorMeta)


class NoteRequest(BaseModel):
    claim_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


class NoteResponse(BaseModel):
    schema_version: str = "1.0"
    accepted: bool
    claim_id: str
    warnings: list[str] = Field(default_factory=list)
    meta: ConnectorMeta = Field(default_factory=ConnectorMeta)


def empty_profile_response(
    *,
    input_value: str,
    vanity_name: str,
    fetched_at: datetime | None = None,
) -> ProfileResponse:
    """Build an empty profile response with all sections marked unavailable."""
    return ProfileResponse(
        input=input_value,
        vanity_name=vanity_name,
        fetched_at=fetched_at or datetime.now(UTC),
        sections_available={
            "profile": False,
            "images": False,
            "experience": False,
            "education": False,
            "skills": False,
            "certifications": False,
            "languages": False,
        },
    )


def profile_response_from_dict(data: dict[str, Any]) -> ProfileResponse:
    return ProfileResponse.model_validate(data)
