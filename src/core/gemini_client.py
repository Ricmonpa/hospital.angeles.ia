"""Gemini client for Hospital Ángeles IA — Agente Contable persona."""

import os
from pathlib import Path
from enum import Enum

import google.generativeai as genai


class GeminiModel(str, Enum):
    """Available Gemini models with their use cases."""
    PRO = "gemini-2.5-pro"        # Complex reasoning, legal analysis, medical context
    FLASH = "gemini-2.0-flash"    # Routing, quick extraction, simple Q&A


# Default paths
SOUL_PATH = Path(__file__).parent.parent.parent / "data" / "prompts" / "SOUL.md"


def ensure_gemini_configured() -> None:
    """Configure google-generativeai with API key from environment.

    Accepts `GEMINI_API_KEY` (Flask app) or `GOOGLE_API_KEY` (legacy).
    """
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError(
            "Falta GEMINI_API_KEY o GOOGLE_API_KEY en el entorno para el Agente Contable."
        )
    genai.configure(api_key=key)


def load_soul(path: Path = SOUL_PATH) -> str:
    """Load the SOUL.md system prompt."""
    if not path.exists():
        raise FileNotFoundError(f"SOUL.md not found at {path}")
    return path.read_text(encoding="utf-8")


def create_agent(
    model: GeminiModel = GeminiModel.FLASH,
    soul_path: Path = SOUL_PATH,
) -> genai.GenerativeModel:
    """Create a Gemini model with the Agente Contable system instruction."""
    ensure_gemini_configured()
    soul = load_soul(soul_path)

    return genai.GenerativeModel(
        model_name=model.value,
        system_instruction=soul,
        generation_config=genai.GenerationConfig(
            temperature=0.3,       # Low creativity — precision over flair
            top_p=0.95,
            max_output_tokens=2048,
        ),
        safety_settings={
            "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
            "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
            "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
        },
    )


def create_chat(
    model: GeminiModel = GeminiModel.FLASH,
    history: list | None = None,
):
    """Start a chat session with the Agente Contable persona."""
    agent = create_agent(model=model)
    return agent.start_chat(history=history or [])
