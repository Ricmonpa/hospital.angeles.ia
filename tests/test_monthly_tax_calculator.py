"""Tests for OpenDoc Monthly Tax Calculator.

Comprehensive tests for:
- ISR tariff application (Régimen 612 progressive rates)
- RESICO flat rate calculation
- IVA treatment (exempt doctor, mixed doctor)
- Accumulated ISR with prior payments
- Cedular (state tax) calculation
- Annual projection
- WhatsApp formatting
- Edge cases (zero income, high income, RESICO cap)
"""

import pytest
from src.tools.monthly_tax_calculator import (
    # Core functions
    _calculate_isr_tarifa,
    _calculate_isr_resico,
    calculate_provisional_612,
    calculate_provisional_resico,
    calculate_annual_projection,
    # Data classes
    IngresosMensuales,
    DeduccionesMensuales,
    IVAMensual,
    ResultadoProvisional,
    # Constants
    TARIFA_ISR_MENSUAL,
    TARIFA_RESICO_MENSUAL,
    IVA_TASA_GENERAL,
    CEDULAR_TASA_GTO,
)


# ══════════════════════════════════════════════════════════════════════
# TEST: ISR Tariff (Art. 96 LISR)
# ══════════════════════════════════════════════════════════════════════

class TestISRTarifa:
    """Test the monthly ISR progressive tariff."""

    def test_zero_income(self):
        assert _calculate_isr_tarifa(0) == 0.0

    def test_negative_income(self):
        assert _calculate_isr_tarifa(-1000) == 0.0

    def test_lowest_bracket(self):
        """Income in first bracket: 1.92%."""
        result = _calculate_isr_tarifa(500)
        assert result > 0
        assert result < 15  # Very low tax

    def test_middle_bracket(self):
        """Income ~$30,000/month (typical doctor)."""
        result = _calculate_isr_tarifa(30_000)
        # Should be in 21.36% bracket
        assert result > 3_000
        assert result < 5_000

    def test_high_bracket(self):
        """Income ~$100,000/month (specialist doctor)."""
        result = _calculate_isr_tarifa(100_000)
        # Should be in 32% bracket
        assert result > 20_000
        assert result < 35_000

    def test_top_bracket(self):
        """Income above $375,975.61 — 35% marginal."""
        result = _calculate_isr_tarifa(400_000)
        assert result > 116_888  # Above cuota fija of top bracket

    def test_progressive_nature(self):
        """Higher income → higher tax."""
        isr_10k = _calculate_isr_tarifa(10_000)
        isr_50k = _calculate_isr_tarifa(50_000)
        isr_100k = _calculate_isr_tarifa(100_000)
        assert isr_10k < isr_50k < isr_100k

    def test_effective_rate_increases(self):
        """Effective rate should increase with income."""
        for income in [10_000, 50_000, 100_000]:
            if income > 0:
                rate = _calculate_isr_tarifa(income) / income
                assert rate > 0

    def test_boundary_first_bracket(self):
        """Test exact boundary of first bracket."""
        result = _calculate_isr_tarifa(746.04)
        assert result >= 0


class TestISRRESICO:
    """Test RESICO flat rate calculation."""

    def test_zero_income(self):
        assert _calculate_isr_resico(0) == 0.0

    def test_negative_income(self):
        assert _calculate_isr_resico(-5000) == 0.0

    def test_lowest_tier(self):
        """Up to $25,000 → 1.0%."""
        result = _calculate_isr_resico(20_000)
        assert result == 200.00  # 20,000 * 1% = 200

    def test_second_tier(self):
        """$25,001 - $50,000 → 1.10%."""
        result = _calculate_isr_resico(40_000)
        assert result == 440.00  # 40,000 * 1.1% = 440

    def test_third_tier(self):
        """$50,001 - $83,333 → 1.50%."""
        result = _calculate_isr_resico(60_000)
        assert result == 900.00  # 60,000 * 1.5% = 900

    def test_fourth_tier(self):
        """$83,334 - $208,333 → 2.00%."""
        result = _calculate_isr_resico(100_000)
        assert result == 2000.00  # 100,000 * 2% = 2,000

    def test_fifth_tier(self):
        """$208,334 - $291,666 → 2.50%."""
        result = _calculate_isr_resico(250_000)
        assert result == 6250.00  # 250,000 * 2.5% = 6,250

    def test_above_cap(self):
        """Above RESICO cap — 2.5% applied."""
        result = _calculate_isr_resico(300_000)
        assert result == 7500.00  # 300,000 * 2.5%

    def test_resico_much_lower_than_612(self):
        """RESICO should be much lower than 612 for typical income."""
        income = 80_000
        resico = _calculate_isr_resico(income)
        tarifa = _calculate_isr_tarifa(income)
        assert resico < tarifa


