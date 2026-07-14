"""
InstantRisk V3 - Email Integration Service

OAuth 2.0 (Gmail + Microsoft Graph) and IMAP app-password email ingestion.
"""
import base64, hashlib, imaplib, json, logging, os, re, secrets, ssl, uuid, asyncio, smtplib
from datetime import datetime, timezone, timedelta
from email import message as email_lib
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.email_integration import AuthMethod, ConnectionStatus, EmailConnection, EmailIngestionEvent, EmailProvider
from app.services.email_bot import EmailBotService, ParsedSubmission

logger = logging.getLogger("email_integration")

_fernet: Optional[Fernet] = None

def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = settings.resolved_email_encryption_key
        if not key:
            raise RuntimeError("EMAIL_TOKEN_ENCRYPTION_KEY is not set and SECRET_KEY must be >= 32 chars")
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet

def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    return _get_fernet().encrypt(value.encode()).decode()

def decrypt_secret(encrypted: str) -> Optional[str]:
    if not encrypted:
        return None
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken:
        logger.warning("Fernet decryption failed")
        return None

_redis_client: Optional[Any] = None

async def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis.asyncio as redis
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=False)
    return _redis_client

# ===== OAuth Helpers =====

def _build_google_oauth_url(state: str, code_verifier: str, redirect_uri: str) -> str:
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile https://www.googleapis.com/auth/gmail.readonly",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

def _build_microsoft_oauth_url(state: str, code_verifier: str, redirect_uri: str) -> str:
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
    params = {
        "client_id": settings.MICROSOFT_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile offline_access https://graph.microsoft.com/Mail.Read",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?{urlencode(params)}"

async def _exchange_google_code(code: str, code_verifier: str, redirect_uri: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            },
        )
        resp.raise_for_status()
        return resp.json()

async def _exchange_microsoft_code(code: str, code_verifier: str, redirect_uri: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "code": code,
                "client_id": settings.MICROSOFT_CLIENT_ID,
                "client_secret": settings.MICROSOFT_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            },
        )
        resp.raise_for_status()
        return resp.json()

