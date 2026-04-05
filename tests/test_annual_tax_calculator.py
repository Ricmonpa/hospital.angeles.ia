"""Tests for OpenDoc Annual Tax Declaration Calculator.

Comprehensive tests for:
- Annual ISR tariff application (Art. 152 LISR — 612 progressive)
- Annual RESICO flat rate (Art. 113-F LISR)
- IngresosAnuales properties (total_ingresos, total_retenciones)
- DeduccionesAnuales total_operativas
- DeduccionesPersonales with tope calculation (15% income or 5 UMA)
- calculate_annual_612 (basic, with deductions, personal deductions, retentions)
- calculate_annual_resico (basic, cap alert, with salary)
- compare_annual_regimes (612 vs RESICO recommendation)
- ISR a cargo vs a favor scenarios
- WhatsApp formatting (resumen_whatsapp)
- ResultadoAnual.to_dict()
- Tariff constants validation (11 brackets for annual, 5 for RESICO)
- Module exports from src.tools
"""

import pytest
from src.tools.annual_tax_calculator import (
    # Core functions
    _calculate_isr_anual_tarifa,
    _calculate_isr_resico_anual,
    calculate_annual_612,
    calculate_annual_resico,
    compare_annual_regimes,
    # Data classes
    IngresosAnuales,
    DeduccionesAnuales,
    DeduccionesPersonales,
    ResultadoAnual,
    # Constants
    TARIFA_ISR_ANUAL,
    TARIFA_RESICO_ANUAL,
    UMA_ANUAL_REAL_2026,
    TOPE_DEDUCCIONES_PERSONALES_UMAS,
)


# ======================================================================
# TEST: Annual ISR Tariff (Art. 152 LISR)
# ======================================================================

class TestISRAnualTarifa:
    """Test the annual ISR progressive tariff."""

    def test_zero_income(self):
        assert _calculate_isr_anual_tarifa(0) == 0.0

    def test_negative_income(self):
        assert _calculate_isr_anual_tarifa(-50_000) == 0.0

    def test_lowest_bracket(self):
        """Income in first bracket: 0.01 - 8,952.49 at 1.92%."""
        result = _calculate_isr_anual_tarifa(5_000)
        # cuota_fija=0, excedente=4999.99, tasa=1.92%
        expected = round(0.00 + (5_000 - 0.01) * 1.92 / 100, 2)
        assert result == expected

    def test_second_bracket(self):
        """Income in second bracket: 8,952.50 - 75,984.55 at 6.40%."""
        result = _calculate_isr_anual_tarifa(50_000)
        excedente = 50_000 - 8_952.50
        expected = round(171.88 + excedente * 6.40 / 100, 2)
        assert result == expected

    def test_middle_bracket(self):
        """Income ~$500,000/year (typical doctor)."""
        result = _calculate_isr_anual_tarifa(500_000)
        # Should be in 23.52% bracket (374,837.89 - 590,795.99)
        excedente = 500_000 - 374_837.89
        expected = round(48_061.74 + excedente * 23.52 / 100, 2)
        assert result == expected

    def test_high_bracket(self):
        """Income ~$1,200,000/year (specialist doctor)."""
        result = _calculate_isr_anual_tarifa(1_200_000)
        # Should be in 32% bracket (1,127,926.85 - 1,503,902.46)
        excedente = 1_200_000 - 1_127_926.85
        expected = round(260_107.00 + excedente * 32.00 / 100, 2)
        assert result == expected

    def test_top_bracket(self):
        """Income above $4,511,707.38 -- 35% marginal."""
        result = _calculate_isr_anual_tarifa(5_000_000)
        excedente = 5_000_000 - 4_511_707.38
        expected = round(1_402_976.52 + excedente * 35.00 / 100, 2)
        assert result == expected

    def test_progressive_nature(self):
        """Higher income -> higher tax."""
        isr_100k = _calculate_isr_anual_tarifa(100_000)
        isr_500k = _calculate_isr_anual_tarifa(500_000)
        isr_1m = _calculate_isr_anual_tarifa(1_000_000)
        assert isr_100k < isr_500k < isr_1m

    def test_effective_rate_increases(self):
        """Effective rate should increase with income."""
        rates = []
        for income in [100_000, 500_000, 1_000_000, 3_000_000]:
            isr = _calculate_isr_anual_tarifa(income)
            rates.append(isr / income)
        for i in range(len(rates) - 1):
            assert rates[i] < rates[i + 1]

    def test_boundary_first_bracket(self):
        """Test exact boundary of first bracket."""
        result = _calculate_isr_anual_tarifa(8_952.49)
        assert result >= 0

    def test_above_max_bracket_uses_last(self):
        """Income beyond all defined brackets still uses 35%."""
        result = _calculate_isr_anual_tarifa(10_000_000)
        assert result > 0
        # Should use last bracket's cuota + 35%
        excedente = 10_000_000 - 4_511_707.38
        expected = round(1_402_976.52 + excedente * 35.00 / 100, 2)
        assert result == expected

    def test_very_small_positive_income(self):
        """Smallest possible income: $0.01."""
        result = _calculate_isr_anual_tarifa(0.01)
        assert result >= 0.0


# ======================================================================
# TEST: Annual RESICO Tariff (Art. 113-F LISR)
# ======================================================================

