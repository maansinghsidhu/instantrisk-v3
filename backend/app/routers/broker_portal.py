"""
InstantRisk V2 - Broker Portal Router

Complete broker-facing portal for:
- Broker registration and authentication
- Submission management
- Quote tracking and acceptance
- Document upload and management
- Communication with underwriters

Broker Portal URL: https://brokers.instantrisk.ai
API Base: /api/v1/broker-portal
"""

import logging
from typing import Optional
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.security import (
    get_current_user,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.core.database import get_db
from app.models.user import User, UserRole, ApprovalStatus
from app.models.assessment import Assessment
from app.models.document import Document
from app.models.quote import Quote
from app.services.qdrant_service import qdrant_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/broker-portal", tags=["Broker Portal"])

# ============================================================
# Pydantic Schemas
# ============================================================


class BrokerRegistrationRequest(BaseModel):
    """Broker registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2)
    company_name: str = Field(..., min_length=2)
    phone: str
    license_number: str
    territory: str = Field(default="UK", description="Primary operating territory")
    fca_reference: Optional[str] = Field(None, description="FCA reference number")


class BrokerLoginRequest(BaseModel):
    """Broker login request."""

    email: EmailStr
    password: str


class BrokerLoginResponse(BaseModel):
    """Broker login response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict
    company: dict


class BrokerSubmissionCreate(BaseModel):
    """Create a new submission."""

    insured_name: str = Field(..., description="Name of insured party")
    risk_category: str = Field(
        ..., description="property|cyber|marine|liability|financial_lines|specialty"
    )
    description: str = Field(..., description="Business description")
    sum_insured: Decimal = Field(..., gt=0, description="Total sum insured in GBP")
    territory: str = Field(..., description="Territory of coverage")
    inception_date: str = Field(..., description="Policy inception date (YYYY-MM-DD)")
    expiry_date: str = Field(..., description="Policy expiry date (YYYY-MM-DD)")
    target_premium: Optional[Decimal] = Field(None, description="Target premium budget")
    deadline: Optional[str] = Field(None, description="Quote deadline (YYYY-MM-DD)")
    notes: Optional[str] = None
    priority: str = Field(default="normal", description="urgent|normal|low")


class SubmissionResponse(BaseModel):
    """Submission response."""

    submission_id: str
    reference: str
    status: str
    insured_name: str
    risk_category: str
    sum_insured: Decimal
    created_at: str
    deadline: Optional[str]
    underwriter: Optional[str]
    quote: Optional[dict]


class QuoteResponse(BaseModel):
    """Quote response for broker."""

    quote_id: str
    submission_id: str
    premium: Decimal
    deductible: Decimal
    coverage: str
    terms: dict
    validity_days: int
    expires_at: str
    status: str
    generated_at: str


class BrokerDashboardStats(BaseModel):
    """Broker dashboard statistics."""

    total_submissions: int
    pending_quotes: int
    accepted_quotes: int
    declined_quotes: int
    total_premium_quoted: Decimal
    total_premium_bound: Decimal
    win_rate: float


# ============================================================
# Broker Authentication
# ============================================================


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register_broker(
    request: BrokerRegistrationRequest, db: AsyncSession = Depends(get_db)
):
    """
    Register a new broker account.

    Brokers require manual approval before accessing the portal.
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == request.email))
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create broker user
    hashed_password = get_password_hash(request.password)
    broker = User(
        email=request.email,
        hashed_password=hashed_password,
        full_name=request.full_name,
        role=UserRole.BROKER,
        approval_status=ApprovalStatus.PENDING,
        is_active=False,  # Inactive until approved
        syndicate_id=None,
        metadata={
            "company_name": request.company_name,
            "phone": request.phone,
            "license_number": request.license_number,
            "territory": request.territory,
            "fca_reference": request.fca_reference,
            "broker_since": datetime.now().isoformat(),
        },
    )

    db.add(broker)
    await db.commit()
    await db.refresh(broker)

    return {
        "message": "Registration submitted for approval",
        "broker_id": str(broker.id),
        "status": "pending_approval",
        "next_steps": [
            "Your application is under review",
            "You will receive an email when approved",
            "Once approved, you can log in and start submitting business",
        ],
    }


@router.post("/login", response_model=BrokerLoginResponse)
async def login_broker(request: BrokerLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate broker and return tokens.

    Only approved brokers can log in.
    """
    # Find user
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    # Verify password
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    # Check if approved broker
    if user.role != UserRole.BROKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This login is for brokers only",
        )

    if user.approval_status != ApprovalStatus.APPROVED:
        if user.approval_status == ApprovalStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is pending approval",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been rejected",
            )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive"
        )

    # Generate tokens
    access_token = create_access_token(
        subject=str(user.id), email=user.email, role=user.role.value
    )
    refresh_token = create_refresh_token(str(user.id))

    return BrokerLoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
        },
        company={
            "name": user.metadata.get("company_name", ""),
            "territory": user.metadata.get("territory", "UK"),
        },
    )


