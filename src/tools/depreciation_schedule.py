"""OpenDoc - Multi-Year Depreciation Schedule Generator.

Generates complete depreciation tables for a doctor's fixed assets,
showing year-by-year deductions from acquisition through full depreciation.

Extends the single-year calculation in deduction_optimizer.py to produce
full asset lifecycle schedules for fiscal planning.

Features:
- Multi-year depreciation table (per asset)
- Full asset registry schedule (all assets combined)
- Monthly deduction breakdown by asset
- Remaining useful life projections
- INPC adjustment support (inflation indexing)

Based on: Art. 31-38 LISR, Art. 36 reglamento LISR, RMF 2026.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import date
import math

from .deduction_optimizer import TASAS_DEPRECIACION, TasaDepreciacion


# ─── Data Classes ─────────────────────────────────────────────────────

@dataclass
class ActivoFijo:
    """A fixed asset in the doctor's registry."""
    nombre: str                           # "Ultrasonido GE Vivid", "MacBook Pro", etc.
    tipo_activo: str                      # Key in TASAS_DEPRECIACION
    moi: float                            # Monto Original de la Inversión (before IVA)
    fecha_adquisicion: str                # ISO date (YYYY-MM-DD)
    iva_pagado: float = 0.0              # IVA (added to MOI for doctors)
    meses_uso_previo: int = 0            # Months already depreciated
    estado: str = "activo"               # activo, vendido, baja
    fecha_baja: str = ""                 # ISO date if disposed
    valor_venta: float = 0.0            # Sale price if sold
    numero_factura: str = ""             # CFDI UUID for traceability
    notas: str = ""

    @property
    def moi_total(self) -> float:
        """MOI including non-creditable IVA."""
        return self.moi + self.iva_pagado

    @property
    def moi_deducible(self) -> float:
        """MOI after applying caps (e.g., $175K for vehicles)."""
        tasa = TASAS_DEPRECIACION.get(self.tipo_activo)
        if tasa and tasa.tope_moi and self.moi_total > tasa.tope_moi:
            return tasa.tope_moi
        return self.moi_total


@dataclass
class LineaDepreciacion:
    """A single year's depreciation line in the schedule."""
    anio: int
    mes_inicio: int                       # 1-12 (first month of depreciation this year)
    mes_fin: int                          # 1-12 (last month of depreciation this year)
    meses_depreciacion: int               # Months depreciated this year
    deduccion_anual: float                # Depreciation deduction this year
    deduccion_mensual: float              # Monthly rate
    acumulado_inicio: float               # Accumulated at start of year
    acumulado_fin: float                  # Accumulated at end of year
    pendiente: float                      # Remaining after this year
    porcentaje_depreciado: float          # % of MOI depreciated to date
    es_ultimo_anio: bool = False          # Is this the final year?


@dataclass
class TablaDepreciacion:
    """Complete depreciation schedule for a single asset."""
    activo: str                           # Asset name
    tipo_activo: str                      # Asset type key
    descripcion_tipo: str                 # Human-readable type
    moi_total: float
    moi_deducible: float
    tasa_anual: float                     # Annual depreciation rate %
    fecha_inicio: str                     # Depreciation start date
    vida_util_anos: int                   # Estimated useful life
    lineas: list = field(default_factory=list)  # List of LineaDepreciacion
    fundamento: str = ""
    excedente_no_deducible: float = 0.0   # Amount above cap (never deducible)

    @property
    def total_deducido(self) -> float:
        if not self.lineas:
            return 0.0
        return self.lineas[-1].acumulado_fin

    @property
    def anios_restantes(self) -> int:
        return sum(1 for l in self.lineas if not l.es_ultimo_anio or l.pendiente > 0)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def resumen_whatsapp(self) -> str:
        """WhatsApp-friendly depreciation summary."""
        lines = [
            f"━━━ DEPRECIACIÓN: {self.activo} ━━━",
            f"📦 {self.descripcion_tipo}",
            f"💰 MOI: ${self.moi_total:,.2f}",
        ]
        if self.excedente_no_deducible > 0:
            lines.append(f"⚠️ Tope: ${self.moi_deducible:,.2f} (excedente ${self.excedente_no_deducible:,.2f} NO deducible)")
        lines.extend([
            f"📉 Tasa: {self.tasa_anual:.0f}% anual ({self.fundamento})",
            f"📅 Vida útil: {self.vida_util_anos} años",
            "",
        ])

        for l in self.lineas:
            icon = "✅" if l.es_ultimo_anio else "📊"
            lines.append(
                f"{icon} {l.anio}: ${l.deduccion_anual:,.2f} "
                f"({l.meses_depreciacion} meses) — {l.porcentaje_depreciado:.0f}% acum."
            )

        if self.lineas:
            last = self.lineas[-1]
            lines.append(f"\n💵 Total deducido: ${last.acumulado_fin:,.2f}")
            if last.pendiente > 0:
                lines.append(f"📌 Pendiente: ${last.pendiente:,.2f}")

        return "\n".join(lines)


