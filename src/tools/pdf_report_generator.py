"""PDF reports for Hospital Ángeles IA — Agente Contable.

Professional PDF generation for Mexican doctor fiscal reports.
Converts calculation results into polished, printable PDF documents
that doctors can share with their contador, deliver to patients, or file.

Report types:
1. Monthly provisional (ISR + IVA + cedular)
2. Annual declaration (612 or RESICO)
3. DIOT (operations with third parties)
4. Fiscal health (alerts + score)
5. Deduction summary (optimization recommendations)

Uses reportlab for PDF generation.
Based on: LISR, LIVA, CFF, RMF 2026.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum
from datetime import date, datetime
from io import BytesIO

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import mm, inch
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)
from reportlab.graphics.shapes import Drawing, Rect, String


# ─── Enums ────────────────────────────────────────────────────────────

class TipoReporte(str, Enum):
    """Type of fiscal report."""
    PROVISIONAL_MENSUAL = "Provisional Mensual"
    DECLARACION_ANUAL = "Declaración Anual"
    DIOT = "DIOT"
    SALUD_FISCAL = "Salud Fiscal"
    DEDUCCIONES = "Resumen de Deducciones"


# ─── Color Palette ────────────────────────────────────────────────────

COLOR_PRIMARY = HexColor("#1a5276")       # Dark blue — headers
COLOR_SECONDARY = HexColor("#2e86c1")     # Medium blue — subheadings
COLOR_ACCENT = HexColor("#27ae60")        # Green — positive values
COLOR_DANGER = HexColor("#e74c3c")        # Red — negative/alerts
COLOR_WARNING = HexColor("#f39c12")       # Orange — warnings
COLOR_LIGHT_BG = HexColor("#eaf2f8")      # Light blue — table rows
COLOR_TABLE_HEADER = HexColor("#1a5276")  # Dark blue — table header
COLOR_BORDER = HexColor("#bdc3c7")        # Gray — borders
COLOR_TEXT = HexColor("#2c3e50")          # Dark gray — body text
COLOR_MUTED = HexColor("#7f8c8d")        # Muted gray — footnotes


# ─── Data Classes ─────────────────────────────────────────────────────

@dataclass
class ConfiguracionPDF:
    """PDF generation configuration."""
    nombre_doctor: str = "Doctor(a)"
    rfc_doctor: str = ""
    regimen: str = "612"
    especialidad: str = ""
    direccion: str = ""
    telefono: str = ""
    email: str = ""

    # Branding
    nombre_consultorio: str = ""
    mostrar_marca_agua: bool = True

    # Layout
    tamano_pagina: tuple = LETTER
    margen_superior: float = 20 * mm
    margen_inferior: float = 20 * mm
    margen_izquierdo: float = 20 * mm
    margen_derecho: float = 20 * mm

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tamano_pagina"] = list(self.tamano_pagina)
        return d


@dataclass
class ResultadoPDF:
    """Result of PDF generation."""
    contenido: bytes              # PDF bytes
    nombre_archivo: str           # Suggested filename
    tipo_reporte: str             # TipoReporte value
    paginas: int = 1
    tamano_bytes: int = 0
    fecha_generacion: str = ""
    resumen: str = ""             # Brief description

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("contenido")        # Don't serialize binary
        return d

    def resumen_whatsapp(self) -> str:
        """WhatsApp-friendly generation summary."""
        kb = self.tamano_bytes / 1024
        return (
            f"━━━ PDF GENERADO ━━━\n"
            f"📄 {self.tipo_reporte}\n"
            f"📁 {self.nombre_archivo}\n"
            f"📊 {self.paginas} página(s) · {kb:.0f} KB\n"
            f"📅 {self.fecha_generacion}\n"
            f"\nℹ️ {self.resumen}"
        )


# ─── Month Names ──────────────────────────────────────────────────────

MESES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


# ─── Style Factory ────────────────────────────────────────────────────

def _build_styles() -> dict:
    """Build custom paragraph styles for fiscal reports."""
    base = getSampleStyleSheet()

    styles = {
        "title": ParagraphStyle(
            "ODTitle",
            parent=base["Title"],
            fontSize=18,
            textColor=COLOR_PRIMARY,
            spaceAfter=6,
            alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "ODSubtitle",
            parent=base["Normal"],
            fontSize=11,
            textColor=COLOR_SECONDARY,
            spaceAfter=12,
            alignment=TA_CENTER,
        ),
        "heading": ParagraphStyle(
            "ODHeading",
            parent=base["Heading2"],
            fontSize=13,
            textColor=COLOR_PRIMARY,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "subheading": ParagraphStyle(
            "ODSubheading",
            parent=base["Heading3"],
            fontSize=11,
            textColor=COLOR_SECONDARY,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "ODBody",
            parent=base["Normal"],
            fontSize=9,
            textColor=COLOR_TEXT,
            leading=13,
        ),
        "body_bold": ParagraphStyle(
            "ODBodyBold",
            parent=base["Normal"],
            fontSize=9,
            textColor=COLOR_TEXT,
            leading=13,
            fontName="Helvetica-Bold",
        ),
        "footer": ParagraphStyle(
            "ODFooter",
            parent=base["Normal"],
            fontSize=7,
            textColor=COLOR_MUTED,
            alignment=TA_CENTER,
        ),
        "amount_positive": ParagraphStyle(
            "ODAmountPositive",
            parent=base["Normal"],
            fontSize=9,
            textColor=COLOR_ACCENT,
            alignment=TA_RIGHT,
            fontName="Helvetica-Bold",
        ),
        "amount_negative": ParagraphStyle(
            "ODAmountNegative",
            parent=base["Normal"],
            fontSize=9,
            textColor=COLOR_DANGER,
            alignment=TA_RIGHT,
            fontName="Helvetica-Bold",
        ),
        "alert_urgent": ParagraphStyle(
            "ODAlertUrgent",
            parent=base["Normal"],
            fontSize=9,
            textColor=COLOR_DANGER,
            leading=12,
        ),
        "alert_warning": ParagraphStyle(
            "ODAlertWarning",
            parent=base["Normal"],
            fontSize=9,
            textColor=COLOR_WARNING,
            leading=12,
        ),
        "alert_info": ParagraphStyle(
            "ODAlertInfo",
            parent=base["Normal"],
            fontSize=9,
            textColor=COLOR_SECONDARY,
            leading=12,
        ),
        "big_number": ParagraphStyle(
            "ODBigNumber",
            parent=base["Normal"],
            fontSize=22,
            textColor=COLOR_PRIMARY,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            spaceAfter=4,
        ),
        "big_label": ParagraphStyle(
            "ODBigLabel",
            parent=base["Normal"],
            fontSize=9,
            textColor=COLOR_MUTED,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
    }
    return styles


# ─── Table Helpers ────────────────────────────────────────────────────

def _fmt_currency(amount: float) -> str:
    """Format amount as Mexican currency."""
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"


def _fmt_pct(value: float) -> str:
    """Format as percentage."""
    return f"{value:.1f}%"


def _make_data_table(
    headers: list,
    rows: list,
    col_widths: Optional[list] = None,
) -> Table:
    """Build a styled data table."""
    data = [headers] + rows
    table = Table(data, colWidths=col_widths, repeatRows=1)

    style_commands = [
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_TABLE_HEADER),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),

        # Body
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 5),

        # Grid
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]

    # Alternate row colors
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_commands.append(
                ("BACKGROUND", (0, i), (-1, i), COLOR_LIGHT_BG)
            )

    table.setStyle(TableStyle(style_commands))
    return table


def _make_kv_table(items: list, col_widths: Optional[list] = None) -> Table:
    """Build a key-value pair table (label, value).

    items: list of (label: str, value: str) tuples.
    """
    if not col_widths:
        col_widths = [250, 200]

    table = Table(items, colWidths=col_widths)

    style_commands = [
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), COLOR_TEXT),
        ("TEXTCOLOR", (1, 0), (1, -1), COLOR_TEXT),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, COLOR_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]

    table.setStyle(TableStyle(style_commands))
    return table


# ─── Score Gauge ──────────────────────────────────────────────────────

def _make_score_drawing(score: int, label: str = "Salud Fiscal") -> Drawing:
    """Create a visual score gauge (0-100)."""
    d = Drawing(200, 80)

    # Background bar
    d.add(Rect(20, 30, 160, 20, fillColor=HexColor("#ecf0f1"),
               strokeColor=None))

    # Score fill
    fill_width = max(1, int(160 * score / 100))
    if score >= 80:
        fill_color = COLOR_ACCENT
    elif score >= 50:
        fill_color = COLOR_WARNING
    else:
        fill_color = COLOR_DANGER

    d.add(Rect(20, 30, fill_width, 20, fillColor=fill_color,
               strokeColor=None))

    # Score text
    d.add(String(100, 58, f"{score}/100",
                 fontSize=16, fillColor=COLOR_PRIMARY,
                 textAnchor="middle", fontName="Helvetica-Bold"))

    # Label
    d.add(String(100, 12, label,
                 fontSize=9, fillColor=COLOR_MUTED,
                 textAnchor="middle"))

    return d


# ─── Header / Footer ─────────────────────────────────────────────────

def _build_header(
    config: ConfiguracionPDF,
    tipo: str,
    periodo: str,
    styles: dict,
) -> list:
    """Build report header elements."""
    elements = []

    # Title
    elements.append(Paragraph(f"Hospital Ángeles IA — Agente Contable — {tipo}", styles["title"]))

    # Doctor info
    info_parts = [config.nombre_doctor]
    if config.rfc_doctor:
        info_parts.append(f"RFC: {config.rfc_doctor}")
    if config.regimen:
        info_parts.append(f"Régimen: {config.regimen}")
    elements.append(Paragraph(" · ".join(info_parts), styles["subtitle"]))

    # Period
    if periodo:
        elements.append(Paragraph(periodo, styles["subtitle"]))

    # Divider
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(
        width="100%", thickness=1.5,
        color=COLOR_PRIMARY, spaceAfter=8,
    ))

    return elements


def _build_footer_text(config: ConfiguracionPDF) -> str:
    """Build footer text."""
    parts = ["Generado por Agente Contable (Hospital Ángeles IA)"]
    parts.append(f"Fecha: {date.today().isoformat()}")
    if config.nombre_consultorio:
        parts.append(config.nombre_consultorio)
    return " · ".join(parts)


# ─── Report: Monthly Provisional ─────────────────────────────────────

def generate_monthly_pdf(
    resultado: dict,
    config: Optional[ConfiguracionPDF] = None,
) -> ResultadoPDF:
    """Generate PDF for monthly provisional tax payment.

    Args:
        resultado: ResultadoProvisional.to_dict() or equivalent dict with:
            mes, anio, regimen, ingresos_totales, deducciones_totales,
            base_gravable_isr, isr_causado, retenciones_isr,
            pagos_provisionales_anteriores, isr_a_pagar,
            iva_causado, iva_acreditable, iva_a_pagar,
            cedular_a_pagar, total_a_pagar, alertas, notas
        config: PDF configuration

    Returns:
        ResultadoPDF with generated document.
    """
    if config is None:
        config = ConfiguracionPDF()

    styles = _build_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=config.tamano_pagina,
        topMargin=config.margen_superior,
        bottomMargin=config.margen_inferior,
        leftMargin=config.margen_izquierdo,
        rightMargin=config.margen_derecho,
    )

    elements = []

    # Header
    mes = resultado.get("mes", 0)
    anio = resultado.get("anio", 2026)
    regimen = resultado.get("regimen", config.regimen)
    mes_nombre = MESES[mes] if 1 <= mes <= 12 else str(mes)

    elements.extend(_build_header(
        config,
        TipoReporte.PROVISIONAL_MENSUAL.value,
        f"{mes_nombre} {anio}",
        styles,
    ))

    # Income section
    elements.append(Paragraph("Ingresos", styles["heading"]))
    ingresos_items = [
        ("Ingresos del período", _fmt_currency(resultado.get("ingresos_totales", 0))),
    ]
    ingresos_acum = resultado.get("ingresos_acumulados_anio", 0)
    if ingresos_acum > 0:
        ingresos_items.append(
            ("Ingresos acumulados (ene-" + mes_nombre[:3].lower() + ")",
             _fmt_currency(ingresos_acum))
        )
    elements.append(_make_kv_table(ingresos_items))

    # Deductions (612 only)
    if regimen == "612":
        ded_total = resultado.get("deducciones_totales", 0)
        if ded_total > 0:
            elements.append(Spacer(1, 8))
            elements.append(Paragraph("Deducciones Autorizadas", styles["heading"]))
            ded_items = [
                ("Deducciones del período", _fmt_currency(ded_total)),
            ]
            ded_acum = resultado.get("deducciones_acumuladas_anio", 0)
            if ded_acum > 0:
                ded_items.append(("Deducciones acumuladas", _fmt_currency(ded_acum)))
            elements.append(_make_kv_table(ded_items))

    # ISR section
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("ISR Provisional", styles["heading"]))

    isr_items = [
        ("Base gravable ISR", _fmt_currency(resultado.get("base_gravable_isr", 0))),
        ("ISR causado", _fmt_currency(resultado.get("isr_causado", 0))),
    ]

    ret = resultado.get("retenciones_isr", 0)
    if ret > 0:
        isr_items.append(("(-) Retenciones ISR (PM 10%)", _fmt_currency(ret)))

    prov_ant = resultado.get("pagos_provisionales_anteriores", 0)
    if prov_ant > 0:
        isr_items.append(("(-) Provisionales anteriores", _fmt_currency(prov_ant)))

    isr_a_pagar = resultado.get("isr_a_pagar", 0)
    isr_items.append(("ISR A PAGAR", _fmt_currency(isr_a_pagar)))
    elements.append(_make_kv_table(isr_items))

    # IVA section
    iva_causado = resultado.get("iva_causado", 0)
    iva_a_pagar = resultado.get("iva_a_pagar", 0)
    if iva_causado > 0 or iva_a_pagar != 0:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("IVA", styles["heading"]))
        iva_items = [
            ("IVA causado", _fmt_currency(iva_causado)),
            ("(-) IVA acreditable", _fmt_currency(resultado.get("iva_acreditable", 0))),
            ("IVA A PAGAR", _fmt_currency(iva_a_pagar)),
        ]
        elements.append(_make_kv_table(iva_items))

    # Cedular
    cedular = resultado.get("cedular_a_pagar", 0)
    if cedular > 0:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("Impuesto Cedular Estatal", styles["heading"]))
        ced_items = [
            ("Base cedular", _fmt_currency(resultado.get("cedular_base", 0))),
            ("Tasa", _fmt_pct(resultado.get("cedular_tasa", 0) * 100)),
            ("Cedular A PAGAR", _fmt_currency(cedular)),
        ]
        elements.append(_make_kv_table(ced_items))

    # Total
    elements.append(Spacer(1, 12))
    total = resultado.get("total_a_pagar", 0)
    elements.append(Paragraph(_fmt_currency(total), styles["big_number"]))
    elements.append(Paragraph("TOTAL A PAGAR", styles["big_label"]))
    elements.append(Paragraph(
        "Fecha límite: día 17 del mes siguiente",
        styles["body"],
    ))

    # Alerts
    alertas = resultado.get("alertas", [])
    if alertas:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("Alertas", styles["heading"]))
        for a in alertas:
            elements.append(Paragraph(f"• {a}", styles["alert_warning"]))

    # Notes
    notas = resultado.get("notas", [])
    if notas:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("Notas", styles["subheading"]))
        for n in notas:
            elements.append(Paragraph(f"• {n}", styles["body"]))

    # Footer
    elements.append(Spacer(1, 16))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_BORDER))
    elements.append(Paragraph(_build_footer_text(config), styles["footer"]))

    # Build
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    filename = f"provisional_{regimen}_{anio}_{mes:02d}.pdf"
    return ResultadoPDF(
        contenido=pdf_bytes,
        nombre_archivo=filename,
        tipo_reporte=TipoReporte.PROVISIONAL_MENSUAL.value,
        paginas=_estimate_pages(len(pdf_bytes)),
        tamano_bytes=len(pdf_bytes),
        fecha_generacion=date.today().isoformat(),
        resumen=f"Pago provisional {mes_nombre} {anio} — Régimen {regimen} — Total: {_fmt_currency(total)}",
    )


# ─── Report: Annual Declaration ──────────────────────────────────────

def generate_annual_pdf(
    resultado: dict,
    config: Optional[ConfiguracionPDF] = None,
) -> ResultadoPDF:
    """Generate PDF for annual tax declaration.

    Args:
        resultado: ResultadoAnual.to_dict() or equivalent dict.
        config: PDF configuration

    Returns:
        ResultadoPDF with generated document.
    """
    if config is None:
        config = ConfiguracionPDF()

    styles = _build_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=config.tamano_pagina,
        topMargin=config.margen_superior,
        bottomMargin=config.margen_inferior,
        leftMargin=config.margen_izquierdo,
        rightMargin=config.margen_derecho,
    )

    elements = []

    anio = resultado.get("anio", 2026)
    regimen = resultado.get("regimen", config.regimen)

    elements.extend(_build_header(
        config,
        TipoReporte.DECLARACION_ANUAL.value,
        f"Ejercicio Fiscal {anio}",
        styles,
    ))

    # Income section
    elements.append(Paragraph("Ingresos del Ejercicio", styles["heading"]))
    ing_items = [
        ("Ingresos totales", _fmt_currency(resultado.get("ingresos_totales", 0))),
    ]

    ing_612 = resultado.get("ingresos_acumulables_612", 0)
    if ing_612 > 0:
        ing_items.append(("Honorarios profesionales (612)", _fmt_currency(ing_612)))

    ing_resico = resultado.get("ingresos_resico", 0)
    if ing_resico > 0:
        ing_items.append(("Ingresos RESICO (625)", _fmt_currency(ing_resico)))

    ing_sal = resultado.get("ingresos_salarios", 0)
    if ing_sal > 0:
        ing_items.append(("Sueldos y salarios", _fmt_currency(ing_sal)))

    elements.append(_make_kv_table(ing_items))

    # Deductions (612)
    ded_op = resultado.get("deducciones_operativas", 0)
    if ded_op > 0:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("Deducciones Autorizadas", styles["heading"]))
        ded_items = [
            ("Deducciones operativas", _fmt_currency(ded_op)),
        ]
        ded_pers = resultado.get("deducciones_personales", 0)
        if ded_pers > 0:
            ded_items.append(("Deducciones personales", _fmt_currency(ded_pers)))
            tope = resultado.get("tope_deducciones_personales", 0)
            if tope > 0:
                ded_items.append(("Tope deducciones personales", _fmt_currency(tope)))
        elements.append(_make_kv_table(ded_items))

    # ISR calculation
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Determinación del ISR", styles["heading"]))

    isr_items = []
    base_612 = resultado.get("base_gravable_612", 0)
    if base_612 > 0:
        isr_items.append(("Base gravable (612)", _fmt_currency(base_612)))
        isr_items.append(("ISR Art. 152", _fmt_currency(resultado.get("isr_anual_612", 0))))

    base_resico = resultado.get("base_gravable_resico", 0)
    if base_resico > 0:
        isr_items.append(("Base gravable RESICO", _fmt_currency(base_resico)))
        isr_items.append(("ISR RESICO", _fmt_currency(resultado.get("isr_anual_resico", 0))))

    isr_total = resultado.get("isr_total_ejercicio", 0)
    isr_items.append(("ISR del ejercicio", _fmt_currency(isr_total)))
    isr_items.append(("(-) Pagos provisionales", _fmt_currency(resultado.get("pagos_provisionales", 0))))
    isr_items.append(("(-) Retenciones ISR", _fmt_currency(resultado.get("retenciones_isr", 0))))

    elements.append(_make_kv_table(isr_items))

    # Result — a cargo / a favor
    elements.append(Spacer(1, 12))
    a_cargo = resultado.get("isr_a_cargo", 0)
    a_favor = resultado.get("isr_a_favor", 0)

    if a_cargo > 0:
        elements.append(Paragraph(_fmt_currency(a_cargo), styles["big_number"]))
        elements.append(Paragraph("ISR A CARGO", styles["big_label"]))
        elements.append(Paragraph(
            "Pagar antes del 30 de abril vía portal SAT.",
            styles["body"],
        ))
    elif a_favor > 0:
        sty = ParagraphStyle("Favor", parent=styles["big_number"], textColor=COLOR_ACCENT)
        elements.append(Paragraph(_fmt_currency(a_favor), sty))
        elements.append(Paragraph("ISR A FAVOR", styles["big_label"]))
        elements.append(Paragraph(
            "Solicitar devolución automática en DeclaraSAT (hasta $150,000).",
            styles["body"],
        ))
    else:
        elements.append(Paragraph("$0.00", styles["big_number"]))
        elements.append(Paragraph("SIN SALDO", styles["big_label"]))

    # Effective rate
    tasa = resultado.get("tasa_efectiva_isr", 0)
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        f"Tasa efectiva de ISR: {_fmt_pct(tasa)}",
        styles["body_bold"],
    ))

    # Alerts + notes
    _append_alerts_notes(elements, resultado, styles)

    # Footer
    _append_footer(elements, config, styles)

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    filename = f"declaracion_anual_{regimen}_{anio}.pdf"
    result_label = f"A cargo: {_fmt_currency(a_cargo)}" if a_cargo > 0 else f"A favor: {_fmt_currency(a_favor)}"
    return ResultadoPDF(
        contenido=pdf_bytes,
        nombre_archivo=filename,
        tipo_reporte=TipoReporte.DECLARACION_ANUAL.value,
        paginas=_estimate_pages(len(pdf_bytes)),
        tamano_bytes=len(pdf_bytes),
        fecha_generacion=date.today().isoformat(),
        resumen=f"Declaración anual {anio} — Régimen {regimen} — {result_label}",
    )


# ─── Report: DIOT ────────────────────────────────────────────────────

def generate_diot_pdf(
    resultado: dict,
    config: Optional[ConfiguracionPDF] = None,
) -> ResultadoPDF:
    """Generate PDF for DIOT report.

    Args:
        resultado: ReporteDIOT.to_dict() or equivalent dict with:
            mes, anio, rfc_declarante, total_operaciones,
            total_iva_pagado, resumen_terceros (list of dicts)
        config: PDF configuration

    Returns:
        ResultadoPDF with generated document.
    """
    if config is None:
        config = ConfiguracionPDF()

    styles = _build_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=config.tamano_pagina,
        topMargin=config.margen_superior,
        bottomMargin=config.margen_inferior,
        leftMargin=config.margen_izquierdo,
        rightMargin=config.margen_derecho,
    )

    elements = []

    mes = resultado.get("mes", 0)
    anio = resultado.get("anio", 2026)
    mes_nombre = MESES[mes] if 1 <= mes <= 12 else str(mes)

    elements.extend(_build_header(
        config,
        TipoReporte.DIOT.value,
        f"{mes_nombre} {anio}",
        styles,
    ))

    # Summary
    elements.append(Paragraph("Resumen General", styles["heading"]))
    summary_items = [
        ("RFC declarante", resultado.get("rfc_declarante", config.rfc_doctor)),
        ("Total operaciones", str(resultado.get("total_operaciones", 0))),
        ("Total proveedores", str(len(resultado.get("resumen_terceros", [])))),
        ("IVA pagado total", _fmt_currency(resultado.get("total_iva_pagado", 0))),
    ]
    elements.append(_make_kv_table(summary_items))

    # Third-party table
    terceros = resultado.get("resumen_terceros", [])
    if terceros:
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Detalle por Proveedor", styles["heading"]))

        headers = ["RFC", "Nombre", "Ops", "Valor 16%", "IVA 16%", "Exento"]
        rows = []
        for t in terceros:
            rows.append([
                t.get("rfc", ""),
                _truncate(t.get("nombre", ""), 25),
                str(t.get("num_operaciones", 0)),
                _fmt_currency(t.get("valor_actos_16", 0)),
                _fmt_currency(t.get("iva_pagado_16", 0)),
                _fmt_currency(t.get("monto_exento", 0)),
            ])

        col_widths = [85, 120, 30, 75, 70, 70]
        elements.append(_make_data_table(headers, rows, col_widths))

    # Alerts
    _append_alerts_notes(elements, resultado, styles)

    # Footer
    _append_footer(elements, config, styles)

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    filename = f"diot_{anio}_{mes:02d}.pdf"
    return ResultadoPDF(
        contenido=pdf_bytes,
        nombre_archivo=filename,
        tipo_reporte=TipoReporte.DIOT.value,
        paginas=_estimate_pages(len(pdf_bytes)),
        tamano_bytes=len(pdf_bytes),
        fecha_generacion=date.today().isoformat(),
        resumen=(
            f"DIOT {mes_nombre} {anio} — "
            f"{len(terceros)} proveedores — "
            f"IVA: {_fmt_currency(resultado.get('total_iva_pagado', 0))}"
        ),
    )


# ─── Report: Fiscal Health ───────────────────────────────────────────

def generate_fiscal_health_pdf(
    resultado: dict,
    config: Optional[ConfiguracionPDF] = None,
) -> ResultadoPDF:
    """Generate PDF for fiscal health report.

    Args:
        resultado: ReporteAlertas.to_dict() or equivalent dict with:
            fecha_reporte, regimen, total_alertas, urgentes, importantes,
            preventivas, informativas, alertas (list), score_salud_fiscal
        config: PDF configuration

    Returns:
        ResultadoPDF with generated document.
    """
    if config is None:
        config = ConfiguracionPDF()

    styles = _build_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=config.tamano_pagina,
        topMargin=config.margen_superior,
        bottomMargin=config.margen_inferior,
        leftMargin=config.margen_izquierdo,
        rightMargin=config.margen_derecho,
    )

    elements = []

    fecha = resultado.get("fecha_reporte", date.today().isoformat())
    elements.extend(_build_header(
        config,
        TipoReporte.SALUD_FISCAL.value,
        f"Reporte al {fecha}",
        styles,
    ))

    # Score gauge
    score = resultado.get("score_salud_fiscal", 100)
    elements.append(_make_score_drawing(score))
    elements.append(Spacer(1, 8))

    # Alert summary
    elements.append(Paragraph("Resumen de Alertas", styles["heading"]))
    summary_items = [
        ("Total alertas", str(resultado.get("total_alertas", 0))),
        ("Urgentes", str(resultado.get("urgentes", 0))),
        ("Importantes", str(resultado.get("importantes", 0))),
        ("Preventivas", str(resultado.get("preventivas", 0))),
        ("Informativas", str(resultado.get("informativas", 0))),
    ]
    elements.append(_make_kv_table(summary_items))

    # Alert details
    alertas = resultado.get("alertas", [])
    if alertas:
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Detalle de Alertas", styles["heading"]))

        for alerta in alertas:
            nivel = alerta.get("nivel", "Informativa")
            if nivel == "Urgente":
                style = styles["alert_urgent"]
                prefix = "URGENTE"
            elif nivel == "Importante":
                style = styles["alert_warning"]
                prefix = "IMPORTANTE"
            else:
                style = styles["alert_info"]
                prefix = nivel.upper()

            titulo = alerta.get("titulo", "")
            mensaje = alerta.get("mensaje", "")
            accion = alerta.get("accion_requerida", "")

            block = [
                Paragraph(f"[{prefix}] {titulo}", style),
                Paragraph(mensaje, styles["body"]),
            ]
            if accion:
                block.append(Paragraph(f"Acción: {accion}", styles["body_bold"]))

            dias = alerta.get("dias_restantes", -1)
            if dias >= 0:
                block.append(Paragraph(
                    f"Días restantes: {dias}",
                    styles["alert_warning"] if dias <= 7 else styles["body"],
                ))

            block.append(Spacer(1, 6))
            elements.append(KeepTogether(block))

    # Footer
    _append_footer(elements, config, styles)

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    filename = f"salud_fiscal_{fecha}.pdf"
    return ResultadoPDF(
        contenido=pdf_bytes,
        nombre_archivo=filename,
        tipo_reporte=TipoReporte.SALUD_FISCAL.value,
        paginas=_estimate_pages(len(pdf_bytes)),
        tamano_bytes=len(pdf_bytes),
        fecha_generacion=date.today().isoformat(),
        resumen=f"Score: {score}/100 — {resultado.get('total_alertas', 0)} alertas detectadas",
    )


# ─── Report: Deduction Summary ───────────────────────────────────────

def generate_deduction_pdf(
    deducciones: list,
    total_ingresos: float,
    regimen: str = "612",
    anio: int = 2026,
    config: Optional[ConfiguracionPDF] = None,
) -> ResultadoPDF:
    """Generate PDF for deduction summary/optimization.

    Args:
        deducciones: List of dicts with deduction details:
            [{concepto, monto, tipo, subcategoria, deducible, fundamento}, ...]
        total_ingresos: Total annual income (for percentage context)
        regimen: "612" or "625"
        anio: Fiscal year
        config: PDF configuration

    Returns:
        ResultadoPDF with generated document.
    """
    if config is None:
        config = ConfiguracionPDF()

    styles = _build_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=config.tamano_pagina,
        topMargin=config.margen_superior,
        bottomMargin=config.margen_inferior,
        leftMargin=config.margen_izquierdo,
        rightMargin=config.margen_derecho,
    )

    elements = []

    elements.extend(_build_header(
        config,
        TipoReporte.DEDUCCIONES.value,
        f"Ejercicio {anio} — Régimen {regimen}",
        styles,
    ))

    # Summary metrics
    total_deducible = sum(d.get("monto", 0) for d in deducciones if d.get("deducible", True))
    total_no_deducible = sum(d.get("monto", 0) for d in deducciones if not d.get("deducible", True))
    pct_deduccion = (total_deducible / total_ingresos * 100) if total_ingresos > 0 else 0

    elements.append(Paragraph("Resumen", styles["heading"]))
    summary_items = [
        ("Ingresos totales", _fmt_currency(total_ingresos)),
        ("Total deducible", _fmt_currency(total_deducible)),
        ("Total no deducible", _fmt_currency(total_no_deducible)),
        ("Proporción deducción/ingreso", _fmt_pct(pct_deduccion)),
        ("Número de conceptos", str(len(deducciones))),
    ]
    elements.append(_make_kv_table(summary_items))

    # Detail table
    if deducciones:
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Detalle de Deducciones", styles["heading"]))

        headers = ["Concepto", "Monto", "Tipo", "Deducible"]
        rows = []
        for d in deducciones:
            deducible_label = "Sí" if d.get("deducible", True) else "No"
            rows.append([
                _truncate(d.get("concepto", ""), 35),
                _fmt_currency(d.get("monto", 0)),
                _truncate(d.get("tipo", ""), 20),
                deducible_label,
            ])

        col_widths = [200, 90, 120, 50]
        elements.append(_make_data_table(headers, rows, col_widths))

    # Category breakdown (pie chart data as table)
    categorias = {}
    for d in deducciones:
        cat = d.get("tipo", "Otros")
        categorias[cat] = categorias.get(cat, 0) + d.get("monto", 0)

    if categorias:
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Desglose por Categoría", styles["heading"]))
        headers = ["Categoría", "Monto", "% del Total"]
        rows = []
        total_cat = sum(categorias.values()) or 1
        for cat, monto in sorted(categorias.items(), key=lambda x: -x[1]):
            rows.append([
                cat,
                _fmt_currency(monto),
                _fmt_pct(monto / total_cat * 100),
            ])
        col_widths = [220, 120, 80]
        elements.append(_make_data_table(headers, rows, col_widths))

    # RESICO warning
    if regimen == "625":
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(
            "RESICO: Las deducciones operativas NO aplican. "
            "Este reporte es informativo para comparación de régimen.",
            styles["alert_warning"],
        ))

    # Footer
    _append_footer(elements, config, styles)

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    filename = f"deducciones_{regimen}_{anio}.pdf"
    return ResultadoPDF(
        contenido=pdf_bytes,
        nombre_archivo=filename,
        tipo_reporte=TipoReporte.DEDUCCIONES.value,
        paginas=_estimate_pages(len(pdf_bytes)),
        tamano_bytes=len(pdf_bytes),
        fecha_generacion=date.today().isoformat(),
        resumen=(
            f"Deducciones {anio} — {len(deducciones)} conceptos — "
            f"Total deducible: {_fmt_currency(total_deducible)} ({_fmt_pct(pct_deduccion)})"
        ),
    )


# ─── Unified Entry Point ─────────────────────────────────────────────

def generate_pdf_report(
    tipo: str,
    data: dict,
    config: Optional[ConfiguracionPDF] = None,
) -> ResultadoPDF:
    """Unified PDF generation entry point.

    Args:
        tipo: TipoReporte value (e.g., "Provisional Mensual", "Declaración Anual")
        data: Report data (dict). Structure depends on report type.
        config: PDF configuration

    Returns:
        ResultadoPDF with generated document.

    Raises:
        ValueError: If tipo is not recognized.
    """
    generators = {
        TipoReporte.PROVISIONAL_MENSUAL.value: generate_monthly_pdf,
        TipoReporte.DECLARACION_ANUAL.value: generate_annual_pdf,
        TipoReporte.DIOT.value: generate_diot_pdf,
        TipoReporte.SALUD_FISCAL.value: generate_fiscal_health_pdf,
    }

    gen = generators.get(tipo)
    if gen is None:
        valid = ", ".join(generators.keys())
        raise ValueError(
            f"Tipo de reporte no reconocido: '{tipo}'. "
            f"Tipos válidos: {valid}"
        )

    return gen(data, config)


# ─── Utility Helpers ─────────────────────────────────────────────────

def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


def _estimate_pages(pdf_size_bytes: int) -> int:
    """Rough page estimate from PDF size.

    A typical single-page reportlab PDF is ~3-6KB.
    Each additional page adds ~2-4KB.
    """
    if pdf_size_bytes < 8000:
        return 1
    return max(1, (pdf_size_bytes - 3000) // 4000 + 1)


def _append_alerts_notes(elements: list, resultado: dict, styles: dict):
    """Append alerts and notes sections to elements."""
    alertas = resultado.get("alertas", [])
    if alertas:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("Alertas", styles["heading"]))
        for a in alertas:
            if isinstance(a, dict):
                nivel = a.get("nivel", "")
                text = a.get("titulo", "") or a.get("mensaje", "")
                if nivel == "Urgente":
                    elements.append(Paragraph(f"• {text}", styles["alert_urgent"]))
                else:
                    elements.append(Paragraph(f"• {text}", styles["alert_warning"]))
            else:
                elements.append(Paragraph(f"• {a}", styles["alert_warning"]))

    notas = resultado.get("notas", [])
    if notas:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("Notas", styles["subheading"]))
        for n in notas:
            elements.append(Paragraph(f"• {n}", styles["body"]))


def _append_footer(elements: list, config: ConfiguracionPDF, styles: dict):
    """Append footer section."""
    elements.append(Spacer(1, 16))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_BORDER))
    elements.append(Paragraph(_build_footer_text(config), styles["footer"]))
