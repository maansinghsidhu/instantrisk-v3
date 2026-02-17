"""Compute embeddings for ACORD forms."""
import json
import sys
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_DIR = Path(__file__).parent.parent
INPUT_FILE = BASE_DIR / "app/data/training_data/embeddings/acord_forms.jsonl"
OUTPUT_NPZ = BASE_DIR / "app/data/training_data/embeddings/computed/acord_forms.npz"

print("Loading insurance-BERT model...")
model = SentenceTransformer("llmware/industry-bert-insurance-v0.1")

print(f"Loading records from {INPUT_FILE}...")
records = []
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            records.append(json.loads(line))

print(f"Computing embeddings for {len(records)} records...")
texts = [r["text"] for r in records]
embeddings = model.encode(texts, batch_size=64, show_progress_bar=True)

print(f"Saving to {OUTPUT_NPZ}...")
OUTPUT_NPZ.parent.mkdir(parents=True, exist_ok=True)
np.savez_compressed(
    OUTPUT_NPZ,
    embeddings=embeddings,
    metadata=json.dumps(records)
)

print(f"✅ Saved {len(records)} ACORD embeddings ({OUTPUT_NPZ.stat().st_size / 1024 / 1024:.1f} MB)")
