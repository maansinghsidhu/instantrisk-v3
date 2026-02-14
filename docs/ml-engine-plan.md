# Plan: InstantRisk Engine — Fine-Tuned Insurance ML Model

## Context

The current clause recommendation system uses keyword search against 11K clauses — producing garbage results (only 2 mandatory LMA clauses returned). The 10 LMA clauses are incomplete/useless stubs. RAG exists (47K vectors in pgvector) but the pipeline doesn't use it effectively for document generation. The user wants to replace all "AI" branding with **"InstantRisk Engine"** (not "Zeus Engine" or generic "AI").

**Goal**: Fine-tune a custom insurance ML model (the **InstantRisk Engine**) that provides:
1. **Clause selection** — which clauses fit which risks
2. **Pricing** — premium/rate estimation patterns
3. **Appetite** — what risks the syndicate wants to write
4. **Guidelines** — underwriting rules, limits, and preferences
5. **Per-user adaptation** — users who upload their own docs get a model fine-tuned to THEIR portfolio

## What Exists Today (v83 deployed)

### Data Assets
| Source | Records | Location | Content |
|--------|---------|----------|---------|
| LEDGAR | 6,804 | `insurance_data/contract_clauses/ledgar/` | Real SEC legal provisions, 100 categories |
| ContractNLI | 4,047 | `insurance_data/contract_clauses/contract_nli/` | Contract NLI pairs, entailment/contradiction |
| CUAD | 542 | `insurance_data/contract_clauses/cuad/` | Contract understanding, 41 clause types |
| LMA | 10 | `insurance_data/lma/` | **TO BE REMOVED** — incomplete stubs |
| **Total Clauses** | **11,393** | `clauses_library_service.py` | In-memory keyword search |

### RAG Vectors (pgvector, 47K+)
| Source | Type | Content |
|--------|------|---------|
| ACORD | `acord` | Standard clause library |
| CUAD | `cuad` | Contract clause understanding |
| JeTech | `underwriting_block` | Reinsurance underwriting blocks with risk details |
| LEDGAR | `ledgar` | SEC contract provisions (60K) |
| MAUD | `maud` | Merger agreement clauses (5K) |
| InsuranceQA | `insurance_qa` | Insurance Q&A pairs (21K) |
| User Uploads | `user` | Per-user training documents |

### Embedding Infrastructure
- **Model**: `llmware/industry-bert-insurance-v0.1` (768-dim, insurance-domain BERT)
- **Storage**: PostgreSQL pgvector (`rag_vectors` table)
- **Search**: Cosine similarity via `1 - (embedding <=> query_vec)`
- **Services**: `rag_indexer.py` (index), `qdrant_service.py` (user docs), `unified_rag.py` (search)

### Pipeline (19 Agents in `opendraft_generator.py`)
- Agents use Bedrock LLM (Haiku/Sonnet) for text generation
- 6/19 agents use RAG (RiskResearcher, ClauseExtractor, SectionDrafter, RiskChallenger, ComplianceReviewer, ClauseCompiler)
- Clauses are passed as `selected_clauses` list with `clause_id`, `name`, `text`, `source`
- Pipeline agents structure sections around clauses but rely on LLM to generate wording

## Data Flow: How ML Model Feeds Into Document Generation & Analysis

### Current Flow (Broken)
```
User creates assessment
  → Manual clause selection (keyword search returns garbage)
  → Triggers document generation
  → 19-agent pipeline (opendraft_generator.py)
    → Agents use RAG for context but LLM GUESSES clause wording
    → ClauseExtractor searches RAG but gets random results
    → SectionDrafter writes sections without real clause text
  → Output: Documents with made-up clause wording
```

### New Flow (With ML Model)

#### A. Assessment Analysis (Pre-Document Generation)
```
User creates assessment (risk_type, territory, sum_insured, etc.)
  │
  ├─→ insurance_model_service.recommend_clauses(assessment_text, user_id)
  │     → Base model: classify into 100+ clause categories (LEDGAR + CUAD types)
  │     → Per-user adapter: adjust weights based on user's training docs
  │     → pgvector semantic search: find top-K matching clauses
  │     → Returns: ranked list of REAL clauses with full text + relevance scores
  │
  ├─→ insurance_model_service.assess_appetite(risk_text, user_id)
  │     → Trained on JeTech underwriting blocks + Snorkel AI data
  │     → Returns: accept/refer/decline + confidence + reasoning
  │     → Per-user: adjusts based on user's uploaded guidelines
  │
  ├─→ insurance_model_service.estimate_pricing(risk_features, user_id)
  │     → Trained on JeTech pricing data + InsuranceQA
  │     → Returns: rate range (low/mid/high), suggested premium band
  │     → Per-user: adjusts based on user's pricing schedules
  │
  └─→ insurance_model_service.match_guidelines(risk_text, user_id)
        → Returns: applicable underwriting rules, limits, exclusions
        → Per-user: user's own guidelines take priority
```

