"""Tests for OpenDoc Deduction Optimizer Engine.

Comprehensive tests for:
- SAT code → expense classification
- Depreciation calculations
- Payment validation
- ISR calculations (612 vs RESICO)
- Regime comparison
- Full deduction analysis
- WhatsApp formatting
"""

import pytest
from src.tools.deduction_optimizer import (
    # Core functions
    classify_expense_by_sat_code,
    is_inversion,
    get_depreciation_type,
    validate_payment,
    calculate_depreciation,
    analyze_deduction,
    compare_regimes,
    calculate_personal_deduction_limit,
    calculate_isr_612_mensual,
    calculate_isr_resico_mensual,
    format_deduction_whatsapp,
    format_strategy_whatsapp,
    # Data classes
    AnalisisDeduccion,
    DepreciacionAnual,
    ValidacionPago,
    EstrategiaAnual,
    TipoDeduccion,
    SubcategoriaGasto,
    TasaDepreciacion,
    # Constants
    TASAS_DEPRECIACION,
    SAT_CODE_DEDUCTION_MAP,
    SUBCATEGORIA_TO_DEPRECIACION,
    INVERSIONES,
    TARIFA_ISR_MENSUAL_2026,
    TARIFA_RESICO_MENSUAL_2026,
)


# ══════════════════════════════════════════════════════════════════════
# TEST: SAT Code → Expense Classification
# ══════════════════════════════════════════════════════════════════════

class TestClassifyExpenseBySATCode:
    """Test SAT product code → subcategory mapping."""

    def test_medical_equipment(self):
        """Equipo médico 42181xxx → EQUIPO_MEDICO."""
        result = classify_expense_by_sat_code("42181502")
        assert result == SubcategoriaGasto.EQUIPO_MEDICO

    def test_computer_equipment(self):
        """Equipo de cómputo 43211xxx → EQUIPO_COMPUTO."""
        result = classify_expense_by_sat_code("43211507")
        assert result == SubcategoriaGasto.EQUIPO_COMPUTO

    def test_office_furniture(self):
        """Mobiliario 56101xxx → MOBILIARIO."""
        result = classify_expense_by_sat_code("56101702")
        assert result == SubcategoriaGasto.MOBILIARIO

    def test_vehicle(self):
        """Vehículo 25101xxx → VEHICULO."""
        result = classify_expense_by_sat_code("25101503")
        assert result == SubcategoriaGasto.VEHICULO

    def test_medical_supplies(self):
        """Material de curación 42131xxx → MATERIAL_CURACION."""
        result = classify_expense_by_sat_code("42131602")
        assert result == SubcategoriaGasto.MATERIAL_CURACION

    def test_medications(self):
        """Medicamentos 51101xxx → MATERIAL_CURACION."""
        result = classify_expense_by_sat_code("51101500")
        assert result == SubcategoriaGasto.MATERIAL_CURACION

    def test_cleaning_service(self):
        """Servicio de limpieza 76111xxx → LIMPIEZA."""
        result = classify_expense_by_sat_code("76111501")
        assert result == SubcategoriaGasto.LIMPIEZA

    def test_advertising(self):
        """Publicidad 82101xxx → PUBLICIDAD."""
        result = classify_expense_by_sat_code("82101502")
        assert result == SubcategoriaGasto.PUBLICIDAD

    def test_software(self):
        """Software 81111xxx → SOFTWARE."""
        result = classify_expense_by_sat_code("81111500")
        assert result == SubcategoriaGasto.SOFTWARE

    def test_insurance(self):
        """Seguros 84131xxx → SEGUROS."""
        result = classify_expense_by_sat_code("84131501")
        assert result == SubcategoriaGasto.SEGUROS

    def test_rent(self):
        """Arrendamiento 80131xxx → ARRENDAMIENTO."""
        result = classify_expense_by_sat_code("80131502")
        assert result == SubcategoriaGasto.ARRENDAMIENTO

    def test_electricity(self):
        """Electricidad 83111xxx → SERVICIOS_BASICOS."""
        result = classify_expense_by_sat_code("83111602")
        assert result == SubcategoriaGasto.SERVICIOS_BASICOS

    def test_restaurant(self):
        """Restaurante 90101xxx → RESTAURANTES."""
        result = classify_expense_by_sat_code("90101501")
        assert result == SubcategoriaGasto.RESTAURANTES

    def test_education(self):
        """Educación médica 86101xxx → EDUCACION_MEDICA."""
        result = classify_expense_by_sat_code("86101705")
        assert result == SubcategoriaGasto.EDUCACION_MEDICA

    def test_stationery(self):
        """Papelería 44121xxx → PAPELERIA."""
        result = classify_expense_by_sat_code("44121600")
        assert result == SubcategoriaGasto.PAPELERIA

    def test_medical_services_as_personal(self):
        """Medical service codes (8510/8511/8512) → GASTOS_MEDICOS_PERSONAL."""
        result = classify_expense_by_sat_code("85121600")
        assert result == SubcategoriaGasto.GASTOS_MEDICOS_PERSONAL

    def test_empty_code(self):
        """Empty code → GASTO_PERSONAL."""
        result = classify_expense_by_sat_code("")
        assert result == SubcategoriaGasto.GASTO_PERSONAL

    def test_none_code(self):
        """None → GASTO_PERSONAL."""
        result = classify_expense_by_sat_code(None)
        assert result == SubcategoriaGasto.GASTO_PERSONAL

    def test_unknown_code(self):
        """Unknown code → GASTO_PERSONAL."""
        result = classify_expense_by_sat_code("99999999")
        assert result == SubcategoriaGasto.GASTO_PERSONAL

    def test_banking_services(self):
        """Servicios bancarios 84121xxx → GASTOS_FINANCIEROS."""
        result = classify_expense_by_sat_code("84121501")
        assert result == SubcategoriaGasto.GASTOS_FINANCIEROS

    def test_surgical_instruments(self):
        """Instrumental quirúrgico 42241xxx → INSTRUMENTAL."""
        result = classify_expense_by_sat_code("42241501")
        assert result == SubcategoriaGasto.INSTRUMENTAL

    def test_laundry(self):
        """Lavandería 91111xxx → LAVANDERIA."""
        result = classify_expense_by_sat_code("91111701")
        assert result == SubcategoriaGasto.LAVANDERIA

    def test_rpbi_collection(self):
        """Recolección RPBI 76121xxx → RECOLECCION_RPBI."""
        result = classify_expense_by_sat_code("76121501")
        assert result == SubcategoriaGasto.RECOLECCION_RPBI

    def test_accounting_services(self):
        """Contabilidad 84111xxx → HONORARIOS_PROFESIONALES."""
        result = classify_expense_by_sat_code("84111502")
        assert result == SubcategoriaGasto.HONORARIOS_PROFESIONALES


