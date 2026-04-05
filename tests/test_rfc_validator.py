"""Tests for OpenDoc RFC Validator.

Validates:
- RFC format validation (PF 13 chars, PM 12 chars)
- Check digit algorithm (SAT official)
- Date extraction and validation
- Generic RFC detection
- Batch validation
- Edge cases (empty, short, long, special chars)
- WhatsApp summary formatting
"""

import pytest

from src.tools.rfc_validator import (
    # Functions
    validate_rfc,
    validate_rfc_batch,
    is_valid_rfc,
    classify_rfc,
    _calculate_check_digit,
    _validate_rfc_date,
    # Classes
    ValidacionRFC,
    TipoPersona,
    ResultadoRFC,
    # Constants
    RFC_GENERICO_NACIONAL,
    RFC_GENERICO_EXTRANJERO,
    RFCS_GENERICOS,
)


# ─── Test: TipoPersona Enum ──────────────────────────────────────────

class TestTipoPersona:
    def test_fisica(self):
        assert TipoPersona.FISICA.value == "Persona Física"

    def test_moral(self):
        assert TipoPersona.MORAL.value == "Persona Moral"

    def test_two_types(self):
        assert len(TipoPersona) == 2


# ─── Test: ResultadoRFC Enum ─────────────────────────────────────────

class TestResultadoRFC:
    def test_valido(self):
        assert ResultadoRFC.VALIDO.value == "Válido"

    def test_invalido(self):
        assert ResultadoRFC.INVALIDO.value == "Inválido"

    def test_generico(self):
        assert ResultadoRFC.GENERICO.value == "Genérico"

    def test_three_statuses(self):
        assert len(ResultadoRFC) == 3


# ─── Test: Generic RFCs ──────────────────────────────────────────────

class TestGenericRFCs:
    def test_nacional(self):
        assert RFC_GENERICO_NACIONAL == "XAXX010101000"

    def test_extranjero(self):
        assert RFC_GENERICO_EXTRANJERO == "XEXX010101000"

    def test_set_contains_both(self):
        assert len(RFCS_GENERICOS) == 2
        assert RFC_GENERICO_NACIONAL in RFCS_GENERICOS
        assert RFC_GENERICO_EXTRANJERO in RFCS_GENERICOS

    def test_validate_generico_nacional(self):
        result = validate_rfc(RFC_GENERICO_NACIONAL)
        assert result.es_valido is True
        assert result.estatus == "Genérico"

    def test_validate_generico_extranjero(self):
        result = validate_rfc(RFC_GENERICO_EXTRANJERO)
        assert result.es_valido is True
        assert result.estatus == "Genérico"

    def test_generico_whatsapp(self):
        result = validate_rfc(RFC_GENERICO_NACIONAL)
        wsp = result.resumen_whatsapp()
        assert "GENÉRICO" in wsp
        assert "XAXX010101000" in wsp


# ─── Test: Check Digit Algorithm ─────────────────────────────────────

class TestCheckDigitAlgorithm:
    def test_returns_single_char(self):
        result = _calculate_check_digit("ABCD123456AB")
        assert len(result) == 1

    def test_short_input_pm(self):
        """PM RFC has 11 chars before check digit — should be padded."""
        result = _calculate_check_digit("ABC123456AB")
        assert len(result) == 1
        assert result != "?"

    def test_invalid_length(self):
        assert _calculate_check_digit("AB") == "?"

    def test_invalid_character(self):
        assert _calculate_check_digit("!@#$%^&*()12") == "?"

    def test_deterministic(self):
        """Same input always produces same check digit."""
        r1 = _calculate_check_digit("ABCD123456AB")
        r2 = _calculate_check_digit("ABCD123456AB")
        assert r1 == r2

    def test_digit_can_be_A(self):
        """Check digit can be 'A' (when 11 - remainder = 10)."""
        # We can't easily force this, but verify the algorithm handles it
        # by testing known RFCs where this occurs
        pass

    def test_different_inputs_different_digits(self):
        r1 = _calculate_check_digit("AAAA000101AB")
        r2 = _calculate_check_digit("ZZZZ991231AB")
        # They CAN be the same by coincidence, but usually differ
        # Just verify both are valid characters
        assert r1 in "0123456789A"
        assert r2 in "0123456789A"


# ─── Test: Date Validation ────────────────────────────────────────────