class TestISRRESICOAnual:
    """Test RESICO annual flat rate calculation."""

    def test_zero_income(self):
        assert _calculate_isr_resico_anual(0) == 0.0

    def test_negative_income(self):
        assert _calculate_isr_resico_anual(-100_000) == 0.0

    def test_first_tier(self):
        """Up to $300,000 -> 1.00%."""
        result = _calculate_isr_resico_anual(200_000)
        assert result == round(200_000 * 1.00 / 100, 2)

    def test_second_tier(self):
        """$300,000.01 - $600,000 -> 1.10%."""
        result = _calculate_isr_resico_anual(500_000)
        assert result == round(500_000 * 1.10 / 100, 2)

    def test_third_tier(self):
        """$600,000.01 - $1,000,000 -> 1.50%."""
        result = _calculate_isr_resico_anual(800_000)
        assert result == round(800_000 * 1.50 / 100, 2)

    def test_fourth_tier(self):
        """$1,000,000.01 - $2,500,000 -> 2.00%."""
        result = _calculate_isr_resico_anual(1_500_000)
        assert result == round(1_500_000 * 2.00 / 100, 2)

    def test_fifth_tier(self):
        """$2,500,000.01 - $3,500,000 -> 2.50%."""
        result = _calculate_isr_resico_anual(3_000_000)
        assert result == round(3_000_000 * 2.50 / 100, 2)

    def test_above_cap(self):
        """Above RESICO cap -- 2.5% applied."""
        result = _calculate_isr_resico_anual(4_000_000)
        assert result == round(4_000_000 * 2.50 / 100, 2)

    def test_resico_much_lower_than_612(self):
        """RESICO should be much lower than 612 for typical income."""
        income = 600_000
        resico = _calculate_isr_resico_anual(income)
        tarifa = _calculate_isr_anual_tarifa(income)
        assert resico < tarifa

    def test_boundary_first_tier(self):
        """Exact boundary of first tier: $300,000."""
        result = _calculate_isr_resico_anual(300_000)
        assert result == round(300_000 * 1.00 / 100, 2)


# ======================================================================
# TEST: IngresosAnuales
# ======================================================================

class TestIngresosAnuales:
    """Test annual income data class."""

    def test_total_ingresos_all_sources(self):
        ing = IngresosAnuales(
            honorarios_facturados_612=500_000,
            ingresos_cobrados_resico=300_000,
            sueldos_y_salarios=200_000,
            intereses_bancarios=10_000,
        )
        assert ing.total_ingresos == 1_010_000

    def test_total_retenciones_all_sources(self):
        ing = IngresosAnuales(
            retenciones_isr_612=50_000,
            retenciones_isr_resico=5_000,
            isr_retenido_salarios=30_000,
            isr_retenido_intereses=1_000,
        )
        assert ing.total_retenciones_isr == 86_000

    def test_defaults_are_zero(self):
        ing = IngresosAnuales()
        assert ing.total_ingresos == 0.0
        assert ing.total_retenciones_isr == 0.0

    def test_single_source_612(self):
        ing = IngresosAnuales(honorarios_facturados_612=800_000)
        assert ing.total_ingresos == 800_000
        assert ing.total_retenciones_isr == 0.0

    def test_single_source_resico(self):
        ing = IngresosAnuales(
            ingresos_cobrados_resico=600_000,
            retenciones_isr_resico=7_200,
        )
        assert ing.total_ingresos == 600_000
        assert ing.total_retenciones_isr == 7_200


# ======================================================================
# TEST: DeduccionesAnuales
# ======================================================================

class TestDeduccionesAnuales:
    """Test annual deduction data class."""

    def test_total_operativas_all_fields(self):
        ded = DeduccionesAnuales(
            arrendamiento=96_000,
            servicios=24_000,
            material_curacion=36_000,
            nomina_y_seguridad=180_000,
            depreciacion=30_000,
            seguros=12_000,
            educacion_medica=15_000,
            honorarios_externos=10_000,
            publicidad=8_000,
            software=6_000,
            limpieza_mantenimiento=5_000,
            vehiculo=20_000,
            otros_deducibles=3_000,
        )
        expected = (96_000 + 24_000 + 36_000 + 180_000 + 30_000 +
                    12_000 + 15_000 + 10_000 + 8_000 + 6_000 +
                    5_000 + 20_000 + 3_000)
        assert ded.total_operativas == expected

    def test_empty_deductions(self):
        ded = DeduccionesAnuales()
        assert ded.total_operativas == 0.0

    def test_partial_deductions(self):
        ded = DeduccionesAnuales(arrendamiento=96_000, servicios=24_000)
        assert ded.total_operativas == 120_000


# ======================================================================
# TEST: DeduccionesPersonales (Art. 151 LISR)
# ======================================================================

