"""Tests for OpenDoc Tax Calendar Engine (Calendario Fiscal).

Comprehensive tests for:
- Obligation catalogs (OBLIGACIONES_MENSUALES, BIMESTRALES, ANUALES)
- Monthly calendar generation (Regimen 612 and RESICO 625)
- Bimonthly obligations (IMSS, INFONAVIT)
- Annual obligations
- Deadline adjustment (weekends)
- Upcoming deadlines function
- Overdue obligations detection
- WhatsApp formatting
- Employee-conditional obligations
- Bimester mapping
- Module exports from src.tools
"""

import pytest
from datetime import date

from src.tools.tax_calendar import (
    # Core functions
    generate_monthly_calendar,
    generate_annual_calendar,
    get_upcoming_deadlines,
    get_overdue_obligations,
    format_monthly_calendar_whatsapp,
    format_upcoming_whatsapp,
    # Internal helpers
    _adjust_deadline,
    _get_bimestre,
    _bimestre_payment_month,
    _mes_nombre,
    # Data classes
    EventoCalendario,
    ObligacionFiscal,
    # Enums
    Frecuencia,
    Prioridad,
    EstadoObligacion,
    # Catalogs
    OBLIGACIONES_MENSUALES,
    OBLIGACIONES_BIMESTRALES,
    OBLIGACIONES_ANUALES,
    BIMESTRES,
)


# ══════════════════════════════════════════════════════════════════════
# TEST: Obligation Catalogs
# ══════════════════════════════════════════════════════════════════════

class TestObligacionesMensuales:
    """Test the monthly obligation catalog structure."""

    def test_catalog_is_not_empty(self):
        """OBLIGACIONES_MENSUALES must contain obligations."""
        assert len(OBLIGACIONES_MENSUALES) > 0

    def test_all_entries_are_obligacion_fiscal(self):
        """Every entry must be an ObligacionFiscal instance."""
        for ob in OBLIGACIONES_MENSUALES:
            assert isinstance(ob, ObligacionFiscal)

    def test_all_have_frecuencia_mensual(self):
        """Monthly obligations must have Mensual frequency."""
        for ob in OBLIGACIONES_MENSUALES:
            assert ob.frecuencia == Frecuencia.MENSUAL.value

    def test_pago_provisional_isr_exists(self):
        """Pago Provisional ISR must be present."""
        nombres = [ob.nombre for ob in OBLIGACIONES_MENSUALES]
        assert "Pago Provisional ISR" in nombres

    def test_declaracion_iva_exists(self):
        """Declaracion Mensual IVA must be present."""
        nombres = [ob.nombre for ob in OBLIGACIONES_MENSUALES]
        assert "Declaración Mensual IVA" in nombres

    def test_diot_exists(self):
        """DIOT must be present."""
        nombres = [ob.nombre for ob in OBLIGACIONES_MENSUALES]
        assert "DIOT" in nombres

    def test_contabilidad_electronica_exists(self):
        """Contabilidad Electronica must be present."""
        nombres = [ob.nombre for ob in OBLIGACIONES_MENSUALES]
        assert "Contabilidad Electrónica" in nombres

    def test_iva_only_for_612(self):
        """IVA declaration should only apply to regimen 612."""
        iva = [ob for ob in OBLIGACIONES_MENSUALES if ob.nombre == "Declaración Mensual IVA"][0]
        assert "612" in iva.regimenes
        assert "625" not in iva.regimenes
        assert iva.aplica_resico is False

    def test_isr_applies_both_regimes(self):
        """Pago Provisional ISR applies to both 612 and 625."""
        isr = [ob for ob in OBLIGACIONES_MENSUALES if ob.nombre == "Pago Provisional ISR"][0]
        assert "612" in isr.regimenes
        assert "625" in isr.regimenes

    def test_diot_not_for_resico(self):
        """DIOT should not apply to RESICO."""
        diot = [ob for ob in OBLIGACIONES_MENSUALES if ob.nombre == "DIOT"][0]
        assert diot.aplica_resico is False
        assert "625" not in diot.regimenes

    def test_all_have_valid_dia_limite(self):
        """All monthly obligations must have dia_limite > 0."""
        for ob in OBLIGACIONES_MENSUALES:
            assert ob.dia_limite > 0
            assert ob.dia_limite <= 31

    def test_all_have_prioridad(self):
        """All monthly obligations must have a valid priority."""
        valid = {Prioridad.CRITICA.value, Prioridad.ALTA.value, Prioridad.MEDIA.value, Prioridad.BAJA.value}
        for ob in OBLIGACIONES_MENSUALES:
            assert ob.prioridad in valid


