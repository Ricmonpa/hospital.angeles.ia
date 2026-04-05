"""Tests for receipt_vision_analyzer.

Unit tests (no API calls) + integration test (requires GOOGLE_API_KEY).
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.tools.receipt_vision_analyzer import (
    ReceiptData,
    _parse_response,
    _encode_image,
    analyze_receipt,
    EXTRACTION_PROMPT,
)


# --------------- Sample data ---------------

SAMPLE_JSON = json.dumps({
    "fecha": "2025-03-15",
    "rfc_emisor": "XAXX010101000",
    "rfc_receptor": "GARJ850101HDF",
    "razon_social_emisor": "Distribuidora Médica del Norte SA de CV",
    "concepto": "Guantes de nitrilo caja x100",
    "subtotal": 862.07,
    "iva": 137.93,
    "total": 1000.00,
    "moneda": "MXN",
    "metodo_pago": "PUE",
    "uso_cfdi": "G03",
    "folio_fiscal": "A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
    "tipo_comprobante": "Ingreso",
    "deducible": True,
    "categoria_fiscal": "Gastos Médicos",
    "notas": "Material indispensable para consultorio"
})


# --------------- Unit tests (no API) ---------------

class TestReceiptData:
    def test_create_receipt_data(self):
        r = ReceiptData(fecha="2025-03-15", total=1000.00, deducible=True)
        assert r.fecha == "2025-03-15"
        assert r.total == 1000.00
        assert r.moneda == "MXN"

    def test_summary_format(self):
        r = ReceiptData(
            fecha="2025-03-15",
            razon_social_emisor="Farmacia Central",
            total=500.00,
            moneda="MXN",
            categoria_fiscal="Gastos Médicos",
            deducible=True,
        )
        s = r.summary()
        assert "2025-03-15" in s
        assert "Farmacia Central" in s
        assert "$500.00" in s
        assert "Deducible" in s

    def test_summary_no_deducible(self):
        r = ReceiptData(
            fecha="2025-03-15",
            total=250.00,
            deducible=False,
            categoria_fiscal="No Deducible",
        )
        assert "No Deducible" in r.summary()

    def test_to_dict(self):
        r = ReceiptData(fecha="2025-01-01", total=100.0)
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["fecha"] == "2025-01-01"
        assert d["total"] == 100.0


class TestParseResponse:
    def test_parse_clean_json(self):
        result = _parse_response(SAMPLE_JSON)
        assert isinstance(result, ReceiptData)
        assert result.rfc_emisor == "XAXX010101000"
        assert result.total == 1000.00
        assert result.deducible is True
        assert result.categoria_fiscal == "Gastos Médicos"

    def test_parse_json_with_markdown_fences(self):
        wrapped = f"```json\n{SAMPLE_JSON}\n```"
        result = _parse_response(wrapped)
        assert result.total == 1000.00

    def test_parse_json_with_whitespace(self):
        padded = f"\n\n  {SAMPLE_JSON}  \n\n"
        result = _parse_response(padded)
        assert result.fecha == "2025-03-15"

    def test_parse_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_response("this is not json")


class TestEncodeImage:
    def test_encode_jpeg(self, tmp_path):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0fake jpeg data")
        result = _encode_image(img)
        assert result["mime_type"] == "image/jpeg"
        assert len(result["data"]) > 0

    def test_encode_png(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\nfake png data")
        result = _encode_image(img)
        assert result["mime_type"] == "image/png"

    def test_unsupported_format_raises(self, tmp_path):
        img = tmp_path / "test.bmp"
        img.write_bytes(b"fake bmp")
        with pytest.raises(ValueError, match="Unsupported"):
            _encode_image(img)


class TestAnalyzeReceipt:
    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            analyze_receipt("/nonexistent/path/receipt.jpg")


class TestExtractionPrompt:
    def test_prompt_contains_lisr_rules(self):
        assert "LISR" in EXTRACTION_PROMPT
        assert "Deducible" in EXTRACTION_PROMPT

    def test_prompt_requests_json(self):
        assert "JSON" in EXTRACTION_PROMPT

    def test_prompt_covers_all_fields(self):
        fields = [
            "fecha", "rfc_emisor", "rfc_receptor", "concepto",
            "subtotal", "iva", "total", "folio_fiscal",
            "deducible", "categoria_fiscal",
        ]
        for field in fields:
            assert field in EXTRACTION_PROMPT, f"Field '{field}' missing from prompt"