async def _refresh_google_token(refresh_token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "refresh_token": refresh_token,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()

async def _refresh_microsoft_token(refresh_token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "refresh_token": refresh_token,
                "client_id": settings.MICROSOFT_CLIENT_ID,
                "client_secret": settings.MICROSOFT_CLIENT_SECRET,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()

async def _fetch_google_profile(access_token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()

async def _fetch_microsoft_profile(access_token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()

# ===== IMAP Helpers =====

ALLOWED_IMAP_HOSTS = {
    EmailProvider.GMAIL: ("imap.gmail.com", 993),
    EmailProvider.OUTLOOK: ("outlook.office365.com", 993),
}

async def _test_imap_connection(provider: EmailProvider, email_address: str, app_password: str) -> Tuple[bool, str]:
    expected_host, expected_port = ALLOWED_IMAP_HOSTS.get(provider, (None, None))
    if expected_host is None:
        return False, f"Unknown provider: {provider}"
    try:
        context = ssl.create_default_context()
        mail = imaplib.IMAP4_SSL(host=expected_host, port=expected_port, ssl_context=context)
        mail.login(email_address, app_password)
        mail.logout()
        return True, ""
    except imaplib.IMAP4.error as e:
        return False, f"IMAP auth failed: {str(e)[:100]}"
    except Exception as e:
        return False, f"IMAP connection error: {str(e)[:100]}"

def _decode_header_value(value: str) -> str:
    if not value:
        return ""
    try:
        parts = decode_header(value)
        result = []
        for part, enc in parts:
            if isinstance(part, bytes):
                result.append(part.decode(enc or "utf-8", errors="replace"))
            else:
                result.append(str(part))
        return "".join(result)
    except Exception:
        return value

def _extract_email_body(msg) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="replace")
                    break
                except Exception:
                    pass
    else:
        try:
            charset = msg.get_content_charset() or "utf-8"
            body = msg.get_payload(decode=True).decode(charset, errors="replace")
        except Exception:
            body = str(msg.get_payload())
    return body

def _extract_attachments(msg) -> List[Dict[str, Any]]:
    """Extract attachments from an email message.

    Returns a list of dicts with keys: filename, mime_type, bytes.
    Decodes the raw payload inline based on content-transfer-encoding.
    """
    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            cd = part.get("Content-Disposition", "")
            if "attachment" in cd:
                filename = _decode_header_value(part.get_filename("attachment") or "unknown")
                if filename and filename != "attachment":
                    raw_payload = part.get_payload(decode=False)
                    decoded_bytes: Optional[bytes] = None
                    cte = (part.get("Content-Transfer-Encoding") or "").strip().lower()
                    if cte == "base64" and isinstance(raw_payload, str):
                        try:
                            decoded_bytes = base64.b64decode(raw_payload)
                        except Exception:
                            decoded_bytes = None
                    elif cte == "quoted-printable" and isinstance(raw_payload, str):
                        try:
                            charset = part.get_content_charset() or "utf-8"
                            decoded_bytes = part.get_payload(decode=True)
                            if decoded_bytes is None:
                                decoded_bytes = raw_payload.encode(charset, errors="replace")
                        except Exception:
                            decoded_bytes = None
                    elif isinstance(raw_payload, bytes):
                        decoded_bytes = raw_payload
                    elif isinstance(raw_payload, str):
                        decoded_bytes = raw_payload.encode("latin-1", errors="replace")

                    if decoded_bytes:
                        attachments.append({
                            "filename": filename,
                            "mime_type": part.get_content_type() or "application/octet-stream",
                            "bytes": decoded_bytes,
                        })
    return attachments

def _parse_email_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

async def _fetch_imap_unread(connection: EmailConnection) -> Tuple[List[Dict[str, Any]], Dict[str, bytes]]:
    """Fetch unread messages from IMAP.

    Returns (messages, raw_messages) where raw_messages is a dict keyed by dedupe_key
    containing the raw RFC822 bytes for each message.
    Uses BODY.PEEK[] so messages are NOT marked as read on fetch.
    UID is extracted via 'UID' response tag, not the message Sequence-number.
    """
    decrypted = decrypt_secret(connection._encrypted_app_password or "")
    if not decrypted:
        return [], {}

    host = connection.imap_host or ALLOWED_IMAP_HOSTS.get(connection.provider, ("", 993))[0]
    port = connection.imap_port or 993

    messages: List[Dict[str, Any]] = []
    raw_messages: Dict[str, bytes] = {}

    try:
        context = ssl.create_default_context()
        mail = imaplib.IMAP4_SSL(host=host, port=port, ssl_context=context)
        mail.login(connection.email_address, decrypted)

        status, _ = mail.select("INBOX")
        if status != "OK":
            mail.logout()
            return [], {}

        status, msg_nums = mail.search(None, "UNSEEN")
        if status != "OK" or not msg_nums[0]:
            mail.logout()
            return [], {}

        status_uidv, uidv_data = mail.response("UIDVALIDITY")
        raw_uidvalidity = uidv_data[0] if status_uidv == "OK" else b"0"
        uidvalidity = (
            raw_uidvalidity.decode(errors="replace")
            if isinstance(raw_uidvalidity, bytes)
            else str(raw_uidvalidity)
        )

        for num in msg_nums[0].split():
            try:
                # BODY.PEEK[] avoids marking the message as SEEN.
                _, data = mail.fetch(num, "(UID BODY.PEEK[])")
                response_item = data[0]
                response_meta = response_item[0] if isinstance(response_item, tuple) else response_item
                raw = response_item[1] if isinstance(response_item, tuple) else response_item
                msg = email_lib.message_from_bytes(raw)

                uid_match = re.search(rb"UID (\d+)", response_meta if isinstance(response_meta, bytes) else b"")
                uid = uid_match.group(1).decode() if uid_match else num.decode()
                dedupe_key = f"{uidvalidity}:{uid}"

                subject = _decode_header_value(msg.get("Subject", ""))
                sender = _decode_header_value(msg.get("From", ""))
                message_id = msg.get("Message-ID", "")
                date_str = msg.get("Date", "")
                body = _extract_email_body(msg)

                # Extract attachments — now includes raw bytes decoded inline
                attachment_list = _extract_attachments(msg)

                # Store raw RFC822 bytes keyed by dedupe_key for later ingestion
                raw_messages[dedupe_key] = raw

                messages.append({
                    "dedupe_key": dedupe_key,
                    "message_id": message_id,
                    "subject": subject,
                    "sender": sender,
                    "body": body[:5000],
                    "received_at": _parse_email_date(date_str),
                    "attachments": attachment_list,
                })
            except Exception as e:
                logger.debug(f"Error fetching IMAP message {num}: {e}")

        mail.logout()
    except Exception as e:
        logger.error(f"IMAP fetch failed for {connection.email_address}: {e}")

    return messages, raw_messages

# ===== Gmail/Outlook REST Fetching =====

async def _fetch_gmail_messages(access_token: str) -> List[Dict[str, Any]]:
    messages = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"q": "is:unread", "maxResults": 50},
            )
            if resp.status_code == 401:
                return []
            resp.raise_for_status()
            data = resp.json()

            for msg_ref in data.get("messages", []):
                try:
                    msg_resp = await client.get(
                        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_ref['id']}",
                        headers={"Authorization": f"Bearer {access_token}"},
                        params={"format": "full"},
                    )
                    if msg_resp.status_code != 200:
                        continue
                    msg_data = msg_resp.json()
                    payload = msg_data.get("payload", {})
                    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

                    body = _extract_gmail_body(payload)
                    attachments = _extract_gmail_attachments(payload)

                    messages.append({
                        "dedupe_key": msg_ref["id"],
                        "message_id": headers.get("message-id", msg_ref["id"]),
                        "subject": headers.get("subject", ""),
                        "sender": headers.get("from", ""),
                        "body": body[:5000],
                        "received_at": _parse_email_date(headers.get("date", "")),
                        "attachments": attachments,
                    })
                except Exception as e:
                    logger.debug(f"Error fetching Gmail message {msg_ref['id']}: {e}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Gmail API error: {e.response.status_code}")
    except Exception as e:
        logger.error(f"Gmail fetch failed: {e}")
    return messages

