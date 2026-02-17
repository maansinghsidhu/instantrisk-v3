"""
Download ACORD insurance forms from Sensible Configuration Library.

Source: https://github.com/sensible-hq/sensible-configuration-library
Forms: ACORD 23, 24, 25, 27, 28, 45, 75, 101, 125, 126, 127, 130, 131, 140, 304, 823
"""

import json
import logging
import requests
from pathlib import Path
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "app/data/insurance_data/acord"
JSONL_OUTPUT = BASE_DIR / "app/data/training_data/embeddings/acord_forms.jsonl"

# ACORD forms available in Sensible Configuration Library
ACORD_FORMS = [
    "acord_23_2007_09",  # Application for Flood Insurance
    "acord_24_2009_01",  # Commercial Automobile Application
    "acord_25_2016_03",  # Certificate of Liability Insurance
    "acord_27_2014_01",  # Commercial General Liability
    "acord_28_2014_01",  # Commercial General Liability Section
    "acord_45_2013_09",  # Commercial Insurance Application
    "acord_75_2014_01",  # Insurance Claim Form
    "acord_101_2008_01", # Additional Remarks Schedule
    "acord_125_2016_03", # Commercial Insurance Application
    "acord_126_2016_03", # Commercial Insurance Application - Additional
    "acord_127_2016_03", # Business Automobile Section
    "acord_130_2016_03", # Workers Compensation Application
    "acord_131_2016_03", # Commercial Property Section
    "acord_140_2007_09", # Property Loss Notice
    "acord_304_2016_03", # Inland Marine Section
    "acord_823_2011_10", # Flood Insurance Application
]

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/sensible-hq/sensible-configuration-library/main/templates/Insurance/ACORD%20Forms/configurations"


def download_acord_form(form_name: str) -> Dict:
    """Download single ACORD form configuration."""
    url = f"{GITHUB_RAW_BASE}/{form_name}.json"
    logger.info(f"Downloading {form_name}...")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        logger.info(f"  ✓ Downloaded {form_name}")
        return data
    except Exception as e:
        logger.error(f"  ✗ Failed to download {form_name}: {e}")
        return None


def extract_fields_from_config(config: Dict, form_name: str) -> List[Dict]:
    """Extract field definitions from ACORD form configuration."""
    records = []

    if not config or "fields" not in config:
        return records

    # Extract form metadata
    form_id = form_name.split("_")[1]  # e.g., "25" from "acord_25_2016_03"
    form_year = form_name.split("_")[2] if len(form_name.split("_")) > 2 else "unknown"

    # Process each field
    for field in config.get("fields", []):
        field_id = field.get("id", "")
        field_type = field.get("type", "")
        field_method = field.get("method", {})

        # Get field description/label
        description = field_id.replace("_", " ").title()
        if isinstance(field_method, dict):
            description = field_method.get("description", description)

        # Create training record
        record = {
            "source": "acord",
            "category": f"ACORD {form_id}",
            "text": f"ACORD Form {form_id} - {description}",
            "metadata": {
                "form_id": form_id,
                "form_name": form_name,
                "form_year": form_year,
                "field_id": field_id,
                "field_type": field_type,
                "clause_type": "insurance",  # For training purposes
                "acord_form_category": "property" if form_id in ["140", "131"] else
                                       "liability" if form_id in ["25", "27", "28"] else
                                       "auto" if form_id in ["24", "127"] else
                                       "flood" if form_id in ["23", "823"] else
                                       "workers_comp" if form_id == "130" else
                                       "commercial",
            }
        }
        records.append(record)

    return records


def main():
    logger.info("=" * 60)
    logger.info("Downloading ACORD Forms from Sensible Configuration Library")
    logger.info("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_records = []

    for form_name in ACORD_FORMS:
        # Download configuration
        config = download_acord_form(form_name)
        if not config:
            continue

        # Save raw JSON
        output_file = OUTPUT_DIR / f"{form_name}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"  → Saved to {output_file}")

        # Extract training records
        records = extract_fields_from_config(config, form_name)
        all_records.extend(records)
        logger.info(f"  → Extracted {len(records)} training records")

    # Save as JSONL for training
    logger.info(f"\nWriting {len(all_records)} records to {JSONL_OUTPUT}")
    with open(JSONL_OUTPUT, "w", encoding="utf-8") as f:
        for record in all_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info("=" * 60)
    logger.info(f"✅ Complete! Downloaded {len(ACORD_FORMS)} ACORD forms")
    logger.info(f"✅ Extracted {len(all_records)} training records")
    logger.info(f"✅ Saved to {JSONL_OUTPUT}")
    logger.info("=" * 60)

    # Summary
    form_counts = {}
    for record in all_records:
        category = record["category"]
        form_counts[category] = form_counts.get(category, 0) + 1

    logger.info("\nRecords by form:")
    for form, count in sorted(form_counts.items()):
        logger.info(f"  {form}: {count} records")


if __name__ == "__main__":
    main()
