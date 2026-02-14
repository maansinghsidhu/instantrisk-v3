"""
InstantRisk Engine - Multi-Task Insurance Model Trainer

Fine-tunes llmware/industry-bert-insurance-v0.1 with 4 task heads:
  A. Clause Category Classifier (100+ labels, sigmoid — multi-label)
  B. Risk Appetite Classifier (accept/refer/decline, softmax)
  C. Pricing Signal Classifier (low/medium/high rate band)
  D. Insurance Intent Classifier (39 intents from Bitext)

Training data sources:
  - LEDGAR (6,804 contract provisions, 100 categories)
  - CUAD (542 contract clauses, 41 types)
  - ContractNLI (4,047 NLI clauses)
  - Bitext Insurance (39,000 intent-labeled examples)
  - JeTech Underwriting (49,944 reinsurance blocks)
  - Snorkel AI (380 multi-turn underwriting tasks)
  - InsuranceQA (21,325 Q&A pairs)
  - Mini Insurance (96 instruction pairs)

Output: Fine-tuned model saved to S3 or local path.
"""

import json
import os
import random
import hashlib
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModel


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class TrainerConfig:
    """Training configuration."""
    # Model
    base_model: str = "llmware/industry-bert-insurance-v0.1"
    max_seq_length: int = 256
    hidden_size: int = 768  # BERT hidden size

    # Training
    epochs: int = 15
    batch_size: int = 32
    learning_rate: float = 2e-5
    weight_decay: float = 0.01
    warmup_steps: int = 500
    max_grad_norm: float = 1.0

    # Task weights (how much each task contributes to total loss)
    clause_weight: float = 1.0
    appetite_weight: float = 1.5
    pricing_weight: float = 1.0
    intent_weight: float = 0.8

    # Data paths
    data_dir: str = ""
    clause_data_dir: str = ""
    training_data_dir: str = ""

    # Output
    output_dir: str = ""
    model_name: str = "instantrisk-engine-v1"

    # Eval
    eval_split: float = 0.1
    log_every: int = 50


# =============================================================================
# Label Registries
# =============================================================================

# LEDGAR 100 categories (from clauses_library_service.py)
LEDGAR_CATEGORIES = [
    "adjustments", "agreements", "amendments", "anti-corruption", "arbitration",
    "assignments", "audits", "authorized_representative", "base_salary", "benefits",
    "binding", "board_composition", "board_meetings", "books_and_records", "brokers",
    "business_combination", "buyout", "cap_on_liability", "change_of_control",
    "choice_of_law", "closing_date", "closing_deliveries", "compliance",
    "conditions_precedent", "confidentiality", "consent_rights", "consideration",
    "covenants", "definitions", "disclosure", "disputes", "drag_along",
    "effectiveness", "employment", "entire_agreement", "equity", "escrow",
    "events_of_default", "exclusivity", "execution", "exercise_period", "expenses",
    "fee", "financial_reporting", "financing", "force_majeure", "further_assurances",
    "general_provisions", "good_faith", "governing_law", "guarantees", "holdback",
    "ip_rights", "indemnification", "information_rights", "insurance", "interest",
    "jurisdiction", "knowledge", "lease", "limitation_of_liability",
    "liquidated_damages", "liquidity", "litigation", "material_adverse_change",
    "milestones", "miscellaneous", "non-compete", "non-solicitation", "notice",
    "participation", "payment_terms", "penalties", "performance", "preemptive_rights",
    "price", "publicity", "purchase_and_sale", "recitals", "redemption",
    "registration_rights", "remedies", "renewal", "representations", "resignation",
    "restrictive_covenants", "rights", "risk_of_loss", "severability",
    "shareholder_rights", "stock_options", "subordination", "survival", "tag_along",
    "taxes", "term", "termination", "third_party_rights", "transfer", "warranties"
]

