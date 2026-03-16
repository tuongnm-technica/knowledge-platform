"""
apps/api/auth/dependencies.py
FastAPI dependencies — inject current_user vào routes.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from apps.api.auth.jwt_handler import decode_token
from dataclasses import dataclass

bearer = HTTPBearer()


@dataclass
class CurrentUser:
    user_id:  str
    email:    str
    is_admin: bool
    role: str = "member"


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> CurrentUser:
    """Inject vào bất kỳ route nào cần auth"""
    try:
        payload = decode_token(credentials.credentials)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CurrentUser(
        user_id  = payload["sub"],
        email    = payload["email"],
        is_admin = payload.get("is_admin", False),
        role     = payload.get("role", "member") or "member",
    )


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Chỉ admin mới được dùng — inject vào routes nhạy cảm như /ingest"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ admin mới có quyền thực hiện thao tác này",
        )
    return current_user


def require_task_manager(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """
    PM/Team lead actions (review/edit/confirm/submit tasks).
    Admin is always allowed.
    """
    if current_user.is_admin:
        return current_user
    role = (current_user.role or "member").lower()
    if role not in {"pm", "team_lead", "lead"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ban khong co quyen thuc hien thao tac nay (PM/Team Lead required)",
        )
    return current_user


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
) -> CurrentUser | None:
    """Optional auth — dùng cho endpoints public nhưng muốn biết user là ai"""
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        return CurrentUser(
            user_id  = payload["sub"],
            email    = payload["email"],
            is_admin = payload.get("is_admin", False),
        )
    except ValueError:
        return None
