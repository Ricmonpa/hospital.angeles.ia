"""Tests for OpenDoc Depreciation Schedule Generator.

Validates:
- ActivoFijo dataclass (MOI calculations, caps)
- LineaDepreciacion fields
- TablaDepreciacion (schedule generation, WhatsApp summary)
- generate_depreciation_schedule() — multi-year tables
- generate_asset_registry() — combined registry
- get_monthly_depreciation() — monthly breakdown
- Edge cases (zero rate, fully depreciated, prior months, sold assets)
"""

import pytest
import math

from src.tools.depreciation_schedule import (
    ActivoFijo,
    LineaDepreciacion,
    TablaDepreciacion,
    ResumenRegistro,
    generate_depreciation_schedule,
    generate_asset_registry,
    get_monthly_depreciation,
)
from src.tools.deduction_optimizer import TASAS_DEPRECIACION, TasaDepreciacion


# ─── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def equipo_medico():
    """Ultrasound machine acquired mid-year."""
    return ActivoFijo(
        nombre="Ultrasonido GE Vivid",
        tipo_activo="equipo_medico",
        moi=250_000.0,
        fecha_adquisicion="2025-06-15",
    )


@pytest.fixture
def laptop():
    """MacBook Pro, 30% depreciation rate."""
    return ActivoFijo(
        nombre="MacBook Pro M3",
        tipo_activo="equipo_computo",
        moi=45_000.0,
        fecha_adquisicion="2026-01-10",
    )


@pytest.fixture
def vehiculo():
    """Car with MOI above the $175K cap."""
    return ActivoFijo(
        nombre="Honda CR-V 2025",
        tipo_activo="vehiculo",
        moi=480_000.0,
        fecha_adquisicion="2025-03-01",
    )


@pytest.fixture
def vehiculo_bajo_tope():
    """Car with MOI below the $175K cap."""
    return ActivoFijo(
        nombre="Nissan March 2024",
        tipo_activo="vehiculo",
        moi=150_000.0,
        fecha_adquisicion="2025-01-15",
    )


@pytest.fixture
def mobiliario():
    """Office furniture."""
    return ActivoFijo(
        nombre="Escritorio ejecutivo",
        tipo_activo="mobiliario",
        moi=12_000.0,
        fecha_adquisicion="2024-11-20",
    )


@pytest.fixture
def activo_con_iva():
    """Medical equipment with IVA (non-creditable for doctors)."""
    return ActivoFijo(
        nombre="Rayos X portátil",
        tipo_activo="equipo_medico",
        moi=180_000.0,
        fecha_adquisicion="2025-09-01",
        iva_pagado=28_800.0,
    )


@pytest.fixture
def activo_vendido():
    """Asset that has been sold."""
    return ActivoFijo(
        nombre="Equipo viejo",
        tipo_activo="equipo_computo",
        moi=20_000.0,
        fecha_adquisicion="2020-01-01",
        estado="vendido",
        fecha_baja="2025-06-01",
        valor_venta=3_000.0,
    )


@pytest.fixture
def activo_con_uso_previo():
    """Equipment with 24 months of prior depreciation."""
    return ActivoFijo(
        nombre="Autoclave",
        tipo_activo="equipo_medico",
        moi=80_000.0,
        fecha_adquisicion="2023-06-01",
        meses_uso_previo=24,
    )


# ─── Test: ActivoFijo Dataclass ──────────────────────────────────────

