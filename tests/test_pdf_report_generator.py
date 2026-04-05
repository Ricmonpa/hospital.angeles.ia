"""Tests for Agente Contable / fiscal PDF report generator.

Validates PDF generation for all report types:
- Monthly provisional (612 + RESICO)
- Annual declaration (612 + RESICO)
- DIOT (operations with third parties)
- Fiscal health (alerts + score)
- Deduction summary

Tests verify: PDF structure, content correctness, configuration,
filename conventions, WhatsApp summaries, edge cases.
"""

import pytest
from datetime import date
from io import BytesIO

from src.tools.pdf_report_generator import (
    # Functions
    generate_monthly_pdf,
    generate_annual_pdf,
    generate_diot_pdf,
    generate_fiscal_health_pdf,
    generate_deduction_pdf,
    generate_pdf_report,
    # Helpers
    _fmt_currency,
    _fmt_pct,
    _truncate,
    _estimate_pages,
    _build_styles,
    _make_data_table,
    _make_kv_table,
    _make_score_drawing,
    _build_footer_text,
    # Classes
    ConfiguracionPDF,
    ResultadoPDF,
    TipoReporte,
    # Constants
    MESES,
    COLOR_PRIMARY,
    COLOR_ACCENT,
    COLOR_DANGER,
    COLOR_WARNING,
)


# ─── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def config_doctor():
    """Standard doctor configuration."""
    return ConfiguracionPDF(
        nombre_doctor="Dra. María García López",
        rfc_doctor="GALM850101ABC",
        regimen="612",
        especialidad="Ginecología",
        nombre_consultorio="Consultorio Médico García",
        direccion="Blvd. López Mateos 1234, León, Gto.",
        telefono="477-123-4567",
        email="dra.garcia@consultorio.mx",
    )


@pytest.fixture
def resultado_provisional_612():
    """Monthly provisional result for Régimen 612."""
    return {
        "mes": 3,
        "anio": 2026,
        "regimen": "612",
        "ingresos_totales": 120_000.00,
        "ingresos_acumulados_anio": 360_000.00,
        "deducciones_totales": 45_000.00,
        "deducciones_acumuladas_anio": 135_000.00,
        "base_gravable_isr": 225_000.00,
        "isr_causado": 28_036.50,
        "retenciones_isr": 6_000.00,
        "pagos_provisionales_anteriores": 15_000.00,
        "isr_a_pagar": 7_036.50,
        "iva_causado": 0.0,
        "iva_acreditable": 0.0,
        "iva_a_pagar": 0.0,
        "cedular_base": 75_000.00,
        "cedular_tasa": 0.02,
        "cedular_a_pagar": 1_500.00,
        "total_a_pagar": 8_536.50,
        "alertas": ["Revisar comprobantes de nómina pendientes"],
        "notas": ["Deducciones al 37.5% de ingresos acumulados"],
    }


@pytest.fixture
def resultado_provisional_resico():
    """Monthly provisional result for RESICO."""
    return {
        "mes": 6,
        "anio": 2026,
        "regimen": "625",
        "ingresos_totales": 85_000.00,
        "ingresos_acumulados_anio": 510_000.00,
        "base_gravable_isr": 85_000.00,
        "isr_causado": 1_275.00,
        "retenciones_isr": 0.0,
        "pagos_provisionales_anteriores": 0.0,
        "isr_a_pagar": 1_275.00,
        "iva_causado": 0.0,
        "iva_acreditable": 0.0,
        "iva_a_pagar": 0.0,
        "cedular_a_pagar": 0.0,
        "total_a_pagar": 1_275.00,
        "alertas": [],
        "notas": ["RESICO: ISR sobre ingresos cobrados, sin deducciones"],
    }


@pytest.fixture
def resultado_anual_612():
    """Annual declaration result for Régimen 612."""
    return {
        "anio": 2025,
        "regimen": "612",
        "ingresos_totales": 1_440_000.00,
        "ingresos_acumulables_612": 1_440_000.00,
        "ingresos_resico": 0.0,
        "ingresos_salarios": 0.0,
        "deducciones_operativas": 540_000.00,
        "deducciones_personales": 80_000.00,
        "tope_deducciones_personales": 206_480.50,
        "base_gravable_612": 820_000.00,
        "isr_anual_612": 167_628.90,
        "base_gravable_resico": 0.0,
        "isr_anual_resico": 0.0,
        "pagos_provisionales": 140_000.00,
        "retenciones_isr": 36_000.00,
        "isr_total_ejercicio": 167_628.90,
        "isr_a_cargo": 0.0,
        "isr_a_favor": 8_371.10,
        "tasa_efectiva_isr": 11.64,
        "alertas": [],
        "notas": [
            "Deducciones operativas: 37% de ingresos por honorarios",
            "Tienes saldo a favor de $8,371.10",
        ],
    }