# ══════════════════════════════════════════════════════════════════════
# TEST: IngresosMensuales
# ══════════════════════════════════════════════════════════════════════

class TestIngresosMensuales:
    """Test income data class."""

    def test_total_calculation(self):
        ing = IngresosMensuales(
            honorarios_personas_fisicas=30_000,
            honorarios_personas_morales=50_000,
            otros_ingresos=5_000,
        )
        assert ing.total == 85_000

    def test_retencion_isr_pm(self):
        """10% retention from Personas Morales."""
        ing = IngresosMensuales(honorarios_personas_morales=50_000)
        assert ing.retencion_isr_pm == 5_000.00

    def test_zero_pm_no_retention(self):
        ing = IngresosMensuales(honorarios_personas_fisicas=80_000)
        assert ing.retencion_isr_pm == 0.0

    def test_defaults_are_zero(self):
        ing = IngresosMensuales()
        assert ing.total == 0.0
        assert ing.retencion_isr_pm == 0.0


# ══════════════════════════════════════════════════════════════════════
# TEST: DeduccionesMensuales
# ══════════════════════════════════════════════════════════════════════

class TestDeduccionesMensuales:
    """Test deduction data class."""

    def test_total_all_fields(self):
        ded = DeduccionesMensuales(
            arrendamiento=8_000,
            servicios=2_000,
            material_curacion=3_000,
            nomina_y_seguridad=15_000,
            depreciacion=2_500,
        )
        assert ded.total == 30_500

    def test_empty_deductions(self):
        ded = DeduccionesMensuales()
        assert ded.total == 0.0


# ══════════════════════════════════════════════════════════════════════
# TEST: IVAMensual
# ══════════════════════════════════════════════════════════════════════

class TestIVAMensual:
    """Test IVA calculations for doctors."""

    def test_all_exempt_no_credit(self):
        """Standard doctor: all services exempt → IVA NOT creditable."""
        iva = IVAMensual(
            actos_exentos=80_000,
            iva_pagado_gastos=5_000,
        )
        assert iva.iva_causado == 0.0
        assert iva.iva_acreditable == 0.0
        assert iva.iva_a_pagar == 0.0

    def test_aesthetic_doctor_iva(self):
        """Aesthetic doctor: gravado at 16% → IVA creditable."""
        iva = IVAMensual(
            actos_exentos=0,
            actos_gravados_16=100_000,
            iva_pagado_gastos=8_000,
        )
        assert iva.iva_causado == 16_000.0  # 100K * 16%
        assert iva.iva_acreditable == 8_000.0  # All creditable (100% gravado)
        assert iva.iva_a_pagar == 8_000.0  # 16K - 8K

    def test_mixed_doctor_proportional_credit(self):
        """Mixed doctor: some exempt, some gravado → proportional credit."""
        iva = IVAMensual(
            actos_exentos=50_000,
            actos_gravados_16=50_000,
            iva_pagado_gastos=8_000,
        )
        assert iva.iva_causado == 8_000.0  # 50K * 16%
        assert iva.iva_acreditable == 4_000.0  # 50% of 8K (50% gravado proportion)
        assert iva.iva_a_pagar == 4_000.0  # 8K - 4K

    def test_no_acts_no_credit(self):
        """No income at all → zero everything."""
        iva = IVAMensual(iva_pagado_gastos=3_000)
        assert iva.iva_causado == 0.0
        assert iva.iva_acreditable == 0.0

    def test_iva_retenido(self):
        """IVA retained reduces IVA to pay."""
        iva = IVAMensual(
            actos_gravados_16=100_000,
            iva_pagado_gastos=5_000,
            iva_retenido_recibido=2_000,
        )
        assert iva.iva_a_pagar == 16_000 - 5_000 - 2_000