def _extract_gmail_body(payload: Dict[str, Any]) -> str:
    body = ""
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain" and "data" in part.get("body", {}):
                body = base64.urlsafe_b64decode(part["body"]["data"] + "==").decode("utf-8", errors="replace")
                break
            elif part.get("mimeType") == "text/html" and not body:
                body = base64.urlsafe_b64decode(part["body"].get("data", "") + "==").decode("utf-8", errors="replace")
    elif payload.get("mimeType") == "text/plain" and "data" in payload.get("body", {}):
        body = base64.urlsafe_b64decode(payload["body"]["data"] + "==").decode("utf-8", errors="replace")
    return body

def _extract_gmail_attachments(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    attachments = []
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("filename"):
                attachments.append({
                    "filename": part["filename"],
                    "mime_type": part.get("mimeType", "application/octet-stream"),
                    "attachment_id": part["body"].get("attachmentId", ""),
                })
            elif "parts" in part:
                attachments.extend(_extract_gmail_attachments(part))
    return attachments

async def _fetch_outlook_messages(access_token: str) -> List[Dict[str, Any]]:
    messages = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                "https://graph.microsoft.com/v1.0/me/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"$filter": "isRead eq false", "$top": 50,
                        "$select": "id,subject,from,receivedDateTime,body,internetMessageId",
                        "$expand": "attachments($select=id,name,contentType,contentBytes)"},
            )
            if resp.status_code == 401:
                return []
            resp.raise_for_status()
            data = resp.json()

            for msg in data.get("value", []):
                try:
                    sender = msg.get("from", {}).get("emailAddress", {})
                    sender_str = f"{sender.get('name', '')} <{sender.get('address', '')}>"

                    body_content = msg.get("body", {}).get("content", "")[:5000]
                    content_type = msg.get("body", {}).get("contentType", "").lower()
                    # Only strip HTML when contentType is HTML.
                    # Plain-text bodies (contentType == "text") are left as-is.
                    if content_type in ("html", "text/html"):
                        body_content = re.sub(r"<[^>]+>", "", body_content)

                    attachments = []
                    for a in msg.get("attachments", {}).get("value", []):
                        content_bytes = b""
                        raw = a.get("contentBytes", "")
                        if raw:
                            try:
                                content_bytes = base64.b64decode(raw)
                            except Exception:
                                logger.debug("Failed to base64-decode attachment " + str(a.get("name")))
                        attachments.append({
                            "filename": a.get("name", "unknown"),
                            "mime_type": a.get("contentType", "application/octet-stream"),
                            "attachment_bytes": content_bytes,
                        })

                    received = msg.get("receivedDateTime", "")
                    try:
                        received_dt = datetime.fromisoformat(received.replace("Z", "+00:00"))
                    except Exception:
                        received_dt = None

                    messages.append({
                        "dedupe_key": msg["id"],
                        "message_id": msg.get("internetMessageId", msg["id"]),
                        "subject": msg.get("subject", ""),
                        "sender": sender_str,
                        "body": body_content[:5000],
                        "received_at": received_dt,
                        "attachments": attachments,
                    })
                except Exception as e:
                    logger.debug(f"Error parsing Outlook message: {e}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Microsoft Graph error: {e.response.status_code}")
    except Exception as e:
        logger.error(f"Outlook fetch failed: {e}")
    return messages