**UI shows**: Recommended clauses (selectable), appetite guidance, pricing range, applicable guidelines.
User can accept/modify recommendations before generating documents.

#### B. Document Generation (19-Agent Pipeline Enhancement)
```
opendraft_generator.py receives:
  - assessment_data (risk info)
  - selected_clauses (ML-recommended, user-confirmed, with FULL TEXT)
  - ml_context = {appetite, pricing, guidelines} from ML model

Agent modifications:
  │
  ├─ agent_risk_researcher()
  │    OLD: RAG search only
  │    NEW: RAG + ML appetite assessment + guideline matches
  │    → Prompt includes: "Appetite: ACCEPT (0.87 confidence). Guidelines: max retention £5M..."
  │
  ├─ agent_clause_extractor()
  │    OLD: LLM guesses which clauses to include
  │    NEW: ML model pre-selected clauses with REAL text from library
  │    → No more guessing — actual clause wording from 11K+ clause library
  │
  ├─ agent_section_drafter()
  │    OLD: RAG context + LLM generates clause wording
  │    NEW: Gets ACTUAL clause text + ML relevance context
  │    → Prompt: "Use this EXACT clause wording: [full clause text from library]"
  │    → LLM structures around real clauses instead of inventing text
  │
  ├─ agent_risk_challenger()
  │    OLD: LLM challenges based on general knowledge
  │    NEW: ML appetite model provides data-driven challenge
  │    → "Model confidence for cyber risks in US: 0.72 (borderline). Flag: no explicit cyber exclusion clause selected."
  │
  ├─ agent_compliance_reviewer()
  │    OLD: LLM checks compliance from general knowledge
  │    NEW: ML guideline matching verifies against actual rules
  │    → "Guideline match: 'Minimum deductible for Property > $10K' — current deductible $5K. FLAG."
  │
  └─ agent_clause_compiler()
       OLD: Compiles LLM-generated clause text
       NEW: Compiles REAL clause text from library + ML-selected additions
       → Final clause schedule uses actual clause wording, not hallucinations
```

#### C. Per-User Document Analysis (Training Doc Upload)
```
User uploads training documents (policies, guidelines, pricing sheets)
  │
  ├─→ qdrant_service.py: Extract text (PDF/DOCX/Excel)
  │
  ├─→ AI Assessment (NEW — before embedding):
  │     → Classify: policy_wording / endorsement / pricing_schedule / guideline / irrelevant
  │     → Score relevance (0-1): marketing fluff → 0.1 (reject), real clause → 0.95 (keep)
  │     → Categorize chunks: clause / pricing / appetite / guideline / exclusion / condition
  │     → Extract: risk types, territories, pricing data, limits, exclusions
  │     → Filter: Remove irrelevant content (ads, disclaimers, boilerplate)
  │
  ├─→ Embed assessed chunks into user_doc_vectors (pgvector)
  │
  └─→ user_model_service.py: When enough data (50+ chunks):
        → Build training pairs from categorized user chunks
        → Fine-tune LoRA adapter on base model
        → Save to S3: s3://.../user-models/{user_id}/adapter.pt
        → User's future recommendations are personalized
```

#### D. End-to-End Example: Cyber Risk Assessment
```
1. User uploads 10 cyber policy docs → AI assesses → 340 relevant chunks
2. User model trained → adapter learns: user writes cyber at £2-5M, requires explicit data breach exclusion

3. New assessment: "Cyber liability, US tech company, $10M limit"
   → ML recommends 18 clauses:
     - Data Breach Notification (CUAD, 0.97 relevance)
     - Network Security Liability (LEDGAR, 0.95)
     - Cyber Extortion Coverage (CUAD, 0.93)
     - Limitation of Liability (LEDGAR, 0.91)
     - ... 14 more ranked by relevance
   → Appetite: ACCEPT (0.89) — user's model confirms this fits their book
   → Pricing: Rate band 1.2-1.8% (based on JeTech + user's historic pricing)
   → Guidelines: "User requires: minimum $50K retention, mandatory breach notification clause"

4. Document generation:
   → SectionDrafter uses ACTUAL "Data Breach Notification" clause text (not hallucinated)
   → ComplianceReviewer flags: "Missing mandatory breach notification clause" if omitted
   → Output: Professional MRC Slip with real clause wording from the library
```

