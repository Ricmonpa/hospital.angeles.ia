"""Hospital Ángeles IA — Agente Contable core (Gemini + persona)."""

from .gemini_client import (
    create_agent,
    create_chat,
    ensure_gemini_configured,
    load_soul,
    GeminiModel,
)

__all__ = [
    "create_agent",
    "create_chat",
    "ensure_gemini_configured",
    "load_soul",
    "GeminiModel",
]
