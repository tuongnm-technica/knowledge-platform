from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from apps.api.auth.dependencies import CurrentUser, require_admin
from storage.db.db import get_db

router = APIRouter(prefix="/settings", tags=["settings"])

class SMTPSettingsRequest(BaseModel):
    smtp_host: str
    smtp_port: int
    security_mode: str # NONE, SSL, STARTTLS
    authentication_enabled: bool
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    sender_email_address: EmailStr
    sender_display_name: str

class TestMailRequest(BaseModel):
    recipient: EmailStr
    body: str

@router.get("/smtp")
async def get_smtp_settings(
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    row = (
        await session.execute(
            text(
                """
                SELECT smtp_host, smtp_port, security_mode, authentication_enabled, 
                       smtp_username, smtp_password, sender_email_address, sender_display_name
                FROM smtp_settings
                WHERE id = 'default'
                """
            )
        )
    ).mappings().first()
    
    if not row:
        return {}
    
    # Do not expose password in plain text if it exists (send a masked version or empty)
    data = dict(row)
    if data.get("smtp_password"):
        data["smtp_password"] = "********"
        
    return data

@router.post("/smtp")
async def update_smtp_settings(
    req: SMTPSettingsRequest,
    session: AsyncSession = Depends(get_db),
    _: CurrentUser = Depends(require_admin),
):
    # Check if we should keep existing password
    final_password = req.smtp_password
    if final_password == "********":
        # fetch existing to preserve
        row = (await session.execute(text("SELECT smtp_password FROM smtp_settings WHERE id = 'default'"))).mappings().first()
        if row:
            final_password = row["smtp_password"]
            
    await session.execute(
        text(
            """
            INSERT INTO smtp_settings (id, smtp_host, smtp_port, security_mode, authentication_enabled, 
                                     smtp_username, smtp_password, sender_email_address, sender_display_name, updated_at)
            VALUES ('default', :host, :port, :mode, :auth, :user, :pwd, :email, :name, NOW())
            ON CONFLICT (id) DO UPDATE SET
                smtp_host = EXCLUDED.smtp_host,
                smtp_port = EXCLUDED.smtp_port,
                security_mode = EXCLUDED.security_mode,
                authentication_enabled = EXCLUDED.authentication_enabled,
                smtp_username = EXCLUDED.smtp_username,
                smtp_password = EXCLUDED.smtp_password,
                sender_email_address = EXCLUDED.sender_email_address,
                sender_display_name = EXCLUDED.sender_display_name,
                updated_at = NOW()
            """
        ),
        {
            "host": req.smtp_host,
            "port": req.smtp_port,
            "mode": req.security_mode,
            "auth": req.authentication_enabled,
            "user": req.smtp_username,
            "pwd": final_password,
            "email": req.sender_email_address,
            "name": req.sender_display_name,
        }
    )
    await session.commit()
    return {"status": "success"}

@router.post("/smtp/test")
async def test_smtp_settings(
    req: TestMailRequest,
    _: CurrentUser = Depends(require_admin),
):
    # This feature will be functional once we implement `email_service.py`
    # For now it acts as an API stub that returns success.
    # We will expand this once we write `services/email_service.py`
    
    from services.email_service import send_email_async
    try:
        await send_email_async(
            to_email=req.recipient,
            subject="Test Message from Knowledge Platform",
            body=req.body,
        )
        return {"status": "success", "message": "Test email sent successfully."}
    except Exception as e:
        import structlog
        structlog.get_logger().error("smtp.test_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")