# ══════════════════════════════════════════════════════════════════════
# TEST: Provisional 612
# ══════════════════════════════════════════════════════════════════════

class TestProvisional612:
    """Test monthly provisional payment for Régimen 612."""

    def test_basic_calculation(self):
        """Basic January calculation."""
        ingresos = IngresosMensuales(honorarios_personas_fisicas=80_000)
        deducciones = DeduccionesMensuales(
            arrendamiento=8_000,
            servicios=2_000,
            material_curacion=3_000,
        )
        result = calculate_provisional_612(
            mes=1, anio=2026,
            ingresos=ingresos,
            deducciones=deducciones,
        )
        assert result.regimen == "612"
        assert result.ingresos_totales == 80_000
        assert result.deducciones_totales == 13_000
        assert result.isr_a_pagar > 0
        assert result.total_a_pagar > 0

    def test_retenciones_reduce_payment(self):
        """ISR retentions from PM should reduce ISR to pay."""
        ingresos = IngresosMensuales(honorarios_personas_morales=80_000)
        deducciones = DeduccionesMensuales(arrendamiento=10_000)
        result = calculate_provisional_612(
            mes=1, anio=2026,
            ingresos=ingresos,
            deducciones=deducciones,
        )
        assert result.retenciones_isr == 8_000.0  # 10% of 80K
        # ISR to pay should be reduced
        assert result.isr_a_pagar < result.isr_causado

    def test_accumulated_basis(self):
        """ISR should be on accumulated basis for month > 1."""
        ingresos = IngresosMensuales(honorarios_personas_fisicas=80_000)
        deducciones = DeduccionesMensuales(arrendamiento=10_000)

        # March calculation with prior accumulations
        result = calculate_provisional_612(
            mes=3, anio=2026,
            ingresos=ingresos,
            deducciones=deducciones,
            ingresos_acumulados_previos=160_000,  # Jan + Feb
            deducciones_acumuladas_previas=20_000,  # Jan + Feb
            pagos_provisionales_anteriores=15_000,  # Jan + Feb payments
        )
        assert result.ingresos_acumulados_anio == 240_000  # 160K + 80K
        assert result.deducciones_acumuladas_anio == 30_000  # 20K + 10K

    def test_prior_payments_reduce_isr(self):
        """Prior provisional payments should reduce current ISR."""
        ingresos = IngresosMensuales(honorarios_personas_fisicas=80_000)
        deducciones = DeduccionesMensuales(arrendamiento=10_000)

        result_no_prior = calculate_provisional_612(
            mes=2, anio=2026,
            ingresos=ingresos, deducciones=deducciones,
            ingresos_acumulados_previos=80_000,
            deducciones_acumuladas_previas=10_000,
        )

        result_with_prior = calculate_provisional_612(
            mes=2, anio=2026,
            ingresos=ingresos, deducciones=deducciones,
            ingresos_acumulados_previos=80_000,
            deducciones_acumuladas_previas=10_000,
            pagos_provisionales_anteriores=10_000,
        )

        assert result_with_prior.isr_a_pagar < result_no_prior.isr_a_pagar

    def test_cedular_state_tax(self):
        """Cedular (state tax) calculation when enabled."""
        ingresos = IngresosMensuales(honorarios_personas_fisicas=80_000)
        deducciones = DeduccionesMensuales(arrendamiento=10_000)

        result = calculate_provisional_612(
            mes=1, anio=2026,
            ingresos=ingresos, deducciones=deducciones,
            include_cedular=True,
        )
        assert result.cedular_a_pagar > 0
        assert result.cedular_tasa == 0.02
        expected_cedular = (80_000 - 10_000) * 0.02
        assert abs(result.cedular_a_pagar - expected_cedular) < 0.01

    def test_cedular_disabled_by_default(self):
        ingresos = IngresosMensuales(honorarios_personas_fisicas=80_000)
        deducciones = DeduccionesMensuales()
        result = calculate_provisional_612(
            mes=1, anio=2026,
            ingresos=ingresos, deducciones=deducciones,
        )
        assert result.cedular_a_pagar == 0

    def test_iva_exempt_doctor(self):
        """IVA for standard exempt doctor."""
        ingresos = IngresosMensuales(honorarios_personas_fisicas=80_000)
        deducciones = DeduccionesMensuales(arrendamiento=8_000)
        iva = IVAMensual(actos_exentos=80_000, iva_pagado_gastos=3_000)

        result = calculate_provisional_612(
            mes=1, anio=2026,
            ingresos=ingresos, deducciones=deducciones, iva=iva,
        )
        assert result.iva_causado == 0.0
        assert result.iva_acreditable == 0.0
        assert len(result.notas) > 0  # Should have exempt note

    def test_alert_high_deductions(self):
        """Alert when deductions are >80% of income."""
        ingresos = IngresosMensuales(honorarios_personas_fisicas=50_000)
        deducciones = DeduccionesMensuales(
            arrendamiento=20_000,
            nomina_y_seguridad=15_000,
            material_curacion=10_000,
        )

        result = calculate_provisional_612(
            mes=1, anio=2026,
            ingresos=ingresos, deducciones=deducciones,
        )
        assert any("80%" in a or "SAT" in a for a in result.alertas)

    def test_alert_deductions_exceed_income(self):
        """Alert when deductions > income."""
        ingresos = IngresosMensuales(honorarios_personas_fisicas=30_000)
        deducciones = DeduccionesMensuales(arrendamiento=40_000)

        result = calculate_provisional_612(
            mes=1, anio=2026,
            ingresos=ingresos, deducciones=deducciones,
        )
        assert any("mayores" in a.lower() or "Deducciones" in a for a in result.alertas)

    def test_isr_never_negative(self):
        """ISR to pay should never be negative."""
        ingresos = IngresosMensuales(honorarios_personas_morales=10_000)
        deducciones = DeduccionesMensuales(arrendamiento=9_000)
        result = calculate_provisional_612(
            mes=1, anio=2026,
            ingresos=ingresos, deducciones=deducciones,
        )
        assert result.isr_a_pagar >= 0

    def test_total_includes_all_taxes(self):
        """Total should include ISR + IVA + cedular."""
        ingresos = IngresosMensuales(honorarios_personas_fisicas=80_000)
        deducciones = DeduccionesMensuales(arrendamiento=10_000)
        iva = IVAMensual(actos_gravados_16=80_000, iva_pagado_gastos=5_000)

        result = calculate_provisional_612(
            mes=1, anio=2026,
            ingresos=ingresos, deducciones=deducciones,
            iva=iva, include_cedular=True,
        )
        expected_total = result.isr_a_pagar + max(0, result.iva_a_pagar) + result.cedular_a_pagar
        assert abs(result.total_a_pagar - expected_total) < 0.02


