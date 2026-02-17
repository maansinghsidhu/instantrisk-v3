"""
InstantRisk V2 - Voice Interface Service

This module provides voice-to-text transcription and voice command processing
for hands-free underwriting using Whisper and Claude AI.

Features:
- Speech-to-text using faster-whisper (local processing, no API costs)
- Voice command parsing using Bedrock Claude
- Support for multiple audio formats (WAV, MP3, M4A, OGG)
- Command execution with structured results
"""

import os
import io
import tempfile
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# Lazy imports for heavy dependencies
_whisper_model = None
_AudioSegment = None


def _get_whisper_model():
    """Lazy load Whisper model to avoid startup overhead."""
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            # Use 'base' model for speed/accuracy balance
            # Device: cpu (compatible with ECS Fargate)
            # Compute type: int8 for efficiency
            _whisper_model = WhisperModel(
                "base",
                device="cpu",
                compute_type="int8",
                download_root=os.getenv("WHISPER_MODEL_PATH", "/tmp/whisper_models")
            )
            logger.info("Whisper model loaded successfully (base/cpu/int8)")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise
    return _whisper_model


def _get_audio_segment():
    """Lazy load pydub AudioSegment."""
    global _AudioSegment
    if _AudioSegment is None:
        from pydub import AudioSegment
        _AudioSegment = AudioSegment
    return _AudioSegment


async def transcribe_audio(audio_data: bytes, audio_format: str = "wav") -> Dict[str, Any]:
    """
    Transcribe audio to text using faster-whisper.

    Args:
        audio_data: Raw audio bytes
        audio_format: Audio format (wav, mp3, m4a, ogg)

    Returns:
        Dict with:
            - text: Transcribed text
            - language: Detected language
            - confidence: Transcription confidence (0-1)
            - duration: Audio duration in seconds

    Raises:
        ValueError: If audio format is unsupported or processing fails
    """
    try:
        # Convert audio to WAV format if needed
        wav_data = audio_data
        if audio_format.lower() != "wav":
            AudioSegment = _get_audio_segment()
            audio = AudioSegment.from_file(io.BytesIO(audio_data), format=audio_format)
            # Convert to WAV: mono, 16kHz (Whisper standard)
            audio = audio.set_channels(1).set_frame_rate(16000)
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            wav_data = wav_buffer.getvalue()
            duration_seconds = len(audio) / 1000.0
        else:
            # For WAV, estimate duration from file size (rough approximation)
            duration_seconds = len(wav_data) / (16000 * 2)  # 16kHz, 16-bit

        # Whisper requires a file path, so write to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_file.write(wav_data)
            tmp_path = tmp_file.name

        try:
            # Transcribe using faster-whisper
            model = _get_whisper_model()
            segments, info = model.transcribe(
                tmp_path,
                language="en",  # Force English for insurance terminology
                beam_size=5,
                vad_filter=True,  # Voice activity detection
                vad_parameters=dict(min_silence_duration_ms=500)
            )

            # Collect segments
            text_parts = []
            confidences = []
            for segment in segments:
                text_parts.append(segment.text)
                # Segment confidence (avg_logprob -> confidence approximation)
                confidence = max(0.0, min(1.0, (segment.avg_logprob + 1.0) / 2.0))
                confidences.append(confidence)

            transcribed_text = " ".join(text_parts).strip()
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            logger.info(f"Transcription complete: {len(transcribed_text)} chars, "
                       f"confidence={avg_confidence:.2f}, duration={duration_seconds:.1f}s")

            return {
                "text": transcribed_text,
                "language": info.language,
                "confidence": round(avg_confidence, 3),
                "duration": round(duration_seconds, 2)
            }

        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"Audio transcription failed: {e}")
        raise ValueError(f"Failed to transcribe audio: {str(e)}")


