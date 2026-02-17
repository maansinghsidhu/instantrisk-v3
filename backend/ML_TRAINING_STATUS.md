# InstantRisk ML Training - Status Update

**Date:** 2026-02-17
**Status:** IN PROGRESS - SageMaker Training Job Launching

---

## ✅ Completed Steps

### 1. Data Collection (141,279 records)

| Dataset | Records | Status | File |
|---------|--------:|--------|------|
| JETech Underwriting Blocks | 48,943 | ✅ | jetech_blocks.jsonl |
| Bitext Insurance Intents | 39,000 | ✅ | bitext_intents.jsonl |
| MAUD Contract Understanding | 25,827 | ✅ | maud.jsonl |
| InsuranceQA v2 | 21,325 | ✅ | insurance_qa.jsonl |
| LEDGAR Contract Provisions | 4,875 | ✅ | ledgar.jsonl |
| **ACORD Forms (NEW!)** | **747** | ✅ | acord_forms.jsonl |
| Snorkel Underwriting | 380 | ✅ | snorkel_underwriting.jsonl |
| Mini Insurance | 92 | ✅ | mini_insurance.jsonl |
| ContractNLI | 56 | ✅ | contract_nli.jsonl |
| CUAD Clauses | 34 | ✅ | cuad.jsonl |
| **TOTAL** | **141,279** | | |

**vs Original Target:** 141,279 / 109,000 = **129% achieved** (+32K records)

### 2. Embeddings Computed

All 10 datasets have pre-computed embeddings using `llmware/industry-bert-insurance-v0.1`:

| File | Size | Records | Status |
|------|------|--------:|--------|
| jetech_blocks.npz | 144 MB | 48,943 | ✅ |
| bitext_intents.npz | 116 MB | 39,000 | ✅ |
| maud.npz | 86 MB | 25,827 | ✅ |
| insurance_qa.npz | 68 MB | 21,325 | ✅ |
| ledgar.npz | 16 MB | 4,875 | ✅ |
| **acord_forms.npz** | **833 KB** | **747** | ✅ |
| snorkel_underwriting.npz | 1.3 MB | 380 | ✅ |
| mini_insurance.npz | 283 KB | 92 | ✅ |
| contract_nli.npz | 168 KB | 56 | ✅ |
| cuad.npz | 104 KB | 34 | ✅ |
| **TOTAL** | **~432 MB** | **141,279** | |

### 3. ACORD Data Acquisition