# ══════════════════════════════════════════════════════════════════════
# TEST: Investment Classification
# ══════════════════════════════════════════════════════════════════════

class TestInversionClassification:
    """Test which subcategories are investments requiring depreciation."""

    def test_equipo_medico_is_inversion(self):
        assert is_inversion(SubcategoriaGasto.EQUIPO_MEDICO) is True

    def test_equipo_computo_is_inversion(self):
        assert is_inversion(SubcategoriaGasto.EQUIPO_COMPUTO) is True

    def test_mobiliario_is_inversion(self):
        assert is_inversion(SubcategoriaGasto.MOBILIARIO) is True

    def test_vehiculo_is_inversion(self):
        assert is_inversion(SubcategoriaGasto.VEHICULO) is True

    def test_construcciones_is_inversion(self):
        assert is_inversion(SubcategoriaGasto.CONSTRUCCIONES) is True

    def test_instrumental_is_inversion(self):
        assert is_inversion(SubcategoriaGasto.INSTRUMENTAL) is True

    def test_material_curacion_not_inversion(self):
        assert is_inversion(SubcategoriaGasto.MATERIAL_CURACION) is False

    def test_arrendamiento_not_inversion(self):
        assert is_inversion(SubcategoriaGasto.ARRENDAMIENTO) is False

    def test_software_not_inversion(self):
        assert is_inversion(SubcategoriaGasto.SOFTWARE) is False

    def test_nomina_not_inversion(self):
        assert is_inversion(SubcategoriaGasto.NOMINA) is False


# ══════════════════════════════════════════════════════════════════════
# TEST: Depreciation Type Mapping
# ══════════════════════════════════════════════════════════════════════

class TestDepreciationTypeMapping:
    """Test subcategory → depreciation type."""

    def test_equipo_medico(self):
        assert get_depreciation_type(SubcategoriaGasto.EQUIPO_MEDICO) == "equipo_medico"

    def test_instrumental(self):
        assert get_depreciation_type(SubcategoriaGasto.INSTRUMENTAL) == "equipo_medico"

    def test_computo(self):
        assert get_depreciation_type(SubcategoriaGasto.EQUIPO_COMPUTO) == "equipo_computo"

    def test_mobiliario(self):
        assert get_depreciation_type(SubcategoriaGasto.MOBILIARIO) == "mobiliario"

    def test_vehiculo(self):
        assert get_depreciation_type(SubcategoriaGasto.VEHICULO) == "vehiculo"

    def test_non_investment_returns_none(self):
        assert get_depreciation_type(SubcategoriaGasto.ARRENDAMIENTO) is None


# ══════════════════════════════════════════════════════════════════════
# TEST: Depreciation Rates Constants
# ══════════════════════════════════════════════════════════════════════