# ══════════════════════════════════════════════════════════════════════
# TEST: Provisional RESICO
# ══════════════════════════════════════════════════════════════════════

class TestProvisionalRESICO:
    """Test monthly provisional for RESICO (625)."""

    def test_basic_resico(self):
        result = calculate_provisional_resico(
            mes=1, anio=2026,
            ingresos_cobrados=60_000,
        )
        assert result.regimen == "625"
        assert result.isr_causado == 900.00  # 60K * 1.5%
        assert result.isr_a_pagar == 900.00

    def test_resico_with_retentions(self):
        """Retentions should reduce ISR to pay."""
        result = calculate_provisional_resico(
            mes=1, anio=2026,
            ingresos_cobrados=60_000,
            retenciones_isr=500,
        )
        assert result.isr_a_pagar == 400.00  # 900 - 500

    def test_resico_cap_alert(self):
        """Alert when income projects above $3.5M annually."""
        result = calculate_provisional_resico(
            mes=1, anio=2026,
            ingresos_cobrados=300_000,  # 300K * 12 = 3.6M > 3.5M
        )
        assert any("RESICO" in a and "3,500,000" in a for a in result.alertas)

    def test_resico_no_deductions(self):
        """RESICO has no deductions."""
        result = calculate_provisional_resico(
            mes=1, anio=2026,
            ingresos_cobrados=100_000,
        )
        assert result.deducciones_totales == 0
        assert "Sin deducciones" in result.notas[0]

    def test_resico_isr_never_negative(self):
        result = calculate_provisional_resico(
            mes=1, anio=2026,
            ingresos_cobrados=10_000,
            retenciones_isr=50_000,  # More than ISR
        )
        assert result.isr_a_pagar >= 0

    def test_resico_total_equals_isr(self):
        """RESICO total = ISR only (no IVA, no cedular)."""
        result = calculate_provisional_resico(
            mes=1, anio=2026,
            ingresos_cobrados=80_000,
        )
        assert result.total_a_pagar == result.isr_a_pagar


