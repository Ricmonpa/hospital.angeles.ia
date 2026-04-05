"""Tests for the Fiscal Classifier — CFDI + Gemini Integration.

Unit tests (no API calls) verify:
- Rule-based pre-classification logic
- Payment method validation
- Prompt building
- Response parsing
- ClasificacionFiscal data structure
- WhatsApp formatting
- Edge cases

Uses the REAL CFDI from Ricardo Moncada Palafox (MOPR881228EF9FF22.xml).
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import asdict

from src.tools.cfdi_parser import parse_cfdi, CFDI, ConceptoCFDI, TimbreFiscal
from src.tools.fiscal_classifier import (
    classify_cfdi,
    classify_cfdi_offline,
    full_cfdi_analysis,
    ClasificacionFiscal,
    Deducibilidad,
    CategoriaFiscal,
    AlertaFiscal,
    _preclassify_tipo_comprobante,
    _preclassify_forma_pago,
    _preclassify_medical_service,
    _build_cfdi_summary_for_gemini,
    _parse_classification_response,
    FISCAL_CLASSIFICATION_PROMPT,
)
from src.tools.cfdi_parser import (
    CLAVES_MEDICAS_SAT,
    MEDICAL_CODE_PREFIXES,
    is_medical_service,
    get_medical_service_name,
)


# Path to the real CFDI XML
REAL_XML = Path(__file__).parent.parent / "data" / "templates" / "MOPR881228EF9FF22.xml"


@pytest.fixture
def real_cfdi():
    """Parse the real CFDI once for all tests."""
    return parse_cfdi(REAL_XML)


@pytest.fixture
def ingreso_cfdi():
    """Create a CFDI where doctor is the emisor (income)."""
    cfdi = CFDI(
        version="4.0",
        tipo_comprobante="I",
        tipo_comprobante_desc="Ingreso",
        emisor_rfc="DOCX900101ABC",
        emisor_nombre="DR. JUAN PÉREZ",
        emisor_regimen="612",
        receptor_rfc="XAXX010101000",
        receptor_nombre="PÚBLICO EN GENERAL",
        total=5000.0,
        subtotal=4310.34,
        iva_trasladado=689.66,
        forma_pago="03",
        metodo_pago="PUE",
        fecha="2025-01-15T10:00:00",
        timbre=TimbreFiscal(uuid="TEST-UUID-001", fecha_timbrado="2025-01-15T10:05:00"),
    )
    return cfdi


@pytest.fixture
def nomina_cfdi():
    """Create a Nómina CFDI."""
    return CFDI(
        version="4.0",
        tipo_comprobante="N",
        tipo_comprobante_desc="Nómina",
        emisor_rfc="DOCX900101ABC",
        emisor_nombre="DR. JUAN PÉREZ",
        receptor_rfc="EMPL850101XYZ",
        receptor_nombre="MARIA LÓPEZ",
        total=8500.0,
        subtotal=8500.0,
        forma_pago="03",
        fecha="2025-01-31T12:00:00",
    )


@pytest.fixture
def traslado_cfdi():
    """Create a Traslado CFDI."""
    return CFDI(
        version="4.0",
        tipo_comprobante="T",
        tipo_comprobante_desc="Traslado",
        emisor_rfc="TRANS900101XXX",
        total=0.0,
        fecha="2025-02-01T08:00:00",
    )


@pytest.fixture
def efectivo_cfdi():
    """CFDI paid in cash over $2,000."""
    return CFDI(
        version="3.3",
        tipo_comprobante="I",
        tipo_comprobante_desc="Ingreso",
        emisor_rfc="PROV900101ABC",
        emisor_nombre="FARMACIA DEL CENTRO",
        receptor_rfc="DOCX900101ABC",
        receptor_nombre="DR. JUAN PÉREZ",
        total=3500.0,
        subtotal=3017.24,
        iva_trasladado=482.76,
        forma_pago="01",  # Efectivo
        forma_pago_desc="Efectivo",
        metodo_pago="PUE",
        fecha="2025-01-20T14:00:00",
    )


# ─── Test: Data Structures ─────────────────────────────────────────────

class TestClasificacionFiscal:
    def test_create_basic(self):
        c = ClasificacionFiscal(
            deducibilidad="Deducible",
            categoria_fiscal="Gastos Médicos",
            confianza=0.95,
        )
        assert c.deducibilidad == "Deducible"
        assert c.confianza == 0.95

    def test_to_dict(self):
        c = ClasificacionFiscal(
            deducibilidad="No Deducible",
            categoria_fiscal="No Deducible",
            confianza=0.8,
        )
        d = c.to_dict()
        assert isinstance(d, dict)
        assert d["deducibilidad"] == "No Deducible"
        assert d["confianza"] == 0.8

    def test_resumen_whatsapp_deducible(self):
        c = ClasificacionFiscal(
            deducibilidad="Deducible",
            categoria_fiscal="Gastos Médicos",
            fundamento_legal="Art. 27 fracción I LISR",
            resumen_doctor="Material quirúrgico deducible al 100%.",
            confianza=0.95,
        )
        resumen = c.resumen_whatsapp()
        assert "✅" in resumen
        assert "Deducible" in resumen
        assert "Art. 27" in resumen

    def test_resumen_whatsapp_no_deducible(self):
        c = ClasificacionFiscal(
            deducibilidad="No Deducible",
            categoria_fiscal="No Deducible",
            resumen_doctor="Gasto personal, no deducible.",
            confianza=0.9,
        )
        resumen = c.resumen_whatsapp()
        assert "❌" in resumen

    def test_resumen_whatsapp_parcial(self):
        c = ClasificacionFiscal(
            deducibilidad="Parcialmente Deducible",
            categoria_fiscal="Gastos en General",
            resumen_doctor="Automóvil deducible hasta $175,000.",
            confianza=0.85,
        )
        resumen = c.resumen_whatsapp()
        assert "⚠️" in resumen

    def test_resumen_whatsapp_with_alerts(self):
        c = ClasificacionFiscal(
            deducibilidad="Deducible",
            categoria_fiscal="Gastos Médicos",
            resumen_doctor="OK",
            alertas=[
                {"tipo": "warning", "mensaje": "Pago en efectivo mayor a $2,000"},
                {"tipo": "info", "mensaje": "RMF 2026 actualizada"},
            ],
            confianza=0.9,
        )
        resumen = c.resumen_whatsapp()
        assert "🚨" in resumen
        assert "ℹ️" in resumen

    def test_resumen_whatsapp_with_recommendations(self):
        c = ClasificacionFiscal(
            deducibilidad="Deducible",
            categoria_fiscal="Honorarios Profesionales",
            resumen_doctor="Servicio profesional.",
            recomendaciones=["Guardar comprobante de pago", "Verificar UUID en portal SAT"],
            confianza=0.9,
        )
        resumen = c.resumen_whatsapp()
        assert "→ Guardar comprobante" in resumen
        assert "→ Verificar UUID" in resumen


class TestEnums:
    def test_deducibilidad_values(self):
        assert Deducibilidad.DEDUCIBLE.value == "Deducible"
        assert Deducibilidad.NO_DEDUCIBLE.value == "No Deducible"
        assert Deducibilidad.PARCIALMENTE.value == "Parcialmente Deducible"
        assert Deducibilidad.REQUIERE_REVISION.value == "Requiere Revisión"

    def test_categoria_fiscal_values(self):
        assert CategoriaFiscal.GASTOS_MEDICOS.value == "Gastos Médicos"
        assert CategoriaFiscal.HONORARIOS.value == "Honorarios Profesionales"
        assert CategoriaFiscal.INVERSIONES.value == "Inversiones (Activo Fijo)"
        assert CategoriaFiscal.INGRESO.value == "Ingreso Acumulable"


class TestAlertaFiscal:
    def test_create_alert(self):
        a = AlertaFiscal(
            tipo="warning",
            mensaje="Pago en efectivo mayor a $2,000",
            referencia_legal="Art. 27 fracción III LISR",
        )
        assert a.tipo == "warning"
        assert "efectivo" in a.mensaje
        assert "Art. 27" in a.referencia_legal


# ─── Test: Pre-classification (rule-based, no API) ─────────────────────

class TestPreclassifyTipoComprobante:
    def test_nomina_skip_gemini(self, nomina_cfdi):
        pre = _preclassify_tipo_comprobante(nomina_cfdi)
        assert pre["skip_gemini"] is True
        assert pre["clasificacion_rapida"] is not None
        assert pre["clasificacion_rapida"].deducibilidad == "Deducible"
        assert pre["clasificacion_rapida"].categoria_fiscal == "Nómina"
        assert pre["clasificacion_rapida"].confianza == 0.99

    def test_traslado_skip_gemini(self, traslado_cfdi):
        pre = _preclassify_tipo_comprobante(traslado_cfdi)
        assert pre["skip_gemini"] is True
        assert pre["clasificacion_rapida"].deducibilidad == "No Deducible"
        assert "Traslado" in pre["clasificacion_rapida"].categoria_fiscal

    def test_ingreso_detected(self, ingreso_cfdi):
        pre = _preclassify_tipo_comprobante(ingreso_cfdi, doctor_rfc="DOCX900101ABC")
        assert pre["es_ingreso"] is True
        assert pre["skip_gemini"] is False

    def test_ingreso_not_detected_without_rfc(self, ingreso_cfdi):
        pre = _preclassify_tipo_comprobante(ingreso_cfdi)
        assert pre["es_ingreso"] is False

    def test_egreso_detected(self):
        cfdi = CFDI(tipo_comprobante="E", tipo_comprobante_desc="Egreso")
        pre = _preclassify_tipo_comprobante(cfdi)
        assert pre["es_egreso"] is True
        assert pre["skip_gemini"] is False

    def test_ingreso_regular_not_skipped(self, real_cfdi):
        pre = _preclassify_tipo_comprobante(real_cfdi)
        assert pre["skip_gemini"] is False
        assert pre["es_ingreso"] is False

    def test_real_cfdi_doctor_is_emisor(self, real_cfdi):
        """With the real CFDI, if doctor's RFC matches emisor, it's income."""
        pre = _preclassify_tipo_comprobante(real_cfdi, doctor_rfc="MOPR881228EF9")
        assert pre["es_ingreso"] is True


class TestPreclassifyFormaPago:
    def test_efectivo_over_2000(self, efectivo_cfdi):
        alertas = _preclassify_forma_pago(efectivo_cfdi)
        assert len(alertas) >= 1
        assert alertas[0].tipo == "warning"
        assert "efectivo" in alertas[0].mensaje.lower()
        assert "$3,500.00" in alertas[0].mensaje

    def test_efectivo_under_2000(self):
        cfdi = CFDI(forma_pago="01", total=1500.0)
        alertas = _preclassify_forma_pago(cfdi)
        assert len(alertas) >= 1
        assert alertas[0].tipo == "info"
        assert "menor a $2,000" in alertas[0].mensaje

    def test_transferencia_no_alert(self, real_cfdi):
        """Real CFDI uses forma_pago=03 (transferencia), no cash alert."""
        alertas = _preclassify_forma_pago(real_cfdi)
        cash_alerts = [a for a in alertas if "efectivo" in a.mensaje.lower()]
        assert len(cash_alerts) == 0

    def test_ppd_without_timbre(self):
        cfdi = CFDI(
            metodo_pago="PPD",
            forma_pago="03",
            total=10000.0,
            timbre=None,
        )
        alertas = _preclassify_forma_pago(cfdi)
        ppd_alerts = [a for a in alertas if "PPD" in a.mensaje]
        assert len(ppd_alerts) >= 1
        assert ppd_alerts[0].tipo == "action_required"


# ─── Test: CFDI Summary Builder ────────────────────────────────────────

class TestBuildCFDISummary:
    def test_real_cfdi_summary(self, real_cfdi):
        summary = _build_cfdi_summary_for_gemini(real_cfdi)
        assert summary["version"] == "3.3"
        assert "MOPR881228EF9" in summary["emisor"]["rfc"]
        assert "RICARDO MONCADA" in summary["emisor"]["nombre"]
        assert summary["montos"]["total"] == 150000.0
        assert summary["montos"]["exento_iva"] is True
        assert len(summary["conceptos"]) == 1
        assert "YOPETT" in summary["conceptos"][0]["descripcion"]

    def test_summary_is_json_serializable(self, real_cfdi):
        summary = _build_cfdi_summary_for_gemini(real_cfdi)
        json_str = json.dumps(summary, ensure_ascii=False)
        assert len(json_str) > 100
        # Should be parseable back
        parsed = json.loads(json_str)
        assert parsed["version"] == "3.3"

    def test_summary_includes_uuid(self, real_cfdi):
        summary = _build_cfdi_summary_for_gemini(real_cfdi)
        assert "C0172468" in summary["uuid"]


# ─── Test: Response Parsing ────────────────────────────────────────────

class TestParseClassificationResponse:
    def test_clean_json(self):
        response = json.dumps({
            "deducibilidad": "Deducible",
            "categoria_fiscal": "Gastos Médicos",
            "porcentaje_deducible": 100,
            "fundamento_legal": "Art. 27 LISR",
            "tipo_gasto": "Estrictamente indispensable",
            "depreciacion_aplicable": False,
            "tasa_depreciacion": None,
            "alertas": [],
            "resumen_doctor": "Material médico deducible.",
            "recomendaciones": ["Guardar comprobante"],
            "confianza": 0.95,
        })
        result = _parse_classification_response(response)
        assert result.deducibilidad == "Deducible"
        assert result.categoria_fiscal == "Gastos Médicos"
        assert result.confianza == 0.95
        assert result.fundamento_legal == "Art. 27 LISR"

    def test_markdown_fenced_json(self):
        response = """```json
{
  "deducibilidad": "No Deducible",
  "categoria_fiscal": "No Deducible",
  "porcentaje_deducible": 0,
  "fundamento_legal": "Art. 28 LISR",
  "tipo_gasto": "Personal",
  "depreciacion_aplicable": false,
  "tasa_depreciacion": null,
  "alertas": [{"tipo": "warning", "mensaje": "Gasto personal"}],
  "resumen_doctor": "No es deducible.",
  "recomendaciones": [],
  "confianza": 0.9
}
```"""
        result = _parse_classification_response(response)
        assert result.deducibilidad == "No Deducible"
        assert len(result.alertas) == 1
        assert result.alertas[0]["tipo"] == "warning"

    def test_with_depreciacion(self):
        response = json.dumps({
            "deducibilidad": "Deducible",
            "categoria_fiscal": "Inversiones (Activo Fijo)",
            "porcentaje_deducible": 100,
            "fundamento_legal": "Art. 34 fracción XI LISR",
            "tipo_gasto": "Inversión",
            "depreciacion_aplicable": True,
            "tasa_depreciacion": 30.0,
            "alertas": [],
            "resumen_doctor": "Equipo de cómputo. Depreciación anual 30%.",
            "recomendaciones": ["Registrar como activo fijo"],
            "confianza": 0.92,
        })
        result = _parse_classification_response(response)
        assert result.depreciacion_aplicable is True
        assert result.tasa_depreciacion == 30.0
        assert "Inversiones" in result.categoria_fiscal

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_classification_response("This is not JSON at all")

    def test_missing_fields_uses_defaults(self):
        response = json.dumps({
            "deducibilidad": "Deducible",
        })
        result = _parse_classification_response(response)
        assert result.deducibilidad == "Deducible"
        assert result.confianza == 0.0  # default
        assert result.categoria_fiscal == ""  # default

    def test_ingreso_classification(self):
        response = json.dumps({
            "deducibilidad": "Deducible",
            "categoria_fiscal": "Ingreso Acumulable",
            "porcentaje_deducible": 0,
            "fundamento_legal": "Art. 100 LISR — Ingresos por actividad profesional",
            "tipo_gasto": "Ingreso",
            "depreciacion_aplicable": False,
            "tasa_depreciacion": None,
            "alertas": [
                {
                    "tipo": "info",
                    "mensaje": "Este CFDI es un ingreso acumulable para declaración anual",
                    "referencia_legal": "Art. 100 LISR",
                }
            ],
            "resumen_doctor": "Ingreso por $150,000. Acumular para declaración anual.",
            "recomendaciones": ["Registrar en libro de ingresos", "Provisionar ISR"],
            "confianza": 0.97,
        })
        result = _parse_classification_response(response)
        assert result.categoria_fiscal == "Ingreso Acumulable"
        assert len(result.alertas) == 1
        assert len(result.recomendaciones) == 2


# ─── Test: Offline Classification (no API) ─────────────────────────────

class TestClassifyCFDIOffline:
    def test_nomina_offline(self, nomina_cfdi):
        result = classify_cfdi_offline(nomina_cfdi)
        assert result.deducibilidad == "Deducible"
        assert result.categoria_fiscal == "Nómina"
        assert result.confianza == 0.99

    def test_traslado_offline(self, traslado_cfdi):
        result = classify_cfdi_offline(traslado_cfdi)
        assert result.deducibilidad == "No Deducible"
        assert result.confianza == 0.99

    def test_regular_cfdi_offline_requires_review(self, real_cfdi):
        result = classify_cfdi_offline(real_cfdi)
        assert result.deducibilidad == "Requiere Revisión"
        assert result.confianza == 0.5

    def test_efectivo_alert_offline(self, efectivo_cfdi):
        result = classify_cfdi_offline(efectivo_cfdi)
        assert any("efectivo" in str(a).lower() for a in result.alertas)


# ─── Test: Prompt Engineering ──────────────────────────────────────────

class TestPromptBuilding:
    def test_prompt_contains_lisr_rules(self):
        assert "Art. 27" in FISCAL_CLASSIFICATION_PROMPT
        assert "Art. 28" in FISCAL_CLASSIFICATION_PROMPT
        assert "LISR" in FISCAL_CLASSIFICATION_PROMPT

    def test_prompt_contains_rmf_2026(self):
        assert "RMF 2026" in FISCAL_CLASSIFICATION_PROMPT
        assert "2.07%" in FISCAL_CLASSIFICATION_PROMPT

    def test_prompt_contains_resico(self):
        assert "RESICO" in FISCAL_CLASSIFICATION_PROMPT
        assert "113-E" in FISCAL_CLASSIFICATION_PROMPT

    def test_prompt_contains_payment_rules(self):
        assert "$2,000" in FISCAL_CLASSIFICATION_PROMPT or "2,000" in FISCAL_CLASSIFICATION_PROMPT
        assert "Efectivo" in FISCAL_CLASSIFICATION_PROMPT or "efectivo" in FISCAL_CLASSIFICATION_PROMPT

    def test_prompt_contains_depreciation_rates(self):
        assert "10%" in FISCAL_CLASSIFICATION_PROMPT  # equipo médico
        assert "30%" in FISCAL_CLASSIFICATION_PROMPT  # cómputo
        assert "25%" in FISCAL_CLASSIFICATION_PROMPT  # automóviles

    def test_prompt_placeholder_for_cfdi_json(self):
        assert "{cfdi_json}" in FISCAL_CLASSIFICATION_PROMPT
        assert "{regimen_receptor}" in FISCAL_CLASSIFICATION_PROMPT


# ─── Test: Mocked Gemini Classification ────────────────────────────────

class TestClassifyCFDIWithMockedGemini:
    @patch("src.tools.fiscal_classifier.genai.GenerativeModel")
    def test_classify_real_cfdi_as_ingreso(self, mock_model_class, real_cfdi):
        """Simulate Gemini classifying the real CFDI as income (doctor is emisor)."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "deducibilidad": "Deducible",
            "categoria_fiscal": "Ingreso Acumulable",
            "porcentaje_deducible": 0,
            "fundamento_legal": "Art. 100 LISR — Ingresos por actividad profesional",
            "tipo_gasto": "Ingreso",
            "depreciacion_aplicable": False,
            "tasa_depreciacion": None,
            "alertas": [
                {
                    "tipo": "info",
                    "mensaje": "Ingreso de $150,000 por proyecto YOPETT",
                    "referencia_legal": "Art. 100 LISR",
                }
            ],
            "resumen_doctor": "Ingreso por $150,000 del proyecto YOPETT. Acumular para ISR anual.",
            "recomendaciones": [
                "Registrar en libro de ingresos",
                "Provisionar ISR (tasa marginal ~30%)",
            ],
            "confianza": 0.96,
        })
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_instance

        result = classify_cfdi(real_cfdi, doctor_rfc="MOPR881228EF9")

        assert result.categoria_fiscal == "Ingreso Acumulable"
        assert result.confianza == 0.96
        assert "YOPETT" in result.resumen_doctor
        assert len(result.recomendaciones) == 2

    @patch("src.tools.fiscal_classifier.genai.GenerativeModel")
    def test_classify_real_cfdi_as_gasto(self, mock_model_class, real_cfdi):
        """Simulate Gemini classifying the real CFDI as expense (doctor is receptor)."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "deducibilidad": "Deducible",
            "categoria_fiscal": "Gastos en General",
            "porcentaje_deducible": 100,
            "fundamento_legal": "Art. 27 fracción I LISR",
            "tipo_gasto": "Estrictamente indispensable",
            "depreciacion_aplicable": False,
            "tasa_depreciacion": None,
            "alertas": [],
            "resumen_doctor": "Servicio profesional recibido. Deducible al 100%.",
            "recomendaciones": ["Guardar comprobante de transferencia"],
            "confianza": 0.93,
        })
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_instance

        result = classify_cfdi(real_cfdi, doctor_rfc="IIC200908QY6")

        assert result.deducibilidad == "Deducible"
        assert result.categoria_fiscal == "Gastos en General"

    @patch("src.tools.fiscal_classifier.genai.GenerativeModel")
    def test_gemini_bad_json_fallback(self, mock_model_class, real_cfdi):
        """If Gemini returns garbage, we get a safe default."""
        mock_response = MagicMock()
        mock_response.text = "Sorry, I can't analyze this document right now."
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_instance

        result = classify_cfdi(real_cfdi)

        assert result.deducibilidad == "Requiere Revisión"
        assert result.confianza == 0.0
        assert "Error" in result.resumen_doctor

    @patch("src.tools.fiscal_classifier.genai.GenerativeModel")
    def test_full_analysis_output(self, mock_model_class, real_cfdi):
        """Test the complete analysis string output."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "deducibilidad": "Deducible",
            "categoria_fiscal": "Ingreso Acumulable",
            "porcentaje_deducible": 0,
            "fundamento_legal": "Art. 100 LISR",
            "tipo_gasto": "Ingreso",
            "depreciacion_aplicable": False,
            "tasa_depreciacion": None,
            "alertas": [],
            "resumen_doctor": "Ingreso acumulable de $150,000.",
            "recomendaciones": [],
            "confianza": 0.95,
        })
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_instance

        output = full_cfdi_analysis(real_cfdi, doctor_rfc="MOPR881228EF9")

        # Should contain both the CFDI summary and fiscal analysis
        assert "CFDI 3.3" in output
        assert "ANÁLISIS FISCAL" in output
        assert "RICARDO MONCADA" in output
        assert "150,000" in output


