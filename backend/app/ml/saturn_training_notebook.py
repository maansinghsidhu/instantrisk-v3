#!/usr/bin/env python3
"""
Insurance AI Model Training for Saturn Cloud
=============================================

This script is designed to run on Saturn Cloud with a GPU instance.
Upload this file along with your training data to the Saturn Cloud workspace.

Training Data Required:
- insurance_qa_train.jsonl (for chat model)
- clause_generation_train.jsonl (for document generator)

Usage on Saturn Cloud:
1. Upload this file to /home/jovyan/workspace/
2. Upload training data to /home/jovyan/workspace/data/
3. Run: python saturn_training_notebook.py --model chat
4. Download trained model from /home/jovyan/workspace/output/

Author: InstantRisk AI Team
"""

import os
import sys
import json
import time
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

# Configuration
WORKSPACE_DIR = Path("/home/jovyan/workspace")
DATA_DIR = WORKSPACE_DIR / "data"
OUTPUT_DIR = WORKSPACE_DIR / "output"

# Training Configuration
CONFIG = {
    "base_model": "unsloth/Phi-3-mini-4k-instruct-bnb-4bit",  # Smallest, fastest
    "max_seq_length": 2048,
    "lora_r": 16,
    "lora_alpha": 16,
    "batch_size": 2,
    "gradient_accumulation": 4,
    "learning_rate": 2e-4,
    "num_epochs": 1,
    "max_samples": None,  # Set to limit training data (e.g., 10000 for testing)
}

def install_dependencies():
    """Install required packages."""
    print("Installing dependencies...")

    packages = [
        "torch",
        "transformers>=4.36.0",
        "datasets",
        "trl",
        "peft",
        "accelerate",
        "bitsandbytes",
        "xformers",
    ]

    for pkg in packages:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", pkg], check=True)

    # Install Unsloth
    print("Installing Unsloth...")
    subprocess.run([
        sys.executable, "-m", "pip", "install", "-q",
        "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
    ], check=True)

    print("Dependencies installed!")


def check_gpu():
    """Check GPU availability."""
    import torch

    if torch.cuda.is_available():
        gpu = torch.cuda.get_device_properties(0)
        print(f"GPU: {gpu.name}")
        print(f"VRAM: {gpu.total_memory / 1e9:.1f} GB")
        return True
    else:
        print("WARNING: No GPU detected! Training will be very slow.")
        return False


def load_model():
    """Load base model with LoRA."""
    from unsloth import FastLanguageModel

    print(f"\nLoading model: {CONFIG['base_model']}")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=CONFIG["base_model"],
        max_seq_length=CONFIG["max_seq_length"],
        load_in_4bit=True,
        dtype=None,
    )

    # Apply LoRA
    model = FastLanguageModel.get_peft_model(
        model,
        r=CONFIG["lora_r"],
        lora_alpha=CONFIG["lora_alpha"],
        lora_dropout=0,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj"
        ],
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    print("Model loaded with LoRA!")
    return model, tokenizer


def load_chat_dataset(tokenizer):
    """Load insurance Q&A dataset."""
    from datasets import load_dataset
    from unsloth.chat_templates import get_chat_template

    # Setup chat template
    tokenizer = get_chat_template(tokenizer, chat_template="phi-3")

    # Find training data
    data_files = [
        DATA_DIR / "insurance_qa_train.jsonl",
        WORKSPACE_DIR / "insurance_qa_train.jsonl",
        Path("insurance_qa_train.jsonl"),
    ]

    data_path = None
    for f in data_files:
        if f.exists():
            data_path = str(f)
            break

    if data_path is None:
        print("ERROR: No training data found!")
        print("Please upload insurance_qa_train.jsonl to:")
        print(f"  {DATA_DIR}/")
        sys.exit(1)

    print(f"Loading data from: {data_path}")
    dataset = load_dataset("json", data_files=data_path, split="train")

    # Limit samples if configured
    if CONFIG["max_samples"]:
        dataset = dataset.select(range(min(CONFIG["max_samples"], len(dataset))))

    print(f"Loaded {len(dataset)} training examples")

    # Format for training
    def format_conversation(example):
        messages = example.get("messages", [])
        formatted = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )
        return {"text": formatted}

    dataset = dataset.map(format_conversation, remove_columns=dataset.column_names)

    return dataset, tokenizer


