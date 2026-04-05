"""Tests for OpenDoc Centralized Fiscal Tables.

Validates:
- All tariffs have correct structure and values
- UMA and salary constants are reasonable
- IVA rates match law
- Cross-module consistency (same values available from all importers)
- Single source of truth: changing fiscal_tables propagates everywhere
"""

import pytest


# ─── Direct import from fiscal_tables ────────────────────────────────

from src.tools.fiscal_tables import (
    EJERCICIO_FISCAL,
    # UMA
    UMA_DIARIA_2026,
    UMA_MENSUAL_2026,
    UMA_ANUAL_2026,
    UMA_ANUAL_REAL_2026,
    # Salario Mínimo
    SALARIO_MINIMO_DIARIO_2026,
    SALARIO_MINIMO_MENSUAL_2026,
    # ISR Tariffs
    TARIFA_ISR_MENSUAL,
    TARIFA_ISR_ANUAL,
    TARIFA_RESICO_MENSUAL,
    TARIFA_RESICO_ANUAL,
    # Subsidio
    SUBSIDIO_EMPLEO_MENSUAL,
    # IVA
    IVA_TASA_GENERAL,
    IVA_TASA_FRONTERA,
    IVA_TASA_CERO,
    # Cedular
    CEDULAR_TASA_GTO,
    # IMSS
    TOPE_SBC_25_UMA,
    # INFONAVIT / SAR
    INFONAVIT_TASA_PATRONAL,
    SAR_TASA_PATRONAL,
    # ISN
    ISN_TASA_GTO,
    # Deduction limits
    TOPE_DEDUCCIONES_PERSONALES_UMAS,
    TOPE_DEDUCCIONES_PERSONALES_PCT,
    # RESICO
    RESICO_TOPE_INGRESOS,
    # Retenciones
    RETENCION_ISR_PM,
    RETENCION_IVA_PM,
)


# ─── Test: Fiscal Year ───────────────────────────────────────────────

class TestFiscalYear:
    def test_ejercicio_2026(self):
        assert EJERCICIO_FISCAL == 2026


# ─── Test: UMA Constants ─────────────────────────────────────────────

class TestUMA:
    def test_uma_diaria_reasonable(self):
        """UMA diaria should be between $100 and $150 for 2026."""
        assert 100 < UMA_DIARIA_2026 < 150

    def test_uma_mensual_calculation(self):
        assert abs(UMA_MENSUAL_2026 - UMA_DIARIA_2026 * 30.4) < 0.01

    def test_uma_anual_calculation(self):
        assert abs(UMA_ANUAL_2026 - UMA_DIARIA_2026 * 365) < 0.01

    def test_uma_anual_real_alias(self):
        """UMA_ANUAL_REAL_2026 should be same as UMA_ANUAL_2026."""
        assert UMA_ANUAL_REAL_2026 == UMA_ANUAL_2026

    def test_uma_anual_approx_41k(self):
        assert 40_000 < UMA_ANUAL_2026 < 45_000


# ─── Test: Salario Mínimo ────────────────────────────────────────────

class TestSalarioMinimo:
    def test_salario_minimo_above_uma(self):
        """Salario mínimo should always be above UMA."""
        assert SALARIO_MINIMO_DIARIO_2026 > UMA_DIARIA_2026

    def test_salario_minimo_mensual(self):
        assert abs(SALARIO_MINIMO_MENSUAL_2026 - SALARIO_MINIMO_DIARIO_2026 * 30.4) < 0.01

    def test_salario_minimo_reasonable(self):
        assert 250 < SALARIO_MINIMO_DIARIO_2026 < 400


# ─── Test: ISR Monthly Tariff ────────────────────────────────────────

