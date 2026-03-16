"""
apps/api/auth/jwt_handler.py
Create and verify JWT tokens.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from config.settings import settings

try:
    import jwt
except ImportError:  # pragma: no cover - runtime safeguard
    jwt = None


def _require_jwt() -> None:
    if jwt is None:
        raise ValueError("Missing PyJWT dependency. Reinstall requirements.txt.")


def create_access_token(user_id: str, email: str, is_admin: bool, role: str = "member") -> str:
    _require_jwt()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "is_admin": is_admin,
        "role": role or "member",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def create_refresh_token(user_id: str) -> str:
    _require_jwt()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_DAYS)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    _require_jwt()
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token da het han")
    except jwt.InvalidTokenError:
        raise ValueError("Token khong hop le")