class TestActivoFijo:
    def test_basic_fields(self, equipo_medico):
        assert equipo_medico.nombre == "Ultrasonido GE Vivid"
        assert equipo_medico.tipo_activo == "equipo_medico"
        assert equipo_medico.moi == 250_000.0

    def test_moi_total_without_iva(self, equipo_medico):
        assert equipo_medico.moi_total == 250_000.0

    def test_moi_total_with_iva(self, activo_con_iva):
        assert activo_con_iva.moi_total == 208_800.0  # 180K + 28.8K

    def test_moi_deducible_no_cap(self, equipo_medico):
        assert equipo_medico.moi_deducible == 250_000.0

    def test_moi_deducible_with_cap(self, vehiculo):
        """Vehicle MOI $480K but capped at $175K."""
        assert vehiculo.moi_deducible == 175_000.0

    def test_moi_deducible_below_cap(self, vehiculo_bajo_tope):
        """Vehicle MOI $150K, below $175K cap."""
        assert vehiculo_bajo_tope.moi_deducible == 150_000.0

    def test_default_estado(self, equipo_medico):
        assert equipo_medico.estado == "activo"

    def test_default_iva(self, equipo_medico):
        assert equipo_medico.iva_pagado == 0.0

    def test_default_meses_uso_previo(self, equipo_medico):
        assert equipo_medico.meses_uso_previo == 0

    def test_vendido_estado(self, activo_vendido):
        assert activo_vendido.estado == "vendido"
        assert activo_vendido.valor_venta == 3_000.0

    def test_moi_deducible_iva_added(self, activo_con_iva):
        """IVA is added to MOI for deducible calculation (non-creditable)."""
        assert activo_con_iva.moi_deducible == 208_800.0


# ─── Test: generate_depreciation_schedule — Basic ────────────────────

