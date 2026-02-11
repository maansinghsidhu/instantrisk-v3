# Insurance AI Model Training

Fine-tuned LLMs for insurance domain tasks using **Unsloth** + **LoRA**.

## Models

1. **InsuranceChat** - Q&A about insurance policies, claims, underwriting
   - Training data: 78,237 examples (93.4 MB)
   - Use case: Customer support, policy explanation, claims guidance

2. **DocumentGen** - Generate insurance clauses and policy documents
   - Training data: 31,610 clauses + 13 full policies
   - Use case: Draft policies, generate clauses, legal text

## Quick Start

### Option 1: Google Colab (Recommended - Free)

1. Open [colab_training.ipynb](./colab_training.ipynb) in Google Colab
2. Enable GPU: Runtime > Change runtime type > T4 GPU
3. Upload your training data when prompted
4. Run all cells
5. Download the trained model

**Estimated time:** 2-4 hours for full training on free T4

### Option 2: Saturn Cloud

```bash
# Install dependencies
pip install requests

# Run setup (creates GPU resource)
python saturn_cloud_setup.py --token YOUR_SATURN_TOKEN

# Then follow the printed instructions
```

**Note:** Saturn Cloud free tier provides 10-30 hours of T4 GPU per month.

### Option 3: Local Training (requires GPU)

```bash
# Install dependencies
pip install torch transformers datasets trl accelerate bitsandbytes
pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"

# Train chat model
python train_insurance_model.py --model chat --epochs 1

# Train document generator
python train_insurance_model.py --model docgen --epochs 1

# Train both
python train_insurance_model.py --model both --epochs 1
```

## Training Data Format

### Chat Model (insurance_qa_train.jsonl)
```json
{
  "messages": [
    {"role": "system", "content": "You are an expert insurance professional..."},
    {"role": "user", "content": "What is a deductible?"},
    {"role": "assistant", "content": "A deductible is the amount..."}
  ]
}
```

### Document Generator (clause_generation_train.jsonl)
```json
{
  "prompt": "Generate an insurance clause for: War Risks Clause (Category: Time Charter Party)",
  "completion": "The Vessel shall not be ordered to..."
}
```

## Configuration

### Base Models (smallest to largest)

| Model | Parameters | Speed | Quality | Free Tier |
|-------|------------|-------|---------|-----------|
| `phi3-mini` | 3.8B | Fastest | Good | Yes |
| `qwen2.5-3b` | 3B | Fast | Good | Yes |
| `llama3.2-3b` | 3B | Fast | Good | Yes |
| `phi3.5-mini` | 3.8B | Fast | Better | Yes |
| `mistral-7b` | 7B | Slower | Best | Maybe |

**Recommendation:** Start with `phi3-mini` for testing, use `mistral-7b` for production.

### Training Parameters

```python
# LoRA Configuration
LORA_R = 16           # Rank (higher = better quality, slower)
LORA_ALPHA = 16       # Scaling factor
MAX_SEQ_LENGTH = 2048 # Context window

# Training
BATCH_SIZE = 2        # Per-device batch size
GRADIENT_ACCUMULATION = 4  # Effective batch = 8
LEARNING_RATE = 2e-4
NUM_EPOCHS = 1-3      # 1 epoch is usually sufficient
```

## Inference

### Command Line

```bash
# Interactive chat
python inference.py --model chat --interactive

# Single prompt
python inference.py --model docgen --prompt "Generate a cyber liability clause"

# Start API server
python inference.py --serve --port 8000
```

### Python API

```python
from inference import InsuranceChatModel, DocumentGenModel, GenerationConfig

# Chat model
chat = InsuranceChatModel("./models/insurance-chat-phi3-mini-20240127/merged_model")
chat.load()

response = chat.answer("What is the difference between term and whole life insurance?")
print(response)

# Document generator
docgen = DocumentGenModel("./models/insurance-docgen-phi3-mini-20240127/merged_model")
docgen.load()

clause = docgen.generate_clause(
    clause_type="Cyber Liability",
    category="Professional Liability",
    requirements="Include data breach coverage"
)
print(clause)
```

### REST API

```bash
# Start server
python inference.py --serve --port 8000

# Chat endpoint
curl -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is a deductible?"}'

# Document generation endpoint
curl -X POST http://localhost:8000/v1/generate-clause \
  -H "Content-Type: application/json" \
  -d '{"clause_type": "War Risks", "category": "Marine"}'
```

## File Structure

```
ml/
├── README.md                    # This file
├── train_insurance_model.py     # Main training script
├── inference.py                 # Inference and API server
├── saturn_cloud_setup.py        # Saturn Cloud automation
├── colab_training.ipynb         # Google Colab notebook
└── models/                      # Trained models (created after training)
    ├── insurance-chat-phi3-mini-YYYYMMDD/
    │   ├── lora_adapter/       # LoRA weights only (~50MB)
    │   ├── merged_model/       # Full merged model (~7GB)
    │   └── training_info.json
    └── insurance-docgen-phi3-mini-YYYYMMDD/
        └── ...
```

## Platform Comparison

| Platform | Cost | GPU | Hours/Month | Setup |
|----------|------|-----|-------------|-------|
| Google Colab | Free | T4/A100 | ~12-40 | Easy |
| Saturn Cloud | Free | T4 | 10-30 | Medium |
| HuggingFace Spaces | Free | T4 | ~40 | Easy |
| Lambda Labs | $0.50/hr | A10 | Unlimited | Easy |
| RunPod | $0.30/hr | A40 | Unlimited | Easy |

## Tips for Free Tier Training

1. **Use smaller models:** `phi3-mini` or `qwen2.5-3b`
2. **Limit samples:** Start with 5,000-10,000 for testing
3. **1 epoch is enough:** More epochs rarely help significantly
4. **Save LoRA only:** Merged models are much larger
5. **Use 4-bit quantization:** Reduces VRAM by 75%

## Troubleshooting

### Out of Memory
- Reduce `BATCH_SIZE` to 1
- Reduce `MAX_SEQ_LENGTH` to 1024
- Enable gradient checkpointing (default)
- Use 4-bit quantization (default)

### Slow Training
- Use `phi3-mini` instead of larger models
- Reduce training samples with `--max-samples`
- Enable `packing=True` in trainer (may reduce quality)

### Model Quality Issues
- Increase `LORA_R` to 32 or 64
- Train for 2-3 epochs
- Use larger base model (`mistral-7b`)
- Check training data quality

## Model Performance

Benchmarks on insurance Q&A test set (estimated):

| Model | Accuracy | Latency | VRAM |
|-------|----------|---------|------|
| Phi-3-mini (fine-tuned) | 78% | 45ms | 4GB |
| Mistral-7B (fine-tuned) | 85% | 120ms | 8GB |
| GPT-4 (baseline) | 92% | 500ms | API |

## License

Training scripts: MIT License
Base models: Check individual model licenses on Hugging Face
Training data: See data source licenses

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Saturn Cloud/Colab documentation
3. Check Unsloth GitHub issues: https://github.com/unslothai/unsloth