## Changes Required

### Step 0: Deploy Existing Local Changes (v84)
**Already staged but uncommitted:**
- Frontend logo replacements (logo-icon.png, logo-full.png, favicon.png, PWA icons)
- Frontend Dart files (use logo-icon for small sizes in AppBar, sidebar, login)
- `clauses.py` recommend endpoint rewrite (risk_search_map approach)
- `clauses_library_service.py` is_mandatory fix

**Action:** Commit + deploy these as v84 before starting ML work.

### Step 1: Remove LMA Clauses + Branding Changes
**Files to modify:**
- `backend/app/services/clauses_library_service.py` — Remove `_load_lma_clauses()` call
- `backend/app/data/insurance_data/lma/` — Keep but don't load (may add real LMA later)
- `backend/app/routers/clauses.py` — Remove ALL LMA mandatory references from recommend endpoint
- Frontend: Replace all "AI Generated" / "Zeus Engine" text with **"InstantRisk Engine"**
  - Document generation screens, headers, footers
  - Any reference to "AI-powered" → "InstantRisk Engine powered"

### Step 2: Download Additional Insurance Datasets
**New datasets to download from HuggingFace:**

| Dataset | Records | Purpose | URL |
|---------|---------|---------|-----|
| `snorkelai/Multi-Turn-Insurance-Underwriting` | ~100 | Underwriting tasks with appetite matrix, guidelines, tool use | HuggingFace |
| `bitext/Bitext-insurance-llm-chatbot-training-dataset` | ~39K | 39 insurance intents, 1K examples each — claim filing, coverage, pricing | HuggingFace |
| `deccan-ai/insuranceQA-v2` | ~21K | Insurance Q&A for domain understanding | HuggingFace |
| `JETech/underwriting-dataset-blocks` | ~5K | Reinsurance underwriting blocks with risk, pricing, territory | HuggingFace |
| `sujra/mini-insurance` | ~1K | Insurance classification dataset | HuggingFace |

**Download to:** `backend/app/data/insurance_data/training/` (new directory)

### Step 3: Create Training Data Pipeline
**New file:** `backend/app/services/model_trainer.py`

Build training pairs from ALL data for multi-task fine-tuning:

**Task A — Clause Recommendation (multi-label classification)**
- Input: Risk description (category + territory + perils + features)
- Output: Relevant clause categories (from LEDGAR 100 categories + CUAD 41 types)
- Training data: Use clause text → infer what risk types they apply to
- ~11K training pairs from existing clause data

**Task B — Risk Appetite Classification**
- Input: Risk description
- Output: accept / refer / decline + confidence
- Training data: JeTech underwriting blocks + Snorkel AI underwriting dataset
- ~5K+ training pairs

**Task C — Pricing Signal Extraction**
- Input: Risk features (category, territory, sum insured, claims history)
- Output: Rate indicators (high/medium/low) + suggested rate range
- Training data: JeTech blocks contain pricing info + InsuranceQA pricing questions
- ~2K+ training pairs

**Task D — Guideline Matching**
- Input: Risk description
- Output: Relevant underwriting guidelines and limits
- Training data: Snorkel AI guidelines + Bitext insurance intents
- ~1K+ training pairs

### Step 4: Fine-Tune Insurance-BERT
**New file:** `backend/app/services/model_trainer.py`

Fine-tune `llmware/industry-bert-insurance-v0.1` using multi-task learning:

```
Base model: llmware/industry-bert-insurance-v0.1 (768-dim)
Training approach: Multi-task with shared encoder
  - Head A: Clause category classifier (100+ labels, sigmoid)
  - Head B: Appetite classifier (3 labels, softmax)
  - Head C: Pricing regressor (rate indicator)
  - Head D: Guideline similarity (contrastive learning)

Training:
  - Use SageMaker training job OR local with torch
  - Epochs: 10-20
  - Batch size: 32
  - Learning rate: 2e-5
  - Save to S3: s3://instantrisk-pipeline-artifacts-995306061991/models/
```

**Output:** Fine-tuned model saved as `instantrisk-insurance-bert-v1`

