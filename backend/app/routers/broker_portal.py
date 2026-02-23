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
from app.models.pricing_models import Quote

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Broker Portal"])

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
    recent_submissions: list = Field(default_factory=list)


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
        created_by=current_user.id,
        underwriter_notes=f"Broker submission. Description: {request.description}. Notes: {request.notes or ''}. Priority: {request.priority}",
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

    query = select(Assessment).where(Assessment.created_by == current_user.id)

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
            Assessment.id == submission_id, Assessment.created_by == current_user.id
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
            "description": assessment.underwriter_notes or "",
            "notes": "",
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
    total_result = await db.execute(
        select(func.count(Assessment.id)).where(
            Assessment.created_by == current_user.id
        )
    )
    total_count = total_result.scalar() or 0

    pending_result = await db.execute(
        select(func.count(Assessment.id)).where(
            Assessment.created_by == current_user.id,
            Assessment.status.in_(["submitted", "under_review", "quote_pending"]),
        )
    )
    pending_count = pending_result.scalar() or 0

    accepted_result = await db.execute(
        select(func.count(Assessment.id)).where(
            Assessment.created_by == current_user.id, Assessment.status == "bound"
        )
    )
    accepted_count = accepted_result.scalar() or 0

    declined_result = await db.execute(
        select(func.count(Assessment.id)).where(
            Assessment.created_by == current_user.id, Assessment.status == "declined"
        )
    )
    declined_count = declined_result.scalar() or 0

    # Aggregate premium totals from quotes
    quoted_premium_result = await db.execute(
        select(func.coalesce(func.sum(Quote.quoted_premium), 0))
        .join(Assessment, Quote.assessment_id == Assessment.id)
        .where(Assessment.created_by == current_user.id)
    )
    total_premium_quoted = Decimal(str(quoted_premium_result.scalar() or 0))

    bound_premium_result = await db.execute(
        select(func.coalesce(func.sum(Quote.quoted_premium), 0))
        .join(Assessment, Quote.assessment_id == Assessment.id)
        .where(
            Assessment.created_by == current_user.id,
            Quote.status == "accepted",
        )
    )
    total_premium_bound = Decimal(str(bound_premium_result.scalar() or 0))

    # Win rate calculation
    total_decided = accepted_count + declined_count
    win_rate = (accepted_count / total_decided * 100) if total_decided > 0 else 0.0

    # Recent submissions (last 5)
    recent_result = await db.execute(
        select(Assessment)
        .where(Assessment.created_by == current_user.id)
        .order_by(Assessment.created_at.desc())
        .limit(5)
    )
    recent_assessments = recent_result.scalars().all()
    recent_submissions = [
        {
            "submission_id": str(a.id),
            "insured_name": a.insured_name,
            "status": a.status,
            "risk_category": a.risk_category,
            "sum_insured": a.sum_insured,
            "created_at": a.created_at.isoformat(),
        }
        for a in recent_assessments
    ]

    return BrokerDashboardStats(
        total_submissions=total_count,
        pending_quotes=pending_count,
        accepted_quotes=accepted_count,
        declined_quotes=declined_count,
        total_premium_quoted=total_premium_quoted,
        total_premium_bound=total_premium_bound,
        win_rate=win_rate,
        recent_submissions=recent_submissions,
    )


# ============================================================
# Broker Quotes
# ============================================================


