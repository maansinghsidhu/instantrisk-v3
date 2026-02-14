"""
InstantRisk Engine - ML Inference Service

Provides intelligent recommendations using the fine-tuned insurance-BERT model:
- Clause recommendations based on risk description
- Risk appetite assessment (accept/refer/decline)
- Insurance intent classification
- Pricing signal classification
- Semantic search via fine-tuned embeddings

Falls back to keyword search if model is not available.
"""

import os
import json
from typing import List, Dict, Optional

try:
    import torch
    import numpy as np
    from transformers import AutoTokenizer
    from app.services.model_trainer import InsuranceMultiTaskModel
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
    torch = None
    np = None


# =============================================================================
# Configuration
# =============================================================================

# Look for best model first, then final
MODEL_DIR_BEST = os.path.join(os.path.dirname(__file__), "..", "data", "models", "instantrisk-engine-v1-best")
MODEL_DIR_FINAL = os.path.join(os.path.dirname(__file__), "..", "data", "models", "instantrisk-engine-v1-final")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu") if _TORCH_AVAILABLE else None
MAX_SEQ_LEN = 256
EMBEDDING_DIM = 512  # shared_proj output dim


# =============================================================================
# Service
# =============================================================================

class InsuranceModelService:
    """
    Singleton service for InstantRisk Engine ML inference.

    Loads the fine-tuned model once and provides inference methods.
    Falls back gracefully if model is not available.
    """

    def __init__(self):
        self._model: Optional[InsuranceMultiTaskModel] = None
        self._tokenizer = None
        self._config: Dict = {}
        self._loaded = False
        self._available = False

    def load(self, model_dir: Optional[str] = None) -> bool:
        """Load the trained model. Returns True if successful."""
        if self._loaded:
            return self._available

        if not _TORCH_AVAILABLE:
            print("InstantRisk Engine: torch not available — running in fallback mode")
            self._loaded = True
            self._available = False
            return False

        # Find model directory
        if model_dir is None:
            if os.path.exists(os.path.join(MODEL_DIR_BEST, "model.pt")):
                model_dir = MODEL_DIR_BEST
            elif os.path.exists(os.path.join(MODEL_DIR_FINAL, "model.pt")):
                model_dir = MODEL_DIR_FINAL
            else:
                print(f"InstantRisk Engine model not found — running in fallback mode")
                self._loaded = True
                self._available = False
                return False

        model_path = os.path.join(model_dir, "model.pt")
        config_path = os.path.join(model_dir, "config.json")

        if not os.path.exists(model_path):
            print(f"InstantRisk Engine model not found at {model_path} — running in fallback mode")
            self._loaded = True
            self._available = False
            return False

        try:
            print(f"Loading InstantRisk Engine from {model_dir}...")

            # Load config
            with open(config_path, "r") as f:
                self._config = json.load(f)

            # Build model with correct architecture
            self._model = InsuranceMultiTaskModel(
                base_model_name=self._config["base_model"],
                num_clause_labels=self._config["num_clause_labels"],
                num_intent_labels=self._config["num_intent_labels"],
            ).to(DEVICE)

            # Load trained weights (state_dict only)
            state_dict = torch.load(model_path, map_location=DEVICE, weights_only=False)
            self._model.load_state_dict(state_dict)
            self._model.eval()

            # Load tokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(model_dir)

            self._loaded = True
            self._available = True
            print(f"InstantRisk Engine loaded: {self._config['num_clause_labels']} clause labels, "
                  f"{self._config['num_intent_labels']} intent labels")
            return True

        except Exception as e:
            print(f"Error loading InstantRisk Engine: {e}")
            self._loaded = True
            self._available = False
            return False

    @property
    def is_available(self) -> bool:
        """Check if the ML model is loaded and available."""
        if not self._loaded:
            self.load()
        return self._available

    def _encode(self, text: str) -> Dict[str, torch.Tensor]:
        """Tokenize text for model input."""
        encoding = self._tokenizer(
            text,
            max_length=MAX_SEQ_LEN,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )
        return {k: v.to(DEVICE) for k, v in encoding.items()}

    def get_embedding(self, text: str):
        """Get semantic embedding for text using the fine-tuned encoder (512-dim)."""
        if not self.is_available:
            return [0.0] * EMBEDDING_DIM

        with torch.no_grad():
            inputs = self._encode(text)
            embedding = self._model.get_embedding(
                inputs["input_ids"],
                inputs["attention_mask"]
            )
            return embedding.cpu().numpy().flatten()

    def get_embeddings_batch(self, texts: List[str], batch_size: int = 32):
        """Get embeddings for a batch of texts (512-dim each)."""
        if not self.is_available:
            return [[0.0] * EMBEDDING_DIM for _ in texts]

        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            encodings = self._tokenizer(
                batch_texts,
                max_length=MAX_SEQ_LEN,
                padding="max_length",
                truncation=True,
                return_tensors="pt"
            )
            encodings = {k: v.to(DEVICE) for k, v in encodings.items()}

            with torch.no_grad():
                embeddings = self._model.get_embedding(
                    encodings["input_ids"],
                    encodings["attention_mask"]
                )
                all_embeddings.append(embeddings.cpu().numpy())

        return np.concatenate(all_embeddings, axis=0)

    def recommend_clause_categories(
        self,
        risk_description: str,
        top_k: int = 15,
        threshold: float = 0.3
    ) -> List[Dict]:
        """
        Recommend clause categories for a risk description.

        Returns list of {category, score} sorted by relevance.
        """
        if not self.is_available:
            return []

        with torch.no_grad():
            inputs = self._encode(risk_description)
            logits = self._model(
                inputs["input_ids"],
                inputs["attention_mask"],
                task="clause"
            )
            probs = torch.sigmoid(logits).cpu().numpy().flatten()

        categories = self._config.get("clause_labels", [])
        results = []
        for cat, score in zip(categories, probs):
            if score >= threshold:
                results.append({"category": cat, "score": round(float(score), 4)})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def assess_appetite(self, risk_description: str) -> Dict:
        """
        Assess risk appetite for a given risk description.

        Returns {decision, confidence, scores: {accept, refer, decline}}.
        """
        if not self.is_available:
            return {"decision": "refer", "confidence": 0.0,
                    "scores": {"accept": 0.33, "refer": 0.34, "decline": 0.33}}

        with torch.no_grad():
            inputs = self._encode(risk_description)
            logits = self._model(
                inputs["input_ids"],
                inputs["attention_mask"],
                task="appetite"
            )
            probs = torch.softmax(logits, dim=1).cpu().numpy().flatten()

        labels = self._config.get("appetite_labels", ["accept", "refer", "decline"])
        decision_idx = int(np.argmax(probs))

        return {
            "decision": labels[decision_idx],
            "confidence": round(float(probs[decision_idx]), 4),
            "scores": {label: round(float(p), 4) for label, p in zip(labels, probs)},
        }

    def classify_pricing(self, risk_description: str) -> Dict:
        """
        Classify pricing signal for a risk description.

        Returns {band, confidence, scores: {low, medium, high}}.
        """
        if not self.is_available:
            return {"band": "medium", "confidence": 0.0,
                    "scores": {"low": 0.33, "medium": 0.34, "high": 0.33}}

        with torch.no_grad():
            inputs = self._encode(risk_description)
            logits = self._model(
                inputs["input_ids"],
                inputs["attention_mask"],
                task="pricing"
            )
            probs = torch.softmax(logits, dim=1).cpu().numpy().flatten()

        labels = self._config.get("pricing_labels", ["low", "medium", "high"])
        band_idx = int(np.argmax(probs))

        return {
            "band": labels[band_idx],
            "confidence": round(float(probs[band_idx]), 4),
            "scores": {label: round(float(p), 4) for label, p in zip(labels, probs)},
        }

    def classify_intent(self, text: str) -> Dict:
        """
        Classify insurance intent of a text.

        Returns {intent, confidence, top_intents: [{intent, score}]}.
        """
        if not self.is_available:
            return {"intent": "unknown", "confidence": 0.0, "top_intents": []}

        with torch.no_grad():
            inputs = self._encode(text)
            logits = self._model(
                inputs["input_ids"],
                inputs["attention_mask"],
                task="intent"
            )
            probs = torch.softmax(logits, dim=1).cpu().numpy().flatten()

        intents = self._config.get("intent_labels", [])
        top_indices = np.argsort(probs)[::-1][:5]

        return {
            "intent": intents[top_indices[0]] if len(intents) > top_indices[0] else "unknown",
            "confidence": round(float(probs[top_indices[0]]), 4),
            "top_intents": [
                {"intent": intents[idx] if len(intents) > idx else f"intent_{idx}",
                 "score": round(float(probs[idx]), 4)}
                for idx in top_indices
            ]
        }

    def predict_all(self, text: str) -> Dict:
        """
        Run all prediction heads on a single text.

        Returns {clauses, appetite, pricing, intent, embedding}.
        """
        if not self.is_available:
            return {
                "clauses": [],
                "appetite": {"decision": "refer", "confidence": 0.0},
                "pricing": {"band": "medium", "confidence": 0.0},
                "intent": {"intent": "unknown", "confidence": 0.0},
            }

        with torch.no_grad():
            inputs = self._encode(text)
            all_logits = self._model(
                inputs["input_ids"],
                inputs["attention_mask"],
                task=None  # returns all heads
            )

        # Clause categories (multi-label, sigmoid)
        clause_probs = torch.sigmoid(all_logits["clause"]).cpu().numpy().flatten()
        clause_labels = self._config.get("clause_labels", [])
        clauses = [
            {"category": cat, "score": round(float(s), 4)}
            for cat, s in zip(clause_labels, clause_probs) if s >= 0.3
        ]
        clauses.sort(key=lambda x: x["score"], reverse=True)

        # Appetite (softmax)
        appetite_probs = torch.softmax(all_logits["appetite"], dim=1).cpu().numpy().flatten()
        appetite_labels = self._config.get("appetite_labels", ["accept", "refer", "decline"])
        appetite_idx = int(np.argmax(appetite_probs))

        # Pricing (softmax)
        pricing_probs = torch.softmax(all_logits["pricing"], dim=1).cpu().numpy().flatten()
        pricing_labels = self._config.get("pricing_labels", ["low", "medium", "high"])
        pricing_idx = int(np.argmax(pricing_probs))

        # Intent (softmax)
        intent_probs = torch.softmax(all_logits["intent"], dim=1).cpu().numpy().flatten()
        intent_labels = self._config.get("intent_labels", [])
        intent_idx = int(np.argmax(intent_probs))

        return {
            "clauses": clauses[:15],
            "appetite": {
                "decision": appetite_labels[appetite_idx],
                "confidence": round(float(appetite_probs[appetite_idx]), 4),
                "scores": {l: round(float(p), 4) for l, p in zip(appetite_labels, appetite_probs)},
            },
            "pricing": {
                "band": pricing_labels[pricing_idx],
                "confidence": round(float(pricing_probs[pricing_idx]), 4),
                "scores": {l: round(float(p), 4) for l, p in zip(pricing_labels, pricing_probs)},
            },
            "intent": {
                "intent": intent_labels[intent_idx] if len(intent_labels) > intent_idx else "unknown",
                "confidence": round(float(intent_probs[intent_idx]), 4),
            },
        }

    def build_risk_description(self, assessment_data: Dict) -> str:
        """Build a risk description string from assessment data for ML input."""
        parts = []

        risk_category = assessment_data.get("risk_category", "")
        if risk_category:
            parts.append(f"{risk_category} insurance")

        territory = assessment_data.get("territory", "")
        if territory:
            parts.append(f"in {territory}")

        summary = assessment_data.get("summary", "")
        if summary:
            parts.append(summary[:300])

        insured = assessment_data.get("insured_entity_name", "") or assessment_data.get("insured_name", "")
        if insured:
            parts.append(f"for {insured}")

        extracted = assessment_data.get("extracted_data", {}) or {}
        if isinstance(extracted, dict):
            for key in ["perils", "coverage_type", "line_of_business", "risk_type"]:
                if key in extracted:
                    parts.append(f"{key}: {extracted[key]}")

        return ". ".join(parts) if parts else "general insurance risk"


# Singleton instance
insurance_model_service = InsuranceModelService()