# ─── Phase 5.5: Medical Service Codes Tests ──────────────────────────

class TestMedicalServiceCodes:
    def test_catalog_not_empty(self):
        assert len(CLAVES_MEDICAS_SAT) >= 30

    def test_known_codes_in_catalog(self):
        assert "85121600" in CLAVES_MEDICAS_SAT
        assert "85121502" in CLAVES_MEDICAS_SAT
        assert "85121601" in CLAVES_MEDICAS_SAT
        assert "85121608" in CLAVES_MEDICAS_SAT

    def test_is_medical_service_exact_match(self):
        assert is_medical_service("85121600") is True
        assert is_medical_service("85121502") is True
        assert is_medical_service("85121800") is True

    def test_is_medical_service_prefix_match(self):
        """Codes starting with medical prefixes should match."""
        assert is_medical_service("85109999") is True  # 8510xxxx
        assert is_medical_service("85129999") is True  # 8512xxxx
        assert is_medical_service("85139999") is True  # 8513xxxx

    def test_is_medical_service_non_medical(self):
        assert is_medical_service("43232100") is False  # Software
        assert is_medical_service("78111802") is False  # Transport
        assert is_medical_service("") is False
        assert is_medical_service("12345678") is False

    def test_get_medical_service_name_found(self):
        name = get_medical_service_name("85121600")
        assert "especialistas" in name.lower()

    def test_get_medical_service_name_not_found(self):
        name = get_medical_service_name("12345678")
        assert name == ""

    def test_get_medical_service_name_empty(self):
        assert get_medical_service_name("") == ""

    def test_medical_prefixes_tuple(self):
        assert "8510" in MEDICAL_CODE_PREFIXES
        assert "8512" in MEDICAL_CODE_PREFIXES
        assert "8513" in MEDICAL_CODE_PREFIXES


