"""Tests for OpenDoc Fiscal Alerts / Watchdog Engine.

Comprehensive tests for:
- Certificate expiry checks (e.firma, CSD)
- RESICO income cap monitoring
- Deduction pattern detection
- Missing monthly filings
- Employee compliance gaps
- Full fiscal health report generation
- Health score calculation
- WhatsApp formatting
- Enum definitions
- Module exports from src.tools
"""

import pytest
from datetime import date, timedelta

from src.tools.fiscal_alerts import (
    # Core functions
    check_certificate_expiry,
    check_resico_income_cap,
    check_deduction_patterns,
    check_missing_filings,
    check_employee_compliance,
    generate_fiscal_health_report,
    # Data classes
    AlertaFiscal,
    ReporteAlertas,
    # Enums
    NivelAlerta,
    CategoriaAlerta,
)

# Fixed reference date so tests never depend on today's date
REF = date(2026, 2, 15)


# ══════════════════════════════════════════════════════════════════════
# TEST: NivelAlerta Enum
# ══════════════════════════════════════════════════════════════════════

class TestNivelAlertaEnum:
    """Test NivelAlerta enum values and behaviour."""

    def test_urgente_value(self):
        assert NivelAlerta.URGENTE.value == "Urgente"

    def test_importante_value(self):
        assert NivelAlerta.IMPORTANTE.value == "Importante"

    def test_preventiva_value(self):
        assert NivelAlerta.PREVENTIVA.value == "Preventiva"

    def test_informativa_value(self):
        assert NivelAlerta.INFORMATIVA.value == "Informativa"

    def test_is_str_enum(self):
        """NivelAlerta members are also strings."""
        assert isinstance(NivelAlerta.URGENTE, str)
        assert NivelAlerta.URGENTE == "Urgente"

    def test_member_count(self):
        assert len(NivelAlerta) == 4


# ══════════════════════════════════════════════════════════════════════
# TEST: CategoriaAlerta Enum
# ══════════════════════════════════════════════════════════════════════

class TestCategoriaAlertaEnum:
    """Test CategoriaAlerta enum values."""

    def test_certificados(self):
        assert CategoriaAlerta.CERTIFICADOS.value == "Certificados"

    def test_declaraciones(self):
        assert CategoriaAlerta.DECLARACIONES.value == "Declaraciones"

    def test_ingresos(self):
        assert CategoriaAlerta.INGRESOS.value == "Ingresos"

    def test_deducciones(self):
        assert CategoriaAlerta.DEDUCCIONES.value == "Deducciones"

    def test_pagos(self):
        assert CategoriaAlerta.PAGOS.value == "Pagos"

    def test_empleados(self):
        assert CategoriaAlerta.EMPLEADOS.value == "Empleados"

    def test_regimen(self):
        assert CategoriaAlerta.REGIMEN.value == "Régimen"

    def test_cfdi(self):
        assert CategoriaAlerta.CFDI.value == "CFDI"

    def test_is_str_enum(self):
        assert isinstance(CategoriaAlerta.CERTIFICADOS, str)

    def test_member_count(self):
        assert len(CategoriaAlerta) == 8


# ══════════════════════════════════════════════════════════════════════
# TEST: Certificate Expiry Checks
# ══════════════════════════════════════════════════════════════════════