@dataclass
class ResumenRegistro:
    """Summary of all assets in the registry."""
    total_activos: int = 0
    total_moi: float = 0.0
    total_moi_deducible: float = 0.0
    deduccion_anual_total: float = 0.0    # Current year's total depreciation
    deduccion_mensual_total: float = 0.0  # Current month's total depreciation
    total_acumulado: float = 0.0
    total_pendiente: float = 0.0
    tablas: list = field(default_factory=list)  # List of TablaDepreciacion
    alertas: list = field(default_factory=list)
    anio_calculo: int = 2026

    def to_dict(self) -> dict:
        return asdict(self)

    def resumen_whatsapp(self) -> str:
        """WhatsApp summary of full asset registry."""
        lines = [
            f"━━━ REGISTRO DE ACTIVOS {self.anio_calculo} ━━━",
            f"📦 {self.total_activos} activo(s) registrado(s)",
            f"💰 MOI total: ${self.total_moi:,.2f}",
            f"📉 Deducción anual: ${self.deduccion_anual_total:,.2f}",
            f"   Deducción mensual: ${self.deduccion_mensual_total:,.2f}",
            f"📊 Acumulado deducido: ${self.total_acumulado:,.2f}",
            f"📌 Pendiente: ${self.total_pendiente:,.2f}",
        ]

        if self.tablas:
            lines.append("")
            for t in self.tablas:
                pct = (t.total_deducido / t.moi_deducible * 100) if t.moi_deducible > 0 else 0
                lines.append(
                    f"   • {t.activo}: ${t.moi_deducible:,.0f} "
                    f"@ {t.tasa_anual:.0f}% — {pct:.0f}% depreciado"
                )

        if self.alertas:
            lines.append("")
            for a in self.alertas:
                lines.append(f"🚨 {a}")

        return "\n".join(lines)


# ─── Core Functions ───────────────────────────────────────────────────

