"""
Per-User Model Adapter Service — trains and manages lightweight adapters
on top of the base InsuranceMultiTaskModel.

Architecture:
    Base model (shared, ~441MB) stays frozen
    + Per-user adapter (~2-5MB) adjusts task head outputs
    = Personalized predictions for each user

Training flow:
    1. Collect user's document chunks from user_doc_vectors
    2. Build pseudo-labels from chunk text + categories
    3. Train adapter weights (base model frozen)
    4. Save adapter to local path (or S3 for production)
    5. Load at inference time via LRU cache
"""

import os
import json
import logging
import threading
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timezone
from collections import OrderedDict

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import numpy as np
    from torch.utils.data import DataLoader, TensorDataset
    from transformers import AutoTokenizer
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
    torch = None
    nn = None


# =============================================================================
# User Adapter Network
# =============================================================================

if _TORCH_AVAILABLE:
    class UserAdapter(nn.Module):
        """
        Lightweight adapter that adjusts task head outputs for a specific user.

        Takes the shared projection features (512-dim) from the base model
        and produces per-task adjustments that are ADDED to base model logits.
        This allows the adapter to learn user-specific biases without
        modifying the base model.

        Size: ~300KB-2MB per user depending on label counts.
        """

        def __init__(self, hidden_dim: int = 512, adapter_dim: int = 64,
                     num_clause_labels: int = 134, num_intent_labels: int = 39):
            super().__init__()
            self.hidden_dim = hidden_dim
            self.adapter_dim = adapter_dim

            # Per-task adapter networks (small MLPs)
            self.clause_adapter = nn.Sequential(
                nn.Linear(hidden_dim, adapter_dim),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(adapter_dim, num_clause_labels),
            )

            self.appetite_adapter = nn.Sequential(
                nn.Linear(hidden_dim, adapter_dim),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(adapter_dim, 3),
            )

            self.pricing_adapter = nn.Sequential(
                nn.Linear(hidden_dim, adapter_dim),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(adapter_dim, 3),
            )

            self.intent_adapter = nn.Sequential(
                nn.Linear(hidden_dim, adapter_dim),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(adapter_dim, num_intent_labels),
            )

        def forward(self, shared_features, base_logits, task=None):
            """Add adapter adjustments to base model logits."""
            if task == "clause":
                return base_logits + self.clause_adapter(shared_features)
            elif task == "appetite":
                return base_logits + self.appetite_adapter(shared_features)
            elif task == "pricing":
                return base_logits + self.pricing_adapter(shared_features)
            elif task == "intent":
                return base_logits + self.intent_adapter(shared_features)
            else:
                return {
                    "clause": base_logits["clause"] + self.clause_adapter(shared_features),
                    "appetite": base_logits["appetite"] + self.appetite_adapter(shared_features),
                    "pricing": base_logits["pricing"] + self.pricing_adapter(shared_features),
                    "intent": base_logits["intent"] + self.intent_adapter(shared_features),
                }


# =============================================================================
# Constants
# =============================================================================

ADAPTER_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "models", "user-adapters")
MIN_CHUNKS_FOR_TRAINING = 50
ADAPTER_DIM = 64
HIDDEN_DIM = 512
MAX_CACHED_ADAPTERS = 10
ADAPTER_EPOCHS = 10
ADAPTER_BATCH_SIZE = 16
ADAPTER_LR = 1e-3
MAX_SEQ_LEN = 128

