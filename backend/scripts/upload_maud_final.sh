#!/bin/bash
# Final command to upload MAUD embeddings to S3
# Run this with fresh AWS credentials

# TODO: Update these credentials before running
export AWS_ACCESS_KEY_ID="YOUR_ACCESS_KEY_HERE"
export AWS_SECRET_ACCESS_KEY="YOUR_SECRET_KEY_HERE"
export AWS_SESSION_TOKEN="YOUR_SESSION_TOKEN_HERE"

# Upload MAUD embeddings
echo "Uploading MAUD embeddings to S3..."
aws s3 cp \
  /c/Users/maani/github-instantrisk/repo/backend/app/data/training_data/embeddings/computed/maud.npz \
  s3://instantrisk-documents-995306061991/ml-training/embeddings/maud.npz

echo ""
echo "Verifying upload..."
aws s3 ls s3://instantrisk-documents-995306061991/ml-training/embeddings/ --human-readable | grep maud

echo ""
echo "Upload complete! All 9 datasets now in S3."
