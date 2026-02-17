"""
SageMaker Multi-Task Training Script for InstantRisk Engine

Trains a fine-tuned insurance-BERT model with 4 task heads:
- Task A: Clause Recommendation (multi-label, 134 labels from LEDGAR + CUAD merged)
- Task B: Risk Appetite (3-class: accept / refer / decline)
- Task C: Pricing Signal (3-class: low / medium / high)
- Task D: Intent Classification (39-class)
- Task E: Guideline Matching (embedding projection - no supervised loss)

Model: llmware/industry-bert-insurance-v0.1 (768-dim)
Training data: 109K+ insurance records from S3
"""

import os
import re
import json
import argparse
import logging
import itertools
from pathlib import Path
from typing import List, Optional

import torch
import torch.nn as nn
import numpy as np
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoTokenizer,
    AutoModel,
    AdamW,
    get_linear_schedule_with_warmup,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Label Taxonomies
# ---------------------------------------------------------------------------

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
    "taxes", "term", "termination", "third_party_rights", "transfer", "warranties",
]

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
    "warranty_duration", "insurance", "covenant_not_to_sue", "third_party_beneficiary",
]

# Sorted, deduplicated merge - 134 labels total
ALL_CLAUSE_LABELS: List[str] = sorted(set(LEDGAR_CATEGORIES + CUAD_TYPES))
NUM_CLAUSE_LABELS = len(ALL_CLAUSE_LABELS)  # 134

APPETITE_LABELS = ["accept", "refer", "decline"]
PRICING_LABELS = ["low", "medium", "high"]

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
    "update_contact_information", "update_coverage", "update_payment_method",
]
NUM_INTENT_LABELS = len(INTENT_LABELS)  # 39

# Build fast look-up maps
_CLAUSE_LABEL_TO_IDX = {label: i for i, label in enumerate(ALL_CLAUSE_LABELS)}
_LEDGAR_IDX_TO_CLAUSE_IDX = {
    li: _CLAUSE_LABEL_TO_IDX[label]
    for li, label in enumerate(LEDGAR_CATEGORIES)
    if label in _CLAUSE_LABEL_TO_IDX
}

# CUAD question-text keyword → clause label index
# Each CUAD_TYPE is matched by looking for its tokens in the question string.
_CUAD_KEYWORD_MAP = {
    ct.replace("_", " "): _CLAUSE_LABEL_TO_IDX[ct]
    for ct in CUAD_TYPES
    if ct in _CLAUSE_LABEL_TO_IDX
}
_CUAD_DIRECT_MAP = {
    ct: _CLAUSE_LABEL_TO_IDX[ct]
    for ct in CUAD_TYPES
    if ct in _CLAUSE_LABEL_TO_IDX
}

_INTENT_LABEL_TO_IDX = {label: i for i, label in enumerate(INTENT_LABELS)}
_APPETITE_LABEL_TO_IDX = {label: i for i, label in enumerate(APPETITE_LABELS)}
_PRICING_LABEL_TO_IDX = {label: i for i, label in enumerate(PRICING_LABELS)}

# ---------------------------------------------------------------------------
# Label-resolution helpers
# ---------------------------------------------------------------------------

def resolve_clause_labels_ledgar(metadata: dict) -> Optional[List[int]]:
    """Return [clause_index] for a LEDGAR record, or None if unresolvable."""
    clause_type = metadata.get("clause_type", "")
    if clause_type:
        normalised = clause_type.strip().lower().replace(" ", "_")
        if normalised in _CLAUSE_LABEL_TO_IDX:
            return [_CLAUSE_LABEL_TO_IDX[normalised]]
    # Fallback: numeric label_index or label into LEDGAR_CATEGORIES
    label_index = metadata.get("label_index") or metadata.get("label")
    if label_index is not None and isinstance(label_index, int):
        mapped = _LEDGAR_IDX_TO_CLAUSE_IDX.get(label_index)
        if mapped is not None:
            return [mapped]
    return None