class TestTarifaISRMensual:
    def test_eleven_brackets(self):
        assert len(TARIFA_ISR_MENSUAL) == 11

    def test_starts_at_001(self):
        assert TARIFA_ISR_MENSUAL[0][0] == 0.01

    def test_max_rate_35(self):
        assert TARIFA_ISR_MENSUAL[-1][3] == 35.00

    def test_last_bracket_infinite(self):
        assert TARIFA_ISR_MENSUAL[-1][1] == float("inf")

    def test_brackets_continuous(self):
        """Each bracket's lower limit should be ~1 cent above previous upper."""
        for i in range(len(TARIFA_ISR_MENSUAL) - 1):
            upper = TARIFA_ISR_MENSUAL[i][1]
            next_lower = TARIFA_ISR_MENSUAL[i + 1][0]
            assert next_lower - upper <= 0.02

    def test_rates_ascending(self):
        rates = [b[3] for b in TARIFA_ISR_MENSUAL]
        assert rates == sorted(rates)

    def test_cuotas_ascending(self):
        cuotas = [b[2] for b in TARIFA_ISR_MENSUAL]
        assert cuotas == sorted(cuotas)

    def test_first_cuota_zero(self):
        assert TARIFA_ISR_MENSUAL[0][2] == 0.00

    def test_first_rate_192(self):
        assert TARIFA_ISR_MENSUAL[0][3] == 1.92


# ─── Test: ISR Annual Tariff ─────────────────────────────────────────

class TestTarifaISRAnual:
    def test_eleven_brackets(self):
        assert len(TARIFA_ISR_ANUAL) == 11

    def test_starts_at_001(self):
        assert TARIFA_ISR_ANUAL[0][0] == 0.01

    def test_max_rate_35(self):
        assert TARIFA_ISR_ANUAL[-1][3] == 35.00

    def test_last_bracket_infinite(self):
        assert TARIFA_ISR_ANUAL[-1][1] == float("inf")

    def test_brackets_continuous(self):
        for i in range(len(TARIFA_ISR_ANUAL) - 1):
            upper = TARIFA_ISR_ANUAL[i][1]
            next_lower = TARIFA_ISR_ANUAL[i + 1][0]
            assert next_lower - upper <= 0.02

    def test_annual_limits_larger_than_monthly(self):
        """Annual limits should be roughly 12× monthly limits."""
        for i in range(min(5, len(TARIFA_ISR_ANUAL))):
            annual_upper = TARIFA_ISR_ANUAL[i][1]
            monthly_upper = TARIFA_ISR_MENSUAL[i][1]
            if monthly_upper != float("inf"):
                ratio = annual_upper / monthly_upper
                assert 10 < ratio < 14, f"Bracket {i} ratio={ratio}"


# ─── Test: RESICO Tariffs ────────────────────────────────────────────

class TestTarifaRESICO:
    def test_monthly_five_tiers(self):
        assert len(TARIFA_RESICO_MENSUAL) == 5

    def test_annual_five_tiers(self):
        assert len(TARIFA_RESICO_ANUAL) == 5

    def test_monthly_rates_range(self):
        rates = [t[2] for t in TARIFA_RESICO_MENSUAL]
        assert min(rates) == 1.00
        assert max(rates) == 2.50

    def test_annual_rates_range(self):
        rates = [t[2] for t in TARIFA_RESICO_ANUAL]
        assert min(rates) == 1.00
        assert max(rates) == 2.50

    def test_annual_cap_3_5m(self):
        assert TARIFA_RESICO_ANUAL[-1][1] == 3_500_000

    def test_monthly_continuous(self):
        for i in range(len(TARIFA_RESICO_MENSUAL) - 1):
            upper = TARIFA_RESICO_MENSUAL[i][1]
            next_lower = TARIFA_RESICO_MENSUAL[i + 1][0]
            assert next_lower - upper <= 0.02


# ─── Test: Subsidio al Empleo ─────────────────────────────────────────

class TestSubsidio:
    def test_has_entries(self):
        assert len(SUBSIDIO_EMPLEO_MENSUAL) > 0

    def test_decreasing_subsidio(self):
        """Subsidio should decrease as income increases."""
        subsidios = [s[2] for s in SUBSIDIO_EMPLEO_MENSUAL]
        for i in range(len(subsidios) - 1):
            assert subsidios[i] >= subsidios[i + 1]

    def test_last_bracket_zero(self):
        assert SUBSIDIO_EMPLEO_MENSUAL[-1][2] == 0.00

    def test_last_bracket_infinite(self):
        assert SUBSIDIO_EMPLEO_MENSUAL[-1][1] == float("inf")


