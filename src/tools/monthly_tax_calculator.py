"""OpenDoc - Monthly Provisional Tax Calculator.

Calculates ISR provisional payment, IVA, and state tax (cedular)
for a Mexican doctor. Supports Régimen 612 and RESICO 625.

This is what the contador does every month before the 17th.
OpenDoc automates the calculation; the doctor signs and sends.

Based on: LISR 2026 (Art. 96, 106, 113-E to 113-J), LIVA, RMF 2026.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum

from .fiscal_tables import (  # noqa: F401 — re-exported for backward compat
    TARIFA_ISR_MENSUAL,
    TARIFA_RESICO_MENSUAL,
    IVA_TASA_GENERAL,
    IVA_TASA_FRONTERA,
    IVA_TASA_CERO,
    CEDULAR_TASA_GTO,
)


# ─── Data Classes ─────────────────────────────────────────────────────

@dataclass
class IngresosMensuales:
    """Monthly income breakdown."""
    honorarios_personas_fisicas: float = 0.0   # Billed to individuals
    honorarios_personas_morales: float = 0.0   # Billed to companies (10% ISR retained)
    otros_ingresos: float = 0.0                # Other professional income

    @property
    def total(self) -> float:
        return (self.honorarios_personas_fisicas +
                self.honorarios_personas_morales +
                self.otros_ingresos)

    @property
    def retencion_isr_pm(self) -> float:
        """10% ISR retention from Personas Morales (Art. 106 LISR)."""
        return round(self.honorarios_personas_morales * 0.10, 2)


@dataclass
class DeduccionesMensuales:
    """Monthly deduction breakdown."""
    arrendamiento: float = 0.0
    servicios: float = 0.0          # Luz, agua, internet, teléfono
    material_curacion: float = 0.0
    nomina_y_seguridad: float = 0.0  # Salarios + IMSS + INFONAVIT
    depreciacion: float = 0.0        # Monthly depreciation of assets
    seguros: float = 0.0
    educacion_medica: float = 0.0
    honorarios_externos: float = 0.0  # Contador, abogado, otros médicos
    publicidad: float = 0.0
    software: float = 0.0
    limpieza_mantenimiento: float = 0.0
    vehiculo: float = 0.0            # Gas, maintenance (proportional)
    otros_deducibles: float = 0.0

    @property
    def total(self) -> float:
        return (self.arrendamiento + self.servicios + self.material_curacion +
                self.nomina_y_seguridad + self.depreciacion + self.seguros +
                self.educacion_medica + self.honorarios_externos +
                self.publicidad + self.software + self.limpieza_mantenimiento +
                self.vehiculo + self.otros_deducibles)


@dataclass
class IVAMensual:
    """Monthly IVA breakdown for a doctor."""
    # IVA caused (doctor charges)
    actos_exentos: float = 0.0       # Medical services (Art. 15 LIVA) — most common
    actos_gravados_16: float = 0.0   # Aesthetic procedures (Criterio 7/IVA/N)
    actos_tasa_cero: float = 0.0     # Rarely applies to doctors

    # IVA paid on expenses (NOT creditable for exempt doctors)
    iva_pagado_gastos: float = 0.0   # IVA on rent, supplies, services
    iva_retenido_recibido: float = 0.0  # IVA retained by Personas Morales (rare for doctors)

    @property
    def iva_causado(self) -> float:
        """IVA the doctor must charge (only on gravado services)."""
        return round(self.actos_gravados_16 * IVA_TASA_GENERAL, 2)

    @property
    def iva_acreditable(self) -> float:
        """IVA the doctor can credit.

        CRITICAL: If ALL income is exempt (standard doctor), IVA is NOT creditable.
        If doctor has gravado income (aesthetic), proportional credit applies.
        """
        if self.actos_gravados_16 == 0:
            return 0.0  # All exempt → zero credit

        # Proportional credit (only for mixed doctors — exento + gravado)
        total_actos = self.actos_exentos + self.actos_gravados_16 + self.actos_tasa_cero
        if total_actos == 0:
            return 0.0

        proporcion_gravada = (self.actos_gravados_16 + self.actos_tasa_cero) / total_actos
        return round(self.iva_pagado_gastos * proporcion_gravada, 2)

    @property
    def iva_a_pagar(self) -> float:
        """Net IVA to pay or in favor."""
        return round(self.iva_causado - self.iva_acreditable - self.iva_retenido_recibido, 2)


@dataclass
class ResultadoProvisional:
    """Complete monthly provisional payment result."""
    # Period
    mes: int
    anio: int
    regimen: str  # "612" or "625"

    # Income
    ingresos_totales: float = 0.0
    ingresos_acumulados_anio: float = 0.0  # Year-to-date income

    # Deductions (only 612)
    deducciones_totales: float = 0.0
    deducciones_acumuladas_anio: float = 0.0  # Year-to-date deductions

    # ISR
    base_gravable_isr: float = 0.0
    isr_causado: float = 0.0
    pagos_provisionales_anteriores: float = 0.0
    retenciones_isr: float = 0.0  # 10% from Personas Morales
    isr_a_pagar: float = 0.0

    # IVA
    iva_causado: float = 0.0
    iva_acreditable: float = 0.0
    iva_retenido: float = 0.0
    iva_a_pagar: float = 0.0

    # State tax (cedular)
    cedular_base: float = 0.0
    cedular_tasa: float = 0.0
    cedular_a_pagar: float = 0.0

    # Totals
    total_a_pagar: float = 0.0

    # Alerts
    alertas: list = field(default_factory=list)
    notas: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def resumen_whatsapp(self) -> str:
        """WhatsApp-friendly summary."""
        mes_nombre = [
            "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ]
        nombre = mes_nombre[self.mes] if 1 <= self.mes <= 12 else str(self.mes)

        lines = [
            f"━━━ PROVISIONAL {nombre.upper()} {self.anio} ━━━",
            f"📋 Régimen: {self.regimen}",
            "",
            f"💰 Ingresos: ${self.ingresos_totales:,.2f}",
        ]

        if self.regimen == "612":
            lines.append(f"📉 Deducciones: ${self.deducciones_totales:,.2f}")
            lines.append(f"📊 Base gravable: ${self.base_gravable_isr:,.2f}")

        lines.extend([
            "",
            f"🏛️ ISR causado: ${self.isr_causado:,.2f}",
        ])

        if self.retenciones_isr > 0:
            lines.append(f"   Retenciones ISR (PM): -${self.retenciones_isr:,.2f}")
        if self.pagos_provisionales_anteriores > 0:
            lines.append(f"   Provisionales ant.: -${self.pagos_provisionales_anteriores:,.2f}")

        lines.append(f"   ➡️ ISR a pagar: ${self.isr_a_pagar:,.2f}")

        if self.iva_causado > 0 or self.iva_a_pagar != 0:
            lines.extend([
                "",
                f"🧾 IVA causado: ${self.iva_causado:,.2f}",
                f"   IVA acreditable: -${self.iva_acreditable:,.2f}",
                f"   ➡️ IVA a pagar: ${self.iva_a_pagar:,.2f}",
            ])

        if self.cedular_a_pagar > 0:
            lines.extend([
                "",
                f"🏘️ Cedular estatal ({self.cedular_tasa*100:.0f}%): ${self.cedular_a_pagar:,.2f}",
            ])

        lines.extend([
            "",
            f"💵 TOTAL A PAGAR: ${self.total_a_pagar:,.2f}",
            f"📅 Fecha límite: 17 del mes siguiente",
        ])

        if self.alertas:
            lines.append("")
            for a in self.alertas:
                lines.append(f"🚨 {a}")

        return "\n".join(lines)


# ─── Core Calculation Functions ───────────────────────────────────────

def _calculate_isr_tarifa(base_mensual: float) -> float:
    """Apply monthly ISR tariff (Art. 96 LISR) to a base amount."""
    if base_mensual <= 0:
        return 0.0

    for li, ls, cuota, tasa in TARIFA_ISR_MENSUAL:
        if li <= base_mensual <= ls:
            excedente = base_mensual - li
            return round(cuota + (excedente * tasa / 100), 2)

    # Above max bracket
    last = TARIFA_ISR_MENSUAL[-1]
    excedente = base_mensual - last[0]
    return round(last[2] + (excedente * last[3] / 100), 2)


def _calculate_isr_resico(ingresos_cobrados: float) -> float:
    """Apply RESICO flat rate (Art. 113-E LISR)."""
    if ingresos_cobrados <= 0:
        return 0.0

    for li, ls, tasa in TARIFA_RESICO_MENSUAL:
        if li <= ingresos_cobrados <= ls:
            return round(ingresos_cobrados * tasa / 100, 2)

    # Above RESICO cap — shouldn't happen (expelled to 612)
    return round(ingresos_cobrados * 2.50 / 100, 2)


def calculate_provisional_612(
    mes: int,
    anio: int,
    ingresos: IngresosMensuales,
    deducciones: DeduccionesMensuales,
    iva: Optional[IVAMensual] = None,
    pagos_provisionales_anteriores: float = 0.0,
    ingresos_acumulados_previos: float = 0.0,
    deducciones_acumuladas_previas: float = 0.0,
    include_cedular: bool = False,
    tasa_cedular: float = CEDULAR_TASA_GTO,
) -> ResultadoProvisional:
    """Calculate monthly provisional payment for Régimen 612.

    ISR is calculated on ACCUMULATED basis (Jan-current month),
    then prior provisional payments are subtracted.

    Args:
        mes: Month (1-12)
        anio: Year (e.g., 2026)
        ingresos: Monthly income breakdown
        deducciones: Monthly deduction breakdown
        iva: Monthly IVA breakdown (optional, most doctors are exempt)
        pagos_provisionales_anteriores: Sum of ISR provisionals paid Jan through previous month
        ingresos_acumulados_previos: Cumulative income from Jan through previous month
        deducciones_acumuladas_previas: Cumulative deductions from Jan through previous month
        include_cedular: Whether to calculate state cedular tax
        tasa_cedular: State tax rate (default: Guanajuato 2%)

    Returns:
        ResultadoProvisional with full calculation.
    """
    alertas = []
    notas = []

    # ─── ISR Calculation (accumulated basis) ────────────
    ingresos_mes = ingresos.total
    deducciones_mes = deducciones.total
    retenciones_mes = ingresos.retencion_isr_pm

    # Accumulate year-to-date
    ingresos_acum = ingresos_acumulados_previos + ingresos_mes
    deducciones_acum = deducciones_acumuladas_previas + deducciones_mes

    # Base gravable (accumulated)
    utilidad_acum = max(0, ingresos_acum - deducciones_acum)

    # Monthly average for tariff
    utilidad_mensual_promedio = utilidad_acum / mes if mes > 0 else 0

    # ISR on accumulated basis
    isr_causado_acum = _calculate_isr_tarifa(utilidad_mensual_promedio) * mes

    # ISR for this month = accumulated ISR - prior payments - retentions
    isr_a_pagar = max(0, isr_causado_acum - pagos_provisionales_anteriores - retenciones_mes)

    # ─── IVA Calculation ────────────────────────────────
    iva_causado = 0.0
    iva_acreditable = 0.0
    iva_retenido = 0.0
    iva_a_pagar = 0.0

    if iva:
        iva_causado = iva.iva_causado
        iva_acreditable = iva.iva_acreditable
        iva_retenido = iva.iva_retenido_recibido
        iva_a_pagar = iva.iva_a_pagar

        if iva.actos_exentos > 0 and iva.actos_gravados_16 == 0:
            notas.append(
                "Todos tus servicios son exentos de IVA (Art. 15 LIVA). "
                "El IVA que pagas en gastos NO es acreditable — se suma al costo."
            )

    # ─── Cedular (state tax) ────────────────────────────
    cedular_base = 0.0
    cedular_a_pagar = 0.0
    if include_cedular:
        cedular_base = max(0, ingresos_mes - deducciones_mes)
        cedular_a_pagar = round(cedular_base * tasa_cedular, 2)

    # ─── Total ──────────────────────────────────────────
    total = round(isr_a_pagar + max(0, iva_a_pagar) + cedular_a_pagar, 2)

    # ─── Alerts ─────────────────────────────────────────
    if retenciones_mes > 0:
        notas.append(
            f"Retención ISR de Personas Morales: ${retenciones_mes:,.2f} "
            f"(acreditable en este pago provisional)"
        )

    if deducciones_mes > ingresos_mes:
        alertas.append(
            "Deducciones mayores que ingresos este mes. "
            "Verifica que todos los gastos sean estrictamente indispensables."
        )

    utilidad_pct = (deducciones_mes / ingresos_mes * 100) if ingresos_mes > 0 else 0
    if utilidad_pct > 80:
        alertas.append(
            f"Deducciones representan {utilidad_pct:.0f}% de ingresos. "
            f"Proporción alta — podría llamar la atención del SAT."
        )

    return ResultadoProvisional(
        mes=mes,
        anio=anio,
        regimen="612",
        ingresos_totales=ingresos_mes,
        ingresos_acumulados_anio=ingresos_acum,
        deducciones_totales=deducciones_mes,
        deducciones_acumuladas_anio=deducciones_acum,
        base_gravable_isr=round(utilidad_mensual_promedio, 2),
        isr_causado=round(isr_causado_acum, 2),
        pagos_provisionales_anteriores=pagos_provisionales_anteriores,
        retenciones_isr=retenciones_mes,
        isr_a_pagar=round(isr_a_pagar, 2),
        iva_causado=iva_causado,
        iva_acreditable=iva_acreditable,
        iva_retenido=iva_retenido,
        iva_a_pagar=iva_a_pagar,
        cedular_base=cedular_base,
        cedular_tasa=tasa_cedular,
        cedular_a_pagar=cedular_a_pagar,
        total_a_pagar=total,
        alertas=alertas,
        notas=notas,
    )


def calculate_provisional_resico(
    mes: int,
    anio: int,
    ingresos_cobrados: float,
    retenciones_isr: float = 0.0,
) -> ResultadoProvisional:
    """Calculate monthly provisional payment for RESICO (625).

    RESICO is simple: flat rate on gross income collected.
    No deductions, no accumulation.

    Args:
        mes: Month (1-12)
        anio: Year
        ingresos_cobrados: Gross income effectively collected this month
        retenciones_isr: ISR retentions from Personas Morales

    Returns:
        ResultadoProvisional.
    """
    alertas = []

    isr_causado = _calculate_isr_resico(ingresos_cobrados)
    isr_a_pagar = max(0, isr_causado - retenciones_isr)

    # RESICO cap check
    if ingresos_cobrados * 12 > 3_500_000:
        alertas.append(
            f"Proyección anual: ${ingresos_cobrados * 12:,.0f} excede tope RESICO $3,500,000. "
            f"Riesgo de expulsión automática a Régimen 612."
        )

    return ResultadoProvisional(
        mes=mes,
        anio=anio,
        regimen="625",
        ingresos_totales=ingresos_cobrados,
        base_gravable_isr=ingresos_cobrados,
        isr_causado=isr_causado,
        retenciones_isr=retenciones_isr,
        isr_a_pagar=round(isr_a_pagar, 2),
        total_a_pagar=round(isr_a_pagar, 2),
        alertas=alertas,
        notas=["RESICO: ISR sobre ingresos cobrados. Sin deducciones operativas."],
    )


def calculate_annual_projection(
    provisionales: list[ResultadoProvisional],
) -> dict:
    """Project annual totals from monthly provisionals.

    Args:
        provisionales: List of monthly ResultadoProvisional (Jan through latest month)

    Returns:
        Dict with annual projections and alerts.
    """
    if not provisionales:
        return {"error": "No hay provisionales para proyectar"}

    meses_capturados = len(provisionales)
    regimen = provisionales[0].regimen

    total_ingresos = sum(p.ingresos_totales for p in provisionales)
    total_deducciones = sum(p.deducciones_totales for p in provisionales)
    total_isr_pagado = sum(p.isr_a_pagar for p in provisionales)
    total_iva_pagado = sum(max(0, p.iva_a_pagar) for p in provisionales)
    total_cedular = sum(p.cedular_a_pagar for p in provisionales)
    total_retenciones = sum(p.retenciones_isr for p in provisionales)

    # Project to 12 months
    factor = 12 / meses_capturados if meses_capturados > 0 else 1
    proyeccion_ingresos = total_ingresos * factor
    proyeccion_deducciones = total_deducciones * factor
    proyeccion_isr = total_isr_pagado * factor
    proyeccion_iva = total_iva_pagado * factor

    alertas = []

    if regimen == "625" and proyeccion_ingresos > 3_500_000:
        alertas.append(
            f"Proyección anual ${proyeccion_ingresos:,.0f} excede tope RESICO. "
            f"Evaluar cambio preventivo a Régimen 612."
        )

    tasa_efectiva = (total_isr_pagado / total_ingresos * 100) if total_ingresos > 0 else 0

    return {
        "meses_capturados": meses_capturados,
        "regimen": regimen,
        "acumulado": {
            "ingresos": round(total_ingresos, 2),
            "deducciones": round(total_deducciones, 2),
            "isr_pagado": round(total_isr_pagado, 2),
            "iva_pagado": round(total_iva_pagado, 2),
            "cedular_pagado": round(total_cedular, 2),
            "retenciones_isr": round(total_retenciones, 2),
        },
        "proyeccion_anual": {
            "ingresos": round(proyeccion_ingresos, 2),
            "deducciones": round(proyeccion_deducciones, 2),
            "isr_estimado": round(proyeccion_isr, 2),
            "iva_estimado": round(proyeccion_iva, 2),
        },
        "tasa_efectiva_isr": round(tasa_efectiva, 2),
        "alertas": alertas,
    }
