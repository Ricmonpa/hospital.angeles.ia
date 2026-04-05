"""OpenDoc - Fiscal Classifier (CFDI → Gemini Integration).

Takes structured CFDI data from cfdi_parser and uses Gemini to produce
intelligent fiscal analysis: deductibility per LISR, category classification,
RMF 2026 alerts, and actionable recommendations for the doctor.

This is the brain that turns raw XML parsing into fiscal intelligence.
"""

import json
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum

import google.generativeai as genai

from src.core.gemini_client import GeminiModel
from src.tools.cfdi_parser import (
    CFDI,
    REGIMEN_FISCAL,
    USO_CFDI,
    TIPO_COMPROBANTE,
    FORMA_PAGO,
    CLAVES_MEDICAS_SAT,
    is_medical_service,
    get_medical_service_name,
)


class Deducibilidad(str, Enum):
    """Deductibility classification per LISR."""
    DEDUCIBLE = "Deducible"
    NO_DEDUCIBLE = "No Deducible"
    PARCIALMENTE = "Parcialmente Deducible"
    REQUIERE_REVISION = "Requiere Revisión"


class CategoriaFiscal(str, Enum):
    """Fiscal category for expense classification."""
    GASTOS_MEDICOS = "Gastos Médicos"
    HONORARIOS = "Honorarios Profesionales"
    GASTOS_GENERALES = "Gastos en General"
    INVERSIONES = "Inversiones (Activo Fijo)"
    NOMINA = "Nómina"
    VIATICOS = "Viáticos"
    ARRENDAMIENTO = "Arrendamiento"
    SEGUROS = "Seguros y Fianzas"
    DONATIVOS = "Donativos"
    NO_DEDUCIBLE = "No Deducible"
    INGRESO = "Ingreso Acumulable"


@dataclass
class AlertaFiscal:
    """A fiscal alert or recommendation."""
    tipo: str  # "warning", "info", "action_required"
    mensaje: str
    referencia_legal: Optional[str] = None  # e.g., "Art. 27 LISR", "RMF 2026 3.13.x"


@dataclass
class ClasificacionFiscal:
    """Complete fiscal classification result from Gemini analysis."""
    # Core classification
    deducibilidad: str = ""
    categoria_fiscal: str = ""
    porcentaje_deducible: float = 100.0  # 0-100, relevant for partial deductions

    # LISR analysis
    fundamento_legal: str = ""  # e.g., "Art. 27 fracción III LISR"
    tipo_gasto: str = ""  # "Estrictamente indispensable", "Personal", etc.
    depreciacion_aplicable: bool = False
    tasa_depreciacion: Optional[float] = None  # Annual % if applicable

    # IVA analysis (new in Phase 5.5)
    iva_tratamiento: str = ""  # "Exento", "Gravado 16%", "Tasa 0%", "No aplica"
    iva_acreditable: bool = False  # Can doctor credit this IVA?
    retencion_isr_aplicable: bool = False  # Is 10% ISR retention applicable?

    # RMF 2026 considerations
    alertas: list = field(default_factory=list)

    # For the doctor
    resumen_doctor: str = ""  # Plain Spanish summary
    recomendaciones: list = field(default_factory=list)

    # Medical service context (new in Phase 5.5)
    es_servicio_medico: bool = False
    clave_medica_desc: str = ""  # Medical service name from catalog

    # Confidence
    confianza: float = 0.0  # 0.0-1.0

    # Raw Gemini response for audit trail
    raw_response: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def resumen_whatsapp(self) -> str:
        """Compact summary for WhatsApp delivery."""
        icon = "✅" if self.deducibilidad == "Deducible" else (
            "⚠️" if self.deducibilidad == "Parcialmente Deducible" else "❌"
        )
        lines = [
            f"{icon} {self.deducibilidad} — {self.categoria_fiscal}",
            f"📋 {self.fundamento_legal}" if self.fundamento_legal else "",
            f"💡 {self.resumen_doctor}",
        ]
        if self.alertas:
            lines.append("")
            for a in self.alertas:
                alert_icon = "🚨" if a["tipo"] == "warning" else "ℹ️"
                lines.append(f"{alert_icon} {a['mensaje']}")
        if self.recomendaciones:
            lines.append("")
            for r in self.recomendaciones:
                lines.append(f"→ {r}")
        return "\n".join(line for line in lines if line)