class TestCheckCertificateExpiry:
    """Test e.firma and CSD certificate expiry detection."""

    def test_efirma_expired(self):
        """e.firma that expired 10 days ago -> URGENTE alert."""
        expired = REF - timedelta(days=10)
        alerts = check_certificate_expiry(efirma_expiry=expired, reference_date=REF)
        assert len(alerts) == 1
        assert alerts[0].nivel == NivelAlerta.URGENTE.value
        assert "VENCIDO" in alerts[0].titulo
        assert "e.firma" in alerts[0].titulo
        assert alerts[0].dias_restantes == -10
        assert alerts[0].fecha_limite == expired.isoformat()
        assert alerts[0].categoria == CategoriaAlerta.CERTIFICADOS.value

    def test_efirma_expired_long_ago(self):
        """e.firma expired over a year ago -> mentions presencial."""
        expired = REF - timedelta(days=400)
        alerts = check_certificate_expiry(efirma_expiry=expired, reference_date=REF)
        assert len(alerts) == 1
        assert "venció hace 400 días" in alerts[0].mensaje
        assert "presencial" in alerts[0].accion_requerida

    def test_csd_expired(self):
        """CSD that expired -> URGENTE alert."""
        expired = REF - timedelta(days=5)
        alerts = check_certificate_expiry(csd_expiry=expired, reference_date=REF)
        assert len(alerts) == 1
        assert "CSD" in alerts[0].titulo
        assert "VENCIDO" in alerts[0].titulo

    def test_efirma_expires_within_30_days(self):
        """e.firma expiring in 20 days -> URGENTE, 'por vencer'."""
        expiry = REF + timedelta(days=20)
        alerts = check_certificate_expiry(efirma_expiry=expiry, reference_date=REF)
        assert len(alerts) == 1
        assert alerts[0].nivel == NivelAlerta.URGENTE.value
        assert "por vencer" in alerts[0].titulo
        assert alerts[0].dias_restantes == 20

    def test_csd_expires_within_30_days(self):
        """CSD expiring in 5 days -> URGENTE."""
        expiry = REF + timedelta(days=5)
        alerts = check_certificate_expiry(csd_expiry=expiry, reference_date=REF)
        assert len(alerts) == 1
        assert alerts[0].nivel == NivelAlerta.URGENTE.value
        assert "CSD" in alerts[0].titulo

    def test_efirma_expires_exactly_30_days(self):
        """e.firma expiring in exactly 30 days -> still URGENTE (<=30)."""
        expiry = REF + timedelta(days=30)
        alerts = check_certificate_expiry(efirma_expiry=expiry, reference_date=REF)
        assert len(alerts) == 1
        assert alerts[0].nivel == NivelAlerta.URGENTE.value

    def test_efirma_expires_31_days(self):
        """e.firma expiring in 31 days -> IMPORTANTE (31-90 range)."""
        expiry = REF + timedelta(days=31)
        alerts = check_certificate_expiry(efirma_expiry=expiry, reference_date=REF)
        assert len(alerts) == 1
        assert alerts[0].nivel == NivelAlerta.IMPORTANTE.value
        assert "vence pronto" in alerts[0].titulo

    def test_efirma_expires_within_90_days(self):
        """e.firma expiring in 60 days -> IMPORTANTE."""
        expiry = REF + timedelta(days=60)
        alerts = check_certificate_expiry(efirma_expiry=expiry, reference_date=REF)
        assert len(alerts) == 1
        assert alerts[0].nivel == NivelAlerta.IMPORTANTE.value
        assert alerts[0].dias_restantes == 60

    def test_efirma_expires_exactly_90_days(self):
        """e.firma expiring in exactly 90 days -> IMPORTANTE (<=90)."""
        expiry = REF + timedelta(days=90)
        alerts = check_certificate_expiry(efirma_expiry=expiry, reference_date=REF)
        assert len(alerts) == 1
        assert alerts[0].nivel == NivelAlerta.IMPORTANTE.value

    def test_efirma_expires_91_days(self):
        """e.firma expiring in 91 days -> no alert (far future)."""
        expiry = REF + timedelta(days=91)
        alerts = check_certificate_expiry(efirma_expiry=expiry, reference_date=REF)
        assert len(alerts) == 0

    def test_far_future_no_alert(self):
        """Certificate valid for 2 years -> no alert."""
        expiry = REF + timedelta(days=730)
        alerts = check_certificate_expiry(
            efirma_expiry=expiry,
            csd_expiry=expiry,
            reference_date=REF,
        )
        assert len(alerts) == 0

    def test_no_dates_provided(self):
        """No certificate dates -> no alerts."""
        alerts = check_certificate_expiry(reference_date=REF)
        assert len(alerts) == 0

    def test_none_dates_explicitly(self):
        """Explicit None dates -> no alerts."""
        alerts = check_certificate_expiry(
            efirma_expiry=None,
            csd_expiry=None,
            reference_date=REF,
        )
        assert len(alerts) == 0

    def test_both_expired(self):
        """Both e.firma and CSD expired -> two alerts."""
        expired_efirma = REF - timedelta(days=30)
        expired_csd = REF - timedelta(days=15)
        alerts = check_certificate_expiry(
            efirma_expiry=expired_efirma,
            csd_expiry=expired_csd,
            reference_date=REF,
        )
        assert len(alerts) == 2
        assert all(a.nivel == NivelAlerta.URGENTE.value for a in alerts)

    def test_one_expired_one_soon(self):
        """e.firma expired, CSD expiring in 45 days -> one URGENTE + one IMPORTANTE."""
        alerts = check_certificate_expiry(
            efirma_expiry=REF - timedelta(days=5),
            csd_expiry=REF + timedelta(days=45),
            reference_date=REF,
        )
        assert len(alerts) == 2
        niveles = {a.nivel for a in alerts}
        assert NivelAlerta.URGENTE.value in niveles
        assert NivelAlerta.IMPORTANTE.value in niveles

    def test_expired_has_url_portal(self):
        """Expired certificate alert includes SAT URL."""
        alerts = check_certificate_expiry(
            efirma_expiry=REF - timedelta(days=1),
            reference_date=REF,
        )
        assert alerts[0].url_portal != ""
        assert "sat.gob.mx" in alerts[0].url_portal

    def test_expired_has_fundamento(self):
        """Expired certificate references CFF Art. 17-D."""
        alerts = check_certificate_expiry(
            efirma_expiry=REF - timedelta(days=1),
            reference_date=REF,
        )
        assert "17-D" in alerts[0].fundamento

    def test_expired_has_consecuencia(self):
        """Expired certificate warns about inability to invoice."""
        alerts = check_certificate_expiry(
            efirma_expiry=REF - timedelta(days=1),
            reference_date=REF,
        )
        assert "CFDI" in alerts[0].consecuencia