# ─── Test: IVA Rates ─────────────────────────────────────────────────

class TestIVA:
    def test_tasa_general_16(self):
        assert IVA_TASA_GENERAL == 0.16

    def test_tasa_frontera_8(self):
        assert IVA_TASA_FRONTERA == 0.08

    def test_tasa_cero(self):
        assert IVA_TASA_CERO == 0.00


# ─── Test: Other Constants ───────────────────────────────────────────

class TestOtherConstants:
    def test_cedular_gto(self):
        assert CEDULAR_TASA_GTO == 0.02

    def test_tope_sbc(self):
        assert abs(TOPE_SBC_25_UMA - UMA_DIARIA_2026 * 25) < 0.01

    def test_infonavit(self):
        assert INFONAVIT_TASA_PATRONAL == 0.05

    def test_sar(self):
        assert SAR_TASA_PATRONAL == 0.02

    def test_isn_gto(self):
        assert ISN_TASA_GTO == 0.03

    def test_tope_deducciones_5_umas(self):
        assert TOPE_DEDUCCIONES_PERSONALES_UMAS == 5

    def test_tope_deducciones_15_pct(self):
        assert TOPE_DEDUCCIONES_PERSONALES_PCT == 0.15

    def test_resico_tope(self):
        assert RESICO_TOPE_INGRESOS == 3_500_000.00

    def test_retencion_isr_pm(self):
        assert RETENCION_ISR_PM == 0.10

    def test_retencion_iva_pm(self):
        assert abs(RETENCION_IVA_PM - 0.1067) < 0.001


# ─── Test: Cross-Module Consistency ──────────────────────────────────

class TestCrossModuleConsistency:
    """Verify that importing from the original modules gives same values."""

    def test_monthly_tarifa_same_as_central(self):
        from src.tools.monthly_tax_calculator import TARIFA_ISR_MENSUAL as MT
        assert MT is TARIFA_ISR_MENSUAL

    def test_monthly_resico_same_as_central(self):
        from src.tools.monthly_tax_calculator import TARIFA_RESICO_MENSUAL as MR
        assert MR is TARIFA_RESICO_MENSUAL

    def test_monthly_iva_same_as_central(self):
        from src.tools.monthly_tax_calculator import IVA_TASA_GENERAL as MV
        assert MV == IVA_TASA_GENERAL

    def test_monthly_cedular_same_as_central(self):
        from src.tools.monthly_tax_calculator import CEDULAR_TASA_GTO as MC
        assert MC == CEDULAR_TASA_GTO

    def test_annual_tarifa_same_as_central(self):
        from src.tools.annual_tax_calculator import TARIFA_ISR_ANUAL as AT
        assert AT is TARIFA_ISR_ANUAL

    def test_annual_resico_same_as_central(self):
        from src.tools.annual_tax_calculator import TARIFA_RESICO_ANUAL as AR
        assert AR is TARIFA_RESICO_ANUAL

    def test_annual_uma_same_as_central(self):
        from src.tools.annual_tax_calculator import UMA_ANUAL_REAL_2026 as AU
        assert AU == UMA_ANUAL_REAL_2026

    def test_payroll_tarifa_same_as_central(self):
        from src.tools.payroll_calculator import TARIFA_ISR_MENSUAL as PT
        assert PT is TARIFA_ISR_MENSUAL

    def test_payroll_uma_same_as_central(self):
        from src.tools.payroll_calculator import UMA_DIARIA_2026 as PU
        assert PU == UMA_DIARIA_2026

    def test_payroll_subsidio_same_as_central(self):
        from src.tools.payroll_calculator import SUBSIDIO_EMPLEO_MENSUAL as PS
        assert PS is SUBSIDIO_EMPLEO_MENSUAL

    def test_deduction_isr_same_as_central(self):
        from src.tools.deduction_optimizer import TARIFA_ISR_MENSUAL_2026 as DI
        assert DI is TARIFA_ISR_MENSUAL

    def test_deduction_resico_same_as_central(self):
        from src.tools.deduction_optimizer import TARIFA_RESICO_MENSUAL_2026 as DR
        assert DR is TARIFA_RESICO_MENSUAL
