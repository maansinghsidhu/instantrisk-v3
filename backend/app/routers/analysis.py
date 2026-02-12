"""
Analysis API Router

Provides endpoints for:
- Analysis mode selection and time estimation
- WebSocket for real-time progress updates
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
import asyncio
import json
from datetime import datetime

from ..services.autogen_processor import (
    AnalysisMode,
    estimate_analysis_time,
    get_all_mode_estimates,
    MODE_DESCRIPTIONS,
    AGENT_DETAILED_STEPS
)
from ..core.security import get_current_user

router = APIRouter(prefix="/analysis", tags=["Analysis"])


# =============================================================================
# Schemas
# =============================================================================

class ModeEstimateRequest(BaseModel):
    document_count: int = 1
    total_chars: int = 2000


class ModeInfo(BaseModel):
    mode: str
    name: str
    description: str
    agents: List[str]
    icon: str
    estimated_seconds: int
    agents_count: int


class AllModesResponse(BaseModel):
    modes: List[dict]
    recommended: str


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/modes")
async def get_analysis_modes(
    document_count: int = Query(1, ge=1, le=100),
    total_chars: int = Query(2000, ge=100, le=500000),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all available analysis modes with time estimates.

    Returns mode information including:
    - Name and description
    - Agents used
    - Estimated processing time
    - Recommended mode based on document complexity
    """
    estimates = get_all_mode_estimates(document_count, total_chars)

    # Determine recommended mode based on complexity
    if total_chars < 3000 and document_count <= 2:
        recommended = "quick"
    elif total_chars < 10000 and document_count <= 5:
        recommended = "go_no_go"
    else:
        recommended = "deep"

    return {
        "modes": estimates,
        "recommended": recommended,
        "document_count": document_count,
        "total_chars": total_chars
    }


@router.get("/modes/{mode}")
async def get_mode_details(
    mode: str,
    document_count: int = Query(1, ge=1, le=100),
    total_chars: int = Query(2000, ge=100, le=500000),
    current_user: dict = Depends(get_current_user)
):
    """Get detailed information about a specific analysis mode."""
    try:
        analysis_mode = AnalysisMode(mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}. Valid modes: quick, go_no_go, deep")

    estimate = estimate_analysis_time(analysis_mode, document_count, total_chars)
    return estimate


@router.post("/estimate")
async def estimate_time(
    request: ModeEstimateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Get time estimates for all modes based on document parameters.

    Useful for showing estimated times before user selects a mode.
    """
    return {
        "estimates": get_all_mode_estimates(request.document_count, request.total_chars),
        "input": {
            "document_count": request.document_count,
            "total_chars": request.total_chars
        }
    }


# =============================================================================
# WebSocket for Real-Time Progress
# =============================================================================

# Store active WebSocket connections per session
active_connections: dict[str, WebSocket] = {}


@router.websocket("/ws/{session_id}")
async def analysis_progress_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time analysis progress updates.

    Messages sent:
    {
        "type": "progress",
        "current_agent": "RiskAnalyst",
        "agent_index": 3,
        "total_agents": 5,
        "description": "Analyzing risk factors...",
        "progress_percent": 60,
        "elapsed_seconds": 25,
        "estimated_remaining": 18
    }

    {
        "type": "complete",
        "decision": "GO",
        "confidence": 0.85,
        "processing_time": 45
    }

    {
        "type": "error",
        "message": "Processing failed"
    }
    """
    await websocket.accept()
    active_connections[session_id] = websocket

    try:
        while True:
            # Keep connection alive, wait for client messages or disconnection
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=300)
                # Handle ping/pong or other client messages
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_json({"type": "keepalive", "timestamp": datetime.now().isoformat()})
    except WebSocketDisconnect:
        pass
    finally:
        if session_id in active_connections:
            del active_connections[session_id]


