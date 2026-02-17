# Voice Interface Deployment Checklist

## Pre-Deployment Checks

### 1. Dependencies
- [ ] `faster-whisper==1.1.0` added to `requirements.txt`
- [ ] `pydub==0.25.1` added to `requirements.txt`
- [ ] `ffmpeg-python==0.2.0` added to `requirements.txt`
- [ ] FFmpeg installed in Docker image

### 2. Code Files
- [ ] `app/services/voice_interface.py` created and tested
- [ ] `app/routers/voice.py` created and tested
- [ ] `app/schemas/voice.py` created and tested
- [ ] Voice router registered in `app/main.py`
- [ ] Voice schemas exported in `app/schemas/__init__.py`

### 3. Configuration
- [ ] Environment variables documented
- [ ] Whisper model download path configured
- [ ] Bedrock API credentials verified
- [ ] Rate limits configured appropriately

## Docker/ECS Updates

### 1. Dockerfile Changes
Add FFmpeg installation to Dockerfile:

```dockerfile
# Install system dependencies including FFmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
```

### 2. ECS Task Definition
Update task definition with:

**Memory Requirements:**
- Minimum: 1 GB (512 MB base + 500 MB for Whisper model)
- Recommended: 2 GB for production

**CPU Requirements:**
- Minimum: 0.5 vCPU
- Recommended: 1 vCPU for better transcription performance

**Environment Variables:**
```bash
WHISPER_MODEL_PATH=/tmp/whisper_models
BEDROCK_ENABLED=true
AWS_BEDROCK_REGION=us-east-1
```

**Storage:**
- Ensure `/tmp` has at least 500 MB for model storage
- EFS mount not required (models can use ephemeral storage)

### 3. Build and Deploy
```bash
# Update requirements
pip install -r requirements.txt

# Test locally
python test_voice_interface.py

# Build Docker image
docker build -t instantrisk-backend:voice .

# Deploy to ECR
# (Use existing deploy_v18.py script with updated dependencies)
```

## Testing Checklist

### 1. Unit Tests
- [ ] Test audio transcription with WAV file
- [ ] Test audio transcription with MP3 file
- [ ] Test command parsing with various phrases
- [ ] Test supported commands listing
- [ ] Test schema validation

### 2. Integration Tests
- [ ] Test `/api/v1/voice/transcribe` endpoint
- [ ] Test `/api/v1/voice/command` endpoint
- [ ] Test `/api/v1/voice/supported-commands` endpoint
- [ ] Test `/api/v1/voice/health` endpoint
- [ ] Test authentication and rate limiting
- [ ] Test error handling (invalid files, oversized files)

### 3. Performance Tests
- [ ] Test transcription speed (should be <2s for 10s audio)
- [ ] Test command execution speed (should be <3s)
- [ ] Test concurrent requests (rate limit enforcement)
- [ ] Monitor memory usage (should stay under 1.5 GB)

### 4. End-to-End Tests
- [ ] Record actual voice command
- [ ] Upload and transcribe
- [ ] Verify command parsing
- [ ] Verify command execution
- [ ] Check response summary

## Security Checklist

### 1. Authentication
- [ ] All endpoints (except `/health`) require JWT token
- [ ] Token validation working correctly
- [ ] User ID extracted from token correctly

### 2. Rate Limiting
- [ ] `/transcribe` limited to 20/minute per user
- [ ] `/command` limited to 10/minute per user
- [ ] Rate limit headers returned in responses
- [ ] Rate limit errors return 429 status

### 3. Input Validation
- [ ] File size limit enforced (10 MB)
- [ ] Audio format validation working
- [ ] Malicious file handling tested
- [ ] SQL injection prevention verified

### 4. Data Privacy
- [ ] Audio files not persisted to disk
- [ ] Transcriptions not logged in sensitive logs
- [ ] No PII exposed in error messages
- [ ] Database queries use parameterization

## Monitoring and Logging

### 1. Metrics to Track
- [ ] Transcription success rate
- [ ] Command parsing success rate
- [ ] Command execution success rate
- [ ] Average transcription time
- [ ] Average command execution time
- [ ] Rate limit rejections
- [ ] Error rates by type