# ══════════════════════════════════════════════════════════════════════
# TEST: RESICO Income Cap Checks
# ══════════════════════════════════════════════════════════════════════

class TestCheckResicoIncomeCap:
    """Test RESICO $3.5M income cap monitoring."""

    def test_income_exceeded_cap(self):
        """Accumulated income >= $3.5M -> URGENTE."""
        alerts = check_resico_income_cap(
            ingresos_acumulados=3_600_000,
            mes_actual=8,
            reference_date=REF,
        )
        assert len(alerts) == 1
        assert alerts[0].nivel == NivelAlerta.URGENTE.value
        assert "EXCEDIDO" in alerts[0].titulo
        assert alerts[0].categoria == CategoriaAlerta.REGIMEN.value
        assert "113-E" in alerts[0].fundamento

    def test_income_exactly_at_cap(self):
        """Exactly $3.5M -> URGENTE (>= check)."""
        alerts = check_resico_income_cap(
            ingresos_acumulados=3_500_000,
            mes_actual=12,
            reference_date=REF,
        )
        assert len(alerts) == 1
        assert alerts[0].nivel == NivelAlerta.URGENTE.value

    def test_projection_exceeds_cap(self):
        """Low accumulated but projection exceeds $3.5M -> IMPORTANTE."""
        # $2M in 6 months -> projection $4M/year
        alerts = check_resico_income_cap(
            ingresos_acumulados=2_000_000,
            mes_actual=6,
            reference_date=REF,
        )
        assert len(alerts) == 1
        assert alerts[0].nivel == NivelAlerta.IMPORTANTE.value
        assert "Proyección" in alerts[0].titulo
        assert "612" in alerts[0].accion_requerida

    def test_sixty_percent_warning(self):
        """Over 60% of cap but projection OK -> PREVENTIVA."""
        # $2.2M in 10 months -> projection $2.64M (under cap), but 62.8% used
        alerts = check_resico_income_cap(
            ingresos_acumulados=2_200_000,
            mes_actual=10,
            reference_date=REF,
        )
        assert len(alerts) == 1
        assert alerts[0].nivel == NivelAlerta.PREVENTIVA.value
        assert "%" in alerts[0].titulo

    def test_safe_low_income(self):
        """Low income, well under cap -> no alert."""
        alerts = check_resico_income_cap(
            ingresos_acumulados=500_000,
            mes_actual=6,
            reference_date=REF,
        )
        assert len(alerts) == 0

    def test_zero_income_no_alert(self):
        """Zero income -> no alert."""
        alerts = check_resico_income_cap(
            ingresos_acumulados=0,
            mes_actual=3,
            reference_date=REF,
        )
        assert len(alerts) == 0

    def test_negative_income_no_alert(self):
        """Negative income -> no alert."""
        alerts = check_resico_income_cap(
            ingresos_acumulados=-100_000,
            mes_actual=3,
            reference_date=REF,
        )
        assert len(alerts) == 0

    def test_month_zero_uses_twelve_multiplier(self):
        """mes_actual=0 -> projection = income * 12."""
        # $300K * 12 = $3.6M (exceeds cap)
        alerts = check_resico_income_cap(
            ingresos_acumulados=300_000,
            mes_actual=0,
            reference_date=REF,
        )
        assert len(alerts) == 1
        assert alerts[0].nivel == NivelAlerta.IMPORTANTE.value

    def test_exceeded_has_consecuencia(self):
        """Exceeded cap alert mentions expulsion to 612."""
        alerts = check_resico_income_cap(
            ingresos_acumulados=4_000_000,
            mes_actual=10,
        )
        assert "612" in alerts[0].consecuencia


# ══════════════════════════════════════════════════════════════════════
# TEST: Deduction Pattern Checks
# ══════════════════════════════════════════════════════════════════════

