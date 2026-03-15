"""Simple password gate for the app."""

import hashlib
import hmac
import logging
import time

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from chronocanvas.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_NAME = "cc_session"
_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def _sign(payload: str) -> str:
    """Create an HMAC signature for the payload."""
    return hmac.new(
        settings.secret_key.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def _make_token() -> str:
    """Create a signed session token (timestamp + signature)."""
    ts = str(int(time.time()))
    sig = _sign(ts)
    return f"{ts}.{sig}"


def _verify_token(token: str) -> bool:
    """Verify a session token's signature and expiry."""
    try:
        ts_str, sig = token.split(".", 1)
        if not hmac.compare_digest(sig, _sign(ts_str)):
            return False
        ts = int(ts_str)
        if time.time() - ts > _COOKIE_MAX_AGE:
            return False
        return True
    except (ValueError, AttributeError):
        return False


def is_authenticated(request: Request) -> bool:
    """Check if the request has a valid session cookie."""
    if not settings.app_password:
        return True  # no password configured = open access
    token = request.cookies.get(_COOKIE_NAME)
    if not token:
        return False
    return _verify_token(token)


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
async def login(body: LoginRequest, response: Response):
    if not settings.app_password:
        return {"ok": True}
    if not hmac.compare_digest(body.password, settings.app_password):
        logger.warning("Failed login attempt")
        response.status_code = 401
        return {"detail": "Wrong password"}
    token = _make_token()
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,  # allow HTTP locally; nginx handles HTTPS remotely
    )
    return {"ok": True}


@router.get("/check")
async def check_auth(request: Request):
    return {"authenticated": is_authenticated(request)}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key=_COOKIE_NAME)
    return {"ok": True}