# CUAD 41 clause types
CUAD_TYPES = [
    "document_name", "parties", "agreement_date", "effective_date", "expiration_date",
    "renewal_term", "notice_period_to_terminate_renewal", "governing_law",
    "most_favored_nation", "non-compete", "exclusivity", "no-solicit_of_customers",
    "competitive_restriction_exception", "no-solicit_of_employees", "non-disparagement",
    "termination_for_convenience", "rofr_rofo_rofn", "change_of_control",
    "anti-assignment", "revenue_profit_sharing", "price_restrictions",
    "minimum_commitment", "volume_restriction", "ip_ownership_assignment",
    "joint_ip_ownership", "license_grant", "non-transferable_license",
    "affiliate_license_licensor", "affiliate_license_licensee",
    "unlimited_all_you_can_eat_license", "irrevocable_or_perpetual_license",
    "source_code_escrow", "post-termination_services", "audit_rights",
    "uncapped_liability", "cap_on_liability", "liquidated_damages",
    "warranty_duration", "insurance", "covenant_not_to_sue", "third_party_beneficiary"
]

# Combined clause labels (deduplicated)
ALL_CLAUSE_LABELS = sorted(set(LEDGAR_CATEGORIES + CUAD_TYPES))

# Risk appetite labels
APPETITE_LABELS = ["accept", "refer", "decline"]

# Pricing band labels
PRICING_LABELS = ["low", "medium", "high"]

# Insurance intent labels (from Bitext)
INTENT_LABELS = [
    "accept_settlement", "appeal_denied_insurance_claim", "cancel_insurance_policy",
    "change_deductible", "check_claim_status", "claim_insurance", "compare_policies",
    "contact_agent", "coverage_details", "dispute_invoice",
    "enroll_dependents", "enroll_insurance_plan", "file_claim", "file_complaint",
    "get_quote", "increase_coverage", "information_auto_insurance",
    "information_health_insurance", "information_home_insurance",
    "information_life_insurance", "information_pet_insurance",
    "information_travel_insurance", "make_payment", "negotiate_settlement",
    "new_insurance_policy", "receive_payment", "reduce_coverage",
    "refund_payment", "reject_settlement", "renew_insurance_policy",
    "report_incident", "request_documentation", "review_claim",
    "track_claim", "track_payment", "update_beneficiary",
    "update_contact_information", "update_coverage", "update_payment_method"
]


# =============================================================================
# Training Data Builder
# =============================================================================

