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
    role: str = "standard"


ROLE_SYSTEM_ADMIN = "system_admin"
ROLE_KNOWLEDGE_ARCHITECT = "knowledge_architect"
ROLE_PM_PO = "pm_po"
ROLE_BA_SA = "ba_sa"
ROLE_DEV_QA = "dev_qa"
ROLE_STANDARD = "standard"

_ROLE_ALIASES: dict[str, str] = {
    "admin": ROLE_SYSTEM_ADMIN,
    "system_admin": ROLE_SYSTEM_ADMIN,
    "sysadmin": ROLE_SYSTEM_ADMIN,
    "knowledge_architect": ROLE_KNOWLEDGE_ARCHITECT,
    "prompt_engineer": ROLE_KNOWLEDGE_ARCHITECT,
    "pm": ROLE_PM_PO,
    "po": ROLE_PM_PO,
    "product_owner": ROLE_PM_PO,
    "project_manager": ROLE_PM_PO,
    "team_lead": ROLE_PM_PO,
    "lead": ROLE_PM_PO,
    "ba": ROLE_BA_SA,
    "sa": ROLE_BA_SA,
    "business_analyst": ROLE_BA_SA,
    "system_analyst": ROLE_BA_SA,
    "dev": ROLE_DEV_QA,
    "developer": ROLE_DEV_QA,
    "qa": ROLE_DEV_QA,
    "qa_engineer": ROLE_DEV_QA,
    "member": ROLE_STANDARD,
    "standard": ROLE_STANDARD,
}


def normalize_role(role: str | None, *, is_admin: bool = False) -> str:
    raw = (role or "").strip().lower()
    if not raw:
        return ROLE_SYSTEM_ADMIN if is_admin else ROLE_STANDARD
    return _ROLE_ALIASES.get(raw, raw)


def has_role(current_user: CurrentUser, allowed: set[str]) -> bool:
    if current_user.is_admin:
        return True
    role = normalize_role(current_user.role, is_admin=current_user.is_admin)
    return role in allowed


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
    raw_is_admin = bool(payload.get("is_admin", False))
    role = normalize_role(payload.get("role", ROLE_STANDARD) or ROLE_STANDARD, is_admin=raw_is_admin)
    effective_admin = raw_is_admin or role == ROLE_SYSTEM_ADMIN
    return CurrentUser(
        user_id=payload["sub"],
        email=payload["email"],
        is_admin=effective_admin,
        role=role,
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
    role = normalize_role(current_user.role, is_admin=current_user.is_admin)
    if role not in {ROLE_PM_PO}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ban khong co quyen thuc hien thao tac nay (PM/PO required)",
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
        raw_is_admin = bool(payload.get("is_admin", False))
        role = normalize_role(payload.get("role", ROLE_STANDARD) or ROLE_STANDARD, is_admin=raw_is_admin)
        effective_admin = raw_is_admin or role == ROLE_SYSTEM_ADMIN
        return CurrentUser(
            user_id  = payload["sub"],
            email    = payload["email"],
            is_admin = effective_admin,
            role     = role,
        )
    except ValueError:
        return None