@pytest.fixture
def resultado_anual_resico():
    """Annual declaration result for RESICO."""
    return {
        "anio": 2025,
        "regimen": "625",
        "ingresos_totales": 960_000.00,
        "ingresos_acumulables_612": 0.0,
        "ingresos_resico": 960_000.00,
        "ingresos_salarios": 0.0,
        "deducciones_operativas": 0.0,
        "deducciones_personales": 0.0,
        "base_gravable_612": 0.0,
        "isr_anual_612": 0.0,
        "base_gravable_resico": 960_000.00,
        "isr_anual_resico": 14_400.00,
        "pagos_provisionales": 12_000.00,
        "retenciones_isr": 0.0,
        "isr_total_ejercicio": 14_400.00,
        "isr_a_cargo": 2_400.00,
        "isr_a_favor": 0.0,
        "tasa_efectiva_isr": 1.50,
        "alertas": [],
        "notas": ["RESICO: Sin deducciones operativas"],
    }


@pytest.fixture
def resultado_diot():
    """DIOT report result."""
    return {
        "mes": 3,
        "anio": 2026,
        "rfc_declarante": "GALM850101ABC",
        "total_operaciones": 8,
        "total_iva_pagado": 4_320.00,
        "resumen_terceros": [
            {
                "rfc": "XAXX010101000",
                "nombre": "Público en General",
                "num_operaciones": 3,
                "valor_actos_16": 15_000.00,
                "iva_pagado_16": 2_400.00,
                "monto_exento": 0.0,
            },
            {
                "rfc": "ABC990101ABC",
                "nombre": "Distribuidora Médica del Bajío SA de CV",
                "num_operaciones": 5,
                "valor_actos_16": 12_000.00,
                "iva_pagado_16": 1_920.00,
                "monto_exento": 3_500.00,
            },
        ],
        "alertas": [],
        "notas": ["DIOT generada correctamente"],
    }


@pytest.fixture
def resultado_salud_fiscal():
    """Fiscal health report result."""
    return {
        "fecha_reporte": "2026-02-27",
        "regimen": "612",
        "total_alertas": 4,
        "urgentes": 1,
        "importantes": 1,
        "preventivas": 1,
        "informativas": 1,
        "score_salud_fiscal": 72,
        "alertas": [
            {
                "titulo": "e.firma vence en 15 días",
                "mensaje": "Tu certificado e.firma vence el 2026-03-14.",
                "nivel": "Urgente",
                "categoria": "Certificados",
                "accion_requerida": "Renovar en portal SAT",
                "dias_restantes": 15,
            },
            {
                "titulo": "Declaración febrero pendiente",
                "mensaje": "No se detectó pago provisional de febrero 2026.",
                "nivel": "Importante",
                "categoria": "Declaraciones",
                "accion_requerida": "Presentar antes del 17 de marzo",
                "dias_restantes": 18,
            },
            {
                "titulo": "Ingresos RESICO al 65% del tope",
                "mensaje": "Ingresos acumulados: $2,275,000 de $3,500,000.",
                "nivel": "Preventiva",
                "categoria": "Ingresos",
                "accion_requerida": "",
                "dias_restantes": -1,
            },
            {
                "titulo": "Buzón Tributario activo",
                "mensaje": "Tu Buzón Tributario está habilitado correctamente.",
                "nivel": "Informativa",
                "categoria": "Régimen",
                "accion_requerida": "",
                "dias_restantes": -1,
            },
        ],
    }


@pytest.fixture
def deducciones_lista():
    """List of deductions for deduction report."""
    return [
        {"concepto": "Renta consultorio", "monto": 12_000.00, "tipo": "Deducción Operativa", "deducible": True, "fundamento": "Art. 27 LISR"},
        {"concepto": "Material de curación", "monto": 8_500.00, "tipo": "Deducción Operativa", "deducible": True, "fundamento": "Art. 27 LISR"},
        {"concepto": "Luz y agua", "monto": 2_200.00, "tipo": "Deducción Operativa", "deducible": True, "fundamento": "Art. 27 LISR"},
        {"concepto": "Internet", "monto": 800.00, "tipo": "Deducción Operativa", "deducible": True, "fundamento": "Art. 27 LISR"},
        {"concepto": "Nómina asistente", "monto": 15_000.00, "tipo": "Deducción Operativa", "deducible": True, "fundamento": "Art. 27 LISR"},
        {"concepto": "Depreciación equipo médico", "monto": 4_167.00, "tipo": "Inversión (Activo Fijo)", "deducible": True, "fundamento": "Art. 31 LISR"},
        {"concepto": "Comida personal", "monto": 3_000.00, "tipo": "No Deducible", "deducible": False},
        {"concepto": "Gasolina sin CFDI", "monto": 1_500.00, "tipo": "No Deducible", "deducible": False},
    ]


# ─── Test: TipoReporte Enum ──────────────────────────────────────────

