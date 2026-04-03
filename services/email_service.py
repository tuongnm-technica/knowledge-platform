import aiosmtplib
from email.message import EmailMessage
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from storage.db.db import AsyncSessionLocal

log = structlog.get_logger()

async def get_smtp_config() -> dict | None:
    """Fetch SMTP configuration from the database."""
    try:
        async with AsyncSessionLocal() as session:
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
                return None
            return dict(row)
    except Exception as e:
        log.error("email_service.get_config_error", error=str(e))
        return None

async def send_email_async(
    to_email: str | list[str],
    subject: str,
    body: str,
    is_html: bool = False,
    attachment_paths: list[str] | None = None
) -> bool:
    """
    Sends an email using the system's SMTP configuration asynchronously.
    """
    config = await get_smtp_config()
    if not config:
        log.warning("email_service.no_config", msg="Cannot send email, SMTP config not found in database.")
        return False
        
    host = config.get("smtp_host")
    port = config.get("smtp_port")
    
    if not host or not port:
        log.error("email_service.invalid_config", msg="SMTP Host or Port is empty.")
        return False

    sender_email = config.get("sender_email_address")
    sender_name = config.get("sender_display_name", "Knowledge Platform")
    
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = f"{sender_name} <{sender_email}>"
    
    if isinstance(to_email, list):
        msg['To'] = ", ".join(to_email)
    else:
        msg['To'] = to_email

    if is_html:
        # Fallback text inside the HTML message object
        msg.set_content(body) 
        msg.add_alternative(body, subtype='html')
    else:
        msg.set_content(body)

    # Handle attachments
    if attachment_paths:
        import mimetypes
        from pathlib import Path
        for path_str in attachment_paths:
            path = Path(path_str)
            if not path.exists():
                log.warning("email_service.attachment_not_found", path=path_str)
                continue
            
            ctype, encoding = mimetypes.guess_type(str(path))
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)
            
            with open(path, 'rb') as f:
                msg.add_attachment(
                    f.read(),
                    maintype=maintype,
                    subtype=subtype,
                    filename=path.name
                )
            log.info("email_service.attachment_added", file=path.name)

    mode = config.get("security_mode")
    use_tls = (mode == "SSL")
    start_tls = (mode == "STARTTLS")
    
    auth_enabled = config.get("authentication_enabled")
    username = config.get("smtp_username") if auth_enabled else None
    password = config.get("smtp_password") if auth_enabled else None
    
    try:
        log.info("email_service.sending", to=msg['To'], subject=subject, host=host, port=port)
        await aiosmtplib.send(
            msg,
            hostname=host,
            port=port,
            use_tls=use_tls,
            start_tls=start_tls,
            username=username,
            password=password,
            timeout=10.0
        )
        log.info("email_service.sent_success", to=msg['To'])
        return True
    except aiosmtplib.SMTPException as smtpe:
        log.error("email_service.smtp_error", error=str(smtpe))
        raise
    except Exception as e:
        log.error("email_service.unexpected_error", error=str(e))
        raise