def resolve_clause_labels_cuad(metadata: dict) -> Optional[List[int]]:
    """Return [clause_index] for a CUAD record, or None if unresolvable."""
    clause_type = metadata.get("clause_type", "")
    if not clause_type:
        return None
    # Try direct match (normalised key)
    normalised = clause_type.strip().lower().replace(" ", "_")
    if normalised in _CUAD_DIRECT_MAP:
        return [_CUAD_DIRECT_MAP[normalised]]
    # Try keyword search in the question text
    question_lower = clause_type.lower()
    for keyword, idx in _CUAD_KEYWORD_MAP.items():
        if keyword in question_lower:
            return [idx]
    return None


def resolve_clause_labels_generic(category: str, text: str) -> Optional[List[int]]:
    """Best-effort label for contract_nli / maud / acord sources."""
    # Try to match category string directly
    normalised = category.strip().lower().replace(" ", "_").replace("-", "_")
    if normalised in _CLAUSE_LABEL_TO_IDX:
        return [_CLAUSE_LABEL_TO_IDX[normalised]]
    # Keyword scan of ALL_CLAUSE_LABELS against category and text fragment
    text_lower = (category + " " + text[:500]).lower()
    for label, idx in _CLAUSE_LABEL_TO_IDX.items():
        tokens = label.replace("-", " ").replace("_", " ")
        if tokens in text_lower:
            return [idx]
    return None


def resolve_appetite_snorkel(metadata: dict) -> Optional[int]:
    """Return appetite class index for a Snorkel 'Appetite Check' record."""
    task = metadata.get("task", "")
    if "appetite" not in task.lower():
        return None
    answer = metadata.get("reference_answer", "").lower()
    if any(w in answer for w in ("decline", "declined", "reject", "ineligible", "not acceptable")):
        return _APPETITE_LABEL_TO_IDX["decline"]
    if any(w in answer for w in ("refer", "referral", "review", "underwriter", "consider")):
        return _APPETITE_LABEL_TO_IDX["refer"]
    if any(w in answer for w in ("accept", "approved", "eligible", "standard", "preferred")):
        return _APPETITE_LABEL_TO_IDX["accept"]
    return None


def resolve_appetite_jetech(text: str) -> int:
    """Heuristic appetite label for JeTech blocks."""
    text_lower = text.lower()
    if any(w in text_lower for w in ("decline", "excluded", "not acceptable", "ineligible", "prohibited")):
        return _APPETITE_LABEL_TO_IDX["decline"]
    if any(w in text_lower for w in ("refer", "further review", "underwriter approval", "consider")):
        return _APPETITE_LABEL_TO_IDX["refer"]
    return _APPETITE_LABEL_TO_IDX["accept"]


def resolve_pricing_heuristic(text: str) -> int:
    """Heuristic pricing label from text content."""
    text_lower = text.lower()
    if any(w in text_lower for w in ("high risk", "surcharge", "excess premium", "elevated", "significant loss")):
        return _PRICING_LABEL_TO_IDX["high"]
    if any(w in text_lower for w in ("standard", "moderate", "average", "typical")):
        return _PRICING_LABEL_TO_IDX["medium"]
    return _PRICING_LABEL_TO_IDX["low"]


def resolve_intent_bitext(metadata: dict) -> Optional[int]:
    """Return intent class index for a Bitext record."""
    intent = metadata.get("intent", "")
    if not intent:
        return None
    normalised = intent.strip().lower().replace(" ", "_")
    return _INTENT_LABEL_TO_IDX.get(normalised)


# ---------------------------------------------------------------------------
# Per-task datasets
# ---------------------------------------------------------------------------

