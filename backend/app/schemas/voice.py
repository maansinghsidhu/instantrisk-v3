"""
InstantRisk V2 - Voice Interface Pydantic Schemas

This module defines Pydantic schemas for voice interface
requests and responses.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class TranscriptionResponse(BaseModel):
    """
    Schema for audio transcription response.

    Attributes:
        text: Transcribed text from audio
        language: Detected language code
        confidence: Transcription confidence (0-1)
        duration: Audio duration in seconds
    """
    text: str
    language: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    duration: float = Field(..., ge=0.0)


class VoiceCommandResponse(BaseModel):
    """
    Schema for voice command execution response.

    Attributes:
        success: Whether command executed successfully
        command: The command type that was executed
        data: Command execution results (structure varies by command)
        summary: Human-readable summary of results (voice-friendly)
        transcription: Original transcription details
    """
    success: bool
    command: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    summary: str
    transcription: Optional[TranscriptionResponse] = None


class SupportedCommand(BaseModel):
    """
    Schema for a supported voice command definition.

    Attributes:
        command: Command type identifier
        description: Human-readable description
        examples: List of example voice commands
        parameters: Description of required/optional parameters
    """
    command: str
    description: str
    examples: List[str]
    parameters: str


class SupportedCommandsResponse(BaseModel):
    """
    Schema for list of supported commands response.

    Attributes:
        commands: List of supported command definitions
        count: Total number of supported commands
    """
    commands: List[SupportedCommand]
    count: int


class AudioFormat(BaseModel):
    """
    Schema for audio format information.

    Attributes:
        format: Audio format (wav, mp3, m4a, ogg)
        max_duration: Maximum audio duration in seconds
        sample_rate: Recommended sample rate in Hz
    """
    format: str
    max_duration: int = 30
    sample_rate: int = 16000


class VoiceError(BaseModel):
    """
    Schema for voice interface error responses.

    Attributes:
        error: Error type
        message: Human-readable error message
        details: Optional additional error details
    """
    error: str
    message: str
    details: Optional[str] = None