def load_docgen_dataset(tokenizer):
    """Load document generation dataset."""
    from datasets import load_dataset, concatenate_datasets
    from unsloth.chat_templates import get_chat_template

    tokenizer = get_chat_template(tokenizer, chat_template="phi-3")

    datasets_list = []

    # Try to find clause generation data
    clause_files = [
        DATA_DIR / "clause_generation_train.jsonl",
        WORKSPACE_DIR / "clause_generation_train.jsonl",
    ]

    for f in clause_files:
        if f.exists():
            ds = load_dataset("json", data_files=str(f), split="train")
            datasets_list.append(ds)
            print(f"Loaded {len(ds)} clause examples from {f}")
            break

    # Try to find policy generation data
    policy_files = [
        DATA_DIR / "policy_generation_train.jsonl",
        WORKSPACE_DIR / "policy_generation_train.jsonl",
    ]

    for f in policy_files:
        if f.exists():
            ds = load_dataset("json", data_files=str(f), split="train")
            datasets_list.append(ds)
            print(f"Loaded {len(ds)} policy examples from {f}")
            break

    if not datasets_list:
        print("ERROR: No document generation data found!")
        print("Please upload clause_generation_train.jsonl to:")
        print(f"  {DATA_DIR}/")
        sys.exit(1)

    dataset = concatenate_datasets(datasets_list)

    if CONFIG["max_samples"]:
        dataset = dataset.select(range(min(CONFIG["max_samples"], len(dataset))))

    print(f"Total: {len(dataset)} examples")

    # System prompt for document generation
    system_prompt = """You are an expert insurance document generator. You create professional insurance clauses, policy documents, and legal text based on the given requirements. Your output should be precise, legally sound, and follow insurance industry standards."""

    def format_docgen(example):
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

    cols_to_remove = [c for c in dataset.column_names if c != "text"]
    dataset = dataset.map(format_docgen, remove_columns=cols_to_remove)

    return dataset, tokenizer


def train(model, tokenizer, dataset, model_type):
    """Run training."""
    from trl import SFTTrainer
    from transformers import TrainingArguments
    from unsloth import is_bfloat16_supported

    output_dir = OUTPUT_DIR / f"insurance-{model_type}-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nOutput directory: {output_dir}")
    print(f"Training samples: {len(dataset)}")
    print(f"Epochs: {CONFIG['num_epochs']}")
    print(f"Batch size: {CONFIG['batch_size']} x {CONFIG['gradient_accumulation']} = {CONFIG['batch_size'] * CONFIG['gradient_accumulation']}")

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=CONFIG["max_seq_length"],
        dataset_num_proc=2,
        packing=False,
        args=TrainingArguments(
            output_dir=str(output_dir),
            per_device_train_batch_size=CONFIG["batch_size"],
            gradient_accumulation_steps=CONFIG["gradient_accumulation"],
            warmup_ratio=0.03,
            num_train_epochs=CONFIG["num_epochs"],
            learning_rate=CONFIG["learning_rate"],
            fp16=not is_bfloat16_supported(),
            bf16=is_bfloat16_supported(),
            logging_steps=10,
            save_strategy="epoch",
            optim="adamw_8bit",
            weight_decay=0.001,
            lr_scheduler_type="cosine",
            seed=42,
            report_to="none",
        ),
    )

    print("\n" + "="*60)
    print("STARTING TRAINING")
    print("="*60)

    start_time = time.time()
    trainer_stats = trainer.train()
    training_time = time.time() - start_time

    print(f"\nTraining completed in {training_time/60:.1f} minutes")
    print(f"Final loss: {trainer_stats.training_loss:.4f}")

    return output_dir, trainer_stats


def save_model(model, tokenizer, output_dir, model_type, training_stats):
    """Save trained model."""
    print("\nSaving model...")

    # Save LoRA adapter
    lora_dir = output_dir / "lora_adapter"
    model.save_pretrained(str(lora_dir))
    tokenizer.save_pretrained(str(lora_dir))
    print(f"LoRA adapter saved to: {lora_dir}")

    # Save merged model (optional - takes more space but easier to use)
    try:
        merged_dir = output_dir / "merged_model"
        print("Saving merged model (this may take a few minutes)...")
        model.save_pretrained_merged(
            str(merged_dir),
            tokenizer,
            save_method="merged_16bit"
        )
        print(f"Merged model saved to: {merged_dir}")
    except Exception as e:
        print(f"Warning: Could not save merged model: {e}")

    # Save training info
    info = {
        "model_type": model_type,
        "base_model": CONFIG["base_model"],
        "training_samples": training_stats.global_step * CONFIG["batch_size"] * CONFIG["gradient_accumulation"],
        "final_loss": float(training_stats.training_loss),
        "config": CONFIG,
        "timestamp": datetime.now().isoformat()
    }

    with open(output_dir / "training_info.json", "w") as f:
        json.dump(info, f, indent=2)

    print(f"\nTraining info saved to: {output_dir / 'training_info.json'}")

    return output_dir