class TestCheckDeductionPatterns:
    """Test suspicious deduction pattern detection."""

    def test_deductions_over_90_percent_critical(self):
        """>90% deduction ratio -> URGENTE, SAT audit warning."""
        alerts = check_deduction_patterns(
            ingresos_acumulados=100_000,
            deducciones_acumuladas=95_000,
            mes_actual=6,
        )
        urgentes = [a for a in alerts if a.nivel == NivelAlerta.URGENTE.value]
        assert len(urgentes) >= 1
        urgente = urgentes[0]
        assert "excesivas" in urgente.titulo.lower()
        assert urgente.categoria == CategoriaAlerta.DEDUCCIONES.value
        assert "SAT" in urgente.consecuencia

    def test_deductions_over_75_percent_warning(self):
        """>75% deduction ratio -> IMPORTANTE."""
        alerts = check_deduction_patterns(
            ingresos_acumulados=100_000,
            deducciones_acumuladas=80_000,
            mes_actual=6,
        )
        importantes = [a for a in alerts if a.nivel == NivelAlerta.IMPORTANTE.value]
        assert len(importantes) >= 1
        assert "alta" in importantes[0].titulo.lower()

    def test_deductions_exactly_90_percent(self):
        """Exactly 90% -> falls in >75% warning, not >90% critical."""
        alerts = check_deduction_patterns(
            ingresos_acumulados=100_000,
            deducciones_acumuladas=90_000,
            mes_actual=6,
        )
        # 90% is not > 90, so it hits the >75 bracket
        importantes = [a for a in alerts if a.nivel == NivelAlerta.IMPORTANTE.value]
        assert len(importantes) >= 1

    def test_deductions_exactly_91_percent(self):
        """91% -> hits the >90% URGENTE bracket."""
        alerts = check_deduction_patterns(
            ingresos_acumulados=100_000,
            deducciones_acumuladas=91_000,
            mes_actual=6,
        )
        urgentes = [a for a in alerts if a.nivel == NivelAlerta.URGENTE.value]
        assert len(urgentes) >= 1

    def test_low_deductions_resico_suggestion(self):
        """<30% deductions + under RESICO cap -> INFORMATIVA RESICO hint."""
        alerts = check_deduction_patterns(
            ingresos_acumulados=200_000,
            deducciones_acumuladas=40_000,  # 20%
            mes_actual=6,
        )
        informativos = [a for a in alerts if a.nivel == NivelAlerta.INFORMATIVA.value]
        assert len(informativos) == 1
        assert "RESICO" in informativos[0].titulo

    def test_normal_deductions_no_alert(self):
        """50% deductions -> no warning, no RESICO hint (high income)."""
        # Income too high for RESICO suggestion at mes_actual=6:
        # $3.5M * (6/12) = $1.75M cap at 6 months
        # We need ingresos > that to avoid the RESICO hint
        alerts = check_deduction_patterns(
            ingresos_acumulados=2_000_000,
            deducciones_acumuladas=1_000_000,  # 50%
            mes_actual=6,
        )
        assert len(alerts) == 0

    def test_zero_income_no_alert(self):
        """Zero income -> no alert regardless of deductions."""
        alerts = check_deduction_patterns(
            ingresos_acumulados=0,
            deducciones_acumuladas=50_000,
            mes_actual=6,
        )
        assert len(alerts) == 0

    def test_deductions_75_percent_boundary(self):
        """Exactly 75% -> not >75%, no warning."""
        alerts = check_deduction_patterns(
            ingresos_acumulados=2_000_000,
            deducciones_acumuladas=1_500_000,  # 75% exact
            mes_actual=6,
        )
        # 75% is not > 75, no IMPORTANTE alert
        importantes = [a for a in alerts if a.nivel == NivelAlerta.IMPORTANTE.value]
        assert len(importantes) == 0


# ══════════════════════════════════════════════════════════════════════
# TEST: Missing Filings Detection
# ══════════════════════════════════════════════════════════════════════