class ClauseDataset(Dataset):
    """Multi-label clause classification: sources ledgar, cuad, contract_nli, maud, acord."""

    def __init__(self, records: list, tokenizer, max_length: int):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.items = []  # (text, label_vec)
        skipped = 0
        for rec in records:
            source = rec.get("source", "")
            meta = rec.get("metadata", {}) or {}
            text = rec.get("text", "")
            category = rec.get("category", "")
            indices = None
            if source in ("ledgar", "ledgar_provision"):
                indices = resolve_clause_labels_ledgar(meta)
            elif source in ("cuad", "cuad_clause"):
                indices = resolve_clause_labels_cuad(meta)
            elif source in ("contract_nli", "maud", "acord", "acord_standard", "acord_jetech"):
                # Use explicit clause_type from metadata first (enhanced labels)
                clause_type = meta.get("clause_type", "")
                if clause_type:
                    normalised = clause_type.strip().lower().replace(" ", "_")
                    if normalised in _CLAUSE_LABEL_TO_IDX:
                        indices = [_CLAUSE_LABEL_TO_IDX[normalised]]
                        # Add secondary clause type for multi-label (MAUD)
                        secondary = meta.get("secondary_clause_type", "")
                        if secondary:
                            sec_norm = secondary.strip().lower().replace(" ", "_")
                            if sec_norm in _CLAUSE_LABEL_TO_IDX:
                                indices.append(_CLAUSE_LABEL_TO_IDX[sec_norm])
                if indices is None:
                    # Fallback: acord clause_id / clause_category / generic
                    clause_id = meta.get("clause_id", "")
                    clause_cat = meta.get("clause_category", "") or meta.get("acord_form_category", "")
                    hint = clause_id or clause_cat or category
                    indices = resolve_clause_labels_generic(hint, text)
            if indices is None:
                skipped += 1
                continue
            label_vec = [0.0] * NUM_CLAUSE_LABELS
            for idx in indices:
                label_vec[idx] = 1.0
            self.items.append((text, label_vec))
        logger.info(
            f"ClauseDataset: {len(self.items)} usable, {skipped} skipped (no label resolved)"
        )

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        text, label_vec = self.items[idx]
        enc = self.tokenizer(
            text, max_length=self.max_length, padding="max_length",
            truncation=True, return_tensors="pt"
        )
        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "labels": torch.tensor(label_vec, dtype=torch.float32),
        }


class AppetiteDataset(Dataset):
    """3-class appetite classification: sources snorkel, jetech."""

    def __init__(self, records: list, tokenizer, max_length: int):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.items = []
        skipped = 0
        for rec in records:
            source = rec.get("source", "")
            meta = rec.get("metadata", {}) or {}
            text = rec.get("text", "")
            label = None
            if source in ("snorkel", "snorkel_underwriting"):
                label = resolve_appetite_snorkel(meta)
            elif source in ("jetech", "acord_jetech"):
                label = resolve_appetite_jetech(text)
            if label is None:
                skipped += 1
                continue
            self.items.append((text, label))
        logger.info(
            f"AppetiteDataset: {len(self.items)} usable, {skipped} skipped"
        )

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        text, label = self.items[idx]
        enc = self.tokenizer(
            text, max_length=self.max_length, padding="max_length",
            truncation=True, return_tensors="pt"
        )
        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "labels": torch.tensor(label, dtype=torch.long),
        }


class PricingDataset(Dataset):
    """3-class pricing signal: heuristic from jetech and insurance_qa sources."""

    def __init__(self, records: list, tokenizer, max_length: int):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.items = []
        for rec in records:
            source = rec.get("source", "")
            text = rec.get("text", "")
            if source not in ("jetech", "insurance_qa", "acord_jetech"):
                continue
            label = resolve_pricing_heuristic(text)
            self.items.append((text, label))
        logger.info(f"PricingDataset: {len(self.items)} usable")

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        text, label = self.items[idx]
        enc = self.tokenizer(
            text, max_length=self.max_length, padding="max_length",
            truncation=True, return_tensors="pt"
        )
        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "labels": torch.tensor(label, dtype=torch.long),
        }


