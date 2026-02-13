"""
AWS Bedrock Claude Client for InstantRisk V2.

Replaces MiniMax as the LLM backend. Uses EC2 instance role for authentication
(no hardcoded credentials). Supports both streaming and non-streaming responses.

Available models in Maani-Sandbox (us-east-1):
- anthropic.claude-3-sonnet-20240229-v1:0 (Claude Sonnet 4) - default
- anthropic.claude-3-haiku-20240307-v1:0 (Claude Haiku 4.5) - fallback
"""

import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
from dotenv import load_dotenv

# Load .env file so credentials and config are available via os.getenv
# override=True ensures .env values take precedence over stale env vars
load_dotenv(override=True)

logger = logging.getLogger(__name__)

# Bedrock configuration - use inference profile IDs (us. prefix) for newer models
BEDROCK_REGION = os.getenv("AWS_BEDROCK_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
BEDROCK_FALLBACK_MODEL = os.getenv("BEDROCK_FALLBACK_MODEL", "anthropic.claude-3-haiku-20240307-v1:0")
BEDROCK_ENABLED = os.getenv("BEDROCK_ENABLED", "true").lower() == "true"


class BedrockClient:
    """AWS Bedrock Claude client with retry logic."""

    def __init__(self, model_id: str = None, region: str = None):
        self.model_id = model_id or BEDROCK_MODEL_ID
        self.fallback_model_id = BEDROCK_FALLBACK_MODEL
        self.region = region or BEDROCK_REGION
        self.max_retries = 3
        self.base_delay = 2.0
        self._client = None
        self._runtime_client = None

    def _get_client(self, force_new: bool = False):
        """Get or create boto3 Bedrock runtime client."""
        if self._runtime_client is None or force_new:
            import boto3
            profile = os.getenv("AWS_PROFILE", "")
            try:
                if profile:
                    session = boto3.Session(profile_name=profile, region_name=self.region)
                else:
                    # Default credential chain: env vars -> IAM role -> config
                    session = boto3.Session(region_name=self.region)
            except Exception:
                session = boto3.Session(region_name=self.region)
            self._runtime_client = session.client("bedrock-runtime")
        return self._runtime_client

    def _build_bedrock_body(
        self,
        messages: List[Dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """Build the request body for Bedrock Claude API."""
        # Separate system message from conversation messages
        system_content = ""
        conversation_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_content += msg["content"] + "\n"
            else:
                conversation_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        # Ensure messages alternate properly and start with user
        if not conversation_messages or conversation_messages[0]["role"] != "user":
            conversation_messages.insert(0, {"role": "user", "content": "Hello"})

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": conversation_messages,
        }

        if system_content.strip():
            body["system"] = system_content.strip()

        return body

    async def chat(
        self,
        messages: List[Dict],
        temperature: float = 0.1,
        max_tokens: int = 8000,
        model_id: str = None,
    ) -> str:
        """
        Non-streaming chat completion. Used by AutoGen agents and document generator.

        Args:
            messages: List of message dicts with role and content
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            model_id: Optional model ID override (for Haiku/Sonnet selection)

        Returns the response text content.
        """
        if not BEDROCK_ENABLED:
            logger.warning("Bedrock is disabled")
            return ""

        body = self._build_bedrock_body(messages, temperature, max_tokens)
        model_id = model_id or self.model_id

        last_error = None
        for attempt in range(self.max_retries):
            try:
                client = self._get_client()

                logger.info(f"Bedrock API REQUEST - Model: {model_id}, attempt {attempt + 1}")

                # Run synchronous boto3 call in executor to avoid blocking
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: client.invoke_model(
                        modelId=model_id,
                        body=json.dumps(body),
                        contentType="application/json",
                        accept="application/json",
                    ),
                )

                response_body = json.loads(response["body"].read())
                content = ""
                for block in response_body.get("content", []):
                    if block.get("type") == "text":
                        content += block.get("text", "")

                logger.info(f"Bedrock API RESPONSE - Content length: {len(content)}")

                # Filter <think> blocks if present
                if "<think>" in content and "</think>" in content:
                    content = content.split("</think>")[-1].strip()

                return content

            except Exception as e:
                error_str = str(e)
                logger.warning(f"Bedrock API error (attempt {attempt + 1}/{self.max_retries}): {error_str}")
                last_error = error_str

                # On credential/token errors, force new client on next attempt
                if "expired" in error_str.lower() or "credential" in error_str.lower():
                    logger.info("Credential error - refreshing boto3 client")
                    self._runtime_client = None

                # Try fallback model on model-specific errors
                if attempt == 0 and ("model" in error_str.lower() or "validation" in error_str.lower()):
                    logger.info(f"Trying fallback model: {self.fallback_model_id}")
                    model_id = self.fallback_model_id

                delay = self.base_delay * (2 ** attempt)
                await asyncio.sleep(delay)

        logger.error(f"Bedrock API failed after {self.max_retries} attempts. Last error: {last_error}")
        return ""

    async def stream_chat(
        self,
        messages: List[Dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming chat completion. Yields text tokens as they arrive.
        Used by the chat service for real-time responses.
        """
        if not BEDROCK_ENABLED:
            yield "Error: AI service not configured."
            return

        body = self._build_bedrock_body(messages, temperature, max_tokens)
        model_id = self.model_id

        try:
            client = self._get_client()
            loop = asyncio.get_event_loop()

            response = await loop.run_in_executor(
                None,
                lambda: client.invoke_model_with_response_stream(
                    modelId=model_id,
                    body=json.dumps(body),
                    contentType="application/json",
                    accept="application/json",
                ),
            )

            stream = response.get("body")
            if not stream:
                yield "Error: No response stream"
                return

            in_think_block = False

            for event in stream:
                chunk = event.get("chunk")
                if not chunk:
                    continue

                chunk_data = json.loads(chunk["bytes"])
                event_type = chunk_data.get("type", "")

                if event_type == "content_block_delta":
                    delta = chunk_data.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            # Filter <think> blocks
                            if "<think>" in text:
                                in_think_block = True
                            if "</think>" in text:
                                in_think_block = False
                                parts = text.split("</think>")
                                if len(parts) > 1:
                                    text = parts[1]
                                else:
                                    continue

                            if not in_think_block and text:
                                yield text

                elif event_type == "message_stop":
                    break

        except Exception as e:
            logger.error(f"Bedrock stream error: {e}")
            # Try non-streaming fallback
            try:
                result = await self.chat(messages, temperature, max_tokens)
                if result:
                    yield result
                else:
                    yield f"\n\n[Error: {str(e)}]"
            except Exception:
                yield f"\n\n[Error: {str(e)}]"


# Singleton instance
bedrock_client = BedrockClient()


def get_bedrock_client() -> BedrockClient:
    """Get the singleton Bedrock client."""
    return bedrock_client
