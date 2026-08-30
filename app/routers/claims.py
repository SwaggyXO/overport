import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import Settings, get_settings
from app.legacy.connector import LegacyPortalConnector
from app.models import ClaimResponse, ErrorDetail, ErrorResponse, NoteRequest, NoteResponse

router = APIRouter(prefix="/v1", tags=["legacy-api"])


def _error_response(code: str, message: str) -> dict[str, dict[str, str]]:
    return ErrorResponse(error=ErrorDetail(code=code, message=message)).model_dump()


async def _portal_http(request: Request) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=request.app),
        base_url="http://legacy.test",
        follow_redirects=True,
    )


@router.get(
    "/claims/{claim_id}",
    response_model=ClaimResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_claim(
    claim_id: str,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> ClaimResponse:
    async with await _portal_http(request) as http:
        result = await LegacyPortalConnector(settings, http).get_claim(claim_id)
    if "legacy_session_rejected" in result.warnings:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error_response("legacy_session_rejected", "Legacy portal login failed."),
        )
    if "claim_not_found" in result.warnings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_response("claim_not_found", f"Claim '{claim_id}' was not found."),
        )
    return ClaimResponse.model_validate(result.data)


@router.post(
    "/notes",
    response_model=NoteResponse,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def post_note(
    body: NoteRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> NoteResponse:
    text = body.text.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_response("invalid_note", "Note text must not be empty."),
        )
    async with await _portal_http(request) as http:
        result = await LegacyPortalConnector(settings, http).submit_note(body.claim_id, text)
    if "claim_not_found" in result.warnings or any(hop.status == 404 for hop in result.hops):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_response("claim_not_found", f"Claim '{body.claim_id}' was not found."),
        )
    return NoteResponse.model_validate(result.data)