class IntentDataset(Dataset):
    """39-class intent classification: sources bitext, insurance_qa."""

    def __init__(self, records: list, tokenizer, max_length: int):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.items = []
        skipped = 0
        for rec in records:
            source = rec.get("source", "")
            if source not in ("bitext", "insurance_qa"):
                continue
            meta = rec.get("metadata", {}) or {}
            text = rec.get("text", "")
            label = resolve_intent_bitext(meta)
            if label is None:
                skipped += 1
                continue
            self.items.append((text, label))
        logger.info(
            f"IntentDataset: {len(self.items)} usable, {skipped} skipped"
        )

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        text, label = self.items[idx]
        enc = self.tokenizer(
            text, max_length=self.max_length, padding="max_length",
            truncation=True, return_tensors="pt"
        )
        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "labels": torch.tensor(label, dtype=torch.long),
        }


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class MultiTaskInsuranceModel(nn.Module):
    """Multi-task model with shared BERT encoder and task-specific heads."""

    def __init__(self, base_model_name: str = "llmware/industry-bert-insurance-v0.1"):
        super().__init__()

        # Shared encoder
        self.bert = AutoModel.from_pretrained(base_model_name)
        hidden_size = self.bert.config.hidden_size

        # Task A: Clause Recommendation (134 labels, multi-label BCE)
        # NOTE: NO Sigmoid here - use BCEWithLogitsLoss for numerical stability
        self.clause_head = nn.Sequential(
            nn.Linear(hidden_size, 512),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(512, NUM_CLAUSE_LABELS),
        )

        # Task B: Risk Appetite (3-class CrossEntropy, raw logits)
        self.appetite_head = nn.Sequential(
            nn.Linear(hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, 3),
        )

        # Task C: Pricing Signal (3-class CrossEntropy, raw logits)
        self.pricing_head = nn.Sequential(
            nn.Linear(hidden_size, 128),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(128, 3),
        )

        # Task D: Intent Classification (39-class CrossEntropy, raw logits)
        self.intent_head = nn.Sequential(
            nn.Linear(hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, NUM_INTENT_LABELS),
        )

        # Task E: Guideline Matching (embedding projection, no supervised loss)
        self.guideline_head = nn.Sequential(
            nn.Linear(hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(256, 128),
        )

    def forward(self, input_ids, attention_mask, task="all"):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled = outputs.pooler_output

        if task == "all":
            return {
                "clause": self.clause_head(pooled),
                "appetite": self.appetite_head(pooled),
                "pricing": self.pricing_head(pooled),
                "intent": self.intent_head(pooled),
                "guideline": self.guideline_head(pooled),
            }
        elif task == "clause":
            return self.clause_head(pooled)
        elif task == "appetite":
            return self.appetite_head(pooled)
        elif task == "pricing":
            return self.pricing_head(pooled)
        elif task == "intent":
            return self.intent_head(pooled)
        elif task == "guideline":
            return self.guideline_head(pooled)
        else:
            raise ValueError(f"Unknown task: {task}")


# ---------------------------------------------------------------------------
# Cyclic dataloader helper
# ---------------------------------------------------------------------------

def infinite_loader(loader):
    """Yield batches from loader indefinitely."""
    while True:
        for batch in loader:
            yield batch


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def load_jsonl(path: str) -> list:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning(f"Skipping bad JSON at line {line_no}: {exc}")
    logger.info(f"Loaded {len(records)} raw records from {path}")
    return records


def build_datasets(records, tokenizer, max_length):
    clause_ds = ClauseDataset(records, tokenizer, max_length)
    appetite_ds = AppetiteDataset(records, tokenizer, max_length)
    pricing_ds = PricingDataset(records, tokenizer, max_length)
    intent_ds = IntentDataset(records, tokenizer, max_length)
    return clause_ds, appetite_ds, pricing_ds, intent_ds


def log_dataset_stats(clause_ds, appetite_ds, pricing_ds, intent_ds):
    logger.info(
        f"Dataset sizes — clause: {len(clause_ds)}, "
        f"appetite: {len(appetite_ds)}, "
        f"pricing: {len(pricing_ds)}, "
        f"intent: {len(intent_ds)}"
    )
    total = len(clause_ds) + len(appetite_ds) + len(pricing_ds) + len(intent_ds)
    logger.info(f"Total training examples across all tasks: {total}")


def train_epoch(
    model,
    clause_iter, appetite_iter, pricing_iter, intent_iter,
    steps_per_epoch,
    optimizer, scheduler, device,
    loss_weights=None,
):
    """Run one epoch of multi-task training."""
    model.train()

    if loss_weights is None:
        loss_weights = {"clause": 1.0, "appetite": 1.0, "pricing": 0.5, "intent": 1.0}

    bce_loss = nn.BCEWithLogitsLoss()
    ce_loss = nn.CrossEntropyLoss()

    total_loss = 0.0
    task_losses = {"clause": 0.0, "appetite": 0.0, "pricing": 0.0, "intent": 0.0}

    for step in range(steps_per_epoch):
        optimizer.zero_grad()
        combined_loss = torch.tensor(0.0, device=device)

        # --- Clause batch ---
        batch = next(clause_iter)
        if batch is not None and len(batch["input_ids"]) > 0:
            ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)
            logits = model(ids, mask, task="clause")
            loss = bce_loss(logits, labels)
            combined_loss = combined_loss + loss_weights["clause"] * loss
            task_losses["clause"] += loss.item()

        # --- Appetite batch ---
        batch = next(appetite_iter)
        if batch is not None and len(batch["input_ids"]) > 0:
            ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)
            logits = model(ids, mask, task="appetite")
            loss = ce_loss(logits, labels)
            combined_loss = combined_loss + loss_weights["appetite"] * loss
            task_losses["appetite"] += loss.item()

        # --- Pricing batch ---
        batch = next(pricing_iter)
        if batch is not None and len(batch["input_ids"]) > 0:
            ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)
            logits = model(ids, mask, task="pricing")
            loss = ce_loss(logits, labels)
            combined_loss = combined_loss + loss_weights["pricing"] * loss
            task_losses["pricing"] += loss.item()

        # --- Intent batch ---
        batch = next(intent_iter)
        if batch is not None and len(batch["input_ids"]) > 0:
            ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)
            logits = model(ids, mask, task="intent")
            loss = ce_loss(logits, labels)
            combined_loss = combined_loss + loss_weights["intent"] * loss
            task_losses["intent"] += loss.item()

        combined_loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

        total_loss += combined_loss.item()

        if step % 50 == 0:
            logger.info(
                f"  Step {step}/{steps_per_epoch} | "
                f"combined={combined_loss.item():.4f} | "
                f"clause={task_losses['clause'] / (step + 1):.4f} | "
                f"appetite={task_losses['appetite'] / (step + 1):.4f} | "
                f"pricing={task_losses['pricing'] / (step + 1):.4f} | "
                f"intent={task_losses['intent'] / (step + 1):.4f}"
            )

    avg = total_loss / steps_per_epoch
    avg_tasks = {k: v / steps_per_epoch for k, v in task_losses.items()}
    return avg, avg_tasks


