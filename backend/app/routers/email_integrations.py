"""
InstantRisk V3 - Email Integrations Router

Endpoints for user-connected Gmail/Outlook email ingestion.

Routes:
    GET  /api/v1/integrations/email                  → list user connections
    GET  /api/v1/integrations/email/providers       → provider configuration status
    POST /api/v1/integrations/email/{provider}/authorize → start OAuth flow (returns URL)
    GET  /api/v1/integrations/email/{provider}/callback → OAuth callback (redirects to Flutter)
    POST /api/v1/integrations/email/imap            → connect via IMAP app-password
    POST /api/v1/integrations/email/{connection_id}/sync → sync inbox
    DELETE /api/v1/integrations/email/{connection_id} → disconnect and revoke

Auth: bearer JWT (get_current_user)
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.email_integration import EmailProvider, ConnectionStatus
from app.services import email_integration as svc
from app.schemas.email_integration import (
    EmailConnectionResponse,
    EmailConnectionListResponse,
    EmailProvidersResponse,
    AuthorizeRequest,
    AuthorizeResponse,
    IMAPConnectRequest,
    IMAPConnectResponse,
    SyncResult,
    ProviderStatus,
)

router = APIRouter()


def _connection_to_response(conn) -> EmailConnectionResponse:
    """Map model to public schema (no secrets)."""
    return EmailConnectionResponse(
        id=str(conn.id),
        provider=conn.provider,
        auth_method=conn.auth_method,
        email_address=conn.email_address,
        display_name=conn.display_name,
        avatar_url=conn.avatar_url,
        status=conn.status,
        error_message=conn.error_message,
        last_sync_at=conn.last_sync_at,
        total_messages_synced=conn.total_messages_synced or 0,
        created_at=conn.created_at,
    )


# ============================================================
# List Connections
# ============================================================

@router.get("", response_model=EmailConnectionListResponse, tags=["Email Integrations"])
async def list_connections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all email connections for the authenticated user.
    No tokens or secrets are returned.
    """
    connections = await svc.get_user_connections(db, current_user.id)
    return EmailConnectionListResponse(
        connections=[_connection_to_response(c) for c in connections]
    )


# ============================================================
# Provider Status
# ============================================================

@router.get("/providers", response_model=EmailProvidersResponse, tags=["Email Integrations"])
async def list_providers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return provider configuration status.
    Indicates which providers have OAuth credentials configured
    and whether IMAP app-password is supported.
    """
    providers = await svc.get_provider_status()
    return EmailProvidersResponse(
        providers=[ProviderStatus(**p) for p in providers]
    )


# ============================================================
# OAuth Authorization
# ============================================================

@router.post("/{provider}/authorize", response_model=AuthorizeResponse, tags=["Email Integrations"])
async def authorize(
    provider: str,
    body: Optional[AuthorizeRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start OAuth 2.0 + PKCE authorization code flow.

    Returns an authorization URL to redirect the user to.
    After authorization, the provider redirects to /callback with code+state.
    State and PKCE verifier are stored in Redis for 10 minutes.
    """
    result = await svc.start_oauth_flow(
        db=db,
        user_id=current_user.id,
        provider=provider,
        redirect_uri=body.redirect_uri if body else None,
    )

    if "error" in result:
        err = result["error"]
        missing = result.get("missing", [])
        if err == "google_not_configured":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": "Gmail OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
                    "provider": "gmail",
                    "missing_credentials": missing,
                },
            )
        elif err == "outlook_not_configured":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": "Microsoft OAuth not configured. Set MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET.",
                    "provider": "outlook",
                    "missing_credentials": missing,
                },
            )
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    return AuthorizeResponse(
        authorization_url=result["authorization_url"],
        state=result["state"],
    )


@router.get("/{provider}/callback", tags=["Email Integrations"])
async def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    OAuth callback — exchanges code for tokens, upserts connection,
    redirects to Flutter /settings/integrations page.
    """
    connection, err = await svc.handle_oauth_callback(db, code, state)

    frontend_base = (settings.EMAIL_OAUTH_REDIRECT_BASE or settings.CORS_ORIGINS[0]).rstrip("/")
    if err:
        from urllib.parse import urlencode

        query = urlencode({"error": err, "provider": provider})
        return RedirectResponse(
            url=f"{frontend_base}/settings/integrations?{query}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url=f"{frontend_base}/settings/integrations?connected={provider}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ============================================================
# IMAP App-Password Connect
# ============================================================

@router.post("/imap", response_model=IMAPConnectResponse, tags=["Email Integrations"])
async def connect_imap(
    body: IMAPConnectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Connect via IMAP app-password (no OAuth app registration needed).

    Restricted to:
    - imap.gmail.com:993 (Gmail)
    - outlook.office365.com:993 (Outlook/Microsoft)

    App password is tested via SSL IMAP login before persisting.
    Credentials are never logged.
    """
    connection, err = await svc.connect_imap(
        db=db,
        user_id=current_user.id,
        provider=body.provider.value,
        email_address=body.email_address,
        app_password=body.app_password,
    )

    if err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"IMAP connection failed: {err}",
        )

    return IMAPConnectResponse(
        connection=_connection_to_response(connection),
        messages_tested=1,
        connection_ok=True,
    )


# ============================================================
# Sync
# ============================================================

@router.post("/{connection_id}/sync", response_model=SyncResult, tags=["Email Integrations"])
async def sync_connection(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch unread messages, deduplicate, parse submissions, create
    assessments/documents, queue OCR.

    Deduplication keys:
    - OAuth (Gmail/Outlook): provider's immutable message ID
    - IMAP: UIDVALIDITY:UID

    Returns counts of fetched messages, new assessments, documents,
    and skipped duplicates.
    """
    result = await svc.sync_connection(db, connection_id, current_user.id)

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
            if "not found" in result["error"].lower()
            else status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    return SyncResult(**result)


# ============================================================
# Disconnect
# ============================================================

@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Email Integrations"])
async def disconnect(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Revoke OAuth token best-effort and delete the connection.

    For OAuth: calls provider token revocation endpoint.
    For IMAP: no revocation needed; deletes connection.
    """
    ok = await svc.disconnect_connection(db, connection_id, current_user.id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found",
        )
