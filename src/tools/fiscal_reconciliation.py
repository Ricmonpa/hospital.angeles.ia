"""OpenDoc - Fiscal Reconciliation Engine.

Verifies that monthly provisional payments reconcile with the annual declaration.
Detects discrepancies, missing months, and calculation errors BEFORE filing.

This is the doctor's "internal audit" — catches mistakes the SAT would catch.

Reconciliation checks:
1. Sum of 12 monthly incomes == annual income
2. Sum of 12 monthly deductions == annual deductions
3. Sum of ISR provisionals == annual provisionals credited
4. ISR annual calculated matches expected based on monthly data
5. Retentions consistency across months
6. IVA annual reconciliation

Based on: LISR Art. 106 (provisionals), Art. 150-152 (annual), RMF 2026.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────────

class NivelDiscrepancia(str, Enum):
    """Severity of a reconciliation discrepancy."""
    CRITICA = "Crítica"           # Will cause SAT rejection
    IMPORTANTE = "Importante"     # Likely audit trigger
    MENOR = "Menor"               # Rounding or timing
    INFORMATIVA = "Informativa"   # FYI


class AreaReconciliacion(str, Enum):
    """Area of the reconciliation check."""
    INGRESOS = "Ingresos"
    DEDUCCIONES = "Deducciones"
    ISR = "ISR"
    IVA = "IVA"
    RETENCIONES = "Retenciones"
    MESES = "Meses"


# ─── Data Classes ─────────────────────────────────────────────────────

@dataclass
class Discrepancia:
    """A single reconciliation discrepancy."""
    area: str                             # AreaReconciliacion value
    nivel: str                            # NivelDiscrepancia value
    descripcion: str
    monto_mensual: float = 0.0            # Sum from monthly data
    monto_anual: float = 0.0              # Value in annual declaration
    diferencia: float = 0.0               # Absolute difference
    mes_afectado: int = 0                 # Specific month (0 = all year)
    accion_requerida: str = ""


@dataclass
class MesConciliado:
    """Reconciliation data for a single month."""
    mes: int
    tiene_datos: bool = False
    ingresos: float = 0.0
    deducciones: float = 0.0
    isr_causado: float = 0.0
    isr_pagado: float = 0.0              # Provisional payment made
    retenciones_isr: float = 0.0
    iva_causado: float = 0.0
    iva_pagado: float = 0.0


@dataclass
class ResultadoConciliacion:
    """Complete reconciliation result."""
    anio: int
    regimen: str
    es_conciliado: bool = True            # True if no critical discrepancies

    # Totals from monthly data
    ingresos_mensuales_total: float = 0.0
    deducciones_mensuales_total: float = 0.0
    isr_provisionales_total: float = 0.0
    retenciones_mensuales_total: float = 0.0
    iva_pagado_total: float = 0.0

    # Totals from annual declaration
    ingresos_anual: float = 0.0
    deducciones_anual: float = 0.0
    isr_ejercicio: float = 0.0
    provisionales_acreditados: float = 0.0
    retenciones_anual: float = 0.0

    # Computed
    isr_a_cargo_esperado: float = 0.0
    isr_a_favor_esperado: float = 0.0

    # Analysis
    meses_presentados: int = 0
    meses_faltantes: list = field(default_factory=list)
    discrepancias: list = field(default_factory=list)  # List of Discrepancia
    meses: list = field(default_factory=list)           # List of MesConciliado
    score: int = 100                      # 0-100 reconciliation score

    # Alerts
    alertas: list = field(default_factory=list)
    notas: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def resumen_whatsapp(self) -> str:
        """WhatsApp-friendly reconciliation summary."""
        icon = "✅" if self.es_conciliado else "❌"
        lines = [
            f"━━━ CONCILIACIÓN FISCAL {self.anio} ━━━",
            f"{icon} Score: {self.score}/100",
            f"📋 Régimen: {self.regimen}",
            "",
            f"📊 Meses presentados: {self.meses_presentados}/12",
        ]

        if self.meses_faltantes:
            faltantes = ", ".join(str(m) for m in self.meses_faltantes)
            lines.append(f"🚨 Meses faltantes: {faltantes}")

        lines.extend([
            "",
            "── Ingresos ──",
            f"   Mensual acumulado: ${self.ingresos_mensuales_total:,.2f}",
            f"   Declaración anual: ${self.ingresos_anual:,.2f}",
            f"   Diferencia: ${abs(self.ingresos_mensuales_total - self.ingresos_anual):,.2f}",
            "",
            "── ISR ──",
            f"   Provisionales pagados: ${self.isr_provisionales_total:,.2f}",
            f"   ISR del ejercicio: ${self.isr_ejercicio:,.2f}",
        ])

        if self.isr_a_cargo_esperado > 0:
            lines.append(f"   💸 A cargo estimado: ${self.isr_a_cargo_esperado:,.2f}")
        elif self.isr_a_favor_esperado > 0:
            lines.append(f"   ✅ A favor estimado: ${self.isr_a_favor_esperado:,.2f}")

        if self.discrepancias:
            lines.append("")
            criticas = [d for d in self.discrepancias if d.nivel == NivelDiscrepancia.CRITICA.value]
            importantes = [d for d in self.discrepancias if d.nivel == NivelDiscrepancia.IMPORTANTE.value]
            menores = [d for d in self.discrepancias if d.nivel == NivelDiscrepancia.MENOR.value]

            if criticas:
                lines.append(f"🔴 {len(criticas)} discrepancia(s) crítica(s)")
            if importantes:
                lines.append(f"🟡 {len(importantes)} discrepancia(s) importante(s)")
            if menores:
                lines.append(f"🟢 {len(menores)} discrepancia(s) menor(es)")

            lines.append("")
            for d in self.discrepancias[:5]:  # Show top 5
                icon = "🔴" if d.nivel == "Crítica" else "🟡" if d.nivel == "Importante" else "🟢"
                lines.append(f"{icon} {d.descripcion}")
                if d.accion_requerida:
                    lines.append(f"   ➡️ {d.accion_requerida}")

        if self.alertas:
            lines.append("")
            for a in self.alertas:
                lines.append(f"🚨 {a}")

        return "\n".join(lines)


MESES_NOMBRES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


# ─── Core Functions ───────────────────────────────────────────────────

def reconcile_fiscal_year(
    datos_mensuales: list,
    datos_anuales: dict,
    regimen: str = "612",
    tolerancia: float = 1.0,
) -> ResultadoConciliacion:
    """Reconcile monthly provisionals against annual declaration.

    Args:
        datos_mensuales: List of 1-12 dicts, each representing a month's
            provisional data. Keys: mes, ingresos, deducciones, isr_causado,
            isr_pagado, retenciones_isr, iva_causado, iva_pagado.
            Missing months are detected.
        datos_anuales: Dict with annual declaration data. Keys:
            ingresos_totales, deducciones_operativas, isr_total_ejercicio,
            pagos_provisionales, retenciones_isr, isr_a_cargo, isr_a_favor.
        regimen: "612" or "625"
        tolerancia: Maximum acceptable difference before flagging (default $1.00
            to account for rounding).

    Returns:
        ResultadoConciliacion with full analysis.
    """
    anio = datos_anuales.get("anio", 2026)

    # Build monthly index
    meses_dict = {}
    for d in datos_mensuales:
        m = d.get("mes", 0)
        if 1 <= m <= 12:
            meses_dict[m] = d

    # Build MesConciliado list
    meses_list = []
    for m in range(1, 13):
        if m in meses_dict:
            d = meses_dict[m]
            meses_list.append(MesConciliado(
                mes=m,
                tiene_datos=True,
                ingresos=d.get("ingresos", 0.0),
                deducciones=d.get("deducciones", 0.0),
                isr_causado=d.get("isr_causado", 0.0),
                isr_pagado=d.get("isr_pagado", 0.0),
                retenciones_isr=d.get("retenciones_isr", 0.0),
                iva_causado=d.get("iva_causado", 0.0),
                iva_pagado=d.get("iva_pagado", 0.0),
            ))
        else:
            meses_list.append(MesConciliado(mes=m, tiene_datos=False))

    # Calculate monthly totals
    meses_presentados = sum(1 for mc in meses_list if mc.tiene_datos)
    meses_faltantes = [mc.mes for mc in meses_list if not mc.tiene_datos]

    ing_mensual = sum(mc.ingresos for mc in meses_list)
    ded_mensual = sum(mc.deducciones for mc in meses_list)
    isr_prov_total = sum(mc.isr_pagado for mc in meses_list)
    ret_mensual = sum(mc.retenciones_isr for mc in meses_list)
    iva_pagado = sum(mc.iva_pagado for mc in meses_list)

    # Annual values
    ing_anual = datos_anuales.get("ingresos_totales", 0.0)
    ded_anual = datos_anuales.get("deducciones_operativas", 0.0)
    isr_ejercicio = datos_anuales.get("isr_total_ejercicio", 0.0)
    prov_acreditados = datos_anuales.get("pagos_provisionales", 0.0)
    ret_anual = datos_anuales.get("retenciones_isr", 0.0)
    a_cargo = datos_anuales.get("isr_a_cargo", 0.0)
    a_favor = datos_anuales.get("isr_a_favor", 0.0)

    # Expected ISR result
    isr_neto = isr_ejercicio - isr_prov_total - ret_mensual
    esperado_cargo = max(0, isr_neto)
    esperado_favor = max(0, -isr_neto)

    # Run reconciliation checks
    discrepancias = []
    alertas = []
    notas = []

    # Check 1: Missing months
    if meses_faltantes:
        nivel = NivelDiscrepancia.CRITICA if len(meses_faltantes) >= 3 else NivelDiscrepancia.IMPORTANTE
        nombres = [MESES_NOMBRES[m] for m in meses_faltantes]
        discrepancias.append(Discrepancia(
            area=AreaReconciliacion.MESES.value,
            nivel=nivel.value,
            descripcion=f"{len(meses_faltantes)} mes(es) sin datos: {', '.join(nombres)}",
            accion_requerida="Obtener datos de provisionales faltantes antes de la anual",
        ))

    # Check 2: Income reconciliation
    diff_ingresos = abs(ing_mensual - ing_anual)
    if diff_ingresos > tolerancia:
        nivel = NivelDiscrepancia.CRITICA if diff_ingresos > ing_anual * 0.05 else NivelDiscrepancia.IMPORTANTE
        discrepancias.append(Discrepancia(
            area=AreaReconciliacion.INGRESOS.value,
            nivel=nivel.value,
            descripcion=(
                f"Ingresos mensuales (${ing_mensual:,.2f}) no cuadran con "
                f"anual (${ing_anual:,.2f}). Diferencia: ${diff_ingresos:,.2f}"
            ),
            monto_mensual=ing_mensual,
            monto_anual=ing_anual,
            diferencia=diff_ingresos,
            accion_requerida="Verificar CFDIs emitidos contra acumulado mensual",
        ))

    # Check 3: Deductions reconciliation (612 only)
    if regimen == "612":
        diff_ded = abs(ded_mensual - ded_anual)
        if diff_ded > tolerancia:
            nivel = NivelDiscrepancia.IMPORTANTE if diff_ded > 1000 else NivelDiscrepancia.MENOR
            discrepancias.append(Discrepancia(
                area=AreaReconciliacion.DEDUCCIONES.value,
                nivel=nivel.value,
                descripcion=(
                    f"Deducciones mensuales (${ded_mensual:,.2f}) difieren de "
                    f"anual (${ded_anual:,.2f}). Diferencia: ${diff_ded:,.2f}"
                ),
                monto_mensual=ded_mensual,
                monto_anual=ded_anual,
                diferencia=diff_ded,
                accion_requerida="Revisar ajustes anuales a deducciones (depreciación, proporciones)",
            ))

    # Check 4: Provisionals paid vs credited in annual
    diff_prov = abs(isr_prov_total - prov_acreditados)
    if diff_prov > tolerancia:
        nivel = NivelDiscrepancia.CRITICA if diff_prov > 5000 else NivelDiscrepancia.IMPORTANTE
        discrepancias.append(Discrepancia(
            area=AreaReconciliacion.ISR.value,
            nivel=nivel.value,
            descripcion=(
                f"Provisionales pagados (${isr_prov_total:,.2f}) no coinciden con "
                f"acreditados en anual (${prov_acreditados:,.2f}). Diferencia: ${diff_prov:,.2f}"
            ),
            monto_mensual=isr_prov_total,
            monto_anual=prov_acreditados,
            diferencia=diff_prov,
            accion_requerida="Verificar acuses de pago de provisionales en portal SAT",
        ))

    # Check 5: Retentions
    diff_ret = abs(ret_mensual - ret_anual)
    if diff_ret > tolerancia:
        nivel = NivelDiscrepancia.IMPORTANTE if diff_ret > 1000 else NivelDiscrepancia.MENOR
        discrepancias.append(Discrepancia(
            area=AreaReconciliacion.RETENCIONES.value,
            nivel=nivel.value,
            descripcion=(
                f"Retenciones ISR mensuales (${ret_mensual:,.2f}) difieren de "
                f"anual (${ret_anual:,.2f}). Diferencia: ${diff_ret:,.2f}"
            ),
            monto_mensual=ret_mensual,
            monto_anual=ret_anual,
            diferencia=diff_ret,
            accion_requerida="Verificar constancias de retención de Personas Morales",
        ))

    # Check 6: ISR a cargo/favor consistency
    if a_cargo > 0:
        diff_cargo = abs(esperado_cargo - a_cargo)
        if diff_cargo > tolerancia:
            discrepancias.append(Discrepancia(
                area=AreaReconciliacion.ISR.value,
                nivel=NivelDiscrepancia.IMPORTANTE.value,
                descripcion=(
                    f"ISR a cargo esperado (${esperado_cargo:,.2f}) difiere del "
                    f"declarado (${a_cargo:,.2f}). Diferencia: ${diff_cargo:,.2f}"
                ),
                monto_mensual=esperado_cargo,
                monto_anual=a_cargo,
                diferencia=diff_cargo,
                accion_requerida="Revisar cálculo del ISR anual y deducciones personales",
            ))

    if a_favor > 0:
        diff_favor = abs(esperado_favor - a_favor)
        if diff_favor > tolerancia:
            discrepancias.append(Discrepancia(
                area=AreaReconciliacion.ISR.value,
                nivel=NivelDiscrepancia.MENOR.value,
                descripcion=(
                    f"ISR a favor esperado (${esperado_favor:,.2f}) difiere del "
                    f"declarado (${a_favor:,.2f}). Diferencia: ${diff_favor:,.2f}"
                ),
                monto_mensual=esperado_favor,
                monto_anual=a_favor,
                diferencia=diff_favor,
                accion_requerida="Diferencia puede deberse a deducciones personales no incluidas en provisionales",
            ))

    # Check 7: Monthly anomalies
    if meses_presentados >= 3:
        ingresos_meses = [mc.ingresos for mc in meses_list if mc.tiene_datos and mc.ingresos > 0]
        if ingresos_meses:
            promedio = sum(ingresos_meses) / len(ingresos_meses)
            for mc in meses_list:
                if mc.tiene_datos and mc.ingresos > 0:
                    if mc.ingresos > promedio * 3:
                        discrepancias.append(Discrepancia(
                            area=AreaReconciliacion.INGRESOS.value,
                            nivel=NivelDiscrepancia.INFORMATIVA.value,
                            descripcion=(
                                f"{MESES_NOMBRES[mc.mes]}: ingresos ${mc.ingresos:,.0f} son "
                                f"3× el promedio (${promedio:,.0f}). Verificar si es correcto."
                            ),
                            mes_afectado=mc.mes,
                        ))

    # Check 8: Zero-income months (for non-RESICO)
    for mc in meses_list:
        if mc.tiene_datos and mc.ingresos == 0 and mc.isr_pagado > 0:
            discrepancias.append(Discrepancia(
                area=AreaReconciliacion.ISR.value,
                nivel=NivelDiscrepancia.IMPORTANTE.value,
                descripcion=(
                    f"{MESES_NOMBRES[mc.mes]}: ISR pagado (${mc.isr_pagado:,.2f}) "
                    f"sin ingresos reportados."
                ),
                mes_afectado=mc.mes,
                accion_requerida="Verificar si hubo ingresos no registrados",
            ))

    # Notes
    if regimen == "625":
        notas.append("RESICO: Sin deducciones operativas. Conciliación solo de ingresos e ISR.")

    if meses_presentados == 12 and not discrepancias:
        notas.append("Conciliación perfecta: 12 meses cuadran con declaración anual.")

    # Effective rate analysis
    tasa_efectiva = (isr_ejercicio / ing_anual * 100) if ing_anual > 0 else 0
    if tasa_efectiva > 30:
        alertas.append(
            f"Tasa efectiva ISR: {tasa_efectiva:.1f}%. "
            f"Evaluar optimización de deducciones."
        )
    notas.append(f"Tasa efectiva ISR: {tasa_efectiva:.1f}%")

    # Score calculation
    score = 100
    for d in discrepancias:
        if d.nivel == NivelDiscrepancia.CRITICA.value:
            score -= 25
        elif d.nivel == NivelDiscrepancia.IMPORTANTE.value:
            score -= 10
        elif d.nivel == NivelDiscrepancia.MENOR.value:
            score -= 3
    score = max(0, score)

    es_conciliado = all(
        d.nivel != NivelDiscrepancia.CRITICA.value
        for d in discrepancias
    )

    return ResultadoConciliacion(
        anio=anio,
        regimen=regimen,
        es_conciliado=es_conciliado,
        ingresos_mensuales_total=round(ing_mensual, 2),
        deducciones_mensuales_total=round(ded_mensual, 2),
        isr_provisionales_total=round(isr_prov_total, 2),
        retenciones_mensuales_total=round(ret_mensual, 2),
        iva_pagado_total=round(iva_pagado, 2),
        ingresos_anual=round(ing_anual, 2),
        deducciones_anual=round(ded_anual, 2),
        isr_ejercicio=round(isr_ejercicio, 2),
        provisionales_acreditados=round(prov_acreditados, 2),
        retenciones_anual=round(ret_anual, 2),
        isr_a_cargo_esperado=round(esperado_cargo, 2),
        isr_a_favor_esperado=round(esperado_favor, 2),
        meses_presentados=meses_presentados,
        meses_faltantes=meses_faltantes,
        discrepancias=discrepancias,
        meses=meses_list,
        score=score,
        alertas=alertas,
        notas=notas,
    )


def quick_reconcile(
    ingresos_mensuales: list,
    ingreso_anual: float,
    isr_provisionales: list,
    isr_ejercicio: float,
) -> dict:
    """Quick reconciliation check with minimal inputs.

    Args:
        ingresos_mensuales: List of 12 monthly income amounts.
        ingreso_anual: Total annual income from declaration.
        isr_provisionales: List of 12 monthly ISR payments.
        isr_ejercicio: ISR del ejercicio from annual declaration.

    Returns:
        Dict with {cuadra_ingresos, cuadra_isr, diferencia_ingresos,
        diferencia_isr, meses_con_datos}.
    """
    sum_ingresos = sum(ingresos_mensuales)
    sum_isr = sum(isr_provisionales)
    meses_con_datos = sum(1 for x in ingresos_mensuales if x > 0)

    diff_ing = abs(sum_ingresos - ingreso_anual)
    diff_isr = abs(sum_isr - isr_ejercicio)

    return {
        "cuadra_ingresos": diff_ing < 1.0,
        "cuadra_isr": diff_isr < 1.0,
        "diferencia_ingresos": round(diff_ing, 2),
        "diferencia_isr": round(diff_isr, 2),
        "sum_ingresos_mensuales": round(sum_ingresos, 2),
        "sum_isr_provisionales": round(sum_isr, 2),
        "ingreso_anual": ingreso_anual,
        "isr_ejercicio": isr_ejercicio,
        "meses_con_datos": meses_con_datos,
    }
