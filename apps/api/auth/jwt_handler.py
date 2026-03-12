"""
apps/api/auth/jwt_handler.py
Tạo và verify JWT token.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from config.settings import settings


def create_access_token(user_id: str, email: str, is_admin: bool) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub":      user_id,
        "email":    email,
        "is_admin": is_admin,
        "exp":      expire,
        "iat":      datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_DAYS)
    payload = {
        "sub":  user_id,
        "type": "refresh",
        "exp":  expire,
        "iat":  datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token đã hết hạn")
    except jwt.InvalidTokenError:
        raise ValueError("Token không hợp lệ")