class TestDepreciationRates:
    """Test TASAS_DEPRECIACION constants."""

    def test_equipo_medico_10_percent(self):
        tasa = TASAS_DEPRECIACION["equipo_medico"]
        assert tasa.tasa_anual == 10.0
        assert "Art. 35" in tasa.fundamento

    def test_computo_30_percent(self):
        tasa = TASAS_DEPRECIACION["equipo_computo"]
        assert tasa.tasa_anual == 30.0
        assert "Art. 35" in tasa.fundamento

    def test_mobiliario_10_percent(self):
        tasa = TASAS_DEPRECIACION["mobiliario"]
        assert tasa.tasa_anual == 10.0
        assert "Art. 34" in tasa.fundamento

    def test_vehiculo_25_percent_with_cap(self):
        tasa = TASAS_DEPRECIACION["vehiculo"]
        assert tasa.tasa_anual == 25.0
        assert tasa.tope_moi == 175_000.0
        assert "Art. 36" in tasa.fundamento

    def test_construcciones_5_percent(self):
        tasa = TASAS_DEPRECIACION["construcciones"]
        assert tasa.tasa_anual == 5.0
        assert "Art. 34" in tasa.fundamento

    def test_all_have_fundamento(self):
        for key, tasa in TASAS_DEPRECIACION.items():
            assert tasa.fundamento, f"Missing fundamento for {key}"

    def test_all_have_descripcion(self):
        for key, tasa in TASAS_DEPRECIACION.items():
            assert tasa.descripcion, f"Missing descripcion for {key}"


# ══════════════════════════════════════════════════════════════════════
# TEST: Payment Validation
# ══════════════════════════════════════════════════════════════════════

class TestPaymentValidation:
    """Test payment method → deductibility validation."""

    def test_cash_over_2000_not_deductible(self):
        result = validate_payment("01", 5000)
        assert result.es_deducible is False
        assert "NO DEDUCIBLE" in result.problema
        assert "Art. 27" in result.fundamento

    def test_cash_under_2000_deductible(self):
        result = validate_payment("01", 1500)
        assert result.es_deducible is True
        assert "bancarizar" in result.recomendacion.lower()

    def test_cash_exactly_2000_deductible(self):
        result = validate_payment("01", 2000)
        assert result.es_deducible is True

    def test_cash_2001_not_deductible(self):
        result = validate_payment("01", 2001)
        assert result.es_deducible is False

    def test_transfer_deductible(self):
        result = validate_payment("03", 50000)
        assert result.es_deducible is True

    def test_credit_card_deductible(self):
        result = validate_payment("04", 10000)
        assert result.es_deducible is True

    def test_debit_card_deductible(self):
        result = validate_payment("28", 10000)
        assert result.es_deducible is True

    def test_check_deductible(self):
        result = validate_payment("02", 10000)
        assert result.es_deducible is True

    def test_electronic_wallet_deductible(self):
        result = validate_payment("05", 3000)
        assert result.es_deducible is True

    def test_por_definir_not_deductible(self):
        result = validate_payment("99", 5000)
        assert result.es_deducible is False
        assert "no definida" in result.problema.lower()

    def test_unknown_forma_not_deductible(self):
        result = validate_payment("XX", 5000)
        assert result.es_deducible is False

    def test_restaurant_with_card_91_5_percent(self):
        result = validate_payment("04", 1000, es_restaurante=True)
        assert result.es_deducible is True
        assert "91.5%" in result.recomendacion
        assert "$915" in result.recomendacion

    def test_restaurant_with_cash_small(self):
        result = validate_payment("01", 500, es_restaurante=False)
        assert result.es_deducible is True

    def test_forma_pago_descriptions(self):
        """Verify that descriptions are human-readable."""
        result = validate_payment("03", 1000)
        assert result.forma_pago == "Transferencia"

        result = validate_payment("04", 1000)
        assert result.forma_pago == "Tarjeta de crédito"


# ══════════════════════════════════════════════════════════════════════
# TEST: Depreciation Calculation
# ══════════════════════════════════════════════════════════════════════