# ─── Prompt Engineering ────────────────────────────────────────────────

FISCAL_CLASSIFICATION_PROMPT = """Eres un experto fiscal mexicano especializado en el régimen de Personas Físicas con Actividades Empresariales y Profesionales (Régimen 612) y RESICO (Régimen 625), con enfoque particular en médicos.

DATOS DEL CFDI PARSEADO:
```json
{cfdi_json}
```

CONTEXTO DEL CONTRIBUYENTE:
- Profesión: Médico (persona física)
- Actividad principal: Consulta médica privada
- Régimen probable del receptor: {regimen_receptor}
{medical_context}

INSTRUCCIONES DE ANÁLISIS:
Analiza este CFDI y determina su clasificación fiscal. Responde ÚNICAMENTE con JSON válido:

```json
{{
  "deducibilidad": "Deducible | No Deducible | Parcialmente Deducible | Requiere Revisión",
  "categoria_fiscal": "Gastos Médicos | Honorarios Profesionales | Gastos en General | Inversiones (Activo Fijo) | Nómina | Viáticos | Arrendamiento | Seguros y Fianzas | Donativos | No Deducible | Ingreso Acumulable",
  "porcentaje_deducible": 100,
  "fundamento_legal": "Artículo y fracción de LISR aplicable",
  "tipo_gasto": "Estrictamente indispensable | Parcialmente indispensable | Personal | Inversión",
  "depreciacion_aplicable": false,
  "tasa_depreciacion": null,
  "iva_tratamiento": "Exento | Gravado 16% | Tasa 0% | No aplica",
  "iva_acreditable": false,
  "retencion_isr_aplicable": false,
  "alertas": [
    {{
      "tipo": "warning | info | action_required",
      "mensaje": "Descripción de la alerta",
      "referencia_legal": "Artículo o regla aplicable"
    }}
  ],
  "resumen_doctor": "Explicación breve y directa en español para el doctor",
  "recomendaciones": ["Recomendación 1", "Recomendación 2"],
  "confianza": 0.95
}}
```

REGLAS FISCALES A APLICAR:

1. **LISR Art. 27 — Deducciones autorizadas:**
   - Estrictamente indispensables para la actividad (consulta médica)
   - Pagados con transferencia, cheque nominativo, tarjeta de crédito/débito (>$2,000 MXN)
   - Con CFDI que cumpla requisitos fiscales

2. **LISR Art. 28 — No deducibles:**
   - Gastos personales (alimentación personal, ropa, entretenimiento)
   - Gastos sin comprobante fiscal válido
   - ISR propio, multas, recargos

3. **Inversiones (LISR Art. 31-38):**
   - Equipo médico: depreciación 10% anual
   - Equipo de cómputo: 30% anual
   - Automóviles: hasta $175,000 deducible, 25% anual
   - Mobiliario oficina: 10% anual

4. **RESICO (Art. 113-E a 113-J LISR):**
   - Régimen simplificado con tasas reducidas 1.0% - 2.5%
   - Ingresos tope: $3,500,000 anuales (superar = expulsión automática a Régimen 612)
   - NO permite deducciones operativas para cálculo de ISR
   - Facilidades RMF 2026 (regla 3.13.16): relevado de contabilidad electrónica y DIOT
   - Buzón Tributario OBLIGATORIO — falta de activación = expulsión de RESICO
   - Deducciones personales en declaración anual aplican SOLO sobre ingresos por salarios, NO sobre honorarios RESICO

5. **Forma de pago y deducibilidad:**
   - Efectivo: gastos del doctor >$2,000 MXN NO deducibles (Art. 27-III LISR)
   - Efectivo: paciente pierde deducción personal COMPLETA si paga en efectivo
   - Transferencia/tarjeta/cheque nominativo: deducción sin límite
   - Todas las deducciones personales exigen pago bancarizado

6. **IVA EN SERVICIOS MÉDICOS (Art. 15 LIVA):**
   - Servicios profesionales de medicina por persona física con título = EXENTOS de IVA
   - IVA pagado por el doctor en gastos operativos (renta, equipo, teléfono) = NO acreditable, se convierte en costo
   - EXCEPCIÓN — Medicina estética/cirugía plástica (Criterio 7/IVA/N):
     * Procedimientos de embellecimiento sin fin rehabilitatorio = GRAVADOS al 16%
     * Procedimientos reconstructivos/rehabilitatorios = EXENTOS
   - Medicamentos en hospital: se absorben en servicio hospitalario exento
   - Medicamentos en farmacia: tasa 0% IVA (enajenación de medicinas de patente)

7. **RETENCIÓN ISR POR PERSONAS MORALES (Art. 106 LISR):**
   - Cuando doctor factura a Persona Moral (hospital, clínica, aseguradora): retención 10% ISR obligatoria
   - Es pago anticipado de impuesto (acreditamiento en pago provisional mensual)
   - Ejemplo: Honorario $2,500 → Retención $250 → Neto $2,250

8. **CFDI 4.0 — REGLAS ESPECÍFICAS PARA MÉDICOS:**
   - Uso CFDI correcto: D01 (Honorarios médicos, dentales y gastos hospitalarios) para que sea deducible
   - Si paciente no sabe: usar P01 (Por definir) — CFDI mantiene validez, NO requiere cancelación
   - Clave de unidad: E48 (Unidad de servicio) obligatoria
   - ObjetoImp: "02" (Sí objeto de impuesto) con Factor "Exento" para servicios médicos

9. **ALERTAS RMF 2026:**
   - Controles reforzados para cancelación de CFDI (nueva ventana de 24 horas)
   - Tasa de recargos mensual 2.07% (incremento vs 2025)
   - ISR tarifas actualizadas por inflación para el ejercicio 2026
   - Buzón Tributario obligatorio — verificar habilitación
   - Pagos provisionales: día 17 del mes siguiente
   - Declaración anual: abril
   - Impuesto cedular estatal (modelo Guanajuato): 2% sobre utilidad, día 22 del mes siguiente

10. **TIPO DE COMPROBANTE:**
    - Ingreso (I): Es un ingreso para el emisor → clasificar como "Ingreso Acumulable" si el doctor es emisor
    - Egreso (E): Nota de crédito → verificar CFDI relacionado
    - Pago (P): Complemento de pago → verificar factura original
    - Traslado (T): Sin implicación fiscal directa

11. **CATEGORÍAS DE GASTOS DEDUCIBLES DEL CONSULTORIO (Régimen 612):**
    - Arrendamiento del local (100% deducible)
    - Servicios: luz, agua, internet, teléfono (100%; celular proporcional 70-80%)
    - Material de curación: guantes, jeringas, gasas, antisépticos, suturas (100%)
    - Medicamentos para aplicar en consultorio (100%, IVA tasa 0%)
    - Papelería: recetarios, expedientes, toner, impresiones (100%)
    - Limpieza y mantenimiento del local (100%)
    - Recolección RPBI por empresa autorizada (100%)
    - Publicidad y marketing médico (100%, con aviso COFEPRIS si aplica)
    - Software: facturación, EMR, contabilidad, suscripciones médicas (100%)
    - Lavandería: batas, sábanas, uniformes médicos (100%)
    - Seguros: responsabilidad civil profesional, inmueble, equipo (100%)
    - Educación: cursos CME, congresos, certificaciones, cuotas colegios (100%)
    - Comisiones bancarias y TPV (100%)
    - Permisos y licencias: uso de suelo, COFEPRIS, Protección Civil (100%)

12. **INVERSIONES — REGLAS DE DEPRECIACIÓN DETALLADAS:**
    - Equipo médico (ecógrafo, ECG, autoclave, desfibrilador, etc.): 10% anual — Art. 35 LISR
    - Instrumental quirúrgico reutilizable (sets de cirugía, cauterios): 10% anual — Art. 35 LISR
    - Equipo de cómputo (PC, laptop, tablet, impresora, servidor, UPS, red): 30% anual — Art. 35 LISR
    - Mobiliario (escritorio, sillas, vitrinas, mesa exploración, archiveros): 10% anual — Art. 34-VI LISR
    - Vehículo: 25% anual con TOPE MOI $175,000 — Art. 36-II LISR
    - Construcciones/adecuaciones: 5% anual — Art. 34-I LISR
    - Mejoras a inmueble arrendado: se deprecian en el plazo del contrato — Art. 36-VII LISR
    - El IVA NO acreditable se SUMA al MOI (incrementa la base depreciable)

13. **RESTAURANTES (Art. 28-XX LISR):**
    - 91.5% deducible SI se paga con tarjeta de crédito/débito a nombre del contribuyente
    - Propinas: NO deducibles
    - Debe ser gasto estrictamente indispensable (comida durante jornada laboral)
    - En bar o centro nocturno: NO deducible

14. **NÓMINA Y PERSONAL:**
    - Salarios, aguinaldo, vacaciones, prima vacacional, PTU: 100% deducible — Art. 27-V LISR
    - Cuotas patronales IMSS, INFONAVIT, SAR: 100% — Art. 27-V LISR
    - Previsión social (vales, fondo ahorro, seguro vida): 100% si generalizada — Art. 27-XI LISR
    - Requisito: pago SIEMPRE por transferencia bancaria

15. **VEHÍCULO — ESTRATEGIA:**
    - Tope MOI $175,000 — excedente NUNCA se deduce
    - Si auto cuesta más de $350,000: evaluar arrendamiento puro ($200/día + IVA = ~$73,000/año)
    - Gasolina y mantenimiento: proporcional al uso profesional (documentar con bitácora)
    - Seguro, verificación, tenencia, casetas: deducibles con CFDI

IMPORTANTE:
- Si el doctor es el EMISOR, este CFDI representa un INGRESO, no un gasto
- Si el doctor es el RECEPTOR, este CFDI representa un GASTO potencialmente deducible
- Analiza la ClaveProdServ para determinar la naturaleza del gasto/servicio
- Verifica que la forma de pago sea compatible con deducibilidad
- Determina el tratamiento de IVA correcto (exento, gravado 16%, tasa 0%)
- Indica si aplica retención de ISR (10% cuando receptor es Persona Moral)
- Para inversiones, indica tasa de depreciación y si conviene deducción inmediata
- Para gastos >$2,000 en efectivo, marcar como NO DEDUCIBLE
- Para restaurantes con tarjeta, aplicar 91.5%
"""