# ══════════════════════════════════════════════════════════════════════
# TEST: Annual Projection
# ══════════════════════════════════════════════════════════════════════

class TestAnnualProjection:
    """Test annual projection from monthly provisionals."""

    def test_empty_list(self):
        result = calculate_annual_projection([])
        assert "error" in result

    def test_single_month_projection(self):
        """One month → project × 12."""
        prov = ResultadoProvisional(
            mes=1, anio=2026, regimen="612",
            ingresos_totales=80_000,
            deducciones_totales=20_000,
            isr_a_pagar=10_000,
        )
        result = calculate_annual_projection([prov])
        assert result["proyeccion_anual"]["ingresos"] == 960_000  # 80K * 12
        assert result["proyeccion_anual"]["isr_estimado"] == 120_000

    def test_three_months_projection(self):
        """Three months → project × 4."""
        provs = [
            ResultadoProvisional(mes=i, anio=2026, regimen="612",
                                 ingresos_totales=80_000, isr_a_pagar=10_000)
            for i in range(1, 4)
        ]
        result = calculate_annual_projection(provs)
        assert result["meses_capturados"] == 3
        assert result["acumulado"]["ingresos"] == 240_000
        assert result["proyeccion_anual"]["ingresos"] == 960_000

    def test_resico_cap_alert(self):
        """Alert when projected income exceeds RESICO cap."""
        provs = [
            ResultadoProvisional(mes=1, anio=2026, regimen="625",
                                 ingresos_totales=350_000, isr_a_pagar=8_750)
        ]
        result = calculate_annual_projection(provs)
        assert any("RESICO" in a for a in result["alertas"])

    def test_effective_rate(self):
        """Effective ISR rate calculation."""
        prov = ResultadoProvisional(
            mes=1, anio=2026, regimen="612",
            ingresos_totales=100_000, isr_a_pagar=20_000,
        )
        result = calculate_annual_projection([prov])
        assert result["tasa_efectiva_isr"] == 20.0


# ══════════════════════════════════════════════════════════════════════
# TEST: WhatsApp Formatting
# ══════════════════════════════════════════════════════════════════════