# ─── Phase 5.5: Medical Pre-classification Tests ─────────────────────

class TestPreclassifyMedicalService:
    def test_non_medical_cfdi(self, real_cfdi):
        """Real CFDI (YOPETT project) is not medical."""
        result = _preclassify_medical_service(real_cfdi)
        assert result["es_servicio_medico"] is False
        assert result["clave_medica_desc"] == ""

    def test_medical_cfdi_detected(self):
        """CFDI with medical SAT code should be detected."""
        cfdi = CFDI(
            version="4.0",
            tipo_comprobante="I",
            emisor_rfc="DOCX900101ABC",
            receptor_rfc="XAXX010101000",
            total=2500.0,
            subtotal=2500.0,
            exento_iva=True,
            conceptos=[ConceptoCFDI(
                clave_prod_serv="85121600",
                descripcion="Consulta médica especialidad",
                cantidad=1.0,
                importe=2500.0,
                exento=True,
            )],
        )
        result = _preclassify_medical_service(cfdi)
        assert result["es_servicio_medico"] is True
        assert "especialistas" in result["clave_medica_desc"].lower()
        assert "85121600" in result["medical_context_for_prompt"]

    def test_iva_exento_hint(self):
        """Exento IVA should generate proper hint."""
        cfdi = CFDI(
            version="4.0",
            emisor_rfc="DOCX900101ABC",
            receptor_rfc="XAXX010101000",
            exento_iva=True,
            total=1500.0,
            conceptos=[ConceptoCFDI(
                clave_prod_serv="85121502",
                descripcion="Consulta general",
                cantidad=1.0,
                importe=1500.0,
                exento=True,
            )],
        )
        result = _preclassify_medical_service(cfdi)
        assert result["iva_hint"] == "Exento"
        assert "Art. 15 LIVA" in result["medical_context_for_prompt"]

    def test_iva_gravado_hint_possible_aesthetic(self):
        """Gravado 16% with medical code should flag possible aesthetic procedure."""
        cfdi = CFDI(
            version="4.0",
            emisor_rfc="DOCX900101ABC",
            receptor_rfc="XAXX010101000",
            iva_trasladado=400.0,
            total=2900.0,
            subtotal=2500.0,
            conceptos=[ConceptoCFDI(
                clave_prod_serv="85121700",
                descripcion="Cirugía estética",
                cantidad=1.0,
                importe=2500.0,
                iva_tasa=0.16,
                iva_importe=400.0,
            )],
        )
        result = _preclassify_medical_service(cfdi)
        assert result["iva_hint"] == "Gravado 16%"
        assert "estético" in result["medical_context_for_prompt"].lower() or \
               "Criterio 7/IVA/N" in result["medical_context_for_prompt"]

    def test_isr_retention_detected(self):
        """ISR retention should be detected when doctor is emisor billing PM."""
        cfdi = CFDI(
            version="4.0",
            emisor_rfc="DOCX900101ABC",
            receptor_rfc="BSI061110963",  # Persona Moral (12 chars)
            isr_retenido=250.0,
            total=2250.0,
            subtotal=2500.0,
            exento_iva=True,
            conceptos=[ConceptoCFDI(
                clave_prod_serv="85121600",
                descripcion="Consulta especialidad",
                cantidad=1.0,
                importe=2500.0,
                exento=True,
                isr_retencion=250.0,
            )],
        )
        result = _preclassify_medical_service(cfdi, doctor_rfc="DOCX900101ABC")
        assert result["retencion_hint"] == "Retención ISR 10% aplicada"
        assert "Art. 106 LISR" in result["medical_context_for_prompt"]

    def test_persona_moral_receptor_flags_expected_retention(self):
        """When doctor bills PM (RFC 12 digits) without explicit retention, flag it."""
        cfdi = CFDI(
            version="4.0",
            emisor_rfc="DOCX900101ABC",
            receptor_rfc="GCM221031837",  # 12 chars = Persona Moral
            total=5000.0,
            subtotal=5000.0,
            exento_iva=True,
            conceptos=[ConceptoCFDI(
                clave_prod_serv="85121600",
                descripcion="Consulta",
                cantidad=1.0,
                importe=5000.0,
                exento=True,
            )],
        )
        result = _preclassify_medical_service(cfdi, doctor_rfc="DOCX900101ABC")
        assert "esperada" in result["retencion_hint"].lower()
        assert "Persona Moral" in result["medical_context_for_prompt"]


