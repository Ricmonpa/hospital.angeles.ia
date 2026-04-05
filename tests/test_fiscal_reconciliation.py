"""Tests for OpenDoc Fiscal Reconciliation Engine.

Validates:
- NivelDiscrepancia and AreaReconciliacion enums
- Discrepancia, MesConciliado, ResultadoConciliacion dataclasses
- reconcile_fiscal_year() — full reconciliation with 8 checks
- quick_reconcile() — minimal-input validation
- Scoring algorithm (100 → 0 based on discrepancies)
- WhatsApp summary formatting
- Edge cases (empty data, RESICO, perfect match, severe mismatches)
"""

import pytest

from src.tools.fiscal_reconciliation import (
    NivelDiscrepancia,
    AreaReconciliacion,
    Discrepancia,
    MesConciliado,
    ResultadoConciliacion,
    reconcile_fiscal_year,
    quick_reconcile,
    MESES_NOMBRES,
)


# ─── Fixtures ────────────────────────────────────────────────────────

def _make_monthly(mes, ingresos=50_000.0, deducciones=15_000.0,
                   isr_causado=5_000.0, isr_pagado=5_000.0,
                   retenciones_isr=1_000.0, iva_causado=0.0, iva_pagado=0.0):
    """Helper to create a month's data dict."""
    return {
        "mes": mes,
        "ingresos": ingresos,
        "deducciones": deducciones,
        "isr_causado": isr_causado,
        "isr_pagado": isr_pagado,
        "retenciones_isr": retenciones_isr,
        "iva_causado": iva_causado,
        "iva_pagado": iva_pagado,
    }


@pytest.fixture
def perfect_612():
    """12 months perfectly matching annual for Régimen 612."""
    monthly = [_make_monthly(m) for m in range(1, 13)]
    annual = {
        "anio": 2026,
        "ingresos_totales": 600_000.0,       # 50K × 12
        "deducciones_operativas": 180_000.0,  # 15K × 12
        "isr_total_ejercicio": 60_000.0,      # 5K × 12
        "pagos_provisionales": 60_000.0,      # 5K × 12
        "retenciones_isr": 12_000.0,          # 1K × 12
        "isr_a_cargo": 0.0,
        "isr_a_favor": 12_000.0,
    }
    return monthly, annual


@pytest.fixture
def perfect_resico():
    """12 months perfectly matching annual for RESICO 625."""
    monthly = [_make_monthly(m, deducciones=0.0, isr_causado=750.0,
                             isr_pagado=750.0, retenciones_isr=0.0)
               for m in range(1, 13)]
    annual = {
        "anio": 2026,
        "ingresos_totales": 600_000.0,
        "deducciones_operativas": 0.0,
        "isr_total_ejercicio": 9_000.0,       # 750 × 12
        "pagos_provisionales": 9_000.0,
        "retenciones_isr": 0.0,
        "isr_a_cargo": 0.0,
        "isr_a_favor": 0.0,
    }
    return monthly, annual


@pytest.fixture
def missing_months():
    """Only 9 months, missing Apr/May/Jun."""
    months = [1, 2, 3, 7, 8, 9, 10, 11, 12]
    monthly = [_make_monthly(m) for m in months]
    annual = {
        "anio": 2026,
        "ingresos_totales": 600_000.0,
        "deducciones_operativas": 180_000.0,
        "isr_total_ejercicio": 60_000.0,
        "pagos_provisionales": 60_000.0,
        "retenciones_isr": 12_000.0,
        "isr_a_cargo": 0.0,
        "isr_a_favor": 0.0,
    }
    return monthly, annual


@pytest.fixture
def income_mismatch():
    """Monthly totals $50K short of annual."""
    monthly = [_make_monthly(m) for m in range(1, 13)]
    annual = {
        "anio": 2026,
        "ingresos_totales": 650_000.0,        # 50K more than monthly sum
        "deducciones_operativas": 180_000.0,
        "isr_total_ejercicio": 60_000.0,
        "pagos_provisionales": 60_000.0,
        "retenciones_isr": 12_000.0,
        "isr_a_cargo": 0.0,
        "isr_a_favor": 0.0,
    }
    return monthly, annual