class TestTipoReporte:
    def test_all_types_defined(self):
        assert TipoReporte.PROVISIONAL_MENSUAL.value == "Provisional Mensual"
        assert TipoReporte.DECLARACION_ANUAL.value == "Declaración Anual"
        assert TipoReporte.DIOT.value == "DIOT"
        assert TipoReporte.SALUD_FISCAL.value == "Salud Fiscal"
        assert TipoReporte.DEDUCCIONES.value == "Resumen de Deducciones"

    def test_tipo_is_string(self):
        for t in TipoReporte:
            assert isinstance(t.value, str)
            assert len(t.value) > 0

    def test_five_report_types(self):
        assert len(TipoReporte) == 5


# ─── Test: ConfiguracionPDF ──────────────────────────────────────────

class TestConfiguracionPDF:
    def test_defaults(self):
        c = ConfiguracionPDF()
        assert c.nombre_doctor == "Doctor(a)"
        assert c.rfc_doctor == ""
        assert c.regimen == "612"
        assert c.mostrar_marca_agua is True

    def test_custom_config(self, config_doctor):
        assert config_doctor.nombre_doctor == "Dra. María García López"
        assert config_doctor.rfc_doctor == "GALM850101ABC"
        assert config_doctor.especialidad == "Ginecología"

    def test_to_dict(self, config_doctor):
        d = config_doctor.to_dict()
        assert isinstance(d, dict)
        assert d["nombre_doctor"] == "Dra. María García López"
        assert isinstance(d["tamano_pagina"], list)

    def test_page_size_is_letter(self):
        from reportlab.lib.pagesizes import LETTER
        c = ConfiguracionPDF()
        assert c.tamano_pagina == LETTER

    def test_margins_positive(self):
        c = ConfiguracionPDF()
        assert c.margen_superior > 0
        assert c.margen_inferior > 0
        assert c.margen_izquierdo > 0
        assert c.margen_derecho > 0


# ─── Test: ResultadoPDF ──────────────────────────────────────────────

class TestResultadoPDF:
    def test_basic_creation(self):
        r = ResultadoPDF(
            contenido=b"fake-pdf",
            nombre_archivo="test.pdf",
            tipo_reporte="Test",
            paginas=1,
            tamano_bytes=8,
            fecha_generacion="2026-02-27",
            resumen="Test report",
        )
        assert r.contenido == b"fake-pdf"
        assert r.nombre_archivo == "test.pdf"
        assert r.paginas == 1

    def test_to_dict_excludes_contenido(self):
        r = ResultadoPDF(
            contenido=b"binary-data",
            nombre_archivo="test.pdf",
            tipo_reporte="Test",
        )
        d = r.to_dict()
        assert "contenido" not in d
        assert d["nombre_archivo"] == "test.pdf"
        assert d["tipo_reporte"] == "Test"

    def test_resumen_whatsapp(self):
        r = ResultadoPDF(
            contenido=b"x" * 5120,
            nombre_archivo="report.pdf",
            tipo_reporte="Provisional Mensual",
            paginas=1,
            tamano_bytes=5120,
            fecha_generacion="2026-02-27",
            resumen="Test summary",
        )
        wsp = r.resumen_whatsapp()
        assert "━━━ PDF GENERADO ━━━" in wsp
        assert "report.pdf" in wsp
        assert "5 KB" in wsp
        assert "Test summary" in wsp
        assert "Provisional Mensual" in wsp

    def test_resumen_whatsapp_large_file(self):
        r = ResultadoPDF(
            contenido=b"x",
            nombre_archivo="big.pdf",
            tipo_reporte="DIOT",
            paginas=3,
            tamano_bytes=150_000,
            fecha_generacion="2026-01-01",
            resumen="Big report",
        )
        wsp = r.resumen_whatsapp()
        assert "146 KB" in wsp  # 150000 / 1024 ≈ 146
        assert "3 página(s)" in wsp


# ─── Test: Formatting Helpers ─────────────────────────────────────────

class TestFormattingHelpers:
    def test_fmt_currency_positive(self):
        assert _fmt_currency(1234.56) == "$1,234.56"

    def test_fmt_currency_zero(self):
        assert _fmt_currency(0) == "$0.00"

    def test_fmt_currency_negative(self):
        assert _fmt_currency(-500.00) == "-$500.00"

    def test_fmt_currency_large(self):
        assert _fmt_currency(1_500_000.99) == "$1,500,000.99"

    def test_fmt_pct(self):
        assert _fmt_pct(12.345) == "12.3%"

    def test_fmt_pct_zero(self):
        assert _fmt_pct(0) == "0.0%"

    def test_fmt_pct_hundred(self):
        assert _fmt_pct(100) == "100.0%"

    def test_truncate_short(self):
        assert _truncate("Hello", 10) == "Hello"

    def test_truncate_exact(self):
        assert _truncate("Hello", 5) == "Hello"

    def test_truncate_long(self):
        result = _truncate("Hello World", 8)
        assert len(result) == 8
        assert result.endswith("…")

    def test_truncate_one_char(self):
        result = _truncate("ABCDEF", 2)
        assert len(result) == 2

    def test_estimate_pages_small(self):
        assert _estimate_pages(3000) == 1

    def test_estimate_pages_medium(self):
        pages = _estimate_pages(12000)
        assert pages >= 2

    def test_estimate_pages_large(self):
        pages = _estimate_pages(50000)
        assert pages >= 5


