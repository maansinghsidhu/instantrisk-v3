# ML Model Integration Plan

**Goal:** Ensure the 146K training records properly feed into backend analysis and document generation as intended.

---

## Current State (v98)

### What Works
- ✅ Base insurance-BERT embeddings (semantic search)
- ✅ RAG-enhanced document generation (6/19 agents use RAG)
- ✅ Clause library (11K+ clauses)
- ✅ 146K training records prepared and uploaded to S3

### What's Missing
- ❌ Fine-tuned model not deployed yet (training in progress)
- ❌ Multi-task heads (appetite, pricing, intent) not active
- ❌ Training data not yet utilized in predictions
- ❌ Per-user adaptation not implemented

---

## Integration Architecture

### Data Flow: Training → Inference → Document Generation

```
┌─────────────────────────────────────────────────────────────┐
│ TRAINING PHASE (One-time, then periodic retraining)        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  146K Records                                               │
│  ├─ Bitext (39K)    → Intent Classification                │
│  ├─ JETech (49K)    → Appetite + Pricing + Clauses         │
│  ├─ InsuranceQA     → Intent + Domain Knowledge            │
│  ├─ MAUD (26K)      → Clause Understanding                 │
│  ├─ ContractNLI     → Clause Relationships                 │
│  ├─ ACORD (747)     → Standard Forms                       │
│  ├─ Snorkel (380)   → Underwriting Decisions               │
│  └─ Mini Insurance  → Risk Classification                  │
│                                                             │
│                      ↓                                      │
│                                                             │
│  Multi-Task Fine-Tuning                                    │
│  ├─ Shared BERT Encoder (insurance-BERT base)              │
│  ├─ Task A: Clause Head (134 labels)                       │
│  ├─ Task B: Appetite Head (3 classes)                      │
│  ├─ Task C: Pricing Head (3 classes)                       │
│  ├─ Task D: Intent Head (39 classes)                       │
│  └─ Task E: Guideline Head (embedding)                     │
│                                                             │
│                      ↓                                      │
│                                                             │
│  Output: instantrisk-engine-v1/model.pt                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ INFERENCE PHASE (Every API request)                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  User Creates Assessment                                   │
│  ├─ Risk type: "Cyber Liability"                           │
│  ├─ Territory: "United States"                             │
│  ├─ Sum insured: "$10M"                                    │
│  └─ Description: "Tech company, SaaS platform..."          │
│                                                             │
│                      ↓                                      │
│                                                             │
│  insurance_model_service.analyze(assessment)               │
│  │                                                          │
│  ├─→ Embed assessment text (768-dim)                       │
│  │                                                          │
│  ├─→ Task A: Clause Recommendation                         │
│  │   ├─ Multi-label classification (134 categories)        │
│  │   ├─ Returns: [cyber_liability: 0.95,                   │
│  │   │            data_breach: 0.92,                        │
│  │   │            network_security: 0.89, ...]             │
│  │   └─ Use for: Filtering clause library search           │
│  │                                                          │
│  ├─→ Task B: Risk Appetite                                 │
│  │   ├─ 3-class classification                             │
│  │   ├─ Returns: {class: "accept",                         │
│  │   │            confidence: 0.87,                         │
│  │   │            reasoning: "..."}                         │
│  │   └─ Use for: Pre-screening, guidance to underwriters   │
│  │                                                          │
│  ├─→ Task C: Pricing Signal                                │
│  │   ├─ 3-class classification (low/medium/high)           │
│  │   ├─ Returns: {band: "medium",                          │
│  │   │            rate_range: "1.2-1.8%",                   │
│  │   │            confidence: 0.72}                         │
│  │   └─ Use for: Pricing guidance, rate validation         │
│  │                                                          │
│  ├─→ Task D: Intent Classification                         │
│  │   ├─ 39-class (insurance operations)                    │
│  │   ├─ Returns: {intent: "new_insurance_policy",          │
│  │   │            confidence: 0.94}                         │
│  │   └─ Use for: Routing, automation triggers              │
│  │                                                          │
│  └─→ Semantic Search (RAG)                                 │
│      ├─ Query pgvector with embedding                      │
│      ├─ Filter by clause categories from Task A            │
│      ├─ Returns: Top-K matching clauses with full text     │
│      └─ Use for: Document generation                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ DOCUMENT GENERATION (19-Agent Pipeline)                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  opendraft_generator.py receives:                          │
│  ├─ assessment_data (user input)                           │
│  ├─ selected_clauses (from ML + user selection)            │
│  └─ ml_context (appetite, pricing, guidelines)             │
│                                                             │
│  agent_risk_researcher()                                   │
│  ├─ OLD: RAG search only                                   │
│  ├─ NEW: RAG + ML appetite + pricing                       │
│  └─ Prompt: "Risk: Cyber Liability. ML Appetite: ACCEPT    │
│              (0.87). Pricing: Medium band (1.2-1.8%).       │
│              Research cyber liability risks for tech..."    │
│                                                             │
│  agent_clause_extractor()                                  │
│  ├─ OLD: LLM guesses which clauses                         │
│  ├─ NEW: ML pre-selected clauses from Task A               │
│  └─ Returns: REAL clause IDs from library                  │
│                                                             │
│  agent_section_drafter()                                   │
│  ├─ OLD: RAG context + LLM generates wording               │
│  ├─ NEW: EXACT clause text from library                    │
│  └─ Prompt: "Use this EXACT clause text:                   │
│              [Data Breach Notification Clause]             │
│              The Insured shall notify the Company..."       │
│                                                             │
│  agent_risk_challenger()                                   │
│  ├─ OLD: LLM challenges from general knowledge             │
│  ├─ NEW: ML appetite model provides data-driven challenge  │
│  └─ Prompt: "ML confidence: 0.87 (borderline for cyber).   │
│              Challenge: No explicit cyber exclusion         │
│              clause selected. Flag for review."             │
│                                                             │
│  agent_compliance_reviewer()                               │
│  ├─ OLD: LLM checks from general knowledge                 │
│  ├─ NEW: ML guideline matching                             │
│  └─ Prompt: "Guideline match: 'Min deductible >$10K'.      │
│              Current: $5K. FLAG: Non-compliant."            │
│                                                             │
│  agent_clause_compiler()                                   │
│  ├─ OLD: Compiles LLM-generated text                       │
│  ├─ NEW: Compiles REAL clause text from library            │
│  └─ Output: Professional MRC Slip with actual clauses      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Phase 1: Backend Integration (Current Priority)

#### 1.1 Update insurance_model_service.py

**File:** `backend/app/services/insurance_model_service.py`

**Changes Needed:**
```python
class InsuranceModelService:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.device = None
        self.clause_labels = []

    def load_model(self, model_path: str):
        """Load fine-tuned multi-task model."""
        # Load config
        config = json.load(open(f"{model_path}/config.json"))
        self.clause_labels = config["clause_labels"]

        # Load model
        self.model = MultiTaskInsuranceModel()
        self.model.load_state_dict(torch.load(f"{model_path}/model.pt"))
        self.model.eval()

    def analyze_assessment(self, assessment_text: str, user_id: Optional[str] = None):
        """Complete ML analysis of assessment."""
        # Embed
        encoding = self.tokenizer(assessment_text, ...)

        # Run all task heads
        with torch.no_grad():
            outputs = self.model(encoding["input_ids"], encoding["attention_mask"], task="all")

        # Task A: Clause recommendations
        clause_logits = outputs["clause"]
        clause_probs = torch.sigmoid(clause_logits)
        top_clause_indices = clause_probs.topk(20).indices
        recommended_clauses = [
            {"category": self.clause_labels[idx], "score": clause_probs[idx].item()}
            for idx in top_clause_indices
        ]

        # Task B: Appetite
        appetite_logits = outputs["appetite"]
        appetite_probs = torch.softmax(appetite_logits, dim=-1)
        appetite_class = appetite_probs.argmax().item()
        appetite_labels = ["accept", "refer", "decline"]

        # Task C: Pricing
        pricing_logits = outputs["pricing"]
        pricing_probs = torch.softmax(pricing_logits, dim=-1)
        pricing_class = pricing_probs.argmax().item()
        pricing_labels = ["low", "medium", "high"]

        # Task D: Intent
        intent_logits = outputs["intent"]
        intent_probs = torch.softmax(intent_logits, dim=-1)
        intent_class = intent_probs.argmax().item()

        return {
            "clause_recommendations": recommended_clauses,
            "appetite": {
                "decision": appetite_labels[appetite_class],
                "confidence": appetite_probs[appetite_class].item(),
                "probabilities": {
                    label: appetite_probs[i].item()
                    for i, label in enumerate(appetite_labels)
                }
            },
            "pricing": {
                "band": pricing_labels[pricing_class],
                "confidence": pricing_probs[pricing_class].item(),
            },
            "intent": {
                "category": self.intent_labels[intent_class],
                "confidence": intent_probs[intent_class].item(),
            },
            "embedding": outputs["guideline"].cpu().numpy(),  # For RAG search
        }