async def send_progress_update(session_id: str, progress_data: dict):
    """Send progress update to connected WebSocket client."""
    if session_id in active_connections:
        websocket = active_connections[session_id]
        try:
            await websocket.send_json(progress_data)
        except Exception:
            # Connection might be closed
            if session_id in active_connections:
                del active_connections[session_id]


async def create_progress_callback(session_id: str, mode: AnalysisMode, start_time: datetime):
    """
    Create a progress callback function for the analysis processor.

    This callback sends real-time updates via WebSocket including detailed sub-steps
    and live findings.
    """
    from ..services.autogen_processor import MODE_AGENTS, AGENT_TIME_ESTIMATES, AGENT_DETAILED_STEPS

    agents = MODE_AGENTS.get(mode, [])
    total_estimated = sum(AGENT_TIME_ESTIMATES.get(a, 10) for a in agents)

    async def callback(progress_state: dict):
        """Handle progress updates with full state including findings."""
        # Handle both old format (list) and new format (dict with full state)
        if isinstance(progress_state, list):
            progress_steps = progress_state
            live_findings = []
            current_sub_step = ""
        else:
            progress_steps = progress_state.get("steps", [])
            live_findings = progress_state.get("live_findings", [])
            current_sub_step = progress_state.get("current_sub_step", "")

        if not progress_steps:
            return

        current_step = progress_steps[-1]
        agent_name = current_step.get("agent", "")
        agent_index = agents.index(agent_name) + 1 if agent_name in agents else 0

        elapsed = (datetime.now() - start_time).total_seconds()

        # Calculate estimated progress including sub-steps
        completed_agents = agent_index - 1
        completed_time = sum(
            AGENT_TIME_ESTIMATES.get(agents[i], 10)
            for i in range(completed_agents)
        )

        # Add partial progress within current agent based on sub-step
        sub_steps = AGENT_DETAILED_STEPS.get(agent_name, [])
        current_sub_index = current_step.get("current_sub_step", 0)
        if sub_steps and len(sub_steps) > 0:
            agent_time = AGENT_TIME_ESTIMATES.get(agent_name, 10)
            sub_step_progress = (current_sub_index / len(sub_steps)) * agent_time
            completed_time += sub_step_progress

        progress_percent = min(99, int((completed_time / total_estimated) * 100))
        remaining = max(0, total_estimated - elapsed)

        # Get current sub-step description
        sub_step_desc = ""
        if sub_steps and current_sub_index < len(sub_steps):
            sub_step_desc = sub_steps[current_sub_index].get("desc", "")

        # Extract document-level progress if present
        current_document = progress_state.get("current_document", 0) if isinstance(progress_state, dict) else 0
        total_documents = progress_state.get("total_documents", 0) if isinstance(progress_state, dict) else 0
        documents_remaining = progress_state.get("documents_remaining", 0) if isinstance(progress_state, dict) else 0
        document_name = progress_state.get("document_name", "") if isinstance(progress_state, dict) else ""
        overall_progress = progress_state.get("overall_progress", progress_percent) if isinstance(progress_state, dict) else progress_percent
        current_agent_from_state = progress_state.get("current_agent", agent_name) if isinstance(progress_state, dict) else agent_name

        await send_progress_update(session_id, {
            "type": "progress",
            "current_agent": current_agent_from_state or agent_name,
            "agent_index": agent_index,
            "total_agents": len(agents),
            "description": current_step.get("description", "Processing..."),
            "sub_step_description": sub_step_desc or current_sub_step,
            "sub_step_index": current_sub_index,
            "total_sub_steps": len(sub_steps),
            "progress_percent": overall_progress,  # Use cumulative progress
            "elapsed_seconds": int(elapsed),
            "estimated_remaining": int(remaining),
            "status": current_step.get("status", "running"),
            "live_findings": live_findings[-15:],  # Send last 15 findings for more visibility
            # Document-level progress
            "current_document": current_document,
            "total_documents": total_documents,
            "documents_remaining": documents_remaining,
            "document_name": document_name
        })

    return callback