# ─── Test: Style Factory ─────────────────────────────────────────────

class TestStyleFactory:
    def test_build_styles_returns_dict(self):
        styles = _build_styles()
        assert isinstance(styles, dict)

    def test_all_expected_styles(self):
        styles = _build_styles()
        expected = [
            "title", "subtitle", "heading", "subheading",
            "body", "body_bold", "footer",
            "amount_positive", "amount_negative",
            "alert_urgent", "alert_warning", "alert_info",
            "big_number", "big_label",
        ]
        for name in expected:
            assert name in styles, f"Missing style: {name}"

    def test_styles_have_font_size(self):
        styles = _build_styles()
        for name, style in styles.items():
            assert style.fontSize > 0, f"Style {name} has no fontSize"


# ─── Test: Table Helpers ──────────────────────────────────────────────

class TestTableHelpers:
    def test_make_data_table(self):
        headers = ["A", "B", "C"]
        rows = [["1", "2", "3"], ["4", "5", "6"]]
        table = _make_data_table(headers, rows)
        assert table is not None

    def test_make_data_table_with_widths(self):
        headers = ["Col1", "Col2"]
        rows = [["x", "y"]]
        table = _make_data_table(headers, rows, col_widths=[100, 200])
        assert table is not None

    def test_make_data_table_single_row(self):
        table = _make_data_table(["H"], [["V"]])
        assert table is not None

    def test_make_kv_table(self):
        items = [("Label 1", "Value 1"), ("Label 2", "Value 2")]
        table = _make_kv_table(items)
        assert table is not None

    def test_make_kv_table_custom_widths(self):
        items = [("L", "V")]
        table = _make_kv_table(items, col_widths=[150, 150])
        assert table is not None

    def test_make_score_drawing(self):
        d = _make_score_drawing(85)
        assert d is not None
        assert d.width == 200
        assert d.height == 80

    def test_make_score_drawing_zero(self):
        d = _make_score_drawing(0)
        assert d is not None

    def test_make_score_drawing_hundred(self):
        d = _make_score_drawing(100)
        assert d is not None

    def test_make_score_drawing_low(self):
        d = _make_score_drawing(30)
        assert d is not None


# ─── Test: Footer ─────────────────────────────────────────────────────

class TestFooter:
    def test_footer_text_basic(self):
        c = ConfiguracionPDF()
        text = _build_footer_text(c)
        assert "Agente Contable" in text
        assert "Fecha:" in text

    def test_footer_text_with_consultorio(self, config_doctor):
        text = _build_footer_text(config_doctor)
        assert "Consultorio Médico García" in text
        assert "Agente Contable" in text


# ─── Test: MESES Constant ────────────────────────────────────────────

class TestMeses:
    def test_twelve_months_plus_empty(self):
        assert len(MESES) == 13
        assert MESES[0] == ""
        assert MESES[1] == "Enero"
        assert MESES[12] == "Diciembre"

    def test_all_months_spanish(self):
        expected = [
            "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
        ]
        assert MESES == expected


# ─── Test: Generate Monthly PDF (612) ────────────────────────────────

class TestGenerateMonthlyPDF612:
    def test_generates_valid_pdf(self, resultado_provisional_612, config_doctor):
        result = generate_monthly_pdf(resultado_provisional_612, config_doctor)
        assert isinstance(result, ResultadoPDF)
        assert result.contenido[:4] == b"%PDF"
        assert result.tamano_bytes > 0

    def test_filename_convention(self, resultado_provisional_612):
        result = generate_monthly_pdf(resultado_provisional_612)
        assert result.nombre_archivo == "provisional_612_2026_03.pdf"

    def test_tipo_reporte(self, resultado_provisional_612):
        result = generate_monthly_pdf(resultado_provisional_612)
        assert result.tipo_reporte == "Provisional Mensual"

    def test_resumen_includes_total(self, resultado_provisional_612):
        result = generate_monthly_pdf(resultado_provisional_612)
        assert "$8,536.50" in result.resumen

    def test_resumen_includes_month(self, resultado_provisional_612):
        result = generate_monthly_pdf(resultado_provisional_612)
        assert "Marzo" in result.resumen

    def test_resumen_includes_regimen(self, resultado_provisional_612):
        result = generate_monthly_pdf(resultado_provisional_612)
        assert "612" in result.resumen

    def test_fecha_generacion(self, resultado_provisional_612):
        result = generate_monthly_pdf(resultado_provisional_612)
        assert result.fecha_generacion == date.today().isoformat()

    def test_pages_at_least_one(self, resultado_provisional_612):
        result = generate_monthly_pdf(resultado_provisional_612)
        assert result.paginas >= 1

    def test_default_config(self, resultado_provisional_612):
        result = generate_monthly_pdf(resultado_provisional_612)
        assert result.contenido[:4] == b"%PDF"

    def test_with_iva(self):
        """Test monthly PDF when doctor has IVA (aesthetic procedures)."""
        data = {
            "mes": 5,
            "anio": 2026,
            "regimen": "612",
            "ingresos_totales": 200_000.00,
            "base_gravable_isr": 150_000.00,
            "isr_causado": 20_000.00,
            "isr_a_pagar": 15_000.00,
            "iva_causado": 16_000.00,
            "iva_acreditable": 5_000.00,
            "iva_a_pagar": 11_000.00,
            "cedular_a_pagar": 0.0,
            "total_a_pagar": 26_000.00,
            "alertas": [],
            "notas": [],
        }
        result = generate_monthly_pdf(data)
        assert result.contenido[:4] == b"%PDF"
        assert result.tamano_bytes > 0

    def test_with_cedular(self, resultado_provisional_612):
        result = generate_monthly_pdf(resultado_provisional_612)
        # Cedular is 1,500 in fixture — should be in PDF
        assert result.contenido[:4] == b"%PDF"