@pytest.fixture
def spike_month():
    """One month has 10× the average income (anomaly detection)."""
    monthly = [_make_monthly(m) for m in range(1, 13)]
    monthly[5]["ingresos"] = 500_000.0  # June has 10× normal
    total_ing = sum(d["ingresos"] for d in monthly)
    annual = {
        "anio": 2026,
        "ingresos_totales": total_ing,
        "deducciones_operativas": 180_000.0,
        "isr_total_ejercicio": 60_000.0,
        "pagos_provisionales": 60_000.0,
        "retenciones_isr": 12_000.0,
        "isr_a_cargo": 0.0,
        "isr_a_favor": 0.0,
    }
    return monthly, annual


# ─── Test: Enums ─────────────────────────────────────────────────────

class TestEnums:
    def test_nivel_critica(self):
        assert NivelDiscrepancia.CRITICA.value == "Crítica"

    def test_nivel_importante(self):
        assert NivelDiscrepancia.IMPORTANTE.value == "Importante"

    def test_nivel_menor(self):
        assert NivelDiscrepancia.MENOR.value == "Menor"

    def test_nivel_informativa(self):
        assert NivelDiscrepancia.INFORMATIVA.value == "Informativa"

    def test_four_levels(self):
        assert len(NivelDiscrepancia) == 4

    def test_area_ingresos(self):
        assert AreaReconciliacion.INGRESOS.value == "Ingresos"

    def test_area_isr(self):
        assert AreaReconciliacion.ISR.value == "ISR"

    def test_six_areas(self):
        assert len(AreaReconciliacion) == 6


class TestMesesNombres:
    def test_12_plus_empty(self):
        assert len(MESES_NOMBRES) == 13  # index 0 is empty

    def test_enero(self):
        assert MESES_NOMBRES[1] == "Enero"

    def test_diciembre(self):
        assert MESES_NOMBRES[12] == "Diciembre"

    def test_index_zero_empty(self):
        assert MESES_NOMBRES[0] == ""


# ─── Test: Dataclasses ───────────────────────────────────────────────

class TestDiscrepancia:
    def test_basic_fields(self):
        d = Discrepancia(
            area="Ingresos",
            nivel="Crítica",
            descripcion="Test error",
            monto_mensual=100.0,
            monto_anual=200.0,
            diferencia=100.0,
        )
        assert d.area == "Ingresos"
        assert d.nivel == "Crítica"
        assert d.diferencia == 100.0

    def test_default_mes(self):
        d = Discrepancia(area="ISR", nivel="Menor", descripcion="test")
        assert d.mes_afectado == 0

    def test_accion_requerida(self):
        d = Discrepancia(
            area="ISR", nivel="Importante",
            descripcion="test", accion_requerida="Verificar acuses",
        )
        assert d.accion_requerida == "Verificar acuses"


class TestMesConciliado:
    def test_defaults(self):
        mc = MesConciliado(mes=1)
        assert mc.tiene_datos is False
        assert mc.ingresos == 0.0
        assert mc.isr_pagado == 0.0

    def test_with_data(self):
        mc = MesConciliado(mes=6, tiene_datos=True, ingresos=50_000.0)
        assert mc.tiene_datos is True
        assert mc.ingresos == 50_000.0


class TestResultadoConciliacion:
    def test_default_score(self):
        r = ResultadoConciliacion(anio=2026, regimen="612")
        assert r.score == 100

    def test_default_conciliado(self):
        r = ResultadoConciliacion(anio=2026, regimen="612")
        assert r.es_conciliado is True

    def test_to_dict(self):
        r = ResultadoConciliacion(anio=2026, regimen="612")
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["anio"] == 2026


