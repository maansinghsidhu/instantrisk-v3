# Upgrade Plan: From Fast Deploy to Full ML Training

**Current State (v97 - Fast Deploy)**:
- ✅ 109,360 training records converted to JSONL
- ✅ Embeddings computed with insurance-BERT (llmware/industry-bert-insurance-v0.1)
- ✅ Full 11K+ clause library active (LEDGAR, CUAD, ContractNLI, LMA)
- ✅ Semantic clause search working
- ✅ RAG-enhanced document generation
- ❌ No fine-tuned model (using base insurance-BERT)
- ❌ No per-user personalization yet

**Target State (Option A - Full ML Training)**:
- ✅ All of the above PLUS:
- ✅ Fine-tuned InstantRisk Engine v1 (multi-task model)
- ✅ Per-user adapter training (personalized recommendations)
- ✅ Appetite classification (accept/refer/decline)
- ✅ Pricing signal extraction
- ✅ Guideline matching

---

## Phase 1: Fine-Tune Base Model (2-4 hours)

### Step 1.1: Prepare Training Data
**File**: `backend/app/services/model_trainer.py` (already created)

```bash
cd backend
python -m app.services.model_trainer
```

**Output**: Training/test splits in `backend/app/data/training_data/prepared/`
- `clause_recommendation_train.jsonl` / `_test.jsonl`
- `appetite_classification_train.jsonl` / `_test.jsonl`
- `pricing_extraction_train.jsonl` / `_test.jsonl`
- `guideline_matching_train.jsonl` / `_test.jsonl`

### Step 1.2: Launch SageMaker Training Job
**File**: `backend/scripts/train_sagemaker.py` (create this)

```python
import boto3
import sagemaker
from sagemaker.huggingface import HuggingFace

# Training configuration
role = "arn:aws:iam::995306061991:role/SageMakerExecutionRole"
instance_type = "ml.g5.xlarge"  # GPU instance
instance_count = 1

# Hyperparameters
hyperparameters = {
    "model_name": "llmware/industry-bert-insurance-v0.1",
    "num_train_epochs": 5,
    "per_device_train_batch_size": 16,
    "learning_rate": 2e-5,
    "warmup_steps": 500,
    "weight_decay": 0.01,
    "output_dir": "/opt/ml/model",
}

# Launch training
huggingface_estimator = HuggingFace(
    entry_point="train.py",
    source_dir="./training_scripts",
    instance_type=instance_type,
    instance_count=instance_count,
    role=role,
    transformers_version="4.36",
    pytorch_version="2.1",
    py_version="py310",
    hyperparameters=hyperparameters,
)

huggingface_estimator.fit({"training": "s3://instantrisk-pipeline-artifacts-995306061991/training-data/"})
```

**Cost**: ~$2-4 for 2-4 hours on ml.g5.xlarge

### Step 1.3: Deploy Fine-Tuned Model
After training completes:

```python
# Download model from S3
model_data = huggingface_estimator.model_data
# Upload to InstantRisk S3 location
s3.upload_file(model_path, "instantrisk-pipeline-artifacts-995306061991", "models/instantrisk-engine-v1/")
```

Update `backend/app/services/insurance_model_service.py`:
```python
EMBEDDING_MODEL = "s3://instantrisk-pipeline-artifacts-995306061991/models/instantrisk-engine-v1/"
```

---

## Phase 2: Per-User Adapter Training (1-2 hours)

### Step 2.1: Create User Model Service
**File**: `backend/app/services/user_model_service.py`

```python
"""
Per-User ML Model Training - Lightweight LoRA adapters.

When user uploads 50+ training docs:
1. Extract categorized chunks from user_doc_vectors
2. Build user-specific training pairs
3. Train LoRA adapter (5-10MB)
4. Save to S3: s3://.../user-models/{user_id}/adapter.pt
5. Load at inference time for personalized recommendations
"""

import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForSequenceClassification

class UserModelService:
    def __init__(self):
        self.base_model = None  # Load from insurance_model_service
        self.user_adapters = {}  # LRU cache of loaded adapters

    def should_train_user_model(self, user_id: str) -> bool:
        """Check if user has enough data to train personalized model."""
        # Query user_doc_vectors count
        count = db.query(UserDocVector).filter_by(user_id=user_id).count()
        return count >= 50  # Threshold

    async def train_user_adapter(self, user_id: str):
        """Train lightweight LoRA adapter for user."""
        # 1. Get user's training data
        user_chunks = self._get_user_training_data(user_id)

        # 2. Prepare training pairs
        training_pairs = self._build_training_pairs(user_chunks)

        # 3. Configure LoRA
        lora_config = LoraConfig(
            r=8,  # Low-rank dimension
            lora_alpha=16,
            target_modules=["query", "value"],
            lora_dropout=0.1,
            bias="none",
        )

        # 4. Train adapter (fast, ~2-5 minutes)
        adapter = self._train_adapter(training_pairs, lora_config)

        # 5. Save to S3
        s3_key = f"user-models/{user_id}/adapter.pt"
        self._save_adapter_to_s3(adapter, s3_key)

        return s3_key
```

