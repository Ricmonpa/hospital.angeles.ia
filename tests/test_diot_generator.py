"""Tests for OpenDoc DIOT Generator.

Comprehensive tests for:
- Operation creation from CFDI data
- IVA treatment detection (16%, 8%, 0%, exempt)
- Grouping operations by RFC
- DIOT report generation
- TXT layout generation (SAT upload format)
- Edge cases (foreign suppliers, generic RFC, empty data)
- WhatsApp formatting
"""

import pytest
from src.tools.diot_generator import (
    # Core functions
    generate_diot,
    group_operations_by_rfc,
    create_operation_from_cfdi,
    _detect_iva_treatment,
    _clean_rfc,
    _format_diot_amount,
    # Data classes
    OperacionTercero,
    ResumenTercero,
    ReporteDIOT,
    TipoTercero,
)


# ══════════════════════════════════════════════════════════════════════
# TEST: IVA Treatment Detection
# ══════════════════════════════════════════════════════════════════════

class TestDetectIVATreatment:
    """Test automatic IVA rate detection."""

    def test_16_percent_iva(self):
        """Standard 16% IVA detection."""
        result = _detect_iva_treatment(10_000, 1_600, 11_600)
        assert result["iva_pagado_16"] == 1_600
        assert result["iva_pagado_8"] == 0
        assert result["monto_exento"] == 0

    def test_8_percent_iva_frontera(self):
        """8% frontera IVA detection."""
        result = _detect_iva_treatment(10_000, 800, 10_800)
        assert result["iva_pagado_8"] == 800
        assert result["iva_pagado_16"] == 0

    def test_exempt_no_iva(self):
        """Zero IVA on subtotal → exempt."""
        result = _detect_iva_treatment(10_000, 0, 10_000)
        assert result["monto_exento"] == 10_000
        assert result["iva_pagado_16"] == 0

    def test_zero_subtotal(self):
        result = _detect_iva_treatment(0, 0, 0)
        assert result["monto_exento"] == 0
        assert result["iva_pagado_16"] == 0

    def test_positive_iva_with_zero_subtotal(self):
        """Edge case: IVA but no subtotal."""
        result = _detect_iva_treatment(0, 100, 100)
        assert result["iva_pagado_16"] == 100  # Default to 16% if IVA > 0


# ══════════════════════════════════════════════════════════════════════
# TEST: Create Operation from CFDI
# ══════════════════════════════════════════════════════════════════════

class TestCreateOperationFromCFDI:
    """Test CFDI-to-DIOT operation conversion."""

    def test_basic_16_percent(self):
        op = create_operation_from_cfdi(
            rfc_emisor="ABC123456789",
            nombre_emisor="Inmobiliaria X",
            subtotal=10_000,
            iva=1_600,
            total=11_600,
        )
        assert op.rfc_tercero == "ABC123456789"
        assert op.iva_pagado_16 == 1_600
        assert op.monto_operacion == 10_000

    def test_exempt_operation(self):
        op = create_operation_from_cfdi(
            rfc_emisor="MED987654321",
            nombre_emisor="Laboratorio Médico",
            subtotal=5_000,
            iva=0,
            total=5_000,
        )
        assert op.monto_exento == 5_000
        assert op.iva_pagado_16 == 0

    def test_foreign_supplier(self):
        op = create_operation_from_cfdi(
            rfc_emisor="XEXX010101000",
            nombre_emisor="Google Cloud",
            subtotal=500,
            iva=80,
            total=580,
        )
        assert op.tipo_tercero == TipoTercero.PROVEEDOR_EXTRANJERO.value

    def test_uuid_and_date(self):
        op = create_operation_from_cfdi(
            rfc_emisor="AAA123456789",
            nombre_emisor="Test",
            subtotal=1000,
            iva=160,
            total=1160,
            uuid="12345-ABCDE",
            fecha="2026-01-15",
        )
        assert op.uuid == "12345-ABCDE"
        assert op.fecha == "2026-01-15"

    def test_with_iva_retenido(self):
        op = create_operation_from_cfdi(
            rfc_emisor="AAA123456789",
            nombre_emisor="Test",
            subtotal=10_000,
            iva=1_600,
            total=11_600,
            iva_retenido=500,
        )
        assert op.iva_retenido == 500

    def test_rfc_normalization(self):
        op = create_operation_from_cfdi(
            rfc_emisor="  abc123456789  ",
            nombre_emisor="Test",
            subtotal=1000,
            iva=160,
            total=1160,
        )
        assert op.rfc_tercero == "ABC123456789"


# ══════════════════════════════════════════════════════════════════════
# TEST: OperacionTercero Properties
# ══════════════════════════════════════════════════════════════════════

class TestOperacionTercero:
    """Test operation data class properties."""

    def test_total_operacion(self):
        op = OperacionTercero(
            rfc_tercero="ABC", monto_operacion=10_000,
            iva_pagado_16=1_600,
        )
        assert op.total_operacion == 11_600

    def test_iva_total(self):
        op = OperacionTercero(
            rfc_tercero="ABC", monto_operacion=10_000,
            iva_pagado_16=1_000, iva_pagado_8=400,
        )
        assert op.iva_total == 1_400


# ══════════════════════════════════════════════════════════════════════
# TEST: Group Operations by RFC
# ══════════════════════════════════════════════════════════════════════

class TestGroupByRFC:
    """Test grouping logic."""

    def test_single_supplier(self):
        ops = [
            OperacionTercero(rfc_tercero="AAA111", nombre_tercero="Supplier A",
                             monto_operacion=5_000, iva_pagado_16=800),
            OperacionTercero(rfc_tercero="AAA111", nombre_tercero="Supplier A",
                             monto_operacion=3_000, iva_pagado_16=480),
        ]
        result = group_operations_by_rfc(ops)
        assert len(result) == 1
        assert result[0].rfc == "AAA111"
        assert result[0].num_operaciones == 2
        assert result[0].iva_pagado_16 == 1_280
        assert result[0].valor_actos_16 == 8_000

    def test_multiple_suppliers(self):
        ops = [
            OperacionTercero(rfc_tercero="AAA111", monto_operacion=5_000, iva_pagado_16=800),
            OperacionTercero(rfc_tercero="BBB222", monto_operacion=3_000, iva_pagado_16=480),
            OperacionTercero(rfc_tercero="CCC333", monto_operacion=2_000, monto_exento=2_000),
        ]
        result = group_operations_by_rfc(ops)
        assert len(result) == 3

    def test_rfc_case_insensitive(self):
        ops = [
            OperacionTercero(rfc_tercero="aaa111", monto_operacion=5_000, iva_pagado_16=800),
            OperacionTercero(rfc_tercero="AAA111", monto_operacion=3_000, iva_pagado_16=480),
        ]
        result = group_operations_by_rfc(ops)
        assert len(result) == 1
        assert result[0].num_operaciones == 2

    def test_empty_operations(self):
        result = group_operations_by_rfc([])
        assert len(result) == 0

    def test_exempt_operations_grouped(self):
        ops = [
            OperacionTercero(rfc_tercero="MED111", monto_operacion=5_000, monto_exento=5_000),
            OperacionTercero(rfc_tercero="MED111", monto_operacion=3_000, monto_exento=3_000),
        ]
        result = group_operations_by_rfc(ops)
        assert result[0].valor_actos_exentos == 8_000

    def test_mixed_iva_same_supplier(self):
        """Same supplier with 16% and exempt operations."""
        ops = [
            OperacionTercero(rfc_tercero="MIX111", monto_operacion=5_000, iva_pagado_16=800),
            OperacionTercero(rfc_tercero="MIX111", monto_operacion=3_000, monto_exento=3_000),
        ]
        result = group_operations_by_rfc(ops)
        assert result[0].valor_actos_16 == 5_000
        assert result[0].valor_actos_exentos == 3_000
        assert result[0].iva_pagado_16 == 800

    def test_tasa_cero_operations(self):
        ops = [
            OperacionTercero(rfc_tercero="FAR111", monto_operacion=2_000, monto_tasa_cero=2_000),
        ]
        result = group_operations_by_rfc(ops)
        assert result[0].valor_actos_tasa_cero == 2_000

    def test_resumen_properties(self):
        ops = [
            OperacionTercero(rfc_tercero="AAA111", monto_operacion=10_000,
                             iva_pagado_16=1_600, iva_retenido=500),
        ]
        result = group_operations_by_rfc(ops)
        assert result[0].total_iva_pagado == 1_600
        assert result[0].total_valor_actos == 10_000
        assert result[0].iva_retenido == 500


# ══════════════════════════════════════════════════════════════════════
# TEST: Generate DIOT Report
# ══════════════════════════════════════════════════════════════════════

class TestGenerateDIOT:
    """Test complete DIOT report generation."""

    def _sample_operations(self):
        return [
            OperacionTercero(rfc_tercero="INM850101ABC",
                             nombre_tercero="Inmobiliaria Centro",
                             monto_operacion=8_000, iva_pagado_16=1_280),
            OperacionTercero(rfc_tercero="CFE370814QI0",
                             nombre_tercero="CFE",
                             monto_operacion=1_500, iva_pagado_16=240),
            OperacionTercero(rfc_tercero="TEL940901AAA",
                             nombre_tercero="Telmex",
                             monto_operacion=800, iva_pagado_16=128),
            OperacionTercero(rfc_tercero="FAR201015BBB",
                             nombre_tercero="Farmacia RPBI",
                             monto_operacion=3_000, monto_tasa_cero=3_000),
        ]

    def test_basic_report(self):
        ops = self._sample_operations()
        report = generate_diot(
            mes=1, anio=2026,
            rfc_declarante="MOPR881228EF9",
            operaciones=ops,
        )
        assert report.mes == 1
        assert report.anio == 2026
        assert report.rfc_declarante == "MOPR881228EF9"
        assert report.total_terceros == 4
        assert report.total_operaciones == 4

    def test_iva_totals(self):
        ops = self._sample_operations()
        report = generate_diot(
            mes=1, anio=2026,
            rfc_declarante="MOPR881228EF9",
            operaciones=ops,
        )
        assert report.total_iva_16 == 1_280 + 240 + 128  # 1,648
        assert report.total_iva_tasa_cero == 3_000

    def test_resico_alert(self):
        """RESICO should get alert about DIOT exemption."""
        ops = self._sample_operations()
        report = generate_diot(
            mes=1, anio=2026,
            rfc_declarante="MOPR881228EF9",
            operaciones=ops,
            regimen="625",
        )
        assert any("RESICO" in a for a in report.alertas)

    def test_empty_operations(self):
        report = generate_diot(
            mes=1, anio=2026,
            rfc_declarante="MOPR881228EF9",
            operaciones=[],
        )
        assert report.total_terceros == 0
        assert any("Sin operaciones" in n for n in report.notas)

    def test_generic_rfc_alert(self):
        """Alert when generic RFC (público en general) is used."""
        ops = [
            OperacionTercero(rfc_tercero="XAXX010101000",
                             monto_operacion=5_000, iva_pagado_16=800),
        ]
        report = generate_diot(
            mes=1, anio=2026,
            rfc_declarante="MOPR881228EF9",
            operaciones=ops,
        )
        assert any("genérico" in a for a in report.alertas)

    def test_foreign_supplier_detection(self):
        """Foreign supplier RFC detection and type change."""
        ops = [
            OperacionTercero(rfc_tercero="XEXX010101000",
                             nombre_tercero="Google Cloud",
                             monto_operacion=500, iva_pagado_16=80),
        ]
        report = generate_diot(
            mes=1, anio=2026,
            rfc_declarante="MOPR881228EF9",
            operaciones=ops,
        )
        assert any("extranjero" in n.lower() for n in report.notas)

    def test_medical_iva_note(self):
        """Should always remind about non-creditable IVA."""
        report = generate_diot(
            mes=1, anio=2026,
            rfc_declarante="MOPR881228EF9",
            operaciones=[],
        )
        assert any("no es acreditable" in n.lower() or "NO es acreditable" in n for n in report.notas)

    def test_to_dict(self):
        ops = self._sample_operations()
        report = generate_diot(
            mes=1, anio=2026,
            rfc_declarante="MOPR881228EF9",
            operaciones=ops,
        )
        d = report.to_dict()
        assert isinstance(d, dict)
        assert d["mes"] == 1
        assert "terceros" in d


# ══════════════════════════════════════════════════════════════════════
# TEST: TXT Layout (SAT Upload)
# ══════════════════════════════════════════════════════════════════════

class TestTXTLayout:
    """Test pipe-delimited TXT generation for SAT."""

    def test_basic_layout(self):
        ops = [
            OperacionTercero(rfc_tercero="INM850101ABC",
                             monto_operacion=10_000, iva_pagado_16=1_600),
        ]
        report = generate_diot(
            mes=1, anio=2026,
            rfc_declarante="MOPR881228EF9",
            operaciones=ops,
        )
        txt = report.generate_txt_layout()
        assert "|" in txt
        assert "INM850101ABC" in txt

    def test_pipe_delimited_format(self):
        ops = [
            OperacionTercero(rfc_tercero="AAA111222333",
                             monto_operacion=5_000, iva_pagado_16=800),
        ]
        report = generate_diot(
            mes=1, anio=2026,
            rfc_declarante="MOPR881228EF9",
            operaciones=ops,
        )
        txt = report.generate_txt_layout()
        parts = txt.strip().split("|")
        assert parts[0] == TipoTercero.PROVEEDOR_NACIONAL.value
        assert parts[1] == "AAA111222333"

    def test_multiple_suppliers_layout(self):
        ops = [
            OperacionTercero(rfc_tercero="AAA111", monto_operacion=5_000, iva_pagado_16=800),
            OperacionTercero(rfc_tercero="BBB222", monto_operacion=3_000, monto_exento=3_000),
        ]
        report = generate_diot(
            mes=1, anio=2026,
            rfc_declarante="MOPR881228EF9",
            operaciones=ops,
        )
        txt = report.generate_txt_layout()
        lines = txt.strip().split("\n")
        assert len(lines) == 2

    def test_empty_report_txt(self):
        report = generate_diot(
            mes=1, anio=2026,
            rfc_declarante="MOPR881228EF9",
            operaciones=[],
        )
        txt = report.generate_txt_layout()
        assert txt == ""


# ══════════════════════════════════════════════════════════════════════
# TEST: WhatsApp Formatting
# ══════════════════════════════════════════════════════════════════════

class TestWhatsAppFormatting:
    """Test DIOT WhatsApp summary."""

    def test_basic_formatting(self):
        ops = [
            OperacionTercero(rfc_tercero="INM850101ABC",
                             nombre_tercero="Inmobiliaria",
                             monto_operacion=10_000, iva_pagado_16=1_600),
        ]
        report = generate_diot(
            mes=1, anio=2026,
            rfc_declarante="MOPR881228EF9",
            operaciones=ops,
        )
        text = report.resumen_whatsapp()
        assert "DIOT" in text
        assert "ENERO" in text
        assert "Proveedores: 1" in text
        assert "IVA 16%" in text

    def test_top_suppliers_shown(self):
        ops = [
            OperacionTercero(rfc_tercero=f"SUP{i:09d}",
                             nombre_tercero=f"Proveedor {i}",
                             monto_operacion=1_000 * i, iva_pagado_16=160 * i)
            for i in range(1, 8)
        ]
        report = generate_diot(
            mes=6, anio=2026,
            rfc_declarante="MOPR881228EF9",
            operaciones=ops,
        )
        text = report.resumen_whatsapp()
        assert "TOP PROVEEDORES" in text
        assert "Proveedor 7" in text  # Should be first (highest value)

    def test_alerts_in_whatsapp(self):
        ops = [
            OperacionTercero(rfc_tercero="XAXX010101000",
                             monto_operacion=5_000, iva_pagado_16=800),
        ]
        report = generate_diot(
            mes=1, anio=2026,
            rfc_declarante="MOPR881228EF9",
            operaciones=ops,
        )
        text = report.resumen_whatsapp()
        assert "🚨" in text


# ══════════════════════════════════════════════════════════════════════
# TEST: Helper Functions
# ══════════════════════════════════════════════════════════════════════

class TestHelpers:
    """Test utility functions."""

    def test_clean_rfc_uppercase(self):
        assert _clean_rfc("abc123") == "ABC123"

    def test_clean_rfc_strips_whitespace(self):
        assert _clean_rfc("  ABC123  ") == "ABC123"

    def test_clean_rfc_empty(self):
        assert _clean_rfc("") == "XAXX010101000"  # Generic RFC

    def test_clean_rfc_none(self):
        assert _clean_rfc(None) == "XAXX010101000"

    def test_format_diot_amount_integer(self):
        assert _format_diot_amount(1600.50) == "1600"

    def test_format_diot_amount_zero(self):
        assert _format_diot_amount(0) == ""

    def test_format_diot_amount_round_up(self):
        assert _format_diot_amount(1600.6) == "1601"


# ══════════════════════════════════════════════════════════════════════
# TEST: Enums
# ══════════════════════════════════════════════════════════════════════

class TestEnums:
    """Test DIOT enums."""

    def test_tipo_tercero_values(self):
        assert TipoTercero.PROVEEDOR_NACIONAL.value == "04"
        assert TipoTercero.PROVEEDOR_EXTRANJERO.value == "05"
        assert TipoTercero.PROVEEDOR_GLOBAL.value == "15"


# ══════════════════════════════════════════════════════════════════════
# TEST: Module Exports
# ══════════════════════════════════════════════════════════════════════

class TestModuleExports:
    """Test imports from __init__."""

    def test_import_functions(self):
        from src.tools import (
            generate_diot,
            group_operations_by_rfc,
            create_operation_from_cfdi,
        )

    def test_import_classes(self):
        from src.tools import (
            OperacionTercero,
            ResumenTercero,
            ReporteDIOT,
            TipoTercero,
        )