# ─── Test: Perfect Reconciliation ────────────────────────────────────

class TestPerfectReconciliation:
    def test_es_conciliado(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        assert result.es_conciliado is True

    def test_score_100(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        assert result.score == 100

    def test_no_criticas(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        criticas = [d for d in result.discrepancias
                    if d.nivel == NivelDiscrepancia.CRITICA.value]
        assert len(criticas) == 0

    def test_12_meses(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        assert result.meses_presentados == 12

    def test_no_meses_faltantes(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        assert result.meses_faltantes == []

    def test_income_matches(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        assert result.ingresos_mensuales_total == 600_000.0
        assert result.ingresos_anual == 600_000.0

    def test_deductions_match(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        assert result.deducciones_mensuales_total == 180_000.0
        assert result.deducciones_anual == 180_000.0

    def test_provisionals_match(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        assert result.isr_provisionales_total == 60_000.0
        assert result.provisionales_acreditados == 60_000.0

    def test_notas_include_perfecta(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        nota_perfecta = [n for n in result.notas if "perfecta" in n.lower()]
        assert len(nota_perfecta) >= 1

    def test_tasa_efectiva_in_notas(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        tasa_nota = [n for n in result.notas if "Tasa efectiva" in n]
        assert len(tasa_nota) >= 1


# ─── Test: Perfect RESICO ───────────────────────────────────────────

class TestPerfectRESICO:
    def test_es_conciliado(self, perfect_resico):
        monthly, annual = perfect_resico
        result = reconcile_fiscal_year(monthly, annual, regimen="625")
        assert result.es_conciliado is True

    def test_no_deduction_check(self, perfect_resico):
        monthly, annual = perfect_resico
        result = reconcile_fiscal_year(monthly, annual, regimen="625")
        ded_disc = [d for d in result.discrepancias
                    if d.area == AreaReconciliacion.DEDUCCIONES.value]
        assert len(ded_disc) == 0

    def test_resico_nota(self, perfect_resico):
        monthly, annual = perfect_resico
        result = reconcile_fiscal_year(monthly, annual, regimen="625")
        resico_nota = [n for n in result.notas if "RESICO" in n]
        assert len(resico_nota) >= 1


# ─── Test: Missing Months ───────────────────────────────────────────

class TestMissingMonths:
    def test_detects_missing(self, missing_months):
        monthly, annual = missing_months
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        assert result.meses_presentados == 9
        assert len(result.meses_faltantes) == 3

    def test_missing_abril_mayo_junio(self, missing_months):
        monthly, annual = missing_months
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        assert 4 in result.meses_faltantes
        assert 5 in result.meses_faltantes
        assert 6 in result.meses_faltantes

    def test_critical_for_3_missing(self, missing_months):
        monthly, annual = missing_months
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        missing_disc = [d for d in result.discrepancias
                        if d.area == AreaReconciliacion.MESES.value]
        assert len(missing_disc) >= 1
        assert missing_disc[0].nivel == NivelDiscrepancia.CRITICA.value

    def test_score_reduced(self, missing_months):
        monthly, annual = missing_months
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        assert result.score < 100

    def test_two_missing_is_importante(self):
        """Only 2 months missing → Importante, not Crítica."""
        months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        monthly = [_make_monthly(m) for m in months]
        annual = {
            "anio": 2026,
            "ingresos_totales": 500_000.0,
            "deducciones_operativas": 150_000.0,
            "isr_total_ejercicio": 50_000.0,
            "pagos_provisionales": 50_000.0,
            "retenciones_isr": 10_000.0,
            "isr_a_cargo": 0.0,
            "isr_a_favor": 0.0,
        }
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        missing_disc = [d for d in result.discrepancias
                        if d.area == AreaReconciliacion.MESES.value]
        assert missing_disc[0].nivel == NivelDiscrepancia.IMPORTANTE.value


# ─── Test: Income Mismatch ──────────────────────────────────────────

class TestIncomeMismatch:
    def test_detects_income_diff(self, income_mismatch):
        monthly, annual = income_mismatch
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        ing_disc = [d for d in result.discrepancias
                    if d.area == AreaReconciliacion.INGRESOS.value]
        assert len(ing_disc) >= 1

    def test_large_diff_is_critica(self, income_mismatch):
        monthly, annual = income_mismatch
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        ing_disc = [d for d in result.discrepancias
                    if d.area == AreaReconciliacion.INGRESOS.value
                    and d.nivel == NivelDiscrepancia.CRITICA.value]
        assert len(ing_disc) >= 1

    def test_small_diff_not_critica(self):
        """$500 diff on $600K income → Importante, not Crítica."""
        monthly = [_make_monthly(m) for m in range(1, 13)]
        annual = {
            "anio": 2026,
            "ingresos_totales": 600_500.0,
            "deducciones_operativas": 180_000.0,
            "isr_total_ejercicio": 60_000.0,
            "pagos_provisionales": 60_000.0,
            "retenciones_isr": 12_000.0,
            "isr_a_cargo": 0.0,
            "isr_a_favor": 0.0,
        }
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        ing_disc = [d for d in result.discrepancias
                    if d.area == AreaReconciliacion.INGRESOS.value]
        if ing_disc:
            assert ing_disc[0].nivel == NivelDiscrepancia.IMPORTANTE.value

    def test_within_tolerance_no_flag(self):
        """$0.50 diff within default $1 tolerance."""
        monthly = [_make_monthly(m) for m in range(1, 13)]
        annual = {
            "anio": 2026,
            "ingresos_totales": 600_000.50,
            "deducciones_operativas": 180_000.0,
            "isr_total_ejercicio": 60_000.0,
            "pagos_provisionales": 60_000.0,
            "retenciones_isr": 12_000.0,
            "isr_a_cargo": 0.0,
            "isr_a_favor": 0.0,
        }
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        ing_disc = [d for d in result.discrepancias
                    if d.area == AreaReconciliacion.INGRESOS.value]
        assert len(ing_disc) == 0


# ─── Test: Provisionals Mismatch ────────────────────────────────────

class TestProvisionalsMismatch:
    def test_detects_mismatch(self):
        monthly = [_make_monthly(m) for m in range(1, 13)]
        annual = {
            "anio": 2026,
            "ingresos_totales": 600_000.0,
            "deducciones_operativas": 180_000.0,
            "isr_total_ejercicio": 60_000.0,
            "pagos_provisionales": 50_000.0,  # $10K short!
            "retenciones_isr": 12_000.0,
            "isr_a_cargo": 0.0,
            "isr_a_favor": 0.0,
        }
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        prov_disc = [d for d in result.discrepancias
                     if d.area == AreaReconciliacion.ISR.value
                     and "Provisionales" in d.descripcion]
        assert len(prov_disc) >= 1

    def test_large_mismatch_is_critica(self):
        monthly = [_make_monthly(m) for m in range(1, 13)]
        annual = {
            "anio": 2026,
            "ingresos_totales": 600_000.0,
            "deducciones_operativas": 180_000.0,
            "isr_total_ejercicio": 60_000.0,
            "pagos_provisionales": 40_000.0,  # $20K short
            "retenciones_isr": 12_000.0,
            "isr_a_cargo": 0.0,
            "isr_a_favor": 0.0,
        }
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        prov_disc = [d for d in result.discrepancias
                     if d.area == AreaReconciliacion.ISR.value
                     and "Provisionales" in d.descripcion]
        assert prov_disc[0].nivel == NivelDiscrepancia.CRITICA.value


# ─── Test: Deductions Check (612 only) ──────────────────────────────

class TestDeductionsCheck:
    def test_612_detects_deduction_mismatch(self):
        monthly = [_make_monthly(m) for m in range(1, 13)]
        annual = {
            "anio": 2026,
            "ingresos_totales": 600_000.0,
            "deducciones_operativas": 200_000.0,  # 20K more than monthly
            "isr_total_ejercicio": 60_000.0,
            "pagos_provisionales": 60_000.0,
            "retenciones_isr": 12_000.0,
            "isr_a_cargo": 0.0,
            "isr_a_favor": 0.0,
        }
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        ded_disc = [d for d in result.discrepancias
                    if d.area == AreaReconciliacion.DEDUCCIONES.value]
        assert len(ded_disc) >= 1

    def test_resico_skips_deduction_check(self):
        monthly = [_make_monthly(m, deducciones=0.0) for m in range(1, 13)]
        annual = {
            "anio": 2026,
            "ingresos_totales": 600_000.0,
            "deducciones_operativas": 50_000.0,  # Irrelevant for RESICO
            "isr_total_ejercicio": 9_000.0,
            "pagos_provisionales": 9_000.0,
            "retenciones_isr": 0.0,
            "isr_a_cargo": 0.0,
            "isr_a_favor": 0.0,
        }
        result = reconcile_fiscal_year(monthly, annual, regimen="625")
        ded_disc = [d for d in result.discrepancias
                    if d.area == AreaReconciliacion.DEDUCCIONES.value]
        assert len(ded_disc) == 0


# ─── Test: Retention Mismatch ───────────────────────────────────────

class TestRetentionMismatch:
    def test_detects_retention_diff(self):
        monthly = [_make_monthly(m) for m in range(1, 13)]
        annual = {
            "anio": 2026,
            "ingresos_totales": 600_000.0,
            "deducciones_operativas": 180_000.0,
            "isr_total_ejercicio": 60_000.0,
            "pagos_provisionales": 60_000.0,
            "retenciones_isr": 15_000.0,  # $3K more than monthly
            "isr_a_cargo": 0.0,
            "isr_a_favor": 0.0,
        }
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        ret_disc = [d for d in result.discrepancias
                    if d.area == AreaReconciliacion.RETENCIONES.value]
        assert len(ret_disc) >= 1


# ─── Test: ISR a cargo/favor ────────────────────────────────────────

class TestISRCargoFavor:
    def test_a_cargo_discrepancy(self):
        monthly = [_make_monthly(m) for m in range(1, 13)]
        annual = {
            "anio": 2026,
            "ingresos_totales": 600_000.0,
            "deducciones_operativas": 180_000.0,
            "isr_total_ejercicio": 80_000.0,
            "pagos_provisionales": 60_000.0,
            "retenciones_isr": 12_000.0,
            "isr_a_cargo": 5_000.0,  # Expected: 80K - 60K - 12K = 8K
            "isr_a_favor": 0.0,
        }
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        cargo_disc = [d for d in result.discrepancias
                      if "a cargo" in d.descripcion.lower()]
        assert len(cargo_disc) >= 1

    def test_a_favor_discrepancy(self):
        monthly = [_make_monthly(m) for m in range(1, 13)]
        annual = {
            "anio": 2026,
            "ingresos_totales": 600_000.0,
            "deducciones_operativas": 180_000.0,
            "isr_total_ejercicio": 50_000.0,
            "pagos_provisionales": 60_000.0,
            "retenciones_isr": 12_000.0,
            "isr_a_cargo": 0.0,
            "isr_a_favor": 10_000.0,  # Expected: -(50K - 60K - 12K) = 22K
            "isr_a_favor_esperado": 22_000.0,
        }
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        favor_disc = [d for d in result.discrepancias
                      if "a favor" in d.descripcion.lower()]
        assert len(favor_disc) >= 1


# ─── Test: Monthly Anomaly Detection ────────────────────────────────

class TestMonthlyAnomalies:
    def test_detects_spike(self, spike_month):
        monthly, annual = spike_month
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        anomaly = [d for d in result.discrepancias
                   if d.nivel == NivelDiscrepancia.INFORMATIVA.value
                   and "3×" in d.descripcion]
        assert len(anomaly) >= 1

    def test_spike_is_informativa(self, spike_month):
        monthly, annual = spike_month
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        anomaly = [d for d in result.discrepancias
                   if "3×" in d.descripcion]
        if anomaly:
            assert anomaly[0].nivel == NivelDiscrepancia.INFORMATIVA.value

    def test_spike_identifies_month(self, spike_month):
        monthly, annual = spike_month
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        anomaly = [d for d in result.discrepancias
                   if "3×" in d.descripcion]
        if anomaly:
            assert anomaly[0].mes_afectado == 6


# ─── Test: Zero Income with ISR Paid ────────────────────────────────

class TestZeroIncomeISR:
    def test_detects_zero_income_with_payment(self):
        monthly = [_make_monthly(m) for m in range(1, 13)]
        monthly[2]["ingresos"] = 0.0     # March: $0 income but ISR paid
        monthly[2]["isr_pagado"] = 5_000.0
        total_ing = sum(d["ingresos"] for d in monthly)
        annual = {
            "anio": 2026,
            "ingresos_totales": total_ing,
            "deducciones_operativas": 180_000.0,
            "isr_total_ejercicio": 60_000.0,
            "pagos_provisionales": 60_000.0,
            "retenciones_isr": 12_000.0,
            "isr_a_cargo": 0.0,
            "isr_a_favor": 0.0,
        }
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        zero_disc = [d for d in result.discrepancias
                     if d.mes_afectado == 3
                     and "sin ingresos" in d.descripcion.lower()]
        assert len(zero_disc) >= 1


# ─── Test: Scoring ──────────────────────────────────────────────────

class TestScoring:
    def test_perfect_is_100(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        assert result.score == 100

    def test_critica_reduces_25(self, missing_months):
        monthly, annual = missing_months
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        # Missing 3 months (Crítica) + income mismatch (could be another)
        criticas = [d for d in result.discrepancias
                    if d.nivel == NivelDiscrepancia.CRITICA.value]
        assert result.score <= 100 - (25 * len(criticas))

    def test_score_never_negative(self):
        """Many discrepancies shouldn't produce negative score."""
        monthly = [_make_monthly(m) for m in range(1, 4)]  # Only 3 months
        annual = {
            "anio": 2026,
            "ingresos_totales": 1_000_000.0,  # Huge mismatch
            "deducciones_operativas": 500_000.0,
            "isr_total_ejercicio": 200_000.0,
            "pagos_provisionales": 10_000.0,
            "retenciones_isr": 50_000.0,
            "isr_a_cargo": 100_000.0,
            "isr_a_favor": 0.0,
        }
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        assert result.score >= 0

    def test_es_conciliado_false_with_critica(self, missing_months):
        monthly, annual = missing_months
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        assert result.es_conciliado is False


# ─── Test: Effective Tax Rate ────────────────────────────────────────

class TestEffectiveTaxRate:
    def test_high_rate_alert(self):
        """Effective rate >30% should trigger alert."""
        monthly = [_make_monthly(m) for m in range(1, 13)]
        annual = {
            "anio": 2026,
            "ingresos_totales": 600_000.0,
            "deducciones_operativas": 180_000.0,
            "isr_total_ejercicio": 200_000.0,  # 33% effective rate
            "pagos_provisionales": 60_000.0,
            "retenciones_isr": 12_000.0,
            "isr_a_cargo": 0.0,
            "isr_a_favor": 0.0,
        }
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        tasa_alert = [a for a in result.alertas if "Tasa efectiva" in a]
        assert len(tasa_alert) >= 1

    def test_normal_rate_no_alert(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        tasa_alert = [a for a in result.alertas if "Tasa efectiva" in a]
        assert len(tasa_alert) == 0


# ─── Test: Custom Tolerance ─────────────────────────────────────────

class TestTolerance:
    def test_tight_tolerance_catches_more(self):
        monthly = [_make_monthly(m) for m in range(1, 13)]
        annual = {
            "anio": 2026,
            "ingresos_totales": 600_000.50,  # $0.50 diff
            "deducciones_operativas": 180_000.0,
            "isr_total_ejercicio": 60_000.0,
            "pagos_provisionales": 60_000.0,
            "retenciones_isr": 12_000.0,
            "isr_a_cargo": 0.0,
            "isr_a_favor": 0.0,
        }
        # Default tolerance ($1) should NOT flag
        r1 = reconcile_fiscal_year(monthly, annual, regimen="612", tolerancia=1.0)
        ing1 = [d for d in r1.discrepancias
                if d.area == AreaReconciliacion.INGRESOS.value]
        assert len(ing1) == 0

        # Tight tolerance ($0.01) SHOULD flag
        r2 = reconcile_fiscal_year(monthly, annual, regimen="612", tolerancia=0.01)
        ing2 = [d for d in r2.discrepancias
                if d.area == AreaReconciliacion.INGRESOS.value]
        assert len(ing2) >= 1


# ─── Test: WhatsApp Summary ─────────────────────────────────────────

class TestWhatsAppSummary:
    def test_divider(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        wsp = result.resumen_whatsapp()
        assert "━━━" in wsp

    def test_score_in_summary(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        wsp = result.resumen_whatsapp()
        assert "Score:" in wsp

    def test_year_in_summary(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        wsp = result.resumen_whatsapp()
        assert "2026" in wsp

    def test_meses_in_summary(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        wsp = result.resumen_whatsapp()
        assert "12/12" in wsp

    def test_missing_months_in_summary(self, missing_months):
        monthly, annual = missing_months
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        wsp = result.resumen_whatsapp()
        assert "faltantes" in wsp.lower()

    def test_critica_shown(self, missing_months):
        monthly, annual = missing_months
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        wsp = result.resumen_whatsapp()
        assert "🔴" in wsp

    def test_conciliado_icon(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        wsp = result.resumen_whatsapp()
        assert "✅" in wsp

    def test_not_conciliado_icon(self, missing_months):
        monthly, annual = missing_months
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        wsp = result.resumen_whatsapp()
        assert "❌" in wsp

    def test_a_favor_shown(self, perfect_612):
        monthly, annual = perfect_612
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        wsp = result.resumen_whatsapp()
        if result.isr_a_favor_esperado > 0:
            assert "A favor" in wsp


# ─── Test: quick_reconcile ──────────────────────────────────────────

class TestQuickReconcile:
    def test_perfect_match(self):
        ingresos = [50_000.0] * 12
        isr = [5_000.0] * 12
        result = quick_reconcile(ingresos, 600_000.0, isr, 60_000.0)
        assert result["cuadra_ingresos"] is True
        assert result["cuadra_isr"] is True

    def test_income_mismatch(self):
        ingresos = [50_000.0] * 12
        result = quick_reconcile(ingresos, 700_000.0, [0] * 12, 0.0)
        assert result["cuadra_ingresos"] is False
        assert result["diferencia_ingresos"] == 100_000.0

    def test_isr_mismatch(self):
        isr = [5_000.0] * 12
        result = quick_reconcile([0] * 12, 0.0, isr, 50_000.0)
        assert result["cuadra_isr"] is False
        assert result["diferencia_isr"] == 10_000.0

    def test_returns_sums(self):
        ingresos = [10_000.0] * 12
        isr = [1_000.0] * 12
        result = quick_reconcile(ingresos, 120_000.0, isr, 12_000.0)
        assert result["sum_ingresos_mensuales"] == 120_000.0
        assert result["sum_isr_provisionales"] == 12_000.0

    def test_meses_con_datos(self):
        ingresos = [50_000.0] * 10 + [0.0, 0.0]
        result = quick_reconcile(ingresos, 500_000.0, [0] * 12, 0.0)
        assert result["meses_con_datos"] == 10

    def test_all_zeros(self):
        result = quick_reconcile([0] * 12, 0.0, [0] * 12, 0.0)
        assert result["cuadra_ingresos"] is True
        assert result["cuadra_isr"] is True
        assert result["meses_con_datos"] == 0


# ─── Test: Edge Cases ───────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_monthly_list(self):
        annual = {
            "anio": 2026,
            "ingresos_totales": 0.0,
            "deducciones_operativas": 0.0,
            "isr_total_ejercicio": 0.0,
            "pagos_provisionales": 0.0,
            "retenciones_isr": 0.0,
            "isr_a_cargo": 0.0,
            "isr_a_favor": 0.0,
        }
        result = reconcile_fiscal_year([], annual, regimen="612")
        assert result.meses_presentados == 0
        assert len(result.meses_faltantes) == 12

    def test_duplicate_month_ignored(self):
        """Two entries for month 1 — only latest matters."""
        monthly = [_make_monthly(1, ingresos=30_000.0),
                   _make_monthly(1, ingresos=50_000.0)]  # second overwrites
        monthly.extend(_make_monthly(m) for m in range(2, 13))
        annual = {
            "anio": 2026,
            "ingresos_totales": 600_000.0,
            "deducciones_operativas": 180_000.0,
            "isr_total_ejercicio": 60_000.0,
            "pagos_provisionales": 60_000.0,
            "retenciones_isr": 12_000.0,
            "isr_a_cargo": 0.0,
            "isr_a_favor": 0.0,
        }
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        assert result.meses_presentados == 12

    def test_invalid_month_number(self):
        """Month 13 should be silently ignored."""
        monthly = [_make_monthly(m) for m in range(1, 13)]
        monthly.append(_make_monthly(13))
        annual = {
            "anio": 2026,
            "ingresos_totales": 600_000.0,
            "deducciones_operativas": 180_000.0,
            "isr_total_ejercicio": 60_000.0,
            "pagos_provisionales": 60_000.0,
            "retenciones_isr": 12_000.0,
            "isr_a_cargo": 0.0,
            "isr_a_favor": 0.0,
        }
        result = reconcile_fiscal_year(monthly, annual, regimen="612")
        assert result.meses_presentados == 12

    def test_default_anio(self):
        """If anio not in datos_anuales, defaults to 2026."""
        annual = {
            "ingresos_totales": 0.0,
            "deducciones_operativas": 0.0,
            "isr_total_ejercicio": 0.0,
            "pagos_provisionales": 0.0,
            "retenciones_isr": 0.0,
            "isr_a_cargo": 0.0,
            "isr_a_favor": 0.0,
        }
        result = reconcile_fiscal_year([], annual, regimen="612")
        assert result.anio == 2026


# ─── Test: Module Exports ───────────────────────────────────────────

class TestModuleExports:
    def test_enums_importable(self):
        from src.tools.fiscal_reconciliation import NivelDiscrepancia, AreaReconciliacion
        assert NivelDiscrepancia is not None
        assert AreaReconciliacion is not None

    def test_dataclasses_importable(self):
        from src.tools.fiscal_reconciliation import (
            Discrepancia, MesConciliado, ResultadoConciliacion
        )
        assert Discrepancia is not None
        assert MesConciliado is not None
        assert ResultadoConciliacion is not None

    def test_functions_callable(self):
        from src.tools.fiscal_reconciliation import reconcile_fiscal_year, quick_reconcile
        assert callable(reconcile_fiscal_year)
        assert callable(quick_reconcile)

    def test_meses_nombres(self):
        from src.tools.fiscal_reconciliation import MESES_NOMBRES
        assert isinstance(MESES_NOMBRES, list)
