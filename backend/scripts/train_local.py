"""
Local Training Script for InstantRisk Engine

Simpler alternative to SageMaker - trains the model locally (requires GPU).
Can also run on Google Colab for free GPU access.

Usage:
    # Local with GPU
    python scripts/train_local.py --epochs 5 --batch-size 16

    # Test run (1 epoch, small batch)
    python scripts/train_local.py --epochs 1 --batch-size 8 --max-samples 1000
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the training script
from scripts.train_sagemaker import (
    logger,
    load_jsonl,
    build_datasets,
    log_dataset_stats,
    MultiTaskInsuranceModel,
    train_epoch,
    evaluate,
    save_model,
    infinite_loader,
)

import torch
from torch.utils.data import DataLoader
from transformers import AutoTokenizer, AdamW, get_linear_schedule_with_warmup

BASE_DIR = Path(__file__).parent.parent
EMBEDDINGS_DIR = BASE_DIR / "app/data/training_data/embeddings"
OUTPUT_DIR = BASE_DIR / "app/data/models/instantrisk-engine-v1-final"


def prepare_combined_jsonl():
    """Combine all JSONL files into train.jsonl and val.jsonl."""
    logger.info("Preparing combined training data...")

    jsonl_files = [
        "bitext_intents.jsonl",
        "contract_nli.jsonl",
        "cuad.jsonl",
        "insurance_qa.jsonl",
        "jetech_blocks.jsonl",
        "ledgar.jsonl",
        "maud.jsonl",
        "mini_insurance.jsonl",
        "snorkel_underwriting.jsonl",
    ]

    all_records = []
    for jsonl_file in jsonl_files:
        path = EMBEDDINGS_DIR / jsonl_file
        if not path.exists():
            logger.warning(f"  ⚠ {jsonl_file} not found, skipping")
            continue

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    all_records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    logger.info(f"Total records: {len(all_records):,}")

    # Shuffle and split
    import random
    random.seed(42)
    random.shuffle(all_records)

    split_idx = int(len(all_records) * 0.9)
    train_records = all_records[:split_idx]
    val_records = all_records[split_idx:]

    logger.info(f"Train: {len(train_records):,}, Val: {len(val_records):,}")

    return train_records, val_records


def main(args):
    logger.info("=" * 60)
    logger.info("InstantRisk Engine - Local Training")
    logger.info("=" * 60)

    # Check for GPU
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Device: {device}")

    if device.type == "cpu":
        logger.warning("⚠️  No GPU detected! Training will be VERY slow.")
        logger.warning("   Consider using Google Colab for free GPU access.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != "y":
            sys.exit(0)

    # Prepare data
    logger.info("\nLoading data...")
    train_records, val_records = prepare_combined_jsonl()

    # Limit samples if requested (for testing)
    if args.max_samples:
        logger.info(f"Limiting to {args.max_samples} samples per split")
        train_records = train_records[:args.max_samples]
        val_records = val_records[:min(args.max_samples // 10, len(val_records))]

    # Tokenizer
    model_name = "llmware/industry-bert-insurance-v0.1"
    logger.info(f"\nLoading tokenizer: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    # Build datasets
    logger.info("\nBuilding train datasets...")
    t_clause, t_appetite, t_pricing, t_intent = build_datasets(
        train_records, tokenizer, args.max_length
    )
    log_dataset_stats(t_clause, t_appetite, t_pricing, t_intent)

    logger.info("\nBuilding val datasets...")
    v_clause, v_appetite, v_pricing, v_intent = build_datasets(
        val_records, tokenizer, args.max_length
    )
    log_dataset_stats(v_clause, v_appetite, v_pricing, v_intent)

    # Dataloaders
    import itertools

    def make_loader(ds, shuffle=True):
        if len(ds) == 0:
            return itertools.repeat({
                "input_ids": torch.zeros(0, args.max_length, dtype=torch.long),
                "attention_mask": torch.zeros(0, args.max_length, dtype=torch.long),
                "labels": torch.zeros(0, dtype=torch.long),
            })
        return infinite_loader(
            DataLoader(ds, batch_size=args.batch_size, shuffle=shuffle, num_workers=0)
        )

    clause_train_iter = make_loader(t_clause)
    appetite_train_iter = make_loader(t_appetite)
    pricing_train_iter = make_loader(t_pricing)
    intent_train_iter = make_loader(t_intent)

    # Steps per epoch
    max_ds_size = max(len(t_clause), len(t_appetite), len(t_pricing), len(t_intent), 1)
    steps_per_epoch = max(1, max_ds_size // args.batch_size)
    logger.info(f"\nSteps per epoch: {steps_per_epoch}")

    # Model
    logger.info(f"\nLoading model: {model_name}")
    model = MultiTaskInsuranceModel(base_model_name=model_name)
    model.to(device)

    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"Total parameters: {total_params:,}")
    logger.info(f"Trainable parameters: {trainable_params:,}")

    # Optimizer
    optimizer = AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    total_steps = steps_per_epoch * args.epochs
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
    for epoch in range(1, args.epochs + 1):
        logger.info(f"\n{'=' * 50}")
        logger.info(f"EPOCH {epoch}/{args.epochs}")
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

        # Save best model
        clause_f1 = val_results.get("clause", {}).get("f1", 0.0)
        if clause_f1 >= best_clause_f1:
            best_clause_f1 = clause_f1
            save_model(model, tokenizer, str(OUTPUT_DIR), args)
            logger.info(f"  --> New best clause F1: {best_clause_f1:.4f} — model saved")

    logger.info("\n" + "=" * 60)
    logger.info("✅ Training complete!")
    logger.info(f"Best clause F1: {best_clause_f1:.4f}")
    logger.info(f"Model saved to: {OUTPUT_DIR}")
    logger.info("=" * 60)

    logger.info("\nNext steps:")
    logger.info("1. Test the model:")
    logger.info("   python -m app.services.insurance_model_service --test")
    logger.info("2. Deploy backend with new model")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train InstantRisk Engine locally")

    # Model
    parser.add_argument("--model-name", type=str, default="llmware/industry-bert-insurance-v0.1")
    parser.add_argument("--max-length", type=int, default=512)

    # Training
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--warmup-steps", type=int, default=500)
    parser.add_argument("--weight-decay", type=float, default=0.01)

    # Testing
    parser.add_argument("--max-samples", type=int, help="Limit samples for testing")

    args = parser.parse_args()
    main(args)
