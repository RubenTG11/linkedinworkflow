"""Admin authentication (password-based)."""
import hashlib
import secrets
from fastapi import Request, HTTPException

from src.config import settings

# Authentication
WEB_PASSWORD = settings.web_password
SESSION_SECRET = settings.session_secret or secrets.token_hex(32)
AUTH_COOKIE_NAME = "linkedin_admin_auth"


def hash_password(password: str) -> str:
    """Hash password with session secret."""
    return hashlib.sha256(f"{password}{SESSION_SECRET}".encode()).hexdigest()


def verify_auth(request: Request) -> bool:
    """Check if request is authenticated for admin."""
    if not WEB_PASSWORD:
        return True  # No password set, allow access
    cookie = request.cookies.get(AUTH_COOKIE_NAME)
    if not cookie:
        return False
    return cookie == hash_password(WEB_PASSWORD)


async def require_auth(request: Request):
    """Dependency to require admin authentication."""
    if not verify_auth(request):
        raise HTTPException(status_code=302, headers={"Location": "/admin/login"})
