#!/usr/bin/env python3
"""
Insurance AI Model Inference
============================

Load and use fine-tuned insurance models for:
1. InsuranceChat - Answer insurance-related questions
2. DocumentGen - Generate insurance clauses and policies

Supports multiple deployment modes:
- Local inference (GPU/CPU)
- API server (FastAPI)
- Batch processing

Usage:
    # Interactive chat
    python inference.py --model chat --interactive

    # Generate document
    python inference.py --model docgen --prompt "Generate a cyber liability clause"

    # Start API server
    python inference.py --serve --port 8000

Author: InstantRisk AI Team
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Generator
from dataclasses import dataclass
from functools import lru_cache

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class GenerationConfig:
    """Configuration for text generation."""
    max_new_tokens: int = 1024
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 50
    repetition_penalty: float = 1.1
    do_sample: bool = True
    stream: bool = False


class InsuranceModel:
    """Base class for insurance models."""

    def __init__(
        self,
        model_path: str,
        model_type: str = "chat",
        device: str = "auto",
        load_in_4bit: bool = True
    ):
        """
        Initialize the insurance model.

        Args:
            model_path: Path to model directory (merged or LoRA adapter)
            model_type: "chat" or "docgen"
            device: "auto", "cuda", or "cpu"
            load_in_4bit: Use 4-bit quantization (recommended)
        """
        self.model_path = Path(model_path)
        self.model_type = model_type
        self.device = device
        self.load_in_4bit = load_in_4bit
        self.model = None
        self.tokenizer = None
        self._loaded = False

        # System prompts
        self.system_prompts = {
            "chat": """You are an expert insurance professional with deep knowledge of Lloyd's of London market practices, commercial insurance, reinsurance, and regulatory frameworks. You provide accurate, detailed, and helpful responses about insurance concepts, policies, claims, and underwriting.""",

            "docgen": """You are an expert insurance document generator. You create professional insurance clauses, policy documents, and legal text based on the given requirements. Your output should be precise, legally sound, and follow insurance industry standards."""
        }

    def load(self):
        """Load the model and tokenizer."""
        if self._loaded:
            return

        logger.info(f"Loading model from {self.model_path}")

        try:
            # Try Unsloth first (faster inference)
            self._load_with_unsloth()
        except ImportError:
            # Fallback to transformers
            logger.info("Unsloth not available, using transformers")
            self._load_with_transformers()

        self._loaded = True
        logger.info("Model loaded successfully")

    def _load_with_unsloth(self):
        """Load using Unsloth for optimized inference."""
        from unsloth import FastLanguageModel
        from unsloth.chat_templates import get_chat_template

        self.model, self.tokenizer = FastLanguageModel.from_pretrained(
            model_name=str(self.model_path),
            max_seq_length=2048,
            load_in_4bit=self.load_in_4bit,
            dtype=None,
        )

        # Enable inference mode
        FastLanguageModel.for_inference(self.model)

        # Setup chat template
        self.tokenizer = get_chat_template(
            self.tokenizer,
            chat_template="phi-3" if "phi" in str(self.model_path).lower() else "llama-3.1",
        )

        self._inference_mode = "unsloth"

    def _load_with_transformers(self):
        """Load using standard transformers."""
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        # Configure quantization
        if self.load_in_4bit:
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )
        else:
            quantization_config = None

        # Load model (local_files_only prevents unintended remote downloads)
        self.model = AutoModelForCausalLM.from_pretrained(
            str(self.model_path),
            quantization_config=quantization_config,
            device_map=self.device,
            torch_dtype=torch.float16,
            trust_remote_code=False,
            local_files_only=True,
        )

        self.tokenizer = AutoTokenizer.from_pretrained(
            str(self.model_path),
            trust_remote_code=False,
            local_files_only=True,
        )

        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self._inference_mode = "transformers"

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Generate a response.

        Args:
            prompt: User input/question
            system_prompt: Override default system prompt
            config: Generation configuration
            history: Conversation history for multi-turn chat

        Returns:
            Generated text response
        """
        if not self._loaded:
            self.load()

        config = config or GenerationConfig()
        system = system_prompt or self.system_prompts.get(self.model_type, "")

        # Build messages
        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        # Add history if provided
        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": prompt})

        # Format with chat template
        input_text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        # Tokenize
        inputs = self.tokenizer(
            input_text,
            return_tensors="pt",
            truncation=True,
            max_length=2048 - config.max_new_tokens
        )

        if hasattr(self.model, 'device'):
            inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        # Generate
        import torch
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=config.max_new_tokens,
                temperature=config.temperature if config.do_sample else 1.0,
                top_p=config.top_p if config.do_sample else 1.0,
                top_k=config.top_k if config.do_sample else 0,
                repetition_penalty=config.repetition_penalty,
                do_sample=config.do_sample,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        # Decode only new tokens
        response = self.tokenizer.decode(
            outputs[0][inputs['input_ids'].shape[1]:],
            skip_special_tokens=True
        )

        return response.strip()

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        config: Optional[GenerationConfig] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Generator[str, None, None]:
        """
        Generate a response with streaming.

        Yields tokens as they are generated.
        """
        if not self._loaded:
            self.load()

        from transformers import TextIteratorStreamer
        from threading import Thread

        config = config or GenerationConfig()
        system = system_prompt or self.system_prompts.get(self.model_type, "")

        # Build messages
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        # Format
        input_text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        inputs = self.tokenizer(
            input_text,
            return_tensors="pt",
            truncation=True,
            max_length=2048 - config.max_new_tokens
        )

        if hasattr(self.model, 'device'):
            inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        # Setup streamer
        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,
            skip_special_tokens=True
        )

        # Generate in background thread
        generation_kwargs = dict(
            **inputs,
            max_new_tokens=config.max_new_tokens,
            temperature=config.temperature if config.do_sample else 1.0,
            top_p=config.top_p if config.do_sample else 1.0,
            do_sample=config.do_sample,
            streamer=streamer,
            pad_token_id=self.tokenizer.pad_token_id,
            eos_token_id=self.tokenizer.eos_token_id,
        )

        thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
        thread.start()

        # Yield tokens
        for text in streamer:
            yield text

        thread.join()

    def batch_generate(
        self,
        prompts: List[str],
        config: Optional[GenerationConfig] = None
    ) -> List[str]:
        """Generate responses for multiple prompts."""
        return [self.generate(p, config=config) for p in prompts]


class InsuranceChatModel(InsuranceModel):
    """Specialized model for insurance Q&A."""

    def __init__(self, model_path: str, **kwargs):
        super().__init__(model_path, model_type="chat", **kwargs)

    def answer(self, question: str, context: Optional[str] = None) -> str:
        """
        Answer an insurance question.

        Args:
            question: The user's question
            context: Optional context (e.g., policy document)

        Returns:
            Answer string
        """
        prompt = question
        if context:
            prompt = f"Context:\n{context}\n\nQuestion: {question}"

        return self.generate(prompt)


class DocumentGenModel(InsuranceModel):
    """Specialized model for generating insurance documents."""

    def __init__(self, model_path: str, **kwargs):
        super().__init__(model_path, model_type="docgen", **kwargs)

    def generate_clause(
        self,
        clause_type: str,
        category: str,
        requirements: Optional[str] = None
    ) -> str:
        """
        Generate an insurance clause.

        Args:
            clause_type: Type of clause (e.g., "Cyber Liability", "War Risks")
            category: Category (e.g., "Time Charter Party", "Environmental")
            requirements: Additional requirements

        Returns:
            Generated clause text
        """
        prompt = f"Generate an insurance clause for: {clause_type} (Category: {category})"
        if requirements:
            prompt += f"\n\nAdditional requirements: {requirements}"

        return self.generate(prompt)

    def generate_policy(
        self,
        policy_type: str,
        coverage_requirements: str,
        insured_info: Optional[str] = None
    ) -> str:
        """
        Generate a policy document.

        Args:
            policy_type: Type of policy
            coverage_requirements: Coverage requirements
            insured_info: Information about the insured

        Returns:
            Generated policy text
        """
        prompt = f"Generate a {policy_type} policy document.\n\nCoverage Requirements:\n{coverage_requirements}"
        if insured_info:
            prompt += f"\n\nInsured Information:\n{insured_info}"

        config = GenerationConfig(max_new_tokens=2048)  # Longer for policies
        return self.generate(prompt, config=config)


# Model Registry
@lru_cache(maxsize=2)
def get_model(model_type: str, model_path: Optional[str] = None) -> InsuranceModel:
    """
    Get a cached model instance.

    Args:
        model_type: "chat" or "docgen"
        model_path: Optional path to model (auto-detects latest if not provided)

    Returns:
        Loaded model instance
    """
    base_dir = Path(__file__).parent

    if model_path is None:
        # Find latest model
        models_dir = base_dir / "models"
        if models_dir.exists():
            matching = sorted(
                [d for d in models_dir.iterdir() if d.is_dir() and model_type in d.name],
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            if matching:
                model_path = str(matching[0] / "merged_model")
                if not Path(model_path).exists():
                    model_path = str(matching[0] / "lora_adapter")

    if model_path is None:
        raise ValueError(f"No {model_type} model found. Please train first or provide --model-path")

    if model_type == "chat":
        model = InsuranceChatModel(model_path)
    else:
        model = DocumentGenModel(model_path)

    model.load()
    return model


# FastAPI Server
def create_app():
    """Create FastAPI application for serving models."""
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from pydantic import BaseModel
        from fastapi.responses import StreamingResponse
    except ImportError:
        logger.error("FastAPI not installed. Run: pip install fastapi uvicorn")
        return None

    app = FastAPI(
        title="Insurance AI API",
        description="Fine-tuned models for insurance Q&A and document generation",
        version="1.0.0"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class ChatRequest(BaseModel):
        question: str
        context: Optional[str] = None
        stream: bool = False
        temperature: float = 0.7
        max_tokens: int = 1024

    class ChatResponse(BaseModel):
        answer: str
        model: str = "insurance-chat"

    class DocGenRequest(BaseModel):
        clause_type: str
        category: str
        requirements: Optional[str] = None
        temperature: float = 0.7
        max_tokens: int = 1024

    class DocGenResponse(BaseModel):
        clause: str
        model: str = "insurance-docgen"

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.post("/v1/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        try:
            model = get_model("chat")
            config = GenerationConfig(
                temperature=request.temperature,
                max_new_tokens=request.max_tokens
            )

            if request.stream:
                async def stream_response():
                    for token in model.generate_stream(
                        request.question,
                        config=config
                    ):
                        yield f"data: {json.dumps({'token': token})}\n\n"
                    yield "data: [DONE]\n\n"

                return StreamingResponse(
                    stream_response(),
                    media_type="text/event-stream"
                )

            answer = model.answer(request.question, request.context)
            return ChatResponse(answer=answer)

        except Exception as e:
            logger.exception("Chat error")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/v1/generate-clause", response_model=DocGenResponse)
    async def generate_clause(request: DocGenRequest):
        try:
            model = get_model("docgen")
            config = GenerationConfig(
                temperature=request.temperature,
                max_new_tokens=request.max_tokens
            )

            clause = model.generate_clause(
                request.clause_type,
                request.category,
                request.requirements
            )
            return DocGenResponse(clause=clause)

        except Exception as e:
            logger.exception("DocGen error")
            raise HTTPException(status_code=500, detail=str(e))

    return app


def interactive_chat(model: InsuranceModel):
    """Run interactive chat session."""
    print("\n" + "="*60)
    print("Insurance AI Chat")
    print("="*60)
    print("Type 'quit' to exit, 'clear' to reset history")
    print("="*60 + "\n")

    history = []

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() == 'quit':
                print("Goodbye!")
                break

            if user_input.lower() == 'clear':
                history = []
                print("History cleared.\n")
                continue

            # Generate response
            print("Assistant: ", end="", flush=True)

            response = ""
            for token in model.generate_stream(user_input, history=history):
                print(token, end="", flush=True)
                response += token

            print("\n")

            # Update history
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})

            # Keep history manageable
            if len(history) > 10:
                history = history[-10:]

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


def main():
    parser = argparse.ArgumentParser(description="Insurance AI Inference")
    parser.add_argument(
        "--model",
        choices=["chat", "docgen"],
        default="chat",
        help="Model type to use"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default=None,
        help="Path to model directory"
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Single prompt to process"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run interactive chat session"
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start API server"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="API server port"
    )
    parser.add_argument(
        "--no-4bit",
        action="store_true",
        help="Disable 4-bit quantization"
    )

    args = parser.parse_args()

    if args.serve:
        # Start API server
        app = create_app()
        if app:
            import uvicorn
            logger.info(f"Starting API server on port {args.port}")
            uvicorn.run(app, host="0.0.0.0", port=args.port)
        return

    # Load model
    try:
        model = get_model(args.model, args.model_path)
    except ValueError as e:
        logger.error(str(e))
        logger.info("Available options:")
        logger.info("  1. Train a model first: python train_insurance_model.py --model chat")
        logger.info("  2. Specify model path: python inference.py --model-path /path/to/model")
        sys.exit(1)

    if args.interactive:
        interactive_chat(model)
    elif args.prompt:
        response = model.generate(args.prompt)
        print(response)
    else:
        # Default to interactive
        interactive_chat(model)


if __name__ == "__main__":
    main()
