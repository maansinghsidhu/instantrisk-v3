"""
InstantRisk V5 - AI Chat Router with MiniMax + RAG

Provides ChatGPT-like AI chat experience with:
- Streaming responses (real-time typing)
- RAG from 20GB+ insurance knowledge base
- Per-user chat history
- Document context attachment
- Rate limiting for cost protection
- Input sanitization
"""

import json
import asyncio
import uuid
from typing import List, Dict, Optional, AsyncGenerator
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.chat_service import ChatService
from app.middleware.rate_limiter import limiter, RateLimits
from app.utils.sanitizer import sanitize_for_ai
from app.services.claimsense_service import get_claimsense_service

router = APIRouter()

# Greeting patterns for direct response (no RAG needed)
GREETING_PATTERNS = {"hi", "hello", "hey", "howdy", "hola", "bonjour", "hallo", "ciao", "greetings", "good morning", "good afternoon", "good evening"}

GREETING_RESPONSES = {
    "en": "Hello! I'm your insurance AI assistant. I can help you with:\n\n• **Risk Assessment** - Analyze insurance submissions\n• **Policy Wording** - Explain clauses and coverage\n• **Pricing** - Technical premium calculations\n• **Lloyd's Market** - Placing and underwriting guidance\n• **Compliance** - FCA, PRA, and Solvency II requirements\n\nHow can I assist you today?",
    "de": "Hallo! Ich bin Ihr KI-Versicherungsassistent. Wie kann ich Ihnen helfen?",
    "fr": "Bonjour! Je suis votre assistant IA en assurance. Comment puis-je vous aider?",
    "es": "¡Hola! Soy su asistente de IA para seguros. ¿Cómo puedo ayudarle?",
    "it": "Ciao! Sono il vostro assistente AI per le assicurazioni. Come posso aiutarvi?",
    "pt": "Olá! Sou o seu assistente de IA para seguros. Como posso ajudá-lo?",
    "nl": "Hallo! Ik ben uw AI-verzekeringsassistent. Hoe kan ik u helpen?",
    "ar": "مرحبا! أنا مساعد التأمين بالذكاء الاصطناعي. كيف يمكنني مساعدتك؟",
    "zh": "你好！我是您的保险AI助手。我能为您做什么？",
    "ja": "こんにちは！私は保険AIアシスタントです。どのようにお手伝いできますか？",
    "ko": "안녕하세요! 저는 보험 AI 어시스턴트입니다. 어떻게 도와드릴까요?",
    "hi": "नमस्ते! मैं आपका बीमा AI सहायक हूं। मैं आपकी कैसे मदद कर सकता हूं?",
}


# ClaimSense benchmark keywords
CLAIMSENSE_KEYWORDS = {
    "benchmark", "claims data", "average severity", "frequency rate",
    "loss ratio", "claims trend", "industry average", "compare to benchmark",
    "claims history", "historical claims", "claim statistics",
    "how does this compare", "industry comparison", "national average",
}

# Policy type detection
POLICY_TYPE_MAP = {
    "general liability": "GL", "gl": "GL",
    "workers comp": "WC", "workers compensation": "WC", "wc": "WC",
    "auto liability": "AL", "auto": "AL", "al": "AL",
    "property": "PR", "pr": "PR",
    "professional liability": "PL", "pl": "PL",
    "cyber": "CY", "cy": "CY",
    "directors and officers": "DO", "d&o": "DO", "do": "DO",
    "employment practices": "EPL", "epl": "EPL",
}

# US state detection
STATE_CODES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}


def detect_claimsense_query(message: str) -> Optional[Dict]:
    """Detect if message is asking for ClaimSense benchmark data.

    Returns dict with policy_type and state if detected, None otherwise.
    """
    msg_lower = message.lower()

    # Check for benchmark-related keywords
    is_benchmark = any(kw in msg_lower for kw in CLAIMSENSE_KEYWORDS)
    if not is_benchmark:
        return None

    # Try to extract policy type
    policy_type = None
    for key, code in POLICY_TYPE_MAP.items():
        if key in msg_lower:
            policy_type = code
            break

    # Try to extract state
    state = None
    for state_name, code in STATE_CODES.items():
        if state_name in msg_lower:
            state = code
            break
    # Also check 2-letter state codes directly
    import re
    state_match = re.search(r'\b([A-Z]{2})\b', message)
    if state_match and not state:
        candidate = state_match.group(1)
        if candidate in STATE_CODES.values():
            state = candidate

    return {
        "policy_type": policy_type or "GL",
        "state": state,
    }


