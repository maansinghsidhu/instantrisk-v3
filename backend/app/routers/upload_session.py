"""Upload Session Router - QR Code Document Upload"""
import json, uuid, os, logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, BackgroundTasks, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db, AsyncSessionLocal
from app.core.security import get_current_user
from app.models.user import User
from app.models.upload_session import UploadSession
from app.models.assessment import Assessment, AssessmentStatus, AssessmentDecision, RiskCategory
from app.models.document import Document, DocumentStatus, DocumentType
from app.services.document_processor import document_processor
import hashlib
import asyncio

# Security imports
from app.utils import validate_file, FileValidationError, scan_file_content, sanitize_filename
from app.middleware import log_file_blocked, log_malware_detected

router = APIRouter()

# Use settings for upload directory (works on both EC2 and Fargate)
from app.config import settings
UPLOAD_DIR = settings.resolved_upload_dir
BASE_URL = "https://d2f065h47nuk0c.cloudfront.net"

def is_expired(expires_at):
    """Check if session is expired (handles both naive and aware datetimes)."""
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return now > expires_at

def _safe_float(val):
    """Safely convert a value to float. Handles dicts, strings, None."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, dict):
        # Try common keys for nested values
        for key in ['amount', 'value', 'total', 'main']:
            if key in val:
                return _safe_float(val[key])
        # If dict has numeric values, sum them or take first
        numeric_vals = [v for v in val.values() if isinstance(v, (int, float))]
        if numeric_vals:
            return float(sum(numeric_vals))
        return None
    if isinstance(val, str):
        try:
            return float(val.replace(',', '').replace(' ', ''))
        except ValueError:
            return None
    return None

@router.post("/")
@router.post("/create")
async def create_session(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    token = UploadSession.generate_token()
    session = UploadSession(token=token, user_id=current_user.id, status="waiting",
                           expires_at=UploadSession.get_expiry(30), documents_json="[]")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"id": session.id, "token": token, "qr_url": f"{BASE_URL}/upload/{token}",
            "deep_link": f"instantrisk://upload/{token}", "expires_at": session.expires_at.isoformat()}

from fastapi import Header
from typing import Optional

async def get_optional_user_id(authorization: Optional[str] = Header(None)) -> Optional[int]:
    """Extract user ID from optional auth token."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        from app.core.security import decode_token
        token = authorization.replace("Bearer ", "")
        payload = decode_token(token)
        user_id = payload.get("sub")
        return user_id if user_id else None
    except:
        return None

@router.post("/demo")
async def create_demo_session(
    db: AsyncSession = Depends(get_db),
    user_id: Optional[int] = Depends(get_optional_user_id)
):
    """Create upload session - uses authenticated user if available, else defaults to user 1"""
    token = UploadSession.generate_token()
    actual_user_id = user_id if user_id else 1

    session = UploadSession(token=token, user_id=actual_user_id, status="waiting",
                           expires_at=UploadSession.get_expiry(30), documents_json="[]")
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"id": session.id, "token": token, "qr_url": f"{BASE_URL}/upload/{token}",
            "deep_link": f"instantrisk://upload/{token}", "expires_at": session.expires_at.isoformat()}

# ========== PUBLIC ENDPOINTS (No Auth Required) ==========
# These endpoints are used by mobile users scanning QR codes without logging in

@router.get("/{token}/validate-public")
async def validate_session_public(token: str, db: AsyncSession = Depends(get_db)):
    """Public validation - no auth required for QR scanned sessions."""
    result = await db.execute(select(UploadSession).where(UploadSession.token == token))
    session = result.scalar_one_or_none()
    if not session: raise HTTPException(404, "Session not found")
    if is_expired(session.expires_at): raise HTTPException(410, "Session expired")
    if session.status == "complete": raise HTTPException(410, "Session already completed")
    return {"valid": True, "status": session.status, "expires_at": session.expires_at.isoformat()}