def _build_cfdi_summary_for_gemini(cfdi: CFDI) -> dict:
    """Build a clean JSON-serializable summary of the CFDI for the prompt."""
    summary = {
        "version": cfdi.version,
        "tipo_comprobante": f"{cfdi.tipo_comprobante} ({cfdi.tipo_comprobante_desc})",
        "fecha": cfdi.fecha,
        "folio": cfdi.folio,
        "emisor": {
            "rfc": cfdi.emisor_rfc,
            "nombre": cfdi.emisor_nombre,
            "regimen_fiscal": f"{cfdi.emisor_regimen} ({cfdi.emisor_regimen_desc})",
        },
        "receptor": {
            "rfc": cfdi.receptor_rfc,
            "nombre": cfdi.receptor_nombre,
            "uso_cfdi": f"{cfdi.receptor_uso_cfdi} ({cfdi.receptor_uso_cfdi_desc})",
        },
        "montos": {
            "subtotal": cfdi.subtotal,
            "descuento": cfdi.descuento,
            "iva_trasladado": cfdi.iva_trasladado,
            "iva_retenido": cfdi.iva_retenido,
            "isr_retenido": cfdi.isr_retenido,
            "total": cfdi.total,
            "neto_a_cobrar": cfdi.neto_a_cobrar,
            "exento_iva": cfdi.exento_iva,
        },
        "pago": {
            "forma_pago": f"{cfdi.forma_pago} ({cfdi.forma_pago_desc})",
            "metodo_pago": cfdi.metodo_pago,
            "moneda": cfdi.moneda,
        },
        "conceptos": [],
        "uuid": cfdi.timbre.uuid if cfdi.timbre else "N/A",
    }

    for c in cfdi.conceptos:
        summary["conceptos"].append({
            "clave_prod_serv": c.clave_prod_serv,
            "descripcion": c.descripcion,
            "cantidad": c.cantidad,
            "importe": c.importe,
            "iva_tasa": c.iva_tasa,
            "exento": c.exento,
            "isr_retencion": c.isr_retencion,
        })

    return summary