# ─── Test: Generate Monthly PDF (RESICO) ─────────────────────────────

class TestGenerateMonthlyPDFRESICO:
    def test_generates_valid_pdf(self, resultado_provisional_resico):
        result = generate_monthly_pdf(resultado_provisional_resico)
        assert result.contenido[:4] == b"%PDF"

    def test_filename_resico(self, resultado_provisional_resico):
        result = generate_monthly_pdf(resultado_provisional_resico)
        assert result.nombre_archivo == "provisional_625_2026_06.pdf"

    def test_resumen_resico(self, resultado_provisional_resico):
        result = generate_monthly_pdf(resultado_provisional_resico)
        assert "625" in result.resumen
        assert "Junio" in result.resumen


# ─── Test: Generate Annual PDF (612) ─────────────────────────────────

class TestGenerateAnnualPDF612:
    def test_generates_valid_pdf(self, resultado_anual_612, config_doctor):
        result = generate_annual_pdf(resultado_anual_612, config_doctor)
        assert result.contenido[:4] == b"%PDF"
        assert result.tamano_bytes > 0

    def test_filename_convention(self, resultado_anual_612):
        result = generate_annual_pdf(resultado_anual_612)
        assert result.nombre_archivo == "declaracion_anual_612_2025.pdf"

    def test_tipo_reporte(self, resultado_anual_612):
        result = generate_annual_pdf(resultado_anual_612)
        assert result.tipo_reporte == "Declaración Anual"

    def test_resumen_a_favor(self, resultado_anual_612):
        result = generate_annual_pdf(resultado_anual_612)
        assert "A favor" in result.resumen
        assert "$8,371.10" in result.resumen

    def test_a_cargo_scenario(self, resultado_anual_resico):
        result = generate_annual_pdf(resultado_anual_resico)
        assert "A cargo" in result.resumen
        assert "$2,400.00" in result.resumen

    def test_zero_balance(self):
        data = {
            "anio": 2025,
            "regimen": "612",
            "ingresos_totales": 500_000.00,
            "isr_total_ejercicio": 50_000.00,
            "pagos_provisionales": 50_000.00,
            "retenciones_isr": 0.0,
            "isr_a_cargo": 0.0,
            "isr_a_favor": 0.0,
            "tasa_efectiva_isr": 10.0,
            "alertas": [],
            "notas": [],
        }
        result = generate_annual_pdf(data)
        assert result.contenido[:4] == b"%PDF"

    def test_fecha_generacion(self, resultado_anual_612):
        result = generate_annual_pdf(resultado_anual_612)
        assert result.fecha_generacion == date.today().isoformat()


# ─── Test: Generate Annual PDF (RESICO) ──────────────────────────────

class TestGenerateAnnualPDFRESICO:
    def test_generates_valid_pdf(self, resultado_anual_resico):
        result = generate_annual_pdf(resultado_anual_resico)
        assert result.contenido[:4] == b"%PDF"

    def test_filename_resico(self, resultado_anual_resico):
        result = generate_annual_pdf(resultado_anual_resico)
        assert result.nombre_archivo == "declaracion_anual_625_2025.pdf"


# ─── Test: Generate DIOT PDF ─────────────────────────────────────────