class TestCheckMissingFilings:
    """Test detection of missing monthly declarations."""

    def test_missing_months_detected(self):
        """Some months not filed -> URGENTE alert listing them."""
        # REF is 2026-02-15. January 2026 was due 2026-02-17.
        # Since REF < Feb 17, January is NOT yet required.
        # For months to be missing, the due date must be < REF.
        # Dec 2025 is due Jan 17, 2026 -> REF > Jan 17 -> Dec required.
        # Nov 2025 is due Dec 17, 2025 -> REF > Dec 17 -> Nov required.
        # Etc. We test for anio=2025 where many months should be due.
        alerts = check_missing_filings(
            meses_declarados=[1, 2, 3],
            anio=2025,
            reference_date=REF,
        )
        assert len(alerts) == 1
        assert alerts[0].nivel == NivelAlerta.URGENTE.value
        assert "pendientes" in alerts[0].titulo
        assert "Abril" in alerts[0].mensaje  # Month 4 missing
        assert alerts[0].categoria == CategoriaAlerta.DECLARACIONES.value

    def test_all_months_filed(self):
        """All months filed for past year -> no alerts."""
        alerts = check_missing_filings(
            meses_declarados=list(range(1, 13)),
            anio=2025,
            reference_date=REF,
        )
        assert len(alerts) == 0

    def test_future_months_not_required(self):
        """Months whose deadline hasn't passed yet are not required."""
        # REF = 2026-02-15. January 2026 due date = 2026-02-17.
        # REF (Feb 15) is NOT > Feb 17, so January is not yet required.
        alerts = check_missing_filings(
            meses_declarados=[],
            anio=2026,
            reference_date=REF,
        )
        # January 2026 due Feb 17 (REF < Feb 17), so not required yet
        assert len(alerts) == 0

    def test_one_month_just_past_due(self):
        """Test with reference date just after a due date."""
        # Use ref_date = 2026-02-18, so January 2026 (due Feb 17) is past due
        ref = date(2026, 2, 18)
        alerts = check_missing_filings(
            meses_declarados=[],
            anio=2026,
            reference_date=ref,
        )
        assert len(alerts) == 1
        assert "Enero" in alerts[0].mensaje

    def test_partially_filed(self):
        """Some months filed, some not -> alert for missing ones only."""
        ref = date(2026, 6, 20)  # Well into year, many months due
        alerts = check_missing_filings(
            meses_declarados=[1, 2, 3],
            anio=2026,
            reference_date=ref,
        )
        assert len(alerts) == 1
        # Months 4 and 5 should be due (April due May 17, May due June 17)
        assert "Abril" in alerts[0].mensaje
        assert "Mayo" in alerts[0].mensaje

    def test_missing_filings_count_in_titulo(self):
        """Title includes count of missing months."""
        ref = date(2026, 4, 20)  # After March due date
        # Months 1, 2, 3 should be due by now for 2026
        alerts = check_missing_filings(
            meses_declarados=[1],  # Only January filed
            anio=2026,
            reference_date=ref,
        )
        assert len(alerts) == 1
        assert "2 declaraciones" in alerts[0].titulo

    def test_missing_filings_has_consecuencia(self):
        """Missing filings alert mentions fines."""
        alerts = check_missing_filings(
            meses_declarados=[1, 2, 3],
            anio=2025,
            reference_date=REF,
        )
        assert "multa" in alerts[0].consecuencia.lower() or "Multa" in alerts[0].consecuencia

    def test_missing_filings_has_url(self):
        """Missing filings alert has SAT portal URL."""
        alerts = check_missing_filings(
            meses_declarados=[],
            anio=2025,
            reference_date=REF,
        )
        assert "sat.gob.mx" in alerts[0].url_portal


# ══════════════════════════════════════════════════════════════════════
# TEST: Employee Compliance
# ══════════════════════════════════════════════════════════════════════

class TestCheckEmployeeCompliance:
    """Test employee-related compliance checks."""

    def test_employees_not_in_imss(self):
        """More total employees than IMSS-registered -> URGENTE."""
        alerts = check_employee_compliance(
            tiene_empleados=True,
            empleados_imss=1,
            empleados_total=3,
        )
        assert len(alerts) == 1
        assert alerts[0].nivel == NivelAlerta.URGENTE.value
        assert "2 empleado(s)" in alerts[0].titulo
        assert alerts[0].categoria == CategoriaAlerta.EMPLEADOS.value
        assert "304" in alerts[0].fundamento

    def test_all_employees_in_imss(self):
        """All employees registered -> no alert for IMSS registration."""
        alerts = check_employee_compliance(
            tiene_empleados=True,
            empleados_imss=3,
            empleados_total=3,
        )
        assert len(alerts) == 0

    def test_bimonthly_payment_lag(self):
        """IMSS payment more than 1 bimestre behind -> URGENTE."""
        alerts = check_employee_compliance(
            tiene_empleados=True,
            empleados_imss=2,
            empleados_total=2,
            ultimo_pago_imss_bimestre=1,
            bimestre_actual=4,
        )
        assert len(alerts) == 1
        assert "3 bimestres atrasados" in alerts[0].titulo
        assert "embargo" in alerts[0].consecuencia.lower()

    def test_bimonthly_payment_one_behind_no_alert(self):
        """Only 1 bimestre behind -> no alert (tolerance)."""
        alerts = check_employee_compliance(
            tiene_empleados=True,
            empleados_imss=2,
            empleados_total=2,
            ultimo_pago_imss_bimestre=3,
            bimestre_actual=4,
        )
        assert len(alerts) == 0

    def test_bimonthly_payment_current_no_alert(self):
        """IMSS payment current -> no alert."""
        alerts = check_employee_compliance(
            tiene_empleados=True,
            empleados_imss=2,
            empleados_total=2,
            ultimo_pago_imss_bimestre=4,
            bimestre_actual=4,
        )
        assert len(alerts) == 0

    def test_no_employees(self):
        """No employees -> no alerts."""
        alerts = check_employee_compliance(tiene_empleados=False)
        assert len(alerts) == 0

    def test_no_employees_ignores_other_params(self):
        """If tiene_empleados=False, other params are irrelevant."""
        alerts = check_employee_compliance(
            tiene_empleados=False,
            empleados_imss=0,
            empleados_total=5,
            ultimo_pago_imss_bimestre=0,
            bimestre_actual=4,
        )
        assert len(alerts) == 0

    def test_both_imss_and_payment_issues(self):
        """Employees not in IMSS AND bimonthly payment lag -> two alerts."""
        alerts = check_employee_compliance(
            tiene_empleados=True,
            empleados_imss=1,
            empleados_total=3,
            ultimo_pago_imss_bimestre=1,
            bimestre_actual=4,
        )
        assert len(alerts) == 2
        assert all(a.nivel == NivelAlerta.URGENTE.value for a in alerts)

    def test_imss_missing_has_consecuencia(self):
        """IMSS missing employee alert mentions fine amount."""
        alerts = check_employee_compliance(
            tiene_empleados=True,
            empleados_imss=0,
            empleados_total=1,
        )
        assert "multa" in alerts[0].consecuencia.lower() or "Multa" in alerts[0].consecuencia