class TrainingDataBuilder:
    """Builds training pairs from all data sources."""

    def __init__(self, config: TrainerConfig):
        self.config = config
        self.clause_label_to_idx = {l: i for i, l in enumerate(ALL_CLAUSE_LABELS)}
        self.appetite_label_to_idx = {l: i for i, l in enumerate(APPETITE_LABELS)}
        self.pricing_label_to_idx = {l: i for i, l in enumerate(PRICING_LABELS)}
        self.intent_label_to_idx = {l: i for i, l in enumerate(INTENT_LABELS)}

    def build_all(self) -> Dict[str, List[dict]]:
        """Build training data for all tasks."""
        data = {
            "clause": [],
            "appetite": [],
            "pricing": [],
            "intent": [],
        }

        print("Building training pairs from all data sources...")

        # Task A: Clause classification from LEDGAR, CUAD, ContractNLI
        data["clause"] = self._build_clause_data()

        # Task B: Appetite classification from Snorkel + JeTech
        data["appetite"] = self._build_appetite_data()

        # Task C: Pricing classification from JeTech + InsuranceQA
        data["pricing"] = self._build_pricing_data()

        # Task D: Intent classification from Bitext
        data["intent"] = self._build_intent_data()

        for task, pairs in data.items():
            print(f"  {task}: {len(pairs)} training pairs")

        return data

    def _build_clause_data(self) -> List[dict]:
        """Build clause classification training pairs from existing clause library data."""
        pairs = []
        clause_dir = self.config.clause_data_dir

        # Load LEDGAR
        ledgar_path = os.path.join(clause_dir, "contract_clauses", "ledgar")
        for filename in ["train.json", "validation.json", "test.json"]:
            filepath = os.path.join(ledgar_path, filename)
            if not os.path.exists(filepath):
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    records = json.load(f)
                for rec in records:
                    text = rec.get("text", "")
                    label_idx = rec.get("label", 0)
                    category = LEDGAR_CATEGORIES[label_idx] if label_idx < len(LEDGAR_CATEGORIES) else "general_provisions"
                    if text and category in self.clause_label_to_idx:
                        # Multi-label: one-hot encode
                        labels = [0.0] * len(ALL_CLAUSE_LABELS)
                        labels[self.clause_label_to_idx[category]] = 1.0
                        pairs.append({"text": text[:512], "labels": labels, "task": "clause"})
            except Exception as e:
                print(f"  Error loading LEDGAR {filename}: {e}")

        # Load CUAD
        cuad_path = os.path.join(clause_dir, "contract_clauses", "cuad")
        for filename in ["train.json", "test.json", "train_full.json"]:
            filepath = os.path.join(cuad_path, filename)
            if not os.path.exists(filepath):
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    records = json.load(f)
                is_full = filename == "train_full.json"
                for rec in records:
                    if is_full:
                        text = rec.get("text", "")
                        category = rec.get("category", "general").lower().replace(" ", "_").replace("/", "_")
                    else:
                        text = rec.get("context", "")
                        question = rec.get("question", "")
                        category = "general"
                        for ct in CUAD_TYPES:
                            if ct.replace("_", " ") in question.lower():
                                category = ct
                                break
                    if text and category in self.clause_label_to_idx:
                        labels = [0.0] * len(ALL_CLAUSE_LABELS)
                        labels[self.clause_label_to_idx[category]] = 1.0
                        pairs.append({"text": text[:512], "labels": labels, "task": "clause"})
            except Exception as e:
                print(f"  Error loading CUAD {filename}: {e}")

        # Load ContractNLI
        nli_path = os.path.join(clause_dir, "contract_clauses", "contract_nli")
        for filename in ["train.json", "dev.json", "test.json", "train_full.json"]:
            filepath = os.path.join(nli_path, filename)
            if not os.path.exists(filepath):
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    records = json.load(f)
                is_full = filename == "train_full.json"
                for rec in records:
                    if is_full:
                        text = rec.get("text", "")
                        category = rec.get("category", "general").lower().replace(" ", "_")
                    else:
                        text = rec.get("sentence1", "")
                        category = self._infer_clause_category(text)
                    if text and category in self.clause_label_to_idx:
                        labels = [0.0] * len(ALL_CLAUSE_LABELS)
                        labels[self.clause_label_to_idx[category]] = 1.0
                        pairs.append({"text": text[:512], "labels": labels, "task": "clause"})
            except Exception as e:
                print(f"  Error loading ContractNLI {filename}: {e}")

        print(f"  Clause pairs: {len(pairs)}")
        return pairs

    def _build_appetite_data(self) -> List[dict]:
        """Build appetite classification from Snorkel + JeTech data."""
        pairs = []
        training_dir = self.config.training_data_dir

        # Snorkel AI: Has explicit appetite check tasks
        snorkel_path = os.path.join(training_dir, "snorkel_underwriting.json")
        if os.path.exists(snorkel_path):
            try:
                with open(snorkel_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
                for rec in records:
                    task = rec.get("task", "")
                    company_desc = rec.get("company description", "")
                    lob = rec.get("lob", "")
                    state = rec.get("state", "")
                    ref_answer = rec.get("reference answer", "")
                    correct = rec.get("correct", False)

                    # Build input text
                    text = f"LOB: {lob}. Company: {company_desc[:200]}. State: {state}."

                    if task == "Appetite Check":
                        # Determine label from reference answer
                        ref_lower = ref_answer.lower()
                        if "not in appetite" in ref_lower or "decline" in ref_lower or "no" in ref_lower[:10]:
                            label = "decline"
                        elif "refer" in ref_lower or "review" in ref_lower:
                            label = "refer"
                        else:
                            label = "accept"
                        pairs.append({"text": text, "label": self.appetite_label_to_idx[label], "task": "appetite"})

                    elif task == "Small Business Elibility Check":
                        # Eligibility = appetite
                        ref_lower = ref_answer.lower()
                        if "not eligible" in ref_lower or "ineligible" in ref_lower:
                            label = "decline"
                        elif "additional" in ref_lower or "review" in ref_lower:
                            label = "refer"
                        else:
                            label = "accept"
                        pairs.append({"text": text, "label": self.appetite_label_to_idx[label], "task": "appetite"})

                    elif task == "Product Recommendations":
                        # If products recommended, it's in appetite
                        if "no other" in ref_answer.lower() or "not in appetite" in ref_answer.lower():
                            label = "decline"
                        else:
                            label = "accept"
                        pairs.append({"text": text, "label": self.appetite_label_to_idx[label], "task": "appetite"})

            except Exception as e:
                print(f"  Error loading Snorkel: {e}")

        # JeTech: Underwriting blocks contain risk acceptance signals
        jetech_path = os.path.join(training_dir, "jetech_underwriting_blocks.json")
        if os.path.exists(jetech_path):
            try:
                with open(jetech_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
                # Sample JeTech blocks that contain underwriting text
                for rec in records[:5000]:  # Limit to avoid memory issues
                    text = rec.get("Text", "")
                    if not text or len(text) < 50:
                        continue
                    text_lower = text.lower()
                    # Heuristic: classify based on content
                    if any(w in text_lower for w in ["decline", "excluded", "not acceptable", "reject", "outside appetite"]):
                        label = "decline"
                    elif any(w in text_lower for w in ["refer", "further review", "additional information", "subject to"]):
                        label = "refer"
                    elif any(w in text_lower for w in ["accept", "approved", "within appetite", "rate", "premium", "coverage"]):
                        label = "accept"
                    else:
                        continue  # Skip ambiguous blocks
                    pairs.append({"text": text[:512], "label": self.appetite_label_to_idx[label], "task": "appetite"})

            except Exception as e:
                print(f"  Error loading JeTech for appetite: {e}")

        print(f"  Appetite pairs: {len(pairs)}")
        return pairs

    def _build_pricing_data(self) -> List[dict]:
        """Build pricing signal classification from JeTech + InsuranceQA."""
        pairs = []
        training_dir = self.config.training_data_dir

        # JeTech: Extract pricing-related blocks
        jetech_path = os.path.join(training_dir, "jetech_underwriting_blocks.json")
        if os.path.exists(jetech_path):
            try:
                with open(jetech_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
                for rec in records[:10000]:
                    text = rec.get("Text", "")
                    if not text or len(text) < 30:
                        continue
                    text_lower = text.lower()
                    # Look for pricing signals
                    has_pricing = any(w in text_lower for w in [
                        "rate", "premium", "price", "cost", "deductible",
                        "retention", "limit", "sublimit", "excess", "commission"
                    ])
                    if not has_pricing:
                        continue
                    # Classify pricing band based on context
                    if any(w in text_lower for w in ["high risk", "catastroph", "adverse", "surcharge", "increase"]):
                        label = "high"
                    elif any(w in text_lower for w in ["competitive", "favorable", "discount", "reduce", "standard"]):
                        label = "low"
                    else:
                        label = "medium"
                    pairs.append({"text": text[:512], "label": self.pricing_label_to_idx[label], "task": "pricing"})

            except Exception as e:
                print(f"  Error loading JeTech for pricing: {e}")

        # InsuranceQA: Extract pricing-related Q&A
        qa_path = os.path.join(training_dir, "insuranceqa_v2.json")
        if os.path.exists(qa_path):
            try:
                with open(qa_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
                for rec in records:
                    question = rec.get("input", "")
                    answer = rec.get("output", "")
                    q_lower = question.lower()
                    if any(w in q_lower for w in ["cost", "price", "premium", "rate", "expensive", "cheap", "afford"]):
                        text = f"Q: {question} A: {answer}"
                        a_lower = answer.lower()
                        if any(w in a_lower for w in ["expensive", "high", "increase", "costly"]):
                            label = "high"
                        elif any(w in a_lower for w in ["cheap", "low", "affordable", "discount", "save"]):
                            label = "low"
                        else:
                            label = "medium"
                        pairs.append({"text": text[:512], "label": self.pricing_label_to_idx[label], "task": "pricing"})

            except Exception as e:
                print(f"  Error loading InsuranceQA for pricing: {e}")

        # Snorkel: Deductible and policy limit tasks have pricing signals
        snorkel_path = os.path.join(training_dir, "snorkel_underwriting.json")
        if os.path.exists(snorkel_path):
            try:
                with open(snorkel_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
                for rec in records:
                    task = rec.get("task", "")
                    if task in ["Deductibles", "Policy Limits"]:
                        company_desc = rec.get("company description", "")
                        lob = rec.get("lob", "")
                        revenue = rec.get("annual revenue", 0)
                        text = f"LOB: {lob}. Revenue: ${revenue}. Company: {company_desc[:200]}"
                        # Higher revenue = higher pricing band
                        if revenue and revenue > 50000000:
                            label = "high"
                        elif revenue and revenue > 10000000:
                            label = "medium"
                        else:
                            label = "low"
                        pairs.append({"text": text, "label": self.pricing_label_to_idx[label], "task": "pricing"})
            except Exception as e:
                print(f"  Error loading Snorkel for pricing: {e}")

        print(f"  Pricing pairs: {len(pairs)}")
        return pairs

    def _build_intent_data(self) -> List[dict]:
        """Build intent classification from Bitext dataset."""
        pairs = []
        training_dir = self.config.training_data_dir

        bitext_path = os.path.join(training_dir, "bitext_insurance_intents.json")
        if os.path.exists(bitext_path):
            try:
                with open(bitext_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
                for rec in records:
                    text = rec.get("instruction", "")
                    intent = rec.get("intent", "")
                    if text and intent in self.intent_label_to_idx:
                        pairs.append({
                            "text": text[:512],
                            "label": self.intent_label_to_idx[intent],
                            "task": "intent"
                        })
            except Exception as e:
                print(f"  Error loading Bitext: {e}")

        # InsuranceQA: General Q&A — classify as information-seeking intents
        qa_path = os.path.join(training_dir, "insuranceqa_v2.json")
        if os.path.exists(qa_path):
            try:
                with open(qa_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
                for rec in records[:5000]:  # Limit
                    question = rec.get("input", "")
                    q_lower = question.lower()
                    # Map to closest intent
                    if "claim" in q_lower and "file" in q_lower:
                        intent = "file_claim"
                    elif "claim" in q_lower:
                        intent = "check_claim_status"
                    elif "cancel" in q_lower:
                        intent = "cancel_insurance_policy"
                    elif "coverage" in q_lower:
                        intent = "coverage_details"
                    elif "quote" in q_lower:
                        intent = "get_quote"
                    elif "auto" in q_lower or "car" in q_lower:
                        intent = "information_auto_insurance"
                    elif "health" in q_lower or "medical" in q_lower:
                        intent = "information_health_insurance"
                    elif "home" in q_lower or "house" in q_lower:
                        intent = "information_home_insurance"
                    elif "life" in q_lower:
                        intent = "information_life_insurance"
                    elif "travel" in q_lower:
                        intent = "information_travel_insurance"
                    elif "payment" in q_lower or "pay" in q_lower:
                        intent = "make_payment"
                    elif "renew" in q_lower:
                        intent = "renew_insurance_policy"
                    else:
                        continue
                    if intent in self.intent_label_to_idx:
                        pairs.append({
                            "text": question[:512],
                            "label": self.intent_label_to_idx[intent],
                            "task": "intent"
                        })
            except Exception as e:
                print(f"  Error loading InsuranceQA for intent: {e}")

        print(f"  Intent pairs: {len(pairs)}")
        return pairs

    def _infer_clause_category(self, text: str) -> str:
        """Infer clause category from text content."""
        text_lower = text.lower()
        if "terminat" in text_lower:
            return "termination"
        elif "indemni" in text_lower:
            return "indemnification"
        elif "confiden" in text_lower:
            return "confidentiality"
        elif "warrant" in text_lower:
            return "warranties"
        elif "liabil" in text_lower:
            return "limitation_of_liability"
        elif "insur" in text_lower:
            return "insurance"
        elif "govern" in text_lower and "law" in text_lower:
            return "governing_law"
        elif "arbitrat" in text_lower:
            return "arbitration"
        elif "disclos" in text_lower:
            return "disclosure"
        elif "assign" in text_lower:
            return "assignments"
        else:
            return "general_provisions"


# =============================================================================
# PyTorch Dataset
# =============================================================================

class MultiTaskDataset(Dataset):
    """Dataset for multi-task training."""

    def __init__(self, data: List[dict], tokenizer, max_length: int = 256):
        self.data = data
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        text = item["text"]
        task = item["task"]

        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )

        result = {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "task": task,
        }

        if task == "clause":
            result["labels"] = torch.tensor(item["labels"], dtype=torch.float)
        else:
            result["labels"] = torch.tensor(item["label"], dtype=torch.long)

        return result


# =============================================================================
# Multi-Task Model
# =============================================================================

class InsuranceMultiTaskModel(nn.Module):
    """
    Multi-task model with shared BERT encoder and 4 task-specific heads.

    Architecture:
        [BERT Encoder] → [CLS token] → [Task Head A/B/C/D]

    Heads:
        A: Clause classifier (multi-label, sigmoid, 130+ labels)
        B: Appetite classifier (3 classes, softmax)
        C: Pricing classifier (3 classes, softmax)
        D: Intent classifier (39 classes, softmax)
    """

    def __init__(self, base_model_name: str, num_clause_labels: int, num_intent_labels: int):
        super().__init__()

        self.encoder = AutoModel.from_pretrained(base_model_name)
        hidden_size = self.encoder.config.hidden_size

        # Shared projection (dimensionality reduction for task heads)
        self.shared_proj = nn.Sequential(
            nn.Linear(hidden_size, 512),
            nn.ReLU(),
            nn.Dropout(0.1),
        )

        # Task heads
        self.clause_head = nn.Sequential(
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, num_clause_labels),
        )

        self.appetite_head = nn.Sequential(
            nn.Linear(512, 128),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(128, 3),
        )

        self.pricing_head = nn.Sequential(
            nn.Linear(512, 128),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(128, 3),
        )

        self.intent_head = nn.Sequential(
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, num_intent_labels),
        )

    def forward(self, input_ids, attention_mask, task: str = None):
        """Forward pass. Returns logits for the specified task."""
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        cls_output = outputs.last_hidden_state[:, 0, :]  # [CLS] token
        shared = self.shared_proj(cls_output)

        if task == "clause":
            return self.clause_head(shared)
        elif task == "appetite":
            return self.appetite_head(shared)
        elif task == "pricing":
            return self.pricing_head(shared)
        elif task == "intent":
            return self.intent_head(shared)
        else:
            # Return all heads (for inference)
            return {
                "clause": self.clause_head(shared),
                "appetite": self.appetite_head(shared),
                "pricing": self.pricing_head(shared),
                "intent": self.intent_head(shared),
            }

    def get_embedding(self, input_ids, attention_mask):
        """Get the shared embedding (for semantic search)."""
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        cls_output = outputs.last_hidden_state[:, 0, :]
        return self.shared_proj(cls_output)


# =============================================================================
# Trainer
# =============================================================================

class InsuranceModelTrainer:
    """Trains the multi-task insurance model."""

    def __init__(self, config: TrainerConfig):
        self.config = config
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Using device: {self.device}")

        # Load tokenizer
        print(f"Loading tokenizer: {config.base_model}")
        self.tokenizer = AutoTokenizer.from_pretrained(config.base_model)

        # Build training data
        builder = TrainingDataBuilder(config)
        all_data = builder.build_all()

        # Split train/eval
        self.train_data = {}
        self.eval_data = {}
        for task, pairs in all_data.items():
            random.shuffle(pairs)
            split_idx = int(len(pairs) * (1 - config.eval_split))
            self.train_data[task] = pairs[:split_idx]
            self.eval_data[task] = pairs[split_idx:]

        # Build model
        self.model = InsuranceMultiTaskModel(
            base_model_name=config.base_model,
            num_clause_labels=len(ALL_CLAUSE_LABELS),
            num_intent_labels=len(INTENT_LABELS),
        ).to(self.device)

        # Loss functions
        self.clause_loss_fn = nn.BCEWithLogitsLoss()  # Multi-label
        self.appetite_loss_fn = nn.CrossEntropyLoss()
        self.pricing_loss_fn = nn.CrossEntropyLoss()
        self.intent_loss_fn = nn.CrossEntropyLoss()

        # Task weights
        self.task_weights = {
            "clause": config.clause_weight,
            "appetite": config.appetite_weight,
            "pricing": config.pricing_weight,
            "intent": config.intent_weight,
        }

    def train(self) -> Dict[str, float]:
        """Run training loop with per-task DataLoaders."""
        config = self.config

        # Create per-task DataLoaders (avoids mixed label size issues)
        task_loaders = {}
        total_samples = 0
        for task_name, pairs in self.train_data.items():
            if not pairs:
                continue
            random.shuffle(pairs)
            dataset = MultiTaskDataset(pairs, self.tokenizer, config.max_seq_length)
            task_loaders[task_name] = DataLoader(dataset, batch_size=config.batch_size, shuffle=True)
            total_samples += len(pairs)

        # Optimizer with differential learning rates
        encoder_params = list(self.model.encoder.parameters())
        head_params = (
            list(self.model.shared_proj.parameters()) +
            list(self.model.clause_head.parameters()) +
            list(self.model.appetite_head.parameters()) +
            list(self.model.pricing_head.parameters()) +
            list(self.model.intent_head.parameters())
        )

        optimizer = torch.optim.AdamW([
            {"params": encoder_params, "lr": config.learning_rate},
            {"params": head_params, "lr": config.learning_rate * 5},  # Higher LR for heads
        ], weight_decay=config.weight_decay)

        # Calculate steps
        steps_per_epoch = sum(len(loader) for loader in task_loaders.values())
        total_steps = steps_per_epoch * config.epochs
        print(f"\nStarting training: {total_steps} total steps ({config.epochs} epochs)")
        print(f"  Train samples: {total_samples}")
        print(f"  Batch size: {config.batch_size}")
        print(f"  Steps per epoch: {steps_per_epoch}")
        for task_name, loader in task_loaders.items():
            print(f"    {task_name}: {len(loader)} batches ({len(loader.dataset)} samples)")

        best_eval_loss = float("inf")
        metrics_history = []

        for epoch in range(config.epochs):
            self.model.train()
            epoch_losses = defaultdict(float)
            epoch_counts = defaultdict(int)
            global_step = 0

            # Create iterators for each task
            task_iters = {name: iter(loader) for name, loader in task_loaders.items()}
            task_names = list(task_iters.keys())

            # Round-robin through tasks
            while task_iters:
                for task_name in list(task_iters.keys()):
                    try:
                        batch = next(task_iters[task_name])
                    except StopIteration:
                        del task_iters[task_name]
                        continue

                    input_ids = batch["input_ids"].to(self.device)
                    attention_mask = batch["attention_mask"].to(self.device)
                    labels = batch["labels"].to(self.device)

                    logits = self.model(input_ids, attention_mask, task=task_name)

                    if task_name == "clause":
                        loss = self.clause_loss_fn(logits, labels)
                    elif task_name == "appetite":
                        loss = self.appetite_loss_fn(logits, labels)
                    elif task_name == "pricing":
                        loss = self.pricing_loss_fn(logits, labels)
                    elif task_name == "intent":
                        loss = self.intent_loss_fn(logits, labels)
                    else:
                        continue

                    weighted_loss = loss * self.task_weights.get(task_name, 1.0)

                    optimizer.zero_grad()
                    weighted_loss.backward()
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), config.max_grad_norm)
                    optimizer.step()

                    epoch_losses[task_name] += loss.item()
                    epoch_counts[task_name] += 1
                    global_step += 1

                    if global_step % config.log_every == 0:
                        avg_losses = {t: epoch_losses[t] / max(epoch_counts[t], 1) for t in epoch_losses}
                        loss_str = " | ".join(f"{t}: {l:.4f}" for t, l in avg_losses.items())
                        print(f"  Epoch {epoch+1}/{config.epochs} Step {global_step}/{steps_per_epoch} — {loss_str}")

            # Epoch summary
            avg_losses = {t: epoch_losses[t] / max(epoch_counts[t], 1) for t in epoch_losses}
            loss_str = " | ".join(f"{t}: {l:.4f}" for t, l in avg_losses.items())
            print(f"\nEpoch {epoch+1}/{config.epochs} complete — {loss_str}")

            # Evaluate
            eval_metrics = self.evaluate()
            metrics_history.append(eval_metrics)
            eval_loss = sum(eval_metrics.get(f"{t}_loss", 0) for t in ["clause", "appetite", "pricing", "intent"])

            if eval_loss < best_eval_loss:
                best_eval_loss = eval_loss
                self._save_model("best")
                print(f"  New best model saved (eval loss: {eval_loss:.4f})")

        # Save final model
        self._save_model("final")
        print(f"\nTraining complete. Best eval loss: {best_eval_loss:.4f}")

        return metrics_history[-1] if metrics_history else {}

    def evaluate(self) -> Dict[str, float]:
        """Evaluate on held-out data."""
        self.model.eval()
        metrics = {}

        for task_name, pairs in self.eval_data.items():
            if not pairs:
                continue

            dataset = MultiTaskDataset(pairs, self.tokenizer, self.config.max_seq_length)
            loader = DataLoader(dataset, batch_size=self.config.batch_size)

            total_loss = 0.0
            correct = 0
            total = 0

            with torch.no_grad():
                for batch in loader:
                    input_ids = batch["input_ids"].to(self.device)
                    attention_mask = batch["attention_mask"].to(self.device)
                    labels = batch["labels"].to(self.device)

                    logits = self.model(input_ids, attention_mask, task=task_name)

                    if task_name == "clause":
                        loss = self.clause_loss_fn(logits, labels)
                        preds = (torch.sigmoid(logits) > 0.5).float()
                        correct += (preds == labels).all(dim=1).sum().item()
                    elif task_name == "appetite":
                        loss = self.appetite_loss_fn(logits, labels)
                        preds = logits.argmax(dim=1)
                        correct += (preds == labels).sum().item()
                    elif task_name == "pricing":
                        loss = self.pricing_loss_fn(logits, labels)
                        preds = logits.argmax(dim=1)
                        correct += (preds == labels).sum().item()
                    elif task_name == "intent":
                        loss = self.intent_loss_fn(logits, labels)
                        preds = logits.argmax(dim=1)
                        correct += (preds == labels).sum().item()

                    total_loss += loss.item()
                    total += labels.size(0)

            avg_loss = total_loss / max(len(loader), 1)
            accuracy = correct / max(total, 1)
            metrics[f"{task_name}_loss"] = avg_loss
            metrics[f"{task_name}_accuracy"] = accuracy
            print(f"  Eval {task_name}: loss={avg_loss:.4f}, accuracy={accuracy:.4f}")

        return metrics

    def _save_model(self, suffix: str):
        """Save model checkpoint."""
        output_dir = os.path.join(self.config.output_dir, f"{self.config.model_name}-{suffix}")
        os.makedirs(output_dir, exist_ok=True)

        # Save model state
        torch.save(self.model.state_dict(), os.path.join(output_dir, "model.pt"))

        # Save tokenizer
        self.tokenizer.save_pretrained(output_dir)

        # Save config
        config_data = {
            "base_model": self.config.base_model,
            "num_clause_labels": len(ALL_CLAUSE_LABELS),
            "num_intent_labels": len(INTENT_LABELS),
            "clause_labels": ALL_CLAUSE_LABELS,
            "appetite_labels": APPETITE_LABELS,
            "pricing_labels": PRICING_LABELS,
            "intent_labels": INTENT_LABELS,
            "max_seq_length": self.config.max_seq_length,
            "hidden_size": self.config.hidden_size,
        }
        with open(os.path.join(output_dir, "config.json"), "w") as f:
            json.dump(config_data, f, indent=2)

        print(f"  Model saved to: {output_dir}")


# =============================================================================
# CLI Entry Point
# =============================================================================

def train_model(
    data_dir: str = None,
    output_dir: str = None,
    epochs: int = 15,
    batch_size: int = 32,
):
    """
    Train the InstantRisk Engine model.

    Args:
        data_dir: Path to insurance_data directory
        output_dir: Where to save the trained model
        epochs: Number of training epochs
        batch_size: Training batch size
    """
    if data_dir is None:
        # Default paths
        if os.path.exists("/app/app/data/insurance_data"):
            data_dir = "/app/app/data/insurance_data"
        else:
            data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "insurance_data")

    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "models")

    config = TrainerConfig(
        data_dir=data_dir,
        clause_data_dir=data_dir,
        training_data_dir=os.path.join(data_dir, "training"),
        output_dir=output_dir,
        epochs=epochs,
        batch_size=batch_size,
    )

    trainer = InsuranceModelTrainer(config)
    metrics = trainer.train()

    print("\n=== Final Metrics ===")
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}")

    return metrics


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Train InstantRisk Engine model")
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--output-dir", type=str, default=None)
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    train_model(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
    )