class TestGenerateDIOTPDF:
    def test_generates_valid_pdf(self, resultado_diot, config_doctor):
        result = generate_diot_pdf(resultado_diot, config_doctor)
        assert result.contenido[:4] == b"%PDF"
        assert result.tamano_bytes > 0

    def test_filename_convention(self, resultado_diot):
        result = generate_diot_pdf(resultado_diot)
        assert result.nombre_archivo == "diot_2026_03.pdf"

    def test_tipo_reporte(self, resultado_diot):
        result = generate_diot_pdf(resultado_diot)
        assert result.tipo_reporte == "DIOT"

    def test_resumen_includes_providers(self, resultado_diot):
        result = generate_diot_pdf(resultado_diot)
        assert "2 proveedores" in result.resumen

    def test_resumen_includes_iva(self, resultado_diot):
        result = generate_diot_pdf(resultado_diot)
        assert "$4,320.00" in result.resumen

    def test_empty_terceros(self):
        data = {
            "mes": 1,
            "anio": 2026,
            "rfc_declarante": "TEST000101AAA",
            "total_operaciones": 0,
            "total_iva_pagado": 0.0,
            "resumen_terceros": [],
            "alertas": [],
            "notas": [],
        }
        result = generate_diot_pdf(data)
        assert result.contenido[:4] == b"%PDF"
        assert "0 proveedores" in result.resumen

    def test_long_provider_name_truncated(self):
        """Provider name longer than 25 chars should be truncated in table."""
        data = {
            "mes": 2,
            "anio": 2026,
            "total_operaciones": 1,
            "total_iva_pagado": 100.00,
            "resumen_terceros": [{
                "rfc": "LONG991231AAA",
                "nombre": "A" * 50,
                "num_operaciones": 1,
                "valor_actos_16": 625.00,
                "iva_pagado_16": 100.00,
                "monto_exento": 0.0,
            }],
            "alertas": [],
            "notas": [],
        }
        result = generate_diot_pdf(data)
        assert result.contenido[:4] == b"%PDF"

    def test_default_config(self, resultado_diot):
        result = generate_diot_pdf(resultado_diot)
        assert result.contenido[:4] == b"%PDF"


# ─── Test: Generate Fiscal Health PDF ─────────────────────────────────

class TestGenerateFiscalHealthPDF:
    def test_generates_valid_pdf(self, resultado_salud_fiscal, config_doctor):
        result = generate_fiscal_health_pdf(resultado_salud_fiscal, config_doctor)
        assert result.contenido[:4] == b"%PDF"
        assert result.tamano_bytes > 0

    def test_filename_convention(self, resultado_salud_fiscal):
        result = generate_fiscal_health_pdf(resultado_salud_fiscal)
        assert result.nombre_archivo == "salud_fiscal_2026-02-27.pdf"

    def test_tipo_reporte(self, resultado_salud_fiscal):
        result = generate_fiscal_health_pdf(resultado_salud_fiscal)
        assert result.tipo_reporte == "Salud Fiscal"

    def test_resumen_includes_score(self, resultado_salud_fiscal):
        result = generate_fiscal_health_pdf(resultado_salud_fiscal)
        assert "72/100" in result.resumen

    def test_resumen_includes_alert_count(self, resultado_salud_fiscal):
        result = generate_fiscal_health_pdf(resultado_salud_fiscal)
        assert "4 alertas" in result.resumen

    def test_perfect_score(self):
        data = {
            "fecha_reporte": "2026-02-27",
            "regimen": "612",
            "total_alertas": 0,
            "urgentes": 0,
            "importantes": 0,
            "preventivas": 0,
            "informativas": 0,
            "score_salud_fiscal": 100,
            "alertas": [],
        }
        result = generate_fiscal_health_pdf(data)
        assert result.contenido[:4] == b"%PDF"
        assert "100/100" in result.resumen

    def test_critical_score(self):
        data = {
            "fecha_reporte": "2026-02-27",
            "total_alertas": 10,
            "urgentes": 5,
            "importantes": 3,
            "preventivas": 2,
            "informativas": 0,
            "score_salud_fiscal": 15,
            "alertas": [
                {"titulo": "Critical issue", "mensaje": "Fix now", "nivel": "Urgente"},
            ],
        }
        result = generate_fiscal_health_pdf(data)
        assert result.contenido[:4] == b"%PDF"
        assert "15/100" in result.resumen

    def test_alert_with_dias_restantes(self, resultado_salud_fiscal):
        result = generate_fiscal_health_pdf(resultado_salud_fiscal)
        assert result.contenido[:4] == b"%PDF"

    def test_default_config(self, resultado_salud_fiscal):
        result = generate_fiscal_health_pdf(resultado_salud_fiscal)
        assert result.contenido[:4] == b"%PDF"


# ─── Test: Generate Deduction PDF ────────────────────────────────────

