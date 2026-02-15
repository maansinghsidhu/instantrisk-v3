#!/usr/bin/env python3
"""
Insurance AI Fine-Tuning Script for Saturn Cloud
================================================
Optimized for T4 GPU (free tier)

This script fine-tunes Phi-3-mini for insurance domain tasks:
1. InsuranceChat - Q&A model for insurance professionals
2. DocumentGen - Clause and policy generation

Run on Saturn Cloud:
1. Upload training data to /home/jovyan/workspace/data/
2. Run: python saturn_training.py --model chat
3. Or: python saturn_training.py --model docgen

Author: InstantRisk AI Team
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# Install dependencies if not present
def install_dependencies():
    """Install required packages."""
    packages = [
        "torch",
        "transformers>=4.36.0",
        "datasets>=2.14.0",
        "trl>=0.7.0",
        "peft>=0.6.0",
        "accelerate>=0.24.0",
        "bitsandbytes>=0.41.0",
    ]

    print("Installing dependencies...")
    for pkg in packages:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", pkg], check=True)

    # Install unsloth separately (special install)
    print("Installing Unsloth...")
    subprocess.run([
        sys.executable, "-m", "pip", "install", "-q",
        "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
    ], check=True)

    print("All dependencies installed!")

# Configuration
CONFIG = {
    "chat": {
        "name": "InsuranceChat",
        "base_model": "unsloth/Phi-3-mini-4k-instruct-bnb-4bit",
        "data_file": "insurance_qa_train.jsonl",
        "output_dir": "models/insurance-chat",
        "max_samples": 10000,  # ~30 min on T4 GPU
    },
    "docgen": {
        "name": "DocumentGen",
        "base_model": "unsloth/Phi-3-mini-4k-instruct-bnb-4bit",
        "data_file": "clause_generation_train.jsonl",
        "output_dir": "models/insurance-docgen",
        "max_samples": 8000,  # ~20 min on T4 GPU
    }
}

# Training hyperparameters (optimized for T4)
LORA_R = 16
LORA_ALPHA = 16
MAX_SEQ_LENGTH = 2048
BATCH_SIZE = 2
GRADIENT_ACCUMULATION = 4
NUM_EPOCHS = 1
LEARNING_RATE = 2e-4


def train_model(model_type: str, data_dir: str = "/home/jovyan/workspace/data"):
    """Train the specified model."""

    # Import after installing
    from unsloth import FastLanguageModel
    from unsloth.chat_templates import get_chat_template
    from datasets import load_dataset, Dataset
    from trl import SFTTrainer
    from transformers import TrainingArguments
    import torch

    config = CONFIG[model_type]
    print(f"\n{'='*60}")
    print(f"Training {config['name']}")
    print(f"{'='*60}")

    # Check GPU
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA not available! Make sure you're running on a GPU instance.")

    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    # Load model
    print(f"\nLoading model: {config['base_model']}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=config['base_model'],
        max_seq_length=MAX_SEQ_LENGTH,
        load_in_4bit=True,
        dtype=None,
    )

    # Apply LoRA
    print("Applying LoRA...")
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=0,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    # Setup chat template
    tokenizer = get_chat_template(tokenizer, chat_template="phi-3")

    # Load training data
    data_path = os.path.join(data_dir, config['data_file'])
    print(f"\nLoading data from: {data_path}")

    if not os.path.exists(data_path):
        # Create sample data for testing
        print("WARNING: Training data not found! Creating sample data...")
        sample_data = create_sample_data(model_type)
        dataset = Dataset.from_list(sample_data)
    else:
        dataset = load_dataset("json", data_files=data_path, split="train")  # nosec B615 - local files only

    # Limit samples for faster training
    if len(dataset) > config['max_samples']:
        print(f"Limiting to {config['max_samples']} samples (from {len(dataset)})")
        dataset = dataset.shuffle(seed=42).select(range(config['max_samples']))

    print(f"Training samples: {len(dataset)}")

    # Format dataset
    def format_example(example):
        if model_type == "chat":
            messages = example.get("messages", [])
        else:
            # DocGen format
            messages = [
                {"role": "system", "content": "You are an expert insurance document generator specializing in Lloyd's of London market clauses and policy wordings."},
                {"role": "user", "content": example.get("prompt", "")},
                {"role": "assistant", "content": example.get("completion", "")}
            ]

        formatted = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )
        return {"text": formatted}

    print("Formatting dataset...")
    dataset = dataset.map(format_example, remove_columns=dataset.column_names)

    # Training
    output_dir = os.path.join("/home/jovyan/workspace", config['output_dir'])
    os.makedirs(output_dir, exist_ok=True)

    print(f"\nOutput directory: {output_dir}")
    print(f"Starting training...")
    print(f"Estimated batches: {len(dataset) // (BATCH_SIZE * GRADIENT_ACCUMULATION)}")

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        dataset_num_proc=2,
        packing=False,
        args=TrainingArguments(
            output_dir=output_dir,
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRADIENT_ACCUMULATION,
            warmup_ratio=0.03,
            num_train_epochs=NUM_EPOCHS,
            learning_rate=LEARNING_RATE,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=10,
            save_strategy="epoch",
            optim="adamw_8bit",
            weight_decay=0.001,
            lr_scheduler_type="cosine",
            seed=42,
            report_to="none",
        ),
    )

    stats = trainer.train()

    print(f"\n{'='*60}")
    print(f"Training Complete!")
    print(f"Final Loss: {stats.training_loss:.4f}")
    print(f"{'='*60}")

    # Save LoRA adapter
    lora_path = os.path.join(output_dir, "lora_adapter")
    print(f"\nSaving LoRA adapter to: {lora_path}")
    model.save_pretrained(lora_path)
    tokenizer.save_pretrained(lora_path)

    # Save merged model
    merged_path = os.path.join(output_dir, "merged_model")
    print(f"Saving merged model to: {merged_path}")
    model.save_pretrained_merged(merged_path, tokenizer, save_method="merged_16bit")

    # Save training info
    info = {
        "model_type": model_type,
        "model_name": config['name'],
        "base_model": config['base_model'],
        "training_samples": len(dataset),
        "num_epochs": NUM_EPOCHS,
        "lora_r": LORA_R,
        "lora_alpha": LORA_ALPHA,
        "max_seq_length": MAX_SEQ_LENGTH,
        "final_loss": float(stats.training_loss),
        "timestamp": datetime.now().isoformat(),
    }

    info_path = os.path.join(output_dir, "training_info.json")
    with open(info_path, "w") as f:
        json.dump(info, f, indent=2)

    print(f"\nModel saved successfully!")
    print(f"- LoRA adapter: {lora_path}")
    print(f"- Merged model: {merged_path}")
    print(f"- Training info: {info_path}")

    return output_dir


def create_sample_data(model_type: str):
    """Create sample training data for testing."""
    if model_type == "chat":
        return [
            {
                "messages": [
                    {"role": "system", "content": "You are an expert insurance professional."},
                    {"role": "user", "content": "What is a deductible?"},
                    {"role": "assistant", "content": "A deductible is the amount you pay out of pocket before your insurance coverage kicks in. For example, with a $500 deductible on your auto policy, you'd pay the first $500 of a covered claim, and your insurer would pay the rest up to your policy limits."}
                ]
            },
            {
                "messages": [
                    {"role": "system", "content": "You are an expert insurance professional."},
                    {"role": "user", "content": "Explain the difference between term and whole life insurance."},
                    {"role": "assistant", "content": "Term life insurance provides coverage for a specific period (term), typically 10-30 years. It pays a death benefit only if you die during the term. Whole life insurance provides permanent coverage for your entire life and includes a cash value component that grows over time. Term is cheaper but temporary; whole life is more expensive but builds equity."}
                ]
            },
        ] * 100  # Repeat for minimal training
    else:
        return [
            {
                "prompt": "Generate an insurance clause for: War Risks Exclusion (Category: Marine Hull)",
                "completion": "This insurance does not cover loss, damage, liability or expense arising from: (a) war, civil war, revolution, rebellion, insurrection, or civil strife arising therefrom, or any hostile act by or against a belligerent power; (b) capture, seizure, arrest, restraint or detainment, and the consequences thereof or any attempt thereat; (c) derelict mines, torpedoes, bombs or other derelict weapons of war."
            },
            {
                "prompt": "Generate an insurance clause for: Cyber Exclusion (Category: Commercial Combined)",
                "completion": "This policy does not cover any loss, damage, liability, claim, cost or expense of whatsoever nature directly or indirectly caused by, contributed to by, resulting from, arising out of or in connection with any Cyber Act or Cyber Incident including, but not limited to, any action taken in controlling, preventing, suppressing or remediating any Cyber Act or Cyber Incident."
            },
        ] * 100


def test_model(model_path: str, model_type: str):
    """Test the trained model with sample prompts."""
    from unsloth import FastLanguageModel
    import torch

    print(f"\n{'='*60}")
    print(f"Testing Model")
    print(f"{'='*60}")

    merged_path = os.path.join(model_path, "merged_model")

    print(f"Loading model from: {merged_path}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=merged_path,
        max_seq_length=MAX_SEQ_LENGTH,
        load_in_4bit=True,
    )

    FastLanguageModel.for_inference(model)

    # Test prompts
    if model_type == "chat":
        test_prompts = [
            "What is the difference between actual cash value and replacement cost?",
            "Explain reinsurance and why companies use it.",
            "What does a standard homeowners policy cover?",
        ]
        system = "You are an expert insurance professional with deep knowledge of Lloyd's of London market practices."
    else:
        test_prompts = [
            "Generate an insurance clause for: Cyber Liability Coverage (Category: Professional Liability)",
            "Generate an insurance clause for: Pollution Exclusion (Category: General Liability)",
        ]
        system = "You are an expert insurance document generator."

    for prompt in test_prompts:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
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

        print(f"\nQ: {prompt}")
        print(f"A: {response[:500]}...")
        print("-" * 50)


def main():
    parser = argparse.ArgumentParser(description="Insurance AI Fine-Tuning for Saturn Cloud")
    parser.add_argument(
        "--model", "-m",
        type=str,
        choices=["chat", "docgen", "both"],
        default="chat",
        help="Model to train: chat, docgen, or both"
    )
    parser.add_argument(
        "--data-dir", "-d",
        type=str,
        default="/home/jovyan/workspace/data",
        help="Directory containing training data"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test model after training"
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install dependencies before training"
    )

    args = parser.parse_args()

    if args.install:
        install_dependencies()

    models_to_train = ["chat", "docgen"] if args.model == "both" else [args.model]

    for model_type in models_to_train:
        output_dir = train_model(model_type, args.data_dir)

        if args.test:
            test_model(output_dir, model_type)

    print(f"\n{'='*60}")
    print("All training complete!")
    print(f"{'='*60}")
    print("\nNext steps:")
    print("1. Download models from /home/jovyan/workspace/models/")
    print("2. Upload to HuggingFace Hub or your server")
    print("3. Use with inference.py for production")


if __name__ == "__main__":
    main()