**Problem:** HuggingFace `theatticusproject/acord` dataset has generation error (won't download)

**Solution:** Downloaded ACORD forms from Sensible Configuration Library

Successfully downloaded:
- ✅ ACORD 125 (Commercial Insurance Application) - 476 fields
- ✅ ACORD 140 (Property Loss Notice) - 263 fields
- ✅ ACORD 823 (Flood Insurance Application) - 8 fields

**Total:** 747 ACORD training records extracted from form configurations

### 4. Training Infrastructure

**Scripts Created:**
- ✅ `scripts/download_acord_forms.py` - Downloads ACORD forms from GitHub
- ✅ `scripts/embed_acord.py` - Computes embeddings for ACORD data
- ✅ `scripts/train_local.py` - Local training (fallback)
- ✅ `scripts/run_sagemaker_training.py` - Complete SageMaker pipeline
- ✅ `scripts/train_sagemaker.py` - Multi-task training script (ready)

**AWS Resources:**
- ✅ S3 Bucket: `instantrisk-documents-995306061991`
- ✅ IAM Role: `instantrisk-backend-task-role`
- ✅ ECR Repository: `instantrisk-backend`
- ✅ Fresh AWS credentials configured (expires in ~12 hours)

---

## 🔄 Current Step: SageMaker Training

**Training Job Configuration:**
- **Instance:** ml.g5.xlarge (GPU, $1.41/hour)
- **Container:** HuggingFace PyTorch 2.1 + Transformers 4.36
- **Base Model:** llmware/industry-bert-insurance-v0.1 (768-dim BERT)
- **Training Records:** 127,151 (90% of 141,279)
- **Validation Records:** 14,128 (10% of 141,279)

**Multi-Task Heads:**
1. **Clause Recommendation** - 134 labels (multi-label classification)
2. **Risk Appetite** - 3 classes (accept/refer/decline)
3. **Pricing Signal** - 3 classes (low/medium/high)
4. **Intent Classification** - 39 insurance intents
5. **Guideline Matching** - Embedding projection (contrastive learning)

**Hyperparameters:**
- Epochs: 5
- Batch size: 16
- Learning rate: 2e-5
- Max length: 512 tokens
- Warmup steps: 500
- Weight decay: 0.01

**Estimated Time:** 2-4 hours on GPU
**Estimated Cost:** $3-6 for training job

---

## 📋 What Happens Next

### Training Pipeline (Automated)

1. ✅ **Data Preparation** - Combine all 10 datasets, shuffle, 90/10 split
2. 🔄 **Upload to S3** - Upload train.jsonl and val.jsonl
3. 🔄 **Launch SageMaker** - Create training job
4. ⏳ **Monitor Progress** - Track training metrics
5. ⏳ **Download Model** - Retrieve trained model.tar.gz from S3
6. ⏳ **Extract & Deploy** - Unpack model to `app/data/models/instantrisk-engine-v1-sagemaker/`

### If SageMaker Fails

**Fallback:** Local training script (`train_local.py`)
- Requires GPU for reasonable performance (2-4 hours)
- CPU training possible but slow (10-20 hours)
- Alternative: Use Google Colab free GPU

---

## 📊 Expected Results

**Baseline Metrics (insurance-BERT base model):**
- Embedding quality: Good for insurance domain
- Clause search: Semantic similarity works but no classification

**After Fine-Tuning (InstantRisk Engine v1):**
- **Clause Recommendation F1:** Target >0.75 (multi-label, 134 classes)
- **Appetite Accuracy:** Target >0.80 (3-class)
- **Pricing Accuracy:** Target >0.65 (3-class, heuristic labels)
- **Intent Accuracy:** Target >0.85 (39-class)

**Real-World Impact:**
- Clause recommendations go from keyword-based (garbage) to ML-powered (relevant)
- Document generation uses REAL clause text instead of LLM hallucinations
- Risk appetite guidance data-driven instead of random
- Per-user personalization possible (LoRA adapters)

---

## 🎯 Deployment Plan

### After Training Completes

1. **Test Model Locally**
   ```bash
   python -m app.services.insurance_model_service --test
   ```

2. **Verify Recommendations Improved**
   - Create test assessment (e.g., "Cyber liability, US tech company, $10M")
   - Check that recommended clauses are relevant
   - Verify appetite/pricing signals make sense

3. **Deploy to ECS**
   - Update task definition with new model path
   - Deploy backend v99 with fine-tuned model
   - Monitor performance (inference latency <500ms p95)

4. **Frontend Updates**
   - No changes needed (API contract unchanged)
   - UI already shows clause recommendations
   - ML predictions seamlessly integrated

### Rollback Plan

If issues occur:
- Keep v98 running (base model)
- Fall back to keyword search
- No database changes needed (backward compatible)

---

## 🔍 Monitoring

**Training Job:**
```bash
# Check status
aws sagemaker describe-training-job --training-job-name instantrisk-engine-YYYYMMDD-HHMMSS

# View CloudWatch logs
aws logs tail /aws/sagemaker/TrainingJobs --follow
```

**Local Process:**
- Running in background (task ID: b6301d0)
- Output: `C:\Users\maani\AppData\Local\Temp\claude\C--Users-maani\tasks\b6301d0.output`

---

## 📝 Notes

### Why ACORD Data Matters

ACORD (Association for Cooperative Operations Research and Development) is the insurance industry standard for forms and data exchange. Having ACORD forms in training data:
- Improves recognition of standard insurance terminology
- Better field extraction from policy documents
- More accurate clause categorization
- Industry-standard compliance

### Training Data Quality

**High Quality (Labeled):**
- LEDGAR: 100 legal provision categories (supervised)
- CUAD: 41 contract clause types (supervised)
- Bitext: 39 insurance intents (supervised)
- Snorkel: Underwriting decisions (supervised)

**Medium Quality (Heuristic):**
- JETech: Pricing/appetite inferred from text
- InsuranceQA: Q&A pairs (weak supervision)
- ACORD: Form fields (structural supervision)

**Lower Quality (Unsupervised):**
- MAUD: Generic contract clauses (transferred knowledge)
- ContractNLI: Entailment pairs (auxiliary task)
- Mini Insurance: Small dataset (augmentation)

### Next Phase: Per-User Models

After base model is trained:
1. Users upload their own policy documents
2. AI assesses and categorizes uploaded content
3. Lightweight LoRA adapter trained (5-10MB per user)
4. User gets personalized recommendations based on their portfolio
5. Adapter loaded at inference time (LRU cache, max 10 users in memory)

**Cost:** ~$0.10 per user model (2-5 minutes training on CPU)

---

## ✅ Success Criteria

- [x] 109K+ training records collected → **141K achieved**
- [x] ACORD data included → **747 records**
- [x] Embeddings pre-computed → **All 10 datasets**
- [ ] SageMaker training job launched
- [ ] Training completes with F1 >0.75
- [ ] Model deployed to production
- [ ] Recommendations verified as relevant
- [ ] End-to-end document generation working

---

**Last Updated:** 2026-02-17 21:20 UTC
**Next Check:** Monitor SageMaker job status (every 5 minutes)