def evaluate(model, clause_ds, appetite_ds, pricing_ds, intent_ds, batch_size, device):
    """Quick evaluation - returns per-task metrics."""
    model.eval()
    bce_loss = nn.BCEWithLogitsLoss()
    ce_loss = nn.CrossEntropyLoss()
    results = {}

    with torch.no_grad():
        # Clause
        if len(clause_ds) > 0:
            loader = DataLoader(clause_ds, batch_size=batch_size, shuffle=False)
            total_l, total_tp, total_fp, total_fn = 0.0, 0, 0, 0
            for batch in loader:
                ids = batch["input_ids"].to(device)
                mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)
                logits = model(ids, mask, task="clause")
                total_l += bce_loss(logits, labels).item()
                preds = (torch.sigmoid(logits) > 0.5).float()
                total_tp += (preds * labels).sum().item()
                total_fp += (preds * (1 - labels)).sum().item()
                total_fn += ((1 - preds) * labels).sum().item()
            prec = total_tp / (total_tp + total_fp + 1e-8)
            rec = total_tp / (total_tp + total_fn + 1e-8)
            f1 = 2 * prec * rec / (prec + rec + 1e-8)
            results["clause"] = {
                "loss": total_l / len(loader),
                "precision": prec,
                "recall": rec,
                "f1": f1,
            }

        # Appetite
        if len(appetite_ds) > 0:
            loader = DataLoader(appetite_ds, batch_size=batch_size, shuffle=False)
            total_l, correct, total_n = 0.0, 0, 0
            for batch in loader:
                ids = batch["input_ids"].to(device)
                mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)
                logits = model(ids, mask, task="appetite")
                total_l += ce_loss(logits, labels).item()
                preds = logits.argmax(dim=-1)
                correct += (preds == labels).sum().item()
                total_n += labels.size(0)
            results["appetite"] = {
                "loss": total_l / len(loader),
                "accuracy": correct / total_n,
            }

        # Pricing
        if len(pricing_ds) > 0:
            loader = DataLoader(pricing_ds, batch_size=batch_size, shuffle=False)
            total_l, correct, total_n = 0.0, 0, 0
            for batch in loader:
                ids = batch["input_ids"].to(device)
                mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)
                logits = model(ids, mask, task="pricing")
                total_l += ce_loss(logits, labels).item()
                preds = logits.argmax(dim=-1)
                correct += (preds == labels).sum().item()
                total_n += labels.size(0)
            results["pricing"] = {
                "loss": total_l / len(loader),
                "accuracy": correct / total_n,
            }

        # Intent
        if len(intent_ds) > 0:
            loader = DataLoader(intent_ds, batch_size=batch_size, shuffle=False)
            total_l, correct, total_n = 0.0, 0, 0
            for batch in loader:
                ids = batch["input_ids"].to(device)
                mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)
                logits = model(ids, mask, task="intent")
                total_l += ce_loss(logits, labels).item()
                preds = logits.argmax(dim=-1)
                correct += (preds == labels).sum().item()
                total_n += labels.size(0)
            results["intent"] = {
                "loss": total_l / len(loader),
                "accuracy": correct / total_n,
            }

    return results


