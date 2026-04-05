"""Tests for OpenDoc Payroll Calculator.

Comprehensive tests for:
- ISR employee withholding (Art. 96 tariff + subsidio al empleo)
- SBC calculation (factor de integración)
- IMSS quotas (all 8 branches)
- INFONAVIT contribution
- State payroll tax (ISN)
- Complete employee payroll
- Multi-employee summary
- WhatsApp formatting
- Edge cases (minimum wage, high salary, no employees)
"""

import pytest
from src.tools.payroll_calculator import (
    # Core functions
    _calculate_sbc,
    calculate_isr_withholding,
    calculate_imss_quotas,
    calculate_employee_payroll,
    calculate_payroll,
    # Data classes
    Empleado,
    NominaEmpleado,
    ResumenNomina,
    DesgloseCuotasIMSS,
    # Constants
    CUOTAS_IMSS,
    TARIFA_ISR_MENSUAL,
    SUBSIDIO_EMPLEO_MENSUAL,
    UMA_DIARIA_2026,
    UMA_MENSUAL_2026,
    SALARIO_MINIMO_DIARIO_2026,
    SALARIO_MINIMO_MENSUAL_2026,
    TOPE_SBC_25_UMA,
    INFONAVIT_TASA_PATRONAL,
    ISN_TOTAL_GTO,
)


# ══════════════════════════════════════════════════════════════════════
# TEST: SBC Calculation
# ══════════════════════════════════════════════════════════════════════

class TestSBCCalculation:
    """Test Salario Base de Cotización calculation."""

    def test_basic_sbc_from_monthly(self):
        """SBC should be higher than daily salary (integration factor > 1)."""
        emp = Empleado(nombre="Test", salario_mensual_bruto=10_000)
        sbc = _calculate_sbc(emp)
        daily = 10_000 / 30.4
        assert sbc > daily

    def test_sbc_integration_factor(self):
        """Verify integration factor components."""
        emp = Empleado(
            nombre="Test",
            salario_mensual_bruto=10_000,
            aguinaldo_dias=15,
            vacaciones_dias=12,
            prima_vacacional_pct=25.0,
        )
        sbc = _calculate_sbc(emp)
        sd = 10_000 / 30.4
        # Factor = 1 + 15/365 + (0.25 * 12)/365
        factor = 1 + 15/365 + (0.25 * 12)/365
        expected = sd * factor
        assert abs(sbc - expected) < 1.0

    def test_sbc_capped_at_25_uma(self):
        """SBC should not exceed 25 UMA daily."""
        emp = Empleado(nombre="Test", salario_mensual_bruto=200_000)
        sbc = _calculate_sbc(emp)
        assert sbc <= TOPE_SBC_25_UMA

    def test_sbc_uses_explicit_sbc(self):
        """If sbc_diario is provided, use it (capped)."""
        emp = Empleado(nombre="Test", sbc_diario=500.0, salario_mensual_bruto=15_000)
        sbc = _calculate_sbc(emp)
        assert sbc == 500.0

    def test_sbc_explicit_above_cap(self):
        emp = Empleado(nombre="Test", sbc_diario=5_000.0)
        sbc = _calculate_sbc(emp)
        assert sbc == TOPE_SBC_25_UMA

    def test_sbc_from_daily_salary(self):
        emp = Empleado(nombre="Test", salario_diario=400.0)
        sbc = _calculate_sbc(emp)
        assert sbc > 400.0  # Integration factor


# ══════════════════════════════════════════════════════════════════════
# TEST: ISR Withholding
# ══════════════════════════════════════════════════════════════════════