# ══════════════════════════════════════════════════════════════════════
# TEST: Full Fiscal Health Report
# ══════════════════════════════════════════════════════════════════════

class TestGenerateFiscalHealthReport:
    """Test the main generate_fiscal_health_report function."""

    def test_clean_report_no_alerts(self):
        """Everything in order -> 0 alerts, score 100."""
        report = generate_fiscal_health_report(
            regimen="612",
            efirma_expiry=REF + timedelta(days=365),
            csd_expiry=REF + timedelta(days=365),
            ingresos_acumulados=0,
            reference_date=REF,
        )
        assert report.total_alertas == 0
        assert report.score_salud_fiscal == 100
        assert report.fecha_reporte == REF.isoformat()
        assert report.regimen == "612"

    def test_report_with_expired_certificate(self):
        """Expired e.firma -> 1 URGENTE alert, score reduced."""
        report = generate_fiscal_health_report(
            regimen="612",
            efirma_expiry=REF - timedelta(days=10),
            reference_date=REF,
        )
        assert report.total_alertas >= 1
        assert report.urgentes >= 1
        assert report.score_salud_fiscal < 100

    def test_resico_cap_only_checked_for_625(self):
        """RESICO cap is only checked for regimen 625, not 612."""
        report = generate_fiscal_health_report(
            regimen="612",
            ingresos_acumulados=4_000_000,
            mes_actual=6,
            reference_date=REF,
        )
        # No RESICO alert for 612
        regimen_alerts = [a for a in report.alertas if a.categoria == CategoriaAlerta.REGIMEN.value]
        resico_exceeded = [a for a in regimen_alerts if "TOPE RESICO" in a.titulo]
        assert len(resico_exceeded) == 0

    def test_resico_cap_checked_for_625(self):
        """RESICO cap IS checked for regimen 625."""
        report = generate_fiscal_health_report(
            regimen="625",
            ingresos_acumulados=4_000_000,
            mes_actual=6,
            reference_date=REF,
        )
        regimen_alerts = [a for a in report.alertas if "TOPE RESICO" in a.titulo]
        assert len(regimen_alerts) == 1

    def test_deductions_only_checked_for_612(self):
        """Deduction patterns checked only for regimen 612."""
        report = generate_fiscal_health_report(
            regimen="625",
            ingresos_acumulados=100_000,
            deducciones_acumuladas=95_000,
            mes_actual=6,
            reference_date=REF,
        )
        deduction_alerts = [a for a in report.alertas if a.categoria == CategoriaAlerta.DEDUCCIONES.value]
        assert len(deduction_alerts) == 0

    def test_missing_filings_only_when_provided(self):
        """Missing filings checked only when meses_declarados is not None."""
        report = generate_fiscal_health_report(
            regimen="612",
            meses_declarados=None,
            anio=2025,
            reference_date=REF,
        )
        filing_alerts = [a for a in report.alertas if a.categoria == CategoriaAlerta.DECLARACIONES.value]
        assert len(filing_alerts) == 0

    def test_employees_only_when_tiene_empleados(self):
        """Employee checks only run when tiene_empleados=True."""
        report = generate_fiscal_health_report(
            regimen="612",
            tiene_empleados=False,
            empleados_total=5,
            empleados_imss=0,
            reference_date=REF,
        )
        emp_alerts = [a for a in report.alertas if a.categoria == CategoriaAlerta.EMPLEADOS.value]
        assert len(emp_alerts) == 0

    def test_alerts_sorted_by_severity(self):
        """Alerts are sorted: URGENTE first, then IMPORTANTE, etc."""
        report = generate_fiscal_health_report(
            regimen="612",
            efirma_expiry=REF - timedelta(days=5),       # URGENTE
            csd_expiry=REF + timedelta(days=60),           # IMPORTANTE
            ingresos_acumulados=100_000,
            deducciones_acumuladas=20_000,                 # might generate INFORMATIVA
            mes_actual=6,
            reference_date=REF,
        )
        if len(report.alertas) >= 2:
            nivel_orden = {
                NivelAlerta.URGENTE.value: 0,
                NivelAlerta.IMPORTANTE.value: 1,
                NivelAlerta.PREVENTIVA.value: 2,
                NivelAlerta.INFORMATIVA.value: 3,
            }
            for i in range(len(report.alertas) - 1):
                current = nivel_orden.get(report.alertas[i].nivel, 9)
                next_one = nivel_orden.get(report.alertas[i + 1].nivel, 9)
                assert current <= next_one

    def test_count_fields_match_alertas(self):
        """Urgentes, importantes, etc. counts match actual alert levels."""
        report = generate_fiscal_health_report(
            regimen="612",
            efirma_expiry=REF - timedelta(days=5),
            csd_expiry=REF + timedelta(days=60),
            ingresos_acumulados=100_000,
            deducciones_acumuladas=95_000,
            mes_actual=6,
            meses_declarados=[1, 2, 3],
            anio=2025,
            reference_date=REF,
        )
        assert report.urgentes == sum(
            1 for a in report.alertas if a.nivel == NivelAlerta.URGENTE.value
        )
        assert report.importantes == sum(
            1 for a in report.alertas if a.nivel == NivelAlerta.IMPORTANTE.value
        )
        assert report.preventivas == sum(
            1 for a in report.alertas if a.nivel == NivelAlerta.PREVENTIVA.value
        )
        assert report.informativas == sum(
            1 for a in report.alertas if a.nivel == NivelAlerta.INFORMATIVA.value
        )
        assert report.total_alertas == len(report.alertas)

    def test_full_report_multiple_issues(self):
        """Report with many issues aggregates all alerts."""
        report = generate_fiscal_health_report(
            regimen="612",
            efirma_expiry=REF - timedelta(days=10),
            csd_expiry=REF - timedelta(days=5),
            ingresos_acumulados=100_000,
            deducciones_acumuladas=95_000,
            mes_actual=6,
            meses_declarados=[1, 2, 3],
            anio=2025,
            tiene_empleados=True,
            empleados_imss=0,
            empleados_total=2,
            reference_date=REF,
        )
        assert report.total_alertas >= 4
        assert report.urgentes >= 3
        assert report.score_salud_fiscal < 50


