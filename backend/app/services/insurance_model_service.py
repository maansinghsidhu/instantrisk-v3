"""
InstantRisk Engine - ML Inference Service

Provides intelligent recommendations using the fine-tuned insurance-BERT model:
- Clause recommendations based on risk description
- Risk appetite assessment (accept/refer/decline)
- Insurance intent classification
- Pricing signal classification
- Semantic search via fine-tuned embeddings
- Per-user personalized predictions via lightweight adapters

Falls back to keyword search if model is not available.
"""

import os
import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

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

# EFS mount paths (primary — persistent, shared across deployments)
EFS_MODEL_DIR_BEST = "/mnt/efs/models/instantrisk-engine-v1-best"
EFS_MODEL_DIR_FINAL = "/mnt/efs/models/instantrisk-engine-v1-final"
EFS_SENTENCE_TRANSFORMER = "/mnt/efs/models/sentence-transformer-insurance"

# Fallback: bundled in Docker image (app/data/models/)
LOCAL_MODEL_DIR_BEST = os.path.join(os.path.dirname(__file__), "..", "data", "models", "instantrisk-engine-v1-best")
LOCAL_MODEL_DIR_FINAL = os.path.join(os.path.dirname(__file__), "..", "data", "models", "instantrisk-engine-v1-final")
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

        # Find model directory: EFS first, then local
        if model_dir is None:
            for candidate in [EFS_MODEL_DIR_BEST, EFS_MODEL_DIR_FINAL, LOCAL_MODEL_DIR_BEST, LOCAL_MODEL_DIR_FINAL]:
                if os.path.exists(os.path.join(candidate, "model.pt")):
                    model_dir = candidate
                    break
            if model_dir is None:
                print("InstantRisk Engine model not found — running in fallback mode")
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
                model_dir=model_dir,
            ).to(DEVICE)

            # Load trained weights (state_dict only)
            state_dict = torch.load(model_path, map_location=DEVICE, weights_only=True)
            self._model.load_state_dict(state_dict)
            self._model.eval()

            # Load tokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)

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

    def load_from_s3(self, s3_uri: str, target: str = "best") -> bool:
        """
        Download model.tar.gz from S3, extract, and hot-reload into service.

        Args:
            s3_uri:  Full S3 URI, e.g. s3://bucket/path/to/model.tar.gz
            target:  Which local slot to overwrite — "best" or "final"
        """
        import boto3
        import tarfile
        import shutil
        import tempfile

        # Parse S3 URI
        parts = s3_uri.replace("s3://", "").split("/", 1)
        bucket = parts[0]
        key = parts[1]

        # Save to EFS if available, otherwise local
        efs_models_dir = "/mnt/efs/models"
        if os.path.isdir("/mnt/efs"):
            models_dir = efs_models_dir
        else:
            models_dir = os.path.join(os.path.dirname(__file__), "..", "data", "models")
        os.makedirs(models_dir, exist_ok=True)

        slot_name = "instantrisk-engine-v1-best" if target == "best" else "instantrisk-engine-v1-final"
        target_dir = os.path.join(models_dir, slot_name)

        # Download to a temp file
        local_tar = os.path.join(models_dir, "model_download.tar.gz")
        print(f"Downloading model from {s3_uri} ...")
        s3 = boto3.client('s3', region_name='us-east-1')
        s3.download_file(bucket, key, local_tar)
        print(f"Download complete ({os.path.getsize(local_tar) // (1024*1024)} MB)")

        # Extract to a temp directory first so we can locate model.pt
        with tempfile.TemporaryDirectory() as tmp_dir:
            print(f"Extracting ...")
            with tarfile.open(local_tar, 'r:gz') as tar:
                tar.extractall(tmp_dir)

            # Walk to find the directory containing model.pt
            model_root = None
            for root, dirs, files in os.walk(tmp_dir):
                if "model.pt" in files:
                    model_root = root
                    break

            if model_root is None:
                print(f"ERROR: model.pt not found in archive. Contents: {os.listdir(tmp_dir)}")
                os.remove(local_tar)
                return False

            print(f"Found model files in: {model_root}")

            # Copy to target dir (replace existing)
            os.makedirs(target_dir, exist_ok=True)
            for fname in os.listdir(model_root):
                src = os.path.join(model_root, fname)
                dst = os.path.join(target_dir, fname)
                shutil.copy2(src, dst)
                print(f"  Installed: {fname}")

        # Clean up download
        os.remove(local_tar)

        # Reset loaded state and reload from the new files
        self._loaded = False
        self._available = False
        self._model = None
        self._tokenizer = None
        return self.load(target_dir)

    def load_from_sagemaker_job(self, job_name: str, target: str = "best") -> bool:
        """
        Download and hot-reload model from a completed SageMaker training job.

        Args:
            job_name:  SageMaker training job name
            target:    Which local model slot to update — "best" (default) or "final"
        """
        import boto3

        sagemaker = boto3.client('sagemaker', region_name='us-east-1')
        response = sagemaker.describe_training_job(TrainingJobName=job_name)

        status = response['TrainingJobStatus']
        if status != 'Completed':
            print(f"Training job {job_name} status: {status} (not completed)")
            return False

        s3_uri = response['ModelArtifacts']['S3ModelArtifacts']
        print(f"Training job completed. Model artifacts: {s3_uri}")
        return self.load_from_s3(s3_uri, target=target)

    @property
    def is_available(self) -> bool:
        """Check if the ML model is loaded and available."""
        if not self._loaded:
            self.load()
        return self._available

    def _encode(self, text: str) -> Dict[str, "torch.Tensor"]:
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

    def _get_user_adapter(self, user_id: Optional[str]):
        """Load user adapter if available. Returns (adapter, shared_features_fn) or (None, None)."""
        if not user_id:
            return None
        try:
            from app.services.user_model_service import user_model_service
            return user_model_service.load_adapter(user_id)
        except Exception as e:
            logger.debug(f"No user adapter for {user_id}: {e}")
            return None

    def _get_shared_features(self, inputs):
        """Get shared projection features from the base model (for adapter use)."""
        outputs = self._model.encoder(
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
        )
        cls_output = outputs.last_hidden_state[:, 0, :]
        return self._model.shared_proj(cls_output)

    def recommend_clause_categories(
        self,
        risk_description: str,
        top_k: int = 15,
        threshold: float = 0.3,
        user_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Recommend clause categories for a risk description.

        If user_id is provided and user has a trained adapter,
        predictions are personalized to the user's portfolio.

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

            # Apply user adapter if available
            adapter = self._get_user_adapter(user_id)
            if adapter is not None:
                shared = self._get_shared_features(inputs)
                logits = adapter.forward(shared, logits, task="clause")

            probs = torch.sigmoid(logits).cpu().numpy().flatten()

        categories = self._config.get("clause_labels", [])
        results = []
        for cat, score in zip(categories, probs):
            if score >= threshold:
                results.append({"category": cat, "score": round(float(score), 4)})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def assess_appetite(self, risk_description: str, user_id: Optional[str] = None) -> Dict:
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

            adapter = self._get_user_adapter(user_id)
            if adapter is not None:
                shared = self._get_shared_features(inputs)
                logits = adapter.forward(shared, logits, task="appetite")

            probs = torch.softmax(logits, dim=1).cpu().numpy().flatten()

        labels = self._config.get("appetite_labels", ["accept", "refer", "decline"])
        decision_idx = int(np.argmax(probs))

        return {
            "decision": labels[decision_idx],
            "confidence": round(float(probs[decision_idx]), 4),
            "scores": {label: round(float(p), 4) for label, p in zip(labels, probs)},
        }

    def classify_pricing(self, risk_description: str, user_id: Optional[str] = None) -> Dict:
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

            adapter = self._get_user_adapter(user_id)
            if adapter is not None:
                shared = self._get_shared_features(inputs)
                logits = adapter.forward(shared, logits, task="pricing")

            probs = torch.softmax(logits, dim=1).cpu().numpy().flatten()

        labels = self._config.get("pricing_labels", ["low", "medium", "high"])
        band_idx = int(np.argmax(probs))

        return {
            "band": labels[band_idx],
            "confidence": round(float(probs[band_idx]), 4),
            "scores": {label: round(float(p), 4) for label, p in zip(labels, probs)},
        }

    def classify_intent(self, text: str, user_id: Optional[str] = None) -> Dict:
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

            adapter = self._get_user_adapter(user_id)
            if adapter is not None:
                shared = self._get_shared_features(inputs)
                logits = adapter.forward(shared, logits, task="intent")

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

    def predict_all(self, text: str, user_id: Optional[str] = None) -> Dict:
        """
        Run all prediction heads on a single text.

        If user_id is provided and user has a trained adapter,
        predictions are personalized to the user's portfolio.

        Returns {clauses, appetite, pricing, intent, personalized}.
        """
        if not self.is_available:
            return {
                "clauses": [],
                "appetite": {"decision": "refer", "confidence": 0.0},
                "pricing": {"band": "medium", "confidence": 0.0},
                "intent": {"intent": "unknown", "confidence": 0.0},
                "personalized": False,
            }

        with torch.no_grad():
            inputs = self._encode(text)
            all_logits = self._model(
                inputs["input_ids"],
                inputs["attention_mask"],
                task=None  # returns all heads
            )

            # Apply user adapter if available
            adapter = self._get_user_adapter(user_id)
            personalized = adapter is not None
            if personalized:
                shared = self._get_shared_features(inputs)
                all_logits = adapter.forward(shared, all_logits, task=None)

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
            "personalized": personalized,
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