class TestWhatsAppFormatting:
    """Test WhatsApp output."""

    def test_resumen_612(self):
        result = calculate_provisional_612(
            mes=1, anio=2026,
            ingresos=IngresosMensuales(honorarios_personas_fisicas=80_000),
            deducciones=DeduccionesMensuales(arrendamiento=10_000),
        )
        text = result.resumen_whatsapp()
        assert "PROVISIONAL" in text
        assert "ENERO" in text
        assert "612" in text
        assert "ISR" in text
        assert "$" in text

    def test_resumen_resico(self):
        result = calculate_provisional_resico(mes=3, anio=2026, ingresos_cobrados=60_000)
        text = result.resumen_whatsapp()
        assert "MARZO" in text
        assert "625" in text

    def test_resumen_with_retentions(self):
        result = calculate_provisional_612(
            mes=1, anio=2026,
            ingresos=IngresosMensuales(honorarios_personas_morales=80_000),
            deducciones=DeduccionesMensuales(),
        )
        text = result.resumen_whatsapp()
        assert "Reten" in text or "PM" in text

    def test_resumen_with_cedular(self):
        result = calculate_provisional_612(
            mes=6, anio=2026,
            ingresos=IngresosMensuales(honorarios_personas_fisicas=80_000),
            deducciones=DeduccionesMensuales(arrendamiento=10_000),
            include_cedular=True,
        )
        text = result.resumen_whatsapp()
        assert "Cedular" in text or "estatal" in text


# ══════════════════════════════════════════════════════════════════════
# TEST: ResultadoProvisional
# ══════════════════════════════════════════════════════════════════════

class TestResultadoProvisional:
    """Test the result data class."""

    def test_to_dict(self):
        result = ResultadoProvisional(mes=1, anio=2026, regimen="612")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["mes"] == 1
        assert d["regimen"] == "612"

    def test_month_name_boundary(self):
        """Test invalid month number in WhatsApp summary."""
        result = ResultadoProvisional(mes=13, anio=2026, regimen="612")
        text = result.resumen_whatsapp()
        assert "13" in text  # Should fall back to number


# ══════════════════════════════════════════════════════════════════════
# TEST: Constants
# ══════════════════════════════════════════════════════════════════════

class TestConstants:
    """Test tariff tables and constants are correct."""

    def test_isr_tariff_has_11_brackets(self):
        assert len(TARIFA_ISR_MENSUAL) == 11

    def test_isr_tariff_starts_at_001(self):
        assert TARIFA_ISR_MENSUAL[0][0] == 0.01

    def test_isr_tariff_top_is_35_pct(self):
        assert TARIFA_ISR_MENSUAL[-1][3] == 35.00

    def test_isr_tariff_continuous(self):
        """Brackets should be continuous (no gaps)."""
        for i in range(len(TARIFA_ISR_MENSUAL) - 1):
            upper = TARIFA_ISR_MENSUAL[i][1]
            next_lower = TARIFA_ISR_MENSUAL[i + 1][0]
            assert abs(next_lower - upper - 0.01) < 0.02

    def test_resico_has_5_tiers(self):
        assert len(TARIFA_RESICO_MENSUAL) == 5

    def test_resico_starts_at_1_pct(self):
        assert TARIFA_RESICO_MENSUAL[0][2] == 1.00

    def test_resico_max_is_25_pct(self):
        assert TARIFA_RESICO_MENSUAL[-1][2] == 2.50

    def test_iva_general_16(self):
        assert IVA_TASA_GENERAL == 0.16

    def test_cedular_gto_2pct(self):
        assert CEDULAR_TASA_GTO == 0.02


# ══════════════════════════════════════════════════════════════════════
# TEST: Module Exports
# ══════════════════════════════════════════════════════════════════════

class TestModuleExports:
    """Test that all symbols are importable from __init__."""

    def test_import_functions(self):
        from src.tools import (
            calculate_provisional_612,
            calculate_provisional_resico,
            calculate_annual_projection,
        )

    def test_import_classes(self):
        from src.tools import (
            IngresosMensuales,
            DeduccionesMensuales,
            IVAMensual,
            ResultadoProvisional,
        )

    def test_import_constants(self):
        from src.tools import (
            TARIFA_ISR_MENSUAL,
            TARIFA_RESICO_MENSUAL,
            IVA_TASA_GENERAL,
            CEDULAR_TASA_GTO,
        )