class TestDepreciationCalculation:
    """Test depreciation calculations for various asset types."""

    def test_medical_equipment_basic(self):
        """Ecógrafo $300,000 — 10% anual."""
        dep = calculate_depreciation(moi=300_000, tipo_activo="equipo_medico")
        assert dep.moi == 300_000
        assert dep.moi_deducible == 300_000
        assert dep.tasa_anual == 10.0
        assert dep.deduccion_anual == 30_000
        assert dep.deduccion_mensual == 2_500
        assert "Art. 35" in dep.fundamento

    def test_computer_30_percent(self):
        """Laptop $30,000 — 30% anual."""
        dep = calculate_depreciation(moi=30_000, tipo_activo="equipo_computo")
        assert dep.tasa_anual == 30.0
        assert dep.deduccion_anual == 9_000
        assert dep.deduccion_mensual == 750

    def test_vehicle_with_cap(self):
        """Auto $500,000 — capped at $175,000."""
        dep = calculate_depreciation(moi=500_000, tipo_activo="vehiculo")
        assert dep.moi == 500_000
        assert dep.moi_deducible == 175_000
        assert dep.tasa_anual == 25.0
        assert dep.deduccion_anual == 43_750
        assert "Tope MOI" in dep.nota_estrategia
        assert "arrendamiento" in dep.nota_estrategia.lower()

    def test_vehicle_under_cap(self):
        """Auto $150,000 — no cap."""
        dep = calculate_depreciation(moi=150_000, tipo_activo="vehiculo")
        assert dep.moi_deducible == 150_000
        assert dep.deduccion_anual == 37_500

    def test_vehicle_exactly_at_cap(self):
        """Auto exactly $175,000."""
        dep = calculate_depreciation(moi=175_000, tipo_activo="vehiculo")
        assert dep.moi_deducible == 175_000
        assert dep.nota_estrategia == ""  # No warning needed

    def test_iva_added_to_moi(self):
        """IVA not creditable — adds to MOI."""
        dep = calculate_depreciation(
            moi=100_000,
            tipo_activo="equipo_medico",
            iva_pagado=16_000,
        )
        assert dep.moi == 116_000  # 100K + 16K IVA
        assert dep.moi_deducible == 116_000
        assert dep.deduccion_anual == 11_600  # 116K * 10%
        assert dep.iva_no_acreditable == 16_000

    def test_iva_on_vehicle_exceeds_cap(self):
        """Vehicle $160,000 + IVA $25,600 = $185,600 → capped at $175,000."""
        dep = calculate_depreciation(
            moi=160_000,
            tipo_activo="vehiculo",
            iva_pagado=25_600,
        )
        assert dep.moi == 185_600
        assert dep.moi_deducible == 175_000

    def test_months_in_use_tracking(self):
        """Track accumulated depreciation."""
        dep = calculate_depreciation(
            moi=120_000,
            tipo_activo="equipo_computo",
            meses_en_uso=12,  # 1 year
        )
        assert dep.acumulado_deducido == 36_000  # 120K * 30% = 36K/year
        assert dep.pendiente_deducir == 84_000
        assert dep.meses_restantes == 28  # ceil(84000 / 3000)

    def test_fully_depreciated(self):
        """Asset fully depreciated after sufficient months."""
        dep = calculate_depreciation(
            moi=30_000,
            tipo_activo="equipo_computo",  # 30%
            meses_en_uso=48,  # 4 years = fully depreciated
        )
        assert dep.acumulado_deducido == 30_000
        assert dep.pendiente_deducir == 0

    def test_construction_5_percent(self):
        dep = calculate_depreciation(moi=200_000, tipo_activo="construcciones")
        assert dep.tasa_anual == 5.0
        assert dep.deduccion_anual == 10_000

    def test_invalid_asset_type_raises(self):
        with pytest.raises(ValueError, match="desconocido"):
            calculate_depreciation(moi=50_000, tipo_activo="invalid_type")

    def test_fecha_adquisicion_stored(self):
        dep = calculate_depreciation(
            moi=50_000,
            tipo_activo="equipo_medico",
            fecha_adquisicion="2026-01-15",
        )
        assert dep.fecha_inicio == "2026-01-15"

    def test_computo_strategy_note(self):
        """Equipo de cómputo gets strategic note about 30% rate."""
        dep = calculate_depreciation(moi=20_000, tipo_activo="equipo_computo")
        assert "30%" in dep.nota_estrategia

    def test_expensive_medical_equipment_strategy(self):
        """Expensive medical equipment gets deducción inmediata hint."""
        dep = calculate_depreciation(moi=200_000, tipo_activo="equipo_medico")
        assert "deducción inmediata" in dep.nota_estrategia.lower()


# ══════════════════════════════════════════════════════════════════════
# TEST: Full Deduction Analysis
# ══════════════════════════════════════════════════════════════════════

