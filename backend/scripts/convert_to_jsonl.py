"""
Convert JSON datasets to JSONL format for embedding computation.
"""
import json
import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "app" / "data"
OUTPUT_DIR = DATA_DIR / "training_data" / "embeddings"


def convert_snorkel_underwriting():
    """Convert Snorkel underwriting dataset to JSONL."""
    input_file = DATA_DIR / "insurance_data" / "training" / "snorkel_underwriting.json"
    output_file = OUTPUT_DIR / "snorkel_underwriting.jsonl"

    logger.info(f"Converting {input_file.name}...")

    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = []
    for item in data:
        # Extract text from the trace
        text_parts = []
        if "trace" in item:
            for msg in item["trace"]:
                content = msg.get("content", "")
                if content:
                    text_parts.append(content)

        if text_parts:
            text = " ".join(text_parts)
            record = {
                "text": text,
                "metadata": {
                    "task": item.get("task", ""),
                    "primary_id": item.get("primary id", ""),
                    "company_task_id": item.get("company task id", ""),
                },
                "source": "snorkel_underwriting",
                "category": item.get("task", "underwriting"),
            }
            records.append(record)

    with open(output_file, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    logger.info(f"  Converted {len(records)} records to {output_file.name}")
    return len(records)


def convert_ledgar():
    """Convert LEDGAR dataset to JSONL."""
    input_file = DATA_DIR / "insurance_data" / "contract_clauses" / "ledgar" / "train.json"
    output_file = OUTPUT_DIR / "ledgar.jsonl"

    logger.info(f"Converting {input_file.name}...")

    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = []
    for item in data:
        text = item.get("text", "")
        label = item.get("label", "")

        if text:
            record = {
                "text": text,
                "metadata": {
                    "label": label,
                },
                "source": "ledgar",
                "category": "contract_clause",
            }
            records.append(record)

    with open(output_file, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    logger.info(f"  Converted {len(records)} records to {output_file.name}")
    return len(records)


def convert_contract_nli():
    """Convert ContractNLI dataset to JSONL."""
    input_file = DATA_DIR / "insurance_data" / "contract_clauses" / "contract_nli" / "train.json"
    output_file = OUTPUT_DIR / "contract_nli.jsonl"

    logger.info(f"Converting {input_file.name}...")

    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = []
    for item in data:
        # ContractNLI has premise/hypothesis pairs
        sentence1 = item.get("sentence1", "")
        sentence2 = item.get("sentence2", "")
        label = item.get("label", "")

        if sentence1:
            # Use premise as main text
            record = {
                "text": sentence1,
                "metadata": {
                    "hypothesis": sentence2,
                    "label": label,
                },
                "source": "contract_nli",
                "category": "contract_nli",
            }
            records.append(record)

    with open(output_file, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    logger.info(f"  Converted {len(records)} records to {output_file.name}")
    return len(records)


def convert_cuad():
    """Convert CUAD dataset to JSONL."""
    input_file = DATA_DIR / "insurance_data" / "contract_clauses" / "cuad" / "train.json"
    output_file = OUTPUT_DIR / "cuad.jsonl"

    logger.info(f"Converting {input_file.name}...")

    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    records = []
    for item in data:
        # CUAD has context and questions
        context = item.get("context", "")
        question = item.get("question", "")
        answers = item.get("answers", {})

        if context:
            record = {
                "text": context,
                "metadata": {
                    "question": question,
                    "answers": answers,
                },
                "source": "cuad",
                "category": "contract_qa",
            }
            records.append(record)

    with open(output_file, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    logger.info(f"  Converted {len(records)} records to {output_file.name}")
    return len(records)


def main():
    """Convert all datasets to JSONL."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = {}

    print("=" * 70)
    print("CONVERTING DATASETS TO JSONL")
    print("=" * 70)

    try:
        results["snorkel_underwriting"] = convert_snorkel_underwriting()
    except Exception as e:
        logger.error(f"Failed to convert snorkel_underwriting: {e}")
        results["snorkel_underwriting"] = 0

    try:
        results["ledgar"] = convert_ledgar()
    except Exception as e:
        logger.error(f"Failed to convert ledgar: {e}")
        results["ledgar"] = 0

    try:
        results["contract_nli"] = convert_contract_nli()
    except Exception as e:
        logger.error(f"Failed to convert contract_nli: {e}")
        results["contract_nli"] = 0

    try:
        results["cuad"] = convert_cuad()
    except Exception as e:
        logger.error(f"Failed to convert cuad: {e}")
        results["cuad"] = 0

    print("\n" + "=" * 70)
    print("CONVERSION SUMMARY")
    print("=" * 70)
    for name, count in sorted(results.items()):
        status = "✓" if count > 0 else "✗"
        print(f"  {status} {name}: {count:,} records")
    print(f"\n  Total: {sum(results.values()):,} records")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
