import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.dependencies import (
    CurrentUser,
    ROLE_BA_SA,
    ROLE_DEV_QA,
    ROLE_KNOWLEDGE_ARCHITECT,
    ROLE_PM_PO,
    ROLE_STANDARD,
    ROLE_SYSTEM_ADMIN,
    normalize_role,
    require_admin,
)
from storage.db.db import get_db
from .groups import GroupOverrideRequest, validate_group_ids as _validate_group_ids

try:
    import bcrypt
except ImportError:  # pragma: no cover - runtime safeguard
    bcrypt = None


router = APIRouter(prefix="/users", tags=["users"])


_ALLOWED_ROLES: set[str] = {
    ROLE_SYSTEM_ADMIN,
    ROLE_KNOWLEDGE_ARCHITECT,
    ROLE_PM_PO,
    ROLE_BA_SA,
    ROLE_DEV_QA,
    ROLE_STANDARD,
}


def _normalize_role(role: str | None, *, strict: bool) -> str:
    normalized = normalize_role(role or ROLE_STANDARD, is_admin=False)
    if normalized not in _ALLOWED_ROLES:
        if not strict:
            return ROLE_STANDARD
        allowed = ", ".join(sorted(_ALLOWED_ROLES))
        raise HTTPException(status_code=400, detail=f"Role khong hop le: {normalized}. Allowed: {allowed}")
    return normalized


class UserCreateRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    is_active: bool = True
    is_admin: bool = False
    role: str = Field(default=ROLE_STANDARD, max_length=50)
    group_ids: list[str] = Field(default_factory=list)


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_active: bool | None = None
    is_admin: bool | None = None
    role: str | None = Field(default=None, max_length=50)
    group_ids: list[str] | None = None


class DocumentOverrideRequest(BaseModel):
    document_id: str = Field(..., min_length=1, max_length=64)
    reason: str | None = Field(default=None, max_length=2000)


