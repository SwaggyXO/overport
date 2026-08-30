from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "service": "overport",
        "status": "ok",
        "linkedin_session_present": settings.linkedin_session_present(),
    }