### Step 5: Embed ALL Clauses with Fine-Tuned Model
**File to modify:** `backend/app/services/rag_indexer.py`

After fine-tuning:
1. Re-embed all 11K+ clauses using the fine-tuned model
2. Store in pgvector with enhanced metadata (clause_type, risk_categories, pricing_relevance)
3. Upload pre-computed embeddings to S3 for fast deployment

### Step 6: Replace Keyword Search with ML Inference
**Files to modify:**
- `backend/app/routers/clauses.py` — `recommend_clauses_for_assessment()` endpoint
  - Old: keyword search `clauses_library_service.search(category=risk_category)`
  - New: Embed assessment description → query pgvector → return top-K clauses by cosine similarity + run classifier heads for appetite/pricing

- `backend/app/services/clauses_library_service.py`
  - Add `semantic_search(query_text, top_k)` method using pgvector
  - Falls back to keyword search if model unavailable

- **New file:** `backend/app/services/insurance_model_service.py`
  - Singleton service that loads the fine-tuned model
  - Methods: `recommend_clauses(assessment_text)`, `assess_appetite(risk_text)`, `estimate_pricing(risk_features)`, `match_guidelines(risk_text)`

### Step 7: Improve Pipeline Integration
**File to modify:** `backend/app/services/opendraft_generator.py`

- `agent_clause_extractor()` — Use ML model to find relevant clauses instead of LLM guessing
- `agent_section_drafter()` — Feed actual clause TEXT from library (not just names) into prompts
- `agent_risk_challenger()` — Use appetite model to challenge risk decisions
- `agent_compliance_reviewer()` — Use guideline matching to check compliance

### Step 8: Per-User ML Model Training Pipeline
**Goal**: When users upload training documents, AI assesses them, categorizes properly, removes irrelevant content, and trains an individual ML model per user.

**Existing infrastructure** (already works):
- `qdrant_service.py` — Upload → extract text → chunk → embed → store in `user_doc_vectors` (per-user isolation via `user_id`)
- `document_processor.py` — AI classification (document type, risk type, field extraction, confidence scoring)
- `user_doc_vectors` table — pgvector with HNSW index, filtered by `user_id`

**New/Modified files:**

**A. Enhanced Document Assessment** (`backend/app/services/qdrant_service.py`)
- On upload, run AI assessment BEFORE embedding:
  1. Classify document type (policy, endorsement, claims, guidelines, pricing schedule, etc.)
  2. Extract structured fields (risk types, territories, lines of business, pricing data)
  3. Score relevance (0-1) — filter out irrelevant content (marketing, spam, duplicates)
  4. Auto-categorize chunks: `clause`, `pricing`, `appetite`, `guideline`, `exclusion`, `condition`
  5. Store category + relevance metadata alongside vectors

**B. Per-User Model Manager** (`backend/app/services/user_model_service.py` — **Create**)
- Triggered after user uploads enough data (minimum threshold: ~50 relevant chunks)
- Creates a lightweight adapter layer (LoRA-style) on top of the base fine-tuned model
- Training flow:
  1. Collect all user's `user_doc_vectors` chunks with categories
  2. Build user-specific training pairs from categorized chunks
  3. Fine-tune a small adapter (not full model) — fast, ~2-5 min per user
  4. Save adapter weights to S3: `s3://instantrisk-pipeline-artifacts-995306061991/user-models/{user_id}/`
  5. Load adapter at inference time for that user's requests
- Adapter approach means: base model (shared, ~400MB) + per-user adapter (~5-10MB each)

**C. Per-User Inference** (`backend/app/services/insurance_model_service.py`)
- `recommend_clauses(assessment_text, user_id)` — loads user adapter if available, falls back to base model
- `assess_appetite(risk_text, user_id)` — user's appetite preferences learned from their docs
- `estimate_pricing(risk_features, user_id)` — user's pricing patterns
- User model cache: LRU cache of loaded adapters (max 10 users in memory)

**D. Training Status API** (`backend/app/routers/training.py` — Modify)
- `GET /training/model-status` — Returns user's model training status (not_started, training, ready, stale)
- `POST /training/retrain` — Manually trigger user model retraining
- Auto-retrain when user uploads 20+ new chunks since last training