class TestObligacionesBimestrales:
    """Test the bimonthly obligation catalog."""

    def test_catalog_has_two_entries(self):
        """Should contain IMSS and INFONAVIT."""
        assert len(OBLIGACIONES_BIMESTRALES) == 2

    def test_imss_exists(self):
        nombres = [ob.nombre for ob in OBLIGACIONES_BIMESTRALES]
        assert "Cuotas IMSS" in nombres

    def test_infonavit_exists(self):
        nombres = [ob.nombre for ob in OBLIGACIONES_BIMESTRALES]
        assert "Aportaciones INFONAVIT" in nombres

    def test_bimonthly_frequency(self):
        for ob in OBLIGACIONES_BIMESTRALES:
            assert ob.frecuencia == Frecuencia.BIMESTRAL.value

    def test_both_apply_to_both_regimes(self):
        """IMSS and INFONAVIT apply to 612 and 625."""
        for ob in OBLIGACIONES_BIMESTRALES:
            assert "612" in ob.regimenes
            assert "625" in ob.regimenes

    def test_both_are_critical_priority(self):
        for ob in OBLIGACIONES_BIMESTRALES:
            assert ob.prioridad == Prioridad.CRITICA.value


class TestObligacionesAnuales:
    """Test the annual obligation catalog."""

    def test_catalog_is_not_empty(self):
        assert len(OBLIGACIONES_ANUALES) > 0

    def test_declaracion_anual_exists(self):
        nombres = [ob.nombre for ob in OBLIGACIONES_ANUALES]
        assert "Declaración Anual PF" in nombres

    def test_constancias_retencion_exists(self):
        nombres = [ob.nombre for ob in OBLIGACIONES_ANUALES]
        assert "Constancias de Retención" in nombres

    def test_diot_anual_only_612(self):
        """DIOT Anual should only apply to regimen 612."""
        diot = [ob for ob in OBLIGACIONES_ANUALES if ob.nombre == "DIOT Anual (Resumen)"][0]
        assert "612" in diot.regimenes
        assert diot.aplica_resico is False

    def test_efirma_is_eventual(self):
        """e.firma renewal is an eventual obligation."""
        efirma = [ob for ob in OBLIGACIONES_ANUALES if ob.nombre == "Actualización de e.firma"][0]
        assert efirma.frecuencia == Frecuencia.EVENTUAL.value

    def test_csd_is_eventual(self):
        """CSD renewal is an eventual obligation."""
        csd = [ob for ob in OBLIGACIONES_ANUALES if ob.nombre == "Renovación CSD"][0]
        assert csd.frecuencia == Frecuencia.EVENTUAL.value


# ══════════════════════════════════════════════════════════════════════
# TEST: Bimester Mapping
# ══════════════════════════════════════════════════════════════════════

class TestBimestreMapping:
    """Test bimester number and payment month calculations."""

    def test_bimestres_dict_has_six_entries(self):
        assert len(BIMESTRES) == 6

    def test_bimestre_1_is_jan_feb(self):
        start, end, name = BIMESTRES[1]
        assert start == 1
        assert end == 2
        assert "Enero" in name and "Febrero" in name

    def test_bimestre_6_is_nov_dec(self):
        start, end, name = BIMESTRES[6]
        assert start == 11
        assert end == 12
        assert "Noviembre" in name and "Diciembre" in name

    def test_get_bimestre_january(self):
        assert _get_bimestre(1) == 1

    def test_get_bimestre_february(self):
        assert _get_bimestre(2) == 1

    def test_get_bimestre_march(self):
        assert _get_bimestre(3) == 2

    def test_get_bimestre_december(self):
        assert _get_bimestre(12) == 6

    def test_get_bimestre_all_months(self):
        """All months 1-12 should map to bimesters 1-6."""
        expected = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3,
                    7: 4, 8: 4, 9: 5, 10: 5, 11: 6, 12: 6}
        for month, bim in expected.items():
            assert _get_bimestre(month) == bim, f"Month {month} should be bimester {bim}"

    def test_bimestre_payment_month_1(self):
        """Bimester 1 (Jan-Feb) payment due in March."""
        assert _bimestre_payment_month(1) == 3

    def test_bimestre_payment_month_5(self):
        """Bimester 5 (Sep-Oct) payment due in November."""
        assert _bimestre_payment_month(5) == 11

    def test_bimestre_payment_month_6(self):
        """Bimester 6 (Nov-Dec) payment wraps to January."""
        assert _bimestre_payment_month(6) == 1