```

#### 1.2 Update clauses.py Router

**File:** `backend/app/routers/clauses.py`

**Changes:**
```python
@router.post("/recommend/{assessment_id}")
async def recommend_clauses_for_assessment(assessment_id: int, db: AsyncSession = Depends(get_db)):
    """ML-powered clause recommendations."""

    # Get assessment
    assessment = await db.get(Assessment, assessment_id)

    # Build assessment text
    assessment_text = f"{assessment.risk_category} insurance for {assessment.territory}. "
    assessment_text += f"Sum insured: {assessment.sum_insured}. "
    if assessment.description:
        assessment_text += assessment.description

    # ML analysis
    ml_results = insurance_model_service.analyze_assessment(assessment_text, assessment.user_id)

    # Get clause categories from ML
    clause_categories = [c["category"] for c in ml_results["clause_recommendations"][:10]]

    # Semantic search for actual clauses
    clauses = await unified_rag.search_clauses(
        query=assessment_text,
        embedding=ml_results["embedding"],
        filters={"category": clause_categories},
        top_k=20
    )

    # Return with ML metadata
    return {
        "clauses": clauses,
        "ml_analysis": {
            "appetite": ml_results["appetite"],
            "pricing": ml_results["pricing"],
            "confidence": ml_results["clause_recommendations"][0]["score"]
        }
    }
