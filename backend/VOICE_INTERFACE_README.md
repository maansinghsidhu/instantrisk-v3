# Voice-First Interface for InstantRisk

## Overview

The Voice-First Interface enables hands-free insurance underwriting through voice commands. Users can create assessments, query data, and retrieve information using natural language voice input.

## Features

- **Speech-to-Text**: Local transcription using faster-whisper (no API costs)
- **AI-Powered Command Parsing**: Uses Bedrock Claude to interpret voice commands
- **Command Execution**: Executes underwriting operations from voice input
- **Voice-Friendly Responses**: Returns human-readable summaries suitable for audio output

## Architecture

### Components

1. **Voice Service** (`app/services/voice_interface.py`)
   - Audio transcription using faster-whisper
   - Command parsing with Claude AI
   - Command execution with database queries
   - Supported commands registry

2. **Voice Router** (`app/routers/voice.py`)
   - REST API endpoints for voice operations
   - Rate limiting and authentication
   - File upload handling

3. **Voice Schemas** (`app/schemas/voice.py`)
   - Pydantic models for request/response validation

## API Endpoints

### 1. Transcribe Audio
**POST** `/api/v1/voice/transcribe`

Transcribe audio file to text.

**Request:**
- `file`: Audio file (multipart/form-data)
- Supported formats: WAV, MP3, M4A, OGG
- Max file size: 10 MB
- Max duration: 30 seconds

**Response:**
```json
{
  "text": "Create cyber assessment for Acme Corporation",
  "language": "en",
  "confidence": 0.95,
  "duration": 3.2
}
```

**Rate Limit:** 20 requests/minute

---

### 2. Execute Voice Command
**POST** `/api/v1/voice/command`

Execute a voice command from audio file.

**Request:**
- `file`: Audio file with voice command
- Same format requirements as `/transcribe`

**Response:**
```json
{
  "success": true,
  "command": "create_assessment",
  "data": {
    "assessment_id": "550e8400-e29b-41d4-a716-446655440000"
  },
  "summary": "Created cyber assessment for Acme Corporation. Assessment ID is 550e8400-e29b-41d4-a716-446655440000.",
  "transcription": {
    "text": "Create cyber assessment for Acme Corporation",
    "language": "en",
    "confidence": 0.95,
    "duration": 3.2
  }
}
```

**Rate Limit:** 10 requests/minute

---

### 3. Get Supported Commands
**GET** `/api/v1/voice/supported-commands`

List all supported voice commands with examples.

**Response:**
```json
{
  "commands": [
    {
      "command": "create_assessment",
      "description": "Create a new risk assessment",
      "examples": [
        "Create cyber assessment for Acme Corporation",
        "Create property assessment for ABC Insurance"
      ],
      "parameters": "company_name (required), risk_category (cyber/property/marine/liability)"
    }
  ],
  "count": 5
}
```

---

### 4. Health Check
**GET** `/api/v1/voice/health`

Check voice interface health status (no authentication required).

**Response:**
```json
{
  "status": "healthy",
  "whisper_loaded": true,
  "supported_formats": ["wav", "mp3", "m4a", "ogg"],
  "max_file_size_mb": 10,
  "max_duration_seconds": 30
}
```

## Supported Commands

### 1. Create Assessment
**Command:** `"Create [risk_category] assessment for [company_name]"`

**Examples:**
- "Create cyber assessment for Acme Corporation"
- "Create property assessment for ABC Insurance"
- "New marine assessment for Global Shipping"

**Parameters:**
- `company_name` (required)
- `risk_category` (optional: cyber/property/marine/liability, default: property)

---

### 2. List Assessments
**Command:** `"Show/list assessments [filters]"`

**Examples:**
- "Show all cyber assessments"
- "List assessments expiring next month"
- "Show assessments from this week"

**Parameters:**
- `risk_category` (optional)
- `time_filter` (optional: today/this_week/next_month)

---

### 3. Get Assessment
**Command:** `"Show/get assessment [ID or reference]"`

**Examples:**
- "Show assessment 12345"
- "Get details for assessment ABC-2024-001"

**Parameters:**
- `assessment_id` or `reference_number` (required)

---

### 4. Get Risk Score
**Command:** `"What is the risk score for assessment [ID]"`

**Examples:**
- "What is the risk score for assessment 12345"
- "Get risk score for assessment ABC-2024-001"

**Parameters:**
- `assessment_id` (required)

---

### 5. Search Documents
**Command:** `"Find/search documents about [topic]"`

**Examples:**
- "Find documents about cyber insurance"
- "Search for policy documents"
- "Show documents about flood coverage"

**Parameters:**
- `topic` (required)

## Dependencies

### Python Packages
- `faster-whisper==1.1.0` - Local speech-to-text (Whisper model)
- `pydub==0.25.1` - Audio format conversion
- `ffmpeg-python==0.2.0` - Audio processing backend

### System Requirements
- **CPU**: Runs on CPU (no GPU required)
- **Memory**: ~500 MB for base model
- **Storage**: ~150 MB for Whisper base model

### External Dependencies
- **FFmpeg**: Required for audio format conversion
  - Install: `apt-get install ffmpeg` (Linux) or `brew install ffmpeg` (Mac)

## Installation