@router.get("")
async def list_users_admin(
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    users_result = await db.execute(
        text("""
            SELECT
                u.id,
                u.email,
                u.display_name,
                u.is_active,
                u.is_admin,
                COALESCE(u.role, 'standard') AS role,
                COALESCE(
                    JSON_AGG(
                        JSON_BUILD_OBJECT('id', g.id, 'name', g.name)
                        ORDER BY g.name
                    ) FILTER (WHERE g.id IS NOT NULL),
                    '[]'::json
                ) AS groups
                ,
                COALESCE(
                    (
                        SELECT JSON_AGG(JSON_BUILD_OBJECT('id', g2.id, 'name', g2.name) ORDER BY g2.name)
                        FROM user_group_overrides ugo
                        JOIN groups g2 ON g2.id = ugo.group_id
                        WHERE ugo.user_id = u.id
                          AND COALESCE(ugo.effect, 'deny') = 'deny'
                    ),
                    '[]'::json
                ) AS group_overrides
            FROM users u
            LEFT JOIN user_groups ug ON ug.user_id = u.id
            LEFT JOIN groups g ON g.id = ug.group_id
            GROUP BY u.id, u.email, u.display_name, u.is_active, u.is_admin
            ORDER BY u.display_name NULLS LAST, u.email
        """)
    )
    users = []
    for row in users_result.mappings().all():
        groups = list(row["groups"] or [])
        group_overrides = list(row.get("group_overrides") or [])
        role = _normalize_role(row.get("role") or ROLE_STANDARD, strict=False)
        # Backward compatible: admin flag implies system_admin.
        if bool(row["is_admin"]) and role != ROLE_SYSTEM_ADMIN:
            role = ROLE_SYSTEM_ADMIN
        users.append(
            {
                "id": row["id"],
                "email": row["email"],
                "display_name": row["display_name"] or row["email"],
                "is_active": row["is_active"],
                "is_admin": bool(row["is_admin"]) or role == ROLE_SYSTEM_ADMIN,
                "role": role,
                "groups": groups,
                "group_ids": [group["id"] for group in groups],
                "group_overrides": group_overrides,
                "group_override_ids": [group["id"] for group in group_overrides],
            }
        )

    groups_result = await db.execute(
        text("""
            SELECT
                g.id,
                g.name,
                COUNT(DISTINCT ug.user_id) AS member_count,
                COALESCE(
                    JSON_AGG(
                        JSON_BUILD_OBJECT(
                            'id', u.id,
                            'email', u.email,
                            'display_name', u.display_name
                        )
                        ORDER BY u.display_name, u.email
                    ) FILTER (WHERE u.id IS NOT NULL),
                    '[]'::json
                ) AS members
            FROM groups g
            LEFT JOIN user_groups ug ON ug.group_id = g.id
            LEFT JOIN users u ON u.id = ug.user_id
            GROUP BY g.id, g.name
            ORDER BY g.name
        """)
    )
    groups = [
        {
            "id": row["id"],
            "name": row["name"],
            "member_count": row["member_count"],
            "members": list(row["members"] or []),
        }
        for row in groups_result.mappings().all()
    ]

    return {"users": users, "groups": groups}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user_admin(
    req: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    _require_bcrypt()
    group_ids = await _validate_group_ids(db, req.group_ids)
    existing = await db.execute(
        text("SELECT 1 FROM users WHERE email = :email"),
        {"email": req.email},
    )
    if existing.first():
        raise HTTPException(status_code=409, detail="Email da ton tai")

    user_id = _make_user_id(req.email)
    password_hash = _hash_password(req.password)

    role = _normalize_role(req.role or ROLE_STANDARD, strict=True)
    if bool(req.is_admin):
        role = ROLE_SYSTEM_ADMIN
    is_admin = role == ROLE_SYSTEM_ADMIN

    await db.execute(
        text(
            """
            INSERT INTO users (id, email, display_name, password_hash, is_active, is_admin, role)
            VALUES (:id, :email, :display_name, :password_hash, :is_active, :is_admin, :role)
            """
        ),
        {
            "id": user_id,
            "email": req.email,
            "display_name": req.display_name.strip(),
            "password_hash": password_hash,
            "is_active": req.is_active,
            "is_admin": is_admin,
            "role": role,
        },
    )
    await _replace_user_groups(db, user_id, group_ids)
    await db.commit()
    return {"status": "created", "user_id": user_id}


@router.patch("/{user_id}")
async def update_user_admin(
    user_id: str,
    req: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    result = await db.execute(
        text("SELECT id, email, is_admin, COALESCE(role, 'standard') AS role FROM users WHERE id = :id"),
        {"id": user_id},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="User khong ton tai")

    updates: list[str] = []
    params: dict[str, object] = {"id": user_id}

    if req.email is not None:
        duplicate = await db.execute(
            text("SELECT 1 FROM users WHERE email = :email AND id != :id"),
            {"email": req.email, "id": user_id},
        )
        if duplicate.first():
            raise HTTPException(status_code=409, detail="Email da ton tai")
        updates.append("email = :email")
        params["email"] = req.email

    if req.display_name is not None:
        updates.append("display_name = :display_name")
        params["display_name"] = req.display_name.strip()

    if req.password is not None:
        _require_bcrypt()
        updates.append("password_hash = :password_hash")
        params["password_hash"] = _hash_password(req.password)

    if req.is_active is not None:
        if current_user.user_id == user_id and not req.is_active:
            raise HTTPException(status_code=400, detail="Khong the tu khoa tai khoan cua chinh minh")
        updates.append("is_active = :is_active")
        params["is_active"] = req.is_active

    next_role: str | None = None
    if req.role is not None:
        next_role = _normalize_role(req.role, strict=True)
        if req.is_admin is True:
            next_role = ROLE_SYSTEM_ADMIN
        if current_user.user_id == user_id and next_role != ROLE_SYSTEM_ADMIN:
            raise HTTPException(status_code=400, detail="Khong the tu ha quyen admin cua chinh minh")
    elif req.is_admin is not None:
        if current_user.user_id == user_id and not req.is_admin:
            raise HTTPException(status_code=400, detail="Khong the tu ha quyen admin cua chinh minh")
        next_role = ROLE_SYSTEM_ADMIN if req.is_admin else ROLE_STANDARD

    if next_role is not None:
        updates.append("role = :role")
        params["role"] = next_role
        updates.append("is_admin = :is_admin")
        params["is_admin"] = (next_role == ROLE_SYSTEM_ADMIN)

    if updates:
        await db.execute(
            text(f"UPDATE users SET {', '.join(updates)} WHERE id = :id"),
            params,
        )

    if req.group_ids is not None:
        group_ids = await _validate_group_ids(db, req.group_ids)
        previous = await _get_user_group_ids(db, user_id)
        next_ids = set(group_ids)
        removed = sorted(previous - next_ids)
        added = sorted(next_ids - previous)
        if removed or added:
            await _apply_user_group_overrides(db, user_id, removed, added, current_user.user_id)
        await _replace_user_groups(db, user_id, group_ids)

    await db.commit()
    return {"status": "updated", "user_id": user_id}

@router.delete("/{user_id}")
async def delete_user_admin(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    result = await db.execute(
        text("DELETE FROM users WHERE id = :id"),
        {"id": user_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="User khong ton tai")
    await db.commit()
    return {"status": "deleted", "user_id": user_id}

@router.get("/{user_id}/overrides")
async def list_user_overrides_admin(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    exists = await db.execute(text("SELECT 1 FROM users WHERE id = :id"), {"id": user_id})
    if not exists.first():
        raise HTTPException(status_code=404, detail="User khong ton tai")

    group_rows = await db.execute(
        text("""
            SELECT
                ugo.group_id,
                COALESCE(g.name, ugo.group_id) AS group_name,
                ugo.effect,
                ugo.reason,
                ugo.created_by,
                ugo.created_at,
                ugo.updated_at
            FROM user_group_overrides ugo
            LEFT JOIN groups g ON g.id = ugo.group_id
            WHERE ugo.user_id = :user_id
            ORDER BY COALESCE(g.name, ugo.group_id)
        """),
        {"user_id": user_id},
    )
    doc_rows = await db.execute(
        text("""
            SELECT
                udo.document_id::text AS document_id,
                COALESCE(d.title, udo.document_id::text) AS document_title,
                udo.effect,
                udo.reason,
                udo.created_by,
                udo.created_at,
                udo.updated_at
            FROM user_document_overrides udo
            LEFT JOIN documents d ON d.id = udo.document_id
            WHERE udo.user_id = :user_id
            ORDER BY udo.updated_at DESC NULLS LAST
        """),
        {"user_id": user_id},
    )
    return {
        "user_id": user_id,
        "group_overrides": [dict(row) for row in group_rows.mappings().all()],
        "document_overrides": [dict(row) for row in doc_rows.mappings().all()],
    }


@router.post("/{user_id}/overrides/groups")
async def deny_user_group_admin(
    user_id: str,
    req: GroupOverrideRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    exists = await db.execute(text("SELECT 1 FROM users WHERE id = :id"), {"id": user_id})
    if not exists.first():
        raise HTTPException(status_code=404, detail="User khong ton tai")
    group_ids = await _validate_group_ids(db, [req.group_id])
    group_id = group_ids[0]

    await db.execute(
        text("""
            INSERT INTO user_group_overrides (user_id, group_id, effect, reason, created_by, created_at, updated_at)
            VALUES (:user_id, :group_id, 'deny', :reason, :created_by, NOW(), NOW())
            ON CONFLICT (user_id, group_id)
            DO UPDATE SET effect = 'deny', reason = EXCLUDED.reason, updated_at = NOW(), created_by = EXCLUDED.created_by
        """),
        {
            "user_id": user_id,
            "group_id": group_id,
            "reason": (req.reason or "").strip() or None,
            "created_by": current_user.user_id,
        },
    )
    # Ensure effective access matches the override immediately.
    await db.execute(
        text("DELETE FROM user_groups WHERE user_id = :user_id AND group_id = :group_id"),
        {"user_id": user_id, "group_id": group_id},
    )
    await db.commit()
    return {"status": "denied", "user_id": user_id, "group_id": group_id}


@router.delete("/{user_id}/overrides/groups/{group_id}")
async def remove_user_group_override_admin(
    user_id: str,
    group_id: str,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    exists = await db.execute(text("SELECT 1 FROM users WHERE id = :id"), {"id": user_id})
    if not exists.first():
        raise HTTPException(status_code=404, detail="User khong ton tai")
    result = await db.execute(
        text("""
            DELETE FROM user_group_overrides
            WHERE user_id = :user_id AND group_id = :group_id
        """),
        {"user_id": user_id, "group_id": group_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Override khong ton tai")
    await db.commit()
    return {"status": "removed", "user_id": user_id, "group_id": group_id}


@router.post("/{user_id}/overrides/documents")
async def deny_user_document_admin(
    user_id: str,
    req: DocumentOverrideRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    exists = await db.execute(text("SELECT 1 FROM users WHERE id = :id"), {"id": user_id})
    if not exists.first():
        raise HTTPException(status_code=404, detail="User khong ton tai")

    doc_id = req.document_id.strip()
    try:
        uuid.UUID(doc_id)
    except Exception:
        raise HTTPException(status_code=400, detail="document_id khong hop le (UUID)")

    # Missing documents can still be overridden preemptively (e.g. before ingestion finishes).
    await db.execute(
        text("""
            INSERT INTO user_document_overrides (user_id, document_id, effect, reason, created_by, created_at, updated_at)
            VALUES (:user_id, :document_id::uuid, 'deny', :reason, :created_by, NOW(), NOW())
            ON CONFLICT (user_id, document_id)
            DO UPDATE SET effect = 'deny', reason = EXCLUDED.reason, updated_at = NOW(), created_by = EXCLUDED.created_by
        """),
        {
            "user_id": user_id,
            "document_id": doc_id,
            "reason": (req.reason or "").strip() or None,
            "created_by": current_user.user_id,
        },
    )
    await db.commit()
    return {"status": "denied", "user_id": user_id, "document_id": doc_id}


@router.delete("/{user_id}/overrides/documents/{document_id}")
async def remove_user_document_override_admin(
    user_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    exists = await db.execute(text("SELECT 1 FROM users WHERE id = :id"), {"id": user_id})
    if not exists.first():
        raise HTTPException(status_code=404, detail="User khong ton tai")
    doc_id = document_id.strip()
    try:
        uuid.UUID(doc_id)
    except Exception:
        raise HTTPException(status_code=400, detail="document_id khong hop le (UUID)")

    result = await db.execute(
        text("""
            DELETE FROM user_document_overrides
            WHERE user_id = :user_id AND document_id = :document_id::uuid
        """),
        {"user_id": user_id, "document_id": doc_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Override khong ton tai")
    await db.commit()
    return {"status": "removed", "user_id": user_id, "document_id": doc_id}



async def _replace_user_groups(db: AsyncSession, user_id: str, group_ids: list[str]) -> None:
    await db.execute(
        text("DELETE FROM user_groups WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    for group_id in group_ids:
        await db.execute(
            text("""
                INSERT INTO user_groups (user_id, group_id)
                VALUES (:user_id, :group_id)
                ON CONFLICT DO NOTHING
            """),
            {"user_id": user_id, "group_id": group_id},
        )


async def _get_user_group_ids(db: AsyncSession, user_id: str) -> set[str]:
    result = await db.execute(
        text("SELECT group_id FROM user_groups WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    return {row[0] for row in result.fetchall()}


async def _apply_user_group_overrides(
    db: AsyncSession,
    user_id: str,
    removed_group_ids: list[str],
    added_group_ids: list[str],
    created_by: str,
) -> None:
    for group_id in removed_group_ids:
        await db.execute(
            text("""
                INSERT INTO user_group_overrides (user_id, group_id, effect, created_by, created_at, updated_at)
                VALUES (:user_id, :group_id, 'deny', :created_by, NOW(), NOW())
                ON CONFLICT (user_id, group_id)
                DO UPDATE SET effect = 'deny', updated_at = NOW(), created_by = EXCLUDED.created_by
            """),
            {"user_id": user_id, "group_id": group_id, "created_by": created_by},
        )

    if added_group_ids:
        await db.execute(
            text("""
                DELETE FROM user_group_overrides
                WHERE user_id = :user_id
                  AND group_id = ANY(:group_ids)
            """),
            {"user_id": user_id, "group_ids": added_group_ids},
        )


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _require_bcrypt() -> None:
    if bcrypt is None:
        raise HTTPException(status_code=503, detail="bcrypt chua san sang tren server")


def _make_user_id(email: str) -> str:
    local = email.split("@", 1)[0].lower()
    slug = re.sub(r"[^a-z0-9]+", "_", local).strip("_") or "user"
    return f"user_{slug}_{uuid.uuid4().hex[:6]}"
