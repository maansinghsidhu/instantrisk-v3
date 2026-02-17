"""
InstantRisk V2 - Broker Communication AI Router

Endpoints for the automated broker email processing pipeline.
The email bot monitors a dedicated inbox, parses broker submissions using AI,
and sends automatic quote responses.

Routes:
    GET  /api/v1/broker-comms/status           - Bot status & configuration
    POST /api/v1/broker-comms/process          - Manually trigger inbox processing
    POST /api/v1/broker-comms/parse            - Parse a submission email (ad-hoc)
    POST /api/v1/broker-comms/simulate         - Inject a test email
    GET  /api/v1/broker-comms/logs             - Recent email processing logs
    POST /api/v1/broker-comms/quote            - Generate preliminary quote
    POST /api/v1/broker-comms/monitor/start    - Start background email monitoring
    POST /api/v1/broker-comms/monitor/stop     - Stop background email monitoring
"""

import logging
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field, EmailStr

from app.core.security import get_current_user
from app.models.user import User
from app.services.email_bot import get_email_bot_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Track monitoring task globally
_monitor_task: Optional[asyncio.Task] = None


# ============================================================
# Schemas
# ============================================================

class ParseEmailRequest(BaseModel):
    """Request to parse a broker submission email."""
    subject: str = Field(..., description="Email subject line")
    sender: str = Field(..., description="Sender email address or name")
    body: str = Field(..., min_length=10, description="Email body text")


class ParseEmailResponse(BaseModel):
    """Response with extracted submission data."""
    email_type: str
    insured_name: Optional[str]
    risk_category: Optional[str]
    sum_insured: Optional[float]
    inception_date: Optional[str]
    expiry_date: Optional[str]
    territory: Optional[str]
    broker_name: Optional[str]
    broker_reference: Optional[str]
    description: Optional[str]
    confidence: float
    extraction_notes: str
    suggested_premium_min: Optional[float]
    suggested_premium_max: Optional[float]
    draft_reply: str


class QuoteRequest(BaseModel):
    """Manual quote generation request."""
    insured_name: str = Field(..., description="Name of insured party")
    risk_category: str = Field(..., description="property|cyber|marine|liability|financial_lines")
    sum_insured: float = Field(..., gt=0, description="Sum insured in GBP")
    territory: str = Field(default="UK", description="Territory of coverage")
    inception_date: Optional[str] = Field(None, description="Inception date (YYYY-MM-DD)")
    expiry_date: Optional[str] = Field(None, description="Expiry date (YYYY-MM-DD)")
    broker_name: Optional[str] = Field(None)
    broker_reference: Optional[str] = Field(None)
    send_to_email: Optional[str] = Field(None, description="Send quote to this email address")


class SimulateEmailRequest(BaseModel):
    """Inject a test email for simulation mode."""
    subject: str = Field(..., description="Email subject")
    sender: str = Field(..., description="Sender email (e.g. broker@lloydbrokers.com)")
    body: str = Field(..., min_length=20, description="Email body text")


# ============================================================
# Endpoints
# ============================================================

@router.get(
    "/status",
    summary="Email bot status and configuration",
)
async def get_bot_status(
    current_user: User = Depends(get_current_user),
):
    """
    Returns the current status of the broker email monitoring bot.

    Shows whether the bot is running, configured IMAP details (masked),
    number of emails processed, and required environment variables for live mode.
    """
    svc = get_email_bot_service()
    return svc.get_status()


@router.post(
    "/process",
    summary="Manually process unread inbox emails",
)
async def process_inbox(
    current_user: User = Depends(get_current_user),
):
    """
    Manually trigger processing of unread emails in the monitored inbox.

    In simulation mode: processes any emails injected via /simulate.
    In live mode: connects to IMAP, fetches unseen messages, parses and replies.

    Returns summary of all emails processed in this batch.
    """
    svc = get_email_bot_service()
    try:
        submissions = await svc.process_inbox_once()
        return {
            "processed": len(submissions),
            "submissions": [
                {
                    "sender": s.raw_sender,
                    "subject": s.raw_subject,
                    "email_type": s.email_type,
                    "insured_name": s.insured_name,
                    "risk_category": s.risk_category,
                    "sum_insured": s.sum_insured,
                    "confidence": s.confidence,
                    "reply_sent": s.auto_reply_sent,
                    "suggested_premium_min": s.suggested_premium_min,
                    "suggested_premium_max": s.suggested_premium_max,
                }
                for s in submissions
            ],
        }
    except Exception as e:
        logger.error(f"Inbox processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing error: {str(e)}",
        )