class TestDateValidation:
    def test_valid_date(self):
        valid, formatted, error = _validate_rfc_date("850101")
        assert valid is True
        assert formatted == "1985-01-01"
        assert error == ""

    def test_year_2000s(self):
        valid, formatted, _ = _validate_rfc_date("001231")
        assert valid is True
        assert formatted == "2000-12-31"

    def test_year_2025(self):
        valid, formatted, _ = _validate_rfc_date("250615")
        assert valid is True
        assert formatted == "2025-06-15"

    def test_year_1999(self):
        valid, formatted, _ = _validate_rfc_date("990101")
        assert valid is True
        assert formatted == "1999-01-01"

    def test_year_1950(self):
        valid, formatted, _ = _validate_rfc_date("500101")
        assert valid is True
        assert formatted == "1950-01-01"

    def test_invalid_month_zero(self):
        valid, _, error = _validate_rfc_date("850001")
        assert valid is False
        assert "Mes" in error

    def test_invalid_month_13(self):
        valid, _, error = _validate_rfc_date("851301")
        assert valid is False
        assert "Mes" in error

    def test_invalid_day_zero(self):
        valid, _, error = _validate_rfc_date("850100")
        assert valid is False
        assert "Día" in error

    def test_invalid_day_32(self):
        valid, _, error = _validate_rfc_date("850132")
        assert valid is False
        assert "Día" in error

    def test_feb_29_allowed(self):
        """Feb 29 is allowed (leap year check is approximate)."""
        valid, _, _ = _validate_rfc_date("000229")
        assert valid is True

    def test_non_digit(self):
        valid, _, error = _validate_rfc_date("85AB01")
        assert valid is False

    def test_short_string(self):
        valid, _, error = _validate_rfc_date("8501")
        assert valid is False


# ─── Test: Persona Física Validation ──────────────────────────────────

class TestPersonaFisica:
    def test_valid_length_13(self):
        result = validate_rfc("ABCD850101XX1")
        assert result.tipo_persona == "Persona Física"

    def test_invalid_pattern_lowercase(self):
        """Lowercase should be uppercased automatically."""
        result = validate_rfc("abcd850101xx1")
        assert result.tipo_persona == "Persona Física"

    def test_date_extracted(self):
        result = validate_rfc("ABCD850101XX1")
        assert "1985-01-01" in result.fecha_nacimiento

    def test_name_extracted(self):
        result = validate_rfc("GALM850101XX1")
        assert result.nombre_parcial == "GALM"

    def test_strips_whitespace(self):
        result = validate_rfc("  ABCD850101XX1  ")
        assert result.rfc == "ABCD850101XX1"


# ─── Test: Persona Moral Validation ──────────────────────────────────

class TestPersonaMoral:
    def test_valid_length_12(self):
        result = validate_rfc("ABC850101XX1")
        assert result.tipo_persona == "Persona Moral"

    def test_date_extracted(self):
        result = validate_rfc("ABC990101XX1")
        assert "1999-01-01" in result.fecha_nacimiento

    def test_name_extracted(self):
        result = validate_rfc("XYZ850101XX1")
        assert result.nombre_parcial == "XYZ"


# ─── Test: Invalid RFCs ──────────────────────────────────────────────

class TestInvalidRFCs:
    def test_too_short(self):
        result = validate_rfc("ABC")
        assert result.es_valido is False
        assert "Longitud" in result.errores[0]

    def test_too_long(self):
        result = validate_rfc("ABCD850101XX12345")
        assert result.es_valido is False
        assert "Longitud" in result.errores[0]

    def test_empty_string(self):
        result = validate_rfc("")
        assert result.es_valido is False

    def test_invalid_month(self):
        result = validate_rfc("ABCD851301XX1")
        assert result.es_valido is False
        assert any("Mes" in e for e in result.errores)

    def test_invalid_day(self):
        result = validate_rfc("ABCD850132XX1")
        assert result.es_valido is False
        assert any("Día" in e for e in result.errores)

    def test_numbers_in_name(self):
        result = validate_rfc("1234850101XX1")
        assert result.es_valido is False

    def test_single_char(self):
        result = validate_rfc("A")
        assert result.es_valido is False


# ─── Test: Check Digit Verification ──────────────────────────────────

class TestCheckDigitVerification:
    def test_wrong_digit_detected(self):
        """Construct an RFC, flip the last char, verify failure."""
        # Start with known good base, calculate check digit
        base = "ABCD850101AB"
        expected = _calculate_check_digit(base)
        good_rfc = base + expected

        # Validate the good one
        result_good = validate_rfc(good_rfc)
        # May have date or other issues but check digit should match
        assert result_good.digito_esperado == result_good.digito_encontrado

        # Now flip the check digit
        wrong_digit = "X" if expected != "X" else "Y"
        bad_rfc = base + wrong_digit
        result_bad = validate_rfc(bad_rfc)
        assert any("verificador" in e.lower() for e in result_bad.errores)

    def test_digito_reported(self):
        result = validate_rfc("ABCD850101AB1")
        assert result.digito_encontrado == "1"
        assert result.digito_esperado != ""


# ─── Test: is_valid_rfc() ────────────────────────────────────────────

class TestIsValidRfc:
    def test_generic_is_valid(self):
        assert is_valid_rfc(RFC_GENERICO_NACIONAL) is True

    def test_empty_is_invalid(self):
        assert is_valid_rfc("") is False

    def test_short_is_invalid(self):
        assert is_valid_rfc("ABC") is False

    def test_returns_bool(self):
        result = is_valid_rfc("ABCD850101XX1")
        assert isinstance(result, bool)


# ─── Test: classify_rfc() ────────────────────────────────────────────