# ══════════════════════════════════════════════════════════════════════
# TEST: Deadline Adjustment
# ══════════════════════════════════════════════════════════════════════

class TestDeadlineAdjustment:
    """Test _adjust_deadline for weekend and month-end handling."""

    def test_weekday_unchanged(self):
        """A Tuesday deadline stays on Tuesday."""
        # Feb 17, 2026 is a Tuesday
        result = _adjust_deadline(2026, 2, 17)
        assert result == date(2026, 2, 17)

    def test_saturday_moves_to_monday(self):
        """Jan 17, 2026 is Saturday -> moves to Monday Jan 19."""
        result = _adjust_deadline(2026, 1, 17)
        assert result == date(2026, 1, 19)
        assert result.weekday() == 0  # Monday

    def test_sunday_moves_to_monday(self):
        """May 17, 2026 is Sunday -> moves to Monday May 18."""
        result = _adjust_deadline(2026, 5, 17)
        assert result == date(2026, 5, 18)
        assert result.weekday() == 0  # Monday

    def test_day_capped_to_month_end(self):
        """Day 31 in February caps to last day of Feb."""
        result = _adjust_deadline(2026, 2, 31)
        # Feb 28, 2026 is Saturday -> moves to Monday Mar 2
        assert result.month in (2, 3)
        assert result.weekday() < 5  # Must be weekday

    def test_day_30_in_february(self):
        """Day 30 in February caps to Feb 28 (non-leap year)."""
        result = _adjust_deadline(2026, 2, 30)
        # Feb 28, 2026 is Saturday -> moves to Monday Mar 2
        assert result == date(2026, 3, 2)

    def test_leap_year_february(self):
        """Day 30 in February 2028 (leap year) caps to Feb 29."""
        result = _adjust_deadline(2028, 2, 30)
        # Feb 29, 2028 is Tuesday
        assert result.month == 2
        assert result.day == 29

    def test_result_is_always_weekday(self):
        """Adjusted deadline must never fall on a weekend."""
        for month in range(1, 13):
            result = _adjust_deadline(2026, month, 17)
            assert result.weekday() < 5, f"Month {month}: deadline fell on weekend"

    def test_sunday_22_moves_to_monday(self):
        """Mar 22, 2026 is Sunday -> moves to Monday Mar 23."""
        result = _adjust_deadline(2026, 3, 22)
        assert result == date(2026, 3, 23)
        assert result.weekday() == 0


# ══════════════════════════════════════════════════════════════════════
# TEST: Mes Nombre Helper
# ══════════════════════════════════════════════════════════════════════

class TestMesNombre:
    """Test the month name helper function."""

    def test_january(self):
        assert _mes_nombre(1) == "Enero"

    def test_december(self):
        assert _mes_nombre(12) == "Diciembre"

    def test_out_of_range_returns_string(self):
        """Out-of-range month returns the number as string."""
        assert _mes_nombre(0) == "0"
        assert _mes_nombre(13) == "13"


# ══════════════════════════════════════════════════════════════════════
# TEST: Monthly Calendar Generation - Regimen 612
# ══════════════════════════════════════════════════════════════════════