# ===== Document Ingestion =====

async def _ingest_attachment(
    db: AsyncSession,
    user_id: uuid.UUID,
    email_address: str,
    subject: str,
    attachment: Dict[str, Any],
    assessment_id: Optional[uuid.UUID],
    connection_id: uuid.UUID,
    attachment_bytes: Optional[bytes] = None,
) -> Optional[int]:
    """Ingest an email attachment as a Document.

    Saves bytes to local disk (email_attachments/{user_id}/{uuid}/{filename}),
    creates a Document record, and schedules OCR processing.

    Args:
        attachment_bytes: Raw bytes of the attachment. Required.
    """
    from app.models.document import Document, DocumentStatus, DocumentType
    from app.utils import validate_file, scan_file_content, sanitize_filename
    import hashlib

    filename = sanitize_filename(attachment.get("filename", "attachment"))
    mime_type = attachment.get("mime_type", "application/octet-stream")

    allowed_exts = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".doc", ".docx"}
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed_exts:
        return None

    file_bytes = attachment_bytes
    if not file_bytes:
        return None

    # Enforce the upload size limit
    if len(file_bytes) > settings.MAX_UPLOAD_SIZE:
        logger.warning(
            f"Attachment '{filename}' exceeds MAX_UPLOAD_SIZE "
            f"({len(file_bytes)} bytes > {settings.MAX_UPLOAD_SIZE})"
        )
        return None

    try:
        await validate_file(file_bytes, filename)
    except Exception as e:
        logger.warning(f"File validation failed for {filename}: {e}")
        return None

    clean, scan_error = await scan_file_content(file_bytes, filename)
    if not clean:
        logger.warning(f"Malware scan failed for {filename}: {scan_error}")
        return None

    checksum = hashlib.sha256(file_bytes).hexdigest()

    # Build local file path: email_attachments/{user_id}/{uuid}/{filename}
    file_uuid = str(uuid.uuid4())
    relative_path = f"email_attachments/{user_id}/{file_uuid}/{filename}"
    storage_dir = Path(settings.resolved_upload_dir) / "email_attachments" / str(user_id) / file_uuid
    storage_dir.mkdir(parents=True, exist_ok=True)
    full_path = storage_dir / filename
    with open(full_path, "wb") as f:
        f.write(file_bytes)

    doc = Document(
        filename=filename,
        file_path=relative_path,
        file_size=len(file_bytes),
        mime_type=mime_type,
        document_type=DocumentType.OTHER,
        status=DocumentStatus.PENDING,
        uploaded_by=user_id,
        assessment_id=assessment_id,
        checksum=checksum,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    await db.commit()

    # Schedule OCR processing using the existing background task pattern
    try:
        from app.routers.documents import process_document_ocr
        asyncio.create_task(process_document_ocr(doc.id))
    except Exception as e:
        logger.warning(f"Failed to schedule OCR for document {doc.id}: {e}")

    return doc.id

async def _fetch_gmail_attachment_bytes(
    access_token: str, message_id: str, attachment_id: str
) -> Optional[bytes]:
    """Fetch raw attachment bytes from Gmail API."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/attachments/{attachment_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            b64_data = data.get("data", "")
            return base64.urlsafe_b64decode(b64_data + "==")
    except Exception as e:
        logger.error(f"Gmail attachment fetch failed: {e}")
        return None

async def _fetch_outlook_attachment_bytes(
    access_token: str, message_id: str, attachment_name: str, mime_type: str
) -> Optional[bytes]:
    """Fetch raw attachment bytes from Microsoft Graph API."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/attachments/{attachment_name}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"$expand": "@microsoft.graph.itemAttachment"},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            content_bytes = data.get("contentBytes", "")
            if content_bytes:
                return base64.b64decode(content_bytes)
            return None
    except Exception as e:
        logger.error(f"Outlook attachment fetch failed: {e}")
        return None

# ===== Core Service Methods =====

async def get_provider_status() -> List[Dict[str, Any]]:
    google_ok = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)
    microsoft_ok = bool(settings.MICROSOFT_CLIENT_ID and settings.MICROSOFT_CLIENT_SECRET)
    return [
        {"provider": "gmail", "oauth_configured": google_ok, "imap_app_password_supported": True,
         "error": None if google_ok else "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET"},
        {"provider": "outlook", "oauth_configured": microsoft_ok, "imap_app_password_supported": True,
         "error": None if microsoft_ok else "Set MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET"},
    ]

