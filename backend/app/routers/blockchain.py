"""
InstantRisk V2 - Blockchain / Smart Contract Router

Endpoints for issuing insurance policies as NFTs and processing
parametric claims on the Polygon blockchain.

All endpoints fall back to simulation mode when Polygon RPC is not
configured, returning realistic mock data for demos.

Routes:
    GET  /api/v1/blockchain/network          - Network info & contract status
    POST /api/v1/blockchain/policies/issue   - Mint policy NFT
    GET  /api/v1/blockchain/policies/{id}    - Fetch policy on-chain data
    POST /api/v1/blockchain/policies/{id}/cancel - Cancel policy NFT
    POST /api/v1/blockchain/claims           - Submit parametric claim
    GET  /api/v1/blockchain/claims/{id}      - Get claim status
    POST /api/v1/blockchain/claims/{id}/process - Process/pay a claim
    GET  /api/v1/blockchain/contracts/source - Return Solidity source
    GET  /api/v1/blockchain/contracts/deploy-guide - Deployment guide
"""

import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field, validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.assessment import Assessment
from app.services.smart_contract_service import get_smart_contract_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Request / Response Schemas
# ============================================================

class PolicyIssueRequest(BaseModel):
    """Request to mint a policy NFT on Polygon."""
    assessment_id: str = Field(..., description="InstantRisk assessment UUID")
    policy_id: str = Field(..., description="Policy reference, e.g. IRP-2026-001")
    holder_wallet: str = Field(
        default="0x0000000000000000000000000000000000000001",
        description="Insured party's Polygon wallet address",
    )
    premium_matic: float = Field(..., gt=0, description="Premium in MATIC tokens")
    sum_insured_matic: float = Field(..., gt=0, description="Sum insured in MATIC tokens")
    inception_date: str = Field(..., description="Policy start date (ISO 8601)")
    expiry_date: str = Field(..., description="Policy expiry date (ISO 8601)")


class PolicyIssueResponse(BaseModel):
    """Response after minting a policy NFT."""
    success: bool
    policy_id: str
    token_id: Optional[int]
    tx_hash: Optional[str]
    block_number: Optional[int]
    gas_used: Optional[int]
    simulated: bool
    message: str
    explorer_url: Optional[str]


class PolicyOnChainResponse(BaseModel):
    """On-chain policy data response."""
    found: bool
    policy_id: str
    token_id: Optional[int]
    premium_matic: Optional[float]
    sum_insured_matic: Optional[float]
    inception: Optional[str]
    expiry: Optional[str]
    active: Optional[bool]
    source: str


class ParametricClaimRequest(BaseModel):
    """Request to submit a parametric insurance claim."""
    policy_id: str = Field(..., description="Policy reference ID")
    trigger_type: str = Field(
        ...,
        description="Event trigger type: wind_speed_mph | earthquake_richter | rainfall_mm | flood_depth_cm",
    )
    trigger_value: float = Field(..., gt=0, description="Observed event value")
    claim_amount_matic: float = Field(..., gt=0, description="Requested payout in MATIC")
    oracle_source: Optional[str] = Field(None, description="Data source (e.g. NOAA, USGS)")
    event_date: Optional[str] = Field(None, description="Date of triggering event (ISO 8601)")
    notes: Optional[str] = Field(None, description="Additional claim notes")


class ClaimResponse(BaseModel):
    """Parametric claim response."""
    success: bool
    claim_id: Optional[int]
    policy_id: str
    trigger_type: str
    trigger_value: float
    claim_amount_matic: float
    status: str
    tx_hash: Optional[str]
    simulated: bool
    message: str
    explorer_url: Optional[str]


class ClaimStatusResponse(BaseModel):
    """Claim status response."""
    found: bool
    claim_id: int
    policy_id: Optional[str]
    trigger_type: Optional[str]
    trigger_value: Optional[float]
    claim_amount_matic: Optional[float]
    status: Optional[str]
    submitted_at: Optional[str]
    resolved_at: Optional[str]
    source: str


# ============================================================
# Helpers
# ============================================================

def _parse_iso_to_ts(date_str: str) -> int:
    """Parse ISO date string to Unix timestamp."""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except Exception:
        raise ValueError(f"Invalid date format: {date_str}. Use ISO 8601 (e.g. 2026-01-01T00:00:00Z)")


def _explorer_url(tx_hash: str, chain_id: int) -> Optional[str]:
    """Return blockchain explorer URL for a transaction."""
    if not tx_hash or tx_hash.startswith("0xaaa"):
        return None  # Simulated
    if chain_id == 137:
        return f"https://polygonscan.com/tx/{tx_hash}"
    return f"https://mumbai.polygonscan.com/tx/{tx_hash}"


# ============================================================
# Endpoints
# ============================================================