class TestMonthlyCalendar612:
    """Test monthly calendar generation for Regimen 612."""

    REF_DATE = date(2026, 2, 15)

    def test_returns_list_of_events(self):
        result = generate_monthly_calendar(1, 2026, "612", True, self.REF_DATE)
        assert isinstance(result, list)
        assert all(isinstance(e, EventoCalendario) for e in result)

    def test_has_isr_obligation(self):
        """ISR pago provisional must appear for 612."""
        result = generate_monthly_calendar(1, 2026, "612", True, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "Pago Provisional ISR" in nombres

    def test_has_iva_obligation(self):
        """IVA declaration must appear for 612."""
        result = generate_monthly_calendar(1, 2026, "612", True, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "Declaración Mensual IVA" in nombres

    def test_has_diot(self):
        """DIOT must appear for 612."""
        result = generate_monthly_calendar(1, 2026, "612", True, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "DIOT" in nombres

    def test_has_contabilidad_electronica(self):
        """Contabilidad Electronica must appear for 612."""
        result = generate_monthly_calendar(1, 2026, "612", True, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "Contabilidad Electrónica" in nombres

    def test_monthly_deadlines_in_following_month(self):
        """Obligations for January 2026 must be due in February 2026."""
        result = generate_monthly_calendar(1, 2026, "612", True, self.REF_DATE)
        for e in result:
            d = date.fromisoformat(e.fecha)
            assert d.month == 2 or (d.month == 3 and d.day <= 2), \
                f"{e.nombre} has unexpected date {e.fecha}"

    def test_december_obligations_due_in_january_next_year(self):
        """December 2025 obligations should be due in January 2026."""
        result = generate_monthly_calendar(12, 2025, "612", True, self.REF_DATE)
        for e in result:
            d = date.fromisoformat(e.fecha)
            assert d.year == 2026
            assert d.month == 1 or (d.month == 1 and d.day <= 19), \
                f"{e.nombre} has unexpected date {e.fecha}"

    def test_sorted_by_date_then_priority(self):
        """Events should be sorted by date, then by priority."""
        result = generate_monthly_calendar(1, 2026, "612", True, self.REF_DATE)
        for i in range(len(result) - 1):
            assert result[i].fecha <= result[i + 1].fecha, \
                f"Out of order: {result[i].nombre} ({result[i].fecha}) > {result[i+1].nombre} ({result[i+1].fecha})"

    def test_periodo_in_descripcion(self):
        """Description should include the period being declared."""
        result = generate_monthly_calendar(1, 2026, "612", True, self.REF_DATE)
        for e in result:
            assert "Enero 2026" in e.descripcion or "Enero-Febrero" in e.descripcion

    def test_dias_restantes_calculated(self):
        """dias_restantes should reflect distance from reference_date."""
        result = generate_monthly_calendar(1, 2026, "612", True, self.REF_DATE)
        isr = [e for e in result if e.nombre == "Pago Provisional ISR"][0]
        deadline = date.fromisoformat(isr.fecha)
        expected_days = (deadline - self.REF_DATE).days
        assert isr.dias_restantes == expected_days

    def test_regimen_field_set(self):
        """Regimen field should be set on all events."""
        result = generate_monthly_calendar(1, 2026, "612", True, self.REF_DATE)
        for e in result:
            assert e.regimen == "612"


# ══════════════════════════════════════════════════════════════════════
# TEST: Monthly Calendar Generation - RESICO 625
# ══════════════════════════════════════════════════════════════════════

class TestMonthlyCalendarRESICO:
    """Test monthly calendar generation for RESICO (Regimen 625)."""

    REF_DATE = date(2026, 2, 15)

    def test_has_isr_but_not_iva(self):
        """RESICO has ISR but NOT IVA."""
        result = generate_monthly_calendar(1, 2026, "625", True, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "Pago Provisional ISR" in nombres
        assert "Declaración Mensual IVA" not in nombres

    def test_no_diot(self):
        """RESICO should not have DIOT."""
        result = generate_monthly_calendar(1, 2026, "625", True, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "DIOT" not in nombres

    def test_no_contabilidad_electronica(self):
        """RESICO should not have Contabilidad Electronica."""
        result = generate_monthly_calendar(1, 2026, "625", True, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "Contabilidad Electrónica" not in nombres

    def test_fewer_obligations_than_612(self):
        """RESICO should have fewer monthly obligations than 612."""
        r612 = generate_monthly_calendar(1, 2026, "612", True, self.REF_DATE)
        r625 = generate_monthly_calendar(1, 2026, "625", True, self.REF_DATE)
        assert len(r625) < len(r612)


# ══════════════════════════════════════════════════════════════════════
# TEST: Employee-Conditional Obligations
# ══════════════════════════════════════════════════════════════════════

class TestEmployeeConditionalObligations:
    """Test that employee-specific obligations are conditional."""

    REF_DATE = date(2026, 2, 15)

    def test_with_employees_has_isn(self):
        """ISN Estatal (Nomina) appears when tiene_empleados=True."""
        result = generate_monthly_calendar(1, 2026, "612", True, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "ISN Estatal (Nómina)" in nombres

    def test_without_employees_no_isn(self):
        """ISN Estatal (Nomina) is omitted when tiene_empleados=False."""
        result = generate_monthly_calendar(1, 2026, "612", False, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "ISN Estatal (Nómina)" not in nombres

    def test_with_employees_has_retencion_isr(self):
        """Retencion ISR Empleados appears when tiene_empleados=True."""
        result = generate_monthly_calendar(1, 2026, "612", True, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "Retención ISR Empleados" in nombres

    def test_without_employees_no_retencion_isr(self):
        """Retencion ISR Empleados is omitted when tiene_empleados=False."""
        result = generate_monthly_calendar(1, 2026, "612", False, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "Retención ISR Empleados" not in nombres

    def test_no_employees_fewer_obligations(self):
        """Without employees, there should be fewer obligations."""
        with_emp = generate_monthly_calendar(1, 2026, "612", True, self.REF_DATE)
        without_emp = generate_monthly_calendar(1, 2026, "612", False, self.REF_DATE)
        assert len(without_emp) < len(with_emp)


# ══════════════════════════════════════════════════════════════════════
# TEST: Bimonthly Obligations in Monthly Calendar
# ══════════════════════════════════════════════════════════════════════

class TestBimonthlyObligationsInCalendar:
    """Test that IMSS/INFONAVIT appear only in bimester-end months."""

    REF_DATE = date(2026, 2, 15)

    def test_bimester_end_month_includes_imss(self):
        """February (end of bimester 1) should include IMSS."""
        result = generate_monthly_calendar(2, 2026, "612", True, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "Cuotas IMSS" in nombres

    def test_bimester_end_month_includes_infonavit(self):
        """February (end of bimester 1) should include INFONAVIT."""
        result = generate_monthly_calendar(2, 2026, "612", True, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "Aportaciones INFONAVIT" in nombres

    def test_bimester_start_month_excludes_imss(self):
        """January (start of bimester 1) should NOT include IMSS."""
        result = generate_monthly_calendar(1, 2026, "612", True, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "Cuotas IMSS" not in nombres

    def test_bimester_start_month_excludes_infonavit(self):
        """January (start of bimester 1) should NOT include INFONAVIT."""
        result = generate_monthly_calendar(1, 2026, "612", True, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "Aportaciones INFONAVIT" not in nombres

    def test_no_employees_excludes_bimonthly(self):
        """Without employees, bimonthly IMSS/INFONAVIT should not appear."""
        result = generate_monthly_calendar(2, 2026, "612", False, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "Cuotas IMSS" not in nombres
        assert "Aportaciones INFONAVIT" not in nombres

    def test_all_even_months_include_bimonthly(self):
        """All bimester-end months (2,4,6,8,10,12) should include IMSS."""
        for month in [2, 4, 6, 8, 10, 12]:
            result = generate_monthly_calendar(month, 2026, "612", True, self.REF_DATE)
            nombres = [e.nombre for e in result]
            assert "Cuotas IMSS" in nombres, f"Month {month} missing IMSS"

    def test_all_odd_months_exclude_bimonthly(self):
        """All bimester-start months (1,3,5,7,9,11) should exclude IMSS."""
        for month in [1, 3, 5, 7, 9, 11]:
            result = generate_monthly_calendar(month, 2026, "612", True, self.REF_DATE)
            nombres = [e.nombre for e in result]
            assert "Cuotas IMSS" not in nombres, f"Month {month} should not have IMSS"

    def test_bimonthly_descripcion_includes_bimester_name(self):
        """IMSS description should include the bimester name."""
        result = generate_monthly_calendar(2, 2026, "612", True, self.REF_DATE)
        imss = [e for e in result if e.nombre == "Cuotas IMSS"][0]
        assert "Enero-Febrero" in imss.descripcion

    def test_december_bimonthly_due_january_next_year(self):
        """December bimonthly (bimester 6) should be due in January next year."""
        result = generate_monthly_calendar(12, 2025, "612", True, self.REF_DATE)
        imss = [e for e in result if e.nombre == "Cuotas IMSS"]
        assert len(imss) == 1
        d = date.fromisoformat(imss[0].fecha)
        assert d.year == 2026
        assert d.month == 1


# ══════════════════════════════════════════════════════════════════════
# TEST: Estado (Pending vs Overdue)
# ══════════════════════════════════════════════════════════════════════

class TestEstadoObligacion:
    """Test that obligation status is computed correctly."""

    def test_future_deadline_is_pendiente(self):
        """Deadline far in the future should be Pendiente."""
        ref = date(2026, 2, 1)
        result = generate_monthly_calendar(1, 2026, "612", True, ref)
        isr = [e for e in result if e.nombre == "Pago Provisional ISR"][0]
        assert isr.estado == EstadoObligacion.PENDIENTE.value
        assert isr.dias_restantes > 0

    def test_past_deadline_is_vencida(self):
        """Deadline in the past should be Vencida."""
        ref = date(2026, 3, 20)
        result = generate_monthly_calendar(1, 2026, "612", True, ref)
        isr = [e for e in result if e.nombre == "Pago Provisional ISR"][0]
        assert isr.estado == EstadoObligacion.VENCIDA.value
        assert isr.dias_restantes < 0


# ══════════════════════════════════════════════════════════════════════
# TEST: Annual Calendar
# ══════════════════════════════════════════════════════════════════════

class TestAnnualCalendar:
    """Test full annual calendar generation."""

    REF_DATE = date(2026, 2, 15)

    def test_returns_events_for_full_year(self):
        """Annual calendar should return events spanning the whole year."""
        result = generate_annual_calendar(2026, "612", True, self.REF_DATE)
        assert len(result) > 0
        months_covered = set()
        for e in result:
            d = date.fromisoformat(e.fecha)
            months_covered.add(d.month)
        # Should cover many months (payments fall in month after period)
        assert len(months_covered) >= 6

    def test_includes_annual_declaration(self):
        """Declaracion Anual PF should appear."""
        result = generate_annual_calendar(2026, "612", True, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "Declaración Anual PF" in nombres

    def test_annual_declaration_in_april_next_year(self):
        """Declaracion Anual for 2026 should be due April 30, 2027."""
        result = generate_annual_calendar(2026, "612", True, self.REF_DATE)
        anual = [e for e in result if e.nombre == "Declaración Anual PF"][0]
        d = date.fromisoformat(anual.fecha)
        assert d.year == 2027
        assert d.month == 4
        assert d.day == 30  # April 30, 2027 is a Friday

    def test_constancias_retencion_feb_next_year(self):
        """Constancias de Retencion for 2026 should be due Feb 15, 2027."""
        result = generate_annual_calendar(2026, "612", True, self.REF_DATE)
        const = [e for e in result if e.nombre == "Constancias de Retención"][0]
        d = date.fromisoformat(const.fecha)
        assert d.year == 2027
        assert d.month == 2

    def test_no_constancias_without_employees(self):
        """Constancias de Retencion should be omitted without employees."""
        result = generate_annual_calendar(2026, "612", False, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "Constancias de Retención" not in nombres

    def test_no_diot_anual_for_resico(self):
        """DIOT Anual should not appear for RESICO."""
        result = generate_annual_calendar(2026, "625", True, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "DIOT Anual (Resumen)" not in nombres

    def test_annual_events_sorted_chronologically(self):
        """Annual events should be sorted by date."""
        result = generate_annual_calendar(2026, "612", True, self.REF_DATE)
        for i in range(len(result) - 1):
            assert result[i].fecha <= result[i + 1].fecha

    def test_annual_no_duplicates(self):
        """No duplicate (fecha, nombre) pairs should exist."""
        result = generate_annual_calendar(2026, "612", True, self.REF_DATE)
        seen = set()
        for e in result:
            key = (e.fecha, e.nombre)
            assert key not in seen, f"Duplicate found: {e.nombre} on {e.fecha}"
            seen.add(key)

    def test_annual_excludes_eventual_obligations(self):
        """Eventual obligations (e.firma, CSD) should not appear in annual calendar."""
        result = generate_annual_calendar(2026, "612", True, self.REF_DATE)
        nombres = [e.nombre for e in result]
        assert "Actualización de e.firma" not in nombres
        assert "Renovación CSD" not in nombres


# ══════════════════════════════════════════════════════════════════════
# TEST: Upcoming Deadlines
# ══════════════════════════════════════════════════════════════════════

class TestUpcomingDeadlines:
    """Test the get_upcoming_deadlines function."""

    REF_DATE = date(2026, 2, 15)

    def test_returns_list(self):
        result = get_upcoming_deadlines("612", True, 30, self.REF_DATE)
        assert isinstance(result, list)

    def test_all_within_window(self):
        """All returned events should be within the look-ahead window."""
        result = get_upcoming_deadlines("612", True, 30, self.REF_DATE)
        for e in result:
            assert 0 <= e.dias_restantes <= 30

    def test_no_overdue_events(self):
        """Upcoming deadlines should not include overdue events."""
        result = get_upcoming_deadlines("612", True, 30, self.REF_DATE)
        for e in result:
            assert e.dias_restantes >= 0

    def test_sorted_by_urgency(self):
        """Results should be sorted by dias_restantes ascending."""
        result = get_upcoming_deadlines("612", True, 30, self.REF_DATE)
        for i in range(len(result) - 1):
            assert result[i].dias_restantes <= result[i + 1].dias_restantes

    def test_narrow_window_returns_fewer_results(self):
        """A smaller look-ahead window should return fewer or equal events."""
        wide = get_upcoming_deadlines("612", True, 60, self.REF_DATE)
        narrow = get_upcoming_deadlines("612", True, 5, self.REF_DATE)
        assert len(narrow) <= len(wide)

    def test_zero_day_window_may_return_empty(self):
        """Zero-day window only includes deadlines exactly today."""
        result = get_upcoming_deadlines("612", True, 0, self.REF_DATE)
        for e in result:
            assert e.dias_restantes == 0


# ══════════════════════════════════════════════════════════════════════
# TEST: Overdue Obligations
# ══════════════════════════════════════════════════════════════════════

class TestOverdueObligations:
    """Test the get_overdue_obligations function."""

    def test_no_overdue_when_early_in_month(self):
        """Early in the month with recent deadlines met should have few overdue."""
        ref = date(2026, 2, 1)
        result = get_overdue_obligations("612", True, ref)
        # Some might be overdue from prior months depending on window
        assert isinstance(result, list)

    def test_overdue_detected_after_deadline(self):
        """After the 17th, prior month obligations should be overdue."""
        # By March 20, January obligations due Feb 17 should be overdue
        ref = date(2026, 3, 20)
        result = get_overdue_obligations("612", True, ref)
        assert len(result) > 0
        for e in result:
            assert e.dias_restantes < 0
            assert e.estado == EstadoObligacion.VENCIDA.value

    def test_overdue_sorted_most_overdue_first(self):
        """Overdue events should be sorted with the most overdue first."""
        ref = date(2026, 3, 20)
        result = get_overdue_obligations("612", True, ref)
        for i in range(len(result) - 1):
            assert result[i].dias_restantes <= result[i + 1].dias_restantes


# ══════════════════════════════════════════════════════════════════════
# TEST: WhatsApp Formatting - Monthly Calendar
# ══════════════════════════════════════════════════════════════════════

class TestWhatsAppMonthlyFormatting:
    """Test format_monthly_calendar_whatsapp output."""

    REF_DATE = date(2026, 2, 15)

    def test_returns_string(self):
        result = format_monthly_calendar_whatsapp(1, 2026, "612", True, self.REF_DATE)
        assert isinstance(result, str)

    def test_contains_header(self):
        result = format_monthly_calendar_whatsapp(1, 2026, "612", True, self.REF_DATE)
        assert "CALENDARIO FISCAL" in result
        assert "ENERO" in result
        assert "2026" in result

    def test_contains_regimen(self):
        result = format_monthly_calendar_whatsapp(1, 2026, "612", True, self.REF_DATE)
        assert "612" in result

    def test_contains_obligation_names(self):
        result = format_monthly_calendar_whatsapp(1, 2026, "612", True, self.REF_DATE)
        assert "Pago Provisional ISR" in result

    def test_contains_fecha_limite(self):
        result = format_monthly_calendar_whatsapp(1, 2026, "612", True, self.REF_DATE)
        assert "Fecha límite" in result

    def test_contains_total_summary(self):
        result = format_monthly_calendar_whatsapp(1, 2026, "612", True, self.REF_DATE)
        assert "Total:" in result
        assert "obligaciones" in result

    def test_overdue_message_shown(self):
        """When deadlines are past, VENCIDA message should appear."""
        ref = date(2026, 3, 20)
        result = format_monthly_calendar_whatsapp(1, 2026, "612", True, ref)
        assert "VENCIDA" in result

    def test_vence_hoy_message(self):
        """When deadline is today, VENCE HOY message should appear."""
        # Feb 17, 2026 is a Tuesday (ISR deadline for Jan)
        ref = date(2026, 2, 17)
        result = format_monthly_calendar_whatsapp(1, 2026, "612", True, ref)
        assert "VENCE HOY" in result

    def test_urgency_count_shown_when_overdue(self):
        """When there are overdue items, the overdue count should appear."""
        ref = date(2026, 3, 20)
        result = format_monthly_calendar_whatsapp(1, 2026, "612", True, ref)
        assert "VENCIDAS" in result


# ══════════════════════════════════════════════════════════════════════
# TEST: WhatsApp Formatting - Upcoming Deadlines
# ══════════════════════════════════════════════════════════════════════

class TestWhatsAppUpcomingFormatting:
    """Test format_upcoming_whatsapp output."""

    REF_DATE = date(2026, 2, 15)

    def test_returns_string(self):
        result = format_upcoming_whatsapp("612", True, 30, self.REF_DATE)
        assert isinstance(result, str)

    def test_contains_header(self):
        result = format_upcoming_whatsapp("612", True, 30, self.REF_DATE)
        assert "VENCIMIENTOS" in result

    def test_contains_reference_date(self):
        result = format_upcoming_whatsapp("612", True, 30, self.REF_DATE)
        assert "2026-02-15" in result

    def test_no_upcoming_shows_all_in_order(self):
        """When no deadlines in window, shows empty message."""
        # Very narrow window where nothing is due
        ref = date(2026, 2, 20)
        result = format_upcoming_whatsapp("612", True, 0, ref)
        # Might be empty or have content depending on exact dates
        assert isinstance(result, str)

    def test_contains_dias_remaining(self):
        """Output should show number of days remaining for each event."""
        result = format_upcoming_whatsapp("612", True, 30, self.REF_DATE)
        assert "días" in result


# ══════════════════════════════════════════════════════════════════════
# TEST: Enums
# ══════════════════════════════════════════════════════════════════════

class TestEnums:
    """Test that all fiscal enums have expected values."""

    def test_frecuencia_values(self):
        assert Frecuencia.MENSUAL.value == "Mensual"
        assert Frecuencia.BIMESTRAL.value == "Bimestral"
        assert Frecuencia.TRIMESTRAL.value == "Trimestral"
        assert Frecuencia.ANUAL.value == "Anual"
        assert Frecuencia.EVENTUAL.value == "Eventual"

    def test_prioridad_values(self):
        assert Prioridad.CRITICA.value == "Crítica"
        assert Prioridad.ALTA.value == "Alta"
        assert Prioridad.MEDIA.value == "Media"
        assert Prioridad.BAJA.value == "Baja"

    def test_estado_values(self):
        assert EstadoObligacion.PENDIENTE.value == "Pendiente"
        assert EstadoObligacion.VENCIDA.value == "Vencida"
        assert EstadoObligacion.COMPLETADA.value == "Completada"
        assert EstadoObligacion.EN_PROGRESO.value == "En Progreso"
        assert EstadoObligacion.NO_APLICA.value == "No Aplica"


# ══════════════════════════════════════════════════════════════════════
# TEST: DataClass Defaults
# ══════════════════════════════════════════════════════════════════════

class TestDataClassDefaults:
    """Test that dataclass default fields work correctly."""

    def test_obligacion_fiscal_defaults(self):
        ob = ObligacionFiscal(
            nombre="Test",
            descripcion="Test",
            frecuencia="Mensual",
            dia_limite=17,
            regimenes=["612"],
            prioridad="Crítica",
        )
        assert ob.portal_url == ""
        assert ob.fundamento == ""
        assert ob.multa_omision == ""
        assert ob.datos_necesarios == []
        assert ob.notas == []
        assert ob.aplica_resico is True

    def test_evento_calendario_defaults(self):
        ev = EventoCalendario(
            fecha="2026-02-17",
            nombre="Test",
            descripcion="Test event",
            prioridad="Crítica",
        )
        assert ev.estado == EstadoObligacion.PENDIENTE.value
        assert ev.portal_url == ""
        assert ev.regimen == ""
        assert ev.dias_restantes == 0
        assert ev.multa_omision == ""
        assert ev.datos_necesarios == []
        assert ev.notas == []


# ══════════════════════════════════════════════════════════════════════
# TEST: Module Exports from src.tools
# ══════════════════════════════════════════════════════════════════════

class TestModuleExports:
    """Test that tax_calendar symbols are accessible from src.tools."""

    def test_generate_monthly_calendar_exported(self):
        from src.tools import generate_monthly_calendar as fn
        assert callable(fn)

    def test_generate_annual_calendar_exported(self):
        from src.tools import generate_annual_calendar as fn
        assert callable(fn)

    def test_get_upcoming_deadlines_exported(self):
        from src.tools import get_upcoming_deadlines as fn
        assert callable(fn)

    def test_get_overdue_obligations_exported(self):
        from src.tools import get_overdue_obligations as fn
        assert callable(fn)

    def test_format_monthly_calendar_whatsapp_exported(self):
        from src.tools import format_monthly_calendar_whatsapp as fn
        assert callable(fn)

    def test_format_upcoming_whatsapp_exported(self):
        from src.tools import format_upcoming_whatsapp as fn
        assert callable(fn)

    def test_evento_calendario_exported(self):
        from src.tools import EventoCalendario as cls
        assert cls is not None

    def test_obligacion_fiscal_exported(self):
        from src.tools import ObligacionFiscal as cls
        assert cls is not None

    def test_obligaciones_mensuales_exported(self):
        from src.tools import OBLIGACIONES_MENSUALES as catalog
        assert isinstance(catalog, list)

    def test_obligaciones_bimestrales_exported(self):
        from src.tools import OBLIGACIONES_BIMESTRALES as catalog
        assert isinstance(catalog, list)

    def test_obligaciones_anuales_exported(self):
        from src.tools import OBLIGACIONES_ANUALES as catalog
        assert isinstance(catalog, list)