def _parse_classification_response(text: str) -> ClasificacionFiscal:
    """Parse Gemini's JSON response into a ClasificacionFiscal object."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.strip()

    data = json.loads(cleaned)

    # Build alertas list
    alertas_raw = data.get("alertas", [])
    alertas = []
    for a in alertas_raw:
        if isinstance(a, dict):
            alertas.append(a)

    return ClasificacionFiscal(
        deducibilidad=data.get("deducibilidad", "Requiere Revisión"),
        categoria_fiscal=data.get("categoria_fiscal", ""),
        porcentaje_deducible=float(data.get("porcentaje_deducible", 100)),
        fundamento_legal=data.get("fundamento_legal", ""),
        tipo_gasto=data.get("tipo_gasto", ""),
        depreciacion_aplicable=data.get("depreciacion_aplicable", False),
        tasa_depreciacion=data.get("tasa_depreciacion"),
        # IVA / ISR fields (Phase 5.5)
        iva_tratamiento=data.get("iva_tratamiento", ""),
        iva_acreditable=data.get("iva_acreditable", False),
        retencion_isr_aplicable=data.get("retencion_isr_aplicable", False),
        alertas=alertas,
        resumen_doctor=data.get("resumen_doctor", ""),
        recomendaciones=data.get("recomendaciones", []),
        confianza=float(data.get("confianza", 0.0)),
        raw_response=text,
    )


# ─── Rule-based pre-classification (fast, no API call) ─────────────────

def _preclassify_tipo_comprobante(cfdi: CFDI, doctor_rfc: Optional[str] = None) -> dict:
    """Quick rule-based classification based on comprobante type."""
    result = {
        "es_ingreso": False,
        "es_egreso": False,
        "skip_gemini": False,
        "clasificacion_rapida": None,
    }

    tipo = cfdi.tipo_comprobante

    if tipo == "N":  # Nómina
        result["clasificacion_rapida"] = ClasificacionFiscal(
            deducibilidad=Deducibilidad.DEDUCIBLE.value,
            categoria_fiscal=CategoriaFiscal.NOMINA.value,
            porcentaje_deducible=100.0,
            fundamento_legal="Art. 27 fracción V LISR — Remuneraciones al personal",
            tipo_gasto="Estrictamente indispensable",
            resumen_doctor="Nómina del personal. Deducible al 100% mientras se cumplan obligaciones patronales (IMSS, INFONAVIT, ISR retenido).",
            recomendaciones=[
                "Verificar que las retenciones de ISR estén correctamente timbradas",
                "Asegurar pago de cuotas IMSS del periodo",
            ],
            confianza=0.99,
        )
        result["skip_gemini"] = True

    elif tipo == "T":  # Traslado
        result["clasificacion_rapida"] = ClasificacionFiscal(
            deducibilidad=Deducibilidad.NO_DEDUCIBLE.value,
            categoria_fiscal="Traslado",
            porcentaje_deducible=0.0,
            fundamento_legal="Sin implicación fiscal — Comprobante de traslado de mercancías",
            tipo_gasto="Sin efecto fiscal",
            resumen_doctor="Comprobante de traslado. No tiene efecto fiscal, solo ampara el movimiento de mercancías.",
            confianza=0.99,
        )
        result["skip_gemini"] = True

    # Detect if doctor is the emisor (this is an INCOME, not expense)
    if doctor_rfc and cfdi.emisor_rfc.upper() == doctor_rfc.upper():
        result["es_ingreso"] = True

    # Detect if this is a Nota de Crédito
    if tipo == "E":
        result["es_egreso"] = True

    return result


def _preclassify_medical_service(cfdi: CFDI, doctor_rfc: Optional[str] = None) -> dict:
    """Analyze CFDI for medical service context.

    Detects if the CFDI involves medical services based on SAT product codes
    and provides IVA/ISR treatment hints.

    Returns:
        dict with keys: es_servicio_medico, clave_medica_desc, iva_hint,
        retencion_hint, medical_context_for_prompt
    """
    result = {
        "es_servicio_medico": False,
        "clave_medica_desc": "",
        "iva_hint": "",
        "retencion_hint": "",
        "medical_context_for_prompt": "",
    }

    # Check if any concepto has a medical SAT code
    medical_codes_found = []
    for c in cfdi.conceptos:
        if is_medical_service(c.clave_prod_serv):
            desc = get_medical_service_name(c.clave_prod_serv)
            medical_codes_found.append((c.clave_prod_serv, desc or c.descripcion))

    if medical_codes_found:
        result["es_servicio_medico"] = True
        result["clave_medica_desc"] = medical_codes_found[0][1]

        # Build context for prompt
        codes_str = ", ".join(f"{code} ({desc})" for code, desc in medical_codes_found)
        result["medical_context_for_prompt"] = f"- Claves médicas SAT detectadas: {codes_str}"

    # IVA treatment hint
    if cfdi.exento_iva:
        result["iva_hint"] = "Exento"
        if result["es_servicio_medico"]:
            result["medical_context_for_prompt"] += "\n- IVA: Exento (Art. 15 LIVA — servicio médico profesional)"
    elif cfdi.iva_trasladado and cfdi.iva_trasladado > 0:
        result["iva_hint"] = "Gravado 16%"
        if result["es_servicio_medico"]:
            result["medical_context_for_prompt"] += "\n- IVA: Gravado 16% — POSIBLE procedimiento estético (Criterio 7/IVA/N)"

    # ISR retention hint (10% when billing Persona Moral)
    doctor_is_emisor = doctor_rfc and cfdi.emisor_rfc.upper() == doctor_rfc.upper()
    if doctor_is_emisor and cfdi.isr_retenido and cfdi.isr_retenido > 0:
        result["retencion_hint"] = "Retención ISR 10% aplicada"
        result["medical_context_for_prompt"] += "\n- Retención ISR 10% detectada (Art. 106 LISR — facturación a Persona Moral)"

    # Check if receptor is Persona Moral (RFC length 12 = PM, 13 = PF)
    if doctor_is_emisor and len(cfdi.receptor_rfc) == 12:
        result["retencion_hint"] = result["retencion_hint"] or "Retención ISR 10% esperada"
        if "Retención ISR" not in result["medical_context_for_prompt"]:
            result["medical_context_for_prompt"] += "\n- Receptor es Persona Moral (RFC 12 dígitos) — retención ISR 10% obligatoria (Art. 106 LISR)"

    return result


def _preclassify_forma_pago(cfdi: CFDI) -> list[AlertaFiscal]:
    """Generate alerts based on payment method."""
    alertas = []

    if cfdi.forma_pago == "01":  # Efectivo
        if cfdi.total > 2000:
            alertas.append(AlertaFiscal(
                tipo="warning",
                mensaje=f"Pago en efectivo por ${cfdi.total:,.2f}. Gastos >$2,000 en efectivo NO son deducibles (Art. 27-III LISR).",
                referencia_legal="Art. 27 fracción III LISR",
            ))
        else:
            alertas.append(AlertaFiscal(
                tipo="info",
                mensaje=f"Pago en efectivo por ${cfdi.total:,.2f}. Deducible por ser menor a $2,000.",
                referencia_legal="Art. 27 fracción III LISR",
            ))

    if cfdi.metodo_pago == "PPD" and not cfdi.timbre:
        alertas.append(AlertaFiscal(
            tipo="action_required",
            mensaje="Método PPD (Pago en Parcialidades o Diferido). Se requiere complemento de pago para deducir.",
            referencia_legal="Art. 29-A CFF / RMF 2026 2.7.1.32",
        ))

    return alertas


# ─── Main classification function ──────────────────────────────────────

def classify_cfdi(
    cfdi: CFDI,
    doctor_rfc: Optional[str] = None,
    model: GeminiModel = GeminiModel.FLASH,
    use_gemini: bool = True,
) -> ClasificacionFiscal:
    """Classify a CFDI for fiscal deductibility using rule-based + Gemini AI.

    This is the main integration point: CFDI parser output → fiscal intelligence.

    Pipeline:
    1. Rule-based pre-classification (instant, no API)
    2. Payment method validation
    3. Gemini deep analysis (if needed)
    4. Merge results

    Args:
        cfdi: Parsed CFDI object from cfdi_parser.
        doctor_rfc: The doctor's RFC (to detect income vs expense).
        model: Gemini model to use (Flash for routine, Pro for complex).
        use_gemini: If False, skip Gemini and return only rule-based result.

    Returns:
        ClasificacionFiscal with full analysis.
    """
    # Step 1: Rule-based pre-classification
    pre = _preclassify_tipo_comprobante(cfdi, doctor_rfc)

    # If rule-based is sufficient (nómina, traslado), return immediately
    if pre["skip_gemini"] or not use_gemini:
        result = pre["clasificacion_rapida"] or ClasificacionFiscal(
            deducibilidad=Deducibilidad.REQUIERE_REVISION.value,
            resumen_doctor="Clasificación automática no disponible. Se recomienda revisión manual.",
            confianza=0.5,
        )
        # Still add payment alerts
        pago_alertas = _preclassify_forma_pago(cfdi)
        for a in pago_alertas:
            result.alertas.append(asdict(a))
        # Still add medical context (Phase 5.5)
        medical_pre = _preclassify_medical_service(cfdi, doctor_rfc)
        if medical_pre["es_servicio_medico"]:
            result.es_servicio_medico = True
            result.clave_medica_desc = medical_pre["clave_medica_desc"]
        if medical_pre["iva_hint"]:
            result.iva_tratamiento = medical_pre["iva_hint"]
        if medical_pre["retencion_hint"]:
            result.retencion_isr_aplicable = True
        return result

    # Step 2: Payment method alerts (will be merged into final result)
    pago_alertas = _preclassify_forma_pago(cfdi)

    # Step 2.5: Medical service pre-classification
    medical_pre = _preclassify_medical_service(cfdi, doctor_rfc)

    # Step 3: Build prompt for Gemini
    cfdi_summary = _build_cfdi_summary_for_gemini(cfdi)
    cfdi_json = json.dumps(cfdi_summary, ensure_ascii=False, indent=2)

    regimen_receptor = ""
    if cfdi.receptor_regimen:
        regimen_receptor = REGIMEN_FISCAL.get(cfdi.receptor_regimen, cfdi.receptor_regimen)
    elif doctor_rfc and cfdi.receptor_rfc.upper() == doctor_rfc.upper():
        regimen_receptor = "Médico receptor — probablemente Régimen 612 o 625"

    # Build medical context string for prompt
    medical_context = ""
    if medical_pre["medical_context_for_prompt"]:
        medical_context = "\n" + medical_pre["medical_context_for_prompt"]

    prompt = FISCAL_CLASSIFICATION_PROMPT.format(
        cfdi_json=cfdi_json,
        regimen_receptor=regimen_receptor or "No especificado",
        medical_context=medical_context,
    )

    # Add income context if doctor is emisor
    if pre["es_ingreso"]:
        prompt += "\n\nNOTA IMPORTANTE: El doctor es el EMISOR de este CFDI. Esto es un INGRESO, no un gasto. Clasifica como 'Ingreso Acumulable'."

    if pre["es_egreso"]:
        prompt += "\n\nNOTA IMPORTANTE: Este es un comprobante tipo Egreso (nota de crédito). Verificar el CFDI de ingreso relacionado."

    # Step 4: Call Gemini
    fiscal_model = genai.GenerativeModel(
        model_name=model.value,
        generation_config=genai.GenerationConfig(
            temperature=0.1,  # Maximum precision for fiscal analysis
            max_output_tokens=2048,
        ),
    )

    response = fiscal_model.generate_content(prompt)

    # Step 5: Parse response
    try:
        result = _parse_classification_response(response.text)
    except (json.JSONDecodeError, KeyError) as e:
        # If Gemini returns bad JSON, return a safe default
        result = ClasificacionFiscal(
            deducibilidad=Deducibilidad.REQUIERE_REVISION.value,
            resumen_doctor=f"Error al procesar análisis fiscal. Respuesta de IA: {response.text[:200]}",
            confianza=0.0,
            raw_response=response.text,
        )

    # Step 6: Merge payment alerts into result
    for a in pago_alertas:
        result.alertas.append(asdict(a))

    # Step 7: Merge medical service context into result
    if medical_pre["es_servicio_medico"]:
        result.es_servicio_medico = True
        result.clave_medica_desc = medical_pre["clave_medica_desc"]
    if medical_pre["iva_hint"] and not result.iva_tratamiento:
        result.iva_tratamiento = medical_pre["iva_hint"]
    if medical_pre["retencion_hint"] and not result.retencion_isr_aplicable:
        result.retencion_isr_aplicable = "esperada" in medical_pre["retencion_hint"].lower() or \
                                          "aplicada" in medical_pre["retencion_hint"].lower()

    return result


def classify_cfdi_offline(
    cfdi: CFDI,
    doctor_rfc: Optional[str] = None,
) -> ClasificacionFiscal:
    """Classify a CFDI using ONLY rule-based logic (no API call).

    Useful for:
    - Batch processing when Gemini quota is limited
    - Quick pre-screening before detailed analysis
    - Offline mode

    Args:
        cfdi: Parsed CFDI object.
        doctor_rfc: The doctor's RFC.

    Returns:
        ClasificacionFiscal with rule-based analysis only.
    """
    return classify_cfdi(cfdi, doctor_rfc=doctor_rfc, use_gemini=False)


def full_cfdi_analysis(
    cfdi: CFDI,
    doctor_rfc: Optional[str] = None,
    model: GeminiModel = GeminiModel.FLASH,
) -> str:
    """Complete CFDI analysis: parse summary + fiscal classification.

    Returns a formatted string ready for WhatsApp or dashboard display.

    Args:
        cfdi: Parsed CFDI object.
        doctor_rfc: The doctor's RFC.
        model: Gemini model to use.

    Returns:
        Formatted analysis string in Spanish.
    """
    clasificacion = classify_cfdi(cfdi, doctor_rfc=doctor_rfc, model=model)

    lines = [
        cfdi.fiscal_summary(),
        "",
        "━━━ ANÁLISIS FISCAL ━━━",
        "",
        clasificacion.resumen_whatsapp(),
    ]

    if clasificacion.confianza < 0.7:
        lines.append("")
        lines.append("⚕️ Confianza baja. Se recomienda validación con contador.")

    return "\n".join(lines)