class TestDeduccionesPersonales:
    """Test personal deductions with cap calculation."""

    def test_total_antes_tope(self):
        pers = DeduccionesPersonales(
            gastos_medicos=50_000,
            primas_seguro_gmm=30_000,
            colegiaturas=20_000,
        )
        assert pers.total_antes_tope == 100_000

    def test_total_con_tope_under_limit(self):
        """Personal deductions below both caps -> full amount."""
        pers = DeduccionesPersonales(gastos_medicos=50_000)
        # 15% of 1,000,000 = 150,000; 5 UMA = 206,480.50
        # tope = min(150,000, 206,480.50) = 150,000
        # 50,000 < 150,000 -> returns 50,000
        result = pers.total_con_tope(1_000_000)
        assert result == 50_000

    def test_total_con_tope_percentage_cap(self):
        """15% of income is the binding constraint."""
        pers = DeduccionesPersonales(gastos_medicos=200_000)
        # 15% of 500,000 = 75,000; 5 UMA = 206,480.50
        # tope = min(75,000, 206,480.50) = 75,000
        # 200,000 > 75,000 -> returns 75,000
        result = pers.total_con_tope(500_000)
        assert result == 75_000

    def test_total_con_tope_uma_cap(self):
        """5 UMA annual is the binding constraint for high income."""
        pers = DeduccionesPersonales(gastos_medicos=300_000)
        tope_umas = UMA_ANUAL_REAL_2026 * TOPE_DEDUCCIONES_PERSONALES_UMAS
        # 15% of 5,000,000 = 750,000; 5 UMA = 206,480.50
        # tope = min(750,000, 206,480.50) = 206,480.50
        # 300,000 > 206,480.50 -> returns 206,480.50
        result = pers.total_con_tope(5_000_000)
        assert result == tope_umas

    def test_total_con_tope_zero_income(self):
        """Zero income -> tope is zero."""
        pers = DeduccionesPersonales(gastos_medicos=50_000)
        result = pers.total_con_tope(0)
        assert result == 0.0

    def test_all_personal_deduction_fields(self):
        pers = DeduccionesPersonales(
            gastos_medicos=10_000,
            gastos_hospitalarios=5_000,
            lentes_opticos=2_500,
            primas_seguro_gmm=15_000,
            gastos_funerarios=3_000,
            donativos=5_000,
            intereses_hipotecarios=20_000,
            aportaciones_retiro=10_000,
            colegiaturas=14_000,
            transporte_escolar=4_000,
        )
        expected = (10_000 + 5_000 + 2_500 + 15_000 + 3_000 +
                    5_000 + 20_000 + 10_000 + 14_000 + 4_000)
        assert pers.total_antes_tope == expected

    def test_empty_personal_deductions(self):
        pers = DeduccionesPersonales()
        assert pers.total_antes_tope == 0.0
        assert pers.total_con_tope(1_000_000) == 0.0


# ======================================================================
# TEST: calculate_annual_612
# ======================================================================