def test_model(model, tokenizer, model_type):
    """Test the trained model."""
    from unsloth import FastLanguageModel

    print("\n" + "="*60)
    print("TESTING MODEL")
    print("="*60)

    FastLanguageModel.for_inference(model)

    if model_type == "chat":
        questions = [
            "What is the difference between actual cash value and replacement cost?",
            "What does a standard homeowners policy cover?",
        ]
        system = "You are an expert insurance professional."
    else:
        questions = [
            "Generate an insurance clause for: Cyber Liability Coverage (Category: Technology)",
            "Generate an insurance clause for: War Risks (Category: Marine)",
        ]
        system = "You are an expert insurance document generator."

    for q in questions:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": q}
        ]

        inputs = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt"
        ).to("cuda")

        outputs = model.generate(
            input_ids=inputs,
            max_new_tokens=256,
            temperature=0.7,
            do_sample=True,
        )

        response = tokenizer.decode(outputs[0][inputs.shape[1]:], skip_special_tokens=True)

        print(f"\nQ: {q[:80]}...")
        print(f"A: {response[:300]}...")
        print("-" * 40)


def main():
    parser = argparse.ArgumentParser(description="Train Insurance AI Models on Saturn Cloud")
    parser.add_argument("--model", choices=["chat", "docgen", "both"], default="chat",
                       help="Which model to train")
    parser.add_argument("--max-samples", type=int, default=None,
                       help="Limit training samples (for testing)")
    parser.add_argument("--epochs", type=int, default=1,
                       help="Number of training epochs")
    parser.add_argument("--skip-install", action="store_true",
                       help="Skip dependency installation")
    parser.add_argument("--test-only", action="store_true",
                       help="Only test, don't train")

    args = parser.parse_args()

    # Update config
    if args.max_samples:
        CONFIG["max_samples"] = args.max_samples
    CONFIG["num_epochs"] = args.epochs

    print("="*60)
    print("Insurance AI Model Training")
    print("="*60)
    print(f"Model: {args.model}")
    print(f"Base model: {CONFIG['base_model']}")
    print(f"Epochs: {CONFIG['num_epochs']}")
    if CONFIG["max_samples"]:
        print(f"Max samples: {CONFIG['max_samples']}")
    print("="*60)

    # Install dependencies
    if not args.skip_install:
        install_dependencies()

    # Check GPU
    check_gpu()

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Train models
    models_to_train = ["chat", "docgen"] if args.model == "both" else [args.model]

    for model_type in models_to_train:
        print(f"\n{'='*60}")
        print(f"Training {model_type.upper()} model")
        print(f"{'='*60}")

        # Load model
        model, tokenizer = load_model()

        # Load dataset
        if model_type == "chat":
            dataset, tokenizer = load_chat_dataset(tokenizer)
        else:
            dataset, tokenizer = load_docgen_dataset(tokenizer)

        if args.test_only:
            test_model(model, tokenizer, model_type)
            continue

        # Train
        output_dir, stats = train(model, tokenizer, dataset, model_type)

        # Save
        save_model(model, tokenizer, output_dir, model_type, stats)

        # Test
        test_model(model, tokenizer, model_type)

        print(f"\n{'='*60}")
        print(f"{model_type.upper()} MODEL COMPLETE")
        print(f"Output: {output_dir}")
        print(f"{'='*60}")

    print("\n" + "="*60)
    print("ALL TRAINING COMPLETE!")
    print("="*60)
    print(f"\nDownload your models from: {OUTPUT_DIR}")
    print("\nTo use the model locally:")
    print("  1. Download the lora_adapter or merged_model folder")
    print("  2. Use inference.py to run the model")


if __name__ == "__main__":
    main()