@router.get("/network", summary="Get blockchain network status")
async def get_network_info(
    current_user: User = Depends(get_current_user),
):
    """
    Returns Polygon network connection status and deployed contract addresses.
    Shows simulation mode details when live Polygon connection is not configured.
    """
    svc = get_smart_contract_service()
    info = await svc.get_network_info()
    return info


@router.post(
    "/policies/issue",
    response_model=PolicyIssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a policy as a blockchain NFT",
)
async def issue_policy_nft(
    req: PolicyIssueRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mints an ERC-721 PolicyNFT on Polygon representing this insurance policy.

    - In simulation mode: returns a realistic mock token ID and tx hash
    - In live mode: signs and broadcasts a real Polygon transaction

    The NFT contains: policy reference, premium, sum insured, inception/expiry dates.
    The token holder (insured) can verify their policy on any NFT explorer.
    """
    # Validate assessment exists
    result = await db.execute(
        select(Assessment).where(Assessment.id == req.assessment_id)
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment {req.assessment_id} not found",
        )

    # Parse dates
    try:
        inception_ts = _parse_iso_to_ts(req.inception_date)
        expiry_ts = _parse_iso_to_ts(req.expiry_date)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    if expiry_ts <= inception_ts:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Expiry must be after inception")

    svc = get_smart_contract_service()
    result_obj = await svc.issue_policy_nft(
        assessment_id=req.assessment_id,
        policy_id=req.policy_id,
        holder_wallet=req.holder_wallet,
        premium_matic=req.premium_matic,
        sum_insured_matic=req.sum_insured_matic,
        inception_ts=inception_ts,
        expiry_ts=expiry_ts,
    )

    if not result_obj.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result_obj.error or "Policy NFT minting failed",
        )

    chain_id = svc.config.chain_id
    explorer = _explorer_url(result_obj.tx_hash or "", chain_id) if result_obj.tx_hash else None

    return PolicyIssueResponse(
        success=True,
        policy_id=req.policy_id,
        token_id=result_obj.token_id,
        tx_hash=result_obj.tx_hash,
        block_number=result_obj.block_number,
        gas_used=result_obj.gas_used,
        simulated=result_obj.simulated,
        message=f"Policy NFT minted successfully (token #{result_obj.token_id})" + (
            " [SIMULATION]" if result_obj.simulated else ""
        ),
        explorer_url=explorer,
    )


@router.get(
    "/policies/{policy_id}",
    response_model=PolicyOnChainResponse,
    summary="Fetch policy data from blockchain",
)
async def get_policy_on_chain(
    policy_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves on-chain data for a policy NFT by its reference ID.
    Returns token ID, premium, sum insured, inception/expiry, and active status.
    """
    svc = get_smart_contract_service()
    data = await svc.get_policy_on_chain(policy_id)

    if not data:
        return PolicyOnChainResponse(
            found=False,
            policy_id=policy_id,
            source="blockchain" if not svc._simulation_mode else "simulation",
        )

    def _ts_to_iso(ts) -> Optional[str]:
        if not ts:
            return None
        if isinstance(ts, str):
            return ts  # Already ISO from simulation
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except Exception:
            return None

    return PolicyOnChainResponse(
        found=True,
        policy_id=policy_id,
        token_id=data.get("token_id"),
        premium_matic=data.get("premium_matic") or (
            data.get("premium_wei", 0) / 1e18 if data.get("premium_wei") else None
        ),
        sum_insured_matic=data.get("sum_insured_matic") or (
            data.get("sum_insured_wei", 0) / 1e18 if data.get("sum_insured_wei") else None
        ),
        inception=_ts_to_iso(data.get("inception")),
        expiry=_ts_to_iso(data.get("expiry")),
        active=data.get("active"),
        source=data.get("source", "unknown"),
    )


@router.post(
    "/policies/{policy_id}/cancel",
    summary="Cancel a policy NFT",
)
async def cancel_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Deactivates a policy NFT on the blockchain.
    Only callable by the contract operator (InstantRisk platform).
    The NFT remains in the holder's wallet but is marked inactive.
    """
    svc = get_smart_contract_service()
    result = await svc.cancel_policy(policy_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Cancel failed"),
        )
    return result


@router.post(
    "/claims",
    response_model=ClaimResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a parametric insurance claim",
)
async def submit_parametric_claim(
    req: ParametricClaimRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Submits an automated parametric insurance claim.

    Parametric triggers supported:
    - **wind_speed_mph**: Hurricane >= 74.0 mph triggers payout
    - **earthquake_richter**: Earthquake >= 6.0 triggers payout
    - **rainfall_mm**: Rainfall >= 150.0 mm/24h triggers payout
    - **flood_depth_cm**: Flood >= 100.0 cm depth triggers payout

    The smart contract validates the trigger threshold and auto-approves
    qualifying claims. No loss adjustment needed for parametric events.
    """
    svc = get_smart_contract_service()
    result = await svc.submit_parametric_claim(
        policy_id=req.policy_id,
        trigger_type=req.trigger_type,
        trigger_value=req.trigger_value,
        claim_amount_matic=req.claim_amount_matic,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Claim submission failed",
        )

    chain_id = svc.config.chain_id
    explorer = _explorer_url(result.tx_hash or "", chain_id) if result.tx_hash else None

    return ClaimResponse(
        success=True,
        claim_id=result.claim_id,
        policy_id=req.policy_id,
        trigger_type=req.trigger_type,
        trigger_value=req.trigger_value,
        claim_amount_matic=req.claim_amount_matic,
        status=result.status,
        tx_hash=result.tx_hash,
        simulated=result.simulated,
        message=f"Parametric claim #{result.claim_id} submitted and {result.status}" + (
            " [SIMULATION]" if result.simulated else ""
        ),
        explorer_url=explorer,
    )


@router.get(
    "/claims/{claim_id}",
    response_model=ClaimStatusResponse,
    summary="Get parametric claim status",
)
async def get_claim_status(
    claim_id: int,
    current_user: User = Depends(get_current_user),
):
    """
    Returns the current status of a parametric claim.
    Status values: pending | approved | paid | rejected
    """
    svc = get_smart_contract_service()
    data = await svc.get_claim_status(claim_id)

    if not data:
        return ClaimStatusResponse(
            found=False,
            claim_id=claim_id,
            source="blockchain" if not svc._simulation_mode else "simulation",
        )

    return ClaimStatusResponse(
        found=True,
        claim_id=claim_id,
        policy_id=data.get("policy_id"),
        trigger_type=data.get("trigger_type") or data.get("trigger"),
        trigger_value=data.get("trigger_value"),
        claim_amount_matic=data.get("claim_amount_matic"),
        status=data.get("status"),
        submitted_at=data.get("submitted_at") or (
            str(datetime.fromtimestamp(data["submittedAt"], tz=timezone.utc))
            if data.get("submittedAt") else None
        ),
        resolved_at=data.get("resolved_at") or (
            str(datetime.fromtimestamp(data["resolvedAt"], tz=timezone.utc))
            if data.get("resolvedAt") else None
        ),
        source=data.get("source", "unknown"),
    )


@router.post(
    "/claims/{claim_id}/process",
    summary="Process (pay) an approved parametric claim",
)
async def process_claim(
    claim_id: int,
    current_user: User = Depends(get_current_user),
):
    """
    Marks an approved parametric claim as paid.
    Operator-only action that triggers the on-chain payout event.
    In a production system, this is called automatically after oracle verification.
    """
    svc = get_smart_contract_service()
    result = await svc.process_claim(claim_id)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Claim processing failed"),
        )
    return result