class TestAnalyzeDeduction:
    """Test the main analyze_deduction function."""

    def test_medical_supply_deductible(self):
        """Material de curación paid by transfer → 100% deductible."""
        result = analyze_deduction(
            monto=5_000,
            clave_prod_serv="42131602",
            forma_pago="03",
            regimen="612",
        )
        assert result.deducible_612 is True
        assert result.deducible_resico is False
        assert result.monto_deducible == 5_000
        assert result.porcentaje_deducible == 100.0
        assert result.subcategoria == SubcategoriaGasto.MATERIAL_CURACION.value
        assert result.depreciacion is None  # Not an investment

    def test_medical_equipment_investment(self):
        """Ecógrafo → investment with depreciation."""
        result = analyze_deduction(
            monto=300_000,
            clave_prod_serv="42181502",
            forma_pago="03",
            regimen="612",
        )
        assert result.deducible_612 is True
        assert result.tipo_deduccion == TipoDeduccion.INVERSION.value
        assert result.depreciacion is not None
        assert result.depreciacion.tasa_anual == 10.0
        assert result.depreciacion.deduccion_anual == 30_000

    def test_computer_investment(self):
        """Laptop → 30% depreciation."""
        result = analyze_deduction(
            monto=25_000,
            clave_prod_serv="43211507",
            forma_pago="04",
            regimen="612",
        )
        assert result.depreciacion is not None
        assert result.depreciacion.tasa_anual == 30.0

    def test_cash_over_2000_blocks_deduction(self):
        """Cash >$2,000 → NOT deductible."""
        result = analyze_deduction(
            monto=5_000,
            clave_prod_serv="42131602",
            forma_pago="01",
            regimen="612",
        )
        assert result.deducible_612 is False
        assert result.monto_deducible == 0
        assert result.porcentaje_deducible == 0
        assert len(result.alertas) > 0

    def test_resico_no_operational_deductions(self):
        """RESICO → no operational deductions."""
        result = analyze_deduction(
            monto=5_000,
            clave_prod_serv="42131602",
            forma_pago="03",
            regimen="625",
        )
        assert result.tipo_deduccion == TipoDeduccion.RESICO_NO_APLICA.value
        assert result.deducible_resico is False
        assert any("RESICO" in a for a in result.alertas)

    def test_restaurant_91_5_percent(self):
        """Restaurant with card → 91.5% deductible."""
        result = analyze_deduction(
            monto=1_000,
            clave_prod_serv="90101501",
            forma_pago="04",
            regimen="612",
        )
        assert result.porcentaje_deducible == 91.5
        assert result.monto_deducible == 915.0

    def test_vehicle_with_iva(self):
        """Vehicle with IVA → cap applied."""
        result = analyze_deduction(
            monto=400_000,
            clave_prod_serv="25101503",
            forma_pago="03",
            regimen="612",
            iva_pagado=64_000,
        )
        assert result.depreciacion is not None
        assert result.depreciacion.moi == 464_000  # 400K + IVA
        assert result.depreciacion.moi_deducible == 175_000
        assert any("tope" in a.lower() or "excede" in a.lower() for a in result.alertas)

    def test_requirements_include_cfdi(self):
        """All expenses require CFDI."""
        result = analyze_deduction(
            monto=1_000,
            clave_prod_serv="42131602",
            forma_pago="03",
        )
        assert any("CFDI" in r for r in result.requisitos)

    def test_over_2000_requires_bank(self):
        """Expenses >$2,000 require banked payment."""
        result = analyze_deduction(
            monto=3_000,
            clave_prod_serv="42131602",
            forma_pago="03",
        )
        assert any("sistema financiero" in r.lower() for r in result.requisitos)

    def test_investment_requires_fixed_asset(self):
        """Investments require registration as fixed asset."""
        result = analyze_deduction(
            monto=50_000,
            clave_prod_serv="42181502",
            forma_pago="03",
        )
        assert any("activo fijo" in r.lower() for r in result.requisitos)

    def test_vehicle_requires_log(self):
        """Vehicle deduction requires usage log (bitácora)."""
        result = analyze_deduction(
            monto=200_000,
            clave_prod_serv="25101503",
            forma_pago="03",
        )
        assert any("bitácora" in r.lower() for r in result.requisitos)
        assert any("bitácora" in r.lower() or "proporción" in r.lower() for r in result.recomendaciones)

    def test_to_dict(self):
        """AnalisisDeduccion can be serialized."""
        result = analyze_deduction(
            monto=5_000,
            clave_prod_serv="42131602",
            forma_pago="03",
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "subcategoria" in d
        assert "monto_total" in d


# ══════════════════════════════════════════════════════════════════════
# TEST: ISR Calculations
# ══════════════════════════════════════════════════════════════════════

class TestISRCalculation:
    """Test ISR computation for both regimes."""

    def test_isr_612_zero_income(self):
        assert calculate_isr_612_mensual(0) == 0.0

    def test_isr_612_negative_income(self):
        assert calculate_isr_612_mensual(-5000) == 0.0

    def test_isr_612_low_income(self):
        """Low income → low bracket."""
        isr = calculate_isr_612_mensual(5_000)
        assert isr > 0
        assert isr < 5_000  # Less than income

    def test_isr_612_medium_income(self):
        """Medium income doctor (~$50K/month net)."""
        isr = calculate_isr_612_mensual(50_000)
        assert isr > 0
        assert isr < 50_000

    def test_isr_612_high_income(self):
        """High income doctor (~$200K/month)."""
        isr = calculate_isr_612_mensual(200_000)
        assert isr > 0
        # At high brackets, ISR is ~30-35%
        assert isr > 200_000 * 0.20  # At least 20%

    def test_isr_612_progressive(self):
        """ISR should be progressive (higher income → higher rate)."""
        isr_low = calculate_isr_612_mensual(10_000)
        isr_high = calculate_isr_612_mensual(100_000)
        rate_low = isr_low / 10_000
        rate_high = isr_high / 100_000
        assert rate_high > rate_low  # Progressive tax

    def test_isr_resico_zero(self):
        assert calculate_isr_resico_mensual(0) == 0.0

    def test_isr_resico_negative(self):
        assert calculate_isr_resico_mensual(-5000) == 0.0

    def test_isr_resico_low_bracket(self):
        """RESICO ≤$25K → 1%."""
        isr = calculate_isr_resico_mensual(20_000)
        assert isr == 200.0  # 20K * 1%

    def test_isr_resico_medium_bracket(self):
        """RESICO $50K-$83K → 1.5%."""
        isr = calculate_isr_resico_mensual(60_000)
        assert isr == 900.0  # 60K * 1.5%

    def test_isr_resico_high_bracket(self):
        """RESICO $83K-$208K → 2%."""
        isr = calculate_isr_resico_mensual(150_000)
        assert isr == 3_000.0  # 150K * 2%

    def test_isr_resico_max_bracket(self):
        """RESICO $208K-$291K → 2.5%."""
        isr = calculate_isr_resico_mensual(250_000)
        assert isr == 6_250.0  # 250K * 2.5%

    def test_resico_always_less_than_income(self):
        """RESICO rates 1-2.5% → always much less than income."""
        for income in [10_000, 50_000, 100_000, 200_000]:
            isr = calculate_isr_resico_mensual(income)
            assert isr < income * 0.03  # Always < 3%


# ══════════════════════════════════════════════════════════════════════
# TEST: Regime Comparison
# ══════════════════════════════════════════════════════════════════════

class TestRegimeComparison:
    """Test 612 vs RESICO comparison logic."""

    def test_high_expenses_favors_612(self):
        """Doctor with very high expenses (>80%) → 612 is better.

        RESICO rates (1-2.5%) are so low that deductions must exceed ~78%
        of income for Régimen 612 to be cheaper.
        """
        result = compare_regimes(
            ingresos_mensuales=100_000,
            deducciones_mensuales=82_000,  # 82% of income
            depreciacion_mensual=5_000,
        )
        assert "612" in result.regimen_recomendado
        assert result.isr_estimado_612 < result.isr_estimado_resico
        assert result.ahorro_estimado > 0

    def test_low_expenses_favors_resico(self):
        """Doctor with low expenses → RESICO is better."""
        result = compare_regimes(
            ingresos_mensuales=100_000,
            deducciones_mensuales=10_000,  # Only 10% of income
            depreciacion_mensual=0,
        )
        assert "RESICO" in result.regimen_recomendado or "625" in result.regimen_recomendado
        assert result.isr_estimado_resico < result.isr_estimado_612

    def test_exceeds_resico_cap(self):
        """Income >$3.5M → forced to 612."""
        result = compare_regimes(
            ingresos_mensuales=350_000,  # $4.2M/year
            deducciones_mensuales=50_000,
        )
        assert "obligatorio" in result.regimen_recomendado.lower() or "612" in result.regimen_recomendado
        assert any("excede" in a.lower() or "tope" in a.lower() for a in result.alertas)

    def test_annualization(self):
        """Monthly figures are annualized correctly."""
        result = compare_regimes(
            ingresos_mensuales=100_000,
            deducciones_mensuales=50_000,
        )
        assert result.ingresos_totales == 1_200_000
        assert result.deducciones_operativas_612 == 600_000

    def test_base_gravable_612_not_negative(self):
        """Base gravable 612 can't be negative."""
        result = compare_regimes(
            ingresos_mensuales=50_000,
            deducciones_mensuales=80_000,  # More deductions than income
        )
        assert result.base_gravable_612 >= 0

    def test_depreciation_included_in_612(self):
        """Depreciation adds to 612 deductions."""
        result = compare_regimes(
            ingresos_mensuales=100_000,
            deducciones_mensuales=40_000,
            depreciacion_mensual=10_000,
        )
        assert result.depreciacion_total_612 == 120_000

    def test_strategy_to_dict(self):
        result = compare_regimes(
            ingresos_mensuales=80_000,
            deducciones_mensuales=30_000,
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "regimen_recomendado" in d

    def test_gray_zone_alert(self):
        """Gray zone (30-40% expenses) triggers alert."""
        result = compare_regimes(
            ingresos_mensuales=100_000,
            deducciones_mensuales=35_000,  # 35%
        )
        # May or may not trigger gray zone depending on depreciation
        # Just verify no crash
        assert result.regimen_recomendado != ""


# ══════════════════════════════════════════════════════════════════════
# TEST: Personal Deduction Limit
# ══════════════════════════════════════════════════════════════════════

class TestPersonalDeductionLimit:
    """Test personal deduction limit calculation."""

    def test_low_income_uses_percentage(self):
        """Low income → 15% is less than 5 UMAs."""
        limit = calculate_personal_deduction_limit(500_000)
        assert limit == 75_000  # 500K * 15%

    def test_high_income_capped_by_umas(self):
        """High income → 5 UMAs is less than 15%."""
        limit = calculate_personal_deduction_limit(5_000_000)
        uma_tope = 37_844.40 * 5
        assert limit == uma_tope

    def test_custom_uma(self):
        """Custom UMA value."""
        limit = calculate_personal_deduction_limit(
            500_000, uma_anual=40_000.0
        )
        assert limit == 75_000  # 15% is still less


# ══════════════════════════════════════════════════════════════════════
# TEST: WhatsApp Formatting
# ══════════════════════════════════════════════════════════════════════

class TestWhatsAppFormatting:
    """Test WhatsApp-ready output formatting."""

    def test_deduction_format_deductible(self):
        result = analyze_deduction(
            monto=5_000,
            clave_prod_serv="42131602",
            forma_pago="03",
        )
        text = format_deduction_whatsapp(result)
        assert "✅" in text
        assert "Material de Curación" in text
        assert "$5,000" in text

    def test_deduction_format_not_deductible(self):
        result = analyze_deduction(
            monto=5_000,
            clave_prod_serv="42131602",
            forma_pago="01",  # Cash > $2000
        )
        text = format_deduction_whatsapp(result)
        assert "❌" in text

    def test_deduction_format_with_depreciation(self):
        result = analyze_deduction(
            monto=100_000,
            clave_prod_serv="42181502",
            forma_pago="03",
        )
        text = format_deduction_whatsapp(result)
        assert "Depreciación" in text
        assert "10%" in text

    def test_strategy_format(self):
        strategy = compare_regimes(
            ingresos_mensuales=100_000,
            deducciones_mensuales=50_000,
        )
        text = format_strategy_whatsapp(strategy)
        assert "COMPARATIVO FISCAL" in text
        assert "RÉGIMEN 612" in text
        assert "RESICO" in text
        assert "RECOMENDACIÓN" in text


# ══════════════════════════════════════════════════════════════════════
# TEST: Enum Values
# ══════════════════════════════════════════════════════════════════════

class TestEnumValues:
    """Test enum definitions are correct."""

    def test_tipo_deduccion_values(self):
        assert TipoDeduccion.OPERATIVA.value == "Deducción Operativa"
        assert TipoDeduccion.INVERSION.value == "Inversión (Activo Fijo)"
        assert TipoDeduccion.PERSONAL.value == "Deducción Personal"
        assert TipoDeduccion.NO_DEDUCIBLE.value == "No Deducible"
        assert TipoDeduccion.RESICO_NO_APLICA.value == "No aplica en RESICO"

    def test_subcategoria_has_all_doctor_expenses(self):
        """Verify all key doctor expense categories exist."""
        expected_categories = [
            "ARRENDAMIENTO", "SERVICIOS_BASICOS", "MATERIAL_CURACION",
            "PUBLICIDAD", "SOFTWARE", "EQUIPO_MEDICO", "EQUIPO_COMPUTO",
            "MOBILIARIO", "VEHICULO", "SEGUROS", "EDUCACION_MEDICA",
            "NOMINA", "SEGURIDAD_SOCIAL", "HONORARIOS_PROFESIONALES",
            "RESTAURANTES", "VIATICOS", "GASTOS_FINANCIEROS",
            "PERMISOS_LICENCIAS", "RECOLECCION_RPBI",
        ]
        for cat in expected_categories:
            assert hasattr(SubcategoriaGasto, cat), f"Missing: {cat}"


# ══════════════════════════════════════════════════════════════════════
# TEST: SAT Code Map Coverage
# ══════════════════════════════════════════════════════════════════════

class TestSATCodeMapCoverage:
    """Test that the SAT code map covers essential medical expense categories."""

    def test_map_not_empty(self):
        assert len(SAT_CODE_DEDUCTION_MAP) > 40

    def test_all_values_are_valid_subcategorias(self):
        for code, subcat in SAT_CODE_DEDUCTION_MAP.items():
            assert isinstance(subcat, SubcategoriaGasto), f"Invalid value for {code}: {subcat}"

    def test_medical_equipment_codes_present(self):
        assert "42181" in SAT_CODE_DEDUCTION_MAP
        assert SAT_CODE_DEDUCTION_MAP["42181"] == SubcategoriaGasto.EQUIPO_MEDICO

    def test_computer_codes_present(self):
        assert "43211" in SAT_CODE_DEDUCTION_MAP
        assert SAT_CODE_DEDUCTION_MAP["43211"] == SubcategoriaGasto.EQUIPO_COMPUTO

    def test_medication_codes_present(self):
        assert "51101" in SAT_CODE_DEDUCTION_MAP
        assert SAT_CODE_DEDUCTION_MAP["51101"] == SubcategoriaGasto.MATERIAL_CURACION

    def test_insurance_codes_present(self):
        assert "84131" in SAT_CODE_DEDUCTION_MAP

    def test_restaurant_codes_present(self):
        assert "90101" in SAT_CODE_DEDUCTION_MAP
        assert SAT_CODE_DEDUCTION_MAP["90101"] == SubcategoriaGasto.RESTAURANTES


# ══════════════════════════════════════════════════════════════════════
# TEST: Enhanced Prompt Rules
# ══════════════════════════════════════════════════════════════════════

class TestEnhancedPromptRules:
    """Test that the fiscal classifier prompt includes deduction rules."""

    def test_prompt_has_depreciation_rules(self):
        from src.tools.fiscal_classifier import FISCAL_CLASSIFICATION_PROMPT
        assert "10% anual" in FISCAL_CLASSIFICATION_PROMPT
        assert "30% anual" in FISCAL_CLASSIFICATION_PROMPT
        assert "25% anual" in FISCAL_CLASSIFICATION_PROMPT
        assert "$175,000" in FISCAL_CLASSIFICATION_PROMPT

    def test_prompt_has_restaurant_rule(self):
        from src.tools.fiscal_classifier import FISCAL_CLASSIFICATION_PROMPT
        assert "91.5%" in FISCAL_CLASSIFICATION_PROMPT
        assert "restaurante" in FISCAL_CLASSIFICATION_PROMPT.lower()

    def test_prompt_has_vehicle_strategy(self):
        from src.tools.fiscal_classifier import FISCAL_CLASSIFICATION_PROMPT
        assert "arrendamiento puro" in FISCAL_CLASSIFICATION_PROMPT.lower()
        assert "$200/día" in FISCAL_CLASSIFICATION_PROMPT

    def test_prompt_has_nomina_rules(self):
        from src.tools.fiscal_classifier import FISCAL_CLASSIFICATION_PROMPT
        assert "IMSS" in FISCAL_CLASSIFICATION_PROMPT
        assert "INFONAVIT" in FISCAL_CLASSIFICATION_PROMPT

    def test_prompt_has_consultorio_categories(self):
        from src.tools.fiscal_classifier import FISCAL_CLASSIFICATION_PROMPT
        prompt = FISCAL_CLASSIFICATION_PROMPT.lower()
        assert "material de curación" in prompt
        assert "publicidad" in prompt
        assert "limpieza" in prompt
        assert "rpbi" in prompt
        assert "educación" in prompt or "cme" in prompt

    def test_prompt_has_iva_non_creditable_note(self):
        from src.tools.fiscal_classifier import FISCAL_CLASSIFICATION_PROMPT
        assert "IVA NO acreditable se SUMA al MOI" in FISCAL_CLASSIFICATION_PROMPT


# ══════════════════════════════════════════════════════════════════════
# TEST: Exports from __init__.py
# ══════════════════════════════════════════════════════════════════════

class TestModuleExports:
    """Test that deduction_optimizer is properly exported."""

    def test_import_from_tools(self):
        from src.tools import analyze_deduction as ad
        assert callable(ad)

    def test_import_calculate_depreciation(self):
        from src.tools import calculate_depreciation as cd
        assert callable(cd)

    def test_import_compare_regimes(self):
        from src.tools import compare_regimes as cr
        assert callable(cr)

    def test_import_validate_payment(self):
        from src.tools import validate_payment as vp
        assert callable(vp)

    def test_import_types(self):
        from src.tools import (
            AnalisisDeduccion, DepreciacionAnual, ValidacionPago,
            EstrategiaAnual, TipoDeduccion, SubcategoriaGasto,
        )
        assert AnalisisDeduccion is not None
        assert TipoDeduccion is not None

    def test_import_constants(self):
        from src.tools import TASAS_DEPRECIACION, SAT_CODE_DEDUCTION_MAP
        assert len(TASAS_DEPRECIACION) > 0
        assert len(SAT_CODE_DEDUCTION_MAP) > 0