# Keyword-based pseudo-labeling for user document chunks
CLAUSE_KEYWORDS = {
    "indemnification": ["indemnif", "hold harmless", "indemnity"],
    "limitation_of_liability": ["limitation of liability", "cap on liability", "aggregate liability"],
    "confidentiality": ["confidential", "non-disclosure", "proprietary information"],
    "termination": ["terminat", "cancell", "rescind"],
    "governing_law": ["governing law", "governed by", "jurisdiction"],
    "insurance": ["insurance", "insured", "policy", "coverage", "premium"],
    "warranties": ["warrant", "representation", "guarantees"],
    "force_majeure": ["force majeure", "act of god", "unforeseeable"],
    "arbitration": ["arbitrat", "mediat", "dispute resolution"],
    "compliance": ["comply", "compliance", "regulatory"],
    "payment_terms": ["payment", "invoice", "remittance"],
    "notice": ["notice", "notification", "written notice"],
    "amendments": ["amend", "modif", "supplement"],
    "assignments": ["assign", "transfer", "delegate"],
    "severability": ["severab", "invalid provision", "unenforceable"],
}

APPETITE_KEYWORDS = {
    "accept": ["accept", "approve", "bind", "write", "underwrite", "renew", "offer"],
    "refer": ["refer", "review", "escalat", "borderline", "consider"],
    "decline": ["decline", "reject", "not acceptable", "excluded", "prohibit"],
}

PRICING_KEYWORDS = {
    "low": ["low risk", "minimal exposure", "good loss history", "standard rate", "discount"],
    "medium": ["moderate risk", "average", "standard exposure", "market rate"],
    "high": ["high risk", "significant exposure", "poor loss history", "surcharge", "loaded rate"],
}


# =============================================================================
# Service
# =============================================================================