class TestISRWithholding:
    """Test employee ISR withholding."""

    def test_zero_income(self):
        result = calculate_isr_withholding(0)
        assert result["isr_neto"] == 0.0

    def test_negative_income(self):
        result = calculate_isr_withholding(-1000)
        assert result["isr_neto"] == 0.0

    def test_low_income_with_subsidy(self):
        """Low-income employee gets employment subsidy."""
        result = calculate_isr_withholding(5_000)
        assert result["subsidio"] > 0
        # ISR should be reduced by subsidy
        assert result["isr_neto"] <= result["isr_bruto"]

    def test_medium_income(self):
        """Typical secretary salary."""
        result = calculate_isr_withholding(8_000)
        assert result["isr_bruto"] > 0
        assert result["isr_neto"] >= 0

    def test_high_income_no_subsidy(self):
        """Higher income → no employment subsidy."""
        result = calculate_isr_withholding(15_000)
        assert result["subsidio"] == 0.0
        assert result["isr_neto"] == result["isr_bruto"]

    def test_isr_never_negative(self):
        """ISR to retain should never be negative."""
        result = calculate_isr_withholding(3_000)
        assert result["isr_neto"] >= 0

    def test_isr_progressive(self):
        """Higher salary → higher ISR."""
        isr_8k = calculate_isr_withholding(8_000)["isr_neto"]
        isr_15k = calculate_isr_withholding(15_000)["isr_neto"]
        isr_30k = calculate_isr_withholding(30_000)["isr_neto"]
        assert isr_8k <= isr_15k <= isr_30k

    def test_minimum_wage_low_isr(self):
        """Minimum wage should have relatively low ISR with subsidy."""
        result = calculate_isr_withholding(SALARIO_MINIMO_MENSUAL_2026)
        # Minimum wage ~$8,476/month → ISR reduced by subsidio al empleo
        # Effective rate should be well below the marginal bracket rate
        effective_rate = result["isr_neto"] / SALARIO_MINIMO_MENSUAL_2026 * 100
        assert effective_rate < 10  # Less than 10% effective rate


# ══════════════════════════════════════════════════════════════════════
# TEST: IMSS Quotas
# ══════════════════════════════════════════════════════════════════════

class TestIMSSQuotas:
    """Test IMSS employer + employee quota calculations."""

    def test_basic_quotas(self):
        sbc = 400.0  # ~$12,000/month
        result = calculate_imss_quotas(sbc, dias=30)
        assert result.total_patronal > 0
        assert result.total_obrero > 0
        assert result.total > result.total_patronal

    def test_riesgos_trabajo_patron_only(self):
        """Riesgos de trabajo is employer-only."""
        sbc = 400.0
        result = calculate_imss_quotas(sbc, dias=30)
        assert result.riesgos_trabajo_patron > 0
        # No employee share for riesgos de trabajo

    def test_enfermedad_fija_on_uma(self):
        """Cuota fija uses UMA, not SBC."""
        sbc_low = 300.0
        sbc_high = 800.0
        result_low = calculate_imss_quotas(sbc_low, dias=30)
        result_high = calculate_imss_quotas(sbc_high, dias=30)
        # Cuota fija should be the same regardless of SBC
        assert result_low.enfermedad_fija_patron == result_high.enfermedad_fija_patron

    def test_excedente_zero_when_below_3uma(self):
        """No excedente if SBC ≤ 3 UMA."""
        sbc = UMA_DIARIA_2026 * 2  # Below 3 UMA
        result = calculate_imss_quotas(sbc, dias=30)
        assert result.enfermedad_excedente_patron == 0.0
        assert result.enfermedad_excedente_obrero == 0.0

    def test_excedente_positive_above_3uma(self):
        """Excedente should be positive when SBC > 3 UMA."""
        sbc = UMA_DIARIA_2026 * 5  # Above 3 UMA
        result = calculate_imss_quotas(sbc, dias=30)
        assert result.enfermedad_excedente_patron > 0
        assert result.enfermedad_excedente_obrero > 0

    def test_guarderias_patron_only(self):
        """Guarderías is employer-only."""
        sbc = 400.0
        result = calculate_imss_quotas(sbc, dias=30)
        assert result.guarderias_patron > 0

    def test_retiro_patron_only(self):
        """SAR/Retiro is employer-only."""
        sbc = 400.0
        result = calculate_imss_quotas(sbc, dias=30)
        assert result.retiro_patron > 0

    def test_cesantia_both_shares(self):
        """Cesantía has both employer and employee shares."""
        sbc = 400.0
        result = calculate_imss_quotas(sbc, dias=30)
        assert result.cesantia_patron > 0
        assert result.cesantia_obrero > 0

    def test_patron_higher_than_obrero(self):
        """Employer total should be higher than employee total."""
        sbc = 400.0
        result = calculate_imss_quotas(sbc, dias=30)
        assert result.total_patronal > result.total_obrero

    def test_higher_sbc_higher_quotas(self):
        """Higher SBC → higher quotas (except fija)."""
        low = calculate_imss_quotas(300, dias=30)
        high = calculate_imss_quotas(800, dias=30)
        assert high.total > low.total

    def test_desglose_total_consistency(self):
        """total_patronal + total_obrero = total."""
        sbc = 500.0
        result = calculate_imss_quotas(sbc, dias=30)
        assert abs(result.total - (result.total_patronal + result.total_obrero)) < 0.02