class TestCalculateAnnual612:
    """Test annual ISR calculation for Regimen 612."""

    def test_basic_calculation(self):
        """Basic annual calculation with only honorarios."""
        ingresos = IngresosAnuales(honorarios_facturados_612=960_000)
        deducciones = DeduccionesAnuales(arrendamiento=96_000, servicios=24_000)

        result = calculate_annual_612(
            anio=2025,
            ingresos=ingresos,
            deducciones=deducciones,
        )
        assert result.regimen == "612"
        assert result.anio == 2025
        assert result.ingresos_totales == 960_000
        assert result.deducciones_operativas == 120_000
        assert result.base_gravable_612 == 840_000
        assert result.isr_anual_612 > 0
        assert result.isr_total_ejercicio == result.isr_anual_612

    def test_with_operational_deductions(self):
        """Deductions should reduce base gravable."""
        ingresos = IngresosAnuales(honorarios_facturados_612=960_000)

        ded_none = DeduccionesAnuales()
        ded_some = DeduccionesAnuales(arrendamiento=96_000, nomina_y_seguridad=180_000)

        r_none = calculate_annual_612(2025, ingresos, ded_none)
        r_some = calculate_annual_612(2025, ingresos, ded_some)

        assert r_some.base_gravable_612 < r_none.base_gravable_612
        assert r_some.isr_anual_612 < r_none.isr_anual_612

    def test_with_personal_deductions(self):
        """Personal deductions should further reduce ISR."""
        ingresos = IngresosAnuales(honorarios_facturados_612=960_000)
        deducciones = DeduccionesAnuales(arrendamiento=96_000)
        personales = DeduccionesPersonales(
            gastos_medicos=30_000,
            primas_seguro_gmm=20_000,
        )

        r_no_pers = calculate_annual_612(2025, ingresos, deducciones)
        r_with_pers = calculate_annual_612(2025, ingresos, deducciones, personales)

        assert r_with_pers.deducciones_personales > 0
        assert r_with_pers.isr_anual_612 < r_no_pers.isr_anual_612

    def test_personal_deductions_tope_applied(self):
        """Personal deductions exceeding tope should be capped."""
        ingresos = IngresosAnuales(honorarios_facturados_612=500_000)
        deducciones = DeduccionesAnuales()
        personales = DeduccionesPersonales(gastos_medicos=300_000)

        result = calculate_annual_612(2025, ingresos, deducciones, personales)

        # 15% of 500,000 = 75,000
        tope_umas = UMA_ANUAL_REAL_2026 * TOPE_DEDUCCIONES_PERSONALES_UMAS
        expected_tope = min(500_000 * 0.15, tope_umas)
        assert result.deducciones_personales == expected_tope
        assert result.tope_deducciones_personales == expected_tope
        # Alert about tope
        assert any("tope" in a.lower() or "exceden" in a.lower() for a in result.alertas)

    def test_with_retentions(self):
        """ISR retentions should reduce ISR a cargo."""
        ingresos = IngresosAnuales(
            honorarios_facturados_612=960_000,
            retenciones_isr_612=96_000,  # 10% of 960K
        )
        deducciones = DeduccionesAnuales(arrendamiento=96_000)

        result = calculate_annual_612(2025, ingresos, deducciones)
        assert result.retenciones_isr == 96_000
        # ISR a cargo should be less than total ISR
        assert result.isr_a_cargo < result.isr_total_ejercicio

    def test_with_provisional_payments(self):
        """Provisional payments should reduce ISR a cargo."""
        ingresos = IngresosAnuales(honorarios_facturados_612=960_000)
        deducciones = DeduccionesAnuales(arrendamiento=96_000)

        r_no_prov = calculate_annual_612(2025, ingresos, deducciones)
        r_with_prov = calculate_annual_612(
            2025, ingresos, deducciones, pagos_provisionales=100_000
        )

        assert r_with_prov.pagos_provisionales == 100_000
        assert r_with_prov.isr_a_cargo < r_no_prov.isr_a_cargo

    def test_isr_a_favor(self):
        """When retentions + provisionals exceed ISR, result is a favor."""
        ingresos = IngresosAnuales(
            honorarios_facturados_612=500_000,
            retenciones_isr_612=50_000,
        )
        deducciones = DeduccionesAnuales(
            arrendamiento=96_000,
            nomina_y_seguridad=180_000,
            material_curacion=36_000,
        )

        result = calculate_annual_612(
            2025, ingresos, deducciones, pagos_provisionales=100_000
        )

        # Large deductions + large provisional + retentions should produce a favor
        if result.isr_a_favor > 0:
            assert result.isr_a_cargo == 0
            assert any("favor" in n.lower() or "devoluc" in n.lower() for n in result.notas)

    def test_isr_a_cargo(self):
        """When ISR exceeds credits, result is a cargo."""
        ingresos = IngresosAnuales(honorarios_facturados_612=1_500_000)
        deducciones = DeduccionesAnuales(arrendamiento=96_000)

        result = calculate_annual_612(
            2025, ingresos, deducciones, pagos_provisionales=50_000
        )
        assert result.isr_a_cargo > 0
        assert result.isr_a_favor == 0

    def test_isr_never_negative(self):
        """ISR a cargo and a favor should never be negative."""
        ingresos = IngresosAnuales(honorarios_facturados_612=100_000)
        deducciones = DeduccionesAnuales(arrendamiento=200_000)

        result = calculate_annual_612(2025, ingresos, deducciones)
        assert result.isr_a_cargo >= 0
        assert result.isr_a_favor >= 0

    def test_base_gravable_never_negative(self):
        """Base gravable should be floored at zero."""
        ingresos = IngresosAnuales(honorarios_facturados_612=100_000)
        deducciones = DeduccionesAnuales(arrendamiento=200_000)

        result = calculate_annual_612(2025, ingresos, deducciones)
        assert result.base_gravable_612 >= 0

    def test_includes_salarios_in_acumulable(self):
        """Salarios should be added to acumulable income."""
        ingresos = IngresosAnuales(
            honorarios_facturados_612=500_000,
            sueldos_y_salarios=200_000,
        )
        deducciones = DeduccionesAnuales()

        result = calculate_annual_612(2025, ingresos, deducciones)
        assert result.ingresos_acumulables_612 == 700_000
        assert result.ingresos_salarios == 200_000

    def test_includes_intereses_in_acumulable(self):
        """Bank interest should be included in acumulable income."""
        ingresos = IngresosAnuales(
            honorarios_facturados_612=500_000,
            intereses_bancarios=10_000,
        )
        deducciones = DeduccionesAnuales()

        result = calculate_annual_612(2025, ingresos, deducciones)
        assert result.ingresos_acumulables_612 == 510_000

    def test_tasa_efectiva(self):
        """Effective tax rate should be calculated correctly."""
        ingresos = IngresosAnuales(honorarios_facturados_612=960_000)
        deducciones = DeduccionesAnuales()

        result = calculate_annual_612(2025, ingresos, deducciones)
        expected_rate = result.isr_anual_612 / 960_000 * 100
        assert abs(result.tasa_efectiva_isr - round(expected_rate, 2)) < 0.01

    def test_high_tasa_efectiva_alert(self):
        """Alert when effective rate exceeds 30%."""
        ingresos = IngresosAnuales(honorarios_facturados_612=5_000_000)
        deducciones = DeduccionesAnuales()

        result = calculate_annual_612(2025, ingresos, deducciones)
        # 5M income with no deductions should have high effective rate
        if result.tasa_efectiva_isr > 30:
            assert any("tasa efectiva" in a.lower() for a in result.alertas)

    def test_deduction_percentage_note(self):
        """Note about deduction percentage when deductions > 0."""
        ingresos = IngresosAnuales(honorarios_facturados_612=960_000)
        deducciones = DeduccionesAnuales(arrendamiento=96_000)

        result = calculate_annual_612(2025, ingresos, deducciones)
        assert any("Deducciones operativas" in n for n in result.notas)

    def test_zero_income(self):
        """Zero income should produce zero ISR."""
        ingresos = IngresosAnuales()
        deducciones = DeduccionesAnuales()

        result = calculate_annual_612(2025, ingresos, deducciones)
        assert result.isr_anual_612 == 0.0
        assert result.isr_a_cargo == 0.0


# ======================================================================
# TEST: calculate_annual_resico
# ======================================================================

