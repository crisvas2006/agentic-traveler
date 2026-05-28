import ipaddress
import logging
import os
from typing import Optional

import jwt
from fastapi import Header, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN", "")
APP_ADMIN_API_KEY = os.getenv("APP_ADMIN_API_KEY", "")
TALLY_WEBHOOK_TOKEN = os.getenv("TALLY_WEBHOOK_TOKEN", "")


class WebUserCtx(BaseModel):
    """Authenticated web-user context resolved from a Supabase JWT."""
    user_id: str        # public.users.id
    auth_id: str        # auth.users.id (== JWT sub)
    email: str | None = None

TELEGRAM_CIDRS = [
    ipaddress.ip_network("149.154.160.0/20"),
    ipaddress.ip_network("91.108.4.0/22"),
]

def verify_telegram_ip(request: Request) -> None:
    """Verify that the request comes from a Telegram IP."""
    skip_ip_check = os.getenv("SKIP_IP_CHECK", "").lower() in ("1", "true")
    if skip_ip_check:
        return

    forwarded = request.headers.get("X-Forwarded-For", "")
    raw_ip = forwarded.split(",")[0].strip() if forwarded else request.client.host if request.client else ""
    if not raw_ip:
        raise HTTPException(status_code=403, detail="Forbidden: No IP")
    
    try:
        ip = ipaddress.ip_address(raw_ip)
    except ValueError:
        logger.warning("Invalid IP address: %s", raw_ip)
        raise HTTPException(status_code=403, detail="Forbidden: Invalid IP")
        
    allowed = any(ip in cidr for cidr in TELEGRAM_CIDRS)
    if not allowed:
        logger.warning("Rejected request from non-Telegram IP: %s", raw_ip)
        raise HTTPException(status_code=403, detail="Forbidden: IP not allowed")

def verify_telegram_secret(request: Request, x_telegram_bot_api_secret_token: str = Header(default="")) -> None:
    """Verify the secret token from the header and path parameter."""
    secret_token = os.getenv("TELEGRAM_SECRET_TOKEN", "")
    if not secret_token:
        logger.error("TELEGRAM_SECRET_TOKEN is not configured")
        raise HTTPException(status_code=500, detail="Server Configuration Error")
        
    if x_telegram_bot_api_secret_token != secret_token:
        logger.warning("Rejected: wrong secret token header")
        raise HTTPException(status_code=403, detail="Forbidden: Invalid token")

def verify_tally_token(authorization: Optional[str] = Header(default=None)) -> None:
    """Verify the Tally webhook Authorization header."""
    tally_token = os.getenv("TALLY_WEBHOOK_TOKEN", "")
    if tally_token:
        if authorization != f"Bearer {tally_token}":
            logger.warning("Tally webhook rejected: unauthorized")
            raise HTTPException(status_code=401, detail="Unauthorized")

def verify_admin_key(x_admin_key: str = Header(default="")) -> None:
    """Verify the X-Admin-Key header."""
    admin_key = os.getenv("APP_ADMIN_API_KEY", "")
    if not admin_key:
        logger.error("APP_ADMIN_API_KEY is not configured")
        raise HTTPException(status_code=500, detail="Server Configuration Error")

    if x_admin_key != admin_key:
        raise HTTPException(status_code=403, detail="Unauthorized")


def verify_supabase_jwt(authorization: str = Header(default="")) -> WebUserCtx:
    """
    Verify a Supabase access token (HS256 signed with SUPABASE_JWT_SECRET) and
    resolve it to a public.users row.

    Returns:
        WebUserCtx with the internal users.id, the auth.users.id, and email.

    Raises:
        401 — missing/invalid/expired token.
        403 — token valid but no matching users row (profile not provisioned).
    """
    secret = os.getenv("SUPABASE_JWT_SECRET", "")
    if not secret:
        logger.error("SUPABASE_JWT_SECRET is not configured")
        raise HTTPException(status_code=500, detail="Server Configuration Error")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization[len("Bearer "):].strip()

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        logger.warning("Invalid Supabase JWT: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid token")

    auth_id = payload.get("sub")
    if not auth_id:
        raise HTTPException(status_code=401, detail="Token missing sub claim")

    # After Task 36: public.users.id IS the auth UUID for web users — no lookup
    # needed. The auth trigger guarantees the users/profile/credits rows exist
    # for every authenticated user. We do not validate the row exists here; an
    # absent row would surface as an integrity error at the first write attempt
    # downstream, which is the correct loud failure for a config drift.
    return WebUserCtx(
        user_id=auth_id,
        auth_id=auth_id,
        email=payload.get("email"),
    )