### 1. Install Python Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Install FFmpeg
**Ubuntu/Debian:**
```bash
apt-get update && apt-get install -y ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Docker (add to Dockerfile):**
```dockerfile
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
```

### 3. Download Whisper Model (Automatic)
The Whisper base model (~150 MB) is downloaded automatically on first use to:
- Default: `/tmp/whisper_models`
- Custom: Set `WHISPER_MODEL_PATH` environment variable

## Configuration

### Environment Variables
```bash
# Optional: Custom Whisper model download path
WHISPER_MODEL_PATH=/app/models/whisper

# AWS Bedrock (required for command parsing)
AWS_BEDROCK_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
BEDROCK_ENABLED=true
```

## Usage Examples

### Python Client
```python
import requests

# 1. Transcribe audio
with open("command.mp3", "rb") as f:
    response = requests.post(
        "http://localhost:8200/api/v1/voice/transcribe",
        files={"file": f},
        headers={"Authorization": "Bearer YOUR_TOKEN"}
    )
    print(response.json()["text"])

# 2. Execute voice command
with open("command.mp3", "rb") as f:
    response = requests.post(
        "http://localhost:8200/api/v1/voice/command",
        files={"file": f},
        headers={"Authorization": "Bearer YOUR_TOKEN"}
    )
    result = response.json()
    print(result["summary"])  # Voice-friendly response
```

### cURL
```bash
# Transcribe audio
curl -X POST http://localhost:8200/api/v1/voice/transcribe \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@recording.wav"

# Execute command
curl -X POST http://localhost:8200/api/v1/voice/command \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@recording.wav"

# List supported commands
curl http://localhost:8200/api/v1/voice/supported-commands \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Performance

### Transcription Speed
- **Base model**: ~5-10x real-time on CPU
  - 3-second audio: ~500ms processing time
  - 10-second audio: ~1.5s processing time
- **Memory usage**: ~500 MB

### Command Execution
- **Parse + Execute**: 1-3 seconds (includes Bedrock API call)
- **Rate limits**:
  - Transcribe: 20/minute
  - Command: 10/minute

## Error Handling

### Common Errors

**400 Bad Request**
- Unsupported audio format
- File too large (>10 MB)
- Empty audio file

**422 Unprocessable Entity**
- Audio transcription failed
- Command parsing failed
- Low confidence in command parsing (<0.5)

**429 Too Many Requests**
- Rate limit exceeded
- Wait before retrying

**500 Internal Server Error**
- Whisper model loading failed
- Database connection error
- Bedrock API unavailable

### Error Response Format
```json
{
  "detail": "Error message"
}
```

## Security

### Authentication
- All endpoints require JWT authentication (except `/health`)
- Use `Authorization: Bearer <token>` header

### Rate Limiting
- Per-user rate limits enforced
- Prevents abuse and API overload

### Data Privacy
- Audio files are not stored
- Transcriptions processed in-memory only
- No data sent to external APIs (Whisper runs locally)

### Input Validation
- File size limits (10 MB)
- Duration limits (30 seconds)
- Format validation (WAV, MP3, M4A, OGG only)

## Monitoring

### Health Check
```bash
curl http://localhost:8200/api/v1/voice/health
```

### Logs
Voice interface logs include:
- Transcription results and confidence scores
- Command parsing success/failure
- Execution results
- Performance metrics

**Log format:**
```
INFO: Transcribing audio: recording.wav, size=245760 bytes, format=wav, user=<user_id>
INFO: Transcription complete: 42 chars, confidence=0.95, duration=3.2s
INFO: Parsed command: create_assessment, confidence=0.92
INFO: Command execution successful
```

## Troubleshooting

### Issue: Whisper model download fails
**Solution:**
- Check internet connection
- Set `WHISPER_MODEL_PATH` to writable directory
- Manually download model to `/tmp/whisper_models`

### Issue: FFmpeg not found
**Solution:**
```bash
# Install FFmpeg
apt-get install ffmpeg  # Linux
brew install ffmpeg     # macOS
```

### Issue: Low transcription confidence
**Solution:**
- Use higher quality audio (16kHz, mono, WAV format)
- Reduce background noise
- Speak clearly and slowly
- Use close-talking microphone

### Issue: Command parsing fails
**Solution:**
- Check Bedrock API credentials
- Verify `BEDROCK_ENABLED=true`
- Use simpler, more direct commands
- Review supported command examples

## Future Enhancements

### Planned Features
1. **Multi-language support**: Support for non-English commands
2. **Streaming transcription**: Real-time transcription for long audio
3. **Voice output**: Text-to-speech for responses
4. **Command confirmation**: Ask for confirmation before executing
5. **Complex queries**: Support for multi-step commands
6. **Voice authentication**: Speaker recognition for security

### Model Upgrades
- Option to use larger Whisper models (small, medium, large)
- GPU acceleration support
- Fine-tuned model for insurance terminology

## Contributing

When adding new voice commands:

1. **Define command in service** (`voice_interface.py`):
   - Add to `execute_voice_command()` function
   - Add to `get_supported_commands()` list

2. **Update command parser**:
   - Add command examples to system prompt
   - Update valid command types list

3. **Test thoroughly**:
   - Test with various phrasings
   - Verify parameter extraction
   - Check error handling

## License

Part of InstantRisk V2 - AI-powered insurance underwriting platform.