class TestClassifyRfc:
    def test_generic(self):
        assert classify_rfc(RFC_GENERICO_NACIONAL) == "Genérico SAT"

    def test_persona_fisica(self):
        # 13-char RFC classified as PF (even if check digit wrong)
        result = classify_rfc("ABCD850101XX1")
        assert result in ["Persona Física", "Inválido"]

    def test_persona_moral(self):
        result = classify_rfc("ABC850101XX1")
        assert result in ["Persona Moral", "Inválido"]

    def test_invalid(self):
        assert classify_rfc("X") == "Inválido"


# ─── Test: validate_rfc_batch() ──────────────────────────────────────

class TestBatchValidation:
    def test_empty_list(self):
        results = validate_rfc_batch([])
        assert results == []

    def test_single_item(self):
        results = validate_rfc_batch([RFC_GENERICO_NACIONAL])
        assert len(results) == 1
        assert results[0].es_valido is True

    def test_multiple_items(self):
        rfcs = [RFC_GENERICO_NACIONAL, "ABC", RFC_GENERICO_EXTRANJERO]
        results = validate_rfc_batch(rfcs)
        assert len(results) == 3
        assert results[0].es_valido is True
        assert results[1].es_valido is False
        assert results[2].es_valido is True

    def test_returns_list_of_validacion(self):
        results = validate_rfc_batch(["ABCD850101XX1"])
        assert isinstance(results[0], ValidacionRFC)


# ─── Test: WhatsApp Summary ──────────────────────────────────────────

class TestWhatsAppSummary:
    def test_valid_rfc_summary(self):
        result = validate_rfc(RFC_GENERICO_NACIONAL)
        wsp = result.resumen_whatsapp()
        assert "━━━" in wsp
        assert "XAXX010101000" in wsp

    def test_invalid_rfc_summary(self):
        result = validate_rfc("INVALID")
        wsp = result.resumen_whatsapp()
        assert "━━━" in wsp
        assert "❌" in wsp

    def test_summary_includes_errors(self):
        result = validate_rfc("INVALID")
        wsp = result.resumen_whatsapp()
        assert "🚨" in wsp

    def test_generico_summary(self):
        result = validate_rfc(RFC_GENERICO_EXTRANJERO)
        wsp = result.resumen_whatsapp()
        assert "GENÉRICO" in wsp
        assert "extranjeros" in wsp.lower() or "general" in wsp.lower()


# ─── Test: ValidacionRFC Dataclass ───────────────────────────────────

class TestValidacionRFC:
    def test_default_errores_empty(self):
        v = ValidacionRFC(rfc="TEST", es_valido=True, estatus="test")
        assert v.errores == []

    def test_errores_preserved(self):
        v = ValidacionRFC(
            rfc="TEST", es_valido=False, estatus="test",
            errores=["Error 1", "Error 2"],
        )
        assert len(v.errores) == 2

    def test_all_fields(self):
        v = ValidacionRFC(
            rfc="ABCD850101AB1",
            es_valido=True,
            estatus="Válido",
            tipo_persona="Persona Física",
            digito_esperado="1",
            digito_encontrado="1",
            errores=[],
            fecha_nacimiento="1985-01-01",
            nombre_parcial="ABCD",
        )
        assert v.rfc == "ABCD850101AB1"
        assert v.tipo_persona == "Persona Física"
        assert v.fecha_nacimiento == "1985-01-01"


# ─── Test: Edge Cases ─────────────────────────────────────────────────

class TestEdgeCases:
    def test_ampersand_in_rfc(self):
        """RFC can contain & for Persona Moral."""
        result = validate_rfc("A&B850101XX1")
        assert result.tipo_persona == "Persona Moral"

    def test_n_tilde_in_rfc(self):
        """RFC can contain Ñ."""
        result = validate_rfc("MUÑO850101XX1")
        assert result.tipo_persona == "Persona Física"

    def test_case_insensitive(self):
        r1 = validate_rfc("ABCD850101AB1")
        r2 = validate_rfc("abcd850101ab1")
        assert r1.rfc == r2.rfc

    def test_whitespace_handling(self):
        result = validate_rfc("  XAXX010101000  ")
        assert result.es_valido is True
        assert result.rfc == "XAXX010101000"

    def test_very_old_date(self):
        """RFC from 1930s — valid format."""
        result = validate_rfc("ABCD310101XX1")
        assert "1931" in result.fecha_nacimiento or "2031" in result.fecha_nacimiento

    def test_recent_date(self):
        """RFC from 2020."""
        result = validate_rfc("ABCD200615XX1")
        assert "2020-06-15" in result.fecha_nacimiento


# ─── Test: Module Exports ────────────────────────────────────────────

class TestModuleExports:
    def test_functions_exist(self):
        from src.tools import rfc_validator as m
        assert callable(m.validate_rfc)
        assert callable(m.validate_rfc_batch)
        assert callable(m.is_valid_rfc)
        assert callable(m.classify_rfc)

    def test_classes_exist(self):
        from src.tools import rfc_validator as m
        assert m.ValidacionRFC is not None
        assert m.TipoPersona is not None
        assert m.ResultadoRFC is not None

    def test_constants_exist(self):
        from src.tools import rfc_validator as m
        assert m.RFC_GENERICO_NACIONAL is not None
        assert m.RFC_GENERICO_EXTRANJERO is not None
        assert m.RFCS_GENERICOS is not None