class TestGenerateScheduleBasic:
    def test_returns_tabla(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        assert isinstance(tabla, TablaDepreciacion)

    def test_activo_name(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        assert tabla.activo == "Ultrasonido GE Vivid"

    def test_tasa_anual(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        assert tabla.tasa_anual == 10.0

    def test_vida_util(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        assert tabla.vida_util_anos == 10

    def test_fundamento(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        assert "Art. 35" in tabla.fundamento

    def test_lineas_not_empty(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        assert len(tabla.lineas) > 0

    def test_moi_total_in_tabla(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        assert tabla.moi_total == 250_000.0

    def test_moi_deducible_in_tabla(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        assert tabla.moi_deducible == 250_000.0


class TestGenerateScheduleEquipoMedico:
    """10% annual rate, 10-year life, $250K MOI, acquired June 2025."""

    def test_annual_deduction_full_year(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        # First year starts July 2025 (month after acquisition)
        # → 6 months (Jul-Dec) in 2025
        first = tabla.lineas[0]
        assert first.anio == 2025
        assert first.meses_depreciacion == 6
        monthly = 250_000.0 * 0.10 / 12
        assert abs(first.deduccion_anual - monthly * 6) < 1.0

    def test_second_year_full_12_months(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        second = tabla.lineas[1]
        assert second.anio == 2026
        assert second.meses_depreciacion == 12

    def test_full_deduction_equals_moi(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        total = tabla.total_deducido
        assert abs(total - 250_000.0) < 1.0

    def test_last_line_pendiente_zero(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        assert tabla.lineas[-1].pendiente == 0.0

    def test_last_line_is_ultimo_anio(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        assert tabla.lineas[-1].es_ultimo_anio is True

    def test_deduccion_mensual_consistent(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        expected_monthly = 250_000.0 * 0.10 / 12
        for linea in tabla.lineas:
            assert abs(linea.deduccion_mensual - expected_monthly) < 0.01

    def test_porcentaje_depreciado_increases(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        prev_pct = 0
        for linea in tabla.lineas:
            assert linea.porcentaje_depreciado >= prev_pct
            prev_pct = linea.porcentaje_depreciado


class TestGenerateScheduleLaptop:
    """30% annual rate, ~3.3 year life, $45K MOI, acquired Jan 2026."""

    def test_first_year_starts_feb(self, laptop):
        tabla = generate_depreciation_schedule(laptop)
        first = tabla.lineas[0]
        assert first.anio == 2026
        assert first.mes_inicio == 2  # Feb (month after Jan acquisition)
        assert first.meses_depreciacion == 11

    def test_tasa_30(self, laptop):
        tabla = generate_depreciation_schedule(laptop)
        assert tabla.tasa_anual == 30.0

    def test_fully_depreciated_within_5_years(self, laptop):
        tabla = generate_depreciation_schedule(laptop)
        last_year = tabla.lineas[-1].anio
        assert last_year <= 2030

    def test_total_equals_moi(self, laptop):
        tabla = generate_depreciation_schedule(laptop)
        assert abs(tabla.total_deducido - 45_000.0) < 1.0


class TestGenerateScheduleVehicle:
    """25% rate, $175K cap on $480K MOI."""

    def test_excedente_no_deducible(self, vehiculo):
        tabla = generate_depreciation_schedule(vehiculo)
        assert tabla.excedente_no_deducible == 305_000.0  # 480K - 175K

    def test_moi_deducible_capped(self, vehiculo):
        tabla = generate_depreciation_schedule(vehiculo)
        assert tabla.moi_deducible == 175_000.0

    def test_total_never_exceeds_cap(self, vehiculo):
        tabla = generate_depreciation_schedule(vehiculo)
        assert tabla.total_deducido <= 175_000.01

    def test_vehicle_below_cap_no_excedente(self, vehiculo_bajo_tope):
        tabla = generate_depreciation_schedule(vehiculo_bajo_tope)
        assert tabla.excedente_no_deducible == 0.0


class TestGenerateScheduleWithIVA:
    """IVA added to MOI (non-creditable for exempt medical services)."""

    def test_moi_includes_iva(self, activo_con_iva):
        tabla = generate_depreciation_schedule(activo_con_iva)
        assert tabla.moi_total == 208_800.0

    def test_deduction_based_on_total_moi(self, activo_con_iva):
        tabla = generate_depreciation_schedule(activo_con_iva)
        expected_monthly = 208_800.0 * 0.10 / 12
        assert abs(tabla.lineas[0].deduccion_mensual - expected_monthly) < 0.01


class TestGenerateScheduleWithPriorUse:
    """Asset with 24 months already depreciated."""

    def test_accumulated_start(self, activo_con_uso_previo):
        tabla = generate_depreciation_schedule(activo_con_uso_previo)
        monthly = 80_000.0 * 0.10 / 12
        expected_acum = monthly * 24
        first = tabla.lineas[0]
        assert abs(first.acumulado_inicio - expected_acum) < 1.0

    def test_remaining_less_than_full(self, activo_con_uso_previo):
        tabla = generate_depreciation_schedule(activo_con_uso_previo)
        monthly = 80_000.0 * 0.10 / 12
        expected_remaining = 80_000.0 - (monthly * 24)
        first = tabla.lineas[0]
        expected_pendiente_after = expected_remaining - first.deduccion_anual
        assert first.pendiente < 80_000.0

    def test_total_still_equals_moi(self, activo_con_uso_previo):
        """Prior months + schedule should add up to MOI."""
        tabla = generate_depreciation_schedule(activo_con_uso_previo)
        monthly = 80_000.0 * 0.10 / 12
        prior = monthly * 24
        total = prior + sum(l.deduccion_anual for l in tabla.lineas)
        assert abs(total - 80_000.0) < 1.0


# ─── Test: generate_depreciation_schedule — Edge Cases ───────────────

class TestScheduleEdgeCases:
    def test_invalid_tipo_raises_error(self):
        activo = ActivoFijo(
            nombre="Widget",
            tipo_activo="tipo_inventado",
            moi=10_000.0,
            fecha_adquisicion="2026-01-01",
        )
        with pytest.raises(ValueError, match="Tipo de activo desconocido"):
            generate_depreciation_schedule(activo)

    def test_error_lists_valid_types(self):
        activo = ActivoFijo(
            nombre="Widget",
            tipo_activo="fake",
            moi=10_000.0,
            fecha_adquisicion="2026-01-01",
        )
        with pytest.raises(ValueError, match="equipo_medico"):
            generate_depreciation_schedule(activo)

    def test_adecuaciones_arrendado_zero_rate(self):
        activo = ActivoFijo(
            nombre="Pisos consultorio",
            tipo_activo="adecuaciones_arrendado",
            moi=50_000.0,
            fecha_adquisicion="2025-01-01",
        )
        tabla = generate_depreciation_schedule(activo)
        assert tabla.tasa_anual == 0
        assert tabla.lineas == []

    def test_december_acquisition_wraps_year(self):
        """Acquired Dec 2025 → depreciation starts Jan 2026."""
        activo = ActivoFijo(
            nombre="Monitor",
            tipo_activo="equipo_computo",
            moi=15_000.0,
            fecha_adquisicion="2025-12-15",
        )
        tabla = generate_depreciation_schedule(activo)
        assert tabla.lineas[0].anio == 2026
        assert tabla.lineas[0].mes_inicio == 1

    def test_invalid_date_defaults_to_2026(self):
        activo = ActivoFijo(
            nombre="Algo",
            tipo_activo="equipo_computo",
            moi=10_000.0,
            fecha_adquisicion="not-a-date",
        )
        tabla = generate_depreciation_schedule(activo)
        assert tabla.lineas[0].anio == 2026

    def test_anio_hasta_limits_schedule(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico, anio_hasta=2027)
        years = [l.anio for l in tabla.lineas]
        assert all(y <= 2027 for y in years)

    def test_zero_moi_no_crash(self):
        activo = ActivoFijo(
            nombre="Donación",
            tipo_activo="mobiliario",
            moi=0.0,
            fecha_adquisicion="2026-01-01",
        )
        tabla = generate_depreciation_schedule(activo)
        assert tabla.moi_total == 0.0

    def test_fully_prior_depreciated(self):
        """All months already used up before schedule starts."""
        activo = ActivoFijo(
            nombre="Viejo equipo",
            tipo_activo="equipo_computo",
            moi=30_000.0,
            fecha_adquisicion="2020-01-01",
            meses_uso_previo=200,
        )
        tabla = generate_depreciation_schedule(activo)
        assert len(tabla.lineas) == 0


# ─── Test: TablaDepreciacion Properties and Methods ──────────────────

class TestTablaDepreciacion:
    def test_total_deducido(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        assert tabla.total_deducido > 0

    def test_total_deducido_empty_lineas(self):
        tabla = TablaDepreciacion(
            activo="test", tipo_activo="test", descripcion_tipo="test",
            moi_total=0, moi_deducible=0, tasa_anual=0,
            fecha_inicio="2026-01-01", vida_util_anos=0, lineas=[],
        )
        assert tabla.total_deducido == 0.0

    def test_to_dict(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico, anio_hasta=2027)
        d = tabla.to_dict()
        assert isinstance(d, dict)
        assert "activo" in d
        assert "lineas" in d
        assert isinstance(d["lineas"], list)

    def test_whatsapp_contains_activo_name(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico, anio_hasta=2027)
        wsp = tabla.resumen_whatsapp()
        assert "Ultrasonido GE Vivid" in wsp

    def test_whatsapp_contains_divider(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico, anio_hasta=2027)
        wsp = tabla.resumen_whatsapp()
        assert "━━━" in wsp

    def test_whatsapp_contains_years(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico, anio_hasta=2027)
        wsp = tabla.resumen_whatsapp()
        assert "2025" in wsp or "2026" in wsp

    def test_whatsapp_vehicle_shows_tope(self, vehiculo):
        tabla = generate_depreciation_schedule(vehiculo)
        wsp = tabla.resumen_whatsapp()
        assert "excedente" in wsp.lower() or "Tope" in wsp

    def test_whatsapp_total_deducido(self, laptop):
        tabla = generate_depreciation_schedule(laptop)
        wsp = tabla.resumen_whatsapp()
        assert "Total deducido" in wsp


# ─── Test: generate_asset_registry ───────────────────────────────────

class TestAssetRegistry:
    def test_empty_list(self):
        result = generate_asset_registry([])
        assert isinstance(result, ResumenRegistro)
        assert result.total_activos == 0
        assert result.total_moi == 0.0

    def test_single_asset(self, equipo_medico):
        result = generate_asset_registry([equipo_medico], anio=2026)
        assert result.total_activos == 1
        assert result.total_moi == 250_000.0

    def test_multiple_assets(self, equipo_medico, laptop, mobiliario):
        result = generate_asset_registry([equipo_medico, laptop, mobiliario], anio=2026)
        assert result.total_activos == 3
        expected_moi = 250_000.0 + 45_000.0 + 12_000.0
        assert abs(result.total_moi - expected_moi) < 0.01

    def test_excludes_vendido(self, equipo_medico, activo_vendido):
        result = generate_asset_registry([equipo_medico, activo_vendido], anio=2026)
        assert result.total_activos == 1

    def test_tablas_per_active_asset(self, equipo_medico, laptop):
        result = generate_asset_registry([equipo_medico, laptop], anio=2026)
        assert len(result.tablas) == 2

    def test_deduccion_anual_total(self, equipo_medico, laptop):
        result = generate_asset_registry([equipo_medico, laptop], anio=2026)
        assert result.deduccion_anual_total > 0

    def test_deduccion_mensual_total(self, equipo_medico, laptop):
        result = generate_asset_registry([equipo_medico, laptop], anio=2026)
        expected_monthly = result.deduccion_anual_total / 12
        assert abs(result.deduccion_mensual_total - expected_monthly) < 0.01

    def test_anio_calculo(self, equipo_medico):
        result = generate_asset_registry([equipo_medico], anio=2027)
        assert result.anio_calculo == 2027

    def test_alert_vehicle_cap_exceeded(self, vehiculo):
        result = generate_asset_registry([vehiculo], anio=2026)
        excedente_alert = [a for a in result.alertas if "excede tope" in a]
        assert len(excedente_alert) >= 1

    def test_alert_fully_depreciated(self):
        """Asset already fully depreciated gets an alert."""
        activo = ActivoFijo(
            nombre="Impresora vieja",
            tipo_activo="equipo_computo",
            moi=9_000.0,
            fecha_adquisicion="2020-01-01",
            meses_uso_previo=60,
        )
        result = generate_asset_registry([activo], anio=2026)
        depr_alert = [a for a in result.alertas if "depreciado" in a.lower()]
        assert len(depr_alert) >= 1

    def test_invalid_tipo_goes_to_alertas(self):
        activo = ActivoFijo(
            nombre="Misterio",
            tipo_activo="tipo_malo",
            moi=5_000.0,
            fecha_adquisicion="2026-01-01",
        )
        result = generate_asset_registry([activo], anio=2026)
        assert result.total_activos == 0
        assert len(result.alertas) >= 1


class TestResumenRegistroWhatsApp:
    def test_whatsapp_divider(self, equipo_medico, laptop):
        result = generate_asset_registry([equipo_medico, laptop], anio=2026)
        wsp = result.resumen_whatsapp()
        assert "━━━" in wsp

    def test_whatsapp_includes_year(self, equipo_medico):
        result = generate_asset_registry([equipo_medico], anio=2026)
        wsp = result.resumen_whatsapp()
        assert "2026" in wsp

    def test_whatsapp_includes_count(self, equipo_medico, laptop):
        result = generate_asset_registry([equipo_medico, laptop], anio=2026)
        wsp = result.resumen_whatsapp()
        assert "2 activo" in wsp

    def test_whatsapp_includes_moi(self, equipo_medico):
        result = generate_asset_registry([equipo_medico], anio=2026)
        wsp = result.resumen_whatsapp()
        assert "$" in wsp


# ─── Test: get_monthly_depreciation ──────────────────────────────────

class TestMonthlyDepreciation:
    def test_returns_dict(self, equipo_medico):
        result = get_monthly_depreciation([equipo_medico], mes=6, anio=2026)
        assert isinstance(result, dict)
        assert "total" in result
        assert "desglose" in result

    def test_month_and_year(self, equipo_medico):
        result = get_monthly_depreciation([equipo_medico], mes=3, anio=2026)
        assert result["mes"] == 3
        assert result["anio"] == 2026

    def test_total_positive_for_active(self, equipo_medico):
        """Equipo medico acquired June 2025, should be active in 2026."""
        result = get_monthly_depreciation([equipo_medico], mes=6, anio=2026)
        assert result["total"] > 0

    def test_desglose_has_asset_name(self, equipo_medico):
        result = get_monthly_depreciation([equipo_medico], mes=6, anio=2026)
        if result["desglose"]:
            assert result["desglose"][0]["activo"] == "Ultrasonido GE Vivid"

    def test_excludes_vendido(self, equipo_medico, activo_vendido):
        result = get_monthly_depreciation([equipo_medico, activo_vendido], mes=6, anio=2026)
        nombres = [d["activo"] for d in result["desglose"]]
        assert "Equipo viejo" not in nombres

    def test_multiple_assets_sum(self, equipo_medico, laptop):
        result = get_monthly_depreciation([equipo_medico, laptop], mes=6, anio=2026)
        total = sum(d["monto"] for d in result["desglose"])
        assert abs(result["total"] - total) < 0.01

    def test_zero_for_month_before_acquisition(self):
        """Laptop acquired Jan 2026, depreciation starts Feb 2026."""
        activo = ActivoFijo(
            nombre="Laptop nueva",
            tipo_activo="equipo_computo",
            moi=30_000.0,
            fecha_adquisicion="2026-01-15",
        )
        result = get_monthly_depreciation([activo], mes=1, anio=2026)
        assert result["total"] == 0.0

    def test_empty_list(self):
        result = get_monthly_depreciation([], mes=6, anio=2026)
        assert result["total"] == 0.0
        assert result["desglose"] == []


# ─── Test: LineaDepreciacion Fields ──────────────────────────────────

class TestLineaDepreciacion:
    def test_acumulado_grows(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        for i in range(1, len(tabla.lineas)):
            prev = tabla.lineas[i - 1]
            curr = tabla.lineas[i]
            assert curr.acumulado_fin >= prev.acumulado_fin

    def test_pendiente_decreases(self, equipo_medico):
        tabla = generate_depreciation_schedule(equipo_medico)
        for i in range(1, len(tabla.lineas)):
            prev = tabla.lineas[i - 1]
            curr = tabla.lineas[i]
            assert curr.pendiente <= prev.pendiente

    def test_acumulado_continuity(self, equipo_medico):
        """End of one year = start of next year."""
        tabla = generate_depreciation_schedule(equipo_medico)
        for i in range(1, len(tabla.lineas)):
            prev = tabla.lineas[i - 1]
            curr = tabla.lineas[i]
            assert abs(curr.acumulado_inicio - prev.acumulado_fin) < 0.01

    def test_deduccion_plus_pendiente_equals_moi(self, laptop):
        tabla = generate_depreciation_schedule(laptop)
        for linea in tabla.lineas:
            total = linea.acumulado_fin + linea.pendiente
            assert abs(total - tabla.moi_deducible) < 1.0


# ─── Test: Construcciones (5% rate, 20 years) ───────────────────────

class TestConstrucciones:
    def test_5_pct_rate(self):
        activo = ActivoFijo(
            nombre="Adecuación consultorio",
            tipo_activo="construcciones",
            moi=500_000.0,
            fecha_adquisicion="2025-01-01",
        )
        tabla = generate_depreciation_schedule(activo)
        assert tabla.tasa_anual == 5.0
        assert tabla.vida_util_anos == 20

    def test_20_year_schedule(self):
        activo = ActivoFijo(
            nombre="Consultorio",
            tipo_activo="construcciones",
            moi=1_000_000.0,
            fecha_adquisicion="2025-01-01",
        )
        tabla = generate_depreciation_schedule(activo)
        assert len(tabla.lineas) >= 19  # ~20 years


# ─── Test: Module Exports ────────────────────────────────────────────

class TestModuleExports:
    def test_activo_fijo_importable(self):
        from src.tools.depreciation_schedule import ActivoFijo
        assert ActivoFijo is not None

    def test_tabla_importable(self):
        from src.tools.depreciation_schedule import TablaDepreciacion
        assert TablaDepreciacion is not None

    def test_generate_function_callable(self):
        from src.tools.depreciation_schedule import generate_depreciation_schedule
        assert callable(generate_depreciation_schedule)

    def test_registry_function_callable(self):
        from src.tools.depreciation_schedule import generate_asset_registry
        assert callable(generate_asset_registry)

    def test_monthly_function_callable(self):
        from src.tools.depreciation_schedule import get_monthly_depreciation
        assert callable(get_monthly_depreciation)

    def test_uses_central_tasas(self):
        """Verify it uses the same TASAS_DEPRECIACION from deduction_optimizer."""
        from src.tools.depreciation_schedule import TASAS_DEPRECIACION as DS_TASAS
        from src.tools.deduction_optimizer import TASAS_DEPRECIACION as DO_TASAS
        assert DS_TASAS is DO_TASAS