class TestCalculateAnnualRESICO:
    """Test annual ISR calculation for RESICO (625)."""

    def test_basic_resico(self):
        """Basic annual RESICO calculation."""
        ingresos = IngresosAnuales(ingresos_cobrados_resico=800_000)

        result = calculate_annual_resico(2025, ingresos)
        assert result.regimen == "625"
        assert result.anio == 2025
        assert result.ingresos_totales == 800_000
        assert result.ingresos_resico == 800_000
        assert result.base_gravable_resico == 800_000
        # 800K in $600,001 - $1,000,000 -> 1.50%
        assert result.isr_anual_resico == round(800_000 * 1.50 / 100, 2)

    def test_resico_no_deductions_note(self):
        """RESICO should have a note about no operational deductions."""
        ingresos = IngresosAnuales(ingresos_cobrados_resico=500_000)
        result = calculate_annual_resico(2025, ingresos)
        assert any("Sin deducciones" in n or "RESICO" in n for n in result.notas)

    def test_cap_alert_above_3_5m(self):
        """Alert when income exceeds $3,500,000."""
        ingresos = IngresosAnuales(ingresos_cobrados_resico=4_000_000)
        result = calculate_annual_resico(2025, ingresos)
        assert any("3,500,000" in a for a in result.alertas)
        assert any("expuls" in a.lower() or "Expuls" in a for a in result.alertas)

    def test_no_cap_alert_under_3_5m(self):
        """No alert when income is under $3,500,000."""
        ingresos = IngresosAnuales(ingresos_cobrados_resico=3_000_000)
        result = calculate_annual_resico(2025, ingresos)
        assert not any("3,500,000" in a for a in result.alertas)

    def test_with_salary_income(self):
        """RESICO with salary income applies 612 tariff to salary portion."""
        ingresos = IngresosAnuales(
            ingresos_cobrados_resico=600_000,
            sueldos_y_salarios=200_000,
        )
        result = calculate_annual_resico(2025, ingresos)

        # ISR total should include both RESICO flat rate + salary tariff
        isr_resico_only = _calculate_isr_resico_anual(600_000)
        isr_salary_only = _calculate_isr_anual_tarifa(200_000)
        expected_total = round(isr_resico_only + isr_salary_only, 2)
        assert result.isr_total_ejercicio == expected_total

    def test_with_salary_and_personal_deductions(self):
        """Personal deductions should apply to salary portion in RESICO."""
        ingresos = IngresosAnuales(
            ingresos_cobrados_resico=600_000,
            sueldos_y_salarios=200_000,
        )
        personales = DeduccionesPersonales(gastos_medicos=30_000)

        r_no_pers = calculate_annual_resico(2025, ingresos)
        r_with_pers = calculate_annual_resico(2025, ingresos, personales)

        # With personal deductions on salary, total ISR should be lower
        assert r_with_pers.isr_total_ejercicio <= r_no_pers.isr_total_ejercicio

    def test_personal_deductions_only_salary_note(self):
        """Note about personal deductions applied to salary."""
        ingresos = IngresosAnuales(
            ingresos_cobrados_resico=600_000,
            sueldos_y_salarios=200_000,
        )
        personales = DeduccionesPersonales(gastos_medicos=30_000)

        result = calculate_annual_resico(2025, ingresos, personales)
        assert any("personales" in n.lower() and "salario" in n.lower() for n in result.notas)

    def test_personal_deductions_ignored_without_salary(self):
        """Personal deductions have no effect without salary income."""
        ingresos = IngresosAnuales(ingresos_cobrados_resico=600_000)
        personales = DeduccionesPersonales(gastos_medicos=30_000)

        r_no_pers = calculate_annual_resico(2025, ingresos)
        r_with_pers = calculate_annual_resico(2025, ingresos, personales)

        assert r_with_pers.isr_total_ejercicio == r_no_pers.isr_total_ejercicio

    def test_retentions_reduce_isr(self):
        """ISR retentions reduce ISR a cargo."""
        ingresos = IngresosAnuales(
            ingresos_cobrados_resico=600_000,
            retenciones_isr_resico=10_000,
        )
        result = calculate_annual_resico(2025, ingresos)
        assert result.retenciones_isr == 10_000
        assert result.isr_a_cargo < result.isr_total_ejercicio

    def test_provisional_payments_reduce_isr(self):
        """Provisional payments reduce ISR a cargo."""
        ingresos = IngresosAnuales(ingresos_cobrados_resico=600_000)

        r_no_prov = calculate_annual_resico(2025, ingresos)
        r_with_prov = calculate_annual_resico(2025, ingresos, pagos_provisionales=5_000)

        assert r_with_prov.isr_a_cargo < r_no_prov.isr_a_cargo

    def test_isr_a_favor_resico(self):
        """When retentions + provisionals exceed ISR, result is a favor."""
        ingresos = IngresosAnuales(
            ingresos_cobrados_resico=300_000,
            retenciones_isr_resico=5_000,
        )
        # 300K * 1% = 3,000 ISR; retentions 5,000 + provisionals 5,000 = 10,000
        result = calculate_annual_resico(
            2025, ingresos, pagos_provisionales=5_000
        )
        assert result.isr_a_favor > 0
        assert result.isr_a_cargo == 0

    def test_tasa_efectiva_resico(self):
        """Effective rate for RESICO should be very low."""
        ingresos = IngresosAnuales(ingresos_cobrados_resico=800_000)
        result = calculate_annual_resico(2025, ingresos)
        assert result.tasa_efectiva_isr < 5.0  # RESICO rates are 1-2.5%

    def test_zero_income_resico(self):
        """Zero income produces zero ISR."""
        ingresos = IngresosAnuales()
        result = calculate_annual_resico(2025, ingresos)
        assert result.isr_total_ejercicio == 0.0
        assert result.isr_a_cargo == 0.0


# ======================================================================
# TEST: compare_annual_regimes
# ======================================================================

