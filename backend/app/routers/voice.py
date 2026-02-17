"""
InstantRisk V2 - Voice Interface Router

This module provides REST API endpoints for voice-to-text transcription
and voice command execution for hands-free insurance underwriting.

Endpoints:
- POST /api/v1/voice/transcribe - Transcribe audio to text
- POST /api/v1/voice/command - Execute voice command from audio
- GET /api/v1/voice/supported-commands - List supported commands
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.voice import (
    TranscriptionResponse,
    VoiceCommandResponse,
    SupportedCommandsResponse,
    SupportedCommand,
    VoiceError
)
from app.services.voice_interface import (
    transcribe_audio,
    parse_voice_command,
    execute_voice_command,
    get_supported_commands
)
from app.services.bedrock_client import get_bedrock_client
from app.middleware.rate_limiter import limiter, RateLimits

logger = logging.getLogger(__name__)

router = APIRouter()

# Supported audio formats and limits
SUPPORTED_FORMATS = {"wav", "mp3", "m4a", "ogg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_DURATION = 30  # seconds


@router.post("/transcribe", response_model=TranscriptionResponse)
@limiter.limit("20/minute")
async def transcribe_audio_endpoint(
    request: Request,
    file: UploadFile = File(..., description="Audio file (WAV, MP3, M4A, OGG)"),
    current_user: User = Depends(get_current_user)
) -> TranscriptionResponse:
    """
    Transcribe audio file to text using Whisper.

    **Audio Requirements:**
    - Formats: WAV, MP3, M4A, OGG
    - Max file size: 10 MB
    - Max duration: 30 seconds
    - Recommended: 16kHz sample rate, mono channel

    **Rate Limits:**
    - 20 requests per minute per user

    **Returns:**
    - Transcribed text
    - Detected language
    - Confidence score (0-1)
    - Audio duration in seconds

    **Errors:**
    - 400: Invalid audio format or file too large
    - 422: Audio processing failed
    - 429: Rate limit exceeded
    """
    try:
        # Validate file format
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required"
            )

        file_ext = file.filename.split(".")[-1].lower()
        if file_ext not in SUPPORTED_FORMATS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported audio format. Supported: {', '.join(SUPPORTED_FORMATS)}"
            )

        # Read file data
        audio_data = await file.read()

        # Validate file size
        if len(audio_data) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)} MB"
            )

        if len(audio_data) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty audio file"
            )

        # Transcribe audio
        logger.info(f"Transcribing audio: {file.filename}, size={len(audio_data)} bytes, "
                   f"format={file_ext}, user={current_user.id}")

        result = await transcribe_audio(audio_data, file_ext)

        # Validate duration
        if result["duration"] > MAX_DURATION:
            logger.warning(f"Audio duration {result['duration']}s exceeds max {MAX_DURATION}s")
            # Allow it but log warning - transcription already completed

        logger.info(f"Transcription successful: {len(result['text'])} chars, "
                   f"confidence={result['confidence']}")

        return TranscriptionResponse(**result)

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Audio processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Transcription endpoint error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process audio file"
        )


@router.post("/command", response_model=VoiceCommandResponse)
@limiter.limit("10/minute")
async def execute_voice_command_endpoint(
    request: Request,
    file: UploadFile = File(..., description="Audio file with voice command"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> VoiceCommandResponse:
    """
    Execute a voice command from audio file.

    This endpoint:
    1. Transcribes the audio to text
    2. Parses the command using AI
    3. Executes the command
    4. Returns structured results with voice-friendly summary

    **Supported Commands:**
    - Create assessment: "Create cyber assessment for Company X"
    - List assessments: "Show all property assessments"
    - Get assessment: "Show assessment 12345"
    - Get risk score: "What is the risk score for assessment 12345"
    - Search documents: "Find documents about cyber insurance"

    **Audio Requirements:**
    - Same as /transcribe endpoint

    **Rate Limits:**
    - 10 requests per minute per user

    **Returns:**
    - success: Whether command executed successfully
    - command: The command type that was executed
    - data: Structured command results
    - summary: Human-readable summary (voice-friendly)
    - transcription: Original transcription details

    **Errors:**
    - 400: Invalid audio or command format
    - 422: Command parsing or execution failed
    - 429: Rate limit exceeded
    """
    try:
        # Validate and read audio file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required"
            )

        file_ext = file.filename.split(".")[-1].lower()
        if file_ext not in SUPPORTED_FORMATS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported audio format. Supported: {', '.join(SUPPORTED_FORMATS)}"
            )

        audio_data = await file.read()

        if len(audio_data) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)} MB"
            )

        logger.info(f"Processing voice command: {file.filename}, user={current_user.id}")

        # Step 1: Transcribe audio
        transcription = await transcribe_audio(audio_data, file_ext)
        transcribed_text = transcription["text"]

        if not transcribed_text or len(transcribed_text.strip()) < 3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not transcribe audio or transcription too short"
            )

        logger.info(f"Transcribed: '{transcribed_text}'")

        # Step 2: Parse command using AI
        bedrock_client = get_bedrock_client()
        command_type, parameters, error = await parse_voice_command(
            transcribed_text,
            bedrock_client
        )

        if error or not command_type:
            logger.warning(f"Command parsing failed: {error}")
            return VoiceCommandResponse(
                success=False,
                command=None,
                data=None,
                summary=f"I couldn't understand that command. {error or 'Please try again.'}",
                transcription=TranscriptionResponse(**transcription)
            )

        logger.info(f"Parsed command: {command_type}, parameters={parameters}")

        # Step 3: Execute command
        result = await execute_voice_command(
            command_type=command_type,
            parameters=parameters,
            user_id=str(current_user.id),
            db_session=db
        )

        # Return response with transcription
        return VoiceCommandResponse(
            success=result["success"],
            command=result["command"],
            data=result["data"],
            summary=result["summary"],
            transcription=TranscriptionResponse(**transcription)
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Voice command processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Voice command endpoint error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process voice command"
        )


@router.get("/supported-commands", response_model=SupportedCommandsResponse)
async def get_supported_commands_endpoint(
    current_user: User = Depends(get_current_user)
) -> SupportedCommandsResponse:
    """
    Get list of supported voice commands.

    Returns definitions, examples, and parameter descriptions for all
    supported voice commands.

    **Authentication Required:** Yes

    **Returns:**
    - List of command definitions with examples
    - Total count of supported commands

    **Example Response:**
    ```json
    {
      "commands": [
        {
          "command": "create_assessment",
          "description": "Create a new risk assessment",
          "examples": ["Create cyber assessment for Acme Corp"],
          "parameters": "company_name (required), risk_category (optional)"
        }
      ],
      "count": 5
    }
    ```
    """
    try:
        commands = get_supported_commands()

        return SupportedCommandsResponse(
            commands=[SupportedCommand(**cmd) for cmd in commands],
            count=len(commands)
        )

    except Exception as e:
        logger.error(f"Error getting supported commands: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve supported commands"
        )


@router.get("/health")
async def voice_health_check():
    """
    Health check endpoint for voice interface.

    Returns the status of voice interface components.
    Does not require authentication.
    """
    try:
        # Check if Whisper can be loaded (lazy check)
        from app.services.voice_interface import _whisper_model

        status_info = {
            "status": "healthy",
            "whisper_loaded": _whisper_model is not None,
            "supported_formats": list(SUPPORTED_FORMATS),
            "max_file_size_mb": MAX_FILE_SIZE // (1024 * 1024),
            "max_duration_seconds": MAX_DURATION
        }

        return JSONResponse(content=status_info)

    except Exception as e:
        logger.error(f"Voice health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )
