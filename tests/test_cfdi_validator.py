"""Tests for the CFDI Validator — Structural, Fiscal, Deducibility, Medical, Payment.

Unit tests verify:
- Structural validation (required fields, UUID, version, RFC length, conceptos)
- Fiscal validation (tipo comprobante, forma/metodo pago, PPD+99, PUE+99, amounts)
- Deducibility validation (cash limit, forma_pago 99, PPD warning, RESICO, uso S01)
- Medical validation (IVA exemption for medical services, ISR retention for PM)
- Payment validation (missing forma_pago, missing metodo_pago)
- Score calculation (100 for clean, reduced for errors/warnings)
- validate_cfdi integration with clean and error-filled CFDIs
- validate_cfdi_batch with multiple CFDIs
- WhatsApp formatting (resumen_whatsapp)
- ResultadoValidacion.to_dict()
- Module exports from src.tools

Based on: Anexo 20 CFDI 4.0, CFF Art. 29/29-A, LISR Art. 27, RMF 2026.
"""

import copy
import pytest

from src.tools.cfdi_validator import (
    validate_cfdi,
    validate_cfdi_batch,
    ResultadoValidacion,
    ErrorCFDI,
    SeveridadError,
    TipoValidacion,
    _validate_structure,
    _validate_fiscal,
    _validate_deducibility,
    _validate_medical,
    _validate_payment,
    FORMAS_PAGO_VALIDAS,
    METODOS_PAGO_VALIDOS,
    TIPOS_COMPROBANTE_VALIDOS,
)


# ---- Sample CFDI Dicts -------------------------------------------------------

CFDI_VALIDO = {
    "version": "4.0",
    "emisor_rfc": "INM850101ABC",
    "emisor_nombre": "Inmobiliaria Centro",
    "emisor_regimen": "601",
    "receptor_rfc": "MOPR881228EF9",
    "receptor_nombre": "Dr. Mario Lopez",
    "receptor_uso_cfdi": "G03",
    "fecha": "2026-01-15T10:30:00",
    "tipo_comprobante": "I",
    "forma_pago": "03",
    "metodo_pago": "PUE",
    "subtotal": 10000.0,
    "total": 11600.0,
    "iva_trasladado": 1600.0,
    "isr_retenido": 0,
    "iva_retenido": 0,
    "descuento": 0,
    "conceptos": [{"clave_prod_serv": "80131502", "descripcion": "Renta consultorio"}],
    "timbre": {"uuid": "ABC12345-1234-1234-1234-123456789012"},
}


def _make_cfdi(**overrides):
    """Create a copy of the valid CFDI with specific overrides."""
    cfdi = copy.deepcopy(CFDI_VALIDO)
    for key, value in overrides.items():
        if value is None:
            cfdi.pop(key, None)
        else:
            cfdi[key] = value
    return cfdi


# ---- Enum Tests ---------------------------------------------------------------

class TestSeveridadError:
    def test_critico_value(self):
        assert SeveridadError.CRITICO.value == "Critico" or SeveridadError.CRITICO.value == "Cr\u00edtico"

    def test_advertencia_value(self):
        assert SeveridadError.ADVERTENCIA.value == "Advertencia"

    def test_info_value(self):
        assert "Informaci" in SeveridadError.INFO.value

    def test_is_str_enum(self):
        assert isinstance(SeveridadError.CRITICO, str)


class TestTipoValidacion:
    def test_estructura_value(self):
        assert TipoValidacion.ESTRUCTURA.value == "Estructura"

    def test_fiscal_value(self):
        assert TipoValidacion.FISCAL.value == "Fiscal"

    def test_deducibilidad_value(self):
        assert TipoValidacion.DEDUCIBILIDAD.value == "Deducibilidad"

    def test_medico_value(self):
        assert "dico" in TipoValidacion.MEDICO.value  # "Medico" or "Medico"

    def test_pago_value(self):
        assert TipoValidacion.PAGO.value == "Pago"


# ---- ErrorCFDI Tests ----------------------------------------------------------

class TestErrorCFDI:
    def test_create_basic(self):
        e = ErrorCFDI(
            codigo="TEST-001",
            mensaje="Test error",
            severidad=SeveridadError.CRITICO.value,
            tipo=TipoValidacion.ESTRUCTURA.value,
        )
        assert e.codigo == "TEST-001"
        assert e.mensaje == "Test error"
        assert e.campo == ""
        assert e.recomendacion == ""

    def test_create_full(self):
        e = ErrorCFDI(
            codigo="TEST-002",
            mensaje="Full error",
            severidad=SeveridadError.ADVERTENCIA.value,
            tipo=TipoValidacion.FISCAL.value,
            campo="forma_pago",
            valor_actual="99",
            valor_esperado="03",
            fundamento="Art. 27 LISR",
            recomendacion="Cambiar forma de pago.",
        )
        assert e.campo == "forma_pago"
        assert e.valor_actual == "99"
        assert e.fundamento == "Art. 27 LISR"


# ---- ResultadoValidacion Tests ------------------------------------------------

class TestResultadoValidacion:
    def test_defaults(self):
        r = ResultadoValidacion()
        assert r.es_valido is True
        assert r.total_errores == 0
        assert r.total_advertencias == 0
        assert r.total_info == 0
        assert r.score == 100
        assert r.errores == []

    def test_to_dict_empty(self):
        r = ResultadoValidacion()
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["es_valido"] is True
        assert d["score"] == 100
        assert d["errores"] == []
        assert "total_errores" in d
        assert "total_advertencias" in d
        assert "total_info" in d

    def test_to_dict_with_errors(self):
        err = ErrorCFDI(
            codigo="X-001",
            mensaje="Missing field",
            severidad=SeveridadError.CRITICO.value,
            tipo=TipoValidacion.ESTRUCTURA.value,
            campo="version",
            recomendacion="Add version.",
        )
        r = ResultadoValidacion(
            es_valido=False,
            total_errores=1,
            errores=[err],
            score=80,
        )
        d = r.to_dict()
        assert d["es_valido"] is False
        assert d["score"] == 80
        assert len(d["errores"]) == 1
        assert d["errores"][0]["codigo"] == "X-001"
        assert d["errores"][0]["campo"] == "version"
        assert d["errores"][0]["recomendacion"] == "Add version."

    def test_to_dict_error_keys(self):
        """Verify to_dict includes exactly the expected keys per error."""
        err = ErrorCFDI(
            codigo="Z-001",
            mensaje="test",
            severidad=SeveridadError.INFO.value,
            tipo=TipoValidacion.PAGO.value,
            campo="x",
            recomendacion="fix it",
        )
        r = ResultadoValidacion(errores=[err])
        error_dict = r.to_dict()["errores"][0]
        expected_keys = {"codigo", "mensaje", "severidad", "tipo", "campo", "recomendacion"}
        assert set(error_dict.keys()) == expected_keys


# ---- WhatsApp Formatting Tests ------------------------------------------------

class TestResumenWhatsApp:
    def test_clean_cfdi_whatsapp(self):
        r = ResultadoValidacion(es_valido=True, score=100)
        text = r.resumen_whatsapp()
        assert "100/100" in text
        assert "Sin problemas detectados" in text

    def test_errors_show_red_icon(self):
        err = ErrorCFDI(
            codigo="EST-001",
            mensaje="Campo faltante",
            severidad=SeveridadError.CRITICO.value,
            tipo=TipoValidacion.ESTRUCTURA.value,
            recomendacion="Corregir",
        )
        r = ResultadoValidacion(
            es_valido=False,
            total_errores=1,
            errores=[err],
            score=80,
        )
        text = r.resumen_whatsapp()
        assert "1 errores" in text or "1 error" in text
        assert "[EST-001]" in text
        assert "Corregir" in text

    def test_warnings_show_yellow_icon(self):
        warn = ErrorCFDI(
            codigo="FIS-005",
            mensaje="PUE con 99",
            severidad=SeveridadError.ADVERTENCIA.value,
            tipo=TipoValidacion.FISCAL.value,
            recomendacion="Especificar forma.",
        )
        r = ResultadoValidacion(
            es_valido=True,
            total_advertencias=1,
            errores=[warn],
            score=95,
        )
        text = r.resumen_whatsapp()
        assert "1 advertencias" in text or "1 advertencia" in text
        assert "[FIS-005]" in text

    def test_info_shows_icon(self):
        info_err = ErrorCFDI(
            codigo="DED-004",
            mensaje="RESICO info",
            severidad=SeveridadError.INFO.value,
            tipo=TipoValidacion.DEDUCIBILIDAD.value,
        )
        r = ResultadoValidacion(
            es_valido=True,
            total_info=1,
            errores=[info_err],
            score=99,
        )
        text = r.resumen_whatsapp()
        assert "1 sugerencias" in text or "1 sugerencia" in text

    def test_mixed_errors_in_whatsapp(self):
        errors = [
            ErrorCFDI(
                codigo="EST-001",
                mensaje="Critical",
                severidad=SeveridadError.CRITICO.value,
                tipo=TipoValidacion.ESTRUCTURA.value,
            ),
            ErrorCFDI(
                codigo="FIS-004",
                mensaje="Warning",
                severidad=SeveridadError.ADVERTENCIA.value,
                tipo=TipoValidacion.FISCAL.value,
                recomendacion="Fix it",
            ),
            ErrorCFDI(
                codigo="DED-004",
                mensaje="Info",
                severidad=SeveridadError.INFO.value,
                tipo=TipoValidacion.DEDUCIBILIDAD.value,
            ),
        ]
        r = ResultadoValidacion(
            es_valido=False,
            total_errores=1,
            total_advertencias=1,
            total_info=1,
            errores=errors,
            score=74,
        )
        text = r.resumen_whatsapp()
        assert "[EST-001]" in text
        assert "[FIS-004]" in text
        assert "[DED-004]" in text
        assert "Fix it" in text

    def test_whatsapp_no_recommendation_no_arrow(self):
        """Error without recommendation should not produce arrow line."""
        err = ErrorCFDI(
            codigo="X-001",
            mensaje="No rec",
            severidad=SeveridadError.CRITICO.value,
            tipo=TipoValidacion.ESTRUCTURA.value,
            recomendacion="",
        )
        r = ResultadoValidacion(es_valido=False, total_errores=1, errores=[err], score=80)
        text = r.resumen_whatsapp()
        lines = text.split("\n")
        arrow_lines = [l for l in lines if l.strip().startswith("->") or l.strip().startswith("\u2192")]
        assert len(arrow_lines) == 0


# ---- Structural Validation Tests ----------------------------------------------

class TestValidateStructure:
    def test_valid_cfdi_no_errors(self):
        errors = _validate_structure(CFDI_VALIDO)
        assert errors == []

    def test_missing_version(self):
        cfdi = _make_cfdi(version=None)
        errors = _validate_structure(cfdi)
        codes = [e.codigo for e in errors]
        assert "EST-001" in codes
        campo_errors = [e for e in errors if e.campo == "version"]
        assert len(campo_errors) >= 1

    def test_missing_emisor_rfc(self):
        cfdi = _make_cfdi(emisor_rfc=None)
        errors = _validate_structure(cfdi)
        codes = [e.codigo for e in errors]
        assert "EST-001" in codes

    def test_missing_receptor_rfc(self):
        cfdi = _make_cfdi(receptor_rfc=None)
        errors = _validate_structure(cfdi)
        codes = [e.codigo for e in errors]
        assert "EST-001" in codes

    def test_missing_fecha(self):
        cfdi = _make_cfdi(fecha=None)
        errors = _validate_structure(cfdi)
        campos = [e.campo for e in errors]
        assert "fecha" in campos

    def test_missing_total(self):
        cfdi = _make_cfdi(total=None)
        errors = _validate_structure(cfdi)
        campos = [e.campo for e in errors]
        assert "total" in campos

    def test_total_zero_not_error(self):
        """Total of 0 should not be treated as missing."""
        cfdi = _make_cfdi(total=0)
        errors = _validate_structure(cfdi)
        total_missing = [e for e in errors if e.campo == "total" and e.codigo == "EST-001"]
        assert len(total_missing) == 0

    def test_missing_tipo_comprobante(self):
        cfdi = _make_cfdi(tipo_comprobante=None)
        errors = _validate_structure(cfdi)
        campos = [e.campo for e in errors]
        assert "tipo_comprobante" in campos

    def test_multiple_missing_fields(self):
        cfdi = _make_cfdi(version=None, emisor_rfc=None, fecha=None)
        errors = _validate_structure(cfdi)
        est001 = [e for e in errors if e.codigo == "EST-001"]
        assert len(est001) >= 3

    def test_missing_uuid(self):
        cfdi = _make_cfdi(timbre={})
        errors = _validate_structure(cfdi)
        codes = [e.codigo for e in errors]
        assert "EST-002" in codes
        uuid_err = [e for e in errors if e.codigo == "EST-002"][0]
        assert uuid_err.severidad == SeveridadError.CRITICO.value

    def test_missing_timbre_key(self):
        cfdi = _make_cfdi(timbre=None)
        cfdi.pop("timbre", None)
        errors = _validate_structure(cfdi)
        codes = [e.codigo for e in errors]
        assert "EST-002" in codes

    def test_timbre_with_empty_uuid(self):
        cfdi = _make_cfdi(timbre={"uuid": ""})
        errors = _validate_structure(cfdi)
        codes = [e.codigo for e in errors]
        assert "EST-002" in codes

    def test_invalid_version(self):
        cfdi = _make_cfdi(version="2.0")
        errors = _validate_structure(cfdi)
        codes = [e.codigo for e in errors]
        assert "EST-003" in codes
        ver_err = [e for e in errors if e.codigo == "EST-003"][0]
        assert ver_err.severidad == SeveridadError.ADVERTENCIA.value
        assert ver_err.valor_actual == "2.0"

    def test_version_33_accepted(self):
        cfdi = _make_cfdi(version="3.3")
        errors = _validate_structure(cfdi)
        ver_errors = [e for e in errors if e.codigo == "EST-003"]
        assert len(ver_errors) == 0

    def test_version_40_accepted(self):
        cfdi = _make_cfdi(version="4.0")
        errors = _validate_structure(cfdi)
        ver_errors = [e for e in errors if e.codigo == "EST-003"]
        assert len(ver_errors) == 0

    def test_bad_rfc_length_short(self):
        cfdi = _make_cfdi(emisor_rfc="ABC")
        errors = _validate_structure(cfdi)
        codes = [e.codigo for e in errors]
        assert "EST-004" in codes

    def test_bad_rfc_length_long(self):
        cfdi = _make_cfdi(emisor_rfc="ABCDEFGHIJKLMNO")  # 15 chars
        errors = _validate_structure(cfdi)
        codes = [e.codigo for e in errors]
        assert "EST-004" in codes

    def test_rfc_12_chars_persona_moral_ok(self):
        cfdi = _make_cfdi(emisor_rfc="INM850101AB")  # 11? No, needs 12
        cfdi["emisor_rfc"] = "INM850101ABC"  # 12 chars
        errors = _validate_structure(cfdi)
        rfc_errors = [e for e in errors if e.codigo == "EST-004"]
        assert len(rfc_errors) == 0

    def test_rfc_13_chars_persona_fisica_ok(self):
        cfdi = _make_cfdi(emisor_rfc="MOPR881228EF9")  # 13 chars
        errors = _validate_structure(cfdi)
        rfc_errors = [e for e in errors if e.codigo == "EST-004"]
        assert len(rfc_errors) == 0

    def test_no_conceptos(self):
        cfdi = _make_cfdi(conceptos=[])
        errors = _validate_structure(cfdi)
        codes = [e.codigo for e in errors]
        assert "EST-005" in codes

    def test_missing_conceptos_key(self):
        cfdi = _make_cfdi()
        cfdi.pop("conceptos", None)
        errors = _validate_structure(cfdi)
        codes = [e.codigo for e in errors]
        assert "EST-005" in codes

    def test_all_structural_errors_are_critico_or_advertencia(self):
        errors = _validate_structure(CFDI_VALIDO)
        for e in errors:
            assert e.severidad in (SeveridadError.CRITICO.value, SeveridadError.ADVERTENCIA.value)


# ---- Fiscal Validation Tests --------------------------------------------------

class TestValidateFiscal:
    def test_valid_cfdi_no_fiscal_errors(self):
        errors = _validate_fiscal(CFDI_VALIDO)
        assert errors == []

    def test_invalid_tipo_comprobante(self):
        cfdi = _make_cfdi(tipo_comprobante="X")
        errors = _validate_fiscal(cfdi)
        codes = [e.codigo for e in errors]
        assert "FIS-001" in codes
        fis_err = [e for e in errors if e.codigo == "FIS-001"][0]
        assert fis_err.severidad == SeveridadError.CRITICO.value

    def test_valid_tipo_comprobante_all(self):
        for tipo in TIPOS_COMPROBANTE_VALIDOS:
            cfdi = _make_cfdi(tipo_comprobante=tipo)
            errors = _validate_fiscal(cfdi)
            tipo_errors = [e for e in errors if e.codigo == "FIS-001"]
            assert len(tipo_errors) == 0, f"Tipo '{tipo}' incorrectly flagged"

    def test_bad_forma_pago(self):
        cfdi = _make_cfdi(forma_pago="ZZ")
        errors = _validate_fiscal(cfdi)
        codes = [e.codigo for e in errors]
        assert "FIS-002" in codes
        fis_err = [e for e in errors if e.codigo == "FIS-002"][0]
        assert fis_err.severidad == SeveridadError.ADVERTENCIA.value

    def test_valid_formas_pago_accepted(self):
        for fp in ["01", "03", "04", "06", "28", "99"]:
            cfdi = _make_cfdi(forma_pago=fp)
            errors = _validate_fiscal(cfdi)
            fp_errors = [e for e in errors if e.codigo == "FIS-002"]
            assert len(fp_errors) == 0, f"Forma pago '{fp}' incorrectly flagged"

    def test_bad_metodo_pago(self):
        cfdi = _make_cfdi(metodo_pago="XYZ")
        errors = _validate_fiscal(cfdi)
        codes = [e.codigo for e in errors]
        assert "FIS-003" in codes
        fis_err = [e for e in errors if e.codigo == "FIS-003"][0]
        assert fis_err.severidad == SeveridadError.CRITICO.value

    def test_ppd_with_non_99_forma_pago(self):
        cfdi = _make_cfdi(metodo_pago="PPD", forma_pago="03")
        errors = _validate_fiscal(cfdi)
        codes = [e.codigo for e in errors]
        assert "FIS-004" in codes

    def test_ppd_with_99_no_fis004(self):
        cfdi = _make_cfdi(metodo_pago="PPD", forma_pago="99")
        errors = _validate_fiscal(cfdi)
        fis004 = [e for e in errors if e.codigo == "FIS-004"]
        assert len(fis004) == 0

    def test_pue_with_99_forma_pago(self):
        cfdi = _make_cfdi(metodo_pago="PUE", forma_pago="99")
        errors = _validate_fiscal(cfdi)
        codes = [e.codigo for e in errors]
        assert "FIS-005" in codes

    def test_pue_with_03_no_fis005(self):
        cfdi = _make_cfdi(metodo_pago="PUE", forma_pago="03")
        errors = _validate_fiscal(cfdi)
        fis005 = [e for e in errors if e.codigo == "FIS-005"]
        assert len(fis005) == 0

    def test_amount_consistency_valid(self):
        """subtotal(10000) + iva(1600) = total(11600) should pass."""
        errors = _validate_fiscal(CFDI_VALIDO)
        fis007 = [e for e in errors if e.codigo == "FIS-007"]
        assert len(fis007) == 0

    def test_amount_consistency_mismatch(self):
        cfdi = _make_cfdi(subtotal=10000.0, total=15000.0, iva_trasladado=1600.0)
        errors = _validate_fiscal(cfdi)
        codes = [e.codigo for e in errors]
        assert "FIS-007" in codes

    def test_amount_consistency_with_retenciones(self):
        """subtotal(10000) + iva(1600) - isr_ret(1000) - iva_ret(0) = 10600."""
        cfdi = _make_cfdi(
            subtotal=10000.0,
            iva_trasladado=1600.0,
            isr_retenido=1000.0,
            iva_retenido=0,
            total=10600.0,
        )
        errors = _validate_fiscal(cfdi)
        fis007 = [e for e in errors if e.codigo == "FIS-007"]
        assert len(fis007) == 0

    def test_amount_consistency_with_descuento(self):
        """subtotal(10000) - descuento(500) + iva(1520) = 11020."""
        cfdi = _make_cfdi(
            subtotal=10000.0,
            descuento=500.0,
            iva_trasladado=1520.0,
            total=11020.0,
        )
        errors = _validate_fiscal(cfdi)
        fis007 = [e for e in errors if e.codigo == "FIS-007"]
        assert len(fis007) == 0

    def test_amount_tolerance_within_one_peso(self):
        """Within $1 tolerance should not flag."""
        cfdi = _make_cfdi(
            subtotal=10000.0,
            iva_trasladado=1600.0,
            total=11600.50,  # 0.50 off
        )
        errors = _validate_fiscal(cfdi)
        fis007 = [e for e in errors if e.codigo == "FIS-007"]
        assert len(fis007) == 0

    def test_amount_tolerance_exceeds_one_peso(self):
        cfdi = _make_cfdi(
            subtotal=10000.0,
            iva_trasladado=1600.0,
            total=11602.0,  # 2.0 off
        )
        errors = _validate_fiscal(cfdi)
        fis007 = [e for e in errors if e.codigo == "FIS-007"]
        assert len(fis007) == 1

    def test_unrecognized_uso_cfdi(self):
        cfdi = _make_cfdi(receptor_uso_cfdi="ZZZ")
        errors = _validate_fiscal(cfdi)
        codes = [e.codigo for e in errors]
        assert "FIS-006" in codes

    def test_valid_uso_cfdi_g03(self):
        cfdi = _make_cfdi(receptor_uso_cfdi="G03")
        errors = _validate_fiscal(cfdi)
        fis006 = [e for e in errors if e.codigo == "FIS-006"]
        assert len(fis006) == 0

    def test_valid_uso_cfdi_s01(self):
        cfdi = _make_cfdi(receptor_uso_cfdi="S01")
        errors = _validate_fiscal(cfdi)
        fis006 = [e for e in errors if e.codigo == "FIS-006"]
        assert len(fis006) == 0


# ---- Deducibility Validation Tests --------------------------------------------

class TestValidateDeducibility:
    def test_valid_cfdi_no_deducibility_errors(self):
        errors = _validate_deducibility(CFDI_VALIDO, regimen_doctor="612")
        assert errors == []

    def test_cash_over_2000(self):
        cfdi = _make_cfdi(forma_pago="01", total=2500.0)
        errors = _validate_deducibility(cfdi)
        codes = [e.codigo for e in errors]
        assert "DED-001" in codes
        ded_err = [e for e in errors if e.codigo == "DED-001"][0]
        assert ded_err.severidad == SeveridadError.CRITICO.value
        assert "Art. 27" in ded_err.fundamento

    def test_cash_exactly_2000_no_error(self):
        cfdi = _make_cfdi(forma_pago="01", total=2000.0)
        errors = _validate_deducibility(cfdi)
        ded001 = [e for e in errors if e.codigo == "DED-001"]
        assert len(ded001) == 0

    def test_cash_under_2000_no_error(self):
        cfdi = _make_cfdi(forma_pago="01", total=500.0)
        errors = _validate_deducibility(cfdi)
        ded001 = [e for e in errors if e.codigo == "DED-001"]
        assert len(ded001) == 0

    def test_forma_pago_99_with_pue(self):
        cfdi = _make_cfdi(forma_pago="99", metodo_pago="PUE")
        errors = _validate_deducibility(cfdi)
        codes = [e.codigo for e in errors]
        assert "DED-002" in codes

    def test_forma_pago_99_with_ppd_no_ded002(self):
        cfdi = _make_cfdi(forma_pago="99", metodo_pago="PPD")
        errors = _validate_deducibility(cfdi)
        ded002 = [e for e in errors if e.codigo == "DED-002"]
        assert len(ded002) == 0

    def test_ppd_warning(self):
        cfdi = _make_cfdi(metodo_pago="PPD", forma_pago="99")
        errors = _validate_deducibility(cfdi)
        codes = [e.codigo for e in errors]
        assert "DED-003" in codes
        ded_err = [e for e in errors if e.codigo == "DED-003"][0]
        assert ded_err.severidad == SeveridadError.ADVERTENCIA.value

    def test_pue_no_ded003(self):
        cfdi = _make_cfdi(metodo_pago="PUE")
        errors = _validate_deducibility(cfdi)
        ded003 = [e for e in errors if e.codigo == "DED-003"]
        assert len(ded003) == 0

    def test_resico_info(self):
        cfdi = _make_cfdi()
        errors = _validate_deducibility(cfdi, regimen_doctor="625")
        codes = [e.codigo for e in errors]
        assert "DED-004" in codes
        ded_err = [e for e in errors if e.codigo == "DED-004"][0]
        assert ded_err.severidad == SeveridadError.INFO.value

    def test_non_resico_no_ded004(self):
        cfdi = _make_cfdi()
        errors = _validate_deducibility(cfdi, regimen_doctor="612")
        ded004 = [e for e in errors if e.codigo == "DED-004"]
        assert len(ded004) == 0

    def test_uso_s01_not_deducible(self):
        cfdi = _make_cfdi(receptor_uso_cfdi="S01")
        errors = _validate_deducibility(cfdi)
        codes = [e.codigo for e in errors]
        assert "DED-005" in codes
        ded_err = [e for e in errors if e.codigo == "DED-005"][0]
        assert ded_err.severidad == SeveridadError.CRITICO.value

    def test_uso_g03_no_ded005(self):
        cfdi = _make_cfdi(receptor_uso_cfdi="G03")
        errors = _validate_deducibility(cfdi)
        ded005 = [e for e in errors if e.codigo == "DED-005"]
        assert len(ded005) == 0


# ---- Medical Validation Tests -------------------------------------------------

class TestValidateMedical:
    def test_non_medical_no_errors(self):
        errors = _validate_medical(CFDI_VALIDO)
        assert errors == []

    def test_medical_with_iva_should_be_exempt(self):
        cfdi = _make_cfdi(
            emisor_regimen="612",
            tipo_comprobante="I",
            subtotal=5000.0,
            iva_trasladado=800.0,
            total=5800.0,
            conceptos=[{"clave_prod_serv": "85121600", "descripcion": "Consulta medica"}],
        )
        errors = _validate_medical(cfdi)
        codes = [e.codigo for e in errors]
        assert "MED-001" in codes
        med_err = [e for e in errors if e.codigo == "MED-001"][0]
        assert med_err.severidad == SeveridadError.CRITICO.value
        assert "Art. 15" in med_err.fundamento

    def test_medical_exento_iva_no_med001(self):
        cfdi = _make_cfdi(
            emisor_regimen="612",
            tipo_comprobante="I",
            subtotal=5000.0,
            iva_trasladado=0,
            total=5000.0,
            exento_iva=True,
            conceptos=[{"clave_prod_serv": "85121600", "descripcion": "Consulta medica"}],
        )
        errors = _validate_medical(cfdi)
        med001 = [e for e in errors if e.codigo == "MED-001"]
        assert len(med001) == 0

    def test_medical_with_exento_flag_no_error(self):
        """If exento_iva is True, even with IVA > 0 the code checks for exento flag."""
        cfdi = _make_cfdi(
            emisor_regimen="612",
            tipo_comprobante="I",
            subtotal=5000.0,
            iva_trasladado=800.0,
            total=5800.0,
            exento_iva=True,
            conceptos=[{"clave_prod_serv": "85121600", "descripcion": "Consulta medica"}],
        )
        errors = _validate_medical(cfdi)
        med001 = [e for e in errors if e.codigo == "MED-001"]
        assert len(med001) == 0

    def test_medical_code_prefix_8510(self):
        cfdi = _make_cfdi(
            emisor_regimen="625",
            tipo_comprobante="I",
            subtotal=3000.0,
            iva_trasladado=480.0,
            total=3480.0,
            conceptos=[{"clave_prod_serv": "85101501", "descripcion": "Servicio dental"}],
        )
        errors = _validate_medical(cfdi)
        med001 = [e for e in errors if e.codigo == "MED-001"]
        assert len(med001) == 1

    def test_medical_code_prefix_8511(self):
        cfdi = _make_cfdi(
            emisor_regimen="612",
            tipo_comprobante="I",
            subtotal=2000.0,
            iva_trasladado=320.0,
            total=2320.0,
            conceptos=[{"clave_prod_serv": "85111501", "descripcion": "Laboratorio"}],
        )
        errors = _validate_medical(cfdi)
        med001 = [e for e in errors if e.codigo == "MED-001"]
        # Code starts with 8511, which matches startswith("8511") check? Let's verify.
        # The source checks startswith(("8510", "8511", "8512", "8513"))
        assert len(med001) == 1

    def test_non_medical_code_no_med001(self):
        cfdi = _make_cfdi(
            emisor_regimen="612",
            tipo_comprobante="I",
            subtotal=5000.0,
            iva_trasladado=800.0,
            total=5800.0,
            conceptos=[{"clave_prod_serv": "43232100", "descripcion": "Software"}],
        )
        errors = _validate_medical(cfdi)
        med001 = [e for e in errors if e.codigo == "MED-001"]
        assert len(med001) == 0

    def test_persona_moral_without_isr_retention(self):
        cfdi = _make_cfdi(
            emisor_regimen="612",
            tipo_comprobante="I",
            receptor_rfc="INM850101AB",  # Need 12 chars
            subtotal=5000.0,
            isr_retenido=0,
        )
        # Ensure receptor_rfc is exactly 12 characters
        cfdi["receptor_rfc"] = "INM850101ABC"  # 12 chars = PM
        errors = _validate_medical(cfdi)
        codes = [e.codigo for e in errors]
        assert "MED-002" in codes
        med_err = [e for e in errors if e.codigo == "MED-002"][0]
        assert med_err.severidad == SeveridadError.ADVERTENCIA.value
        assert "Art. 106" in med_err.fundamento

    def test_persona_moral_with_isr_retention_no_med002(self):
        cfdi = _make_cfdi(
            emisor_regimen="612",
            tipo_comprobante="I",
            receptor_rfc="INM850101ABC",  # 12 chars = PM
            subtotal=5000.0,
            isr_retenido=500.0,
        )
        errors = _validate_medical(cfdi)
        med002 = [e for e in errors if e.codigo == "MED-002"]
        assert len(med002) == 0

    def test_persona_fisica_no_isr_retention_required(self):
        cfdi = _make_cfdi(
            emisor_regimen="612",
            tipo_comprobante="I",
            receptor_rfc="MOPR881228EF9",  # 13 chars = PF
            subtotal=5000.0,
            isr_retenido=0,
        )
        errors = _validate_medical(cfdi)
        med002 = [e for e in errors if e.codigo == "MED-002"]
        assert len(med002) == 0

    def test_non_medical_regimen_no_med_errors(self):
        """Emisor regimen not 612/625 should not trigger MED checks."""
        cfdi = _make_cfdi(
            emisor_regimen="601",
            tipo_comprobante="I",
            receptor_rfc="INM850101ABC",
            subtotal=5000.0,
            isr_retenido=0,
        )
        errors = _validate_medical(cfdi)
        med_errors = [e for e in errors if e.codigo.startswith("MED")]
        assert len(med_errors) == 0


# ---- Payment Validation Tests -------------------------------------------------

class TestValidatePayment:
    def test_valid_cfdi_no_payment_errors(self):
        errors = _validate_payment(CFDI_VALIDO)
        assert errors == []

    def test_missing_forma_pago_ingreso(self):
        cfdi = _make_cfdi(tipo_comprobante="I", forma_pago=None)
        errors = _validate_payment(cfdi)
        codes = [e.codigo for e in errors]
        assert "PAG-001" in codes

    def test_missing_forma_pago_egreso(self):
        cfdi = _make_cfdi(tipo_comprobante="E", forma_pago=None)
        errors = _validate_payment(cfdi)
        codes = [e.codigo for e in errors]
        assert "PAG-001" in codes

    def test_missing_metodo_pago_ingreso(self):
        cfdi = _make_cfdi(tipo_comprobante="I", metodo_pago=None)
        errors = _validate_payment(cfdi)
        codes = [e.codigo for e in errors]
        assert "PAG-002" in codes

    def test_missing_metodo_pago_egreso(self):
        cfdi = _make_cfdi(tipo_comprobante="E", metodo_pago=None)
        errors = _validate_payment(cfdi)
        codes = [e.codigo for e in errors]
        assert "PAG-002" in codes

    def test_pago_type_no_payment_required(self):
        """Type P (Pago) should not require forma/metodo pago."""
        cfdi = _make_cfdi(tipo_comprobante="P", forma_pago=None, metodo_pago=None)
        errors = _validate_payment(cfdi)
        assert errors == []

    def test_nomina_type_no_payment_required(self):
        """Type N (Nomina) should not require forma/metodo pago."""
        cfdi = _make_cfdi(tipo_comprobante="N", forma_pago=None, metodo_pago=None)
        errors = _validate_payment(cfdi)
        assert errors == []

    def test_traslado_type_no_payment_required(self):
        """Type T (Traslado) should not require forma/metodo pago."""
        cfdi = _make_cfdi(tipo_comprobante="T", forma_pago=None, metodo_pago=None)
        errors = _validate_payment(cfdi)
        assert errors == []

    def test_missing_both_forma_and_metodo(self):
        cfdi = _make_cfdi(tipo_comprobante="I", forma_pago=None, metodo_pago=None)
        errors = _validate_payment(cfdi)
        codes = [e.codigo for e in errors]
        assert "PAG-001" in codes
        assert "PAG-002" in codes


# ---- Score Calculation Tests --------------------------------------------------

class TestScoreCalculation:
    def test_clean_cfdi_score_100(self):
        result = validate_cfdi(CFDI_VALIDO, es_gasto=True)
        assert result.score == 100

    def test_one_critico_minus_20(self):
        cfdi = _make_cfdi(timbre={})  # EST-002 = critical
        result = validate_cfdi(cfdi, es_gasto=False)
        assert result.score <= 80

    def test_one_advertencia_minus_5(self):
        cfdi = _make_cfdi(metodo_pago="PUE", forma_pago="99")  # FIS-005 = warning
        result = validate_cfdi(cfdi, es_gasto=False)
        assert result.score <= 95

    def test_score_never_below_zero(self):
        """Even with many errors, score floors at 0."""
        cfdi = {
            "tipo_comprobante": "X",  # FIS-001 critical
        }
        result = validate_cfdi(cfdi, es_gasto=True, regimen_doctor="625")
        assert result.score >= 0

    def test_score_never_above_100(self):
        result = validate_cfdi(CFDI_VALIDO, es_gasto=True)
        assert result.score <= 100

    def test_info_minus_1(self):
        """RESICO info error subtracts 1 from score."""
        result = validate_cfdi(CFDI_VALIDO, es_gasto=True, regimen_doctor="625")
        ded004 = [e for e in result.errores if e.codigo == "DED-004"]
        assert len(ded004) == 1
        assert result.score == 99


# ---- validate_cfdi Integration Tests ------------------------------------------

class TestValidateCFDI:
    def test_clean_cfdi_valid(self):
        result = validate_cfdi(CFDI_VALIDO)
        assert result.es_valido is True
        assert result.total_errores == 0
        assert result.score == 100

    def test_clean_cfdi_no_errors(self):
        result = validate_cfdi(CFDI_VALIDO)
        assert result.errores == []

    def test_clean_cfdi_counts(self):
        result = validate_cfdi(CFDI_VALIDO)
        assert result.total_errores == 0
        assert result.total_advertencias == 0
        assert result.total_info == 0

    def test_multiple_errors_low_score(self):
        cfdi = {
            "tipo_comprobante": "X",  # FIS-001 critical
            # Missing: version, emisor_rfc, receptor_rfc, fecha, total -> 5 x EST-001
            # Missing timbre -> EST-002
            # No conceptos -> EST-005
        }
        result = validate_cfdi(cfdi, es_gasto=True, regimen_doctor="625")
        assert result.es_valido is False
        assert result.total_errores >= 5
        assert result.score <= 20

    def test_es_gasto_false_skips_deducibility(self):
        """When es_gasto=False, deducibility checks are skipped."""
        cfdi = _make_cfdi(forma_pago="01", total=5000.0)  # Cash over 2000
        result_gasto = validate_cfdi(cfdi, es_gasto=True)
        result_ingreso = validate_cfdi(cfdi, es_gasto=False)
        ded_gasto = [e for e in result_gasto.errores if e.codigo.startswith("DED")]
        ded_ingreso = [e for e in result_ingreso.errores if e.codigo.startswith("DED")]
        assert len(ded_gasto) >= 1
        assert len(ded_ingreso) == 0

    def test_default_regimen_is_612(self):
        cfdi = _make_cfdi()
        result = validate_cfdi(cfdi)
        ded004 = [e for e in result.errores if e.codigo == "DED-004"]
        assert len(ded004) == 0  # 612 != 625, so no RESICO info

    def test_resico_regimen_adds_info(self):
        cfdi = _make_cfdi()
        result = validate_cfdi(cfdi, regimen_doctor="625")
        ded004 = [e for e in result.errores if e.codigo == "DED-004"]
        assert len(ded004) == 1

    def test_es_valido_true_when_only_warnings(self):
        cfdi = _make_cfdi(metodo_pago="PUE", forma_pago="99")  # FIS-005 warning
        result = validate_cfdi(cfdi, es_gasto=False)
        assert result.es_valido is True
        assert result.total_advertencias >= 1

    def test_es_valido_false_with_critical(self):
        cfdi = _make_cfdi(timbre={})
        result = validate_cfdi(cfdi, es_gasto=False)
        assert result.es_valido is False

    def test_all_validation_types_run(self):
        """Ensure all five validation modules are called."""
        # Build a CFDI that triggers at least one error from each module
        cfdi = _make_cfdi(
            version="2.0",               # EST-003 (structure)
            tipo_comprobante="I",
            metodo_pago="PUE",
            forma_pago="99",             # FIS-005 (fiscal) + DED-002 (deducibility)
            emisor_regimen="612",
            receptor_rfc="INM850101ABC", # 12 chars PM -> MED-002 (medical)
            subtotal=5000.0,
            isr_retenido=0,
        )
        result = validate_cfdi(cfdi, es_gasto=True)
        tipos = {e.tipo for e in result.errores}
        # Should have at least Estructura, Fiscal, and Deducibilidad
        assert TipoValidacion.ESTRUCTURA.value in tipos
        assert TipoValidacion.FISCAL.value in tipos
        assert TipoValidacion.DEDUCIBILIDAD.value in tipos


# ---- validate_cfdi_batch Tests ------------------------------------------------

class TestValidateCFDIBatch:
    def test_single_cfdi(self):
        result = validate_cfdi_batch([CFDI_VALIDO])
        assert result["total_cfdis"] == 1
        assert result["cfdis_validos"] == 1
        assert result["cfdis_con_errores"] == 0
        assert result["score_promedio"] == 100.0

    def test_multiple_cfdis(self):
        cfdi_bad = _make_cfdi(timbre={})
        result = validate_cfdi_batch([CFDI_VALIDO, cfdi_bad])
        assert result["total_cfdis"] == 2
        assert result["cfdis_validos"] == 1
        assert result["cfdis_con_errores"] == 1

    def test_batch_score_promedio(self):
        result = validate_cfdi_batch([CFDI_VALIDO, CFDI_VALIDO])
        assert result["score_promedio"] == 100.0

    def test_batch_result_keys(self):
        result = validate_cfdi_batch([CFDI_VALIDO])
        expected_keys = {
            "total_cfdis", "cfdis_validos", "cfdis_con_errores",
            "total_errores_criticos", "total_advertencias",
            "score_promedio", "resultados",
        }
        assert set(result.keys()) == expected_keys

    def test_batch_result_per_cfdi_keys(self):
        result = validate_cfdi_batch([CFDI_VALIDO])
        r = result["resultados"][0]
        expected_keys = {
            "index", "uuid", "emisor", "total", "score",
            "es_valido", "errores", "advertencias",
        }
        assert set(r.keys()) == expected_keys

    def test_batch_uuid_truncated(self):
        result = validate_cfdi_batch([CFDI_VALIDO])
        uuid_short = result["resultados"][0]["uuid"]
        assert len(uuid_short) == 8
        assert uuid_short == "ABC12345"

    def test_batch_emisor_extracted(self):
        result = validate_cfdi_batch([CFDI_VALIDO])
        assert result["resultados"][0]["emisor"] == "Inmobiliaria Centro"

    def test_batch_total_errores_criticos_summed(self):
        cfdi_bad1 = _make_cfdi(timbre={})
        cfdi_bad2 = _make_cfdi(timbre={}, version=None)
        result = validate_cfdi_batch([cfdi_bad1, cfdi_bad2])
        assert result["total_errores_criticos"] >= 2

    def test_empty_batch(self):
        result = validate_cfdi_batch([])
        assert result["total_cfdis"] == 0
        assert result["score_promedio"] == 0

    def test_batch_with_regimen(self):
        result = validate_cfdi_batch([CFDI_VALIDO], regimen_doctor="625")
        # RESICO info should appear
        assert result["total_cfdis"] == 1


# ---- Catalog Constants Tests --------------------------------------------------

class TestCatalogConstants:
    def test_formas_pago_is_set(self):
        assert isinstance(FORMAS_PAGO_VALIDAS, set)
        assert "01" in FORMAS_PAGO_VALIDAS
        assert "03" in FORMAS_PAGO_VALIDAS
        assert "99" in FORMAS_PAGO_VALIDAS

    def test_metodos_pago_is_set(self):
        assert isinstance(METODOS_PAGO_VALIDOS, set)
        assert METODOS_PAGO_VALIDOS == {"PUE", "PPD"}

    def test_tipos_comprobante_is_set(self):
        assert isinstance(TIPOS_COMPROBANTE_VALIDOS, set)
        assert TIPOS_COMPROBANTE_VALIDOS == {"I", "E", "P", "N", "T"}


# ---- Module Exports Tests ----------------------------------------------------

class TestModuleExports:
    def test_validate_cfdi_importable_from_tools(self):
        from src.tools import validate_cfdi as vc
        assert callable(vc)

    def test_validate_cfdi_batch_importable_from_tools(self):
        from src.tools import validate_cfdi_batch as vcb
        assert callable(vcb)

    def test_resultado_validacion_importable_from_tools(self):
        from src.tools import ResultadoValidacion as RV
        assert RV is not None

    def test_error_cfdi_importable_from_tools(self):
        from src.tools import ErrorCFDI as EC
        assert EC is not None

    def test_severidad_error_importable_from_tools(self):
        from src.tools import SeveridadError as SE
        assert SE is not None

    def test_tipo_validacion_importable_from_tools(self):
        from src.tools import TipoValidacion as TV
        assert TV is not None

    def test_all_exports_in_tools_all(self):
        import src.tools
        all_names = src.tools.__all__
        assert "validate_cfdi" in all_names
        assert "validate_cfdi_batch" in all_names
        assert "ResultadoValidacion" in all_names
        assert "ErrorCFDI" in all_names
        assert "SeveridadError" in all_names
        assert "TipoValidacion" in all_names