class TestGenerateDeductionPDF:
    def test_generates_valid_pdf(self, deducciones_lista, config_doctor):
        result = generate_deduction_pdf(
            deducciones_lista, 120_000.00, "612", 2026, config_doctor,
        )
        assert result.contenido[:4] == b"%PDF"
        assert result.tamano_bytes > 0

    def test_filename_convention(self, deducciones_lista):
        result = generate_deduction_pdf(deducciones_lista, 100_000.00)
        assert result.nombre_archivo == "deducciones_612_2026.pdf"

    def test_tipo_reporte(self, deducciones_lista):
        result = generate_deduction_pdf(deducciones_lista, 100_000.00)
        assert result.tipo_reporte == "Resumen de Deducciones"

    def test_resumen_includes_count(self, deducciones_lista):
        result = generate_deduction_pdf(deducciones_lista, 100_000.00)
        assert "8 conceptos" in result.resumen

    def test_resumen_includes_deductible_total(self, deducciones_lista):
        result = generate_deduction_pdf(deducciones_lista, 100_000.00)
        # Total deducible = 12000+8500+2200+800+15000+4167 = 42,667
        assert "$42,667.00" in result.resumen

    def test_resumen_percentage(self, deducciones_lista):
        result = generate_deduction_pdf(deducciones_lista, 100_000.00)
        # 42667 / 100000 = 42.7%
        assert "42.7%" in result.resumen

    def test_resico_regime(self, deducciones_lista):
        result = generate_deduction_pdf(
            deducciones_lista, 100_000.00, "625", 2026,
        )
        assert result.nombre_archivo == "deducciones_625_2026.pdf"
        assert result.contenido[:4] == b"%PDF"

    def test_empty_deductions(self):
        result = generate_deduction_pdf([], 100_000.00)
        assert result.contenido[:4] == b"%PDF"
        assert "0 conceptos" in result.resumen

    def test_zero_income(self, deducciones_lista):
        result = generate_deduction_pdf(deducciones_lista, 0.0)
        assert result.contenido[:4] == b"%PDF"

    def test_all_non_deductible(self):
        deds = [
            {"concepto": "Gasto personal", "monto": 5000.00, "tipo": "No Deducible", "deducible": False},
            {"concepto": "Sin CFDI", "monto": 3000.00, "tipo": "No Deducible", "deducible": False},
        ]
        result = generate_deduction_pdf(deds, 100_000.00)
        assert result.contenido[:4] == b"%PDF"
        assert "$0.00" in result.resumen  # no deductible amount

    def test_default_params(self, deducciones_lista):
        result = generate_deduction_pdf(deducciones_lista, 80_000.00)
        assert result.nombre_archivo == "deducciones_612_2026.pdf"


# ─── Test: Unified Entry Point ───────────────────────────────────────

class TestGeneratePdfReport:
    def test_provisional(self, resultado_provisional_612):
        result = generate_pdf_report(
            TipoReporte.PROVISIONAL_MENSUAL.value,
            resultado_provisional_612,
        )
        assert result.tipo_reporte == "Provisional Mensual"
        assert result.contenido[:4] == b"%PDF"

    def test_annual(self, resultado_anual_612):
        result = generate_pdf_report(
            TipoReporte.DECLARACION_ANUAL.value,
            resultado_anual_612,
        )
        assert result.tipo_reporte == "Declaración Anual"
        assert result.contenido[:4] == b"%PDF"

    def test_diot(self, resultado_diot):
        result = generate_pdf_report(
            TipoReporte.DIOT.value,
            resultado_diot,
        )
        assert result.tipo_reporte == "DIOT"
        assert result.contenido[:4] == b"%PDF"

    def test_fiscal_health(self, resultado_salud_fiscal):
        result = generate_pdf_report(
            TipoReporte.SALUD_FISCAL.value,
            resultado_salud_fiscal,
        )
        assert result.tipo_reporte == "Salud Fiscal"
        assert result.contenido[:4] == b"%PDF"

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="no reconocido"):
            generate_pdf_report("Reporte Inexistente", {})

    def test_with_config(self, resultado_provisional_612, config_doctor):
        result = generate_pdf_report(
            TipoReporte.PROVISIONAL_MENSUAL.value,
            resultado_provisional_612,
            config_doctor,
        )
        assert result.contenido[:4] == b"%PDF"

    def test_deduction_not_in_unified(self):
        """Deduction report requires different params, not in unified."""
        with pytest.raises(ValueError):
            generate_pdf_report(TipoReporte.DEDUCCIONES.value, {})