@router.post(
    "/parse",
    response_model=ParseEmailResponse,
    summary="Parse a broker submission email",
)
async def parse_email(
    req: ParseEmailRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Parse a single broker submission email to extract structured risk data.

    Uses AI (Bedrock Claude) to extract:
    - Insured name, risk category, sum insured
    - Policy dates, territory, broker reference
    - Email classification (new submission / renewal / loss / enquiry)

    Falls back to regex extraction when AI is unavailable.
    Also generates a draft reply appropriate for the email type.
    """
    svc = get_email_bot_service()
    try:
        email_data = {
            "subject": req.subject,
            "sender": req.sender,
            "body": req.body,
        }
        submission = await svc.parse_submission_email(email_data)
        draft_reply = svc._draft_reply_email(submission)

        return ParseEmailResponse(
            email_type=submission.email_type,
            insured_name=submission.insured_name,
            risk_category=submission.risk_category,
            sum_insured=submission.sum_insured,
            inception_date=submission.inception_date,
            expiry_date=submission.expiry_date,
            territory=submission.territory,
            broker_name=submission.broker_name,
            broker_reference=submission.broker_reference,
            description=submission.description,
            confidence=submission.confidence,
            extraction_notes=submission.extraction_notes,
            suggested_premium_min=submission.suggested_premium_min,
            suggested_premium_max=submission.suggested_premium_max,
            draft_reply=draft_reply,
        )
    except Exception as e:
        logger.error(f"Email parse error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parse error: {str(e)}",
        )


@router.post(
    "/simulate",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Inject a simulated email for testing",
)
async def simulate_email(
    req: SimulateEmailRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Injects a test email into the simulation inbox.

    Call POST /broker-comms/process afterward to process it.
    This allows end-to-end testing of the email pipeline without a real IMAP server.

    Example test email:
    - Subject: "New Submission - Cyber Risk - TechCorp Ltd"
    - Body: "Please provide terms for TechCorp Ltd, cyber risk, sum insured £5m,
             territory UK, inception 01/04/2026..."
    """
    svc = get_email_bot_service()
    svc.inject_test_email(
        subject=req.subject,
        sender=req.sender,
        body=req.body,
    )
    return {
        "status": "queued",
        "message": "Email injected into simulation inbox. Call POST /process to handle it.",
        "pending_count": len(svc._simulated_inbox),
    }


@router.get(
    "/logs",
    summary="Recent email processing logs",
)
async def get_email_logs(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    """
    Returns recent email processing logs.

    Shows: sender, subject, email type, parse status, reply sent, any errors.
    Ordered most-recent-first.
    """
    svc = get_email_bot_service()
    logs = svc.get_logs(limit=limit)
    return {"logs": logs, "count": len(logs)}


@router.post(
    "/quote",
    summary="Generate a preliminary quote email",
)
async def generate_quote(
    req: QuoteRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """
    Generate a preliminary indicative quote for a broker submission.

    Calculates premium range based on:
    - Risk category (property/cyber/marine/liability/financial lines)
    - Sum insured
    - Market rate benchmarks

    Optionally sends the quote to the provided email address.
    Returns the full quote email text.
    """
    svc = get_email_bot_service()

    # Build a mock submission to generate quote
    from app.services.email_bot import ParsedSubmission
    submission = ParsedSubmission(
        raw_subject=f"Quote for {req.insured_name}",
        raw_sender=req.send_to_email or "broker@example.com",
        raw_body="",
        received_at="",
        insured_name=req.insured_name,
        risk_category=req.risk_category,
        sum_insured=req.sum_insured,
        inception_date=req.inception_date,
        expiry_date=req.expiry_date,
        territory=req.territory,
        broker_name=req.broker_name or "Broker",
        broker_reference=req.broker_reference,
        email_type="new_submission",
    )

    quote_email = svc._draft_reply_email(submission)
    pmin = submission.suggested_premium_min
    pmax = submission.suggested_premium_max

    # Optionally send
    if req.send_to_email:
        background_tasks.add_task(
            svc.send_reply,
            to_addr=req.send_to_email,
            subject=f"Preliminary Quote - {req.insured_name}",
            body=quote_email,
        )

    return {
        "insured_name": req.insured_name,
        "risk_category": req.risk_category,
        "sum_insured": req.sum_insured,
        "territory": req.territory,
        "suggested_premium_min": pmin,
        "suggested_premium_max": pmax,
        "quote_email_text": quote_email,
        "sent_to": req.send_to_email or None,
        "email_queued": bool(req.send_to_email),
    }


@router.post(
    "/monitor/start",
    summary="Start background IMAP email monitoring",
)
async def start_monitor(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """
    Starts the email monitoring daemon as a background task.

    The bot polls the configured IMAP inbox at the configured interval
    (default 60 seconds), processes new emails, and auto-replies.

    This is a fire-and-forget background task that runs until stopped
    via POST /monitor/stop.
    """
    global _monitor_task
    svc = get_email_bot_service()

    if svc._running:
        return {"status": "already_running", "mode": svc.get_status()["mode"]}

    background_tasks.add_task(svc.start_monitoring)

    return {
        "status": "started",
        "mode": "simulation" if svc._simulation_mode else "live",
        "poll_interval_secs": svc._poll_interval,
        "imap_host": svc._imap_host or "(simulation)",
        "message": "Email monitoring started in background. Use POST /process to manually trigger.",
    }


@router.post(
    "/monitor/stop",
    summary="Stop background IMAP email monitoring",
)
async def stop_monitor(
    current_user: User = Depends(get_current_user),
):
    """Stops the email monitoring daemon."""
    svc = get_email_bot_service()
    svc.stop_monitoring()
    return {"status": "stopped", "processed_total": len(svc._processed_logs)}