# ============================================================
# Broker Submissions
# ============================================================


@router.post(
    "/submissions",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_submission(
    request: BrokerSubmissionCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new submission.

    Brokers can submit new risks for underwriting.
    """
    if current_user.role != UserRole.BROKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only brokers can create submissions",
        )

    # Generate submission reference
    ref_date = datetime.now().strftime("%Y%m%d")
    result = await db.execute(
        select(func.count(Assessment.id)).where(
            Assessment.created_at >= datetime.now().replace(hour=0, minute=0, second=0)
        )
    )
    count = result.scalar() or 0
    reference = f"INST/{ref_date}/{str(count + 1).zfill(4)}"

    # Create assessment record
    assessment = Assessment(
        title=f"Submission: {request.insured_name}",
        risk_category=request.risk_category,
        insured_name=request.insured_name,
        sum_insured=float(request.sum_insured),
        territory=request.territory,
        inception_date=datetime.fromisoformat(request.inception_date),
        expiry_date=datetime.fromisoformat(request.expiry_date),
        status="submitted",
        broker_id=current_user.id,
        metadata={
            "description": request.description,
            "target_premium": str(request.target_premium)
            if request.target_premium
            else None,
            "deadline": request.deadline,
            "notes": request.notes,
            "priority": request.priority,
            "source": "broker_portal",
        },
    )

    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)

    # TODO: Trigger background tasks:
    # - Sanctions screening
    # - Initial risk assessment
    # - Notification to underwriters

    return SubmissionResponse(
        submission_id=str(assessment.id),
        reference=reference,
        status=assessment.status,
        insured_name=request.insured_name,
        risk_category=request.risk_category,
        sum_insured=request.sum_insured,
        created_at=assessment.created_at.isoformat(),
        deadline=request.deadline,
        underwriter=None,
        quote=None,
    )


@router.get("/submissions", response_model=list)
async def list_submissions(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List broker's submissions.
    """
    if current_user.role != UserRole.BROKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only brokers can view submissions",
        )

    query = select(Assessment).where(Assessment.broker_id == current_user.id)

    if status_filter:
        query = query.where(Assessment.status == status_filter)

    query = query.order_by(Assessment.created_at.desc())

    result = await db.execute(query)
    assessments = result.scalars().all()

    return [
        {
            "submission_id": str(a.id),
            "reference": f"INST/{a.created_at.strftime('%Y%m%d')}/{str(a.id)[-4:]}",
            "status": a.status,
            "insured_name": a.insured_name,
            "risk_category": a.risk_category,
            "sum_insured": a.sum_insured,
            "created_at": a.created_at.isoformat(),
            "updated_at": a.updated_at.isoformat(),
        }
        for a in assessments
    ]


@router.get("/submissions/{submission_id}", response_model=dict)
async def get_submission(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get submission details with quote if available.
    """
    if current_user.role != UserRole.BROKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only brokers can view submissions",
        )

    result = await db.execute(
        select(Assessment).where(
            Assessment.id == submission_id, Assessment.broker_id == current_user.id
        )
    )
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found"
        )

    # Get quote if exists
    quote_result = await db.execute(
        select(Quote).where(Quote.assessment_id == submission_id)
    )
    quote = quote_result.scalar_one_or_none()

    return {
        "submission": {
            "id": str(assessment.id),
            "reference": f"INST/{assessment.created_at.strftime('%Y%m%d')}/{str(assessment.id)[-4:]}",
            "status": assessment.status,
            "insured_name": assessment.insured_name,
            "risk_category": assessment.risk_category,
            "sum_insured": assessment.sum_insured,
            "territory": assessment.territory,
            "inception_date": assessment.inception_date.isoformat(),
            "expiry_date": assessment.expiry_date.isoformat(),
            "description": assessment.metadata.get("description", ""),
            "notes": assessment.metadata.get("notes", ""),
            "created_at": assessment.created_at.isoformat(),
        },
        "quote": quote.to_dict() if quote else None,
        "documents": [
            {"id": str(d.id), "name": d.filename, "type": d.document_type}
            for d in assessment.documents
        ]
        if assessment.documents
        else [],
    }


# ============================================================
# Broker Dashboard
# ============================================================


@router.get("/dashboard", response_model=BrokerDashboardStats)
async def get_broker_dashboard(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Get broker dashboard statistics.
    """
    if current_user.role != UserRole.BROKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only brokers can view dashboard",
        )

    # Count by status
    total = await db.execute(
        select(func.count(Assessment.id)).where(Assessment.broker_id == current_user.id)
    )
    pending = await db.execute(
        select(func.count(Assessment.id)).where(
            Assessment.broker_id == current_user.id,
            Assessment.status.in_(["submitted", "under_review", "quote_pending"]),
        )
    )
    accepted = await db.execute(
        select(func.count(Assessment.id)).where(
            Assessment.broker_id == current_user.id, Assessment.status == "bound"
        )
    )
    declined = await db.execute(
        select(func.count(Assessment.id)).where(
            Assessment.broker_id == current_user.id, Assessment.status == "declined"
        )
    )

    return BrokerDashboardStats(
        total_submissions=total.scalar() or 0,
        pending_quotes=pending.scalar() or 0,
        accepted_quotes=accepted.scalar() or 0,
        declined_quotes=declined.scalar() or 0,
        total_premium_quoted=Decimal("0.00"),
        total_premium_bound=Decimal("0.00"),
        win_rate=0.0
        if (accepted.scalar() or 0) == 0
        else (accepted.scalar() or 1)
        / ((accepted.scalar() or 1) + (declined.scalar() or 0))
        * 100,
    )


# ============================================================
# Broker Quotes
# ============================================================


@router.post("/quotes/{quote_id}/accept")
async def accept_quote(
    quote_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Accept a quote and bind the policy.
    """
    if current_user.role != UserRole.BROKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only brokers can accept quotes",
        )

    # Get quote
    result = await db.execute(select(Quote).where(Quote.id == quote_id))
    quote = result.scalar_one_or_none()

    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found"
        )

    if quote.status != "quoted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Quote cannot be accepted. Current status: {quote.status}",
        )

    # Update quote status
    quote.status = "accepted"
    quote.accepted_at = datetime.now()
    quote.accepted_by = current_user.id

    # Update assessment to bound
    result = await db.execute(
        select(Assessment).where(Assessment.id == quote.assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if assessment:
        assessment.status = "bound"

    await db.commit()

    return {
        "message": "Quote accepted successfully",
        "quote_id": quote_id,
        "status": "accepted",
        "next_steps": [
            "Policy documents will be generated",
            "You will receive confirmation via email",
            "Coverage is effective from policy inception date",
        ],
    }


@router.post("/quotes/{quote_id}/decline")
async def decline_quote(
    quote_id: str,
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Decline a quote.
    """
    if current_user.role != UserRole.BROKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only brokers can decline quotes",
        )

    result = await db.execute(select(Quote).where(Quote.id == quote_id))
    quote = result.scalar_one_or_none()

    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found"
        )

    quote.status = "declined"
    quote.declined_at = datetime.now()
    quote.decline_reason = reason

    await db.commit()

    return {"message": "Quote declined", "quote_id": quote_id, "status": "declined"}


# ============================================================
# Broker Communication
# ============================================================


@router.post("/submissions/{submission_id}/message")
async def send_message_to_underwriter(
    submission_id: str,
    message: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send message to underwriter about a submission.
    """
    if current_user.role != UserRole.BROKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only brokers can send messages",
        )

    # Verify submission belongs to broker
    result = await db.execute(
        select(Assessment).where(
            Assessment.id == submission_id, Assessment.broker_id == current_user.id
        )
    )
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found"
        )

    # TODO: Store message and notify underwriter
    # - Create message record
    # - Send notification to assigned underwriter
    # - Add to conversation thread

    return {
        "message": "Message sent to underwriter",
        "submission_id": submission_id,
        "sent_at": datetime.now().isoformat(),
    }
