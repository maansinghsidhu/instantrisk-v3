"""
Chat Service - AWS Bedrock Claude AI with Qdrant RAG and Streaming

Provides ChatGPT-like experience with:
- Streaming responses (typing animation)
- Semantic RAG from Qdrant vector database (112k+ insurance records)
- Per-user chat history
- Document context attachment
"""

import os
import json
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Bedrock Configuration
from app.services.bedrock_client import bedrock_client, BEDROCK_ENABLED
from app.services.rag_indexer import rag_indexer
from app.services.qdrant_service import qdrant_service

# RAG Configuration
RAG_DATA_DIR = Path("/app/app/data") if Path("/app/app/data").exists() else Path("app/data")
RAG_TOP_K = 5  # Number of relevant documents to retrieve
TRAINING_DATA_DIR = RAG_DATA_DIR / "training_data"

# System prompt for insurance AI
SYSTEM_PROMPT = """You are an expert insurance AI assistant for InstantRisk, trained on 78,000+ insurance Q&A pairs and 34,000+ policy clauses.

EXPERTISE AREAS:
- Lloyd's of London market operations
- Commercial insurance underwriting
- Risk assessment and actuarial pricing
- Policy wording (BIMCO, LMA, Lloyd's)
- Treaty and facultative reinsurance
- Claims management and reserving
- Regulatory compliance (FCA, PRA, Solvency II, EIOPA)

KNOWLEDGE BASE:
- 34,000+ insurance clauses and wordings
- 78,000+ verified Q&A pairs from industry experts
- Legal cases and regulatory guidance
- Actuarial models and pricing data

RESPONSE GUIDELINES:
1. Answer directly and precisely
2. Cite specific clauses, regulations, or market practices when relevant
3. Use the provided Q&A examples to match the expected response style
4. Flag compliance or regulatory considerations
5. If uncertain, recommend consulting Lloyd's market specialists

Use markdown formatting for clarity. Be concise but comprehensive."""


class ChatService:
    """AI Chat service with AWS Bedrock Claude and Qdrant RAG."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._rag_cache = {}

    async def stream_response(
        self,
        messages: List[Dict[str, str]],
        rag_context: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        user_id: Optional[str] = None,
        language: str = "en",
    ) -> AsyncGenerator[str, None]:
        """
        Stream response from Bedrock Claude token by token.

        Yields tokens as they arrive for real-time typing effect.
        """
        if not BEDROCK_ENABLED:
            yield "Error: AI service not configured. Please contact support."
            return

        # Build system prompt with RAG context
        system_content = SYSTEM_PROMPT

        # Add language instruction if not English
        if language and language != "en":
            lang_names = {
                "fr": "French", "de": "German", "es": "Spanish",
                "it": "Italian", "pt": "Portuguese", "nl": "Dutch",
                "ar": "Arabic", "zh": "Chinese", "ja": "Japanese"
            }
            lang_name = lang_names.get(language, language)
            system_content += f"""

---
LANGUAGE INSTRUCTION:
Respond in {lang_name}. The user's preferred language is {lang_name}.
All responses, explanations, and technical terms should be in {lang_name}."""

        if rag_context:
            system_content += f"""

---
CONTEXT FROM KNOWLEDGE BASE:

{rag_context}