def save_model(model, tokenizer, output_dir: str, args):
    """Save model state_dict, tokenizer, and config.json."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # State dict (named model.pt to match insurance_model_service.py expectation)
    torch.save(model.state_dict(), out / "model.pt")
    logger.info(f"Saved model.pt to {out}")

    # Tokenizer
    tokenizer.save_pretrained(str(out))
    logger.info(f"Saved tokenizer to {out}")

    # Config matching insurance_model_service.py format
    config = {
        "base_model": args.model_name,
        "num_clause_labels": NUM_CLAUSE_LABELS,
        "num_appetite_labels": len(APPETITE_LABELS),
        "num_pricing_labels": len(PRICING_LABELS),
        "num_intent_labels": NUM_INTENT_LABELS,
        "clause_labels": ALL_CLAUSE_LABELS,
        "appetite_labels": APPETITE_LABELS,
        "pricing_labels": PRICING_LABELS,
        "intent_labels": INTENT_LABELS,
        "max_length": args.max_length,
    }
    with open(out / "config.json", "w") as f:
        json.dump(config, f, indent=2)
    logger.info(f"Saved config.json to {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(args):
    logger.info("=" * 60)
    logger.info("InstantRisk Engine - SageMaker Multi-Task Training")
    logger.info("=" * 60)
    logger.info(f"Args: {vars(args)}")
    logger.info(f"NUM_CLAUSE_LABELS={NUM_CLAUSE_LABELS}, NUM_INTENT_LABELS={NUM_INTENT_LABELS}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")

    # Tokenizer
    logger.info(f"Loading tokenizer: {args.model_name}")
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)

    # Load raw records
    train_records = load_jsonl(args.train_data)
    val_records = load_jsonl(args.val_data)

    # Build per-task datasets
    logger.info("Building train datasets...")
    t_clause, t_appetite, t_pricing, t_intent = build_datasets(
        train_records, tokenizer, args.max_length
    )
    log_dataset_stats(t_clause, t_appetite, t_pricing, t_intent)

    logger.info("Building val datasets...")
    v_clause, v_appetite, v_pricing, v_intent = build_datasets(
        val_records, tokenizer, args.max_length
    )
    log_dataset_stats(v_clause, v_appetite, v_pricing, v_intent)

    # Sanity-check: ensure we have real labels
    if len(t_clause) == 0 and len(t_appetite) == 0 and len(t_intent) == 0:
        raise RuntimeError(
            "All task datasets are empty after label resolution. "
            "Check that JSONL source/metadata fields match expectations."
        )

    # DataLoaders (infinite iterators for training)
    def make_loader(ds, shuffle=True):
        if len(ds) == 0:
            # Return iterator that yields empty batches so the training loop
            # still runs but produces zero contribution from this task.
            return itertools.repeat(
                {
                    "input_ids": torch.zeros(0, args.max_length, dtype=torch.long),
                    "attention_mask": torch.zeros(0, args.max_length, dtype=torch.long),
                    "labels": torch.zeros(0, dtype=torch.long),
                }
            )
        return infinite_loader(
            DataLoader(ds, batch_size=args.batch_size, shuffle=shuffle, num_workers=0)
        )

    clause_train_iter = make_loader(t_clause)
    appetite_train_iter = make_loader(t_appetite)
    pricing_train_iter = make_loader(t_pricing)
    intent_train_iter = make_loader(t_intent)

    # Steps per epoch: driven by the largest dataset
    max_ds_size = max(len(t_clause), len(t_appetite), len(t_pricing), len(t_intent), 1)
    steps_per_epoch = max(1, max_ds_size // args.batch_size)
    logger.info(f"Steps per epoch: {steps_per_epoch}")

    # Model
    logger.info(f"Loading model: {args.model_name}")
    model = MultiTaskInsuranceModel(base_model_name=args.model_name)
    model.to(device)

    # Optimizer and scheduler
    optimizer = AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    total_steps = steps_per_epoch * args.num_epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=args.warmup_steps,
        num_training_steps=total_steps,
    )

    loss_weights = {
        "clause": 1.0,
        "appetite": 1.0,
        "pricing": 0.5,
        "intent": 1.0,
    }

    # Training loop
    best_clause_f1 = 0.0
    for epoch in range(1, args.num_epochs + 1):
        logger.info(f"\n{'=' * 50}")
        logger.info(f"EPOCH {epoch}/{args.num_epochs}")
        logger.info(f"{'=' * 50}")

        avg_loss, avg_task_losses = train_epoch(
            model,
            clause_train_iter, appetite_train_iter, pricing_train_iter, intent_train_iter,
            steps_per_epoch,
            optimizer, scheduler, device,
            loss_weights=loss_weights,
        )

        logger.info(
            f"Epoch {epoch} train loss — "
            f"combined={avg_loss:.4f} | "
            + " | ".join(f"{k}={v:.4f}" for k, v in avg_task_losses.items())
        )

        # Validation
        logger.info("Running validation...")
        val_results = evaluate(model, v_clause, v_appetite, v_pricing, v_intent, args.batch_size, device)
        for task_name, metrics in val_results.items():
            metric_str = " | ".join(f"{mk}={mv:.4f}" for mk, mv in metrics.items())
            logger.info(f"  Val [{task_name}]: {metric_str}")

        # Save best model (tracked by clause F1, falls back to any available metric)
        clause_f1 = val_results.get("clause", {}).get("f1", 0.0)
        if clause_f1 >= best_clause_f1:
            best_clause_f1 = clause_f1
            save_model(model, tokenizer, args.output_dir, args)
            logger.info(f"  --> New best clause F1: {best_clause_f1:.4f} — model saved")

    logger.info("\n" + "=" * 60)
    logger.info("Training complete.")
    logger.info(f"Best clause F1: {best_clause_f1:.4f}")
    logger.info(f"Model saved to: {args.output_dir}")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="InstantRisk SageMaker multi-task training script"
    )

    # Model
    parser.add_argument(
        "--model_name", type=str, default="llmware/industry-bert-insurance-v0.1",
        help="HuggingFace model name or path"
    )
    parser.add_argument(
        "--max_length", type=int, default=512,
        help="Maximum tokenisation length"
    )

    # Data (SageMaker convention)
    parser.add_argument(
        "--train_data", type=str,
        default="/opt/ml/input/data/training/train.jsonl",
        help="Path to training JSONL file"
    )
    parser.add_argument(
        "--val_data", type=str,
        default="/opt/ml/input/data/training/val.jsonl",
        help="Path to validation JSONL file"
    )

    # Training
    parser.add_argument("--num_epochs", type=int, default=10)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--learning_rate", type=float, default=2e-5)
    parser.add_argument("--warmup_steps", type=int, default=500)
    parser.add_argument("--weight_decay", type=float, default=0.01)

    # Output (SageMaker convention)
    parser.add_argument(
        "--output_dir", type=str, default="/opt/ml/model",
        help="Directory to save final model artefacts"
    )

    args = parser.parse_args()
    main(args)