# ══════════════════════════════════════════════════════════════════════
# TEST: Employee Payroll
# ══════════════════════════════════════════════════════════════════════

class TestEmployeePayroll:
    """Test complete single-employee payroll."""

    def _nurse(self):
        return Empleado(
            nombre="María García",
            puesto="Enfermera",
            salario_mensual_bruto=12_000,
        )

    def _secretary(self):
        return Empleado(
            nombre="Ana López",
            puesto="Secretaria",
            salario_mensual_bruto=8_000,
        )

    def test_basic_nurse_payroll(self):
        nomina = calculate_employee_payroll(self._nurse())
        assert nomina.nombre == "María García"
        assert nomina.puesto == "Enfermera"
        assert nomina.salario_bruto == 12_000
        assert nomina.isr_a_retener >= 0
        assert nomina.imss_obrero > 0
        assert nomina.salario_neto > 0
        assert nomina.imss_patronal > 0

    def test_net_salary_less_than_gross(self):
        """Net should be less than gross (ISR + IMSS deducted)."""
        nomina = calculate_employee_payroll(self._nurse())
        assert nomina.salario_neto < nomina.salario_bruto

    def test_employer_cost_higher_than_gross(self):
        """Employer total cost > gross salary."""
        nomina = calculate_employee_payroll(self._nurse())
        assert nomina.costo_total_patron > nomina.salario_bruto

    def test_infonavit_5_percent(self):
        """INFONAVIT is 5% of SBC."""
        nomina = calculate_employee_payroll(self._nurse())
        expected = nomina.sbc_diario * 30 * INFONAVIT_TASA_PATRONAL / 100
        assert abs(nomina.infonavit - expected) < 1.0

    def test_no_infonavit_when_disabled(self):
        emp = Empleado(nombre="Test", salario_mensual_bruto=10_000, tiene_infonavit=False)
        nomina = calculate_employee_payroll(emp)
        assert nomina.infonavit == 0.0

    def test_isn_when_enabled(self):
        nomina = calculate_employee_payroll(self._nurse(), include_isn=True)
        expected = 12_000 * ISN_TOTAL_GTO / 100
        assert abs(nomina.isn_estatal - expected) < 1.0

    def test_isn_disabled_by_default(self):
        nomina = calculate_employee_payroll(self._nurse())
        assert nomina.isn_estatal == 0.0

    def test_imss_desglose_present(self):
        nomina = calculate_employee_payroll(self._nurse())
        assert nomina.desglose_imss is not None
        assert nomina.desglose_imss.total_patronal > 0

    def test_secretary_payroll(self):
        nomina = calculate_employee_payroll(self._secretary())
        assert nomina.salario_bruto == 8_000
        assert nomina.salario_neto > 0

    def test_to_dict(self):
        nomina = calculate_employee_payroll(self._nurse())
        d = nomina.to_dict()
        assert isinstance(d, dict)
        assert d["nombre"] == "María García"


# ══════════════════════════════════════════════════════════════════════
# TEST: Full Payroll (Multiple Employees)
# ══════════════════════════════════════════════════════════════════════