class TestCompareAnnualRegimes:
    """Test 612 vs RESICO regime comparison."""

    def test_low_deductions_recommends_resico(self):
        """With low deductions, RESICO should be recommended."""
        ingresos = IngresosAnuales(honorarios_facturados_612=800_000)
        deducciones = DeduccionesAnuales(arrendamiento=20_000)

        result = compare_annual_regimes(2025, ingresos, deducciones)
        assert "RESICO" in result["regimen_recomendado"]
        assert result["isr_625"] < result["isr_612"]

    def test_high_deductions_recommends_612(self):
        """With very high deductions (>85%), 612 should be recommended."""
        ingresos = IngresosAnuales(honorarios_facturados_612=960_000)
        deducciones = DeduccionesAnuales(
            arrendamiento=96_000,
            nomina_y_seguridad=380_000,
            material_curacion=200_000,
            servicios=100_000,
            depreciacion=100_000,
        )

        result = compare_annual_regimes(2025, ingresos, deducciones)
        assert "612" in result["regimen_recomendado"]
        assert result["isr_612"] < result["isr_625"]

    def test_above_resico_cap_forces_612(self):
        """Income above $3.5M forces 612."""
        ingresos = IngresosAnuales(honorarios_facturados_612=4_000_000)
        deducciones = DeduccionesAnuales()

        result = compare_annual_regimes(2025, ingresos, deducciones)
        assert "612" in result["regimen_recomendado"]
        assert "obligatorio" in result["regimen_recomendado"]
        assert "3,500,000" in result["explicacion"]

    def test_returns_both_results(self):
        """Comparison should return results for both regimes."""
        ingresos = IngresosAnuales(honorarios_facturados_612=800_000)
        deducciones = DeduccionesAnuales(arrendamiento=50_000)

        result = compare_annual_regimes(2025, ingresos, deducciones)
        assert "resultado_612" in result
        assert "resultado_625" in result
        assert "regimen_recomendado" in result
        assert "ahorro_estimado" in result
        assert "explicacion" in result

    def test_ahorro_matches_difference(self):
        """Ahorro estimado should be the absolute difference."""
        ingresos = IngresosAnuales(honorarios_facturados_612=800_000)
        deducciones = DeduccionesAnuales(arrendamiento=50_000)

        result = compare_annual_regimes(2025, ingresos, deducciones)
        expected_ahorro = abs(result["isr_612"] - result["isr_625"])
        assert abs(result["ahorro_estimado"] - expected_ahorro) < 0.01

    def test_includes_tasas_efectivas(self):
        """Should include effective rates for both regimes."""
        ingresos = IngresosAnuales(honorarios_facturados_612=800_000)
        deducciones = DeduccionesAnuales()

        result = compare_annual_regimes(2025, ingresos, deducciones)
        assert "tasa_efectiva_612" in result
        assert "tasa_efectiva_625" in result
        assert result["tasa_efectiva_612"] > 0
        assert result["tasa_efectiva_625"] > 0

    def test_with_personal_deductions(self):
        """Personal deductions should affect 612 result."""
        ingresos = IngresosAnuales(honorarios_facturados_612=800_000)
        deducciones = DeduccionesAnuales(arrendamiento=50_000)
        personales = DeduccionesPersonales(gastos_medicos=50_000)

        r_no_pers = compare_annual_regimes(2025, ingresos, deducciones)
        r_with_pers = compare_annual_regimes(2025, ingresos, deducciones, personales)

        assert r_with_pers["isr_612"] <= r_no_pers["isr_612"]

    def test_resico_income_fallback(self):
        """If only 612 income provided, RESICO should use it as fallback."""
        ingresos = IngresosAnuales(honorarios_facturados_612=800_000)
        deducciones = DeduccionesAnuales()

        result = compare_annual_regimes(2025, ingresos, deducciones)
        # RESICO result should not be zero
        assert result["isr_625"] > 0


# ======================================================================
# TEST: ISR a cargo vs a favor scenarios
# ======================================================================

class TestISRCargoFavor:
    """Test ISR a cargo and a favor calculations."""

    def test_cargo_when_isr_exceeds_credits(self):
        """ISR a cargo when annual ISR > provisionals + retentions."""
        ingresos = IngresosAnuales(honorarios_facturados_612=1_200_000)
        deducciones = DeduccionesAnuales()

        result = calculate_annual_612(
            2025, ingresos, deducciones, pagos_provisionales=50_000
        )
        assert result.isr_a_cargo > 0
        assert result.isr_a_favor == 0.0

    def test_favor_when_credits_exceed_isr(self):
        """ISR a favor when provisionals + retentions > annual ISR."""
        ingresos = IngresosAnuales(
            honorarios_facturados_612=500_000,
            retenciones_isr_612=50_000,
        )
        deducciones = DeduccionesAnuales(
            arrendamiento=96_000,
            nomina_y_seguridad=180_000,
        )

        result = calculate_annual_612(
            2025, ingresos, deducciones, pagos_provisionales=100_000
        )
        # With heavy deductions and large credits, expect a favor
        if result.isr_a_favor > 0:
            assert result.isr_a_cargo == 0.0

    def test_exact_balance(self):
        """When ISR exactly matches credits, both should be zero."""
        ingresos = IngresosAnuales(honorarios_facturados_612=960_000)
        deducciones = DeduccionesAnuales()
        result_no_cred = calculate_annual_612(2025, ingresos, deducciones)

        # Pay exactly the ISR as provisionals
        exact_isr = result_no_cred.isr_anual_612
        result = calculate_annual_612(
            2025, ingresos, deducciones, pagos_provisionales=exact_isr
        )
        assert result.isr_a_cargo == 0.0
        assert result.isr_a_favor == 0.0

    def test_mutual_exclusion(self):
        """ISR a cargo and a favor should never both be positive."""
        ingresos = IngresosAnuales(honorarios_facturados_612=800_000)
        deducciones = DeduccionesAnuales(arrendamiento=96_000)

        for prov in [0, 50_000, 100_000, 200_000, 500_000]:
            result = calculate_annual_612(
                2025, ingresos, deducciones, pagos_provisionales=prov
            )
            assert not (result.isr_a_cargo > 0 and result.isr_a_favor > 0), (
                f"Both a_cargo ({result.isr_a_cargo}) and a_favor ({result.isr_a_favor}) "
                f"are positive with provisionales={prov}"
            )


