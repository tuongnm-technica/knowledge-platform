"""
apps/api/routes/auth.py
Login and refresh token endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.dependencies import CurrentUser, get_current_user
from apps.api.auth.jwt_handler import create_access_token, create_refresh_token, decode_token
from storage.db.db import get_db

try:
    import bcrypt
except ImportError:  # pragma: no cover - runtime safeguard
    bcrypt = None


router = APIRouter(prefix="/auth", tags=["auth"])


def _verify_password(plain_text: str, password_hash: str | None) -> bool:
    if bcrypt is None or not password_hash:
        return False
    try:
        return bcrypt.checkpw(plain_text.encode(), password_hash.encode())
    except ValueError:
        return False


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    is_admin: bool


class RefreshRequest(BaseModel):
    refresh_token: str


class MeResponse(BaseModel):
    user_id: str
    email: str
    display_name: str | None
    is_admin: bool


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
            SELECT id, email, display_name, password_hash, is_active, is_admin
            FROM users
            WHERE email = :email
        """),
        {"email": req.email},
    )
    row = result.mappings().first()

    if not row or not row["is_active"] or not _verify_password(req.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoac mat khau khong dung",
        )

    access_token = create_access_token(row["id"], row["email"], row["is_admin"])
    refresh_token = create_refresh_token(row["id"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=row["id"],
        email=row["email"],
        is_admin=row["is_admin"],
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(req.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token khong phai refresh token",
        )

    result = await db.execute(
        text("SELECT id, email, is_active, is_admin FROM users WHERE id = :id"),
        {"id": payload["sub"]},
    )
    row = result.mappings().first()

    if not row or not row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tai khoan khong hop le",
        )

    access_token = create_access_token(row["id"], row["email"], row["is_admin"])
    refresh_token = create_refresh_token(row["id"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=row["id"],
        email=row["email"],
        is_admin=row["is_admin"],
    )


@router.get("/me", response_model=MeResponse)
async def me(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text("SELECT id, email, display_name, is_admin FROM users WHERE id = :id"),
        {"id": current_user.user_id},
    )
    row = result.mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="User khong ton tai")

    return MeResponse(
        user_id=row["id"],
        email=row["email"],
        display_name=row["display_name"],
        is_admin=row["is_admin"],
    )