async def parse_voice_command(
    transcribed_text: str,
    bedrock_client
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Optional[str]]:
    """
    Parse transcribed voice text into a structured command using Claude.

    Args:
        transcribed_text: The transcribed text from voice input
        bedrock_client: BedrockClient instance for AI parsing

    Returns:
        Tuple of (command_type, parameters, error_message)
        - command_type: One of the supported command types (e.g., "create_assessment")
        - parameters: Dict of parsed parameters
        - error_message: Error message if parsing failed

    Supported Commands:
        - create_assessment: Create new risk assessment
        - list_assessments: List assessments with filters
        - get_assessment: Get assessment details by ID or reference
        - search_documents: Search for documents
        - get_risk_score: Get risk score for an assessment
    """
    try:
        # System prompt for command parsing
        system_prompt = """You are a voice command parser for an insurance underwriting platform.

Parse the user's voice command into a structured JSON format with:
1. command_type: The type of command (create_assessment, list_assessments, get_assessment, search_documents, get_risk_score)
2. parameters: Dict of command parameters
3. confidence: Confidence in parsing (0-1)

Supported commands:
- "Create [cyber/property/marine/liability] assessment for [company name]" -> create_assessment
- "Show assessments expiring [next month/this week/today]" -> list_assessments
- "Get risk score for assessment [ID or reference number]" -> get_risk_score
- "List all [cyber/property] assessments" -> list_assessments
- "Find documents about [topic]" -> search_documents
- "Show assessment [ID or reference]" -> get_assessment

Extract relevant parameters like company name, risk category, time filters, etc.

Respond ONLY with valid JSON. No markdown, no explanation.

Example:
{
  "command_type": "create_assessment",
  "parameters": {"company_name": "Acme Corp", "risk_category": "cyber"},
  "confidence": 0.95
}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Parse this voice command: '{transcribed_text}'"}
        ]

        # Use Claude to parse the command
        response = await bedrock_client.chat(
            messages=messages,
            temperature=0.1,  # Low temperature for consistent parsing
            max_tokens=1000
        )

        if not response:
            return None, None, "AI parsing failed - no response"

        # Parse JSON response
        try:
            # Clean response (remove markdown if present)
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response.split("```json")[1].split("```")[0].strip()
            elif clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1].split("```")[0].strip()

            parsed = json.loads(clean_response)
            command_type = parsed.get("command_type")
            parameters = parsed.get("parameters", {})
            confidence = parsed.get("confidence", 0.0)

            # Validate command type
            valid_commands = [
                "create_assessment",
                "list_assessments",
                "get_assessment",
                "search_documents",
                "get_risk_score"
            ]

            if command_type not in valid_commands:
                return None, None, f"Unknown command type: {command_type}"

            if confidence < 0.5:
                return None, None, f"Low confidence in parsing: {confidence:.2f}"

            logger.info(f"Parsed command: {command_type}, confidence={confidence:.2f}")
            return command_type, parameters, None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            return None, None, f"Invalid AI response format: {str(e)}"

    except Exception as e:
        logger.error(f"Command parsing error: {e}")
        return None, None, f"Parsing error: {str(e)}"


async def execute_voice_command(
    command_type: str,
    parameters: Dict[str, Any],
    user_id: str,
    db_session
) -> Dict[str, Any]:
    """
    Execute a parsed voice command and return results.

    Args:
        command_type: Type of command to execute
        parameters: Command parameters
        user_id: User ID for authorization
        db_session: Database session

    Returns:
        Dict with execution results and voice-friendly summary
    """
    try:
        from uuid import UUID
        from sqlalchemy import select, and_, or_
        from app.models.assessment import Assessment
        from app.models.generated_document import GeneratedDocument
        from datetime import datetime, timedelta, timezone

        result = {
            "success": False,
            "data": None,
            "summary": "",
            "command": command_type
        }

        # Execute based on command type
        if command_type == "create_assessment":
            # Create a new assessment
            company_name = parameters.get("company_name")
            risk_category = parameters.get("risk_category", "property")

            if not company_name:
                result["summary"] = "I need a company name to create the assessment."
                return result

            # Create minimal assessment record
            from app.models.assessment import AssessmentMode, AssessmentStatus

            assessment = Assessment(
                created_by=UUID(user_id),
                title=f"{company_name} - {risk_category.title()} Assessment",
                insured_name=company_name,
                risk_category=risk_category,
                mode=AssessmentMode.MANUAL,
                status=AssessmentStatus.IN_PROGRESS
            )
            db_session.add(assessment)
            await db_session.commit()
            await db_session.refresh(assessment)

            result["success"] = True
            result["data"] = {"assessment_id": str(assessment.id)}
            result["summary"] = (
                f"Created {risk_category} assessment for {company_name}. "
                f"Assessment ID is {assessment.id}."
            )

        elif command_type == "list_assessments":
            # List assessments with optional filters
            query = select(Assessment).where(Assessment.created_by == UUID(user_id))

            # Apply filters
            risk_category = parameters.get("risk_category")
            if risk_category:
                query = query.where(Assessment.risk_category == risk_category)

            # Time-based filters
            time_filter = parameters.get("time_filter")  # "next_month", "this_week", "today"
            if time_filter:
                now = datetime.now(timezone.utc)
                if time_filter == "today":
                    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    end = start + timedelta(days=1)
                elif time_filter == "this_week":
                    start = now - timedelta(days=now.weekday())
                    end = start + timedelta(days=7)
                elif time_filter == "next_month":
                    start = now
                    end = now + timedelta(days=30)
                else:
                    start = end = None

                if start and end:
                    query = query.where(
                        and_(
                            Assessment.created_at >= start,
                            Assessment.created_at < end
                        )
                    )

            # Execute query
            query = query.order_by(Assessment.created_at.desc()).limit(10)
            result_set = await db_session.execute(query)
            assessments = result_set.scalars().all()

            result["success"] = True
            result["data"] = {
                "count": len(assessments),
                "assessments": [
                    {
                        "id": str(a.id),
                        "title": a.title,
                        "insured_name": a.insured_name,
                        "risk_category": a.risk_category,
                        "status": a.status
                    }
                    for a in assessments
                ]
            }

            if len(assessments) == 0:
                result["summary"] = "No assessments found matching your criteria."
            elif len(assessments) == 1:
                a = assessments[0]
                result["summary"] = (
                    f"Found 1 assessment: {a.insured_name}, "
                    f"{a.risk_category}, status {a.status}."
                )
            else:
                result["summary"] = (
                    f"Found {len(assessments)} assessments. "
                    f"Most recent is {assessments[0].insured_name}."
                )

        elif command_type == "get_assessment":
            # Get specific assessment by ID or reference
            assessment_id = parameters.get("assessment_id")
            reference = parameters.get("reference_number")

            query = select(Assessment).where(Assessment.created_by == UUID(user_id))

            if assessment_id:
                try:
                    query = query.where(Assessment.id == UUID(assessment_id))
                except ValueError:
                    result["summary"] = "Invalid assessment ID format."
                    return result
            elif reference:
                query = query.where(Assessment.reference_number == reference)
            else:
                result["summary"] = "I need an assessment ID or reference number."
                return result

            result_set = await db_session.execute(query)
            assessment = result_set.scalar_one_or_none()

            if not assessment:
                result["summary"] = "Assessment not found."
                return result

            result["success"] = True
            result["data"] = {
                "id": str(assessment.id),
                "title": assessment.title,
                "insured_name": assessment.insured_name,
                "risk_category": assessment.risk_category,
                "status": assessment.status,
                "risk_score": assessment.risk_score,
                "decision": assessment.decision
            }
            result["summary"] = (
                f"Assessment for {assessment.insured_name}, "
                f"{assessment.risk_category}, "
                f"risk score {assessment.risk_score or 'not calculated'}, "
                f"status {assessment.status}."
            )

        elif command_type == "get_risk_score":
            # Get risk score for an assessment
            assessment_id = parameters.get("assessment_id")

            if not assessment_id:
                result["summary"] = "I need an assessment ID to get the risk score."
                return result

            try:
                query = select(Assessment).where(
                    and_(
                        Assessment.id == UUID(assessment_id),
                        Assessment.created_by == UUID(user_id)
                    )
                )
            except ValueError:
                result["summary"] = "Invalid assessment ID format."
                return result

            result_set = await db_session.execute(query)
            assessment = result_set.scalar_one_or_none()

            if not assessment:
                result["summary"] = "Assessment not found."
                return result

            result["success"] = True
            result["data"] = {
                "risk_score": assessment.risk_score,
                "decision": assessment.decision,
                "confidence": assessment.confidence_score
            }

            if assessment.risk_score:
                result["summary"] = (
                    f"Risk score is {assessment.risk_score} out of 100, "
                    f"decision is {assessment.decision}."
                )
            else:
                result["summary"] = "Risk score has not been calculated yet."

        elif command_type == "search_documents":
            # Search documents
            topic = parameters.get("topic")

            if not topic:
                result["summary"] = "I need a topic to search for."
                return result

            # Search documents by topic/name
            query = select(GeneratedDocument).where(
                and_(
                    GeneratedDocument.created_by == UUID(user_id),
                    or_(
                        GeneratedDocument.name.ilike(f"%{topic}%"),
                        GeneratedDocument.document_type.ilike(f"%{topic}%")
                    )
                )
            ).order_by(GeneratedDocument.created_at.desc()).limit(5)

            result_set = await db_session.execute(query)
            documents = result_set.scalars().all()

            result["success"] = True
            result["data"] = {
                "count": len(documents),
                "documents": [
                    {
                        "id": str(d.id),
                        "name": d.name,
                        "type": d.document_type,
                        "created_at": d.created_at.isoformat()
                    }
                    for d in documents
                ]
            }

            if len(documents) == 0:
                result["summary"] = f"No documents found about {topic}."
            elif len(documents) == 1:
                result["summary"] = f"Found 1 document: {documents[0].name}."
            else:
                result["summary"] = f"Found {len(documents)} documents about {topic}."

        else:
            result["summary"] = f"Command type {command_type} is not yet supported."
            return result

        return result

    except Exception as e:
        logger.error(f"Command execution error: {e}")
        return {
            "success": False,
            "data": None,
            "summary": f"Error executing command: {str(e)}",
            "command": command_type
        }


def get_supported_commands() -> List[Dict[str, str]]:
    """
    Get list of supported voice commands with examples.

    Returns:
        List of command definitions with examples and descriptions
    """
    return [
        {
            "command": "create_assessment",
            "description": "Create a new risk assessment",
            "examples": [
                "Create cyber assessment for Acme Corporation",
                "Create property assessment for ABC Insurance",
                "New marine assessment for Global Shipping"
            ],
            "parameters": "company_name (required), risk_category (cyber/property/marine/liability)"
        },
        {
            "command": "list_assessments",
            "description": "List your assessments with optional filters",
            "examples": [
                "Show all cyber assessments",
                "List assessments expiring next month",
                "Show assessments from this week"
            ],
            "parameters": "risk_category (optional), time_filter (today/this_week/next_month)"
        },
        {
            "command": "get_assessment",
            "description": "Get details of a specific assessment",
            "examples": [
                "Show assessment 12345",
                "Get details for assessment ABC-2024-001"
            ],
            "parameters": "assessment_id or reference_number (required)"
        },
        {
            "command": "get_risk_score",
            "description": "Get the risk score for an assessment",
            "examples": [
                "What is the risk score for assessment 12345",
                "Get risk score for assessment ABC-2024-001"
            ],
            "parameters": "assessment_id (required)"
        },
        {
            "command": "search_documents",
            "description": "Search for documents by topic",
            "examples": [
                "Find documents about cyber insurance",
                "Search for policy documents",
                "Show documents about flood coverage"
            ],
            "parameters": "topic (required)"
        }
    ]