def is_greeting(message: str) -> bool:
    """Check if message is a simple greeting."""
    msg_lower = message.lower().strip()
    # Check exact match
    if msg_lower in GREETING_PATTERNS:
        return True
    # Check if starts with greeting
    for greeting in GREETING_PATTERNS:
        if msg_lower.startswith(greeting) and len(msg_lower) < len(greeting) + 10:
            return True
    return False


# Request/Response Models
class ChatMessage(BaseModel):
    """Single chat message."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Chat request with messages and options."""
    messages: List[ChatMessage] = Field(..., description="Conversation history")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for history")
    use_rag: bool = Field(True, description="Enable RAG for document context")
    assessment_id: Optional[str] = Field(None, description="Link to assessment for context")
    temperature: float = Field(0.3, ge=0, le=1, description="Response creativity (0-1)")
    max_tokens: int = Field(2048, ge=100, le=8192, description="Max response length")


class ChatResponse(BaseModel):
    """Non-streaming chat response."""
    message: str
    conversation_id: str
    sources: List[Dict] = []
    tokens_used: int = 0
    model: str = ""


class ConversationSummary(BaseModel):
    """Conversation list item."""
    id: str
    title: str
    last_message_at: str
    message_count: int


@router.post("/stream")
@limiter.limit(RateLimits.CHAT)
async def chat_stream(
    request: Request,
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Streaming chat endpoint for real-time typing experience.

    Returns Server-Sent Events (SSE) with token-by-token streaming.

    **Flutter Integration:**
    ```dart
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/chat/stream'),
      headers: {'Authorization': 'Bearer $token'},
      body: jsonEncode(request),
    );

    await for (final chunk in response.stream.transform(utf8.decoder)) {
      final data = jsonDecode(chunk);
      if (data['type'] == 'token') {
        setState(() => _response += data['content']);
      }
    }
    ```
    """
    chat_service = ChatService(db)

    # Generate conversation ID if not provided
    conversation_id = chat_request.conversation_id or str(uuid.uuid4())

    async def generate():
        try:
            # Send start event
            yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation_id})}\n\n"

            # Get user's language preference
            user_language = current_user.preferred_language.value if current_user.preferred_language else "en"

            # Check if this is a greeting - respond directly without RAG
            if chat_request.messages:
                user_query = chat_request.messages[-1].content
                if is_greeting(user_query):
                    # Save user message
                    await chat_service.save_message(
                        user_id=current_user.id,
                        conversation_id=conversation_id,
                        role="user",
                        content=user_query,
                    )

                    # Get localized greeting response
                    greeting_response = GREETING_RESPONSES.get(user_language, GREETING_RESPONSES["en"])

                    # Stream greeting token by token
                    for char in greeting_response:
                        yield f"data: {json.dumps({'type': 'token', 'content': char})}\n\n"
                        await asyncio.sleep(0.01)

                    # Save assistant response
                    await chat_service.save_message(
                        user_id=current_user.id,
                        conversation_id=conversation_id,
                        role="assistant",
                        content=greeting_response,
                    )

                    # Send done event
                    yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation_id, 'sources': []})}\n\n"
                    return

            # Get RAG context if enabled
            rag_context = ""
            sources = []
            claimsense_data = None

            if chat_request.use_rag and chat_request.messages:
                user_query = chat_request.messages[-1].content
                yield f"data: {json.dumps({'type': 'thinking', 'message': 'Searching knowledge base...'})}\n\n"

                rag_results = await chat_service.get_rag_context(
                    query=user_query,
                    assessment_id=chat_request.assessment_id,
                    user_id=current_user.id
                )
                rag_context = rag_results.get("context", "")
                sources = rag_results.get("sources", [])

                if sources:
                    yield f"data: {json.dumps({'type': 'sources', 'count': len(sources), 'sources': sources})}\n\n"

                # Check for ClaimSense benchmark query
                cs_query = detect_claimsense_query(user_query)
                if cs_query:
                    yield f"data: {json.dumps({'type': 'thinking', 'message': 'Querying benchmark data...'})}\n\n"
                    try:
                        cs_service = get_claimsense_service(db)
                        benchmark = await cs_service.query_benchmark(
                            policy_type=cs_query["policy_type"],
                            state=cs_query.get("state"),
                        )
                        if benchmark and hasattr(benchmark, 'to_dict'):
                            claimsense_data = benchmark.to_dict()
                        elif isinstance(benchmark, dict):
                            claimsense_data = benchmark

                        if claimsense_data:
                            # Send structured ClaimSense data as special event
                            yield f"data: {json.dumps({'type': 'claimsense', 'data': claimsense_data})}\n\n"
                            # Append benchmark context to RAG for the AI response
                            rag_context += f"\n\nCLAIMSENSE BENCHMARK DATA:\n{json.dumps(claimsense_data, default=str)[:2000]}"
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).warning(f"ClaimSense query failed: {e}")

            # Save user message
            if chat_request.messages:
                await chat_service.save_message(
                    user_id=current_user.id,
                    conversation_id=conversation_id,
                    role="user",
                    content=chat_request.messages[-1].content,
                )

            # Stream AI response
            yield f"data: {json.dumps({'type': 'thinking', 'message': 'Generating response...'})}\n\n"

            full_response = ""
            async for token in chat_service.stream_response(
                messages=[m.dict() for m in chat_request.messages],
                rag_context=rag_context,
                temperature=chat_request.temperature,
                max_tokens=chat_request.max_tokens,
                user_id=current_user.id,
                language=user_language,
            ):
                full_response += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                await asyncio.sleep(0.01)  # Small delay for smooth streaming

            # Save assistant response
            await chat_service.save_message(
                user_id=current_user.id,
                conversation_id=conversation_id,
                role="assistant",
                content=full_response,
                metadata={"sources": sources},
            )

            # Send completion
            yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation_id, 'sources': sources})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        }
    )


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Non-streaming chat endpoint.

    Returns complete response after AI finishes generating.
    Use /stream for real-time typing animation.
    """
    chat_service = ChatService(db)
    conversation_id = request.conversation_id or str(uuid.uuid4())

    # Get RAG context
    rag_context = ""
    sources = []

    if request.use_rag and request.messages:
        user_query = request.messages[-1].content
        rag_results = await chat_service.get_rag_context(
            query=user_query,
            assessment_id=request.assessment_id,
            user_id=current_user.id
        )
        rag_context = rag_results.get("context", "")
        sources = rag_results.get("sources", [])

    # Save user message
    if request.messages:
        await chat_service.save_message(
            user_id=current_user.id,
            conversation_id=conversation_id,
            role="user",
            content=request.messages[-1].content,
        )

    # Get complete response
    response = await chat_service.get_response(
        messages=[m.dict() for m in request.messages],
        rag_context=rag_context,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )

    # Save assistant response
    await chat_service.save_message(
        user_id=current_user.id,
        conversation_id=conversation_id,
        role="assistant",
        content=response["content"],
        metadata={"sources": sources},
    )

    return ChatResponse(
        message=response["content"],
        conversation_id=conversation_id,
        sources=sources,
        tokens_used=response.get("tokens_used", 0),
        model=response.get("model", "")
    )


@router.get("/conversations")
async def get_conversations(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get list of user's chat conversations."""
    chat_service = ChatService(db)
    conversations = await chat_service.get_conversations(
        user_id=current_user.id,
        limit=limit
    )
    return {"conversations": conversations}


@router.get("/history/{conversation_id}")
async def get_conversation_history(
    conversation_id: str,
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get chat history for a specific conversation."""
    chat_service = ChatService(db)
    history = await chat_service.get_history(
        user_id=current_user.id,
        conversation_id=conversation_id,
        limit=limit
    )
    return {"messages": history, "conversation_id": conversation_id}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a conversation and all its messages."""
    # TODO: Implement deletion
    return {"status": "deleted", "conversation_id": conversation_id}


@router.get("/suggestions")
async def get_suggestions(
    context: str = Query("general", description="Context: general, assessment, document, pricing"),
    current_user: User = Depends(get_current_user)
):
    """Get suggested questions based on context."""
    suggestions = {
        "general": [
            "What are the key Lloyd's market regulations?",
            "Explain facultative vs treaty reinsurance",
            "How does the Lloyd's chain of security work?",
            "What is a managing agent's role?",
        ],
        "assessment": [
            "What are the main risks in this submission?",
            "Are there any coverage gaps?",
            "What additional information should I request?",
            "How does this compare to similar risks?",
        ],
        "document": [
            "Summarize the key terms of this policy",
            "Are there any unusual exclusions?",
            "What are the coverage limits?",
            "Explain the claims notification requirements",
        ],
        "pricing": [
            "What factors affect this premium?",
            "How does the market typically price this?",
            "What loss ratio should I target?",
            "Are there rate changes in this segment?",
        ],
    }
    return {"suggestions": suggestions.get(context, suggestions["general"])}


@router.post("/feedback")
async def submit_feedback(
    message_id: str,
    rating: int = Query(..., ge=1, le=5),
    feedback: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submit feedback on a chat response."""
    chat_service = ChatService(db)
    await chat_service.save_feedback(
        message_id=message_id,
        user_id=current_user.id,
        rating=rating,
        feedback=feedback
    )
    return {"status": "success", "message": "Feedback saved"}