# ======================================================================
# TEST: WhatsApp Formatting
# ======================================================================

class TestWhatsAppFormattingAnual:
    """Test WhatsApp output for annual declaration."""

    def test_resumen_612(self):
        ingresos = IngresosAnuales(honorarios_facturados_612=960_000)
        deducciones = DeduccionesAnuales(arrendamiento=96_000)
        result = calculate_annual_612(2025, ingresos, deducciones)

        text = result.resumen_whatsapp()
        assert "ANUAL" in text
        assert "2025" in text
        assert "612" in text
        assert "ISR" in text
        assert "$" in text

    def test_resumen_resico(self):
        ingresos = IngresosAnuales(ingresos_cobrados_resico=600_000)
        result = calculate_annual_resico(2025, ingresos)

        text = result.resumen_whatsapp()
        assert "ANUAL" in text
        assert "625" in text

    def test_resumen_shows_cargo(self):
        """When ISR a cargo, show payment deadline."""
        ingresos = IngresosAnuales(honorarios_facturados_612=1_200_000)
        deducciones = DeduccionesAnuales()
        result = calculate_annual_612(2025, ingresos, deducciones)

        text = result.resumen_whatsapp()
        assert "CARGO" in text
        assert "abril" in text.lower() or "30" in text

    def test_resumen_shows_favor(self):
        """When ISR a favor, show devolution info."""
        ingresos = IngresosAnuales(
            honorarios_facturados_612=500_000,
            retenciones_isr_612=50_000,
        )
        deducciones = DeduccionesAnuales(
            arrendamiento=96_000,
            nomina_y_seguridad=180_000,
        )
        result = calculate_annual_612(
            2025, ingresos, deducciones, pagos_provisionales=200_000
        )

        text = result.resumen_whatsapp()
        if result.isr_a_favor > 0:
            assert "FAVOR" in text
            assert "devoluc" in text.lower() or "DeclaraSAT" in text

    def test_resumen_shows_operativas(self):
        """Show operational deductions when present."""
        ingresos = IngresosAnuales(honorarios_facturados_612=960_000)
        deducciones = DeduccionesAnuales(arrendamiento=96_000)
        result = calculate_annual_612(2025, ingresos, deducciones)

        text = result.resumen_whatsapp()
        assert "operativas" in text.lower() or "Deducciones" in text

    def test_resumen_shows_personales(self):
        """Show personal deductions when present."""
        ingresos = IngresosAnuales(honorarios_facturados_612=960_000)
        deducciones = DeduccionesAnuales()
        personales = DeduccionesPersonales(gastos_medicos=50_000)
        result = calculate_annual_612(2025, ingresos, deducciones, personales)

        text = result.resumen_whatsapp()
        assert "personales" in text.lower() or "Personal" in text

    def test_resumen_shows_tasa_efectiva(self):
        """Always show effective tax rate."""
        ingresos = IngresosAnuales(honorarios_facturados_612=960_000)
        deducciones = DeduccionesAnuales()
        result = calculate_annual_612(2025, ingresos, deducciones)

        text = result.resumen_whatsapp()
        assert "Tasa efectiva" in text or "tasa" in text.lower()

    def test_resumen_shows_alerts(self):
        """Show alerts when present."""
        ingresos = IngresosAnuales(honorarios_facturados_612=5_000_000)
        deducciones = DeduccionesAnuales()
        result = calculate_annual_612(2025, ingresos, deducciones)

        text = result.resumen_whatsapp()
        if result.alertas:
            for alerta in result.alertas:
                assert alerta in text


# ======================================================================
# TEST: ResultadoAnual.to_dict()
# ======================================================================

