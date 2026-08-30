from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.legacy.portal import router as legacy_portal_router
from app.routers import claims, health, profiles

SITE_DIR = Path(__file__).resolve().parent.parent / "docs"

app = FastAPI(
    title="Overport",
    version="0.1.0",
    description=(
        "Stable JSON in front of websites that only speak HTML. "
        "A LinkedIn profile connector replays a short, known HTTP path. "
        "A toy payer portal is wrapped the same way: login, scrape a table, post a form. "
        "Missing fields are omitted, not invented."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://swaggyxo.github.io",
        "http://127.0.0.1:8085",
        "http://localhost:8085",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(health.router)
app.include_router(profiles.router)
app.include_router(claims.router)
app.include_router(legacy_portal_router)


@app.get("/", include_in_schema=False)
def site_home() -> FileResponse:
    return FileResponse(SITE_DIR / "index.html")


@app.get("/config.js", include_in_schema=False)
def site_config() -> FileResponse:
    return FileResponse(SITE_DIR / "config.js", media_type="text/javascript")


if (SITE_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=SITE_DIR / "assets"), name="assets")


def _error_payload(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload("http_error", str(exc.detail)),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_error_payload("validation_error", str(exc.errors())),
    )