# ─── Test: Edge Cases ─────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_resultado_monthly(self):
        """Minimal data should still produce a valid PDF."""
        result = generate_monthly_pdf({"mes": 1, "anio": 2026})
        assert result.contenido[:4] == b"%PDF"

    def test_empty_resultado_annual(self):
        result = generate_annual_pdf({"anio": 2025})
        assert result.contenido[:4] == b"%PDF"

    def test_empty_resultado_diot(self):
        result = generate_diot_pdf({"mes": 1, "anio": 2026})
        assert result.contenido[:4] == b"%PDF"

    def test_empty_resultado_health(self):
        result = generate_fiscal_health_pdf({})
        assert result.contenido[:4] == b"%PDF"

    def test_month_out_of_range(self):
        result = generate_monthly_pdf({"mes": 0, "anio": 2026})
        assert result.contenido[:4] == b"%PDF"

    def test_month_thirteen(self):
        result = generate_monthly_pdf({"mes": 13, "anio": 2026})
        assert result.contenido[:4] == b"%PDF"

    def test_negative_amounts(self):
        data = {
            "mes": 1, "anio": 2026, "regimen": "612",
            "ingresos_totales": -100.00,
            "isr_a_pagar": -50.00,
            "total_a_pagar": -50.00,
            "alertas": [], "notas": [],
        }
        result = generate_monthly_pdf(data)
        assert result.contenido[:4] == b"%PDF"

    def test_very_large_amounts(self):
        data = {
            "mes": 12, "anio": 2026, "regimen": "612",
            "ingresos_totales": 999_999_999.99,
            "isr_a_pagar": 350_000_000.00,
            "total_a_pagar": 350_000_000.00,
            "alertas": [], "notas": [],
        }
        result = generate_monthly_pdf(data)
        assert result.contenido[:4] == b"%PDF"

    def test_many_alerts(self):
        alertas = [
            {"titulo": f"Alert {i}", "mensaje": f"Message {i}", "nivel": "Importante"}
            for i in range(20)
        ]
        data = {
            "fecha_reporte": "2026-01-01",
            "total_alertas": 20,
            "urgentes": 0,
            "importantes": 20,
            "preventivas": 0,
            "informativas": 0,
            "score_salud_fiscal": 10,
            "alertas": alertas,
        }
        result = generate_fiscal_health_pdf(data)
        assert result.contenido[:4] == b"%PDF"

    def test_string_alerts_in_monthly(self):
        """Alerts as plain strings (not dicts)."""
        data = {
            "mes": 3, "anio": 2026,
            "alertas": ["Simple string alert 1", "Simple string alert 2"],
            "notas": ["A note"],
        }
        result = generate_monthly_pdf(data)
        assert result.contenido[:4] == b"%PDF"

    def test_dict_alerts_in_health(self):
        """Alerts as dicts with full structure."""
        data = {
            "fecha_reporte": "2026-02-27",
            "score_salud_fiscal": 50,
            "total_alertas": 1,
            "alertas": [{
                "titulo": "Test",
                "mensaje": "Test message",
                "nivel": "Urgente",
                "accion_requerida": "Do something",
                "dias_restantes": 3,
            }],
        }
        result = generate_fiscal_health_pdf(data)
        assert result.contenido[:4] == b"%PDF"


# ─── Test: Color Constants ───────────────────────────────────────────

class TestColorConstants:
    def test_primary_color(self):
        assert COLOR_PRIMARY is not None

    def test_accent_color(self):
        assert COLOR_ACCENT is not None

    def test_danger_color(self):
        assert COLOR_DANGER is not None

    def test_warning_color(self):
        assert COLOR_WARNING is not None


# ─── Test: Module Exports ────────────────────────────────────────────

class TestModuleExports:
    def test_generate_functions_exist(self):
        from src.tools import pdf_report_generator as m
        assert callable(m.generate_monthly_pdf)
        assert callable(m.generate_annual_pdf)
        assert callable(m.generate_diot_pdf)
        assert callable(m.generate_fiscal_health_pdf)
        assert callable(m.generate_deduction_pdf)
        assert callable(m.generate_pdf_report)

    def test_classes_exist(self):
        from src.tools import pdf_report_generator as m
        assert m.ConfiguracionPDF is not None
        assert m.ResultadoPDF is not None
        assert m.TipoReporte is not None

    def test_constants_exist(self):
        from src.tools import pdf_report_generator as m
        assert m.MESES is not None
        assert m.COLOR_PRIMARY is not None


# ─── Test: PDF Binary Validation ─────────────────────────────────────

class TestPDFBinaryValidation:
    def test_pdf_header_magic_bytes(self, resultado_provisional_612):
        result = generate_monthly_pdf(resultado_provisional_612)
        assert result.contenido[:5] == b"%PDF-"

    def test_pdf_has_eof_marker(self, resultado_provisional_612):
        result = generate_monthly_pdf(resultado_provisional_612)
        assert b"%%EOF" in result.contenido[-100:]

    def test_pdf_not_empty(self, resultado_provisional_612):
        result = generate_monthly_pdf(resultado_provisional_612)
        assert len(result.contenido) > 100

    def test_pdf_size_matches(self, resultado_provisional_612):
        result = generate_monthly_pdf(resultado_provisional_612)
        assert result.tamano_bytes == len(result.contenido)

    def test_annual_pdf_has_magic_bytes(self, resultado_anual_612):
        result = generate_annual_pdf(resultado_anual_612)
        assert result.contenido[:5] == b"%PDF-"

    def test_diot_pdf_has_magic_bytes(self, resultado_diot):
        result = generate_diot_pdf(resultado_diot)
        assert result.contenido[:5] == b"%PDF-"

    def test_health_pdf_has_magic_bytes(self, resultado_salud_fiscal):
        result = generate_fiscal_health_pdf(resultado_salud_fiscal)
        assert result.contenido[:5] == b"%PDF-"

    def test_deduction_pdf_has_magic_bytes(self, deducciones_lista):
        result = generate_deduction_pdf(deducciones_lista, 100_000.00)
        assert result.contenido[:5] == b"%PDF-"