async def start_oauth_flow(db: AsyncSession, user_id: uuid.UUID, provider: str,
                            redirect_uri: Optional[str] = None) -> Dict[str, Any]:
    if provider == "gmail":
        if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
            return {"error": "google_not_configured", "missing": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"]}
    elif provider == "outlook":
        if not (settings.MICROSOFT_CLIENT_ID and settings.MICROSOFT_CLIENT_SECRET):
            return {"error": "outlook_not_configured", "missing": ["MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET"]}
    else:
        return {"error": "invalid_provider"}

    allowed_base = settings.EMAIL_OAUTH_REDIRECT_BASE or settings.CORS_ORIGINS[0]
    expected_path = f"/api/v1/integrations/email/{provider}/callback"

    callback_uri: str
    if redirect_uri:
        parsed = urlparse(redirect_uri)
        allowed_netloc = urlparse(allowed_base).netloc
        if parsed.scheme not in ('http', 'https'):
            return {"error": "invalid_redirect_uri", "detail": "redirect_uri must use https"}
        if parsed.netloc != allowed_netloc:
            return {"error": "invalid_redirect_uri", "detail": "redirect_uri host must match configured base"}
        if parsed.path != expected_path:
            return {"error": "invalid_redirect_uri", "detail": "redirect_uri path must be " + expected_path}
        callback_uri = redirect_uri
    else:
        callback_uri = f"{allowed_base}{expected_path}"

    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)

    redis = await _get_redis()
    state_data = {"user_id": str(user_id), "provider": provider,
                  "code_verifier": code_verifier, "redirect_uri": callback_uri}
    await redis.setex(f"oauth_state:{state}", 600, json.dumps(state_data))

    if provider == "gmail":
        auth_url = _build_google_oauth_url(state, code_verifier, callback_uri)
    else:
        auth_url = _build_microsoft_oauth_url(state, code_verifier, callback_uri)

    return {"authorization_url": auth_url, "state": state}