# ══════════════════════════════════════════════════════════════════════
# TEST: Health Score Calculation
# ══════════════════════════════════════════════════════════════════════

class TestHealthScoreCalculation:
    """Test the fiscal health score (0-100)."""

    def test_score_100_no_alerts(self):
        """Clean slate -> score 100."""
        report = generate_fiscal_health_report(
            regimen="612",
            reference_date=REF,
        )
        assert report.score_salud_fiscal == 100

    def test_score_reduced_by_urgente(self):
        """Each URGENTE alert reduces score by 25."""
        report = generate_fiscal_health_report(
            regimen="612",
            efirma_expiry=REF - timedelta(days=10),  # 1 URGENTE
            reference_date=REF,
        )
        assert report.score_salud_fiscal == 75

    def test_score_reduced_by_importante(self):
        """Each IMPORTANTE alert reduces score by 10."""
        report = generate_fiscal_health_report(
            regimen="612",
            csd_expiry=REF + timedelta(days=60),  # 1 IMPORTANTE
            reference_date=REF,
        )
        assert report.score_salud_fiscal == 90

    def test_score_reduced_by_preventiva(self):
        """Each PREVENTIVA alert reduces score by 3."""
        report = generate_fiscal_health_report(
            regimen="625",
            ingresos_acumulados=2_200_000,  # >60% cap -> PREVENTIVA
            mes_actual=10,
            reference_date=REF,
        )
        assert report.score_salud_fiscal == 97

    def test_score_minimum_is_zero(self):
        """Score cannot go below 0."""
        report = generate_fiscal_health_report(
            regimen="612",
            efirma_expiry=REF - timedelta(days=10),
            csd_expiry=REF - timedelta(days=5),
            ingresos_acumulados=100_000,
            deducciones_acumuladas=95_000,
            mes_actual=6,
            meses_declarados=[],
            anio=2025,
            tiene_empleados=True,
            empleados_imss=0,
            empleados_total=3,
            reference_date=REF,
        )
        assert report.score_salud_fiscal >= 0

    def test_score_maximum_is_100(self):
        """Score cannot exceed 100."""
        report = generate_fiscal_health_report(
            regimen="612",
            reference_date=REF,
        )
        assert report.score_salud_fiscal <= 100


# ══════════════════════════════════════════════════════════════════════
# TEST: WhatsApp Formatting (resumen_whatsapp)
# ══════════════════════════════════════════════════════════════════════

