#!/usr/bin/env python3
"""
Insurance AI Model Fine-Tuning Script
=====================================

Fine-tunes open-source LLMs for insurance domain tasks using Unsloth + LoRA.
Optimized for speed and memory efficiency - works on free tier GPUs (T4, A100-free).

Models trained:
1. InsuranceChat - Q&A about insurance policies, claims, underwriting
2. DocumentGen - Generate insurance clauses and policy documents

Supported platforms:
- Saturn Cloud (free tier: 10-30 hrs T4 GPU)
- Google Colab (free T4/A100)
- Local GPU (16GB+ VRAM recommended)
- HuggingFace Spaces (free GPU)

Usage:
    python train_insurance_model.py --model chat --epochs 1
    python train_insurance_model.py --model docgen --epochs 1
    python train_insurance_model.py --model both --epochs 1

Author: InstantRisk AI Team
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check for required packages
def check_dependencies():
    """Check and provide installation instructions for dependencies."""
    missing = []

    try:
        import torch
    except ImportError:
        missing.append("torch")

    try:
        import transformers
    except ImportError:
        missing.append("transformers")

    try:
        import datasets
    except ImportError:
        missing.append("datasets")

    try:
        import unsloth
    except ImportError:
        missing.append("unsloth")

    try:
        import trl
    except ImportError:
        missing.append("trl")

    if missing:
        logger.error(f"Missing dependencies: {missing}")
        logger.info("Install with:")
        logger.info("  pip install torch transformers datasets trl accelerate bitsandbytes")
        logger.info("  pip install 'unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git'")
        logger.info("")
        logger.info("For Colab/Saturn Cloud, run:")
        logger.info('  !pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"')
        return False
    return True


# Configuration
class TrainingConfig:
    """Training configuration with sensible defaults for free-tier GPUs."""

    # Base models (smallest viable for free tier)
    BASE_MODELS = {
        "phi3-mini": "unsloth/Phi-3-mini-4k-instruct-bnb-4bit",  # 3.8B params, fastest
        "phi3.5-mini": "unsloth/Phi-3.5-mini-instruct-bnb-4bit",  # Better quality
        "mistral-7b": "unsloth/mistral-7b-instruct-v0.3-bnb-4bit",  # Best quality
        "llama3.2-3b": "unsloth/Llama-3.2-3B-Instruct-bnb-4bit",  # Good balance
        "qwen2.5-3b": "unsloth/Qwen2.5-3B-Instruct-bnb-4bit",  # Fast, good quality
    }

    # Default: Phi-3-mini for speed on free tier
    DEFAULT_MODEL = "phi3-mini"

    # Paths
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = BASE_DIR / "data" / "training_data"
    OUTPUT_DIR = BASE_DIR / "ml" / "models"

    # Training paths
    CHAT_TRAIN = DATA_DIR / "chat_finetune" / "insurance_qa_train.jsonl"
    CHAT_VAL = DATA_DIR / "chat_finetune" / "insurance_qa_val.jsonl"
    DOCGEN_TRAIN = DATA_DIR / "document_generator" / "clause_generation_train.jsonl"
    POLICY_TRAIN = DATA_DIR / "document_generator" / "policy_generation_train.jsonl"

    # LoRA Configuration (optimized for speed + quality)
    LORA_R = 16  # Rank - lower = faster, higher = better quality
    LORA_ALPHA = 16  # Scaling factor
    LORA_DROPOUT = 0  # 0 = better for LoRA
    TARGET_MODULES = [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ]

    # Training hyperparameters (optimized for free tier)
    MAX_SEQ_LENGTH = 2048  # Sufficient for insurance Q&A
    BATCH_SIZE = 2  # Fits in 16GB VRAM
    GRADIENT_ACCUMULATION = 4  # Effective batch = 8
    LEARNING_RATE = 2e-4
    WARMUP_RATIO = 0.03
    MAX_GRAD_NORM = 0.3
    WEIGHT_DECAY = 0.001

    # Speed optimizations
    USE_4BIT = True
    USE_GRADIENT_CHECKPOINTING = True
    MIXED_PRECISION = "bf16"  # or "fp16" for older GPUs


def load_model_and_tokenizer(model_key: str = "phi3-mini"):
    """Load base model with 4-bit quantization for memory efficiency."""
    from unsloth import FastLanguageModel

    model_name = TrainingConfig.BASE_MODELS.get(model_key, TrainingConfig.BASE_MODELS["phi3-mini"])
    logger.info(f"Loading model: {model_name}")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_name,
        max_seq_length=TrainingConfig.MAX_SEQ_LENGTH,
        load_in_4bit=TrainingConfig.USE_4BIT,
        dtype=None,  # Auto-detect
    )

    # Apply LoRA
    model = FastLanguageModel.get_peft_model(
        model,
        r=TrainingConfig.LORA_R,
        lora_alpha=TrainingConfig.LORA_ALPHA,
        lora_dropout=TrainingConfig.LORA_DROPOUT,
        target_modules=TrainingConfig.TARGET_MODULES,
        bias="none",
        use_gradient_checkpointing="unsloth" if TrainingConfig.USE_GRADIENT_CHECKPOINTING else False,
        random_state=42,
        use_rslora=False,
        loftq_config=None,
    )

    return model, tokenizer


def load_chat_dataset(tokenizer, max_samples: Optional[int] = None):
    """Load and format the insurance Q&A dataset."""
    from datasets import load_dataset
    from unsloth.chat_templates import get_chat_template, standardize_sharegpt

    logger.info(f"Loading chat dataset from {TrainingConfig.CHAT_TRAIN}")

    # Load from JSONL
    dataset = load_dataset(
        "json",
        data_files={
            "train": str(TrainingConfig.CHAT_TRAIN),
            "validation": str(TrainingConfig.CHAT_VAL) if TrainingConfig.CHAT_VAL.exists() else None
        },
        split="train"
    )

    if max_samples:
        dataset = dataset.select(range(min(max_samples, len(dataset))))

    logger.info(f"Loaded {len(dataset)} training examples")

    # Setup chat template
    tokenizer = get_chat_template(
        tokenizer,
        chat_template="phi-3" if "phi" in tokenizer.name_or_path.lower() else "llama-3.1",
    )

    def format_conversation(example):
        """Convert to the expected conversation format."""
        messages = example.get("messages", [])

        # Format for chat template
        formatted = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )
        return {"text": formatted}

    dataset = dataset.map(format_conversation, remove_columns=dataset.column_names)

    return dataset, tokenizer


def load_docgen_dataset(tokenizer, max_samples: Optional[int] = None):
    """Load and format the document generation dataset."""
    from datasets import load_dataset, concatenate_datasets
    from unsloth.chat_templates import get_chat_template

    logger.info(f"Loading document generation datasets")

    datasets_list = []

    # Load clause generation data
    if TrainingConfig.DOCGEN_TRAIN.exists():
        clause_ds = load_dataset("json", data_files=str(TrainingConfig.DOCGEN_TRAIN), split="train")
        datasets_list.append(clause_ds)
        logger.info(f"Loaded {len(clause_ds)} clause examples")

    # Load policy generation data
    if TrainingConfig.POLICY_TRAIN.exists():
        policy_ds = load_dataset("json", data_files=str(TrainingConfig.POLICY_TRAIN), split="train")
        datasets_list.append(policy_ds)
        logger.info(f"Loaded {len(policy_ds)} policy examples")

    if not datasets_list:
        raise ValueError("No document generation data found!")

    # Combine datasets
    dataset = concatenate_datasets(datasets_list)

    if max_samples:
        dataset = dataset.select(range(min(max_samples, len(dataset))))

    # Setup chat template
    tokenizer = get_chat_template(
        tokenizer,
        chat_template="phi-3" if "phi" in tokenizer.name_or_path.lower() else "llama-3.1",
    )

    # System prompt for document generation
    system_prompt = """You are an expert insurance document generator. You create professional insurance clauses, policy documents, and legal text based on the given requirements. Your output should be precise, legally sound, and follow insurance industry standards."""

    def format_docgen(example):
        """Convert prompt/completion to chat format."""
        prompt = example.get("prompt", "")
        completion = example.get("completion", "")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": completion}
        ]

        formatted = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )
        return {"text": formatted}

    # Remove metadata column if present
    cols_to_remove = [c for c in dataset.column_names if c != "text"]
    dataset = dataset.map(format_docgen, remove_columns=cols_to_remove)

    return dataset, tokenizer


def create_trainer(model, tokenizer, dataset, output_dir: Path, num_epochs: int = 1):
    """Create SFTTrainer with optimized settings."""
    from trl import SFTTrainer
    from transformers import TrainingArguments
    from unsloth import is_bfloat16_supported

    # Calculate training steps
    total_samples = len(dataset)
    effective_batch = TrainingConfig.BATCH_SIZE * TrainingConfig.GRADIENT_ACCUMULATION
    steps_per_epoch = total_samples // effective_batch
    max_steps = steps_per_epoch * num_epochs

    logger.info(f"Training config: {total_samples} samples, {steps_per_epoch} steps/epoch, {max_steps} total steps")

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=TrainingConfig.BATCH_SIZE,
        gradient_accumulation_steps=TrainingConfig.GRADIENT_ACCUMULATION,
        warmup_ratio=TrainingConfig.WARMUP_RATIO,
        num_train_epochs=num_epochs,
        learning_rate=TrainingConfig.LEARNING_RATE,
        fp16=not is_bfloat16_supported(),
        bf16=is_bfloat16_supported(),
        logging_steps=10,
        save_steps=500,
        save_total_limit=2,
        optim="adamw_8bit",
        weight_decay=TrainingConfig.WEIGHT_DECAY,
        lr_scheduler_type="cosine",
        seed=42,
        report_to="none",  # Disable wandb/mlflow for free tier
        max_grad_norm=TrainingConfig.MAX_GRAD_NORM,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=TrainingConfig.MAX_SEQ_LENGTH,
        dataset_num_proc=2,
        packing=False,  # Can enable for speed but may hurt quality
        args=training_args,
    )

    return trainer


def train_model(
    model_type: str,
    base_model: str = "phi3-mini",
    num_epochs: int = 1,
    max_samples: Optional[int] = None,
    save_merged: bool = True
) -> Dict[str, Any]:
    """
    Train an insurance model.

    Args:
        model_type: "chat" for InsuranceChat, "docgen" for DocumentGen
        base_model: Key from BASE_MODELS (phi3-mini, mistral-7b, etc.)
        num_epochs: Number of training epochs (1-3 recommended)
        max_samples: Limit training samples (for testing)
        save_merged: Save merged model (vs just LoRA adapter)

    Returns:
        Dict with training metrics and model path
    """
    import torch
    from unsloth import FastLanguageModel

    start_time = datetime.now()

    # Setup output directory
    timestamp = start_time.strftime("%Y%m%d_%H%M%S")
    model_name = f"insurance-{model_type}-{base_model}-{timestamp}"
    output_dir = TrainingConfig.OUTPUT_DIR / model_name
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"="*60)
    logger.info(f"Training Insurance{model_type.title()} Model")
    logger.info(f"Base model: {base_model}")
    logger.info(f"Output: {output_dir}")
    logger.info(f"="*60)

    # Load model
    model, tokenizer = load_model_and_tokenizer(base_model)

    # Load dataset
    if model_type == "chat":
        dataset, tokenizer = load_chat_dataset(tokenizer, max_samples)
    elif model_type == "docgen":
        dataset, tokenizer = load_docgen_dataset(tokenizer, max_samples)
    else:
        raise ValueError(f"Unknown model type: {model_type}")

    # Train
    trainer = create_trainer(model, tokenizer, dataset, output_dir, num_epochs)

    logger.info("Starting training...")
    gpu_stats = torch.cuda.get_device_properties(0)
    logger.info(f"GPU: {gpu_stats.name} ({gpu_stats.total_memory / 1024**3:.1f}GB)")

    train_result = trainer.train()

    # Log results
    training_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"Training completed in {training_time/60:.1f} minutes")
    logger.info(f"Final loss: {train_result.training_loss:.4f}")

    # Save model
    logger.info("Saving model...")

    # Save LoRA adapter
    lora_dir = output_dir / "lora_adapter"
    model.save_pretrained(str(lora_dir))
    tokenizer.save_pretrained(str(lora_dir))

    # Optionally save merged model (larger but easier to use)
    if save_merged:
        merged_dir = output_dir / "merged_model"
        logger.info("Merging and saving full model (this may take a while)...")
        model.save_pretrained_merged(
            str(merged_dir),
            tokenizer,
            save_method="merged_16bit"  # or "merged_4bit" for smaller
        )

    # Save training info
    info = {
        "model_type": model_type,
        "base_model": base_model,
        "base_model_name": TrainingConfig.BASE_MODELS[base_model],
        "num_epochs": num_epochs,
        "training_samples": len(dataset),
        "training_time_seconds": training_time,
        "final_loss": float(train_result.training_loss),
        "lora_config": {
            "r": TrainingConfig.LORA_R,
            "alpha": TrainingConfig.LORA_ALPHA,
            "target_modules": TrainingConfig.TARGET_MODULES
        },
        "timestamp": timestamp,
        "output_dir": str(output_dir)
    }

    with open(output_dir / "training_info.json", "w") as f:
        json.dump(info, f, indent=2)

    logger.info(f"Model saved to: {output_dir}")
    logger.info(f"  - LoRA adapter: {lora_dir}")
    if save_merged:
        logger.info(f"  - Merged model: {merged_dir}")

    return info


def train_both_models(
    base_model: str = "phi3-mini",
    num_epochs: int = 1,
    max_samples: Optional[int] = None
) -> Dict[str, Any]:
    """Train both InsuranceChat and DocumentGen models."""
    results = {}

    # Train chat model first
    logger.info("\n" + "="*60)
    logger.info("PHASE 1: Training InsuranceChat Model")
    logger.info("="*60 + "\n")
    results["chat"] = train_model("chat", base_model, num_epochs, max_samples)

    # Train document generator
    logger.info("\n" + "="*60)
    logger.info("PHASE 2: Training DocumentGen Model")
    logger.info("="*60 + "\n")
    results["docgen"] = train_model("docgen", base_model, num_epochs, max_samples)

    # Summary
    logger.info("\n" + "="*60)
    logger.info("TRAINING COMPLETE")
    logger.info("="*60)
    logger.info(f"InsuranceChat: {results['chat']['output_dir']}")
    logger.info(f"DocumentGen: {results['docgen']['output_dir']}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Train Insurance AI Models")
    parser.add_argument(
        "--model",
        choices=["chat", "docgen", "both"],
        default="both",
        help="Which model to train"
    )
    parser.add_argument(
        "--base-model",
        choices=list(TrainingConfig.BASE_MODELS.keys()),
        default="phi3-mini",
        help="Base model to fine-tune"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=1,
        help="Number of training epochs (1-3 recommended)"
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Limit training samples (for testing)"
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Don't save merged model (only LoRA adapter)"
    )
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Only check dependencies and exit"
    )

    args = parser.parse_args()

    # Check dependencies
    if not check_dependencies():
        if not args.check_deps:
            sys.exit(1)
        return

    if args.check_deps:
        logger.info("All dependencies installed!")
        return

    # Run training
    if args.model == "both":
        train_both_models(args.base_model, args.epochs, args.max_samples)
    else:
        train_model(
            args.model,
            args.base_model,
            args.epochs,
            args.max_samples,
            save_merged=not args.no_merge
        )


if __name__ == "__main__":
    main()
