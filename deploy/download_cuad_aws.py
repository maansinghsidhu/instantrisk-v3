"""
Download the full CUAD dataset on AWS (Linux) to bypass Windows 260-char path limit.

Run on AWS CloudShell:
  pip install datasets --quiet
  python download_cuad_aws.py

Downloads from HuggingFace, extracts proper clause types from questions,
creates JSONL, and uploads to S3 for both RAG and training.
"""
import json
import re
import sys
import os


# S3 targets
RAG_BUCKET = "instantrisk-pipeline-artifacts-995306061991"
RAG_KEY = "training-data/cuad_clauses.jsonl"
TRAINING_BUCKET = "instantrisk-documents-995306061991"
TRAINING_KEY = "ml-training/training-data/cuad_full.jsonl"

# CUAD question format: 'Highlight the parts ... related to "Clause Type" ...'
CLAUSE_RE = re.compile(r'"([^"]+)"')

# Map CUAD clause names to our normalized taxonomy
CUAD_CLAUSE_MAP = {
    "document name": "document_name",
    "parties": "parties",
    "agreement date": "agreement_date",
    "effective date": "effective_date",
    "expiration date": "expiration_date",
    "renewal term": "renewal_term",
    "notice period to terminate renewal": "notice_period",
    "governing law": "governing_law",
    "most favored nation": "most_favored_nation",
    "non-compete": "non_compete",
    "exclusivity": "exclusivity",
    "no-solicit of customers": "non_solicitation",
    "competitive restriction exception": "competitive_restriction_exception",
    "no-solicit of employees": "non_solicitation",
    "non-disparagement": "non_disparagement",
    "termination for convenience": "termination_for_convenience",
    "rofr/rofo/rofn": "right_of_first_refusal",
    "change of control": "change_of_control",
    "anti-assignment": "anti_assignment",
    "revenue/profit sharing": "revenue_sharing",
    "price restrictions": "price_restrictions",
    "minimum commitment": "minimum_commitment",
    "volume restriction": "volume_restriction",
    "ip ownership assignment": "ip_ownership",
    "joint ip ownership": "ip_ownership",
    "license grant": "license_grant",
    "non-transferable license": "license_grant",
    "affiliate license-licensor": "license_grant",
    "affiliate license-licensee": "license_grant",
    "unlimited/all-you-can-eat-license": "license_grant",
    "irrevocable or perpetual license": "license_grant",
    "source code escrow": "escrow",
    "post-termination services": "post_termination",
    "audit rights": "audit_rights",
    "uncapped liability": "liability",
    "cap on liability": "liability",
    "liquidated damages": "liquidated_damages",
    "warranty duration": "warranty",
    "insurance": "insurance",
    "covenant not to sue": "covenant_not_to_sue",
    "third party beneficiary": "third_party_beneficiary",
}


def download_and_process():
    """Download CUAD from HuggingFace, extract clause types, write JSONL."""
    from datasets import load_dataset

    print("Downloading CUAD dataset from HuggingFace...")
    print("  (This downloads ~40MB of processed SQuAD-format data)")
    ds = load_dataset("theatticusproject/cuad", split="train")
    print(f"  Raw rows: {len(ds)}")

    output_path = "/tmp/cuad_full.jsonl"
    count = 0
    skipped = 0
    clause_type_counts = {}
    seen = set()  # deduplicate by (context_hash, clause_type)

    with open(output_path, "w", encoding="utf-8") as f:
        for row in ds:
            context = row.get("context", "")
            question = row.get("question", "")
            answers = row.get("answers", {})
            title = row.get("title", "")
            answer_texts = answers.get("text", []) if isinstance(answers, dict) else []

            if not context or len(context.strip()) < 20:
                skipped += 1
                continue

            # Extract clause type from quoted text in question
            match = CLAUSE_RE.search(question)
            if not match:
                skipped += 1
                continue

            raw_clause = match.group(1)
            clause_key = raw_clause.lower().strip()
            clause_type = CUAD_CLAUSE_MAP.get(clause_key, clause_key.replace(" ", "_").replace("-", "_"))

            # Deduplicate by (context_hash, clause_type)
            ctx_hash = hash(context[:500])
            dedup_key = (ctx_hash, clause_type)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            record = {
                "text": context[:2000],
                "category": "cuad_clause",
                "source": "cuad",
                "metadata": {
                    "clause_type": clause_type,
                    "cuad_question_type": raw_clause,
                    "has_answer": len(answer_texts) > 0,
                    "answer_excerpt": answer_texts[0][:200] if answer_texts else "",
                    "doc_title": title[:200] if title else "",
                },
            }
            f.write(json.dumps(record) + "\n")
            count += 1

            clause_type_counts[clause_type] = clause_type_counts.get(clause_type, 0) + 1

            if count % 2000 == 0:
                print(f"  Progress: {count} records...")

    print(f"\nResults:")
    print(f"  Total records: {count}")
    print(f"  Skipped: {skipped}")
    print(f"  Unique clause types: {len(clause_type_counts)}")
    print(f"\nClause type distribution:")
    for ct, cnt in sorted(clause_type_counts.items(), key=lambda x: -x[1]):
        print(f"  {ct}: {cnt}")

    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"\nOutput: {output_path} ({size_mb:.1f} MB)")

    return output_path, count


def upload_to_s3(local_path, count):
    """Upload JSONL to S3 for both RAG indexing and training."""
    import boto3

    s3 = boto3.client("s3", region_name="us-east-1")

    # Upload to RAG bucket (for rag_indexer.py to download)
    print(f"\nUploading to s3://{RAG_BUCKET}/{RAG_KEY}...")
    s3.upload_file(local_path, RAG_BUCKET, RAG_KEY)
    print(f"  Done")

    # Upload to training bucket (for SageMaker)
    print(f"Uploading to s3://{TRAINING_BUCKET}/{TRAINING_KEY}...")
    s3.upload_file(local_path, TRAINING_BUCKET, TRAINING_KEY)
    print(f"  Done")

    print(f"\nCUAD full dataset ({count} records) uploaded to S3!")
    print(f"  RAG:      s3://{RAG_BUCKET}/{RAG_KEY}")
    print(f"  Training: s3://{TRAINING_BUCKET}/{TRAINING_KEY}")


def main():
    local_path, count = download_and_process()

    upload = input("\nUpload to S3? [Y/n]: ").strip().lower()
    if upload != "n":
        upload_to_s3(local_path, count)
    else:
        print(f"Skipped S3 upload. File at: {local_path}")


if __name__ == "__main__":
    main()
