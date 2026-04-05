"""OpenDoc - DIOT Generator (Declaración Informativa de Operaciones con Terceros).

Generates the monthly DIOT report that groups IVA paid to suppliers (terceros).
Required ONLY for Régimen 612; RESICO is exempt from DIOT.

The DIOT groups all expenses by supplier RFC and reports the IVA treatment:
- IVA paid at 16%
- IVA paid at 8% (frontera)
- IVA at 0%
- IVA exempt

Since August 2025, the DIOT is filed through the new SAT platform:
https://pstcdi.clouda.sat.gob.mx

Based on: Art. 32 LIVA, Art. 33 Reglamento LIVA, RMF 2026.
Filing deadline: Day 17 of the following month.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum
from collections import defaultdict


# ─── Enums ────────────────────────────────────────────────────────────

class TipoTercero(str, Enum):
    """Type of third party in DIOT."""
    PROVEEDOR_NACIONAL = "04"       # Proveedor nacional
    PROVEEDOR_EXTRANJERO = "05"     # Proveedor extranjero
    PROVEEDOR_GLOBAL = "15"         # Proveedor global (público en general)


class TipoOperacion(str, Enum):
    """Type of operation for DIOT."""
    SERVICIOS_PROFESIONALES = "85"  # Servicios profesionales (honorarios)
    ARRENDAMIENTO = "06"            # Arrendamiento de inmuebles
    OTROS = "85"                    # Otros servicios


# ─── Data Classes ─────────────────────────────────────────────────────

@dataclass
class OperacionTercero:
    """A single operation (expense) with a third party."""
    rfc_tercero: str
    nombre_tercero: str = ""
    monto_operacion: float = 0.0          # Subtotal (before IVA)
    iva_pagado_16: float = 0.0            # IVA paid at 16%
    iva_pagado_8: float = 0.0             # IVA paid at 8% (frontera)
    monto_tasa_cero: float = 0.0          # Amount at 0% IVA (e.g., medicines)
    monto_exento: float = 0.0             # IVA exempt amount
    iva_retenido: float = 0.0             # IVA retained (rare for doctors)
    fecha: str = ""                       # CFDI date
    uuid: str = ""                        # CFDI UUID for traceability
    tipo_tercero: str = TipoTercero.PROVEEDOR_NACIONAL.value

    @property
    def total_operacion(self) -> float:
        """Total including IVA."""
        return self.monto_operacion + self.iva_pagado_16 + self.iva_pagado_8

    @property
    def iva_total(self) -> float:
        """Total IVA paid."""
        return self.iva_pagado_16 + self.iva_pagado_8


@dataclass
class ResumenTercero:
    """Aggregated summary of operations with a single third party."""
    rfc: str
    nombre: str = ""
    tipo_tercero: str = TipoTercero.PROVEEDOR_NACIONAL.value
    num_operaciones: int = 0

    # Aggregated amounts
    valor_actos_16: float = 0.0           # Total base at 16%
    iva_pagado_16: float = 0.0            # Total IVA at 16%
    valor_actos_8: float = 0.0            # Total base at 8%
    iva_pagado_8: float = 0.0             # Total IVA at 8%
    valor_actos_tasa_cero: float = 0.0    # Total at 0%
    valor_actos_exentos: float = 0.0      # Total exempt
    iva_retenido: float = 0.0             # Total IVA retained

    @property
    def total_iva_pagado(self) -> float:
        return self.iva_pagado_16 + self.iva_pagado_8

    @property
    def total_valor_actos(self) -> float:
        return (self.valor_actos_16 + self.valor_actos_8 +
                self.valor_actos_tasa_cero + self.valor_actos_exentos)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReporteDIOT:
    """Complete DIOT report for a month."""
    mes: int
    anio: int
    rfc_declarante: str
    regimen: str = "612"

    # Summary
    total_terceros: int = 0
    total_operaciones: int = 0
    total_valor_actos: float = 0.0
    total_iva_16: float = 0.0
    total_iva_8: float = 0.0
    total_iva_tasa_cero: float = 0.0
    total_iva_exento: float = 0.0
    total_iva_retenido: float = 0.0

    # Per-supplier detail
    terceros: list = field(default_factory=list)

    # Alerts
    alertas: list = field(default_factory=list)
    notas: list = field(default_factory=list)

    def to_dict(self) -> dict:
        result = asdict(self)
        return result

    def resumen_whatsapp(self) -> str:
        """WhatsApp-friendly DIOT summary."""
        mes_nombre = [
            "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ]
        nombre = mes_nombre[self.mes] if 1 <= self.mes <= 12 else str(self.mes)

        lines = [
            f"━━━ DIOT {nombre.upper()} {self.anio} ━━━",
            f"📋 RFC: {self.rfc_declarante}",
            "",
            f"👥 Proveedores: {self.total_terceros}",
            f"🧾 Operaciones: {self.total_operaciones}",
            "",
            "💰 DESGLOSE IVA:",
            f"   IVA 16% pagado: ${self.total_iva_16:,.2f}",
        ]

        if self.total_iva_8 > 0:
            lines.append(f"   IVA 8% pagado: ${self.total_iva_8:,.2f}")

        lines.extend([
            f"   Actos tasa 0%: ${self.total_iva_tasa_cero:,.2f}",
            f"   Actos exentos: ${self.total_iva_exento:,.2f}",
        ])

        if self.total_iva_retenido > 0:
            lines.append(f"   IVA retenido: ${self.total_iva_retenido:,.2f}")

        lines.extend([
            "",
            f"📊 Total operaciones: ${self.total_valor_actos:,.2f}",
            f"📅 Plazo: 17 del mes siguiente",
        ])

        if self.terceros:
            lines.append("")
            lines.append("TOP PROVEEDORES:")

            def _get_valor(t):
                if isinstance(t, dict):
                    return (t.get("valor_actos_16", 0) + t.get("valor_actos_8", 0) +
                            t.get("valor_actos_tasa_cero", 0) + t.get("valor_actos_exentos", 0))
                return t.total_valor_actos

            def _get_iva(t):
                if isinstance(t, dict):
                    return t.get("iva_pagado_16", 0) + t.get("iva_pagado_8", 0)
                return t.total_iva_pagado

            # Show top 5 by value
            sorted_terceros = sorted(
                self.terceros,
                key=_get_valor,
                reverse=True,
            )
            for i, t in enumerate(sorted_terceros[:5], 1):
                if isinstance(t, dict):
                    nombre_t = t.get("nombre", t.get("rfc", ""))
                else:
                    nombre_t = t.nombre or t.rfc
                valor = _get_valor(t)
                iva = _get_iva(t)
                lines.append(f"   {i}. {nombre_t}: ${valor:,.2f} (IVA: ${iva:,.2f})")

        if self.alertas:
            lines.append("")
            for a in self.alertas:
                lines.append(f"🚨 {a}")

        if self.notas:
            lines.append("")
            for n in self.notas:
                lines.append(f"ℹ️ {n}")

        return "\n".join(lines)

    def generate_txt_layout(self) -> str:
        """Generate pipe-delimited text for SAT DIOT upload.

        Format per DIOT specification:
        TipoTercero|RFC|NombreExtranjero|PaisResidencia|Nacionalidad|
        ValorActos16|IVA16|ValorActos8IVAFrontera|IVA8Frontera|
        ValorActosTasa0|ValorActosExentos|IVARetenido|IVADevueltoDevoluciones|

        For national suppliers, NombreExtranjero/PaisResidencia/Nacionalidad are empty.
        """
        lines = []
        for t in self.terceros:
            if isinstance(t, dict):
                rfc = t.get("rfc", "")
                tipo = t.get("tipo_tercero", TipoTercero.PROVEEDOR_NACIONAL.value)
                va16 = t.get("valor_actos_16", 0)
                iva16 = t.get("iva_pagado_16", 0)
                va8 = t.get("valor_actos_8", 0)
                iva8 = t.get("iva_pagado_8", 0)
                vat0 = t.get("valor_actos_tasa_cero", 0)
                vaex = t.get("valor_actos_exentos", 0)
                ivaret = t.get("iva_retenido", 0)
            else:
                rfc = t.rfc
                tipo = t.tipo_tercero
                va16 = t.valor_actos_16
                iva16 = t.iva_pagado_16
                va8 = t.valor_actos_8
                iva8 = t.iva_pagado_8
                vat0 = t.valor_actos_tasa_cero
                vaex = t.valor_actos_exentos
                ivaret = t.iva_retenido

            # National suppliers: fields 3,4,5 are empty
            line = (
                f"{tipo}|{rfc}|||"
                f"|{_format_diot_amount(va16)}"
                f"|{_format_diot_amount(iva16)}"
                f"|{_format_diot_amount(va8)}"
                f"|{_format_diot_amount(iva8)}"
                f"|{_format_diot_amount(vat0)}"
                f"|{_format_diot_amount(vaex)}"
                f"|{_format_diot_amount(ivaret)}"
                f"|"
            )
            lines.append(line)

        return "\n".join(lines)


def _format_diot_amount(amount: float) -> str:
    """Format amount for DIOT file (integer pesos, no cents)."""
    return str(int(round(amount, 0))) if amount else ""


# ─── Core Functions ───────────────────────────────────────────────────

def _clean_rfc(rfc: str) -> str:
    """Normalize RFC for grouping."""
    return rfc.strip().upper() if rfc else "XAXX010101000"


def _detect_iva_treatment(
    subtotal: float,
    iva: float,
    total: float,
) -> dict:
    """Detect IVA treatment from CFDI amounts.

    Returns dict with iva_pagado_16, iva_pagado_8, monto_tasa_cero, monto_exento.
    """
    if iva == 0 and subtotal > 0:
        # Could be exempt or tasa 0% — need more context
        # Default to exempt (most medical expenses)
        return {
            "iva_pagado_16": 0.0,
            "iva_pagado_8": 0.0,
            "monto_tasa_cero": 0.0,
            "monto_exento": subtotal,
        }

    if subtotal > 0 and iva > 0:
        # Calculate effective rate
        effective_rate = iva / subtotal
        if effective_rate > 0.12:
            # 16% rate
            return {
                "iva_pagado_16": iva,
                "iva_pagado_8": 0.0,
                "monto_tasa_cero": 0.0,
                "monto_exento": 0.0,
            }
        elif effective_rate > 0.04:
            # 8% frontera rate
            return {
                "iva_pagado_16": 0.0,
                "iva_pagado_8": iva,
                "monto_tasa_cero": 0.0,
                "monto_exento": 0.0,
            }

    return {
        "iva_pagado_16": iva if iva > 0 else 0.0,
        "iva_pagado_8": 0.0,
        "monto_tasa_cero": 0.0,
        "monto_exento": subtotal if iva == 0 else 0.0,
    }


def group_operations_by_rfc(
    operaciones: list[OperacionTercero],
) -> list[ResumenTercero]:
    """Group individual operations by supplier RFC.

    This is the core DIOT logic: aggregate all expenses with each supplier
    into a single record for the DIOT report.

    Args:
        operaciones: List of individual operations (from CFDIs)

    Returns:
        List of ResumenTercero, one per unique supplier RFC.
    """
    grupos: dict[str, ResumenTercero] = {}

    for op in operaciones:
        rfc = _clean_rfc(op.rfc_tercero)

        if rfc not in grupos:
            grupos[rfc] = ResumenTercero(
                rfc=rfc,
                nombre=op.nombre_tercero,
                tipo_tercero=op.tipo_tercero,
            )

        resumen = grupos[rfc]
        resumen.num_operaciones += 1

        # Aggregate IVA amounts
        if op.iva_pagado_16 > 0:
            resumen.valor_actos_16 += op.monto_operacion
            resumen.iva_pagado_16 += op.iva_pagado_16
        elif op.iva_pagado_8 > 0:
            resumen.valor_actos_8 += op.monto_operacion
            resumen.iva_pagado_8 += op.iva_pagado_8
        elif op.monto_tasa_cero > 0:
            resumen.valor_actos_tasa_cero += op.monto_tasa_cero
        else:
            resumen.valor_actos_exentos += op.monto_exento or op.monto_operacion

        resumen.iva_retenido += op.iva_retenido

        # Update name if we get a better one
        if op.nombre_tercero and not resumen.nombre:
            resumen.nombre = op.nombre_tercero

    return list(grupos.values())


def generate_diot(
    mes: int,
    anio: int,
    rfc_declarante: str,
    operaciones: list[OperacionTercero],
    regimen: str = "612",
) -> ReporteDIOT:
    """Generate complete DIOT report for a month.

    Groups all operations by supplier RFC, aggregates IVA, and produces
    the monthly DIOT report.

    Args:
        mes: Month (1-12)
        anio: Year (e.g., 2026)
        rfc_declarante: Doctor's RFC
        operaciones: List of all expense operations for the month
        regimen: Tax regime ("612" or "625")

    Returns:
        ReporteDIOT with full report.
    """
    alertas = []
    notas = []

    # RESICO check
    if regimen == "625":
        alertas.append(
            "RESICO está relevado de presentar DIOT (RMF 2026, regla 3.13.16). "
            "Este reporte es informativo."
        )

    # Group by RFC
    terceros = group_operations_by_rfc(operaciones)

    # Calculate totals
    total_iva_16 = sum(t.iva_pagado_16 for t in terceros)
    total_iva_8 = sum(t.iva_pagado_8 for t in terceros)
    total_tasa_cero = sum(t.valor_actos_tasa_cero for t in terceros)
    total_exento = sum(t.valor_actos_exentos for t in terceros)
    total_retenido = sum(t.iva_retenido for t in terceros)
    total_valor = sum(t.total_valor_actos for t in terceros)
    total_ops = sum(t.num_operaciones for t in terceros)

    # Validation alerts
    if not operaciones:
        notas.append("Sin operaciones este mes. DIOT vacía.")

    for t in terceros:
        if t.rfc == "XAXX010101000":
            alertas.append(
                f"Proveedor con RFC genérico (público en general). "
                f"Total: ${t.total_valor_actos:,.2f}. "
                f"Obtener CFDI con RFC correcto del proveedor."
            )

        if t.rfc == "XEXX010101000":
            notas.append(
                f"Proveedor extranjero detectado: ${t.total_valor_actos:,.2f}. "
                f"Registrado como Tipo 05."
            )
            t.tipo_tercero = TipoTercero.PROVEEDOR_EXTRANJERO.value

    # Medical services note
    notas.append(
        "Recordatorio: El IVA pagado en gastos operativos NO es acreditable "
        "porque tus servicios médicos son exentos (Art. 15 LIVA). "
        "El IVA pagado se registra como costo."
    )

    # Convert to dicts for serialization
    terceros_data = [t.to_dict() for t in terceros]

    return ReporteDIOT(
        mes=mes,
        anio=anio,
        rfc_declarante=rfc_declarante.strip().upper(),
        regimen=regimen,
        total_terceros=len(terceros),
        total_operaciones=total_ops,
        total_valor_actos=round(total_valor, 2),
        total_iva_16=round(total_iva_16, 2),
        total_iva_8=round(total_iva_8, 2),
        total_iva_tasa_cero=round(total_tasa_cero, 2),
        total_iva_exento=round(total_exento, 2),
        total_iva_retenido=round(total_retenido, 2),
        terceros=terceros_data,
        alertas=alertas,
        notas=notas,
    )


def create_operation_from_cfdi(
    rfc_emisor: str,
    nombre_emisor: str,
    subtotal: float,
    iva: float,
    total: float,
    uuid: str = "",
    fecha: str = "",
    iva_retenido: float = 0.0,
) -> OperacionTercero:
    """Create a DIOT operation from CFDI data.

    Convenience function to create an OperacionTercero from parsed CFDI fields.
    Automatically detects IVA treatment (16%, 8%, 0%, exempt).

    Args:
        rfc_emisor: Supplier RFC
        nombre_emisor: Supplier name
        subtotal: CFDI subtotal (before IVA)
        iva: IVA amount from CFDI
        total: CFDI total
        uuid: CFDI UUID for traceability
        fecha: CFDI emission date
        iva_retenido: IVA retained (if any)

    Returns:
        OperacionTercero ready for DIOT grouping.
    """
    iva_treatment = _detect_iva_treatment(subtotal, iva, total)

    # Detect foreign supplier
    tipo = TipoTercero.PROVEEDOR_NACIONAL.value
    if rfc_emisor and rfc_emisor.strip().upper() == "XEXX010101000":
        tipo = TipoTercero.PROVEEDOR_EXTRANJERO.value

    return OperacionTercero(
        rfc_tercero=_clean_rfc(rfc_emisor),
        nombre_tercero=nombre_emisor,
        monto_operacion=subtotal,
        iva_pagado_16=iva_treatment["iva_pagado_16"],
        iva_pagado_8=iva_treatment["iva_pagado_8"],
        monto_tasa_cero=iva_treatment["monto_tasa_cero"],
        monto_exento=iva_treatment["monto_exento"],
        iva_retenido=iva_retenido,
        fecha=fecha,
        uuid=uuid,
        tipo_tercero=tipo,
    )