# ─── Phase 5.5: Enhanced Classification Fields Tests ─────────────────

class TestEnhancedClassificationFields:
    def test_new_fields_exist(self):
        c = ClasificacionFiscal()
        assert hasattr(c, "iva_tratamiento")
        assert hasattr(c, "iva_acreditable")
        assert hasattr(c, "retencion_isr_aplicable")
        assert hasattr(c, "es_servicio_medico")
        assert hasattr(c, "clave_medica_desc")

    def test_new_fields_defaults(self):
        c = ClasificacionFiscal()
        assert c.iva_tratamiento == ""
        assert c.iva_acreditable is False
        assert c.retencion_isr_aplicable is False
        assert c.es_servicio_medico is False
        assert c.clave_medica_desc == ""

    def test_new_fields_in_to_dict(self):
        c = ClasificacionFiscal(
            iva_tratamiento="Exento",
            iva_acreditable=False,
            retencion_isr_aplicable=True,
            es_servicio_medico=True,
            clave_medica_desc="Servicios médicos de doctores especialistas",
        )
        d = c.to_dict()
        assert d["iva_tratamiento"] == "Exento"
        assert d["retencion_isr_aplicable"] is True
        assert d["es_servicio_medico"] is True

    def test_parse_response_new_fields(self):
        """Gemini response with new fields should be parsed correctly."""
        response = json.dumps({
            "deducibilidad": "Deducible",
            "categoria_fiscal": "Ingreso Acumulable",
            "porcentaje_deducible": 0,
            "fundamento_legal": "Art. 100 LISR",
            "tipo_gasto": "Ingreso",
            "depreciacion_aplicable": False,
            "tasa_depreciacion": None,
            "iva_tratamiento": "Exento",
            "iva_acreditable": False,
            "retencion_isr_aplicable": True,
            "alertas": [],
            "resumen_doctor": "Ingreso médico exento.",
            "recomendaciones": [],
            "confianza": 0.95,
        })
        result = _parse_classification_response(response)
        assert result.iva_tratamiento == "Exento"
        assert result.iva_acreditable is False
        assert result.retencion_isr_aplicable is True

    def test_parse_response_missing_new_fields_uses_defaults(self):
        """Old-format responses (without new fields) should still parse."""
        response = json.dumps({
            "deducibilidad": "Deducible",
            "categoria_fiscal": "Gastos en General",
            "confianza": 0.9,
        })
        result = _parse_classification_response(response)
        assert result.iva_tratamiento == ""
        assert result.iva_acreditable is False
        assert result.retencion_isr_aplicable is False