### 2. Logs to Monitor
- [ ] Whisper model loading success/failure
- [ ] Transcription quality (confidence scores)
- [ ] Command parsing failures
- [ ] Database query errors
- [ ] Bedrock API errors

### 3. Alerts
- [ ] High error rate (>10%)
- [ ] Slow transcription (>5s avg)
- [ ] Memory usage >80%
- [ ] Whisper model load failures

## Production Rollout

### Phase 1: Canary Deployment
- [ ] Deploy to 1 ECS task
- [ ] Test with internal users
- [ ] Monitor error rates and performance
- [ ] Fix any issues before scaling

### Phase 2: Gradual Rollout
- [ ] Scale to 2-3 tasks
- [ ] Enable for beta users
- [ ] Monitor metrics closely
- [ ] Collect user feedback

### Phase 3: Full Production
- [ ] Scale to production task count
- [ ] Enable for all users
- [ ] Set up dashboards
- [ ] Document known issues

## Rollback Plan

### If Issues Occur:
1. **Minor Issues (high latency, low accuracy):**
   - Keep running but disable new user access
   - Investigate and fix
   - Re-enable gradually

2. **Major Issues (crashes, security problems):**
   - Immediately remove voice router from `main.py`
   - Redeploy without voice interface
   - Investigate offline
   - Re-deploy when fixed

### Rollback Commands:
```python
# Comment out in main.py:
# from app.routers import voice
# app.include_router(voice.router, ...)

# Redeploy
python deploy_v18.py
```

## Post-Deployment

### 1. Verification
- [ ] Health check returns healthy status
- [ ] Swagger docs show voice endpoints
- [ ] Test with real voice recordings
- [ ] Verify all commands work
- [ ] Check CloudWatch logs

### 2. Documentation
- [ ] Update API documentation
- [ ] Create user guide for voice commands
- [ ] Document troubleshooting steps
- [ ] Update system architecture diagram

### 3. User Communication
- [ ] Announce new feature
- [ ] Provide usage examples
- [ ] Share supported commands list
- [ ] Collect initial feedback

## Success Criteria

Voice interface deployment is successful if:
- [ ] All endpoints return 2xx for valid requests
- [ ] Transcription accuracy >80% for clear audio
- [ ] Command parsing accuracy >70%
- [ ] Average response time <3 seconds
- [ ] Error rate <5%
- [ ] No security vulnerabilities
- [ ] Positive user feedback
- [ ] Memory usage stable under 1.5 GB

## Known Limitations

Document these for users:
1. **Language Support:** English only initially
2. **Audio Quality:** Requires clear audio with minimal background noise
3. **Command Complexity:** Simple commands only (one action per request)
4. **Accuracy:** Transcription accuracy depends on audio quality
5. **Latency:** 1-3 seconds for transcription + command execution

## Future Enhancements

Track these for future releases:
1. Multi-language support
2. Streaming transcription
3. Text-to-speech responses
4. Complex multi-step commands
5. Voice authentication
6. Offline mode
7. Mobile SDK integration

## Support and Troubleshooting

### Common Issues

**Issue 1: Whisper model not loading**
- Check `/tmp` directory permissions
- Verify internet connection for initial download
- Check available disk space

**Issue 2: Low transcription accuracy**
- Verify audio quality and format
- Check for background noise
- Ensure microphone proximity

**Issue 3: Command parsing failures**
- Verify Bedrock API credentials
- Check command examples in documentation
- Review Bedrock API quotas

**Issue 4: High memory usage**
- Monitor Whisper model memory footprint
- Consider using smaller model (tiny/small)
- Increase ECS task memory if needed

### Getting Help
- Check logs in CloudWatch
- Review `/api/v1/voice/health` endpoint
- Test with `test_voice_interface.py` script
- Contact development team with specific error messages

---

**Deployment Date:** _____________

**Deployed By:** _____________

**Sign-off:**
- [ ] Engineering Lead
- [ ] QA Team
- [ ] Product Owner
- [ ] Security Team
