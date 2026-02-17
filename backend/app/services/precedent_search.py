"""
Precedent Search Service

Finds similar historical assessments using semantic vector search.
Enables underwriters to learn from past decisions.
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sentence_transformers import SentenceTransformer

from app.models.assessment import Assessment
from app.models.assessment_vector import AssessmentVector

logger = logging.getLogger(__name__)


class PrecedentSearchService:
    """
    Semantic search across historical assessments.

    Uses insurance-BERT embeddings + pgvector cosine similarity
    to find similar past risks and their outcomes.
    """

    def __init__(self):
        # Use same embedding model as RAG system
        self.model = SentenceTransformer('llmware/industry-bert-insurance-v0.1')
        logger.info("PrecedentSearchService initialized with insurance-BERT")

    async def embed_assessment(
        self,
        db: AsyncSession,
        assessment: Assessment
    ) -> AssessmentVector:
        """
        Create vector embedding for an assessment.

        Embeds: risk_category + territory + description + key fields
        """

        # Build text representation
        text_parts = [
            f"Risk Category: {assessment.risk_category}",
            f"Territory: {assessment.territory or 'Unknown'}",
        ]

        if assessment.description:
            text_parts.append(f"Description: {assessment.description}")

        if assessment.insured_name:
            text_parts.append(f"Insured: {assessment.insured_name}")

        if assessment.sum_insured:
            text_parts.append(f"Sum Insured: ${assessment.sum_insured:,.0f}")

        text = " | ".join(text_parts)

        # Generate embedding
        embedding = self.model.encode(text, show_progress_bar=False)

        # Prepare metadata for filtering
        metadata = {
            "risk_category": assessment.risk_category,
            "territory": assessment.territory,
            "decision": assessment.decision,
            "status": assessment.status,
            "premium": float(assessment.premium) if assessment.premium else None,
            "sum_insured": float(assessment.sum_insured) if assessment.sum_insured else None,
        }

        # Create or update vector
        vector = await db.get(AssessmentVector, assessment.id)
        if vector:
            vector.embedding = embedding.tolist()
            vector.metadata = metadata
        else:
            vector = AssessmentVector(
                assessment_id=assessment.id,
                embedding=embedding.tolist(),
                metadata=metadata
            )
            db.add(vector)

        await db.commit()
        await db.refresh(vector)

        logger.info(f"Embedded assessment {assessment.id}")
        return vector

    async def find_similar(
        self,
        db: AsyncSession,
        assessment_id: UUID,
        top_k: int = 5,
        min_similarity: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Find similar past assessments.

        Args:
            assessment_id: Current assessment to find matches for
            top_k: Number of similar assessments to return
            min_similarity: Minimum cosine similarity (0-1)
            filters: Optional metadata filters (e.g., {"risk_category": "Cyber"})

        Returns:
            List of similar assessments with similarity scores
        """

        # Get query assessment's embedding
        query_vector = await db.get(AssessmentVector, assessment_id)
        if not query_vector:
            logger.warning(f"Assessment {assessment_id} not embedded yet")
            return []

        # Build query
        query = f"""
            SELECT
                av.assessment_id,
                a.reference_number,
                a.risk_category,
                a.territory,
                a.insured_name,
                a.decision,
                a.premium,
                a.sum_insured,
                a.created_at,
                1 - (av.embedding <=> :query_embedding) AS similarity
            FROM assessment_vectors av
            JOIN assessments a ON a.id = av.assessment_id
            WHERE av.assessment_id != :exclude_id
              AND 1 - (av.embedding <=> :query_embedding) >= :min_similarity
        """

        # Add metadata filters
        params = {
            "query_embedding": query_vector.embedding,
            "exclude_id": assessment_id,
            "min_similarity": min_similarity
        }

        if filters:
            if "risk_category" in filters:
                query += " AND a.risk_category = :risk_category"
                params["risk_category"] = filters["risk_category"]

            if "territory" in filters:
                query += " AND a.territory = :territory"
                params["territory"] = filters["territory"]

            if "decision" in filters:
                query += " AND a.decision = :decision"
                params["decision"] = filters["decision"]

        query += f" ORDER BY similarity DESC LIMIT :top_k"
        params["top_k"] = top_k

        # Execute search
        result = await db.execute(text(query), params)
        rows = result.fetchall()

        # Format results
        similar_assessments = []
        for row in rows:
            similar_assessments.append({
                "assessment_id": str(row.assessment_id),
                "reference_number": row.reference_number,
                "risk_category": row.risk_category,
                "territory": row.territory,
                "insured_name": row.insured_name,
                "decision": row.decision,
                "premium": float(row.premium) if row.premium else None,
                "sum_insured": float(row.sum_insured) if row.sum_insured else None,
                "created_at": row.created_at.isoformat(),
                "similarity": float(row.similarity),
                "similarity_pct": f"{row.similarity * 100:.1f}%"
            })

        logger.info(f"Found {len(similar_assessments)} similar assessments for {assessment_id}")
        return similar_assessments

    async def embed_all_assessments(
        self,
        db: AsyncSession,
        batch_size: int = 100
    ) -> int:
        """
        Batch embed all existing assessments.

        Run this once to populate vectors for existing assessments.
        """

        # Get all assessments without vectors
        query = select(Assessment).outerjoin(
            AssessmentVector,
            Assessment.id == AssessmentVector.assessment_id
        ).where(AssessmentVector.assessment_id.is_(None))

        result = await db.execute(query)
        assessments = result.scalars().all()

        logger.info(f"Embedding {len(assessments)} assessments...")

        embedded_count = 0
        for assessment in assessments:
            try:
                await self.embed_assessment(db, assessment)
                embedded_count += 1

                if embedded_count % 10 == 0:
                    logger.info(f"Embedded {embedded_count}/{len(assessments)}")

            except Exception as e:
                logger.error(f"Failed to embed {assessment.id}: {e}")
                continue

        logger.info(f"✓ Embedded {embedded_count} assessments")
        return embedded_count


# Singleton instance
precedent_search_service = PrecedentSearchService()