@router.get(
    "/contracts/source",
    summary="Return Solidity smart contract source code",
)
async def get_contract_source(
    current_user: User = Depends(get_current_user),
):
    """
    Returns the Solidity source code for PolicyNFT and ParametricClaims contracts.
    Use with Hardhat or Foundry to compile and deploy to Polygon.
    """
    svc = get_smart_contract_service()
    return {
        "contracts": svc.get_solidity_contracts(),
        "compiler_version": "^0.8.20",
        "dependencies": ["@openzeppelin/contracts"],
        "networks": {
            "mumbai_testnet": {
                "chain_id": 80001,
                "rpc": "https://rpc-mumbai.maticvigil.com",
                "explorer": "https://mumbai.polygonscan.com",
            },
            "polygon_mainnet": {
                "chain_id": 137,
                "rpc": "https://polygon-rpc.com",
                "explorer": "https://polygonscan.com",
            },
        },
    }


@router.get(
    "/contracts/deploy-guide",
    summary="Deployment guide for smart contracts",
)
async def get_deploy_guide(
    current_user: User = Depends(get_current_user),
):
    """
    Returns step-by-step instructions for deploying PolicyNFT and ParametricClaims
    to Polygon Mumbai testnet or mainnet.
    """
    svc = get_smart_contract_service()
    return {
        "instructions": svc.get_deploy_instructions(),
        "required_env_vars": [
            "POLYGON_RPC_URL",
            "POLYGON_CHAIN_ID",
            "POLYGON_OPERATOR_KEY",
            "POLICY_NFT_ADDRESS",
            "PARAMETRIC_CLAIMS_ADDRESS",
        ],
        "python_packages": ["web3>=6.0.0", "py-solc-x>=1.1.1"],
        "current_mode": "simulation" if svc._simulation_mode else "live",
    }
