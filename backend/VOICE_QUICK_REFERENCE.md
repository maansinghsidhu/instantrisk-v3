# Voice Interface Quick Reference

## Endpoints Overview

| Endpoint | Method | Auth | Rate Limit | Purpose |
|----------|--------|------|------------|---------|
| `/api/v1/voice/transcribe` | POST | Yes | 20/min | Transcribe audio to text |
| `/api/v1/voice/command` | POST | Yes | 10/min | Execute voice command |
| `/api/v1/voice/supported-commands` | GET | Yes | - | List commands |
| `/api/v1/voice/health` | GET | No | - | Health check |

## Supported Audio Formats

- WAV (recommended)
- MP3
- M4A
- OGG

**Requirements:**
- Max file size: 10 MB
- Max duration: 30 seconds
- Recommended: 16kHz, mono, WAV

## Command Examples

```
Create Commands:
  "Create cyber assessment for Acme Corporation"
  "Create property assessment for ABC Insurance"
  "New marine assessment for Global Shipping"

List Commands:
  "Show all cyber assessments"
  "List assessments expiring next month"
  "Show assessments from this week"

Get Commands:
  "Show assessment 12345"
  "Get details for assessment ABC-2024-001"
  "What is the risk score for assessment 12345"

Search Commands:
  "Find documents about cyber insurance"
  "Search for policy documents"
```

## Quick Test (cURL)

```bash
# Set your token
TOKEN="your-jwt-token-here"
BASE_URL="http://localhost:8200/api/v1"

# Test transcription
curl -X POST $BASE_URL/voice/transcribe \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@recording.wav"

# Execute command
curl -X POST $BASE_URL/voice/command \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@recording.wav"

# List commands
curl $BASE_URL/voice/supported-commands \
  -H "Authorization: Bearer $TOKEN"

# Health check (no auth)
curl $BASE_URL/voice/health
```

## Quick Test (Python)

```python
import requests

BASE_URL = "http://localhost:8200/api/v1"
TOKEN = "your-jwt-token-here"
headers = {"Authorization": f"Bearer {TOKEN}"}

# Transcribe
with open("recording.wav", "rb") as f:
    r = requests.post(f"{BASE_URL}/voice/transcribe",
                     files={"file": f}, headers=headers)
    print(r.json()["text"])

# Execute command
with open("command.wav", "rb") as f:
    r = requests.post(f"{BASE_URL}/voice/command",
                     files={"file": f}, headers=headers)
    print(r.json()["summary"])
```

## Response Formats

### Transcription Response
```json
{
  "text": "Create cyber assessment for Acme Corp",
  "language": "en",
  "confidence": 0.95,
  "duration": 3.2
}
```

### Command Response
```json
{
  "success": true,
  "command": "create_assessment",
  "data": {"assessment_id": "550e8400-e29b-41d4-a716-446655440000"},
  "summary": "Created cyber assessment for Acme Corp.",
  "transcription": { ... }
}
```

## Error Codes

| Code | Meaning | Common Cause |
|------|---------|--------------|
| 400 | Bad Request | Invalid file format/size |
| 401 | Unauthorized | Missing/invalid token |
| 422 | Unprocessable | Transcription failed, low confidence |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Server Error | Whisper/Bedrock error |

## Environment Variables

```bash
# Optional
WHISPER_MODEL_PATH=/tmp/whisper_models

# Required for command parsing
BEDROCK_ENABLED=true
AWS_BEDROCK_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

## Common Command Parameters

| Command | Required | Optional |
|---------|----------|----------|
| create_assessment | company_name | risk_category |
| list_assessments | - | risk_category, time_filter |
| get_assessment | assessment_id OR reference | - |
| get_risk_score | assessment_id | - |
| search_documents | topic | - |

## Performance Benchmarks

- **Transcription**: 500ms - 2s (for 3-10s audio)
- **Command parsing**: 1-2s (Bedrock API call)
- **Total response**: 1-3s
- **Memory**: ~500 MB (Whisper model)

## Troubleshooting Quick Fixes

**Problem:** Model not loading
```bash
# Check temp directory
ls -la /tmp/whisper_models
# Set custom path
export WHISPER_MODEL_PATH=/app/models
```

**Problem:** FFmpeg missing
```bash
apt-get install ffmpeg  # Linux
brew install ffmpeg     # Mac
```

**Problem:** Low accuracy
- Use WAV format, 16kHz, mono
- Reduce background noise
- Speak clearly and slowly

**Problem:** Command not recognized
- Check supported commands: `GET /voice/supported-commands`
- Use simpler phrasing
- Verify Bedrock API is configured

## Monitoring Commands

```bash
# Check health
curl http://localhost:8200/api/v1/voice/health

# View logs (Docker)
docker logs instantrisk-backend | grep voice

# Memory usage
docker stats instantrisk-backend

# Test performance
time curl -X POST http://localhost:8200/api/v1/voice/transcribe \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.wav"
```

## Development Tips

1. **Test without audio:** Use `/supported-commands` endpoint first
2. **Generate test audio:** Use `test_voice_interface.py` script
3. **Mock Bedrock:** Set `BEDROCK_ENABLED=false` for unit tests
4. **Debug transcription:** Check confidence scores in response
5. **Profile performance:** Use Python `cProfile` on service functions

## Files Overview

```
backend/
├── app/
│   ├── routers/
│   │   └── voice.py              # API endpoints
│   ├── services/
│   │   └── voice_interface.py    # Core logic
│   └── schemas/
│       └── voice.py              # Pydantic models
├── requirements.txt              # Dependencies
├── test_voice_interface.py       # Test script
├── VOICE_INTERFACE_README.md     # Full documentation
└── VOICE_DEPLOYMENT_CHECKLIST.md # Deployment guide
```

## Adding New Commands

1. **Add to `execute_voice_command()`** in `voice_interface.py`
2. **Add to `get_supported_commands()`** list
3. **Update parser system prompt** with examples
4. **Add to valid_commands** list
5. **Test thoroughly**

Example:
```python
elif command_type == "new_command":
    # Your implementation
    result["success"] = True
    result["data"] = {...}
    result["summary"] = "Command executed"
```

## Security Checklist

- [ ] JWT token required (except `/health`)
- [ ] Rate limits enforced
- [ ] File size validated
- [ ] Audio files not persisted
- [ ] SQL injection prevented
- [ ] No sensitive data in logs

## Quick Links

- API Docs: http://localhost:8200/docs#/Voice%20Interface
- Health Check: http://localhost:8200/api/v1/voice/health
- Full Documentation: `VOICE_INTERFACE_README.md`
- Deployment Guide: `VOICE_DEPLOYMENT_CHECKLIST.md`

---

**Last Updated:** 2026-02-18
**Version:** 1.0
**Contact:** Development Team