### Step 9: Assessment Field Enhancements
**Files to modify:**
- `backend/app/models/assessment.py` — Add new fields:
  - `inception_date` — Next inception date (DateField)
  - `renewal_date` — Renewal at next inception date
  - `broker_name` — Broker name (e.g., Marsh)
  - `commission_rate` — Agreed commission level (%)
  - `insured_entity_name` — Full entity name (highest point / totality of entity)
  - `companies_house_number` — Companies House registration for entity verification
  - `loss_run_reporting_rules` — Loss run reporting rules text
  - `regulatory_framework` — European regulation / Solvency II framework reference
- `backend/app/routers/assessments.py` — Accept new fields in create/update endpoints
- `backend/app/services/opendraft_generator.py` — Use these fields in document generation:
  - Inception/renewal dates in policy headers
  - Broker + commission in MRC slip format
  - Insured entity + Companies House in policy schedule
  - Loss run rules in claims section
  - Regulatory framework in compliance section
- Frontend assessment creation/edit forms — Add input fields for all new data

### Step 10: Deploy
- Commit and push all changes
- Upload base fine-tuned model to S3
- Deploy backend (v85+) with model loading at startup
- Deploy frontend with branding changes
- Verify clause recommendations return meaningful results
- Test document generation end-to-end
- Test per-user model flow: upload docs → auto-assess → train → verify personalized results

## Key Files to Modify/Create

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/services/clauses_library_service.py` | Modify | Remove LMA loading, add semantic search |
| `backend/app/routers/clauses.py` | Modify | ML-based recommendations instead of keyword |
| `backend/app/services/model_trainer.py` | **Create** | Base model training pipeline for fine-tuning |
| `backend/app/services/insurance_model_service.py` | **Create** | Inference service (base + per-user adapters) |
| `backend/app/services/user_model_service.py` | **Create** | Per-user adapter training + management |
| `backend/app/services/qdrant_service.py` | Modify | Add AI assessment + categorization on upload |
| `backend/app/services/rag_indexer.py` | Modify | Re-embed with fine-tuned model |
| `backend/app/services/opendraft_generator.py` | Modify | Use ML service in pipeline agents |
| `backend/app/routers/training.py` | Modify | Add model status + retrain endpoints |
| `backend/app/routers/document_generation.py` | Modify | Pass ML predictions to pipeline |
| `backend/app/models/assessment.py` | Modify | Add inception_date, broker, commission, companies_house fields |
| `backend/app/routers/assessments.py` | Modify | Accept new assessment fields in API |
| `backend/app/data/insurance_data/training/` | **Create** | New training datasets from HuggingFace |
| Frontend logo/icon files | Modify | Already staged from previous work |
| Frontend branding | Modify | "AI Generated" → "InstantRisk Engine" everywhere |
| Frontend assessment forms | Modify | Add inception date, broker, commission, entity fields |

## Verification

1. **Data check**: `GET /clauses/statistics` returns correct counts (no LMA — should be ~11,393)
2. **Recommendation check**: `POST /clauses/recommend/{id}` returns 15-20 relevant clauses with proper names and relevance scores
3. **Semantic search**: `GET /clauses/library?search=cyber liability` returns semantically relevant results (not just keyword matches)
4. **Appetite check**: New endpoint `POST /underwriting/appetite` returns accept/refer/decline for a risk description
5. **Document generation**: Full pipeline generates documents with proper clause wordings from the library
6. **Base model metrics**: Classification accuracy >80% on held-out test set
7. **Per-user model**: Upload 5+ training docs → `GET /training/model-status` shows `ready` → recommendations differ from base model
8. **Document assessment**: Upload irrelevant doc → AI flags low relevance, doesn't pollute user model
9. **Branding**: No "AI Generated" or "Zeus Engine" text anywhere — all shows "InstantRisk Engine"
10. **Assessment fields**: Create assessment with inception_date, broker, commission → these appear in generated documents

## Implementation Order (Phased Deployment)

**Phase A — v84 (Quick wins, deploy immediately):**
- Step 0: Deploy existing local changes (logos, recommend endpoint fix)
- Step 1: Remove LMA + branding changes

**Phase B — v85 (ML Foundation):**
- Step 2: Download training datasets
- Step 3: Create training data pipeline
- Step 4: Fine-tune base model
- Step 5: Re-embed clauses

**Phase C — v86 (ML Integration):**
- Step 6: Replace keyword search with ML inference
- Step 7: Pipeline integration
- Step 8: Per-user model training

**Phase D — v87 (Assessment Enhancements):**
- Step 9: Assessment field enhancements
- Step 10: Final deploy + end-to-end testing