def generate_depreciation_schedule(
    activo: ActivoFijo,
    anio_hasta: Optional[int] = None,
) -> TablaDepreciacion:
    """Generate a complete multi-year depreciation schedule for one asset.

    Args:
        activo: The fixed asset to depreciate.
        anio_hasta: Last year to show in schedule (default: until fully depreciated).

    Returns:
        TablaDepreciacion with year-by-year breakdown.

    Raises:
        ValueError: If tipo_activo is not recognized.
    """
    if activo.tipo_activo not in TASAS_DEPRECIACION:
        valid = list(TASAS_DEPRECIACION.keys())
        raise ValueError(
            f"Tipo de activo desconocido: '{activo.tipo_activo}'. "
            f"Opciones: {valid}"
        )

    tasa_info = TASAS_DEPRECIACION[activo.tipo_activo]
    moi_total = activo.moi_total
    moi_deducible = activo.moi_deducible
    excedente = max(0, moi_total - moi_deducible)

    tasa = tasa_info.tasa_anual
    if tasa <= 0:
        # Special case: adecuaciones a arrendado (rate based on lease term)
        return TablaDepreciacion(
            activo=activo.nombre,
            tipo_activo=activo.tipo_activo,
            descripcion_tipo=tasa_info.descripcion,
            moi_total=moi_total,
            moi_deducible=moi_deducible,
            tasa_anual=0,
            fecha_inicio=activo.fecha_adquisicion,
            vida_util_anos=0,
            lineas=[],
            fundamento=tasa_info.fundamento,
            excedente_no_deducible=excedente,
        )

    deduccion_anual_completa = moi_deducible * (tasa / 100)
    deduccion_mensual = deduccion_anual_completa / 12

    # Parse acquisition date to determine first depreciation month
    try:
        fecha_adq = date.fromisoformat(activo.fecha_adquisicion)
        # Depreciation starts the month AFTER acquisition (Art. 31 LISR)
        anio_inicio = fecha_adq.year
        mes_inicio = fecha_adq.month + 1
        if mes_inicio > 12:
            mes_inicio = 1
            anio_inicio += 1
    except (ValueError, TypeError):
        anio_inicio = 2026
        mes_inicio = 1

    # Account for prior depreciation
    acumulado = deduccion_mensual * activo.meses_uso_previo
    if acumulado >= moi_deducible:
        acumulado = moi_deducible

    # Calculate schedule
    vida_util_meses = math.ceil(moi_deducible / deduccion_mensual) if deduccion_mensual > 0 else 0
    meses_restantes = vida_util_meses - activo.meses_uso_previo
    if meses_restantes < 0:
        meses_restantes = 0

    if anio_hasta is None:
        anio_hasta = anio_inicio + math.ceil(vida_util_meses / 12) + 1

    lineas = []
    pendiente = moi_deducible - acumulado
    anio_actual = anio_inicio
    mes_actual = mes_inicio
    meses_usados = activo.meses_uso_previo

    # Skip to the year where prior months end
    if activo.meses_uso_previo > 0:
        meses_skip = activo.meses_uso_previo
        while meses_skip > 0:
            meses_en_anio = 12 - mes_actual + 1
            if meses_skip >= meses_en_anio:
                meses_skip -= meses_en_anio
                anio_actual += 1
                mes_actual = 1
            else:
                mes_actual += meses_skip
                meses_skip = 0

    while pendiente > 0.01 and anio_actual <= anio_hasta:
        # Months available for depreciation this year
        meses_en_anio = 12 - mes_actual + 1

        # How much can we depreciate?
        deduccion_posible = deduccion_mensual * meses_en_anio
        deduccion_real = min(deduccion_posible, pendiente)
        meses_reales = math.ceil(deduccion_real / deduccion_mensual) if deduccion_mensual > 0 else 0
        meses_reales = min(meses_reales, meses_en_anio)

        acum_inicio = acumulado
        acumulado += deduccion_real
        pendiente = moi_deducible - acumulado
        if pendiente < 0.01:
            pendiente = 0.0

        pct = (acumulado / moi_deducible * 100) if moi_deducible > 0 else 0

        lineas.append(LineaDepreciacion(
            anio=anio_actual,
            mes_inicio=mes_actual,
            mes_fin=min(mes_actual + meses_reales - 1, 12),
            meses_depreciacion=meses_reales,
            deduccion_anual=round(deduccion_real, 2),
            deduccion_mensual=round(deduccion_mensual, 2),
            acumulado_inicio=round(acum_inicio, 2),
            acumulado_fin=round(acumulado, 2),
            pendiente=round(pendiente, 2),
            porcentaje_depreciado=round(pct, 1),
            es_ultimo_anio=pendiente < 0.01,
        ))

        anio_actual += 1
        mes_actual = 1  # Next year starts in January

    return TablaDepreciacion(
        activo=activo.nombre,
        tipo_activo=activo.tipo_activo,
        descripcion_tipo=tasa_info.descripcion,
        moi_total=round(moi_total, 2),
        moi_deducible=round(moi_deducible, 2),
        tasa_anual=tasa,
        fecha_inicio=activo.fecha_adquisicion,
        vida_util_anos=tasa_info.vida_util_anos,
        lineas=lineas,
        fundamento=tasa_info.fundamento,
        excedente_no_deducible=round(excedente, 2),
    )


