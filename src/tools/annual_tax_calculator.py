"""OpenDoc - Annual Tax Declaration Calculator.

Calculates the annual ISR declaration for Mexican doctors.
Closes the fiscal year cycle: monthly provisionals → annual declaration.

Supports:
- Régimen 612: Full deductions, progressive tariff, personal deductions
- RESICO 625: Simplified, annual rate on gross income
- Hybrid: Income from both regimes + salarios

Based on: LISR 2026 (Art. 150-152 for 612, Art. 113-F for RESICO).
Filing deadline: April 30 of the following year.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional

from .fiscal_tables import (  # noqa: F401 — re-exported for backward compat
    TARIFA_ISR_ANUAL,
    TARIFA_RESICO_ANUAL,
    UMA_ANUAL_2026,
    UMA_ANUAL_REAL_2026,
    TOPE_DEDUCCIONES_PERSONALES_UMAS,
)


# ─── Data Classes ─────────────────────────────────────────────────────

@dataclass
class IngresosAnuales:
    """Annual income breakdown across all sources."""
    # Régimen 612 — Professional services
    honorarios_facturados_612: float = 0.0
    retenciones_isr_612: float = 0.0       # 10% retained by PMs

    # RESICO income
    ingresos_cobrados_resico: float = 0.0
    retenciones_isr_resico: float = 0.0

    # Salarios (if any — some doctors also earn a salary)
    sueldos_y_salarios: float = 0.0
    isr_retenido_salarios: float = 0.0

    # Other income
    intereses_bancarios: float = 0.0
    isr_retenido_intereses: float = 0.0

    @property
    def total_ingresos(self) -> float:
        return (self.honorarios_facturados_612 +
                self.ingresos_cobrados_resico +
                self.sueldos_y_salarios +
                self.intereses_bancarios)

    @property
    def total_retenciones_isr(self) -> float:
        return (self.retenciones_isr_612 +
                self.retenciones_isr_resico +
                self.isr_retenido_salarios +
                self.isr_retenido_intereses)


@dataclass
class DeduccionesAnuales:
    """Annual deduction breakdown (Régimen 612 only)."""
    # Operational deductions
    arrendamiento: float = 0.0
    servicios: float = 0.0
    material_curacion: float = 0.0
    nomina_y_seguridad: float = 0.0
    depreciacion: float = 0.0
    seguros: float = 0.0
    educacion_medica: float = 0.0
    honorarios_externos: float = 0.0
    publicidad: float = 0.0
    software: float = 0.0
    limpieza_mantenimiento: float = 0.0
    vehiculo: float = 0.0
    otros_deducibles: float = 0.0

    @property
    def total_operativas(self) -> float:
        return (self.arrendamiento + self.servicios + self.material_curacion +
                self.nomina_y_seguridad + self.depreciacion + self.seguros +
                self.educacion_medica + self.honorarios_externos +
                self.publicidad + self.software + self.limpieza_mantenimiento +
                self.vehiculo + self.otros_deducibles)


@dataclass
class DeduccionesPersonales:
    """Personal deductions (Art. 151 LISR) — apply to both regimes in annual."""
    gastos_medicos: float = 0.0          # Honorarios médicos, dentales, psicología, nutrición
    gastos_hospitalarios: float = 0.0    # Hospitalización
    lentes_opticos: float = 0.0          # Tope $2,500
    primas_seguro_gmm: float = 0.0       # Gastos médicos mayores
    gastos_funerarios: float = 0.0       # Tope 1 UMA anual
    donativos: float = 0.0              # Tope 7% de ingresos acumulables
    intereses_hipotecarios: float = 0.0  # Reales pagados (crédito infonavit o bancario)
    aportaciones_retiro: float = 0.0     # Afore voluntarias, tope 10% ingresos o 5 UMA
    colegiaturas: float = 0.0           # Hasta nivel licenciatura (topes por nivel)
    transporte_escolar: float = 0.0      # Obligatorio si es deducible

    @property
    def total_antes_tope(self) -> float:
        return (self.gastos_medicos + self.gastos_hospitalarios +
                self.lentes_opticos + self.primas_seguro_gmm +
                self.gastos_funerarios + self.donativos +
                self.intereses_hipotecarios + self.aportaciones_retiro +
                self.colegiaturas + self.transporte_escolar)

    def total_con_tope(self, ingresos_totales: float) -> float:
        """Apply global personal deduction limit.

        Limit = min(15% of total income, 5 annual UMA).
        """
        tope_porcentaje = ingresos_totales * 0.15
        tope_umas = UMA_ANUAL_REAL_2026 * TOPE_DEDUCCIONES_PERSONALES_UMAS
        tope = min(tope_porcentaje, tope_umas)
        return min(self.total_antes_tope, tope)


@dataclass
class ResultadoAnual:
    """Complete annual tax declaration result."""
    anio: int
    regimen: str  # "612", "625", or "mixto"

    # Income
    ingresos_totales: float = 0.0
    ingresos_acumulables_612: float = 0.0
    ingresos_resico: float = 0.0
    ingresos_salarios: float = 0.0

    # Deductions (612)
    deducciones_operativas: float = 0.0
    deducciones_personales: float = 0.0
    tope_deducciones_personales: float = 0.0

    # ISR 612
    base_gravable_612: float = 0.0
    isr_anual_612: float = 0.0

    # ISR RESICO
    base_gravable_resico: float = 0.0
    isr_anual_resico: float = 0.0

    # Credits
    pagos_provisionales: float = 0.0
    retenciones_isr: float = 0.0

    # Result
    isr_total_ejercicio: float = 0.0
    isr_a_cargo: float = 0.0      # Positive = you owe SAT
    isr_a_favor: float = 0.0      # Positive = SAT owes you (devolución)

    # Tasa efectiva
    tasa_efectiva_isr: float = 0.0

    # Alerts
    alertas: list = field(default_factory=list)
    notas: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def resumen_whatsapp(self) -> str:
        """WhatsApp-friendly annual declaration summary."""
        lines = [
            f"━━━ DECLARACIÓN ANUAL {self.anio} ━━━",
            f"📋 Régimen: {self.regimen}",
            "",
            f"💰 Ingresos totales: ${self.ingresos_totales:,.2f}",
        ]

        if self.deducciones_operativas > 0:
            lines.append(f"📉 Deducciones operativas: ${self.deducciones_operativas:,.2f}")
        if self.deducciones_personales > 0:
            lines.append(f"👤 Deducciones personales: ${self.deducciones_personales:,.2f}")

        lines.extend([
            "",
            f"🏛️ ISR del ejercicio: ${self.isr_total_ejercicio:,.2f}",
            f"   Provisionales pagados: -${self.pagos_provisionales:,.2f}",
            f"   Retenciones ISR: -${self.retenciones_isr:,.2f}",
        ])

        if self.isr_a_cargo > 0:
            lines.append(f"   💸 ISR A CARGO: ${self.isr_a_cargo:,.2f}")
            lines.append(f"   📅 Pagar antes del 30 de abril")
        elif self.isr_a_favor > 0:
            lines.append(f"   ✅ ISR A FAVOR: ${self.isr_a_favor:,.2f}")
            lines.append(f"   💳 Solicitar devolución vía DeclaraSAT")

        lines.extend([
            "",
            f"📊 Tasa efectiva ISR: {self.tasa_efectiva_isr:.1f}%",
        ])

        if self.alertas:
            lines.append("")
            for a in self.alertas:
                lines.append(f"🚨 {a}")

        if self.notas:
            lines.append("")
            for n in self.notas:
                lines.append(f"ℹ️ {n}")

        return "\n".join(lines)


# ─── Core Calculation Functions ───────────────────────────────────────

def _calculate_isr_anual_tarifa(base_anual: float) -> float:
    """Apply annual ISR tariff (Art. 152 LISR)."""
    if base_anual <= 0:
        return 0.0

    for li, ls, cuota, tasa in TARIFA_ISR_ANUAL:
        if li <= base_anual <= ls:
            excedente = base_anual - li
            return round(cuota + (excedente * tasa / 100), 2)

    # Above max bracket
    last = TARIFA_ISR_ANUAL[-1]
    excedente = base_anual - last[0]
    return round(last[2] + (excedente * last[3] / 100), 2)


def _calculate_isr_resico_anual(ingresos_anuales: float) -> float:
    """Apply RESICO annual tariff (Art. 113-F LISR)."""
    if ingresos_anuales <= 0:
        return 0.0

    for li, ls, tasa in TARIFA_RESICO_ANUAL:
        if li <= ingresos_anuales <= ls:
            return round(ingresos_anuales * tasa / 100, 2)

    # Above cap
    return round(ingresos_anuales * 2.50 / 100, 2)


def calculate_annual_612(
    anio: int,
    ingresos: IngresosAnuales,
    deducciones: DeduccionesAnuales,
    personales: Optional[DeduccionesPersonales] = None,
    pagos_provisionales: float = 0.0,
) -> ResultadoAnual:
    """Calculate annual ISR for Régimen 612.

    Args:
        anio: Fiscal year
        ingresos: Annual income breakdown
        deducciones: Annual operational deductions
        personales: Personal deductions (Art. 151)
        pagos_provisionales: Total provisional payments made during the year

    Returns:
        ResultadoAnual with full declaration.
    """
    alertas = []
    notas = []

    # Total acumulable income (612 + salarios + intereses)
    ingresos_acumulables = (
        ingresos.honorarios_facturados_612 +
        ingresos.sueldos_y_salarios +
        ingresos.intereses_bancarios
    )

    # Operational deductions (only for 612 professional income)
    ded_operativas = deducciones.total_operativas

    # Personal deductions
    ded_personales = 0.0
    tope_personales = 0.0
    if personales:
        tope_personales = min(
            ingresos.total_ingresos * 0.15,
            UMA_ANUAL_REAL_2026 * TOPE_DEDUCCIONES_PERSONALES_UMAS,
        )
        ded_personales = min(personales.total_antes_tope, tope_personales)

        if personales.total_antes_tope > tope_personales:
            alertas.append(
                f"Deducciones personales (${personales.total_antes_tope:,.0f}) exceden tope "
                f"(${tope_personales:,.0f}). Se aplica el tope."
            )

    # Base gravable
    base_gravable = max(0, ingresos_acumulables - ded_operativas - ded_personales)

    # ISR anual
    isr_anual = _calculate_isr_anual_tarifa(base_gravable)

    # Credits
    total_retenciones = ingresos.total_retenciones_isr

    # ISR a cargo / a favor
    isr_neto = isr_anual - pagos_provisionales - total_retenciones
    isr_a_cargo = max(0, isr_neto)
    isr_a_favor = max(0, -isr_neto)

    # Tasa efectiva
    tasa_efectiva = (isr_anual / ingresos.total_ingresos * 100) if ingresos.total_ingresos > 0 else 0

    # Notes
    if ded_operativas > 0:
        pct = (ded_operativas / ingresos.honorarios_facturados_612 * 100) if ingresos.honorarios_facturados_612 > 0 else 0
        notas.append(f"Deducciones operativas: {pct:.0f}% de ingresos por honorarios")

    if isr_a_favor > 0:
        notas.append(
            "Tienes saldo a favor. Puedes solicitar devolución automática "
            "en DeclaraSAT (hasta $150,000) o compensar contra ISR futuro."
        )

    if tasa_efectiva > 30:
        alertas.append(
            f"Tasa efectiva ISR: {tasa_efectiva:.1f}%. "
            f"Evaluar estrategias de optimización fiscal."
        )

    return ResultadoAnual(
        anio=anio,
        regimen="612",
        ingresos_totales=ingresos.total_ingresos,
        ingresos_acumulables_612=ingresos_acumulables,
        ingresos_salarios=ingresos.sueldos_y_salarios,
        deducciones_operativas=ded_operativas,
        deducciones_personales=ded_personales,
        tope_deducciones_personales=round(tope_personales, 2),
        base_gravable_612=base_gravable,
        isr_anual_612=isr_anual,
        pagos_provisionales=pagos_provisionales,
        retenciones_isr=total_retenciones,
        isr_total_ejercicio=isr_anual,
        isr_a_cargo=round(isr_a_cargo, 2),
        isr_a_favor=round(isr_a_favor, 2),
        tasa_efectiva_isr=round(tasa_efectiva, 2),
        alertas=alertas,
        notas=notas,
    )


def calculate_annual_resico(
    anio: int,
    ingresos: IngresosAnuales,
    personales: Optional[DeduccionesPersonales] = None,
    pagos_provisionales: float = 0.0,
) -> ResultadoAnual:
    """Calculate annual ISR for RESICO (625).

    RESICO annual is simple: flat rate on total collected income.
    Personal deductions only apply to salary income portion.

    Args:
        anio: Fiscal year
        ingresos: Annual income breakdown
        personales: Personal deductions (only for salary portion)
        pagos_provisionales: Total provisional payments

    Returns:
        ResultadoAnual.
    """
    alertas = []
    notas = []

    ingresos_resico = ingresos.ingresos_cobrados_resico

    # RESICO cap check
    if ingresos_resico > 3_500_000:
        alertas.append(
            f"Ingresos RESICO ${ingresos_resico:,.0f} exceden tope $3,500,000. "
            f"Expulsión automática a Régimen 612 para siguiente ejercicio."
        )

    # ISR RESICO
    isr_resico = _calculate_isr_resico_anual(ingresos_resico)

    # Salary ISR (if any)
    isr_salarios = 0.0
    if ingresos.sueldos_y_salarios > 0:
        base_salarios = ingresos.sueldos_y_salarios
        if personales:
            tope = min(
                ingresos.total_ingresos * 0.15,
                UMA_ANUAL_REAL_2026 * TOPE_DEDUCCIONES_PERSONALES_UMAS,
            )
            ded_p = min(personales.total_antes_tope, tope)
            base_salarios = max(0, base_salarios - ded_p)
        isr_salarios = _calculate_isr_anual_tarifa(base_salarios)

    isr_total = isr_resico + isr_salarios
    total_retenciones = ingresos.total_retenciones_isr

    isr_neto = isr_total - pagos_provisionales - total_retenciones
    isr_a_cargo = max(0, isr_neto)
    isr_a_favor = max(0, -isr_neto)

    tasa_efectiva = (isr_total / ingresos.total_ingresos * 100) if ingresos.total_ingresos > 0 else 0

    notas.append("RESICO: Sin deducciones operativas. ISR sobre ingresos cobrados.")

    ded_p = 0.0
    if personales and ingresos.sueldos_y_salarios > 0:
        tope = min(
            ingresos.total_ingresos * 0.15,
            UMA_ANUAL_REAL_2026 * TOPE_DEDUCCIONES_PERSONALES_UMAS,
        )
        ded_p = min(personales.total_antes_tope, tope)
        notas.append(f"Deducciones personales aplicadas a salarios: ${ded_p:,.0f}")

    return ResultadoAnual(
        anio=anio,
        regimen="625",
        ingresos_totales=ingresos.total_ingresos,
        ingresos_resico=ingresos_resico,
        ingresos_salarios=ingresos.sueldos_y_salarios,
        deducciones_personales=round(ded_p, 2),
        base_gravable_resico=ingresos_resico,
        isr_anual_resico=isr_resico,
        pagos_provisionales=pagos_provisionales,
        retenciones_isr=total_retenciones,
        isr_total_ejercicio=round(isr_total, 2),
        isr_a_cargo=round(isr_a_cargo, 2),
        isr_a_favor=round(isr_a_favor, 2),
        tasa_efectiva_isr=round(tasa_efectiva, 2),
        alertas=alertas,
        notas=notas,
    )


def compare_annual_regimes(
    anio: int,
    ingresos: IngresosAnuales,
    deducciones: DeduccionesAnuales,
    personales: Optional[DeduccionesPersonales] = None,
    pagos_provisionales_612: float = 0.0,
    pagos_provisionales_resico: float = 0.0,
) -> dict:
    """Compare annual ISR between Régimen 612 and RESICO.

    Helps doctor decide which regime is better for next year.

    Returns:
        Dict with both calculations and recommendation.
    """
    # For comparison, assume all professional income goes to each regime
    ing_612 = IngresosAnuales(
        honorarios_facturados_612=ingresos.honorarios_facturados_612 or ingresos.ingresos_cobrados_resico,
        retenciones_isr_612=ingresos.retenciones_isr_612 or ingresos.retenciones_isr_resico,
        sueldos_y_salarios=ingresos.sueldos_y_salarios,
        isr_retenido_salarios=ingresos.isr_retenido_salarios,
    )

    ing_resico = IngresosAnuales(
        ingresos_cobrados_resico=ingresos.ingresos_cobrados_resico or ingresos.honorarios_facturados_612,
        retenciones_isr_resico=ingresos.retenciones_isr_resico or ingresos.retenciones_isr_612,
        sueldos_y_salarios=ingresos.sueldos_y_salarios,
        isr_retenido_salarios=ingresos.isr_retenido_salarios,
    )

    r612 = calculate_annual_612(anio, ing_612, deducciones, personales, pagos_provisionales_612)
    r625 = calculate_annual_resico(anio, ing_resico, personales, pagos_provisionales_resico)

    ahorro = abs(r612.isr_total_ejercicio - r625.isr_total_ejercicio)

    total_ingresos = max(
        ingresos.honorarios_facturados_612,
        ingresos.ingresos_cobrados_resico,
        1,
    )

    if r612.isr_total_ejercicio < r625.isr_total_ejercicio:
        recomendado = "Régimen 612"
        razon = (
            f"612 te ahorra ${ahorro:,.0f}/año gracias a deducciones operativas de "
            f"${deducciones.total_operativas:,.0f} ({deducciones.total_operativas/total_ingresos*100:.0f}% de ingresos)."
        )
    else:
        recomendado = "RESICO (625)"
        razon = (
            f"RESICO te ahorra ${ahorro:,.0f}/año. "
            f"Tus deducciones ({deducciones.total_operativas/total_ingresos*100:.0f}% de ingresos) "
            f"no compensan la diferencia de tasas."
        )

    # Force 612 if above RESICO cap
    if total_ingresos > 3_500_000:
        recomendado = "Régimen 612 (obligatorio)"
        razon = f"Ingresos ${total_ingresos:,.0f} exceden tope RESICO $3,500,000."

    return {
        "anio": anio,
        "resultado_612": r612.to_dict(),
        "resultado_625": r625.to_dict(),
        "regimen_recomendado": recomendado,
        "ahorro_estimado": round(ahorro, 2),
        "explicacion": razon,
        "isr_612": round(r612.isr_total_ejercicio, 2),
        "isr_625": round(r625.isr_total_ejercicio, 2),
        "tasa_efectiva_612": r612.tasa_efectiva_isr,
        "tasa_efectiva_625": r625.tasa_efectiva_isr,
    }