async def handle_oauth_callback(db: AsyncSession, code: str, state: str) -> Tuple[Optional[EmailConnection], Optional[str]]:
    redis = await _get_redis()
    raw = await redis.get(f"oauth_state:{state}")
    if not raw:
        return None, "Invalid or expired state token"
    state_data = json.loads(raw)
    await redis.delete(f"oauth_state:{state}")

    provider = state_data["provider"]
    user_id = uuid.UUID(state_data["user_id"])
    code_verifier = state_data["code_verifier"]
    callback_uri = state_data["redirect_uri"]

    if provider == "gmail":
        token_data = await _exchange_google_code(code, code_verifier, callback_uri)
        profile = await _fetch_google_profile(token_data["access_token"])
        email_address = profile.get("email", "")
        display_name = profile.get("name", "")
        avatar_url = profile.get("picture", "")
    else:
        token_data = await _exchange_microsoft_code(code, code_verifier, callback_uri)
        profile = await _fetch_microsoft_profile(token_data["access_token"])
        email_address = profile.get("mail") or profile.get("userPrincipalName", "")
        display_name = f"{profile.get('givenName', '')} {profile.get('surname', '')}".strip() or None
        avatar_url = None

    encrypted_access = encrypt_secret(token_data["access_token"])
    encrypted_refresh = encrypt_secret(token_data.get("refresh_token", ""))
    encrypted_client_secret = encrypt_secret(
        settings.GOOGLE_CLIENT_SECRET if provider == "gmail" else settings.MICROSOFT_CLIENT_SECRET
    )

    expires_in = token_data.get("expires_in", 3600)
    token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    result = await db.execute(
        select(EmailConnection).where(
            EmailConnection.user_id == user_id,
            EmailConnection.email_address == email_address,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing._encrypted_access_token = encrypted_access
        existing._encrypted_refresh_token = encrypted_refresh
        existing._encrypted_client_secret = encrypted_client_secret
        existing.token_expires_at = token_expires_at
        existing.status = ConnectionStatus.ACTIVE
        existing.error_message = None
        connection = existing
    else:
        connection = EmailConnection(
            user_id=user_id,
            provider=EmailProvider.GMAIL if provider == "gmail" else EmailProvider.OUTLOOK,
            auth_method=AuthMethod.OAUTH,
            email_address=email_address,
            display_name=display_name,
            avatar_url=avatar_url,
            _encrypted_access_token=encrypted_access,
            _encrypted_refresh_token=encrypted_refresh,
            _encrypted_client_secret=encrypted_client_secret,
            token_expires_at=token_expires_at,
            status=ConnectionStatus.ACTIVE,
        )
        db.add(connection)

    await db.commit()
    await db.refresh(connection)
    return connection, None

async def connect_imap(db: AsyncSession, user_id: uuid.UUID, provider: str,
                       email_address: str, app_password: str) -> Tuple[Optional[EmailConnection], Optional[str]]:
    if provider == "gmail":
        provider_enum = EmailProvider.GMAIL
    elif provider == "outlook":
        provider_enum = EmailProvider.OUTLOOK
    else:
        return None, "Invalid provider"

    ok, err = await _test_imap_connection(provider_enum, email_address, app_password)
    if not ok:
        return None, err

    encrypted_password = encrypt_secret(app_password)
    expected_host, expected_port = ALLOWED_IMAP_HOSTS.get(provider_enum, (None, None))

    result = await db.execute(
        select(EmailConnection).where(
            EmailConnection.user_id == user_id,
            EmailConnection.email_address == email_address,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing._encrypted_app_password = encrypted_password
        existing.auth_method = AuthMethod.IMAP_APP_PASSWORD
        existing.status = ConnectionStatus.ACTIVE
        existing.error_message = None
        existing.imap_host = expected_host
        existing.imap_port = expected_port
        connection = existing
    else:
        connection = EmailConnection(
            user_id=user_id,
            provider=provider_enum,
            auth_method=AuthMethod.IMAP_APP_PASSWORD,
            email_address=email_address,
            _encrypted_app_password=encrypted_password,
            imap_host=expected_host,
            imap_port=expected_port,
            status=ConnectionStatus.ACTIVE,
        )
        db.add(connection)

    await db.commit()
    await db.refresh(connection)
    return connection, None

async def sync_connection(db: AsyncSession, connection_id: uuid.UUID,
                          user_id: uuid.UUID) -> Dict[str, Any]:
    result = await db.execute(
        select(EmailConnection).where(
            EmailConnection.id == connection_id,
            EmailConnection.user_id == user_id,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        return {"error": "Connection not found"}

    if connection.status not in (ConnectionStatus.ACTIVE, ConnectionStatus.ERROR):
        return {"error": f"Connection is {connection.status.value}"}

    messages: List[Dict[str, Any]] = []
    errors: List[str] = []
    raw_messages: Dict[str, bytes] = {}

    try:
        if connection.auth_method == AuthMethod.IMAP_APP_PASSWORD:
            messages, raw_messages = await _fetch_imap_unread(connection)
        elif connection.auth_method == AuthMethod.OAUTH:
            access_token = decrypt_secret(connection._encrypted_access_token or "")
            if not access_token:
                errors.append("No access token")
                raise ValueError("Missing access token")

            # Refresh if expiring within 5 minutes
            if connection.token_expires_at:
                refresh_threshold = connection.token_expires_at - timedelta(minutes=5)
                if datetime.now(timezone.utc) >= refresh_threshold:
                    access_token = await _refresh_oauth_token(connection)
                    if not access_token:
                        errors.append("Token refresh failed")
                        raise ValueError("Token refresh failed")

            if connection.provider == EmailProvider.GMAIL:
                messages = await _fetch_gmail_messages(access_token)
            else:
                messages = await _fetch_outlook_messages(access_token)
    except Exception as e:
        errors.append(str(e))
        logger.error(f"Sync fetch failed for {connection_id}: {e}")

    if not messages:
        connection.last_sync_at = datetime.now(timezone.utc)
        connection.consecutive_errors = 0
        await db.commit()
        return {
            "connection_id": str(connection_id), "messages_fetched": 0,
            "new_assessments_created": 0, "new_documents_ingested": 0,
            "skipped_duplicates": 0, "errors": errors,
        }

    dedupe_keys = [m["dedupe_key"] for m in messages]
    existing_result = await db.execute(
        select(EmailIngestionEvent.dedupe_key).where(
            EmailIngestionEvent.connection_id == connection_id,
            EmailIngestionEvent.dedupe_key.in_(dedupe_keys),
        )
    )
    existing_keys = {row[0] for row in existing_result.all()}
    new_messages = [m for m in messages if m["dedupe_key"] not in existing_keys]
    skipped = len(messages) - len(new_messages)
    new_assessments = 0
    new_documents = 0

    email_bot = EmailBotService()
    from app.models.user import User
    owner_result = await db.execute(select(User.syndicate_id).where(User.id == user_id))
    owner_syndicate_id = owner_result.scalar_one_or_none()

    for msg in new_messages:
        try:
            email_data = {
                "subject": msg["subject"],
                "sender": msg["sender"],
                "body": msg["body"],
                "received_at": (msg["received_at"] or datetime.now(timezone.utc)).isoformat(),
            }
            parsed: ParsedSubmission = await email_bot.parse_submission_email(email_data)

            assessment_id: Optional[uuid.UUID] = None
            doc_ids: List[int] = []

            if parsed.insured_name and parsed.email_type == "new_submission":
                from app.models.assessment import Assessment, AssessmentStatus, RiskCategory
                cat_map = {
                    "property": RiskCategory.PROPERTY,
                    "cyber": RiskCategory.CYBER,
                    "marine": RiskCategory.MARINE,
                    "liability": RiskCategory.GENERAL_LIABILITY,
                    "financial_lines": RiskCategory.FINANCIAL_LINES,
                    "other": RiskCategory.SPECIALTY,
                }
                risk_cat = cat_map.get(parsed.risk_category or "property", RiskCategory.PROPERTY)

                assessment = Assessment(
                    title=f"Email submission: {parsed.insured_name}",
                    description=parsed.description or "",
                    risk_category=risk_cat,
                    status=AssessmentStatus.SUBMITTED,
                    created_by=user_id,
                    syndicate_id=owner_syndicate_id,
                    insured_name=parsed.insured_name,
                    broker_reference=parsed.broker_reference,
                    sum_insured=parsed.sum_insured,
                    territory=parsed.territory or "UK",
                    broker_name=parsed.broker_name,
                )
                db.add(assessment)
                await db.flush()
                assessment_id = assessment.id
                new_assessments += 1

            for attachment in msg.get("attachments", []):
                attachment_bytes: Optional[bytes] = None

                # IMAP: attachment bytes are decoded inline in _extract_attachments
                if connection.auth_method == AuthMethod.IMAP_APP_PASSWORD:
                    attachment_bytes = attachment.get("bytes")

                # OAuth: fetch attachment bytes via provider API
                elif connection.auth_method == AuthMethod.OAUTH:
                    access_token = decrypt_secret(connection._encrypted_access_token or "") if connection._encrypted_access_token else None
                    if access_token and connection.provider == EmailProvider.GMAIL:
                        att_id = attachment.get("attachment_id")
                        if att_id:
                            attachment_bytes = await _fetch_gmail_attachment_bytes(
                                access_token, msg["dedupe_key"], att_id
                            )
                    elif connection.provider == EmailProvider.OUTLOOK:
                        # Graph `$expand=attachments` already returned decoded
                        # content bytes with the message; avoid a second request.
                        attachment_bytes = attachment.get("attachment_bytes")

                doc_id = await _ingest_attachment(
                    db=db, user_id=user_id,
                    email_address=connection.email_address,
                    subject=msg["subject"],
                    attachment=attachment,
                    assessment_id=assessment_id,
                    connection_id=connection_id,
                    attachment_bytes=attachment_bytes,
                )
                if doc_id:
                    doc_ids.append(doc_id)
                    new_documents += 1

            event = EmailIngestionEvent(
                connection_id=connection_id,
                user_id=user_id,
                dedupe_key=msg["dedupe_key"],
                subject=msg["subject"],
                sender=msg["sender"],
                received_at=msg["received_at"],
                assessment_id=assessment_id,
                document_ids=json.dumps(doc_ids) if doc_ids else None,
                parse_confidence=int(parsed.confidence * 100) if parsed.confidence else None,
                processed=True,
            )
            db.add(event)

        except Exception as e:
            logger.error(f"Error processing message {msg.get('dedupe_key')}: {e}")
            errors.append(f"Message {msg.get('subject', msg.get('dedupe_key'))}: {str(e)}")
            event = EmailIngestionEvent(
                connection_id=connection_id, user_id=user_id,
                dedupe_key=msg["dedupe_key"],
                subject=msg.get("subject"),
                error_message=str(e), processed=False,
            )
            db.add(event)

    connection.last_sync_at = datetime.now(timezone.utc)
    connection.total_messages_synced = (connection.total_messages_synced or 0) + len(new_messages)
    if errors:
        connection.consecutive_errors += 1
        connection.last_error_at = datetime.now(timezone.utc)
        connection.error_message = errors[-1][:500]
        connection.status = ConnectionStatus.ERROR
    else:
        connection.consecutive_errors = 0

    await db.commit()

    return {
        "connection_id": str(connection_id),
        "messages_fetched": len(messages),
        "new_assessments_created": new_assessments,
        "new_documents_ingested": new_documents,
        "skipped_duplicates": skipped,
        "errors": errors,
    }

async def _refresh_oauth_token(connection: EmailConnection) -> Optional[str]:
    from app.core.database import AsyncSessionLocal
    refresh_token = decrypt_secret(connection._encrypted_refresh_token or "")
    if not refresh_token:
        return None
    try:
        if connection.provider == EmailProvider.GMAIL:
            token_data = await _refresh_google_token(refresh_token)
        else:
            token_data = await _refresh_microsoft_token(refresh_token)
        new_access = token_data.get("access_token")
        if new_access:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(EmailConnection).where(EmailConnection.id == connection.id)
                )
                conn = result.scalar_one_or_none()
                if conn:
                    conn._encrypted_access_token = encrypt_secret(new_access)
                    if token_data.get("refresh_token"):
                        conn._encrypted_refresh_token = encrypt_secret(token_data["refresh_token"])
                    if token_data.get("expires_in"):
                        conn.token_expires_at = datetime.now(timezone.utc) + timedelta(
                            seconds=token_data["expires_in"]
                        )
                    await db.commit()
            return new_access
    except Exception as e:
        logger.error(f"Token refresh failed for {connection.id}: {e}")
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(EmailConnection).where(EmailConnection.id == connection.id)
                )
                conn = result.scalar_one_or_none()
                if conn:
                    conn.status = ConnectionStatus.PENDING_REAUTH
                    conn.error_message = "Token refresh failed; re-authorize required"
                    await db.commit()
        except Exception as persist_err:
            logger.error(f"Failed to persist refresh failure status: {persist_err}")
    return None

async def disconnect_connection(db: AsyncSession, connection_id: uuid.UUID,
                                  user_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(EmailConnection).where(
            EmailConnection.id == connection_id,
            EmailConnection.user_id == user_id,
        )
    )
    connection = result.scalar_one_or_none()
    if not connection:
        return False

    if connection.auth_method == AuthMethod.OAUTH:
        try:
            access_token = decrypt_secret(connection._encrypted_access_token or "")
            if access_token and connection.provider == EmailProvider.GMAIL:
                async with httpx.AsyncClient() as client:
                    await client.post("https://oauth2.googleapis.com/revoke", data={"token": access_token})
            elif access_token and connection.provider == EmailProvider.OUTLOOK:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        "https://login.microsoftonline.com/common/oauth2/v2.0/logout",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
        except Exception as e:
            logger.debug(f"Token revocation failed: {e}")

    await db.delete(connection)
    await db.commit()
    return True

async def get_user_connections(db: AsyncSession, user_id: uuid.UUID) -> List[EmailConnection]:
    result = await db.execute(
        select(EmailConnection)
        .where(EmailConnection.user_id == user_id)
        .order_by(EmailConnection.created_at.desc())
    )
    return list(result.scalars().all())