Use the Q&A examples above to match the expected response style. Reference the clauses and documents when relevant."""

        full_messages = [{"role": "system", "content": system_content}]
        full_messages.extend(messages)

        try:
            async for token in bedrock_client.stream_chat(
                messages=full_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                # Yield character by character for typing effect
                for char in token:
                    yield char

        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield f"\n\n[Error: {str(e)}]"

    async def get_response(
        self,
        messages: List[Dict[str, str]],
        rag_context: str = "",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        Get complete (non-streaming) response from Bedrock Claude.
        """
        full_response = ""
        async for token in self.stream_response(
            messages=messages,
            rag_context=rag_context,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            full_response += token

        return {
            "content": full_response,
            "model": "bedrock-claude",
            "tokens_used": len(full_response.split()),
        }

    async def get_rag_context(
        self,
        query: str,
        assessment_id: Optional[str] = None,
        user_id: Optional[str] = None,
        top_k: int = RAG_TOP_K,
    ) -> Dict[str, Any]:
        """
        Retrieve relevant context from RAG knowledge base.

        Uses semantic search over:
        - Insurance clauses and policies
        - Regulatory documents
        - User's assessment documents (if assessment_id provided)
        """
        context_parts = []
        sources = []

        # Search in pre-indexed RAG documents
        rag_results = await self._search_rag_documents(query, top_k)

        for result in rag_results:
            context_parts.append(result["text"])
            sources.append({
                "title": result.get("title", "Insurance Knowledge"),
                "snippet": result["text"][:200] + "...",
                "relevance": result.get("score", 0.8),
                "source_type": result.get("source", "knowledge_base"),
            })

        # If assessment_id provided, add user's document context
        if assessment_id:
            assessment_context = await self._get_assessment_context(assessment_id, user_id)
            if assessment_context:
                context_parts.append(f"User's Assessment Context:\n{assessment_context}")
                sources.append({
                    "title": "Your Assessment",
                    "snippet": assessment_context[:200] + "...",
                    "relevance": 1.0,
                    "source_type": "user_doc",
                })

        # Search user's training documents for relevant context
        if user_id:
            try:
                training_results = await qdrant_service.search_similar(
                    query=query,
                    user_id=str(user_id),
                    limit=3
                )
                for result in training_results:
                    context_parts.append(f"From Training Document ({result.get('filename', 'Unknown')}):\n{result.get('text', '')}")
                    sources.append({
                        "title": f"Training: {result.get('filename', 'Document')}",
                        "snippet": result.get("text", "")[:200] + "...",
                        "relevance": result.get("score", 0.7),
                        "source_type": "training_doc",
                    })
            except Exception as e:
                logger.warning(f"Failed to search training documents: {e}")

        return {
            "context": "\n\n---\n\n".join(context_parts),
            "sources": sources,
        }

    async def _search_rag_documents(self, query: str, top_k: int) -> List[Dict]:
        """
        Semantic RAG search using Qdrant vector database.

        Searches 112k+ indexed insurance records using sentence embeddings.
        Falls back to basic search if Qdrant is unavailable.
        """
        try:
            # Search for Q&A examples (few-shot)
            qa_results = rag_indexer.search(query, top_k=2, doc_type="qa")

            # Search for documents (clauses, policies, regulatory, claims)
            doc_results = rag_indexer.search(query, top_k=3)
            # Filter out QA from doc results to avoid duplicates
            doc_results = [r for r in doc_results if r.get("type") != "qa"][:3]

            results = []

            for r in qa_results:
                results.append({
                    "text": r["text"],
                    "title": r.get("question", "Insurance Q&A Example")[:80],
                    "source": "training_data",
                    "category": "few_shot",
                    "score": r.get("score", 0.8),
                })

            for r in doc_results:
                results.append({
                    "text": r["text"],
                    "title": r.get("name", r.get("category", "Document")),
                    "source": r.get("source", "knowledge_base"),
                    "category": r.get("category", ""),
                    "score": r.get("score", 0.7),
                })

            if results:
                return results

        except Exception as e:
            logger.warning(f"Qdrant search failed, using fallback: {e}")

        # Fallback: basic keyword search on cached data
        return await self._fallback_keyword_search(query, top_k)

    async def _fallback_keyword_search(self, query: str, top_k: int) -> List[Dict]:
        """Keyword-based fallback if Qdrant is unavailable."""
        results = []
        query_terms = set(query.lower().split())

        rag_files = [
            (RAG_DATA_DIR / "training_data/embeddings/clauses_for_rag.jsonl", "clause"),
            (TRAINING_DATA_DIR / "chat_finetune/insurance_qa_train.jsonl", "qa"),
        ]

        for rag_file, doc_type in rag_files:
            if not rag_file.exists():
                continue

            cache_key = str(rag_file)
            if cache_key not in self._rag_cache:
                self._rag_cache[cache_key] = []
                try:
                    with open(rag_file, "r") as f:
                        for i, line in enumerate(f):
                            if i >= 10000:
                                break
                            try:
                                doc = json.loads(line)
                                doc["_type"] = doc_type
                                self._rag_cache[cache_key].append(doc)
                            except json.JSONDecodeError:
                                continue
                except Exception as e:
                    logger.error(f"Error loading RAG file {rag_file}: {e}")

            for doc in self._rag_cache[cache_key]:
                if doc.get("_type") == "qa":
                    messages = doc.get("messages", [])
                    text = " ".join(m.get("content", "") for m in messages)
                else:
                    text = doc.get("text", "")

                doc_terms = set(text.lower().split())
                overlap = len(query_terms & doc_terms)
                if overlap > 0:
                    score = overlap / max(len(query_terms), 1)
                    results.append({
                        "text": text[:1000],
                        "title": "Fallback Result",
                        "source": "keyword_search",
                        "category": doc_type,
                        "score": score,
                    })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    async def _get_assessment_context(
        self, assessment_id: str, user_id: Optional[str]
    ) -> Optional[str]:
        """Get context from user's assessment documents."""
        try:
            # Import here to avoid circular imports
            from app.models.assessment import Assessment

            query = select(Assessment).where(Assessment.id == assessment_id)
            if user_id:
                query = query.where(Assessment.user_id == user_id)

            result = await self.db.execute(query)
            assessment = result.scalar_one_or_none()

            if assessment:
                # Build context from assessment data
                context_parts = []
                if assessment.risk_type:
                    context_parts.append(f"Risk Type: {assessment.risk_type}")
                if assessment.extracted_data:
                    context_parts.append(f"Extracted Data: {json.dumps(assessment.extracted_data)}")
                if assessment.ai_analysis:
                    context_parts.append(f"AI Analysis: {assessment.ai_analysis}")
                return "\n".join(context_parts)
        except Exception as e:
            logger.error(f"Error getting assessment context: {e}")

        return None

    async def save_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Save chat message to database for history."""
        try:
            from app.models.chat import ChatMessage

            message = ChatMessage(
                user_id=user_id,
                conversation_id=conversation_id,
                role=role,
                content=content,
                extra_data=metadata or {},
                created_at=datetime.utcnow(),
            )
            self.db.add(message)
            await self.db.commit()
        except Exception as e:
            logger.error(f"Error saving chat message: {e}")

    async def get_history(
        self,
        user_id: str,
        conversation_id: Optional[str] = None,
        assessment_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Get chat history for a user."""
        try:
            from app.models.chat import ChatMessage

            query = select(ChatMessage).where(ChatMessage.user_id == user_id)

            if conversation_id:
                query = query.where(ChatMessage.conversation_id == conversation_id)

            query = query.order_by(desc(ChatMessage.created_at)).limit(limit)

            result = await self.db.execute(query)
            messages = result.scalars().all()

            return [
                {
                    "id": str(msg.id),
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat(),
                    "metadata": msg.extra_data,
                }
                for msg in reversed(messages)
            ]
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return []

    async def save_feedback(
        self,
        message_id: str,
        user_id: str,
        rating: int,
        feedback: Optional[str] = None,
    ) -> None:
        """Save user feedback on a response for quality improvement."""
        # TODO: Implement feedback storage
        logger.info(f"Feedback received: message={message_id}, rating={rating}")

    async def get_conversations(self, user_id: str, limit: int = 20) -> List[Dict]:
        """Get list of user's conversations."""
        try:
            from app.models.chat import ChatMessage
            from sqlalchemy import func, distinct

            # Get distinct conversation IDs with latest message
            query = (
                select(
                    ChatMessage.conversation_id,
                    func.max(ChatMessage.created_at).label("last_message_at"),
                    func.count(ChatMessage.id).label("message_count"),
                )
                .where(ChatMessage.user_id == user_id)
                .group_by(ChatMessage.conversation_id)
                .order_by(desc("last_message_at"))
                .limit(limit)
            )

            result = await self.db.execute(query)
            conversations = result.all()

            conv_list = []
            for conv in conversations:
                # Get first user message as title
                title_query = (
                    select(ChatMessage.content)
                    .where(
                        ChatMessage.conversation_id == conv.conversation_id,
                        ChatMessage.role == "user",
                    )
                    .order_by(ChatMessage.created_at)
                    .limit(1)
                )
                title_result = await self.db.execute(title_query)
                first_message = title_result.scalar_one_or_none()

                conv_list.append({
                    "id": conv.conversation_id,
                    "title": (first_message or "New Conversation")[:50],
                    "last_message_at": conv.last_message_at.isoformat(),
                    "message_count": conv.message_count,
                })

            return conv_list
        except Exception as e:
            logger.error(f"Error getting conversations: {e}")
            return []
