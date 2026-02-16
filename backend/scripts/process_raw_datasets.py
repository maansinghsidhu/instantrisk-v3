"""
Process raw downloaded training datasets into JSONL format for RAG indexing.

Processes the 5 raw datasets already downloaded:
- jetech_underwriting_blocks.json (184MB)
- bitext_insurance_intents.json (30MB)
- insuranceqa_v2.json (14MB)
- snorkel_underwriting.json (10MB)
- mini_insurance.json (76KB)
"""

import json
import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
RAW_DIR = BASE_DIR / "app" / "data" / "insurance_data" / "training"
OUTPUT_DIR = BASE_DIR / "app" / "data" / "training_data" / "embeddings"


def process_jetech():
    """Process JeTech underwriting blocks (184MB)."""
    input_path = RAW_DIR / "jetech_underwriting_blocks.json"
    output_path = OUTPUT_DIR / "jetech_blocks.jsonl"

    if not input_path.exists():
        logger.warning(f"JeTech file not found: {input_path}")
        return 0

    logger.info(f"Processing JeTech: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle different possible structures
    if isinstance(data, list):
        blocks = data
    elif isinstance(data, dict) and "data" in data:
        blocks = data["data"]
    elif isinstance(data, dict) and "blocks" in data:
        blocks = data["blocks"]
    else:
        logger.warning(f"Unknown JeTech structure: {list(data.keys())[:5]}")
        blocks = []

    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for block in blocks:
            # Extract text from various possible field names
            text = (block.get("Text") or block.get("text") or
                   block.get("block_text") or block.get("content") or "")

            if not text or len(text.strip()) < 20:
                continue

            # Extract metadata
            quality = block.get("Quality") or block.get("quality") or ""
            block_type = block.get("Type") or block.get("type") or block.get("category") or ""

            # Extract underwriting-specific fields
            risk_type = block.get("risk_type") or block.get("line_of_business") or ""
            territory = block.get("territory") or block.get("region") or ""
            pricing = block.get("pricing") or block.get("rate") or ""

            record = {
                "text": text[:2000],
                "category": "underwriting_block",
                "source": "jetech",
                "metadata": {
                    "block_type": str(block_type)[:100],
                    "quality": str(quality)[:50],
                    "risk_type": str(risk_type)[:100],
                    "territory": str(territory)[:100],
                    "pricing": str(pricing)[:200],
                },
            }
            f.write(json.dumps(record) + "\n")
            count += 1

            if count % 5000 == 0:
                logger.info(f"  JeTech progress: {count} blocks...")

    logger.info(f"JeTech: wrote {count} records to {output_path}")
    return count


def process_bitext():
    """Process Bitext insurance intents (30MB, 39K examples)."""
    input_path = RAW_DIR / "bitext_insurance_intents.json"
    output_path = OUTPUT_DIR / "bitext_intents.jsonl"

    if not input_path.exists():
        logger.warning(f"Bitext file not found: {input_path}")
        return 0

    logger.info(f"Processing Bitext: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle different structures
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict) and "data" in data:
        records = data["data"]
    else:
        logger.warning(f"Unknown Bitext structure: {list(data.keys())[:5]}")
        records = []

    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for item in records:
            # Bitext has instruction, response format
            instruction = item.get("instruction") or item.get("query") or item.get("text") or ""
            response = item.get("response") or item.get("answer") or item.get("output") or ""
            intent = item.get("intent") or item.get("category") or ""

            if not response or len(response.strip()) < 10:
                continue

            # Combine instruction + response
            combined = f"{instruction}\n{response}".strip() if instruction else response

            record = {
                "text": combined[:2000],
                "category": "insurance_intent",
                "source": "bitext",
                "metadata": {
                    "intent": str(intent)[:100],
                    "instruction": str(instruction)[:300],
                },
            }
            f.write(json.dumps(record) + "\n")
            count += 1

            if count % 5000 == 0:
                logger.info(f"  Bitext progress: {count} records...")

    logger.info(f"Bitext: wrote {count} records to {output_path}")
    return count


def process_insuranceqa():
    """Process InsuranceQA v2 (14MB, 21K Q&A pairs)."""
    input_path = RAW_DIR / "insuranceqa_v2.json"
    output_path = OUTPUT_DIR / "insurance_qa.jsonl"

    if not input_path.exists():
        logger.warning(f"InsuranceQA file not found: {input_path}")
        return 0

    logger.info(f"Processing InsuranceQA: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        pairs = data
    elif isinstance(data, dict) and "data" in data:
        pairs = data["data"]
    else:
        logger.warning(f"Unknown InsuranceQA structure: {list(data.keys())[:5]}")
        pairs = []

    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for item in pairs:
            question = item.get("question") or item.get("input") or item.get("query") or ""
            answer = item.get("answer") or item.get("output") or item.get("response") or ""

            if not answer or len(answer.strip()) < 10:
                continue

            # Combine Q&A
            combined = f"Q: {question}\nA: {answer}" if question else answer

            record = {
                "text": combined[:2000],
                "category": "insurance_qa",
                "source": "insurance_qa",
                "metadata": {
                    "question": str(question)[:300],
                },
            }
            f.write(json.dumps(record) + "\n")
            count += 1

    logger.info(f"InsuranceQA: wrote {count} records to {output_path}")
    return count


def process_snorkel():
    """Process Snorkel underwriting dataset (10MB)."""
    input_path = RAW_DIR / "snorkel_underwriting.json"
    output_path = OUTPUT_DIR / "snorkel_underwriting.jsonl"

    if not input_path.exists():
        logger.warning(f"Snorkel file not found: {input_path}")
        return 0

    logger.info(f"Processing Snorkel: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        records = data
    elif isinstance(data, dict) and "data" in data:
        records = data["data"]
    else:
        logger.warning(f"Unknown Snorkel structure: {list(data.keys())[:5]}")
        records = []

    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for item in records:
            # Snorkel has multi-turn conversations and underwriting tasks
            text = item.get("text") or item.get("content") or ""

            # Could be conversation format
            if not text and "messages" in item:
                msgs = item["messages"]
                if isinstance(msgs, list):
                    text = "\n".join([m.get("content", "") for m in msgs if m.get("content")])

            if not text or len(text.strip()) < 20:
                continue

            task_type = item.get("task_type") or item.get("category") or ""
            guidelines = item.get("guidelines") or ""

            record = {
                "text": text[:2000],
                "category": "underwriting_task",
                "source": "snorkel",
                "metadata": {
                    "task_type": str(task_type)[:100],
                    "guidelines": str(guidelines)[:300],
                },
            }
            f.write(json.dumps(record) + "\n")
            count += 1

    logger.info(f"Snorkel: wrote {count} records to {output_path}")
    return count


def process_mini_insurance():
    """Process mini insurance classification dataset (76KB)."""
    input_path = RAW_DIR / "mini_insurance.json"
    output_path = OUTPUT_DIR / "mini_insurance.jsonl"

    if not input_path.exists():
        logger.warning(f"Mini insurance file not found: {input_path}")
        return 0

    logger.info(f"Processing mini insurance: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        records = data
    elif isinstance(data, dict) and "data" in data:
        records = data["data"]
    else:
        records = []

    count = 0
    with open(output_path, "w", encoding="utf-8") as f:
        for item in records:
            text = item.get("text") or item.get("content") or ""
            label = item.get("label") or item.get("category") or ""

            if not text or len(text.strip()) < 20:
                continue

            record = {
                "text": text[:2000],
                "category": "insurance_classification",
                "source": "mini_insurance",
                "metadata": {
                    "label": str(label)[:100],
                },
            }
            f.write(json.dumps(record) + "\n")
            count += 1

    logger.info(f"Mini insurance: wrote {count} records to {output_path}")
    return count


def main():
    """Process all raw datasets."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = {}

    logger.info("Processing raw training datasets...")
    logger.info(f"Input dir: {RAW_DIR}")
    logger.info(f"Output dir: {OUTPUT_DIR}")

    results["jetech"] = process_jetech()
    results["bitext"] = process_bitext()
    results["insurance_qa"] = process_insuranceqa()
    results["snorkel"] = process_snorkel()
    results["mini_insurance"] = process_mini_insurance()

    print("\n" + "=" * 60)
    print("RAW DATASET PROCESSING SUMMARY")
    print("=" * 60)
    for name, count in results.items():
        status = "[OK]" if count > 0 else "[FAIL]"
        print(f"  {status} {name}: {count:,} records")
    print(f"\n  Total: {sum(results.values()):,} records")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 60)

    return sum(results.values())


if __name__ == "__main__":
    total = main()
    sys.exit(0 if total > 0 else 1)