```

#### 1.3 Update Document Generation Pipeline

**File:** `backend/app/services/opendraft_generator.py`

**Changes:**
```python
async def generate_document(assessment_id: int, document_type: str, selected_clauses: List[int]):
    """Generate document with ML-enhanced pipeline."""

    # Get ML analysis
    assessment_text = _build_assessment_text(assessment)
    ml_context = insurance_model_service.analyze_assessment(assessment_text)

    # Get full clause TEXT from library (not just IDs)
    clause_texts = await _get_clause_full_texts(selected_clauses)

    # Agent 1: Risk Researcher (with ML context)
    research_prompt = f"""
    Risk: {assessment.risk_category}

    ML Analysis:
    - Appetite: {ml_context['appetite']['decision']} ({ml_context['appetite']['confidence']:.2f} confidence)
    - Pricing: {ml_context['pricing']['band']} band
    - Top clause categories: {', '.join(ml_context['clause_recommendations'][:5])}

    Research this risk and identify key considerations.
    """
    research = await agent_risk_researcher(research_prompt)

    # Agent 5: Section Drafter (with REAL clause text)
    for section in sections:
        relevant_clauses = _filter_clauses_for_section(clause_texts, section)

        draft_prompt = f"""
        Section: {section.title}

        Use these EXACT clause wordings (DO NOT modify):

        {chr(10).join(f"[{c.id}] {c.name}:\\n{c.text}\\n" for c in relevant_clauses)}

        Structure the section around these clauses. Use their exact text.
        """

        section_text = await agent_section_drafter(draft_prompt)

    # Agent 9: Risk Challenger (with ML appetite)
    challenge_prompt = f"""
    ML Appetite Analysis:
    - Decision: {ml_context['appetite']['decision']}
    - Confidence: {ml_context['appetite']['confidence']:.2f}
    - Accept probability: {ml_context['appetite']['probabilities']['accept']:.2f}
    - Refer probability: {ml_context['appetite']['probabilities']['refer']:.2f}
    - Decline probability: {ml_context['appetite']['probabilities']['decline']:.2f}

    If confidence <0.85 or decision is REFER/DECLINE, flag specific concerns.
    Review selected clauses for gaps or conflicts with appetite.
    """
    challenges = await agent_risk_challenger(challenge_prompt)
```

### Phase 2: Frontend Integration

#### 2.1 Update Assessment Analysis Screen

**File:** `frontend/lib/presentation/screens/assessments/analysis_screen.dart`

**Add ML Analysis Card:**
```dart
class MLAnalysisCard extends StatelessWidget {
  final Map<String, dynamic> mlAnalysis;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'InstantRisk Engine Analysis',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            SizedBox(height: 16),

            // Appetite
            _buildAnalysisRow(
              'Risk Appetite',
              mlAnalysis['appetite']['decision'].toUpperCase(),
              mlAnalysis['appetite']['confidence'],
              _getAppetiteColor(mlAnalysis['appetite']['decision']),
            ),