@router.get("/quotes/{quote_id}")
async def get_quote(
    quote_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single quote's details.
    """
    if current_user.role != UserRole.BROKER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only brokers can view quotes",
        )

    result = await db.execute(select(Quote).where(Quote.id == quote_id))
    quote = result.scalar_one_or_none()

    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found"
        )

    # Verify the broker owns the linked assessment
    assessment_result = await db.execute(
        select(Assessment).where(
            Assessment.id == quote.assessment_id,
            Assessment.created_by == current_user.id,
        )
    )
    assessment = assessment_result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this quote",
        )

    return {
        "quote_id": quote.id,
        "submission_id": str(quote.assessment_id),
        "quote_reference": quote.quote_reference,
        "premium": float(quote.quoted_premium) if quote.quoted_premium else 0,
        "currency": quote.currency or "GBP",
        "deductible": quote.terms.get("deductible", 0) if quote.terms else 0,
        "coverage": quote.terms.get("coverage", "") if quote.terms else "",
        "terms": quote.terms or {},
        "conditions": quote.conditions or [],
        "subjectivities": quote.subjectivities or [],
        "exclusions": quote.exclusions or [],
        "valid_from": quote.valid_from.isoformat() if quote.valid_from else None,
        "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
        "expires_at": quote.valid_until.isoformat() if quote.valid_until else None,
        "status": quote.status,
        "created_at": quote.created_at.isoformat() if quote.created_at else None,
        "accepted_at": quote.accepted_at.isoformat() if quote.accepted_at else None,
    }


@router.post("/quotes/{quote_id}/accept")
async def accept_quote(
    quote_id: int,
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
    quote_id: int,
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

    # Also update the assessment status to declined
    assessment_result = await db.execute(
        select(Assessment).where(Assessment.id == quote.assessment_id)
    )
    assessment = assessment_result.scalar_one_or_none()
    if assessment:
        assessment.status = "declined"

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
            Assessment.id == submission_id, Assessment.created_by == current_user.id
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


# ============================================================
# Underwriter-facing endpoints (for broker submission workflow)
# ============================================================


@router.get("/all-submissions", response_model=list)
async def list_all_broker_submissions(
    status_filter: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all broker submissions for underwriters/admins.
    Only accessible by underwriter or admin roles.
    """
    if current_user.role not in [UserRole.UNDERWRITER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only underwriters and admins can view all submissions",
        )

    # Only get assessments created by brokers (status in broker workflow statuses)
    broker_statuses = [
        "submitted",
        "under_review",
        "quote_pending",
        "bound",
        "declined",
    ]
    query = select(Assessment).where(Assessment.status.in_(broker_statuses))

    if status_filter and status_filter != "all":
        query = query.where(Assessment.status == status_filter)

    query = (
        query.order_by(Assessment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    assessments = result.scalars().all()

    # Get broker user info for each submission
    submissions = []
    for a in assessments:
        # Get broker info
        broker_result = await db.execute(select(User).where(User.id == a.created_by))
        broker = broker_result.scalar_one_or_none()

        # Check if quote exists
        quote_result = await db.execute(
            select(Quote).where(Quote.assessment_id == a.id)
        )
        quote = quote_result.scalar_one_or_none()

        submissions.append(
            {
                "submission_id": str(a.id),
                "reference": f"INST/{a.created_at.strftime('%Y%m%d')}/{str(a.id)[-4:]}",
                "status": a.status,
                "insured_name": a.insured_name,
                "risk_category": a.risk_category,
                "sum_insured": a.sum_insured,
                "territory": a.territory,
                "created_at": a.created_at.isoformat(),
                "updated_at": a.updated_at.isoformat() if a.updated_at else None,
                "deadline": a.deadline.isoformat() if a.deadline else None,
                "has_analysis": a.ai_analysis is not None and bool(a.ai_analysis),
                "risk_score": a.risk_score,
                "decision": a.decision if a.decision else None,
                "has_quote": quote is not None,
                "broker": {
                    "id": str(broker.id) if broker else None,
                    "name": broker.full_name if broker else "Unknown",
                    "email": broker.email if broker else None,
                }
                if broker
                else None,
                "assigned_underwriter_id": str(a.assigned_underwriter_id)
                if a.assigned_underwriter_id
                else None,
                "upload_session_token": a.upload_session_token,
            }
        )

    return submissions


@router.get("/submissions/unread-count")
async def get_unread_submission_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get count of broker submissions needing attention (for sidebar badge).
    """
    if current_user.role not in [UserRole.UNDERWRITER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only underwriters and admins can view submission counts",
        )

    # Count submissions that need attention: submitted (new) or quote_pending (broker responded)
    result = await db.execute(
        select(func.count(Assessment.id)).where(
            Assessment.status.in_(["submitted", "quote_pending"])
        )
    )
    count = result.scalar() or 0

    return {"unread_count": count}


@router.get("/brokers", response_model=list)
async def list_brokers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all registered brokers with stats.
    Only accessible by underwriter or admin roles.
    """
    if current_user.role not in [UserRole.UNDERWRITER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only underwriters and admins can view brokers",
        )

    result = await db.execute(
        select(User)
        .where(User.role == UserRole.BROKER)
        .order_by(User.created_at.desc())
    )
    brokers = result.scalars().all()

    broker_list = []
    for broker in brokers:
        # Get submission count for this broker
        count_result = await db.execute(
            select(func.count(Assessment.id)).where(Assessment.created_by == broker.id)
        )
        submission_count = count_result.scalar() or 0

        # Get bound count for win rate
        bound_result = await db.execute(
            select(func.count(Assessment.id)).where(
                Assessment.created_by == broker.id,
                Assessment.status == "bound",
            )
        )
        bound_count = bound_result.scalar() or 0

        broker_list.append(
            {
                "id": str(broker.id),
                "email": broker.email,
                "full_name": broker.full_name,
                "approval_status": broker.approval_status.value
                if broker.approval_status
                else "pending",
                "is_active": broker.is_active,
                "created_at": broker.created_at.isoformat()
                if broker.created_at
                else None,
                "last_login": broker.last_login.isoformat()
                if broker.last_login
                else None,
                "submission_count": submission_count,
                "bound_count": bound_count,
            }
        )

    return broker_list


@router.put("/brokers/{broker_id}/approve")
async def approve_broker(
    broker_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending broker."""
    if current_user.role not in [UserRole.UNDERWRITER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only underwriters and admins can approve brokers",
        )

    result = await db.execute(
        select(User).where(User.id == broker_id, User.role == UserRole.BROKER)
    )
    broker = result.scalar_one_or_none()

    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")

    broker.approval_status = ApprovalStatus.APPROVED
    broker.is_active = True
    broker.approved_by = current_user.id
    broker.approved_at = datetime.now()

    await db.commit()
    return {"message": "Broker approved", "broker_id": broker_id}


@router.put("/brokers/{broker_id}/reject")
async def reject_broker(
    broker_id: str,
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending broker."""
    if current_user.role not in [UserRole.UNDERWRITER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only underwriters and admins can reject brokers",
        )

    result = await db.execute(
        select(User).where(User.id == broker_id, User.role == UserRole.BROKER)
    )
    broker = result.scalar_one_or_none()

    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")

    broker.approval_status = ApprovalStatus.REJECTED
    broker.is_active = False
    broker.rejection_reason = reason

    await db.commit()
    return {"message": "Broker rejected", "broker_id": broker_id}


@router.post(
    "/submissions/{submission_id}/push-to-analysis",
    status_code=status.HTTP_202_ACCEPTED,
)
async def push_submission_to_analysis(
    submission_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Push a broker submission through the AI analysis pipeline.
    Must be assigned to the current underwriter first (status: under_review).
    Reuses the existing run_ai_analysis background task.
    """
    if current_user.role not in [UserRole.UNDERWRITER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only underwriters and admins can trigger analysis",
        )

    result = await db.execute(select(Assessment).where(Assessment.id == submission_id))
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(status_code=404, detail="Submission not found")

    if assessment.status not in ["submitted", "under_review"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot push to analysis: submission is in status '{assessment.status}'",
        )

    # Import the shared background task from assessments router
    from app.routers.assessments import run_ai_analysis

    background_tasks.add_task(
        run_ai_analysis, assessment.id, user_id=str(current_user.id)
    )

    # Update status to under_review if still submitted
    if assessment.status == "submitted":
        assessment.status = "under_review"
    await db.commit()

    return {
        "message": "AI analysis queued",
        "submission_id": submission_id,
        "status": assessment.status,
    }


@router.post("/submissions/{submission_id}/assign")
async def assign_underwriter(
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Assign current underwriter to a broker submission.
    Changes status from 'submitted' to 'under_review'.
    """
    if current_user.role not in [UserRole.UNDERWRITER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only underwriters and admins can be assigned to submissions",
        )

    result = await db.execute(select(Assessment).where(Assessment.id == submission_id))
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(status_code=404, detail="Submission not found")

    assessment.assigned_underwriter_id = current_user.id
    if assessment.status == "submitted":
        assessment.status = "under_review"

    await db.commit()

    return {
        "message": "Underwriter assigned",
        "submission_id": submission_id,
        "assigned_to": str(current_user.id),
        "status": assessment.status,
    }


class CreateQuoteRequest(BaseModel):
    """Request to create a quote for a broker submission."""

    assessment_id: str
    quoted_premium: Decimal = Field(..., gt=0)
    currency: str = "GBP"
    deductible: Optional[Decimal] = None
    conditions: Optional[list] = None
    subjectivities: Optional[list] = None
    exclusions: Optional[list] = None
    terms: Optional[dict] = None
    validity_days: int = Field(default=30, gt=0)


@router.post("/create-quote", status_code=status.HTTP_201_CREATED)
async def create_quote_for_submission(
    request: CreateQuoteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a quote for a broker submission (underwriter action).
    """
    if current_user.role not in [UserRole.UNDERWRITER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only underwriters and admins can create quotes",
        )

    # Verify the assessment exists
    result = await db.execute(
        select(Assessment).where(Assessment.id == request.assessment_id)
    )
    assessment = result.scalar_one_or_none()

    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Generate quote reference
    import uuid as uuid_mod

    ref_date = datetime.now().strftime("%Y%m%d")
    ref_hex = uuid_mod.uuid4().hex[:6].upper()
    quote_reference = f"QT-{ref_date}-{ref_hex}"

    # Build terms dict
    terms = request.terms or {}
    if request.deductible is not None:
        terms["deductible"] = float(request.deductible)

    quote = Quote(
        assessment_id=request.assessment_id,
        quote_reference=quote_reference,
        quoted_premium=request.quoted_premium,
        currency=request.currency,
        terms=terms,
        conditions=request.conditions or [],
        subjectivities=request.subjectivities or [],
        exclusions=request.exclusions or [],
        valid_from=datetime.now(),
        valid_until=datetime.now() + timedelta(days=request.validity_days),
        status="quoted",
        issued_at=datetime.now(),
    )

    db.add(quote)

    # Update assessment status to quote_pending
    assessment.status = "quote_pending"

    await db.commit()
    await db.refresh(quote)

    return {
        "message": "Quote created successfully",
        "quote_id": quote.id,
        "quote_reference": quote_reference,
        "status": "quoted",
        "assessment_id": request.assessment_id,
    }


class UpdateCommissionRequest(BaseModel):
    """Request to update a broker's default commission rate."""

    commission_rate: float = Field(
        ..., ge=0, le=100, description="Commission rate as percentage (0-100)"
    )


@router.put("/brokers/{broker_id}/commission")
async def update_broker_commission(
    broker_id: str,
    request: UpdateCommissionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the default commission rate for a broker (underwriter/admin action)."""
    if current_user.role not in [UserRole.UNDERWRITER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only underwriters and admins can update commission rates",
        )

    result = await db.execute(
        select(User).where(User.id == broker_id, User.role == UserRole.BROKER)
    )
    broker = result.scalar_one_or_none()

    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")

    broker.commission_rate = request.commission_rate
    await db.commit()

    return {
        "message": "Commission rate updated",
        "broker_id": broker_id,
        "commission_rate": request.commission_rate,
    }