# ─── Phase 5.5: Prompt Enhancement Validation ────────────────────────

class TestPromptEnhancements:
    def test_prompt_iva_rules(self):
        assert "Art. 15 LIVA" in FISCAL_CLASSIFICATION_PROMPT
        assert "EXENTOS" in FISCAL_CLASSIFICATION_PROMPT or "EXENTOS de IVA" in FISCAL_CLASSIFICATION_PROMPT

    def test_prompt_aesthetic_exception(self):
        assert "Criterio 7/IVA/N" in FISCAL_CLASSIFICATION_PROMPT
        assert "16%" in FISCAL_CLASSIFICATION_PROMPT

    def test_prompt_isr_retention(self):
        assert "Art. 106 LISR" in FISCAL_CLASSIFICATION_PROMPT
        assert "10%" in FISCAL_CLASSIFICATION_PROMPT
        assert "Persona Moral" in FISCAL_CLASSIFICATION_PROMPT

    def test_prompt_cfdi_40_rules(self):
        assert "D01" in FISCAL_CLASSIFICATION_PROMPT
        assert "E48" in FISCAL_CLASSIFICATION_PROMPT
        assert "P01" in FISCAL_CLASSIFICATION_PROMPT

    def test_prompt_resico_rules(self):
        assert "$3,500,000" in FISCAL_CLASSIFICATION_PROMPT
        assert "Buzón Tributario" in FISCAL_CLASSIFICATION_PROMPT

    def test_prompt_medical_context_placeholder(self):
        assert "{medical_context}" in FISCAL_CLASSIFICATION_PROMPT

    def test_prompt_filing_calendar(self):
        assert "día 17" in FISCAL_CLASSIFICATION_PROMPT or "17 del mes" in FISCAL_CLASSIFICATION_PROMPT
        assert "abril" in FISCAL_CLASSIFICATION_PROMPT.lower()

    def test_prompt_payment_deductibility(self):
        assert "bancarizado" in FISCAL_CLASSIFICATION_PROMPT.lower() or \
               "Efectivo" in FISCAL_CLASSIFICATION_PROMPT