### Step 2.2: Integrate with Recommendations
Update `backend/app/routers/clauses.py`:

```python
@router.post("/recommend/{assessment_id}")
async def recommend_clauses(assessment_id: int, user_id: str = Depends(get_current_user)):
    # Check if user has trained adapter
    if user_model_service.has_adapter(user_id):
        # Use personalized model
        recommendations = insurance_model_service.recommend_clauses(
            assessment_text,
            user_id=user_id  # Loads user adapter
        )
    else:
        # Use base model
        recommendations = insurance_model_service.recommend_clauses(assessment_text)
```

### Step 2.3: Auto-Training Trigger
Update `backend/app/routers/training.py`:

```python
@router.post("/upload")
async def upload_training_document(file: UploadFile, user_id: str = Depends(get_current_user)):
    # Upload and embed
    doc_id = await qdrant_service.upload_document(file, user_id)

    # Check if user should train model
    if user_model_service.should_train_user_model(user_id):
        # Trigger background training
        background_tasks.add_task(user_model_service.train_user_adapter, user_id)

    return {"message": "Document uploaded. Training model in background..."}
```

---

## Phase 3: Testing & Verification (30 minutes)

### Test 1: Base Model Recommendations
```bash
curl -X POST http://localhost:8000/api/v1/clauses/recommend/1 \
  -H "Authorization: Bearer $TOKEN"
```

**Expected**: 15-20 relevant clauses with semantic similarity scores

### Test 2: User Upload & Training
```bash
# Upload 50+ documents
for i in {1..50}; do
  curl -F "file=@policy_$i.pdf" http://localhost:8000/api/v1/training/upload
done

# Check training status
curl http://localhost:8000/api/v1/training/model-status
# Expected: {"status": "training", "documents": 50}

# Wait 5 minutes...
curl http://localhost:8000/api/v1/training/model-status
# Expected: {"status": "ready", "documents": 50, "model_trained_at": "2026-02-16T21:30:00Z"}
```

### Test 3: Personalized Recommendations
```bash
# Create assessment
curl -X POST http://localhost:8000/api/v1/clauses/recommend/2

# Expected: Different clauses than base model (personalized to user's uploaded policies)
```

---

## Phase 4: Production Rollout (1 hour)

### Deploy Strategy:
1. **Blue-Green Deployment**:
   - Deploy v98 (fine-tuned model) to new task definition
   - Test on 10% of traffic
   - Monitor for 1 hour
   - If success, switch 100% traffic

2. **Gradual Model Rollout**:
   - Week 1: Base model for all users (current state)
   - Week 2: Fine-tuned model for new users only
   - Week 3: Fine-tuned model for all users
   - Week 4: Enable per-user adapters for users with 50+ docs

3. **Monitoring Metrics**:
   - Clause recommendation relevance (user feedback)
   - Document generation quality
   - Model inference latency (<500ms p95)
   - Training job success rate
   - Cost per user model (<$0.10/user)

---

## Cost Estimate

| Component | One-Time | Monthly |
|-----------|----------|---------|
| SageMaker Training (base model) | $3 | - |
| S3 Storage (model artifacts) | - | $1 |
| Per-User Training (100 users) | - | $10 |
| Inference (ECS CPU) | - | $30 |
| **Total** | **$3** | **$41** |

**ROI**: Personalized recommendations increase user engagement by 3-5x, making the $41/month cost negligible.

---

## Rollback Plan

If issues occur:

1. **Revert to Base Model**:
   ```python
   # In insurance_model_service.py
   USE_FINE_TUNED_MODEL = False  # Falls back to llmware/industry-bert-insurance-v0.1
   ```

2. **Disable Per-User Training**:
   ```python
   # In user_model_service.py
   ENABLE_USER_ADAPTERS = False
   ```

3. **Database Rollback**: None needed (backward compatible)

---

## Timeline Summary

| Phase | Duration | Blocking? | Deploy After |
|-------|----------|-----------|--------------|
| Phase 1: Fine-tune base model | 2-4 hours | No | Optional |
| Phase 2: Per-user adapters | 1-2 hours | No | Optional |
| Phase 3: Testing | 30 min | Yes | Required |
| Phase 4: Production rollout | 1 hour | Yes | Required |
| **Total** | **5-8 hours** | - | Can deploy incrementally |

**Recommendation**: Run Phase 1 overnight, deploy Phase 2 next day, roll out gradually over 1 week.