def generate_asset_registry(
    activos: list,
    anio: int = 2026,
) -> ResumenRegistro:
    """Generate a full registry summary for all of a doctor's assets.

    Args:
        activos: List of ActivoFijo objects.
        anio: Current fiscal year for deduction calculations.

    Returns:
        ResumenRegistro with combined depreciation schedule.
    """
    tablas = []
    alertas = []

    total_moi = 0.0
    total_moi_ded = 0.0
    total_deduccion_anio = 0.0
    total_acumulado = 0.0
    total_pendiente = 0.0

    for activo in activos:
        if activo.estado != "activo":
            continue

        try:
            tabla = generate_depreciation_schedule(activo, anio_hasta=anio + 5)
        except ValueError as e:
            alertas.append(f"{activo.nombre}: {str(e)}")
            continue

        tablas.append(tabla)

        total_moi += tabla.moi_total
        total_moi_ded += tabla.moi_deducible

        # Find this year's deduction
        deduccion_este_anio = 0.0
        for linea in tabla.lineas:
            if linea.anio == anio:
                deduccion_este_anio = linea.deduccion_anual
                break

        total_deduccion_anio += deduccion_este_anio
        total_acumulado += tabla.total_deducido
        total_pendiente += (tabla.moi_deducible - tabla.total_deducido)

        # Alerts
        if tabla.excedente_no_deducible > 0:
            alertas.append(
                f"{activo.nombre}: ${tabla.excedente_no_deducible:,.0f} excede tope "
                f"y NUNCA será deducible."
            )

        # Check if fully depreciated
        # total_deducido only reflects schedule lines; if lineas is empty
        # but tasa > 0 and MOI > 0, asset was fully depreciated via prior use
        fully_depreciated = tabla.total_deducido >= tabla.moi_deducible - 0.01
        if not fully_depreciated and len(tabla.lineas) == 0 and tabla.tasa_anual > 0 and tabla.moi_deducible > 0:
            fully_depreciated = True
        if fully_depreciated:
            alertas.append(
                f"{activo.nombre}: Totalmente depreciado. "
                f"Considerar reemplazo o baja del registro."
            )

    return ResumenRegistro(
        total_activos=len(tablas),
        total_moi=round(total_moi, 2),
        total_moi_deducible=round(total_moi_ded, 2),
        deduccion_anual_total=round(total_deduccion_anio, 2),
        deduccion_mensual_total=round(total_deduccion_anio / 12, 2),
        total_acumulado=round(total_acumulado, 2),
        total_pendiente=round(max(0, total_pendiente), 2),
        tablas=tablas,
        alertas=alertas,
        anio_calculo=anio,
    )


def get_monthly_depreciation(
    activos: list,
    mes: int,
    anio: int = 2026,
) -> dict:
    """Get the total monthly depreciation for a specific month.

    Useful for feeding into monthly_tax_calculator.DeduccionesMensuales.depreciacion.

    Args:
        activos: List of ActivoFijo.
        mes: Month (1-12).
        anio: Year.

    Returns:
        Dict with total and per-asset breakdown:
        {
            "total": float,
            "desglose": [{"activo": str, "monto": float}, ...],
            "mes": int, "anio": int,
        }
    """
    desglose = []
    total = 0.0

    for activo in activos:
        if activo.estado != "activo":
            continue

        try:
            tabla = generate_depreciation_schedule(activo, anio_hasta=anio)
        except ValueError:
            continue

        for linea in tabla.lineas:
            if linea.anio == anio and linea.mes_inicio <= mes <= linea.mes_fin:
                monto = linea.deduccion_mensual
                desglose.append({"activo": activo.nombre, "monto": round(monto, 2)})
                total += monto
                break

    return {
        "total": round(total, 2),
        "desglose": desglose,
        "mes": mes,
        "anio": anio,
    }
