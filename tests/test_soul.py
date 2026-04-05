"""Tests for SOUL.md loading and Gemini persona verification."""

from pathlib import Path

from src.core.gemini_client import load_soul, SOUL_PATH


def test_soul_file_exists():
    """SOUL.md must exist in data/prompts/."""
    assert SOUL_PATH.exists(), f"SOUL.md not found at {SOUL_PATH}"


def test_soul_is_not_empty():
    """SOUL.md must have content."""
    soul = load_soul()
    assert len(soul) > 100, "SOUL.md is too short"


def test_soul_contains_identity():
    """SOUL.md must define the Agente Contable identity."""
    soul = load_soul()
    assert "Agente Contable" in soul
    assert "Hospital Ángeles" in soul
    assert "IDENTITY" in soul


def test_soul_contains_prime_directives():
    """SOUL.md must contain all 4 Iron Rules."""
    soul = load_soul()
    assert "COFEPRIS" in soul
    assert "LISR" in soul
    assert "NOM-004" in soul
    assert "Requiere validación médica humana" in soul


def test_soul_contains_tools():
    """SOUL.md must reference all agent tools."""
    soul = load_soul()
    tools = [
        "sat_portal_navigator",
        "prescription_generator",
        "receipt_vision_analyzer",
        "patient_history_context",
        "watchdog_service",
    ]
    for tool in tools:
        assert tool in soul, f"Tool '{tool}' not found in SOUL.md"


def test_soul_enforces_spanish():
    """SOUL.md must specify Spanish interaction."""
    soul = load_soul()
    assert "Spanish" in soul or "Español" in soul
