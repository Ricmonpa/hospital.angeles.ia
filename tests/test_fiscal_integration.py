"""Integration Test: CFDI Parser → Gemini Fiscal Classifier.

This test makes REAL API calls to Gemini. Run with:
    docker compose run --rm opendoc python -m pytest tests/test_fiscal_integration.py -v -s

Requires: GOOGLE_API_KEY in .env
"""

import os
import pytest

import google.generativeai as genai
from pathlib import Path

from src.tools.cfdi_parser import parse_cfdi
from src.tools.fiscal_classifier import (
    classify_cfdi,
    full_cfdi_analysis,
    ClasificacionFiscal,
)
from src.core.gemini_client import GeminiModel


REAL_XML = Path(__file__).parent.parent / "data" / "templates" / "MOPR881228EF9FF22.xml"


@pytest.fixture(autouse=True)
def configure_api():
    """Configure Gemini API key from environment."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        pytest.skip("GOOGLE_API_KEY not set — skipping integration test")
    genai.configure(api_key=api_key)


@pytest.fixture
def real_cfdi():
    return parse_cfdi(REAL_XML)


class TestFiscalIntegration:
    """End-to-end: Real XML → Parser → Gemini → Fiscal Classification."""

    def test_classify_as_ingreso(self, real_cfdi):
        """Doctor is the EMISOR → Gemini should classify as income."""
        result = classify_cfdi(
            real_cfdi,
            doctor_rfc="MOPR881228EF9",
            model=GeminiModel.FLASH,
        )

        print("\n" + "=" * 60)
        print("CLASIFICACIÓN FISCAL (Doctor = Emisor → Ingreso)")
        print("=" * 60)
        print(result.resumen_whatsapp())
        print(f"\nConfianza: {result.confianza}")
        print(f"Raw fundamento: {result.fundamento_legal}")
        print("=" * 60)

        # The doctor is the emisor of this CFDI, so it's income
        assert result.deducibilidad is not None
        assert result.categoria_fiscal is not None
        assert result.confianza > 0.5
        assert result.resumen_doctor != ""

    def test_classify_as_gasto(self, real_cfdi):
        """Doctor is the RECEPTOR → Gemini should classify as expense."""
        result = classify_cfdi(
            real_cfdi,
            doctor_rfc="IIC200908QY6",
            model=GeminiModel.FLASH,
        )

        print("\n" + "=" * 60)
        print("CLASIFICACIÓN FISCAL (Doctor = Receptor → Gasto)")
        print("=" * 60)
        print(result.resumen_whatsapp())
        print(f"\nConfianza: {result.confianza}")
        print("=" * 60)

        assert result.deducibilidad is not None
        assert result.confianza > 0.5

    def test_full_analysis_output(self, real_cfdi):
        """Test the complete formatted analysis output."""
        output = full_cfdi_analysis(
            real_cfdi,
            doctor_rfc="MOPR881228EF9",
            model=GeminiModel.FLASH,
        )

        print("\n" + "=" * 60)
        print("ANÁLISIS COMPLETO")
        print("=" * 60)
        print(output)
        print("=" * 60)

        # Should contain both sections
        assert "CFDI 3.3" in output
        assert "ANÁLISIS FISCAL" in output
        assert "RICARDO MONCADA" in output
