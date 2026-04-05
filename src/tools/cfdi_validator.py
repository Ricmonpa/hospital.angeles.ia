"""OpenDoc - CFDI Validator.

Validates CFDIs for common errors, missing data, and fiscal compliance issues.
Catches problems BEFORE they become SAT rejections or audit findings.

This is the doctor's "quality control" for incoming and outgoing invoices.

Validates:
- Structural completeness (required fields present)
- Fiscal consistency (régimen vs uso CFDI, payment method rules)
- Deductibility prerequisites (payment method, CFDI required fields)
- SAT catalog compliance (valid codes)
- Medical-specific rules (Art. 15 LIVA, medical service codes)

Based on: Anexo 20 CFDI 4.0, CFF Art. 29/29-A, LISR Art. 27, RMF 2026.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────────

class SeveridadError(str, Enum):
    CRITICO = "Crítico"         # CFDI is invalid / non-deductible
    ADVERTENCIA = "Advertencia"  # May cause issues
    INFO = "Información"         # Best practice suggestion


class TipoValidacion(str, Enum):
    ESTRUCTURA = "Estructura"
    FISCAL = "Fiscal"
    DEDUCIBILIDAD = "Deducibilidad"
    MEDICO = "Médico"
    PAGO = "Pago"


# ─── Data Classes ─────────────────────────────────────────────────────

@dataclass
class ErrorCFDI:
    """A single validation finding."""
    codigo: str                   # Error code (e.g., "VAL-001")
    mensaje: str                  # Human-readable message
    severidad: str                # SeveridadError value
    tipo: str                     # TipoValidacion value
    campo: str = ""               # Field with the issue
    valor_actual: str = ""        # Current value
    valor_esperado: str = ""      # Expected value
    fundamento: str = ""          # Legal basis
    recomendacion: str = ""       # How to fix


@dataclass
class ResultadoValidacion:
    """Complete validation result for a CFDI."""
    es_valido: bool = True
    total_errores: int = 0
    total_advertencias: int = 0
    total_info: int = 0
    errores: list = field(default_factory=list)
    score: int = 100               # 0-100 quality score

    def to_dict(self) -> dict:
        return {
            "es_valido": self.es_valido,
            "total_errores": self.total_errores,
            "total_advertencias": self.total_advertencias,
            "total_info": self.total_info,
            "score": self.score,
            "errores": [
                {
                    "codigo": e.codigo,
                    "mensaje": e.mensaje,
                    "severidad": e.severidad,
                    "tipo": e.tipo,
                    "campo": e.campo,
                    "recomendacion": e.recomendacion,
                }
                for e in self.errores
            ],
        }

    def resumen_whatsapp(self) -> str:
        """WhatsApp-friendly validation summary."""
        icon = "✅" if self.es_valido and self.total_errores == 0 else "❌"
        lines = [
            f"{icon} VALIDACIÓN CFDI — Score: {self.score}/100",
        ]

        if self.total_errores > 0:
            lines.append(f"🔴 {self.total_errores} errores críticos")
        if self.total_advertencias > 0:
            lines.append(f"🟡 {self.total_advertencias} advertencias")
        if self.total_info > 0:
            lines.append(f"ℹ️ {self.total_info} sugerencias")

        if not self.errores:
            lines.append("Sin problemas detectados.")
            return "\n".join(lines)

        lines.append("")
        for e in self.errores:
            sev = "🔴" if e.severidad == SeveridadError.CRITICO.value else "🟡" if e.severidad == SeveridadError.ADVERTENCIA.value else "ℹ️"
            lines.append(f"{sev} [{e.codigo}] {e.mensaje}")
            if e.recomendacion:
                lines.append(f"   → {e.recomendacion}")

        return "\n".join(lines)


# ─── Valid SAT Catalog Values ─────────────────────────────────────────

FORMAS_PAGO_VALIDAS = {
    "01", "02", "03", "04", "05", "06", "08", "12",
    "13", "14", "15", "17", "23", "24", "25", "26",
    "27", "28", "29", "30", "31", "99",
}

METODOS_PAGO_VALIDOS = {"PUE", "PPD"}

TIPOS_COMPROBANTE_VALIDOS = {"I", "E", "P", "N", "T"}

USOS_CFDI_PERSONAS_FISICAS = {
    "G01", "G02", "G03", "I01", "I02", "I03", "I04",
    "I05", "I06", "I07", "I08", "D01", "D02", "D03",
    "D04", "D05", "D06", "D07", "D08", "D09", "D10",
    "S01", "CP01",
}

USOS_CFDI_MEDICO_COMUNES = {
    "G03",  # Gastos en general (most common for doctor expenses)
    "D01",  # Honorarios médicos (personal deduction)
    "I08",  # Otra maquinaria y equipo
    "I01",  # Construcciones
}

REGIMENES_PERSONA_FISICA = {"605", "606", "608", "612", "614", "621", "625", "626"}
REGIMENES_PERSONA_MORAL = {"601", "603", "620", "622", "623", "624", "626"}


# ─── Core Validation Functions ────────────────────────────────────────

def _validate_structure(cfdi_data: dict) -> list[ErrorCFDI]:
    """Validate CFDI structural completeness."""
    errors = []

    # Required fields
    required = [
        ("version", "Versión"),
        ("emisor_rfc", "RFC Emisor"),
        ("receptor_rfc", "RFC Receptor"),
        ("fecha", "Fecha"),
        ("total", "Total"),
        ("tipo_comprobante", "Tipo de Comprobante"),
    ]

    for field_name, label in required:
        value = cfdi_data.get(field_name)
        if not value and value != 0:
            errors.append(ErrorCFDI(
                codigo="EST-001",
                mensaje=f"Campo obligatorio faltante: {label}",
                severidad=SeveridadError.CRITICO.value,
                tipo=TipoValidacion.ESTRUCTURA.value,
                campo=field_name,
                fundamento="CFF Art. 29-A",
                recomendacion=f"Solicitar CFDI con {label} correcto.",
            ))

    # UUID (Timbre Fiscal)
    timbre = cfdi_data.get("timbre", {})
    if isinstance(timbre, dict):
        uuid = timbre.get("uuid", "")
    else:
        uuid = getattr(timbre, "uuid", "") if timbre else ""

    if not uuid:
        errors.append(ErrorCFDI(
            codigo="EST-002",
            mensaje="CFDI sin Timbre Fiscal Digital (UUID)",
            severidad=SeveridadError.CRITICO.value,
            tipo=TipoValidacion.ESTRUCTURA.value,
            campo="timbre.uuid",
            recomendacion="CFDI no es válido sin timbre. Solicitar retimbrado.",
        ))

    # Version check
    version = cfdi_data.get("version", "")
    if version and version not in ("3.3", "4.0"):
        errors.append(ErrorCFDI(
            codigo="EST-003",
            mensaje=f"Versión CFDI no reconocida: {version}",
            severidad=SeveridadError.ADVERTENCIA.value,
            tipo=TipoValidacion.ESTRUCTURA.value,
            campo="version",
            valor_actual=version,
            valor_esperado="3.3 o 4.0",
        ))

    # RFC format validation
    rfc_emisor = cfdi_data.get("emisor_rfc", "")
    if rfc_emisor and len(rfc_emisor) not in (12, 13):
        errors.append(ErrorCFDI(
            codigo="EST-004",
            mensaje=f"RFC emisor con longitud inválida: {len(rfc_emisor)} caracteres",
            severidad=SeveridadError.CRITICO.value,
            tipo=TipoValidacion.ESTRUCTURA.value,
            campo="emisor_rfc",
            valor_actual=rfc_emisor,
            valor_esperado="12 (PM) o 13 (PF) caracteres",
        ))

    # Conceptos present
    conceptos = cfdi_data.get("conceptos", [])
    if not conceptos:
        errors.append(ErrorCFDI(
            codigo="EST-005",
            mensaje="CFDI sin conceptos (líneas de detalle)",
            severidad=SeveridadError.CRITICO.value,
            tipo=TipoValidacion.ESTRUCTURA.value,
            campo="conceptos",
            recomendacion="Toda factura debe tener al menos un concepto.",
        ))

    return errors


def _validate_fiscal(cfdi_data: dict) -> list[ErrorCFDI]:
    """Validate fiscal consistency."""
    errors = []

    tipo = cfdi_data.get("tipo_comprobante", "")
    forma_pago = cfdi_data.get("forma_pago")
    metodo_pago = cfdi_data.get("metodo_pago")

    # Tipo de comprobante
    if tipo and tipo not in TIPOS_COMPROBANTE_VALIDOS:
        errors.append(ErrorCFDI(
            codigo="FIS-001",
            mensaje=f"Tipo de comprobante inválido: {tipo}",
            severidad=SeveridadError.CRITICO.value,
            tipo=TipoValidacion.FISCAL.value,
            campo="tipo_comprobante",
            valor_actual=tipo,
            valor_esperado="I (Ingreso), E (Egreso), P (Pago), N (Nómina), T (Traslado)",
        ))

    # Forma de pago
    if forma_pago and forma_pago not in FORMAS_PAGO_VALIDAS:
        errors.append(ErrorCFDI(
            codigo="FIS-002",
            mensaje=f"Forma de pago no reconocida: {forma_pago}",
            severidad=SeveridadError.ADVERTENCIA.value,
            tipo=TipoValidacion.FISCAL.value,
            campo="forma_pago",
            valor_actual=forma_pago,
        ))

    # Método de pago
    if metodo_pago and metodo_pago not in METODOS_PAGO_VALIDOS:
        errors.append(ErrorCFDI(
            codigo="FIS-003",
            mensaje=f"Método de pago inválido: {metodo_pago}",
            severidad=SeveridadError.CRITICO.value,
            tipo=TipoValidacion.FISCAL.value,
            campo="metodo_pago",
            valor_actual=metodo_pago,
            valor_esperado="PUE (Pago en Una sola Exhibición) o PPD (Pago en Parcialidades o Diferido)",
        ))

    # PPD requires forma_pago 99
    if metodo_pago == "PPD" and forma_pago and forma_pago != "99":
        errors.append(ErrorCFDI(
            codigo="FIS-004",
            mensaje=f"PPD requiere forma de pago '99' (Por definir), tiene '{forma_pago}'",
            severidad=SeveridadError.ADVERTENCIA.value,
            tipo=TipoValidacion.FISCAL.value,
            campo="forma_pago",
            recomendacion="Si el pago es diferido, la forma de pago debe ser '99' y se aclara con Complemento de Pago.",
        ))

    # PUE should NOT be "99"
    if metodo_pago == "PUE" and forma_pago == "99":
        errors.append(ErrorCFDI(
            codigo="FIS-005",
            mensaje="PUE con forma de pago '99' (Por definir). Debe especificar forma real.",
            severidad=SeveridadError.ADVERTENCIA.value,
            tipo=TipoValidacion.FISCAL.value,
            campo="forma_pago",
            recomendacion="Especificar: 03 (Transferencia), 04 (Tarjeta crédito), 28 (Tarjeta débito), etc.",
        ))

    # Uso CFDI
    uso = cfdi_data.get("receptor_uso_cfdi", "")
    if uso and uso not in USOS_CFDI_PERSONAS_FISICAS and uso not in {"P01", "CP01", "CN01", "S01"}:
        errors.append(ErrorCFDI(
            codigo="FIS-006",
            mensaje=f"Uso de CFDI no reconocido: {uso}",
            severidad=SeveridadError.ADVERTENCIA.value,
            tipo=TipoValidacion.FISCAL.value,
            campo="receptor_uso_cfdi",
            valor_actual=uso,
        ))

    # Amount consistency
    subtotal = cfdi_data.get("subtotal", 0) or 0
    total = cfdi_data.get("total", 0) or 0
    iva = cfdi_data.get("iva_trasladado", 0) or 0
    descuento = cfdi_data.get("descuento", 0) or 0
    isr_ret = cfdi_data.get("isr_retenido", 0) or 0
    iva_ret = cfdi_data.get("iva_retenido", 0) or 0

    expected_total = subtotal - descuento + iva - isr_ret - iva_ret
    if subtotal > 0 and abs(total - expected_total) > 1.0:
        errors.append(ErrorCFDI(
            codigo="FIS-007",
            mensaje=f"Total (${total:,.2f}) no cuadra: subtotal-desc+IVA-retenciones = ${expected_total:,.2f}",
            severidad=SeveridadError.ADVERTENCIA.value,
            tipo=TipoValidacion.FISCAL.value,
            campo="total",
            valor_actual=f"${total:,.2f}",
            valor_esperado=f"${expected_total:,.2f}",
            recomendacion="Verificar cálculo de impuestos o presencia de impuestos locales.",
        ))

    return errors


def _validate_deducibility(cfdi_data: dict, regimen_doctor: str = "612") -> list[ErrorCFDI]:
    """Validate deductibility prerequisites."""
    errors = []

    forma_pago = cfdi_data.get("forma_pago")
    total = cfdi_data.get("total", 0) or 0
    metodo_pago = cfdi_data.get("metodo_pago")

    # Cash over $2,000
    if forma_pago == "01" and total > 2000:
        errors.append(ErrorCFDI(
            codigo="DED-001",
            mensaje=f"Pago en efectivo de ${total:,.2f} (>$2,000). NO DEDUCIBLE.",
            severidad=SeveridadError.CRITICO.value,
            tipo=TipoValidacion.DEDUCIBILIDAD.value,
            campo="forma_pago",
            valor_actual="01 (Efectivo)",
            fundamento="Art. 27 fracción III LISR",
            recomendacion="Pagar por transferencia, tarjeta o cheque nominativo.",
        ))

    # Forma de pago "99" without complemento (if PUE)
    if forma_pago == "99" and metodo_pago == "PUE":
        errors.append(ErrorCFDI(
            codigo="DED-002",
            mensaje="Forma de pago '99' en factura PUE. No se puede comprobar deducibilidad del pago.",
            severidad=SeveridadError.ADVERTENCIA.value,
            tipo=TipoValidacion.DEDUCIBILIDAD.value,
            campo="forma_pago",
            recomendacion="Solicitar corrección con forma de pago real (03, 04, 28).",
        ))

    # PPD without complemento de pago (can't deduct until paid)
    if metodo_pago == "PPD":
        errors.append(ErrorCFDI(
            codigo="DED-003",
            mensaje="Factura con pago diferido (PPD). NO deducible hasta recibir Complemento de Pago.",
            severidad=SeveridadError.ADVERTENCIA.value,
            tipo=TipoValidacion.DEDUCIBILIDAD.value,
            campo="metodo_pago",
            fundamento="Art. 27 LISR — deducción al momento del pago efectivo",
            recomendacion="Solicitar Complemento de Pago (REP) al proveedor cuando pagues.",
        ))

    # RESICO warning
    if regimen_doctor == "625":
        errors.append(ErrorCFDI(
            codigo="DED-004",
            mensaje="RESICO: Este gasto NO es deducible operativamente.",
            severidad=SeveridadError.INFO.value,
            tipo=TipoValidacion.DEDUCIBILIDAD.value,
            recomendacion="RESICO no permite deducciones operativas. Solo aplican deducciones personales.",
        ))

    # Uso CFDI should match deduction intent
    uso = cfdi_data.get("receptor_uso_cfdi", "")
    if uso == "S01":
        errors.append(ErrorCFDI(
            codigo="DED-005",
            mensaje="Uso CFDI: 'S01' (Sin efectos fiscales). Esta factura NO es deducible.",
            severidad=SeveridadError.CRITICO.value,
            tipo=TipoValidacion.DEDUCIBILIDAD.value,
            campo="receptor_uso_cfdi",
            recomendacion="Si quieres deducir, solicitar CFDI con uso G03 (Gastos en general).",
        ))

    return errors


def _validate_medical(cfdi_data: dict) -> list[ErrorCFDI]:
    """Validate medical-specific rules."""
    errors = []

    # Check if this looks like medical income (emitted by the doctor)
    emisor_regimen = cfdi_data.get("emisor_regimen", "")

    # For income CFDIs (type I) from a doctor
    tipo = cfdi_data.get("tipo_comprobante", "")
    if tipo == "I" and emisor_regimen in ("612", "625"):
        # Medical services should be IVA exempt
        iva = cfdi_data.get("iva_trasladado", 0) or 0
        subtotal = cfdi_data.get("subtotal", 0) or 0
        exento = cfdi_data.get("exento_iva", False)

        # Check conceptos for medical service codes
        conceptos = cfdi_data.get("conceptos", [])
        has_medical_code = False
        for c in conceptos:
            clave = ""
            if isinstance(c, dict):
                clave = c.get("clave_prod_serv", "")
            else:
                clave = getattr(c, "clave_prod_serv", "")
            if str(clave).startswith(("8510", "8511", "8512", "8513")):
                has_medical_code = True
                break

        if has_medical_code and iva > 0 and not exento:
            errors.append(ErrorCFDI(
                codigo="MED-001",
                mensaje=f"Servicios médicos con IVA trasladado (${iva:,.2f}). Deben ser EXENTOS.",
                severidad=SeveridadError.CRITICO.value,
                tipo=TipoValidacion.MEDICO.value,
                campo="iva_trasladado",
                fundamento="Art. 15 fracción XIV LIVA",
                recomendacion="Corregir factura: servicios médicos son exentos de IVA.",
            ))

    # ISR retention check (billing to Personas Morales)
    receptor_rfc = cfdi_data.get("receptor_rfc", "")
    isr_ret = cfdi_data.get("isr_retenido", 0) or 0
    subtotal = cfdi_data.get("subtotal", 0) or 0

    if tipo == "I" and emisor_regimen in ("612", "625"):
        # If billing to a Persona Moral (RFC 12 chars), should have 10% ISR retention
        if receptor_rfc and len(receptor_rfc) == 12 and subtotal > 0:
            expected_retention = subtotal * 0.10
            if isr_ret == 0:
                errors.append(ErrorCFDI(
                    codigo="MED-002",
                    mensaje="Factura a Persona Moral sin retención ISR 10%.",
                    severidad=SeveridadError.ADVERTENCIA.value,
                    tipo=TipoValidacion.MEDICO.value,
                    campo="isr_retenido",
                    valor_esperado=f"~${expected_retention:,.2f} (10% de ${subtotal:,.2f})",
                    fundamento="Art. 106 LISR",
                    recomendacion="Las Personas Morales deben retener 10% de ISR. Verificar con el receptor.",
                ))

    return errors


def _validate_payment(cfdi_data: dict) -> list[ErrorCFDI]:
    """Validate payment-related rules."""
    errors = []

    forma_pago = cfdi_data.get("forma_pago")
    metodo_pago = cfdi_data.get("metodo_pago")

    # Missing payment info
    tipo = cfdi_data.get("tipo_comprobante", "")
    if tipo in ("I", "E") and not forma_pago:
        errors.append(ErrorCFDI(
            codigo="PAG-001",
            mensaje="Factura sin forma de pago especificada.",
            severidad=SeveridadError.ADVERTENCIA.value,
            tipo=TipoValidacion.PAGO.value,
            campo="forma_pago",
            recomendacion="Solicitar corrección con forma de pago (03, 04, 28).",
        ))

    if tipo in ("I", "E") and not metodo_pago:
        errors.append(ErrorCFDI(
            codigo="PAG-002",
            mensaje="Factura sin método de pago (PUE/PPD).",
            severidad=SeveridadError.ADVERTENCIA.value,
            tipo=TipoValidacion.PAGO.value,
            campo="metodo_pago",
            recomendacion="Especificar PUE o PPD.",
        ))

    return errors


# ─── Main Validation Function ─────────────────────────────────────────

def validate_cfdi(
    cfdi_data: dict,
    regimen_doctor: str = "612",
    es_gasto: bool = True,
) -> ResultadoValidacion:
    """Validate a CFDI comprehensively.

    Args:
        cfdi_data: Dict with CFDI fields (from CFDI.to_dict() or parsed JSON)
        regimen_doctor: Doctor's tax regime ("612" or "625")
        es_gasto: True if this is an expense (received), False if income (emitted)

    Returns:
        ResultadoValidacion with all findings.
    """
    all_errors = []

    # Run all validations
    all_errors.extend(_validate_structure(cfdi_data))
    all_errors.extend(_validate_fiscal(cfdi_data))
    all_errors.extend(_validate_payment(cfdi_data))

    if es_gasto:
        all_errors.extend(_validate_deducibility(cfdi_data, regimen_doctor))

    all_errors.extend(_validate_medical(cfdi_data))

    # Count by severity
    criticos = sum(1 for e in all_errors if e.severidad == SeveridadError.CRITICO.value)
    advertencias = sum(1 for e in all_errors if e.severidad == SeveridadError.ADVERTENCIA.value)
    info = sum(1 for e in all_errors if e.severidad == SeveridadError.INFO.value)

    # Calculate score
    score = 100 - (criticos * 20) - (advertencias * 5) - (info * 1)
    score = max(0, min(100, score))

    return ResultadoValidacion(
        es_valido=criticos == 0,
        total_errores=criticos,
        total_advertencias=advertencias,
        total_info=info,
        errores=all_errors,
        score=score,
    )


def validate_cfdi_batch(
    cfdis: list[dict],
    regimen_doctor: str = "612",
) -> dict:
    """Validate multiple CFDIs and return summary.

    Args:
        cfdis: List of CFDI dicts
        regimen_doctor: Doctor's regime

    Returns:
        Summary dict with per-CFDI results and totals.
    """
    results = []
    total_criticos = 0
    total_advertencias = 0

    for i, cfdi in enumerate(cfdis):
        result = validate_cfdi(cfdi, regimen_doctor)
        total_criticos += result.total_errores
        total_advertencias += result.total_advertencias

        uuid = ""
        timbre = cfdi.get("timbre", {})
        if isinstance(timbre, dict):
            uuid = timbre.get("uuid", "")[:8]

        results.append({
            "index": i,
            "uuid": uuid,
            "emisor": cfdi.get("emisor_nombre", ""),
            "total": cfdi.get("total", 0),
            "score": result.score,
            "es_valido": result.es_valido,
            "errores": result.total_errores,
            "advertencias": result.total_advertencias,
        })

    return {
        "total_cfdis": len(cfdis),
        "cfdis_validos": sum(1 for r in results if r["es_valido"]),
        "cfdis_con_errores": sum(1 for r in results if not r["es_valido"]),
        "total_errores_criticos": total_criticos,
        "total_advertencias": total_advertencias,
        "score_promedio": round(sum(r["score"] for r in results) / len(results), 1) if results else 0,
        "resultados": results,
    }