class UserModelService:
    """
    Manages per-user adapter training and inference.

    Uses an LRU cache to keep recently-used adapters in memory.
    Adapters are stored as small .pt files (~2-5MB each).
    """

    def __init__(self):
        self._adapter_cache: OrderedDict[str, 'UserAdapter'] = OrderedDict()
        self._training_lock = threading.Lock()
        self._config: Dict = {}
        self._tokenizer = None

    def _ensure_adapter_dir(self):
        """Create adapter storage directory if needed."""
        os.makedirs(ADAPTER_DIR, exist_ok=True)

    def _get_adapter_path(self, user_id: str) -> str:
        """Get the file path for a user's adapter."""
        self._ensure_adapter_dir()
        return os.path.join(ADAPTER_DIR, f"adapter_{user_id}.pt")

    def _get_config_path(self, user_id: str) -> str:
        """Get the config path for a user's adapter."""
        self._ensure_adapter_dir()
        return os.path.join(ADAPTER_DIR, f"config_{user_id}.json")

    def load_adapter(self, user_id: str) -> Optional['UserAdapter']:
        """
        Load a user's adapter from cache or disk.

        Returns None if no adapter exists for this user.
        """
        if not _TORCH_AVAILABLE:
            return None

        # Check cache first
        if user_id in self._adapter_cache:
            self._adapter_cache.move_to_end(user_id)
            return self._adapter_cache[user_id]

        # Try loading from disk
        adapter_path = self._get_adapter_path(user_id)
        config_path = self._get_config_path(user_id)

        if not os.path.exists(adapter_path):
            return None

        try:
            # Load config
            config = {}
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)

            num_clause_labels = config.get("num_clause_labels", 134)
            num_intent_labels = config.get("num_intent_labels", 39)

            from app.services.insurance_model_service import DEVICE
            adapter = UserAdapter(
                hidden_dim=HIDDEN_DIM,
                adapter_dim=ADAPTER_DIM,
                num_clause_labels=num_clause_labels,
                num_intent_labels=num_intent_labels,
            ).to(DEVICE)

            state_dict = torch.load(adapter_path, map_location=DEVICE, weights_only=False)
            adapter.load_state_dict(state_dict)
            adapter.eval()

            # Cache it (LRU eviction)
            self._adapter_cache[user_id] = adapter
            if len(self._adapter_cache) > MAX_CACHED_ADAPTERS:
                self._adapter_cache.popitem(last=False)

            logger.info(f"Loaded user adapter for {user_id}")
            return adapter

        except Exception as e:
            logger.error(f"Failed to load adapter for user {user_id}: {e}")
            return None

    def has_adapter(self, user_id: str) -> bool:
        """Check if a user has a trained adapter."""
        if user_id in self._adapter_cache:
            return True
        return os.path.exists(self._get_adapter_path(user_id))

    def _get_user_chunks(self, user_id: str) -> List[Dict]:
        """Fetch all document chunks for a user from pgvector."""
        try:
            from app.config import settings
            from sqlalchemy import create_engine, text as sql_text

            sync_url = settings.sync_database_url
            if "+psycopg2" not in sync_url:
                sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://")
            engine = create_engine(sync_url, pool_pre_ping=True)

            with engine.connect() as conn:
                result = conn.execute(sql_text("""
                    SELECT text, category, filename, chunk_index
                    FROM user_doc_vectors
                    WHERE user_id = :user_id
                    ORDER BY uploaded_at DESC
                """), {"user_id": user_id})
                rows = result.fetchall()

            engine.dispose()

            return [
                {
                    "text": row[0],
                    "category": row[1] or "general",
                    "filename": row[2] or "",
                    "chunk_index": row[3] or 0,
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Failed to fetch user chunks: {e}")
            return []

    def _build_pseudo_labels(self, chunks: List[Dict]) -> Dict[str, List[Tuple[str, any]]]:
        """
        Build pseudo-labeled training data from user document chunks.

        Uses keyword matching + category metadata to create training pairs
        for each task head.

        Returns:
            {
                "clause": [(text, multi_hot_label), ...],
                "appetite": [(text, label_idx), ...],
                "pricing": [(text, label_idx), ...],
                "intent": [(text, label_idx), ...],
            }
        """
        clause_data = []
        appetite_data = []
        pricing_data = []

        from app.services.insurance_model_service import insurance_model_service
        config = insurance_model_service._config
        clause_labels = config.get("clause_labels", [])
        num_clause = len(clause_labels) or 134

        for chunk in chunks:
            text = chunk["text"].lower()
            category = chunk["category"].lower()

            # --- Clause pseudo-labels (multi-hot) ---
            clause_label = [0.0] * num_clause
            found_clause = False
            for i, cl in enumerate(clause_labels):
                cl_lower = cl.lower().replace("_", " ")
                # Direct match on clause label name
                if cl_lower in text:
                    clause_label[i] = 1.0
                    found_clause = True
                # Keyword match
                for kw_cat, keywords in CLAUSE_KEYWORDS.items():
                    if kw_cat == cl_lower or kw_cat.replace("_", " ") == cl_lower:
                        for kw in keywords:
                            if kw in text:
                                clause_label[i] = 1.0
                                found_clause = True
                                break

            if found_clause:
                clause_data.append((chunk["text"], clause_label))

            # --- Appetite pseudo-labels ---
            appetite_scores = {k: 0 for k in APPETITE_KEYWORDS}
            for label, keywords in APPETITE_KEYWORDS.items():
                for kw in keywords:
                    if kw in text:
                        appetite_scores[label] += 1

            best_appetite = max(appetite_scores, key=appetite_scores.get)
            if appetite_scores[best_appetite] > 0:
                label_idx = ["accept", "refer", "decline"].index(best_appetite)
                appetite_data.append((chunk["text"], label_idx))

            # --- Pricing pseudo-labels ---
            pricing_scores = {k: 0 for k in PRICING_KEYWORDS}
            for label, keywords in PRICING_KEYWORDS.items():
                for kw in keywords:
                    if kw in text:
                        pricing_scores[label] += 1

            best_pricing = max(pricing_scores, key=pricing_scores.get)
            if pricing_scores[best_pricing] > 0:
                label_idx = ["low", "medium", "high"].index(best_pricing)
                pricing_data.append((chunk["text"], label_idx))

        return {
            "clause": clause_data,
            "appetite": appetite_data,
            "pricing": pricing_data,
        }

    def train_adapter(self, user_id: str) -> Dict:
        """
        Train a per-user adapter on their uploaded document chunks.

        Freezes the base model, trains only the lightweight adapter layers.
        Returns training result with status and metrics.
        """
        if not _TORCH_AVAILABLE:
            return {"success": False, "error": "PyTorch not available"}

        with self._training_lock:
            return self._train_adapter_impl(user_id)

    def _train_adapter_impl(self, user_id: str) -> Dict:
        """Internal adapter training implementation."""
        from app.services.insurance_model_service import insurance_model_service, DEVICE

        if not insurance_model_service.is_available:
            return {"success": False, "error": "Base model not available"}

        # 1. Fetch user chunks
        chunks = self._get_user_chunks(user_id)
        if len(chunks) < MIN_CHUNKS_FOR_TRAINING:
            return {
                "success": False,
                "error": f"Need at least {MIN_CHUNKS_FOR_TRAINING} chunks, have {len(chunks)}",
                "chunks": len(chunks),
            }

        logger.info(f"Training adapter for user {user_id} with {len(chunks)} chunks")

        # 2. Build pseudo-labels
        training_data = self._build_pseudo_labels(chunks)
        total_samples = sum(len(v) for v in training_data.values())

        if total_samples < 10:
            return {
                "success": False,
                "error": f"Could not generate enough training pairs ({total_samples}). "
                         "Upload documents with more insurance-specific content.",
                "chunks": len(chunks),
                "samples": total_samples,
            }

        logger.info(f"Built training data: clause={len(training_data['clause'])}, "
                     f"appetite={len(training_data['appetite'])}, "
                     f"pricing={len(training_data['pricing'])}")

        # 3. Get base model config
        config = insurance_model_service._config
        num_clause_labels = config.get("num_clause_labels", 134)
        num_intent_labels = config.get("num_intent_labels", 39)

        # 4. Create adapter
        adapter = UserAdapter(
            hidden_dim=HIDDEN_DIM,
            adapter_dim=ADAPTER_DIM,
            num_clause_labels=num_clause_labels,
            num_intent_labels=num_intent_labels,
        ).to(DEVICE)

        # 5. Prepare tokenizer and data loaders
        tokenizer = insurance_model_service._tokenizer
        dataloaders = {}

        for task_name, samples in training_data.items():
            if not samples:
                continue

            texts = [s[0] for s in samples]
            labels = [s[1] for s in samples]

            encodings = tokenizer(
                texts,
                max_length=MAX_SEQ_LEN,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            )

            if task_name == "clause":
                label_tensor = torch.tensor(labels, dtype=torch.float32)
            else:
                label_tensor = torch.tensor(labels, dtype=torch.long)

            dataset = TensorDataset(
                encodings["input_ids"],
                encodings["attention_mask"],
                label_tensor,
            )
            dataloaders[task_name] = DataLoader(
                dataset, batch_size=ADAPTER_BATCH_SIZE, shuffle=True
            )

        # 6. Training loop — freeze base model, train only adapter
        base_model = insurance_model_service._model
        base_model.eval()

        optimizer = torch.optim.Adam(adapter.parameters(), lr=ADAPTER_LR)
        clause_loss_fn = nn.BCEWithLogitsLoss()
        cls_loss_fn = nn.CrossEntropyLoss()

        best_loss = float("inf")
        training_losses = []

        for epoch in range(ADAPTER_EPOCHS):
            adapter.train()
            epoch_loss = 0.0
            steps = 0

            # Round-robin through tasks
            task_iters = {k: iter(v) for k, v in dataloaders.items()}
            active_tasks = set(task_iters.keys())

            while active_tasks:
                for task_name in list(active_tasks):
                    try:
                        batch = next(task_iters[task_name])
                    except StopIteration:
                        active_tasks.discard(task_name)
                        continue

                    input_ids = batch[0].to(DEVICE)
                    attention_mask = batch[1].to(DEVICE)
                    labels = batch[2].to(DEVICE)

                    # Get base model features (frozen)
                    with torch.no_grad():
                        outputs = base_model.encoder(
                            input_ids=input_ids,
                            attention_mask=attention_mask,
                        )
                        cls_output = outputs.last_hidden_state[:, 0, :]
                        shared_features = base_model.shared_proj(cls_output)

                        # Get base model logits for this task
                        if task_name == "clause":
                            base_logits = base_model.clause_head(shared_features)
                        elif task_name == "appetite":
                            base_logits = base_model.appetite_head(shared_features)
                        elif task_name == "pricing":
                            base_logits = base_model.pricing_head(shared_features)

                    # Adapter forward pass
                    adapted_logits = adapter.forward(
                        shared_features, base_logits, task=task_name
                    )

                    # Loss
                    if task_name == "clause":
                        loss = clause_loss_fn(adapted_logits, labels)
                    else:
                        loss = cls_loss_fn(adapted_logits, labels)

                    optimizer.zero_grad()
                    loss.backward()
                    optimizer.step()

                    epoch_loss += loss.item()
                    steps += 1

            avg_loss = epoch_loss / max(steps, 1)
            training_losses.append(avg_loss)
            logger.info(f"User {user_id} adapter epoch {epoch+1}/{ADAPTER_EPOCHS}: loss={avg_loss:.4f}")

            if avg_loss < best_loss:
                best_loss = avg_loss

        # 7. Save adapter
        adapter.eval()
        adapter_path = self._get_adapter_path(user_id)
        config_path = self._get_config_path(user_id)

        torch.save(adapter.state_dict(), adapter_path)

        adapter_config = {
            "user_id": user_id,
            "num_clause_labels": num_clause_labels,
            "num_intent_labels": num_intent_labels,
            "adapter_dim": ADAPTER_DIM,
            "hidden_dim": HIDDEN_DIM,
            "training_chunks": len(chunks),
            "training_samples": total_samples,
            "training_losses": training_losses,
            "best_loss": best_loss,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "base_model_version": "instantrisk-engine-v1",
        }

        with open(config_path, "w") as f:
            json.dump(adapter_config, f, indent=2)

        # 8. Update cache
        self._adapter_cache[user_id] = adapter
        if len(self._adapter_cache) > MAX_CACHED_ADAPTERS:
            self._adapter_cache.popitem(last=False)

        adapter_size = os.path.getsize(adapter_path)
        logger.info(f"User adapter saved: {adapter_path} ({adapter_size / 1024:.1f}KB)")

        return {
            "success": True,
            "user_id": user_id,
            "chunks_used": len(chunks),
            "training_samples": total_samples,
            "samples_per_task": {k: len(v) for k, v in training_data.items()},
            "best_loss": round(best_loss, 4),
            "final_loss": round(training_losses[-1], 4) if training_losses else None,
            "adapter_size_kb": round(adapter_size / 1024, 1),
            "epochs": ADAPTER_EPOCHS,
        }

    def delete_adapter(self, user_id: str) -> bool:
        """Delete a user's adapter from cache and disk."""
        # Remove from cache
        self._adapter_cache.pop(user_id, None)

        # Remove files
        adapter_path = self._get_adapter_path(user_id)
        config_path = self._get_config_path(user_id)
        deleted = False

        for path in [adapter_path, config_path]:
            if os.path.exists(path):
                os.remove(path)
                deleted = True

        return deleted

    def get_adapter_info(self, user_id: str) -> Optional[Dict]:
        """Get metadata about a user's adapter."""
        config_path = self._get_config_path(user_id)
        if not os.path.exists(config_path):
            return None

        with open(config_path, "r") as f:
            return json.load(f)

    def invalidate_cache(self, user_id: str):
        """Remove a user's adapter from cache (e.g., after retraining)."""
        self._adapter_cache.pop(user_id, None)


# Singleton instance
user_model_service = UserModelService()