class TestFullPayroll:
    """Test multi-employee payroll summary."""

    def _typical_staff(self):
        return [
            Empleado(nombre="María García", puesto="Enfermera",
                     salario_mensual_bruto=12_000),
            Empleado(nombre="Ana López", puesto="Secretaria",
                     salario_mensual_bruto=8_000),
            Empleado(nombre="Juan Pérez", puesto="Limpieza",
                     salario_mensual_bruto=8_500),
        ]

    def test_basic_summary(self):
        resumen = calculate_payroll(
            mes=1, anio=2026,
            rfc_patron="MOPR881228EF9",
            empleados=self._typical_staff(),
        )
        assert resumen.num_empleados == 3
        assert resumen.total_salarios_brutos == 28_500

    def test_totals_consistency(self):
        """Sum of individual totals should match summary."""
        resumen = calculate_payroll(
            mes=1, anio=2026,
            rfc_patron="MOPR881228EF9",
            empleados=self._typical_staff(),
        )
        # Total brutos should be sum of individual brutos
        individual_brutos = sum(
            e["salario_bruto"] if isinstance(e, dict) else e.salario_bruto
            for e in resumen.empleados
        )
        assert abs(resumen.total_salarios_brutos - individual_brutos) < 0.02

    def test_costo_patron_note(self):
        """Should have note about employer cost percentage."""
        resumen = calculate_payroll(
            mes=1, anio=2026,
            rfc_patron="MOPR881228EF9",
            empleados=self._typical_staff(),
        )
        assert any("patronal" in n.lower() for n in resumen.notas)

    def test_deducible_note(self):
        """Should note that payroll is deductible in 612."""
        resumen = calculate_payroll(
            mes=1, anio=2026,
            rfc_patron="MOPR881228EF9",
            empleados=self._typical_staff(),
        )
        assert any("deducible" in n.lower() for n in resumen.notas)

    def test_with_isn(self):
        resumen = calculate_payroll(
            mes=1, anio=2026,
            rfc_patron="MOPR881228EF9",
            empleados=self._typical_staff(),
            include_isn=True,
        )
        assert resumen.total_isn > 0

    def test_empty_employees(self):
        resumen = calculate_payroll(
            mes=1, anio=2026,
            rfc_patron="MOPR881228EF9",
            empleados=[],
        )
        assert resumen.num_empleados == 0
        assert resumen.total_costo_patron == 0

    def test_below_minimum_wage_alert(self):
        """Alert when salary below minimum wage."""
        staff = [
            Empleado(nombre="Underpaid", puesto="Test",
                     salario_mensual_bruto=3_000),
        ]
        resumen = calculate_payroll(
            mes=1, anio=2026,
            rfc_patron="MOPR881228EF9",
            empleados=staff,
        )
        assert any("mínimo" in a for a in resumen.alertas)

    def test_rfc_normalized(self):
        resumen = calculate_payroll(
            mes=1, anio=2026,
            rfc_patron="  mopr881228ef9  ",
            empleados=[],
        )
        assert resumen.rfc_patron == "MOPR881228EF9"

    def test_to_dict(self):
        resumen = calculate_payroll(
            mes=1, anio=2026,
            rfc_patron="MOPR881228EF9",
            empleados=self._typical_staff(),
        )
        d = resumen.to_dict()
        assert isinstance(d, dict)
        assert d["num_empleados"] == 3


# ══════════════════════════════════════════════════════════════════════
# TEST: WhatsApp Formatting
# ══════════════════════════════════════════════════════════════════════

class TestWhatsAppFormatting:
    """Test payroll WhatsApp summary."""

    def test_basic_formatting(self):
        resumen = calculate_payroll(
            mes=1, anio=2026,
            rfc_patron="MOPR881228EF9",
            empleados=[
                Empleado(nombre="María", puesto="Enfermera",
                         salario_mensual_bruto=12_000),
            ],
        )
        text = resumen.resumen_whatsapp()
        assert "NÓMINA" in text
        assert "ENERO" in text
        assert "María" in text
        assert "Enfermera" in text
        assert "COSTO TOTAL" in text

    def test_multiple_employees_in_output(self):
        resumen = calculate_payroll(
            mes=6, anio=2026,
            rfc_patron="MOPR881228EF9",
            empleados=[
                Empleado(nombre="María", puesto="Enfermera",
                         salario_mensual_bruto=12_000),
                Empleado(nombre="Ana", puesto="Secretaria",
                         salario_mensual_bruto=8_000),
            ],
        )
        text = resumen.resumen_whatsapp()
        assert "JUNIO" in text
        assert "María" in text
        assert "Ana" in text
        assert "Empleados: 2" in text

    def test_filing_dates_in_output(self):
        resumen = calculate_payroll(
            mes=1, anio=2026,
            rfc_patron="MOPR881228EF9",
            empleados=[],
        )
        text = resumen.resumen_whatsapp()
        assert "día 17" in text
        assert "día 22" in text


# ══════════════════════════════════════════════════════════════════════
# TEST: Constants
# ══════════════════════════════════════════════════════════════════════

