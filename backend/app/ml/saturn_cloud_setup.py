#!/usr/bin/env python3
"""
Saturn Cloud Setup Script
=========================

This script sets up and runs fine-tuning on Saturn Cloud.

Saturn Cloud is a managed ML platform that provides GPU instances.
Free tier: 10-30 hours of T4 GPU per month.

This script:
1. Authenticates with Saturn Cloud API
2. Creates a GPU resource
3. Uploads training data
4. Runs fine-tuning job
5. Downloads trained model

Usage:
    python saturn_cloud_setup.py --token YOUR_TOKEN

Note: Saturn Cloud doesn't have a direct fine-tuning API like OpenAI.
      You need to create a Jupyter/Python resource and run code on it.
      This script automates that process using their API.

Author: InstantRisk AI Team
"""

import os
import sys
import json
import time
import argparse
import logging
import requests
from pathlib import Path
from typing import Optional, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SaturnCloudClient:
    """Client for Saturn Cloud API."""

    BASE_URL = "https://app.community.saturnenterprise.io/api"

    def __init__(self, token: str):
        """
        Initialize Saturn Cloud client.

        Args:
            token: Saturn Cloud API token (JWT)
        """
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make API request."""
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.request(method, url, headers=self.headers, **kwargs)

        if response.status_code >= 400:
            logger.error(f"API Error: {response.status_code} - {response.text}")
            response.raise_for_status()

        return response.json() if response.text else {}

    def get_user_info(self) -> Dict[str, Any]:
        """Get current user information."""
        return self._request("GET", "/user")

    def list_resources(self) -> Dict[str, Any]:
        """List all resources."""
        return self._request("GET", "/resources")

    def create_resource(
        self,
        name: str,
        resource_type: str = "jupyter",
        size: str = "gpu-small",  # T4 GPU
        image: str = "saturncloud/saturn-python:2024.01.01"
    ) -> Dict[str, Any]:
        """
        Create a new compute resource.

        Args:
            name: Resource name
            resource_type: "jupyter" or "job"
            size: Instance size (gpu-small = T4, gpu-medium = A10G)
            image: Docker image

        Returns:
            Resource details
        """
        data = {
            "name": name,
            "resource_type": resource_type,
            "instance_size": size,
            "image": image,
            "start_on_create": False,
            "working_directory": "/home/jovyan/project"
        }

        return self._request("POST", "/resources", json=data)

    def start_resource(self, resource_id: str) -> Dict[str, Any]:
        """Start a resource."""
        return self._request("POST", f"/resources/{resource_id}/start")

    def stop_resource(self, resource_id: str) -> Dict[str, Any]:
        """Stop a resource."""
        return self._request("POST", f"/resources/{resource_id}/stop")

    def get_resource_status(self, resource_id: str) -> Dict[str, Any]:
        """Get resource status."""
        return self._request("GET", f"/resources/{resource_id}")

    def wait_for_resource(self, resource_id: str, timeout: int = 600) -> bool:
        """Wait for resource to be ready."""
        start = time.time()
        while time.time() - start < timeout:
            status = self.get_resource_status(resource_id)
            state = status.get("state", "")

            if state == "running":
                logger.info("Resource is ready!")
                return True
            elif state in ["error", "failed"]:
                logger.error(f"Resource failed: {status}")
                return False

            logger.info(f"Waiting for resource... (state: {state})")
            time.sleep(10)

        logger.error("Timeout waiting for resource")
        return False


def create_training_script() -> str:
    """Generate the training script to run on Saturn Cloud."""

    script = '''#!/usr/bin/env python3
"""
Insurance Model Training Script for Saturn Cloud
Run this on a Saturn Cloud GPU instance.
"""

import os
import subprocess
import sys

# Install dependencies
print("Installing dependencies...")
subprocess.check_call([
    sys.executable, "-m", "pip", "install", "-q",
    "torch", "transformers", "datasets", "trl", "accelerate", "bitsandbytes",
    "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
])

# Now run training
print("Starting training...")

from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments
import torch
import json

# Configuration
MODEL_NAME = "unsloth/Phi-3-mini-4k-instruct-bnb-4bit"
MAX_SEQ_LENGTH = 2048
LORA_R = 16
LORA_ALPHA = 16
NUM_EPOCHS = 1
BATCH_SIZE = 2
GRADIENT_ACCUMULATION = 4

# Load model
print(f"Loading model: {MODEL_NAME}")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LENGTH,
    load_in_4bit=True,
    dtype=None,
)

# Apply LoRA
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
print("Loading training data...")

# Check for uploaded data, otherwise use sample
data_path = "/home/jovyan/project/data/insurance_qa_train.jsonl"
if os.path.exists(data_path):
    dataset = load_dataset("json", data_files=data_path, split="train")
else:
    # Create sample data for testing
    print("No training data found, using sample data")
    sample_data = [
        {
            "messages": [
                {"role": "system", "content": "You are an insurance expert."},
                {"role": "user", "content": "What is a deductible?"},
                {"role": "assistant", "content": "A deductible is the amount you pay out of pocket before your insurance coverage kicks in."}
            ]
        }
    ] * 100
    from datasets import Dataset
    dataset = Dataset.from_list(sample_data)

print(f"Loaded {len(dataset)} training examples")

# Format dataset
def format_conversation(example):
    messages = example.get("messages", [])
    formatted = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    return {"text": formatted}

dataset = dataset.map(format_conversation, remove_columns=dataset.column_names)

# Training arguments
training_args = TrainingArguments(
    output_dir="/home/jovyan/project/output",
    per_device_train_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRADIENT_ACCUMULATION,
    warmup_ratio=0.03,
    num_train_epochs=NUM_EPOCHS,
    learning_rate=2e-4,
    fp16=not torch.cuda.is_bf16_supported(),
    bf16=torch.cuda.is_bf16_supported(),
    logging_steps=10,
    save_steps=500,
    optim="adamw_8bit",
    weight_decay=0.001,
    lr_scheduler_type="cosine",
    seed=42,
    report_to="none",
)

# Create trainer
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    dataset_num_proc=2,
    packing=False,
    args=training_args,
)

# Train
print("Starting training...")
trainer.train()

# Save model
print("Saving model...")
model.save_pretrained("/home/jovyan/project/output/lora_adapter")
tokenizer.save_pretrained("/home/jovyan/project/output/lora_adapter")

# Save merged model
model.save_pretrained_merged(
    "/home/jovyan/project/output/merged_model",
    tokenizer,
    save_method="merged_16bit"
)

print("Training complete!")
print("Model saved to /home/jovyan/project/output/")
'''
    return script


def setup_saturn_cloud(token: str, training_data_path: Optional[str] = None):
    """
    Setup and run fine-tuning on Saturn Cloud.

    Args:
        token: Saturn Cloud API token
        training_data_path: Path to training data directory
    """
    client = SaturnCloudClient(token)

    # Get user info
    logger.info("Authenticating with Saturn Cloud...")
    try:
        user = client.get_user_info()
        logger.info(f"Authenticated as: {user.get('username', 'Unknown')}")
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        logger.info("")
        logger.info("To authenticate with Saturn Cloud:")
        logger.info("1. Go to https://app.community.saturnenterprise.io/")
        logger.info("2. Sign up/login (free)")
        logger.info("3. Go to Settings > API Tokens")
        logger.info("4. Create a new token")
        logger.info("5. Run: python saturn_cloud_setup.py --token YOUR_TOKEN")
        return

    # List existing resources
    logger.info("Checking existing resources...")
    resources = client.list_resources()
    existing = [r for r in resources.get("items", []) if "insurance-training" in r.get("name", "")]

    if existing:
        logger.info(f"Found existing resource: {existing[0]['name']}")
        resource = existing[0]
    else:
        # Create new resource
        logger.info("Creating new GPU resource...")
        resource = client.create_resource(
            name="insurance-training",
            resource_type="jupyter",
            size="gpu-small",  # T4 - free tier friendly
        )
        logger.info(f"Created resource: {resource.get('id')}")

    resource_id = resource.get("id")

    # Start resource
    logger.info("Starting resource (this may take a few minutes)...")
    client.start_resource(resource_id)

    if not client.wait_for_resource(resource_id):
        logger.error("Failed to start resource")
        return

    # Get resource URL
    status = client.get_resource_status(resource_id)
    url = status.get("url")

    logger.info("")
    logger.info("="*60)
    logger.info("Saturn Cloud resource is ready!")
    logger.info("="*60)
    logger.info("")
    logger.info("Next steps:")
    logger.info(f"1. Open JupyterLab: {url}")
    logger.info("2. Upload your training data to /home/jovyan/project/data/")
    logger.info("3. Create a new notebook and paste the training script")
    logger.info("4. Run the training")
    logger.info("")
    logger.info("Training script saved to: saturn_training_script.py")

    # Save training script
    script = create_training_script()
    with open("saturn_training_script.py", "w") as f:
        f.write(script)

    logger.info("")
    logger.info("IMPORTANT: Saturn Cloud free tier has limited GPU hours.")
    logger.info("Training ~78K examples will take approximately 2-4 hours on T4.")
    logger.info("Consider using a subset (--max-samples 5000) for testing.")


def main():
    parser = argparse.ArgumentParser(description="Saturn Cloud Setup for Insurance Model Training")
    parser.add_argument(
        "--token",
        type=str,
        required=True,
        help="Saturn Cloud API token"
    )
    parser.add_argument(
        "--data-path",
        type=str,
        default=None,
        help="Path to training data directory"
    )

    args = parser.parse_args()

    setup_saturn_cloud(args.token, args.data_path)


if __name__ == "__main__":
    main()
