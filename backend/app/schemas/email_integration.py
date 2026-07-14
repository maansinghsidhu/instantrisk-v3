"""
InstantRisk V3 - Email Integration Schemas

Pydantic schemas for email API endpoints.
No secrets/tokens are ever exposed via these schemas.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr
from app.models.email_integration import EmailProvider, ConnectionStatus, AuthMethod


# ============================================================
# Connection Schemas
# ============================================================

class EmailConnectionResponse(BaseModel):
    """Public view of an email connection — no secrets."""
    id: str
    provider: EmailProvider
    auth_method: AuthMethod
    email_address: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    status: ConnectionStatus
    error_message: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    total_messages_synced: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class EmailConnectionListResponse(BaseModel):
    connections: List[EmailConnectionResponse]


# ============================================================
# Provider Status
# ============================================================

class ProviderStatus(BaseModel):
    """Provider configuration status — no secrets."""
    provider: EmailProvider
    oauth_configured: bool = False   # True if GOOGLE_CLIENT_ID/SECRET or MICROSOFT_CLIENT_ID/SECRET are set
    imap_app_password_supported: bool = True  # IMAP is always available
    error: Optional[str] = None  # Only set when provider is misconfigured


class EmailProvidersResponse(BaseModel):
    providers: List[ProviderStatus]


# ============================================================
# OAuth Authorization
# ============================================================

class AuthorizeRequest(BaseModel):
    redirect_uri: Optional[str] = None


class AuthorizeResponse(BaseModel):
    authorization_url: str
    state: str


# ============================================================
# IMAP App-Password Authorization
# ============================================================

class IMAPConnectRequest(BaseModel):
    """Connect via IMAP app-password (no OAuth app registration needed)."""
    provider: EmailProvider = Field(..., description="gmail or outlook")
    email_address: EmailStr = Field(..., description="Full email address")
    app_password: str = Field(..., min_length=8, max_length=64, description="App-specific password")

    class Config:
        json_schema_extra = {
            "example": {
                "provider": "gmail",
                "email_address": "broker@example.com",
                "app_password": "abcd efgh ijkl mnop"
            }
        }


class IMAPConnectResponse(BaseModel):
    """Result of an IMAP connect attempt — no secrets."""
    connection: EmailConnectionResponse
    messages_tested: int = 0
    connection_ok: bool = True


# ============================================================
# Sync
# ============================================================

class SyncResult(BaseModel):
    """Result of a sync operation."""
    connection_id: str
    messages_fetched: int = 0
    new_assessments_created: int = 0
    new_documents_ingested: int = 0
    skipped_duplicates: int = 0
    errors: List[str] = Field(default_factory=list)


# ============================================================
# Error Responses
# ============================================================

class ProviderNotConfiguredError(BaseModel):
    detail: str = "Provider not configured. Set GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET or MICROSOFT_CLIENT_ID/MICROSOFT_CLIENT_SECRET."
    provider: str
    missing_credentials: List[str]
