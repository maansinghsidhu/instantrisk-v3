"""
Test script for Voice Interface endpoints.

This script tests the voice interface functionality including:
- Audio transcription
- Voice command execution
- Supported commands listing

Usage:
    python test_voice_interface.py
"""

import asyncio
import io
import wave
import struct
import math
from datetime import datetime


def generate_test_audio():
    """
    Generate a simple test WAV file (1 second of 440Hz tone).

    Returns:
        bytes: WAV file data
    """
    sample_rate = 16000
    duration = 1.0  # seconds
    frequency = 440.0  # A4 note

    # Generate sine wave samples
    num_samples = int(sample_rate * duration)
    samples = []
    for i in range(num_samples):
        sample = int(32767 * 0.5 * math.sin(2 * math.pi * frequency * i / sample_rate))
        samples.append(sample)

    # Create WAV file in memory
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(struct.pack(f'{len(samples)}h', *samples))

    return wav_buffer.getvalue()


async def test_transcription():
    """Test audio transcription functionality."""
    from app.services.voice_interface import transcribe_audio

    print("\n=== Testing Audio Transcription ===")

    # Generate test audio
    audio_data = generate_test_audio()
    print(f"Generated test audio: {len(audio_data)} bytes")

    try:
        # Test transcription
        result = await transcribe_audio(audio_data, "wav")

        print(f"Transcription successful!")
        print(f"  Text: {result['text']}")
        print(f"  Language: {result['language']}")
        print(f"  Confidence: {result['confidence']:.3f}")
        print(f"  Duration: {result['duration']:.2f}s")

        return True

    except Exception as e:
        print(f"Transcription failed: {e}")
        return False


async def test_command_parsing():
    """Test voice command parsing."""
    from app.services.voice_interface import parse_voice_command
    from app.services.bedrock_client import get_bedrock_client

    print("\n=== Testing Command Parsing ===")

    test_commands = [
        "Create cyber assessment for Acme Corporation",
        "Show all property assessments",
        "Get risk score for assessment 12345",
        "Find documents about cyber insurance",
    ]

    bedrock_client = get_bedrock_client()

    for text in test_commands:
        print(f"\nParsing: '{text}'")

        try:
            command_type, parameters, error = await parse_voice_command(
                text, bedrock_client
            )

            if error:
                print(f"  Error: {error}")
            else:
                print(f"  Command: {command_type}")
                print(f"  Parameters: {parameters}")

        except Exception as e:
            print(f"  Exception: {e}")


def test_supported_commands():
    """Test supported commands listing."""
    from app.services.voice_interface import get_supported_commands

    print("\n=== Testing Supported Commands ===")

    commands = get_supported_commands()
    print(f"Found {len(commands)} supported commands:")

    for cmd in commands:
        print(f"\n{cmd['command']}:")
        print(f"  Description: {cmd['description']}")
        print(f"  Parameters: {cmd['parameters']}")
        print(f"  Examples:")
        for example in cmd['examples']:
            print(f"    - {example}")


async def test_schemas():
    """Test Pydantic schema validation."""
    from app.schemas.voice import (
        TranscriptionResponse,
        VoiceCommandResponse,
        SupportedCommand,
    )

    print("\n=== Testing Pydantic Schemas ===")

    # Test TranscriptionResponse
    try:
        transcription = TranscriptionResponse(
            text="Create cyber assessment for Acme Corp",
            language="en",
            confidence=0.95,
            duration=3.2
        )
        print(f"TranscriptionResponse: OK")
        print(f"  {transcription.model_dump_json()}")
    except Exception as e:
        print(f"TranscriptionResponse: FAILED - {e}")

    # Test VoiceCommandResponse
    try:
        command_response = VoiceCommandResponse(
            success=True,
            command="create_assessment",
            data={"assessment_id": "123"},
            summary="Created assessment successfully",
            transcription=transcription
        )
        print(f"\nVoiceCommandResponse: OK")
        print(f"  Summary: {command_response.summary}")
    except Exception as e:
        print(f"VoiceCommandResponse: FAILED - {e}")

    # Test SupportedCommand
    try:
        supported_cmd = SupportedCommand(
            command="create_assessment",
            description="Create a new assessment",
            examples=["Create cyber assessment for Company X"],
            parameters="company_name (required)"
        )
        print(f"\nSupportedCommand: OK")
        print(f"  {supported_cmd.model_dump_json()}")
    except Exception as e:
        print(f"SupportedCommand: FAILED - {e}")


async def test_integration():
    """Test full integration flow."""
    print("\n=== Testing Integration Flow ===")

    # Note: This requires a running database and proper auth setup
    print("Integration test requires:")
    print("  - Running database")
    print("  - Valid user authentication")
    print("  - Bedrock API access")
    print("\nSkipping integration test in standalone mode.")
    print("Use the API endpoints directly for integration testing.")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Voice Interface Test Suite")
    print("=" * 60)
    print(f"Started at: {datetime.now().isoformat()}")

    # Test 1: Supported commands (no async)
    test_supported_commands()

    # Test 2: Schemas
    await test_schemas()

    # Test 3: Transcription (requires Whisper model)
    print("\n" + "=" * 60)
    print("NOTE: The following tests require Whisper model download")
    print("      and may take a few minutes on first run.")
    print("=" * 60)

    try:
        await test_transcription()
    except Exception as e:
        print(f"\nTranscription test skipped: {e}")
        print("This is expected if Whisper model is not installed.")

    # Test 4: Command parsing (requires Bedrock API)
    try:
        await test_command_parsing()
    except Exception as e:
        print(f"\nCommand parsing test skipped: {e}")
        print("This is expected if Bedrock API is not configured.")

    # Test 5: Integration
    await test_integration()

    print("\n" + "=" * 60)
    print(f"Tests completed at: {datetime.now().isoformat()}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
