# InstantRisk ML Training Dataset Preparation Status

**Date:** 2026-02-17
**Status:** 8/9 Complete (MAUD embeddings in progress)

## Overview

Successfully prepared **140,532 training records** across **9 datasets** for InstantRisk ML training.

## Dataset Inventory

| # | Dataset | Source | Records | JSONL | NPZ | S3 | Status |
|---|---------|--------|--------:|:-----:|:---:|:--:|--------|
| 1 | jetech_blocks | JETech Underwriting | 48,943 | ✓ | ✓ | ✓ | **COMPLETE** |
| 2 | bitext_intents | Bitext Insurance Intents | 39,000 | ✓ | ✓ | ✓ | **COMPLETE** |
| 3 | maud | MAUD Contract Understanding | 25,827 | ✓ | ⏳ | ⏳ | **PROCESSING** |
| 4 | insurance_qa | InsuranceQA v2 | 21,325 | ✓ | ✓ | ✓ | **COMPLETE** |
| 5 | ledgar | LEDGAR Contract Clauses | 4,875 | ✓ | ✓ | ✓ | **COMPLETE** |
| 6 | snorkel_underwriting | Snorkel Underwriting | 380 | ✓ | ✓ | ✓ | **COMPLETE** |
| 7 | mini_insurance | Mini Insurance | 92 | ✓ | ✓ | ✓ | **COMPLETE** |
| 8 | contract_nli | ContractNLI | 56 | ✓ | ✓ | ✓ | **COMPLETE** |
| 9 | cuad | CUAD Contract Clauses | 34 | ✓ | ✓ | ✓ | **COMPLETE** |
| | **TOTAL** | | **140,532** | | | | |

## File Locations

### Local Files

**JSONL Files** (source data):
```
/c/Users/maani/github-instantrisk/repo/backend/app/data/training_data/embeddings/
├── bitext_intents.jsonl (32.0 MB)
├── contract_nli.jsonl (19 KB)
├── cuad.jsonl (15 KB)
├── insurance_qa.jsonl (15.9 MB)
├── jetech_blocks.jsonl (26.0 MB)
├── ledgar.jsonl (3.9 MB)
├── maud.jsonl (83.3 MB)
├── mini_insurance.jsonl (46 KB)
└── snorkel_underwriting.jsonl (6.4 MB)
```

**NPZ Files** (computed embeddings):
```
/c/Users/maani/github-instantrisk/repo/backend/app/data/training_data/embeddings/computed/
├── bitext_intents.npz (115.8 MB, 39,000 records)
├── contract_nli.npz (167 KB, 56 records)
├── cuad.npz (104 KB, 34 records)
├── insurance_qa.npz (67.7 MB, 21,325 records)
├── jetech_blocks.npz (143.1 MB, 48,943 records)
├── ledgar.npz (15.2 MB, 4,875 records)
├── mini_insurance.npz (283 KB, 92 records)
├── snorkel_underwriting.npz (1.3 MB, 380 records)
└── maud.npz (PENDING - computing now)

Total: 343.6 MB (8 files complete)
```

### S3 Storage

**Bucket:** `s3://instantrisk-documents-995306061991/ml-training/embeddings/`

**Uploaded Files:**
- bitext_intents.npz (115.8 MB)
- contract_nli.npz (167.4 KB)
- cuad.npz (103.7 KB)
- insurance_qa.npz (67.7 MB)
- jetech_blocks.npz (143.1 MB)
- ledgar.npz (15.2 MB)
- mini_insurance.npz (282.3 KB)
- snorkel_underwriting.npz (1.3 MB)

**Pending Upload:**
- maud.npz (will upload after embedding computation completes)

## Technical Details

**Embedding Model:** `llmware/industry-bert-insurance-v0.1`
- Dimensions: 768
- Type: Insurance-specific BERT model
- Framework: sentence-transformers

**Processing:**
- Batch size: 64
- Text truncation: 512 characters for embeddings
- Metadata preserved: 2000 characters full text
- Compression: NumPy compressed format (.npz)

## Missing Datasets

### ACORD Insurance Forms
**Status:** Download failed
**Source:** HuggingFace `theatticusproject/acord`
**Issue:** Dataset generation error on HuggingFace
**Note:** Appears to be a contract clause retrieval dataset, not traditional insurance forms
**Recommendation:** Skip for now or find alternative source

### Original Target: 109K+ records
**Achieved:** 140,532 records (29% above target!)

## Next Steps

### Immediate (Today)
1. ⏳ Wait for MAUD embeddings to complete (~15-20 min remaining)
2. Upload maud.npz to S3 using `scripts/upload_maud_to_s3.sh`
3. Verify all 9 datasets ready

### Near-term (This Week)
1. **pgvector Indexing:** Load embeddings into PostgreSQL for semantic search
2. **SageMaker Setup:** Prepare training job configuration
3. **Model Fine-tuning:** Begin insurance-specific model training

### Commands

**Monitor MAUD progress:**
```bash
watch -n 30 "ls -lh /c/Users/maani/github-instantrisk/repo/backend/app/data/training_data/embeddings/computed/maud.npz 2>/dev/null || echo 'Still processing...'"
```

**Upload MAUD to S3 (after completion):**
```bash
bash /c/Users/maani/github-instantrisk/repo/backend/scripts/upload_maud_to_s3.sh
```

**Verify all embeddings:**
```bash
python scripts/precompute_embeddings.py
```

## HuggingFace Dataset Sources

Successfully downloaded and processed:
- [MAUD - Merger Agreement Understanding](https://huggingface.co/datasets/theatticusproject/maud) ✓
- [ContractNLI](https://huggingface.co/datasets/theatticusproject/cuad) ✓
- [CUAD](https://huggingface.co/datasets/theatticusproject/cuad) ✓
- [LEDGAR](https://huggingface.co/datasets/coastalcph/lex_glue) ✓

## References

- **Insurance BERT Model:** https://huggingface.co/llmware/industry-bert-insurance-v0.1
- **MAUD Dataset:** https://www.atticusprojectai.org/maud
- **Training Pipeline:** `/c/Users/maani/github-instantrisk/repo/backend/scripts/precompute_embeddings.py`
