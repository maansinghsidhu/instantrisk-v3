"""
Verify all InstantRisk ML training datasets are ready.

Checks:
1. All JSONL files exist
2. All NPZ embedding files exist
3. Embeddings are valid and loadable
4. Record counts match expectations
"""

import numpy as np
from pathlib import Path
import json

# Expected datasets
EXPECTED_DATASETS = {
    'jetech_blocks': 48943,
    'bitext_intents': 39000,
    'maud': 25827,
    'insurance_qa': 21325,
    'ledgar': 4875,
    'snorkel_underwriting': 380,
    'mini_insurance': 92,
    'contract_nli': 56,
    'cuad': 34,
}

# Paths
BASE_DIR = Path(__file__).parent.parent
EMBEDDINGS_DIR = BASE_DIR / "app" / "data" / "training_data" / "embeddings"
COMPUTED_DIR = EMBEDDINGS_DIR / "computed"

def verify_datasets():
    """Verify all datasets are ready."""
    print("="*80)
    print("INSTANTRISK DATASET VERIFICATION")
    print("="*80)
    print()

    issues = []
    success_count = 0
    total_records = 0
    total_size_mb = 0

    for dataset_name, expected_count in sorted(EXPECTED_DATASETS.items(), key=lambda x: -x[1]):
        jsonl_file = EMBEDDINGS_DIR / f"{dataset_name}.jsonl"
        npz_file = COMPUTED_DIR / f"{dataset_name}.npz"

        print(f"Checking: {dataset_name}")

        # Check JSONL
        if not jsonl_file.exists():
            issues.append(f"  [ERROR] JSONL file missing: {jsonl_file}")
            print(f"  [X] JSONL file missing")
            continue
        else:
            print(f"  [OK] JSONL file exists")

        # Check NPZ
        if not npz_file.exists():
            issues.append(f"  [ERROR] NPZ file missing: {npz_file}")
            print(f"  [X] NPZ file missing")
            continue
        else:
            print(f"  [OK] NPZ file exists")

        # Verify NPZ content
        try:
            with np.load(npz_file, allow_pickle=True) as data:
                embeddings = data['embeddings']
                metadata = json.loads(str(data['metadata']))

                actual_count = len(embeddings)
                dim = embeddings.shape[1]
                size_mb = npz_file.stat().st_size / 1024 / 1024

                # Verify count
                if actual_count != expected_count:
                    issues.append(f"  [WARNING] {dataset_name}: Expected {expected_count}, got {actual_count}")
                    print(f"  [!] Record count mismatch: expected {expected_count}, got {actual_count}")
                else:
                    print(f"  [OK] Record count: {actual_count:,}")

                # Verify dimension
                if dim != 768:
                    issues.append(f"  [ERROR] {dataset_name}: Invalid embedding dim: {dim} (expected 768)")
                    print(f"  [X] Invalid embedding dimension: {dim}")
                else:
                    print(f"  [OK] Embedding dimension: {dim}")

                print(f"  [OK] File size: {size_mb:.1f} MB")

                total_records += actual_count
                total_size_mb += size_mb
                success_count += 1

        except Exception as e:
            issues.append(f"  [ERROR] {dataset_name}: Failed to load NPZ: {e}")
            print(f"  [X] Failed to load NPZ: {e}")
            continue

        print()

    # Summary
    print("="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    print()
    print(f"Datasets verified: {success_count}/{len(EXPECTED_DATASETS)}")
    print(f"Total records: {total_records:,}")
    print(f"Total size: {total_size_mb:.1f} MB")
    print()

    if issues:
        print("ISSUES FOUND:")
        for issue in issues:
            print(issue)
        print()
        return False
    else:
        print("[SUCCESS] All datasets verified successfully!")
        print()
        print("Ready for:")
        print("  1. pgvector indexing")
        print("  2. SageMaker training")
        print("  3. Model fine-tuning")
        print()
        return True

if __name__ == "__main__":
    success = verify_datasets()
    exit(0 if success else 1)