            // Pricing
            _buildAnalysisRow(
              'Pricing Band',
              mlAnalysis['pricing']['band'].toUpperCase(),
              mlAnalysis['pricing']['confidence'],
              _getPricingColor(mlAnalysis['pricing']['band']),
            ),

            SizedBox(height: 16),

            // Confidence indicator
            LinearProgressIndicator(
              value: mlAnalysis['confidence'],
              backgroundColor: Colors.grey[200],
              valueColor: AlwaysStoppedAnimation<Color>(
                _getConfidenceColor(mlAnalysis['confidence']),
              ),
            ),
            SizedBox(height: 8),
            Text(
              'Overall Confidence: ${(mlAnalysis['confidence'] * 100).toStringAsFixed(0)}%',
              style: TextStyle(fontSize: 12, color: Colors.grey[600]),
            ),
          ],
        ),
      ),
    );
  }
}
```

#### 2.2 Update Clause Review Screen

**File:** `frontend/lib/presentation/screens/documents/clause_review_screen.dart`

**Show ML scores:**
```dart
class ClauseListItem extends StatelessWidget {
  final Clause clause;
  final double? mlScore;  // NEW

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text(clause.name),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(clause.category),
          if (mlScore != null) ...[
            SizedBox(height: 4),
            Row(
              children: [
                Icon(Icons.psychology, size: 12, color: Colors.blue),
                SizedBox(width: 4),
                Text(
                  'ML Relevance: ${(mlScore! * 100).toStringAsFixed(0)}%',
                  style: TextStyle(
                    fontSize: 11,
                    color: Colors.blue,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
      trailing: Checkbox(...),
    );
  }
}
```

---

## Testing Plan

### 1. Unit Tests

**Test ML Model Loading:**
```python
def test_model_loads_correctly():
    service = InsuranceModelService()
    service.load_model("app/data/models/instantrisk-engine-v1-sagemaker")
    assert service.model is not None
    assert len(service.clause_labels) == 134
```

**Test Analysis Output:**
```python
def test_analyze_assessment():
    service = InsuranceModelService()
    service.load_model(...)

    result = service.analyze_assessment(
        "Cyber liability for US tech company, $10M coverage"
    )

    assert "appetite" in result
    assert result["appetite"]["decision"] in ["accept", "refer", "decline"]
    assert 0 <= result["appetite"]["confidence"] <= 1
    assert len(result["clause_recommendations"]) > 0
```

### 2. Integration Tests

**Test End-to-End Flow:**
```python
async def test_clause_recommendation_e2e():
    # Create assessment
    assessment = await create_assessment(
        risk_category="Cyber Liability",
        territory="United States",
        sum_insured=10000000
    )

    # Get recommendations
    response = await client.post(f"/api/v1/clauses/recommend/{assessment.id}")

    assert response.status_code == 200
    data = response.json()

    # Should have ML analysis
    assert "ml_analysis" in data
    assert "appetite" in data["ml_analysis"]

    # Should have relevant clauses
    assert len(data["clauses"]) > 0
    assert any("cyber" in c["name"].lower() for c in data["clauses"])
```

### 3. Manual Testing

**Scenario 1: Cyber Risk**
1. Create assessment: "Cyber liability, US tech company, $10M"
2. Check clause recommendations include:
   - Data breach notification
   - Network security liability
   - Cyber extortion coverage
3. Check appetite shows ACCEPT with high confidence
4. Check pricing shows MEDIUM band

**Scenario 2: High-Risk Property**
1. Create assessment: "Property, earthquake zone, $50M"
2. Check clauses include earthquake exclusions
3. Check appetite shows REFER or DECLINE
4. Check pricing shows HIGH band

---

## Deployment Checklist

- [ ] Fine-tuned model available at `app/data/models/instantrisk-engine-v1-sagemaker/model.pt`
- [ ] Config.json with 134 clause labels present
- [ ] `insurance_model_service.py` updated with multi-task analysis
- [ ] `clauses.py` router updated to use ML
- [ ] `opendraft_generator.py` agents updated with ML context
- [ ] Frontend screens updated to show ML analysis
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] Manual testing complete
- [ ] Backend deployed to ECS
- [ ] Frontend deployed
- [ ] End-to-end smoke test passed

---

**Status:** Waiting for SageMaker training to complete, then implement above changes.
