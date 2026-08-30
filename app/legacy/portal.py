"""Deliberately ugly HTML-only payer portal. No JSON endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from app.config import Settings, get_settings
from app.legacy import store

router = APIRouter(prefix="/legacy", tags=["legacy-portal"])
COOKIE = "legacy_session"


def _page(title: str, body: str, status: int = 200) -> HTMLResponse:
    html = f"""<!DOCTYPE html>
<html>
<head><title>{title}</title></head>
<body bgcolor="#e8e8e8">
<h1>{title}</h1>
{body}
</body>
</html>
"""
    return HTMLResponse(html, status_code=status)


def _authed(request: Request) -> bool:
    return request.cookies.get(COOKIE) == "ok"


@router.get("/login", response_class=HTMLResponse)
def login_form() -> HTMLResponse:
    return _page(
        "Portal Login",
        """
<form method="post" action="/legacy/login">
  <div>User <input name="username" /></div>
  <div>Pass <input name="password" type="password" /></div>
  <button type="submit">Sign in</button>
</form>
""",
    )


@router.post("/login", response_class=HTMLResponse)
def login(
    username: str = Form(""),
    password: str = Form(""),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
    expected_user = settings.legacy_portal_user.get_secret_value()
    expected_pass = settings.legacy_portal_password.get_secret_value()
    if username != expected_user or password != expected_pass:
        return _page("Portal Login", "<p>Access denied</p>", status=401)
    response = _page("Portal Login", "<p>Welcome, clerk.</p>")
    response.set_cookie(COOKIE, "ok", httponly=True)
    return response


@router.get("/claims/{claim_id}", response_class=HTMLResponse)
def claim_status(claim_id: str, request: Request) -> HTMLResponse:
    if not _authed(request):
        return _page("Portal Login", "<p>Please sign in</p>", status=401)
    record = store.get_claim(claim_id)
    if record is None:
        return _page("Claim", f"<p>No claim {claim_id}</p>", status=404)
    rows = [
        ("Claim ID", record["claim_id"]),
        ("Status", record["status"]),
        ("Patient initials", record["patient_initials"]),
        ("As of", record["as_of"]),
    ]
    if "billed_cents" in record:
        dollars = record["billed_cents"] / 100
        rows.insert(2, ("Billed", f"{dollars:.2f}"))
    cells = "".join(f"<tr><th>{label}</th><td>{value}</td></tr>" for label, value in rows)
    return _page("Claim Status", f'<table border="1">{cells}</table>')


@router.get("/notes", response_class=HTMLResponse)
def notes_form(request: Request) -> HTMLResponse:
    if not _authed(request):
        return _page("Portal Login", "<p>Please sign in</p>", status=401)
    return _page(
        "Clinical Note",
        """
<form method="post" action="/legacy/notes">
  <div>Claim <input name="claim_id" /></div>
  <div>Note <textarea name="text"></textarea></div>
  <button type="submit">Submit</button>
</form>
""",
    )


@router.post("/notes", response_class=HTMLResponse)
def submit_note(
    request: Request,
    claim_id: str = Form(""),
    text: str = Form(""),
) -> HTMLResponse:
    if not _authed(request):
        return _page("Portal Login", "<p>Please sign in</p>", status=401)
    if not text.strip():
        return _page("Clinical Note", "<p>Note text is required</p>", status=400)
    if store.get_claim(claim_id) is None:
        return _page("Clinical Note", f"<p>No claim {claim_id}</p>", status=404)
    store.add_note(claim_id, text.strip())
    return _page("Clinical Note", f"<p>Accepted note for {claim_id}</p>")