class TestResumenWhatsApp:
    """Test WhatsApp-friendly report summary."""

    def test_clean_report_message(self):
        """No alerts -> 'Sin alertas' message."""
        report = generate_fiscal_health_report(
            regimen="612",
            reference_date=REF,
        )
        text = report.resumen_whatsapp()
        assert "SALUD FISCAL" in text
        assert REF.isoformat() in text
        assert "100/100" in text
        assert "Sin alertas" in text

    def test_urgente_shows_red_icon(self):
        """Urgent alerts -> red circle icon in summary."""
        report = generate_fiscal_health_report(
            regimen="612",
            efirma_expiry=REF - timedelta(days=10),
            reference_date=REF,
        )
        text = report.resumen_whatsapp()
        # The overall icon should be red when urgentes > 0
        assert "Score: 75/100" in text

    def test_importante_shows_yellow_icon(self):
        """Important (no urgent) -> yellow icon."""
        report = generate_fiscal_health_report(
            regimen="612",
            csd_expiry=REF + timedelta(days=60),
            reference_date=REF,
        )
        text = report.resumen_whatsapp()
        assert "90/100" in text

    def test_alert_details_in_output(self):
        """Each alert appears with title and message."""
        report = generate_fiscal_health_report(
            regimen="612",
            efirma_expiry=REF - timedelta(days=10),
            reference_date=REF,
        )
        text = report.resumen_whatsapp()
        assert "VENCIDO" in text
        assert "e.firma" in text

    def test_action_required_shown(self):
        """Alerts with accion_requerida show the action."""
        report = generate_fiscal_health_report(
            regimen="612",
            efirma_expiry=REF - timedelta(days=10),
            reference_date=REF,
        )
        text = report.resumen_whatsapp()
        assert "Renovar" in text

    def test_days_remaining_shown(self):
        """Alerts with dias_restantes >= 0 show countdown."""
        report = generate_fiscal_health_report(
            regimen="612",
            efirma_expiry=REF + timedelta(days=20),
            reference_date=REF,
        )
        text = report.resumen_whatsapp()
        assert "20 d" in text  # "20 dias"

    def test_urgente_count_in_summary(self):
        """When there are urgentes, the count is displayed."""
        report = generate_fiscal_health_report(
            regimen="612",
            efirma_expiry=REF - timedelta(days=10),
            csd_expiry=REF - timedelta(days=5),
            reference_date=REF,
        )
        text = report.resumen_whatsapp()
        assert "2 alertas urgentes" in text

    def test_multiple_severity_counts(self):
        """Summary shows counts for each severity level present."""
        report = generate_fiscal_health_report(
            regimen="612",
            efirma_expiry=REF - timedelta(days=5),
            csd_expiry=REF + timedelta(days=60),
            reference_date=REF,
        )
        text = report.resumen_whatsapp()
        assert "alertas urgentes" in text
        assert "alertas importantes" in text


# ══════════════════════════════════════════════════════════════════════
# TEST: Data Classes
# ══════════════════════════════════════════════════════════════════════

class TestDataClasses:
    """Test AlertaFiscal and ReporteAlertas data classes."""

    def test_alerta_fiscal_defaults(self):
        """AlertaFiscal has sensible defaults."""
        alert = AlertaFiscal(
            titulo="Test",
            mensaje="Test message",
            nivel=NivelAlerta.INFORMATIVA.value,
            categoria=CategoriaAlerta.CFDI.value,
        )
        assert alert.accion_requerida == ""
        assert alert.fecha_limite == ""
        assert alert.dias_restantes == -1
        assert alert.fundamento == ""
        assert alert.consecuencia == ""
        assert alert.url_portal == ""

    def test_reporte_alertas_defaults(self):
        """ReporteAlertas has sensible defaults."""
        report = ReporteAlertas(
            fecha_reporte="2026-02-15",
            regimen="612",
        )
        assert report.total_alertas == 0
        assert report.urgentes == 0
        assert report.importantes == 0
        assert report.preventivas == 0
        assert report.informativas == 0
        assert report.alertas == []
        assert report.score_salud_fiscal == 100


# ══════════════════════════════════════════════════════════════════════
# TEST: Module Exports from src.tools
# ══════════════════════════════════════════════════════════════════════

class TestModuleExports:
    """Test that fiscal_alerts is properly exported from src.tools."""

    def test_import_generate_fiscal_health_report(self):
        from src.tools import generate_fiscal_health_report as fn
        assert callable(fn)

    def test_import_check_certificate_expiry(self):
        from src.tools import check_certificate_expiry as fn
        assert callable(fn)

    def test_import_check_resico_income_cap(self):
        from src.tools import check_resico_income_cap as fn
        assert callable(fn)

    def test_import_check_deduction_patterns(self):
        from src.tools import check_deduction_patterns as fn
        assert callable(fn)

    def test_import_check_missing_filings(self):
        from src.tools import check_missing_filings as fn
        assert callable(fn)

    def test_import_check_employee_compliance(self):
        from src.tools import check_employee_compliance as fn
        assert callable(fn)

    def test_import_alerta_fiscal(self):
        from src.tools import AlertaFiscal as cls
        assert cls is not None

    def test_import_reporte_alertas(self):
        from src.tools import ReporteAlertas as cls
        assert cls is not None

    def test_import_nivel_alerta(self):
        from src.tools import NivelAlerta as enum
        assert hasattr(enum, "URGENTE")

    def test_import_categoria_alerta(self):
        from src.tools import CategoriaAlerta as enum
        assert hasattr(enum, "CERTIFICADOS")