# ─── Phase 5.5: Medical Context Integration in classify_cfdi ─────────

class TestMedicalContextIntegration:
    def test_offline_medical_cfdi_gets_context(self):
        """classify_cfdi_offline with medical code should set medical fields."""
        cfdi = CFDI(
            version="4.0",
            tipo_comprobante="I",
            tipo_comprobante_desc="Ingreso",
            emisor_rfc="DOCX900101ABC",
            receptor_rfc="XAXX010101000",
            total=2500.0,
            subtotal=2500.0,
            exento_iva=True,
            forma_pago="03",
            conceptos=[ConceptoCFDI(
                clave_prod_serv="85121600",
                descripcion="Consulta médica especialidad",
                cantidad=1.0,
                importe=2500.0,
                exento=True,
            )],
        )
        result = classify_cfdi_offline(cfdi, doctor_rfc="DOCX900101ABC")
        assert result.es_servicio_medico is True
        assert result.iva_tratamiento == "Exento"

    def test_offline_non_medical_no_context(self, real_cfdi):
        """Non-medical CFDI should not have medical fields set."""
        result = classify_cfdi_offline(real_cfdi)
        assert result.es_servicio_medico is False

    @patch("src.tools.fiscal_classifier.genai.GenerativeModel")
    def test_classify_medical_passes_context_to_prompt(self, mock_model_class):
        """Verify medical context is injected into Gemini prompt."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "deducibilidad": "Deducible",
            "categoria_fiscal": "Ingreso Acumulable",
            "porcentaje_deducible": 0,
            "fundamento_legal": "Art. 100 LISR",
            "tipo_gasto": "Ingreso",
            "depreciacion_aplicable": False,
            "tasa_depreciacion": None,
            "iva_tratamiento": "Exento",
            "iva_acreditable": False,
            "retencion_isr_aplicable": False,
            "alertas": [],
            "resumen_doctor": "Consulta médica exenta.",
            "recomendaciones": [],
            "confianza": 0.95,
        })
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_instance

        cfdi = CFDI(
            version="4.0",
            tipo_comprobante="I",
            tipo_comprobante_desc="Ingreso",
            emisor_rfc="DOCX900101ABC",
            receptor_rfc="XAXX010101000",
            total=2500.0,
            subtotal=2500.0,
            exento_iva=True,
            forma_pago="03",
            metodo_pago="PUE",
            fecha="2026-01-15T10:00:00",
            timbre=TimbreFiscal(uuid="MED-UUID-001"),
            conceptos=[ConceptoCFDI(
                clave_prod_serv="85121600",
                descripcion="Consulta médica especialidad",
                cantidad=1.0,
                importe=2500.0,
                exento=True,
            )],
        )

        result = classify_cfdi(cfdi, doctor_rfc="DOCX900101ABC")

        # Verify Gemini was called with prompt containing medical context
        call_args = mock_instance.generate_content.call_args
        prompt_sent = call_args[0][0]
        assert "85121600" in prompt_sent
        assert "médic" in prompt_sent.lower()

        # Verify medical fields were set
        assert result.es_servicio_medico is True
        assert result.iva_tratamiento == "Exento"