@router.post("/{token}/upload-public")
async def upload_doc_public(token: str, request: Request, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """Public upload - no auth required, validates token instead."""
    result = await db.execute(select(UploadSession).where(UploadSession.token == token))
    session = result.scalar_one_or_none()
    if not session: raise HTTPException(404, "Session not found")
    if is_expired(session.expires_at): raise HTTPException(410, "Session expired")
    if session.status == "complete": raise HTTPException(410, "Session already completed")

    # Get client IP for logging
    client_ip = getattr(request.state, "client_ip", request.client.host if request.client else "unknown")

    # Sanitize filename
    safe_filename = sanitize_filename(file.filename)
    ext = os.path.splitext(safe_filename)[1] or ".jpg"

    # Read file content
    content = await file.read()

    # Security validation: MIME type, embedded scripts, macros
    try:
        await validate_file(content, safe_filename)
    except FileValidationError as e:
        await log_file_blocked(safe_filename, e.message, client_ip, session.user_id)
        raise HTTPException(400, f"File validation failed: {e.message}")

    # Antivirus scan
    is_clean, scan_message = await scan_file_content(content, safe_filename)
    if not is_clean:
        await log_malware_detected(safe_filename, scan_message, client_ip, session.user_id)
        logger.critical(f"MALWARE BLOCKED: {safe_filename} from session {token} - {scan_message}")
        raise HTTPException(400, "File rejected: potential security threat detected")

    session_dir = os.path.join(UPLOAD_DIR, token)
    os.makedirs(session_dir, exist_ok=True)
    doc_id = uuid.uuid4().hex[:8]
    filename = f"{doc_id}{ext}"
    with open(os.path.join(session_dir, filename), "wb") as f:
        f.write(content)

    docs = json.loads(session.documents_json)
    docs.append({"id": doc_id, "filename": safe_filename, "url": f"{BASE_URL}/uploads/{token}/{filename}",
                 "uploaded_at": datetime.now(timezone.utc).isoformat()})
    session.documents_json = json.dumps(docs)
    session.status = "uploading"
    await db.commit()
    return {"success": True, "document_id": doc_id, "filename": safe_filename,
            "url": f"{BASE_URL}/uploads/{token}/{filename}", "total_documents": len(docs)}

@router.get("/{token}/status-public")
async def get_status_public(token: str, db: AsyncSession = Depends(get_db)):
    """Public status check - no auth required."""
    result = await db.execute(select(UploadSession).where(UploadSession.token == token))
    session = result.scalar_one_or_none()
    if not session: raise HTTPException(404, "Session not found")
    docs = json.loads(session.documents_json)
    return {"status": session.status, "document_count": len(docs), "documents": docs,
            "expires_at": session.expires_at.isoformat()}

@router.post("/{token}/complete-public")
async def complete_session_public(token: str, db: AsyncSession = Depends(get_db)):
    """Public completion - no auth required."""
    result = await db.execute(select(UploadSession).where(UploadSession.token == token))
    session = result.scalar_one_or_none()
    if not session: raise HTTPException(404, "Session not found")
    if is_expired(session.expires_at): raise HTTPException(410, "Session expired")
    session.status = "complete"
    session.completed_at = datetime.now(timezone.utc)
    await db.commit()
    docs = json.loads(session.documents_json)
    return {"message": "Upload complete! Return to desktop to continue.", "document_count": len(docs)}

# ========== AUTHENTICATED ENDPOINTS ==========

@router.get("/{token}/validate")
async def validate_session(token: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(UploadSession).where(UploadSession.token == token))
    session = result.scalar_one_or_none()
    if not session: raise HTTPException(404, "Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(403, "Access denied to this session")
    if is_expired(session.expires_at): raise HTTPException(410, "Session expired")
    if session.status == "complete": raise HTTPException(410, "Session completed")
    return {"valid": True, "user_id": str(session.user_id)}

@router.post("/{token}/upload")
async def upload_doc(token: str, request: Request, file: UploadFile = File(...), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(UploadSession).where(UploadSession.token == token))
    session = result.scalar_one_or_none()
    if not session: raise HTTPException(404, "Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(403, "Access denied to this session")
    if is_expired(session.expires_at): raise HTTPException(410, "Session expired")

    # Get client IP for logging
    client_ip = getattr(request.state, "client_ip", request.client.host if request.client else "unknown")

    # Sanitize filename
    safe_filename = sanitize_filename(file.filename)
    ext = os.path.splitext(safe_filename)[1] or ".jpg"

    # Read file content
    content = await file.read()

    # Security validation: MIME type, embedded scripts, macros
    try:
        await validate_file(content, safe_filename)
    except FileValidationError as e:
        await log_file_blocked(safe_filename, e.message, client_ip, current_user.id)
        raise HTTPException(400, f"File validation failed: {e.message}")

    # Antivirus scan
    is_clean, scan_message = await scan_file_content(content, safe_filename)
    if not is_clean:
        await log_malware_detected(safe_filename, scan_message, client_ip, current_user.id)
        logger.critical(f"MALWARE BLOCKED: {safe_filename} from user {current_user.id} - {scan_message}")
        raise HTTPException(400, "File rejected: potential security threat detected")

    session_dir = os.path.join(UPLOAD_DIR, token)
    os.makedirs(session_dir, exist_ok=True)
    doc_id = uuid.uuid4().hex[:8]
    filename = f"{doc_id}{ext}"
    with open(os.path.join(session_dir, filename), "wb") as f:
        f.write(content)

    docs = json.loads(session.documents_json)
    docs.append({"id": doc_id, "filename": safe_filename, "url": f"{BASE_URL}/uploads/{token}/{filename}",
                 "uploaded_at": datetime.now(timezone.utc).isoformat()})
    session.documents_json = json.dumps(docs)
    session.status = "uploading"
    await db.commit()
    return {"success": True, "document_id": doc_id, "url": f"{BASE_URL}/uploads/{token}/{filename}"}

@router.get("/{token}/status")
async def get_status(token: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(UploadSession).where(UploadSession.token == token))
    session = result.scalar_one_or_none()
    if not session: raise HTTPException(404, "Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(403, "Access denied to this session")
    docs = json.loads(session.documents_json)
    status_map = {"processed": "completed", "error": "failed", "processing": "processing"}
    mapped_status = status_map.get(session.status, session.status)
    resp = {"status": mapped_status, "document_count": len(docs), "documents": docs}
    if mapped_status == "completed" and session.assessment_id:
        resp["assessment_id"] = session.assessment_id
        if session.analysis_json:
            analysis = json.loads(session.analysis_json)
            resp["result"] = analysis
    return resp

@router.post("/{token}/complete")
async def complete_session(token: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(UploadSession).where(UploadSession.token == token))
    session = result.scalar_one_or_none()
    if not session: raise HTTPException(404, "Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(403, "Access denied to this session")
    session.status = "complete"
    session.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Complete", "document_count": len(json.loads(session.documents_json))}

@router.post("/{token}/process")
async def process_documents(
    token: str,
    mode: str = Query("go_no_go", description="Analysis mode: quick, go_no_go, or deep"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Process uploaded documents with AI and extract insurance information.

    Mode determines analysis depth:
    - quick: Fast classification and decision (2 agents)
    - go_no_go: Standard analysis with extraction (3 agents)
    - deep: Comprehensive risk analysis (5 agents)
    """
    result = await db.execute(select(UploadSession).where(UploadSession.token == token))
    session = result.scalar_one_or_none()
    if not session: raise HTTPException(404, "Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(403, "Access denied to this session")

    # Allow retry if previous attempt failed (status is 'error' or 'processing' stuck)
    if session.status == "processed":
        raise HTTPException(400, "Session already processed")

    docs = json.loads(session.documents_json)
    if not docs:
        raise HTTPException(400, "No documents to process")

    # Get file paths for all uploaded documents
    session_dir = os.path.join(UPLOAD_DIR, token)
    file_paths = []
    for doc in docs:
        # Extract filename from URL
        filename = doc["url"].split("/")[-1]
        file_path = os.path.join(session_dir, filename)
        if os.path.exists(file_path):
            file_paths.append(file_path)

    if not file_paths:
        raise HTTPException(400, "No document files found")

    # Generate reference number and create Assessment immediately with IN_PROGRESS status
    ref_number = f"IR-{datetime.now().strftime('%Y%m%d')}-{token[:8].upper()}"

    # Get first document name for initial title
    first_doc_name = docs[0].get("name", "Document") if docs else "Document"

    assessment = Assessment(
        reference_number=ref_number,
        title=f"Processing: {first_doc_name[:80]}",
        description="Document analysis in progress...",
        risk_category=RiskCategory.PROPERTY,  # Default, will be updated
        status=AssessmentStatus.IN_PROGRESS,
        decision=AssessmentDecision.PENDING,
        created_by=session.user_id or 1,
    )
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)

    # Link session to assessment
    session.assessment_id = assessment.id
    session.status = "processing"
    await db.commit()

    # Analyze documents with selected mode - wrapped in try-except
    try:
        if len(file_paths) == 1:
            analysis = await document_processor.analyze_document(file_paths[0], mode=mode)
        else:
            analysis = await document_processor.analyze_multiple_documents(file_paths, mode=mode)
    except Exception as e:
        # On error, reset session status and mark assessment as failed
        session.status = "error"
        assessment.status = AssessmentStatus.FAILED
        assessment.description = f"Analysis failed: {str(e)}"
        await db.commit()
        raise HTTPException(500, f"Analysis failed: {str(e)}")

    # Store analysis in session
    session.analysis_json = json.dumps(analysis)
    session.status = "processed"

    # Map risk_type to RiskCategory - expanded for better detection
    risk_type_map = {
        # Property variations
        "property": RiskCategory.PROPERTY,
        "building": RiskCategory.PROPERTY,
        "fire": RiskCategory.PROPERTY,
        "motor": RiskCategory.PROPERTY,
        "auto": RiskCategory.PROPERTY,
        # Casualty/Liability
        "liability": RiskCategory.CASUALTY,
        "casualty": RiskCategory.CASUALTY,
        "public": RiskCategory.CASUALTY,
        "employers": RiskCategory.CASUALTY,
        # Marine
        "marine": RiskCategory.MARINE,
        "cargo": RiskCategory.MARINE,
        "hull": RiskCategory.MARINE,
        "vessel": RiskCategory.MARINE,
        # Aviation
        "aviation": RiskCategory.AVIATION,
        "aircraft": RiskCategory.AVIATION,
        "aerospace": RiskCategory.AVIATION,
        # Energy
        "energy": RiskCategory.ENERGY,
        "oil": RiskCategory.ENERGY,
        "gas": RiskCategory.ENERGY,
        "power": RiskCategory.ENERGY,
        # Cyber
        "cyber": RiskCategory.CYBER,
        "technology": RiskCategory.CYBER,
        "data": RiskCategory.CYBER,
        # Financial Lines
        "financial": RiskCategory.FINANCIAL_LINES,
        "financial_lines": RiskCategory.FINANCIAL_LINES,
        "professional": RiskCategory.FINANCIAL_LINES,
        "directors": RiskCategory.FINANCIAL_LINES,
        "d&o": RiskCategory.FINANCIAL_LINES,
        "pi": RiskCategory.FINANCIAL_LINES,
        "e&o": RiskCategory.FINANCIAL_LINES,
        # Specialty
        "specialty": RiskCategory.SPECIALTY,
        "reinsurance": RiskCategory.SPECIALTY,
        "treaty": RiskCategory.SPECIALTY,
    }
    risk_type_str = (analysis.get("risk_type") or "property").lower()
    risk_category = RiskCategory.PROPERTY
    # First try exact match
    if risk_type_str in risk_type_map:
        risk_category = risk_type_map[risk_type_str]
    else:
        # Then try substring match
        for key, val in risk_type_map.items():
            if key in risk_type_str:
                risk_category = val
                break

    # Extract AI agent results for detailed analysis (handle None values)
    agent_results = analysis.get("agent_results") or {}
    underwriter_result = agent_results.get("underwriter") or {}
    risk_analyst_result = agent_results.get("risk_analyst") or {}
    qa_result = agent_results.get("qa") or {}

    # Get confidence and validity (handle bad AI values)
    raw_confidence = analysis.get("confidence_score", 0.5)
    try:
        confidence = float(raw_confidence) if raw_confidence is not None else 0.5
        confidence = max(0.0, min(1.0, confidence))  # Clamp to 0-1 range
    except (ValueError, TypeError):
        confidence = 0.5
    is_valid_doc = analysis.get("is_valid_insurance_doc", True)

    # Use AI underwriter's decision if available, otherwise determine from confidence
    ai_decision = underwriter_result.get("decision", "").upper() if underwriter_result else ""

    if ai_decision == "GO":
        decision = AssessmentDecision.GO
    elif ai_decision in ("NO_GO", "REFER"):
        decision = AssessmentDecision.NO_GO
    elif not is_valid_doc or confidence < 0.3:
        decision = AssessmentDecision.NO_GO
    elif confidence > 0.5:
        decision = AssessmentDecision.GO
    else:
        decision = AssessmentDecision.NO_GO

    # Build comprehensive decision rationale from AI analysis
    rationale_parts = []

    # Main decision rationale from underwriter
    if underwriter_result.get("decision_rationale"):
        rationale_parts.append(f"**Underwriting Decision:** {underwriter_result['decision_rationale']}")

    # Appetite check
    appetite = underwriter_result.get("appetite_check", {})
    if appetite.get("appetite_notes"):
        rationale_parts.append(f"**Appetite Assessment:** {appetite['appetite_notes']}")

    # Pricing assessment
    pricing = underwriter_result.get("pricing_assessment", {})
    if pricing:
        pricing_notes = []
        if pricing.get("price_adequacy"):
            pricing_notes.append(f"Price Adequacy: {pricing['price_adequacy']}")
        if pricing.get("technical_price"):
            pricing_notes.append(f"Technical Price: {pricing['technical_price']}")
        if pricing.get("combined_ratio_projection"):
            pricing_notes.append(f"Combined Ratio: {pricing['combined_ratio_projection']}")
        if pricing_notes:
            rationale_parts.append(f"**Pricing Analysis:** {'; '.join(pricing_notes)}")

    # Terms review
    terms = underwriter_result.get("terms_review", {})
    if terms.get("suggested_amendments"):
        rationale_parts.append(f"**Suggested Amendments:** {', '.join(terms['suggested_amendments'][:3])}")
    if terms.get("mandatory_conditions"):
        rationale_parts.append(f"**Mandatory Conditions:** {', '.join(terms['mandatory_conditions'][:3])}")

    # Decision-specific notes
    if decision == AssessmentDecision.GO and underwriter_result.get("if_go"):
        go_info = underwriter_result["if_go"]
        if go_info.get("special_instructions"):
            rationale_parts.append(f"**Instructions:** {go_info['special_instructions']}")
    elif decision == AssessmentDecision.NO_GO and underwriter_result.get("if_no_go"):
        no_go_info = underwriter_result["if_no_go"]
        if no_go_info.get("decline_reason"):
            rationale_parts.append(f"**Decline Reason:** {no_go_info['decline_reason']}")
        if no_go_info.get("could_reconsider_if"):
            rationale_parts.append(f"**Could Reconsider If:** {no_go_info['could_reconsider_if']}")

    # Risk analysis summary
    risk_profile = risk_analyst_result.get("risk_profile", {})
    if risk_profile.get("overall_risk_level"):
        rationale_parts.append(f"**Risk Level:** {risk_profile['overall_risk_level']} (Score: {risk_profile.get('risk_score', 'N/A')}/100)")

    # QA notes
    if qa_result.get("final_recommendations"):
        rationale_parts.append(f"**QA Recommendations:** {', '.join(qa_result['final_recommendations'][:3])}")

    # Fallback if no detailed rationale available
    if not rationale_parts:
        decision_text = "Approved" if decision == AssessmentDecision.GO else "Declined"
        rationale_parts.append(f"AI Confidence: {confidence:.0%}. {decision_text} based on automated analysis.")
        if not is_valid_doc:
            rationale_parts.append("Note: Document may not be a standard insurance document - manual review recommended.")

    decision_rationale = "\n\n".join(rationale_parts)

    # Get risk score from risk analyst if available (handle bad values)
    raw_risk_score = risk_profile.get("risk_score") if risk_profile else None
    try:
        risk_score = int(raw_risk_score) if raw_risk_score is not None else int(confidence * 100)
        risk_score = max(0, min(100, risk_score))  # Clamp to 0-100 range
    except (ValueError, TypeError):
        risk_score = int(confidence * 100)

    # Build recommendations from multiple sources
    recommendations = []
    if analysis.get("risk_factors"):
        recommendations.extend(analysis["risk_factors"][:5])
    if risk_analyst_result.get("risk_factors"):
        for rf in risk_analyst_result["risk_factors"][:3]:
            if isinstance(rf, dict) and rf.get("mitigation"):
                recommendations.append(rf["mitigation"])
            elif isinstance(rf, str):
                recommendations.append(rf)
    if qa_result.get("final_recommendations"):
        recommendations.extend(qa_result["final_recommendations"][:2])

    # Get full OCR text from analysis
    ocr_text = analysis.get("ocr_extracted_text") or analysis.get("ocr_text_preview") or ""

    # Update the existing Assessment record (created at start with IN_PROGRESS status)
    assessment.title = analysis.get("company_name") or analysis.get("insured_name") or analysis.get("coverage_details", "Document Analysis")[:100]
    assessment.description = analysis.get("coverage_details") or analysis.get("decision_rationale")
    assessment.risk_category = risk_category
    assessment.status = AssessmentStatus.COMPLETED
    assessment.decision = decision
    assessment.insured_name = analysis.get("company_name") or analysis.get("insured_name")
    assessment.premium = _safe_float(analysis.get("premium"))
    assessment.sum_insured = _safe_float(analysis.get("sum_insured"))
    assessment.deductible = _safe_float(analysis.get("deductible"))
    assessment.territory = analysis.get("territory") or analysis.get("location")
    assessment.risk_score = risk_score  # Already validated above
    assessment.confidence_score = int(confidence * 100)
    assessment.ai_analysis = analysis
    assessment.ai_recommendations = recommendations[:10] if recommendations else []
    assessment.decision_rationale = decision_rationale
    assessment.ocr_extracted_text = ocr_text  # Store full OCR text
    assessment.completed_at = datetime.now(timezone.utc)
    await db.commit()

    # Create Document records for each uploaded file
    doc_type_map = {
        "slip": DocumentType.SLIP,
        "policy": DocumentType.POLICY,
        "endorsement": DocumentType.ENDORSEMENT,
        "claim": DocumentType.CLAIM,
        "survey": DocumentType.SURVEY_REPORT,
        "financial": DocumentType.FINANCIAL_STATEMENT,
    }
    detected_type = (analysis.get("document_type") or "other").lower()
    doc_type = DocumentType.OTHER
    for key, val in doc_type_map.items():
        if key in detected_type:
            doc_type = val
            break

    for i, file_path in enumerate(file_paths):
        try:
            # Get file info
            file_stat = os.stat(file_path)
            filename = os.path.basename(file_path)

            # Calculate checksum
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()

            # Determine mime type from extension
            ext = os.path.splitext(filename)[1].lower()
            mime_map = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
            mime_type = mime_map.get(ext, "application/octet-stream")

            # Create document record
            doc = Document(
                filename=docs[i].get("filename", filename) if i < len(docs) else filename,
                file_path=file_path,
                file_size=file_stat.st_size,
                mime_type=mime_type,
                document_type=doc_type,
                status=DocumentStatus.COMPLETED,
                uploaded_by=session.user_id or current_user.id,
                assessment_id=assessment.id,
                ocr_text=ocr_text[:10000] if ocr_text else None,  # Store first 10k chars
                ocr_confidence=confidence,
                extracted_data=analysis,
                checksum=file_hash,
                created_at=datetime.now(timezone.utc),
                processed_at=datetime.now(timezone.utc)
            )
            db.add(doc)
        except Exception as e:
            # Log but don't fail if document record creation fails
            print(f"Warning: Could not create document record for {file_path}: {e}")

    await db.commit()

    return {
        "success": True,
        "analysis": analysis,
        "documents_processed": len(file_paths),
        "assessment_id": assessment.id,
        "reference_number": ref_number
    }

# Background task for async analysis
async def _run_analysis_in_background(
    token: str,
    assessment_id: str,
    file_paths: list,
    mode: str,
    session_id: str,
    user_id: int
):
    """Run document analysis in background with WebSocket progress updates."""
    from app.routers.analysis import send_progress_update, create_progress_callback, AnalysisMode

    # Create new database session for background task
    async with AsyncSessionLocal() as db:
        try:
            # Get assessment
            result = await db.execute(select(Assessment).where(Assessment.id == assessment_id))
            assessment = result.scalar_one_or_none()
            if not assessment:
                await send_progress_update(session_id, {"type": "error", "message": "Assessment not found"})
                return

            # Get upload session
            session_result = await db.execute(select(UploadSession).where(UploadSession.token == token))
            session = session_result.scalar_one_or_none()

            # Create progress callback for WebSocket updates
            start_time = datetime.now()
            try:
                analysis_mode = AnalysisMode(mode)
            except ValueError:
                analysis_mode = AnalysisMode.GO_NO_GO

            progress_callback = await create_progress_callback(session_id, analysis_mode, start_time)

            # Run analysis with progress callback (with 5 minute timeout)
            try:
                if len(file_paths) == 1:
                    analysis = await asyncio.wait_for(
                        document_processor.analyze_document(
                            file_paths[0],
                            mode=mode,
                            progress_callback=progress_callback
                        ),
                        timeout=600.0  # 10 minute timeout
                    )
                else:
                    analysis = await asyncio.wait_for(
                        document_processor.analyze_multiple_documents(
                            file_paths,
                            mode=mode,
                            progress_callback=progress_callback
                        ),
                        timeout=600.0  # 10 minute timeout
                    )
            except Exception as e:
                # On error, reset session status and mark assessment as failed
                import traceback
                logger.error(f"Analysis exception: {e}\n{traceback.format_exc()}")
                if session:
                    session.status = "error"
                assessment.status = AssessmentStatus.FAILED
                assessment.description = f"Analysis failed: {str(e)}"
                await db.commit()
                await send_progress_update(session_id, {"type": "error", "message": str(e)})
                return

            # Handle None or empty analysis result
            if not analysis or not isinstance(analysis, dict):
                logger.error(f"Analysis returned None or invalid result")
                analysis = {
                    "is_valid_insurance_doc": True,
                    "document_type": "UNKNOWN",
                    "confidence_score": 0.3,
                    "risk_type": "property",
                    "agent_results": {},
                    "error": "Analysis returned no result - using fallback"
                }

            # Add analysis mode to results for frontend access
            analysis["analysis_mode"] = mode

            # Store analysis in session
            if session:
                session.analysis_json = json.dumps(analysis)
                session.status = "processed"

            # Map risk_type to RiskCategory - expanded for better detection
            risk_type_map = {
                # Property variations
                "property": RiskCategory.PROPERTY,
                "building": RiskCategory.PROPERTY,
                "fire": RiskCategory.PROPERTY,
                "motor": RiskCategory.PROPERTY,
                "auto": RiskCategory.PROPERTY,
                # Casualty/Liability
                "liability": RiskCategory.CASUALTY,
                "casualty": RiskCategory.CASUALTY,
                "public": RiskCategory.CASUALTY,
                "employers": RiskCategory.CASUALTY,
                # Marine
                "marine": RiskCategory.MARINE,
                "cargo": RiskCategory.MARINE,
                "hull": RiskCategory.MARINE,
                "vessel": RiskCategory.MARINE,
                # Aviation
                "aviation": RiskCategory.AVIATION,
                "aircraft": RiskCategory.AVIATION,
                "aerospace": RiskCategory.AVIATION,
                # Energy
                "energy": RiskCategory.ENERGY,
                "oil": RiskCategory.ENERGY,
                "gas": RiskCategory.ENERGY,
                "power": RiskCategory.ENERGY,
                # Cyber
                "cyber": RiskCategory.CYBER,
                "technology": RiskCategory.CYBER,
                "data": RiskCategory.CYBER,
                # Financial Lines
                "financial": RiskCategory.FINANCIAL_LINES,
                "financial_lines": RiskCategory.FINANCIAL_LINES,
                "professional": RiskCategory.FINANCIAL_LINES,
                "directors": RiskCategory.FINANCIAL_LINES,
                "d&o": RiskCategory.FINANCIAL_LINES,
                "pi": RiskCategory.FINANCIAL_LINES,
                "e&o": RiskCategory.FINANCIAL_LINES,
                # Specialty
                "specialty": RiskCategory.SPECIALTY,
                "reinsurance": RiskCategory.SPECIALTY,
                "treaty": RiskCategory.SPECIALTY,
            }
            risk_type_str = (analysis.get("risk_type") or "property").lower()
            risk_category = RiskCategory.PROPERTY
            # First try exact match
            if risk_type_str in risk_type_map:
                risk_category = risk_type_map[risk_type_str]
            else:
                # Then try substring match
                for key, val in risk_type_map.items():
                    if key in risk_type_str:
                        risk_category = val
                        break

            # Extract AI agent results
            agent_results = analysis.get("agent_results") or {}
            underwriter_result = agent_results.get("underwriter") or {}
            risk_analyst_result = agent_results.get("risk_analyst") or {}
            qa_result = agent_results.get("qa") or {}

            # Get confidence
            raw_confidence = analysis.get("confidence_score", 0.5)
            try:
                confidence = float(raw_confidence) if raw_confidence is not None else 0.5
                confidence = max(0.0, min(1.0, confidence))
            except (ValueError, TypeError):
                confidence = 0.5
            is_valid_doc = analysis.get("is_valid_insurance_doc", True)

            # Determine decision
            ai_decision = underwriter_result.get("decision", "").upper() if underwriter_result else ""

            if ai_decision == "GO":
                decision = AssessmentDecision.GO
            elif ai_decision in ("NO_GO", "REFER"):
                decision = AssessmentDecision.NO_GO
            elif not is_valid_doc or confidence < 0.3:
                decision = AssessmentDecision.NO_GO
            elif confidence > 0.5:
                decision = AssessmentDecision.GO
            else:
                decision = AssessmentDecision.NO_GO

            # Build rationale
            rationale_parts = []
            if underwriter_result.get("decision_rationale"):
                rationale_parts.append(f"**Underwriting Decision:** {underwriter_result['decision_rationale']}")
            appetite = underwriter_result.get("appetite_check", {})
            if appetite.get("appetite_notes"):
                rationale_parts.append(f"**Appetite Assessment:** {appetite['appetite_notes']}")
            if not rationale_parts:
                decision_text = "Approved" if decision == AssessmentDecision.GO else "Declined"
                rationale_parts.append(f"AI Confidence: {confidence:.0%}. {decision_text} based on automated analysis.")
            decision_rationale = "\n\n".join(rationale_parts)

            # Get risk score
            risk_profile = risk_analyst_result.get("risk_profile", {}) if risk_analyst_result else {}
            raw_risk_score = risk_profile.get("risk_score") if risk_profile else None
            try:
                risk_score = int(raw_risk_score) if raw_risk_score is not None else int(confidence * 100)
                risk_score = max(0, min(100, risk_score))
            except (ValueError, TypeError):
                risk_score = int(confidence * 100)

            # Build recommendations
            recommendations = []
            if analysis.get("risk_factors"):
                recommendations.extend(analysis["risk_factors"][:5])
            if risk_analyst_result and risk_analyst_result.get("risk_factors"):
                for rf in risk_analyst_result["risk_factors"][:3]:
                    if isinstance(rf, dict) and rf.get("mitigation"):
                        recommendations.append(rf["mitigation"])
                    elif isinstance(rf, str):
                        recommendations.append(rf)

            # Get OCR text
            ocr_text = analysis.get("ocr_extracted_text") or analysis.get("ocr_text_preview") or ""

            # Update assessment
            assessment.title = analysis.get("company_name") or analysis.get("insured_name") or analysis.get("coverage_details", "Document Analysis")[:100]
            assessment.description = analysis.get("coverage_details") or analysis.get("decision_rationale")
            assessment.risk_category = risk_category
            assessment.status = AssessmentStatus.COMPLETED
            assessment.decision = decision
            assessment.insured_name = analysis.get("company_name") or analysis.get("insured_name")
            assessment.premium = _safe_float(analysis.get("premium"))
            assessment.sum_insured = _safe_float(analysis.get("sum_insured"))
            assessment.deductible = _safe_float(analysis.get("deductible"))
            assessment.territory = analysis.get("territory") or analysis.get("location")
            assessment.risk_score = risk_score
            assessment.confidence_score = int(confidence * 100)
            assessment.ai_analysis = analysis
            assessment.ai_recommendations = recommendations[:10] if recommendations else []
            assessment.decision_rationale = decision_rationale
            assessment.analysis_mode = mode  # Track which analysis depth was used
            assessment.ocr_extracted_text = ocr_text
            assessment.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Send completion message
            processing_time = (datetime.now() - start_time).total_seconds()
            await send_progress_update(session_id, {
                "type": "complete",
                "decision": decision.value if hasattr(decision, 'value') else str(decision),
                "confidence": confidence,
                "processing_time": int(processing_time),
                "assessment_id": assessment_id,
                "risk_score": risk_score
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            await send_progress_update(session_id, {"type": "error", "message": str(e)})


@router.post("/{token}/process-async")
async def process_documents_async(
    token: str,
    background_tasks: BackgroundTasks,
    mode: str = Query("go_no_go", description="Analysis mode: quick, go_no_go, or deep"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Process uploaded documents asynchronously with real-time WebSocket updates.

    Returns immediately with session_id for WebSocket connection.
    Connect to /api/v1/analysis/ws/{session_id} for progress updates.

    Mode determines analysis depth:
    - quick: Fast classification and decision (2 agents)
    - go_no_go: Standard analysis with extraction (3 agents)
    - deep: Comprehensive risk analysis (5 agents)
    """
    result = await db.execute(select(UploadSession).where(UploadSession.token == token))
    session = result.scalar_one_or_none()
    if not session: raise HTTPException(404, "Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(403, "Access denied to this session")

    if session.status == "processed":
        raise HTTPException(400, "Session already processed")

    docs = json.loads(session.documents_json)
    if not docs:
        raise HTTPException(400, "No documents to process")

    # Get file paths
    session_dir = os.path.join(UPLOAD_DIR, token)
    file_paths = []
    for doc in docs:
        filename = doc["url"].split("/")[-1]
        file_path = os.path.join(session_dir, filename)
        if os.path.exists(file_path):
            file_paths.append(file_path)

    if not file_paths:
        raise HTTPException(400, "No document files found")

    # Generate reference number and create Assessment with IN_PROGRESS status
    ref_number = f"IR-{datetime.now().strftime('%Y%m%d')}-{token[:8].upper()}"
    first_doc_name = docs[0].get("name", "Document") if docs else "Document"

    assessment = Assessment(
        reference_number=ref_number,
        title=f"Processing: {first_doc_name[:80]}",
        description="Document analysis in progress...",
        risk_category=RiskCategory.PROPERTY,
        status=AssessmentStatus.IN_PROGRESS,
        decision=AssessmentDecision.PENDING,
        created_by=session.user_id or 1,
    )
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)

    # Link session to assessment and update status
    session.assessment_id = assessment.id
    session.status = "processing"
    await db.commit()

    # Generate unique session_id for WebSocket
    ws_session_id = f"{token}-{assessment.id}"

    # Start background analysis
    asyncio.create_task(_run_analysis_in_background(
        token=token,
        assessment_id=assessment.id,
        file_paths=file_paths,
        mode=mode,
        session_id=ws_session_id,
        user_id=current_user.id
    ))

    return {
        "success": True,
        "session_id": ws_session_id,
        "assessment_id": assessment.id,
        "reference_number": ref_number,
        "websocket_url": f"/api/v1/analysis/ws/{ws_session_id}",
        "message": "Analysis started. Connect to WebSocket for progress updates."
    }


@router.get("/{token}/analysis")
async def get_analysis(token: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get the AI analysis results for a session."""
    result = await db.execute(select(UploadSession).where(UploadSession.token == token))
    session = result.scalar_one_or_none()
    if not session: raise HTTPException(404, "Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(403, "Access denied to this session")

    if not hasattr(session, 'analysis_json') or not session.analysis_json:
        return {"status": "not_processed", "analysis": None}

    return {
        "status": session.status,
        "analysis": json.loads(session.analysis_json),
        "documents": json.loads(session.documents_json)
    }