class TestResultadoAnualToDict:
    """Test the result data class serialization."""

    def test_to_dict_basic(self):
        result = ResultadoAnual(anio=2025, regimen="612")
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["anio"] == 2025
        assert d["regimen"] == "612"

    def test_to_dict_contains_all_fields(self):
        result = ResultadoAnual(anio=2025, regimen="612")
        d = result.to_dict()
        expected_keys = [
            "anio", "regimen", "ingresos_totales", "ingresos_acumulables_612",
            "ingresos_resico", "ingresos_salarios", "deducciones_operativas",
            "deducciones_personales", "tope_deducciones_personales",
            "base_gravable_612", "isr_anual_612", "base_gravable_resico",
            "isr_anual_resico", "pagos_provisionales", "retenciones_isr",
            "isr_total_ejercicio", "isr_a_cargo", "isr_a_favor",
            "tasa_efectiva_isr", "alertas", "notas",
        ]
        for key in expected_keys:
            assert key in d, f"Missing key: {key}"

    def test_to_dict_from_612_calculation(self):
        ingresos = IngresosAnuales(honorarios_facturados_612=960_000)
        deducciones = DeduccionesAnuales(arrendamiento=96_000)
        result = calculate_annual_612(2025, ingresos, deducciones)

        d = result.to_dict()
        assert d["regimen"] == "612"
        assert d["ingresos_totales"] == 960_000
        assert d["deducciones_operativas"] == 96_000
        assert d["isr_anual_612"] > 0

    def test_to_dict_from_resico_calculation(self):
        ingresos = IngresosAnuales(ingresos_cobrados_resico=600_000)
        result = calculate_annual_resico(2025, ingresos)

        d = result.to_dict()
        assert d["regimen"] == "625"
        assert d["ingresos_resico"] == 600_000
        assert d["isr_anual_resico"] > 0

    def test_to_dict_lists_serialized(self):
        """Alertas and notas lists should be serialized properly."""
        result = ResultadoAnual(
            anio=2025, regimen="612",
            alertas=["Alerta 1", "Alerta 2"],
            notas=["Nota 1"],
        )
        d = result.to_dict()
        assert isinstance(d["alertas"], list)
        assert len(d["alertas"]) == 2
        assert isinstance(d["notas"], list)
        assert len(d["notas"]) == 1


# ======================================================================
# TEST: Constants
# ======================================================================

class TestAnnualConstants:
    """Test annual tariff tables and constants are correct."""

    def test_isr_anual_tariff_has_11_brackets(self):
        assert len(TARIFA_ISR_ANUAL) == 11

    def test_isr_anual_tariff_starts_at_001(self):
        assert TARIFA_ISR_ANUAL[0][0] == 0.01

    def test_isr_anual_tariff_top_is_35_pct(self):
        assert TARIFA_ISR_ANUAL[-1][3] == 35.00

    def test_isr_anual_tariff_continuous(self):
        """Brackets should be continuous (no gaps)."""
        for i in range(len(TARIFA_ISR_ANUAL) - 1):
            upper = TARIFA_ISR_ANUAL[i][1]
            next_lower = TARIFA_ISR_ANUAL[i + 1][0]
            assert abs(next_lower - upper - 0.01) < 0.02

    def test_isr_anual_tariff_top_is_inf(self):
        """Last bracket should have infinity as upper bound."""
        assert TARIFA_ISR_ANUAL[-1][1] == float("inf")

    def test_isr_anual_tariff_rates_increase(self):
        """Marginal rates should increase across brackets."""
        rates = [bracket[3] for bracket in TARIFA_ISR_ANUAL]
        for i in range(len(rates) - 1):
            assert rates[i] < rates[i + 1]

    def test_isr_anual_tariff_cuotas_increase(self):
        """Fixed quotas should increase across brackets."""
        cuotas = [bracket[2] for bracket in TARIFA_ISR_ANUAL]
        for i in range(len(cuotas) - 1):
            assert cuotas[i] <= cuotas[i + 1]

    def test_resico_anual_has_5_tiers(self):
        assert len(TARIFA_RESICO_ANUAL) == 5

    def test_resico_anual_starts_at_1_pct(self):
        assert TARIFA_RESICO_ANUAL[0][2] == 1.00

    def test_resico_anual_max_is_25_pct(self):
        assert TARIFA_RESICO_ANUAL[-1][2] == 2.50

    def test_resico_anual_continuous(self):
        """RESICO tiers should be continuous."""
        for i in range(len(TARIFA_RESICO_ANUAL) - 1):
            upper = TARIFA_RESICO_ANUAL[i][1]
            next_lower = TARIFA_RESICO_ANUAL[i + 1][0]
            assert abs(next_lower - upper - 0.01) < 0.02

    def test_resico_anual_rates_increase(self):
        """RESICO rates should increase across tiers."""
        rates = [tier[2] for tier in TARIFA_RESICO_ANUAL]
        for i in range(len(rates) - 1):
            assert rates[i] < rates[i + 1]

    def test_uma_anual_is_positive(self):
        assert UMA_ANUAL_REAL_2026 > 0

    def test_tope_deducciones_personales_is_5(self):
        assert TOPE_DEDUCCIONES_PERSONALES_UMAS == 5

    def test_resico_cap_at_3_5m(self):
        """Last RESICO tier should end at $3,500,000."""
        assert TARIFA_RESICO_ANUAL[-1][1] == 3_500_000


# ======================================================================
# TEST: Module Exports
# ======================================================================

class TestAnnualModuleExports:
    """Test that all symbols are importable from src.tools."""

    def test_import_functions(self):
        from src.tools import (
            calculate_annual_612,
            calculate_annual_resico,
            compare_annual_regimes,
        )

    def test_import_classes(self):
        from src.tools import (
            IngresosAnuales,
            DeduccionesAnualesDecl,
            DeduccionesPersonales,
            ResultadoAnual,
        )

    def test_import_constants(self):
        from src.tools import (
            TARIFA_ISR_ANUAL,
            TARIFA_RESICO_ANUAL,
        )

    def test_deduccionesanuales_alias(self):
        """DeduccionesAnuales is imported as DeduccionesAnualesDecl to avoid clash."""
        from src.tools import DeduccionesAnualesDecl
        # Should be the same class
        assert DeduccionesAnualesDecl is DeduccionesAnuales