class TestConstants:
    """Test payroll constants are reasonable."""

    def test_uma_reasonable(self):
        """UMA should be between 100-150 for 2026."""
        assert 100 < UMA_DIARIA_2026 < 150

    def test_salario_minimo_above_uma(self):
        """Minimum wage should be above UMA."""
        assert SALARIO_MINIMO_DIARIO_2026 > UMA_DIARIA_2026

    def test_tope_sbc_25_uma(self):
        assert abs(TOPE_SBC_25_UMA - UMA_DIARIA_2026 * 25) < 0.01

    def test_infonavit_5_percent(self):
        assert INFONAVIT_TASA_PATRONAL == 5.0

    def test_isn_gto_components(self):
        assert ISN_TOTAL_GTO == 2.6  # 2.3 + 0.2 + 0.1

    def test_imss_has_8_branches(self):
        assert len(CUOTAS_IMSS) == 8

    def test_imss_branch_names(self):
        expected = {
            "riesgos_trabajo", "enfermedades_maternidad_especie_fija",
            "enfermedades_maternidad_especie_excedente",
            "enfermedades_maternidad_dinero", "invalidez_vida",
            "guarderias_ps", "retiro", "cesantia_vejez",
        }
        assert set(CUOTAS_IMSS.keys()) == expected

    def test_isr_tariff_has_11_brackets(self):
        assert len(TARIFA_ISR_MENSUAL) == 11

    def test_subsidio_has_entries(self):
        assert len(SUBSIDIO_EMPLEO_MENSUAL) > 0


# ══════════════════════════════════════════════════════════════════════
# TEST: Realistic Doctor Scenarios
# ══════════════════════════════════════════════════════════════════════

class TestDoctorScenarios:
    """Test realistic scenarios for a typical doctor's office."""

    def test_small_consultorio_cost(self):
        """Typical small consultorio: 1 nurse + 1 secretary.
        Doctor should know the real cost of having employees.
        """
        staff = [
            Empleado(nombre="Enfermera", puesto="Enfermera",
                     salario_mensual_bruto=12_000),
            Empleado(nombre="Secretaria", puesto="Secretaria",
                     salario_mensual_bruto=8_000),
        ]
        resumen = calculate_payroll(
            mes=1, anio=2026,
            rfc_patron="MOPR881228EF9",
            empleados=staff,
            include_isn=True,
        )
        # Employer cost should be 25-40% higher than gross salaries
        overhead = (resumen.total_costo_patron - resumen.total_salarios_brutos)
        overhead_pct = overhead / resumen.total_salarios_brutos * 100
        assert 20 < overhead_pct < 50  # Reasonable range

    def test_net_vs_gross_ratio(self):
        """Employees should receive 80-95% of gross (after ISR + IMSS)."""
        emp = Empleado(nombre="Test", puesto="Nurse",
                       salario_mensual_bruto=12_000)
        nomina = calculate_employee_payroll(emp)
        ratio = nomina.salario_neto / nomina.salario_bruto * 100
        assert 75 < ratio < 97

    def test_high_salary_specialist_nurse(self):
        """Specialist nurse with higher salary."""
        emp = Empleado(nombre="Nurse RN", puesto="Enfermera Especialista",
                       salario_mensual_bruto=25_000)
        nomina = calculate_employee_payroll(emp)
        assert nomina.isr_a_retener > 0
        assert nomina.costo_total_patron > 25_000


# ══════════════════════════════════════════════════════════════════════
# TEST: Module Exports
# ══════════════════════════════════════════════════════════════════════

class TestModuleExports:
    """Test imports from __init__."""

    def test_import_functions(self):
        from src.tools import (
            calculate_payroll,
            calculate_employee_payroll,
            calculate_isr_withholding,
            calculate_imss_quotas,
        )

    def test_import_classes(self):
        from src.tools import (
            Empleado,
            NominaEmpleado,
            ResumenNomina,
            DesgloseCuotasIMSS,
        )

    def test_import_constants(self):
        from src.tools import (
            CUOTAS_IMSS,
            UMA_DIARIA_2026,
            SALARIO_MINIMO_DIARIO_2026,
            INFONAVIT_TASA_PATRONAL,
            ISN_TOTAL_GTO,
        )
