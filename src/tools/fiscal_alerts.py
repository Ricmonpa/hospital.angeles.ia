"""OpenDoc - Fiscal Alerts / Watchdog Engine.

Proactive alert system that monitors the doctor's fiscal health.
Detects risks, approaching deadlines, and compliance gaps BEFORE they become problems.

Alert categories:
1. Certificate expiry (e.firma, CSD)
2. RESICO income cap approaching
3. Missing monthly filings
4. Unusual deduction patterns
5. Payment method risks
6. Employee compliance gaps

This is OpenDoc's "early warning system" — the doctor's fiscal guardian.

Based on: CFF, LISR, LIVA, Ley del Seguro Social, RMF 2026.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from datetime import date, timedelta


# ─── Enums ────────────────────────────────────────────────────────────

class NivelAlerta(str, Enum):
    URGENTE = "Urgente"           # Action needed immediately
    IMPORTANTE = "Importante"     # Action needed within days
    PREVENTIVA = "Preventiva"     # Heads up for future
    INFORMATIVA = "Informativa"   # FYI


class CategoriaAlerta(str, Enum):
    CERTIFICADOS = "Certificados"
    DECLARACIONES = "Declaraciones"
    INGRESOS = "Ingresos"
    DEDUCCIONES = "Deducciones"
    PAGOS = "Pagos"
    EMPLEADOS = "Empleados"
    REGIMEN = "Régimen"
    CFDI = "CFDI"


# ─── Data Classes ─────────────────────────────────────────────────────

@dataclass
class AlertaFiscal:
    """A single fiscal alert."""
    titulo: str
    mensaje: str
    nivel: str                    # NivelAlerta value
    categoria: str                # CategoriaAlerta value
    accion_requerida: str = ""
    fecha_limite: str = ""        # ISO date if applicable
    dias_restantes: int = -1      # Days until deadline (-1 = no deadline)
    fundamento: str = ""
    consecuencia: str = ""        # What happens if ignored
    url_portal: str = ""          # Where to resolve it


@dataclass
class ReporteAlertas:
    """Complete fiscal health report."""
    fecha_reporte: str
    regimen: str
    total_alertas: int = 0
    urgentes: int = 0
    importantes: int = 0
    preventivas: int = 0
    informativas: int = 0
    alertas: list = field(default_factory=list)
    score_salud_fiscal: int = 100  # 0-100

    def resumen_whatsapp(self) -> str:
        """WhatsApp-friendly alert summary."""
        if self.total_alertas == 0:
            return (
                "━━━ SALUD FISCAL ━━━\n"
                f"📅 {self.fecha_reporte}\n"
                f"✅ Score: {self.score_salud_fiscal}/100\n\n"
                "Sin alertas. Todo en orden."
            )

        icon = "🔴" if self.urgentes > 0 else "🟡" if self.importantes > 0 else "🟢"
        lines = [
            f"━━━ SALUD FISCAL ━━━",
            f"📅 {self.fecha_reporte}",
            f"{icon} Score: {self.score_salud_fiscal}/100",
            "",
        ]

        if self.urgentes > 0:
            lines.append(f"🔴 {self.urgentes} alertas urgentes")
        if self.importantes > 0:
            lines.append(f"🟡 {self.importantes} alertas importantes")
        if self.preventivas > 0:
            lines.append(f"🟢 {self.preventivas} alertas preventivas")

        lines.append("")

        for a in self.alertas:
            nivel_icon = {
                NivelAlerta.URGENTE.value: "🔴",
                NivelAlerta.IMPORTANTE.value: "🟡",
                NivelAlerta.PREVENTIVA.value: "🟢",
                NivelAlerta.INFORMATIVA.value: "ℹ️",
            }.get(a.nivel, "📌")

            lines.append(f"{nivel_icon} {a.titulo}")
            lines.append(f"   {a.mensaje}")
            if a.accion_requerida:
                lines.append(f"   → {a.accion_requerida}")
            if a.dias_restantes >= 0:
                lines.append(f"   ⏰ {a.dias_restantes} días")
            lines.append("")

        return "\n".join(lines)


# ─── Alert Generators ─────────────────────────────────────────────────

def check_certificate_expiry(
    efirma_expiry: Optional[date] = None,
    csd_expiry: Optional[date] = None,
    reference_date: Optional[date] = None,
) -> list[AlertaFiscal]:
    """Check e.firma and CSD certificate expiry."""
    hoy = reference_date or date.today()
    alertas = []

    for nombre, fecha_venc, url in [
        ("e.firma (FIEL)", efirma_expiry,
         "https://www.sat.gob.mx/tramites/16703/renueva-tu-e.firma-(antes-firma-electronica)"),
        ("CSD (Sello Digital)", csd_expiry,
         "https://aplicacionesc.mat.sat.gob.mx/certisat/"),
    ]:
        if not fecha_venc:
            continue

        dias = (fecha_venc - hoy).days

        if dias < 0:
            alertas.append(AlertaFiscal(
                titulo=f"{nombre} VENCIDO",
                mensaje=f"Tu {nombre} venció hace {abs(dias)} días. No puedes facturar ni declarar.",
                nivel=NivelAlerta.URGENTE.value,
                categoria=CategoriaAlerta.CERTIFICADOS.value,
                accion_requerida="Renovar inmediatamente. Si venció hace >1 año, requiere cita SAT presencial.",
                fecha_limite=fecha_venc.isoformat(),
                dias_restantes=dias,
                fundamento="Art. 17-D CFF",
                consecuencia="No puedes emitir CFDI ni presentar declaraciones.",
                url_portal=url,
            ))
        elif dias <= 30:
            alertas.append(AlertaFiscal(
                titulo=f"{nombre} por vencer",
                mensaje=f"Tu {nombre} vence en {dias} días ({fecha_venc.isoformat()}).",
                nivel=NivelAlerta.URGENTE.value,
                categoria=CategoriaAlerta.CERTIFICADOS.value,
                accion_requerida="Renovar AHORA en línea con tu e.firma vigente.",
                fecha_limite=fecha_venc.isoformat(),
                dias_restantes=dias,
                url_portal=url,
            ))
        elif dias <= 90:
            alertas.append(AlertaFiscal(
                titulo=f"{nombre} vence pronto",
                mensaje=f"Tu {nombre} vence el {fecha_venc.isoformat()} ({dias} días).",
                nivel=NivelAlerta.IMPORTANTE.value,
                categoria=CategoriaAlerta.CERTIFICADOS.value,
                accion_requerida="Programar renovación en los próximos 30 días.",
                fecha_limite=fecha_venc.isoformat(),
                dias_restantes=dias,
                url_portal=url,
            ))

    return alertas


def check_resico_income_cap(
    ingresos_acumulados: float,
    mes_actual: int,
    reference_date: Optional[date] = None,
) -> list[AlertaFiscal]:
    """Check if RESICO income cap ($3.5M) is approaching."""
    alertas = []
    TOPE_RESICO = 3_500_000

    if ingresos_acumulados <= 0:
        return alertas

    # Project annual income
    if mes_actual > 0:
        proyeccion_anual = ingresos_acumulados * (12 / mes_actual)
    else:
        proyeccion_anual = ingresos_acumulados * 12

    porcentaje_tope = (ingresos_acumulados / TOPE_RESICO) * 100

    if ingresos_acumulados >= TOPE_RESICO:
        alertas.append(AlertaFiscal(
            titulo="TOPE RESICO EXCEDIDO",
            mensaje=f"Ingresos acumulados ${ingresos_acumulados:,.0f} exceden tope de $3,500,000.",
            nivel=NivelAlerta.URGENTE.value,
            categoria=CategoriaAlerta.REGIMEN.value,
            accion_requerida="Cambiar a Régimen 612 para siguiente ejercicio. Consultar contador.",
            fundamento="Art. 113-E LISR",
            consecuencia="Expulsión automática a Régimen 612 el siguiente ejercicio.",
        ))
    elif proyeccion_anual > TOPE_RESICO:
        alertas.append(AlertaFiscal(
            titulo="Proyección excede tope RESICO",
            mensaje=(
                f"Ingresos al mes {mes_actual}: ${ingresos_acumulados:,.0f} ({porcentaje_tope:.0f}% del tope). "
                f"Proyección anual: ${proyeccion_anual:,.0f}."
            ),
            nivel=NivelAlerta.IMPORTANTE.value,
            categoria=CategoriaAlerta.REGIMEN.value,
            accion_requerida="Monitorear ingresos. Evaluar cambio preventivo a Régimen 612.",
            fundamento="Art. 113-E LISR",
        ))
    elif porcentaje_tope > 60:
        alertas.append(AlertaFiscal(
            titulo="Ingresos RESICO al {:.0f}% del tope".format(porcentaje_tope),
            mensaje=f"Acumulado: ${ingresos_acumulados:,.0f} de $3,500,000 ({porcentaje_tope:.0f}%).",
            nivel=NivelAlerta.PREVENTIVA.value,
            categoria=CategoriaAlerta.REGIMEN.value,
            accion_requerida="Seguir monitoreando.",
        ))

    return alertas


def check_deduction_patterns(
    ingresos_acumulados: float,
    deducciones_acumuladas: float,
    mes_actual: int,
) -> list[AlertaFiscal]:
    """Check for suspicious deduction patterns that could trigger SAT audit."""
    alertas = []

    if ingresos_acumulados <= 0:
        return alertas

    pct = (deducciones_acumuladas / ingresos_acumulados) * 100

    if pct > 90:
        alertas.append(AlertaFiscal(
            titulo="Deducciones excesivas",
            mensaje=f"Deducciones: {pct:.0f}% de ingresos (${deducciones_acumuladas:,.0f} / ${ingresos_acumulados:,.0f}).",
            nivel=NivelAlerta.URGENTE.value,
            categoria=CategoriaAlerta.DEDUCCIONES.value,
            accion_requerida="Revisar gastos. Proporción >90% genera revisiones SAT automáticas.",
            consecuencia="Auditoría SAT probable. Asegurar que TODOS los gastos sean estrictamente indispensables.",
        ))
    elif pct > 75:
        alertas.append(AlertaFiscal(
            titulo="Proporción deducciones alta",
            mensaje=f"Deducciones: {pct:.0f}% de ingresos. Zona de atención SAT.",
            nivel=NivelAlerta.IMPORTANTE.value,
            categoria=CategoriaAlerta.DEDUCCIONES.value,
            accion_requerida="Verificar que cada gasto tenga CFDI y sea estrictamente indispensable.",
        ))

    # Check if regime switch would be beneficial
    if pct < 30 and ingresos_acumulados < 3_500_000 * (mes_actual / 12 if mes_actual > 0 else 1):
        alertas.append(AlertaFiscal(
            titulo="RESICO podría ahorrarte impuestos",
            mensaje=f"Tus deducciones son solo {pct:.0f}% de ingresos. RESICO (1-2.5%) puede ser más económico.",
            nivel=NivelAlerta.INFORMATIVA.value,
            categoria=CategoriaAlerta.REGIMEN.value,
            accion_requerida="Evaluar cambio de régimen con el comparativo anual.",
        ))

    return alertas


def check_missing_filings(
    meses_declarados: list[int],
    anio: int,
    regimen: str = "612",
    reference_date: Optional[date] = None,
) -> list[AlertaFiscal]:
    """Check for missing monthly declarations."""
    hoy = reference_date or date.today()
    alertas = []

    # Determine which months should be filed by now
    # A month's declaration is due the 17th of the FOLLOWING month
    meses_obligatorios = []
    for mes in range(1, 13):
        mes_pago = mes + 1 if mes < 12 else 1
        anio_pago = anio if mes < 12 else anio + 1
        fecha_limite = date(anio_pago, mes_pago, 17)
        if hoy > fecha_limite:
            meses_obligatorios.append(mes)

    meses_faltantes = [m for m in meses_obligatorios if m not in meses_declarados]

    if meses_faltantes:
        nombres_meses = [
            "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ]
        lista = ", ".join(nombres_meses[m] for m in meses_faltantes)

        alertas.append(AlertaFiscal(
            titulo=f"{len(meses_faltantes)} declaraciones mensuales pendientes",
            mensaje=f"Meses sin declarar: {lista} {anio}.",
            nivel=NivelAlerta.URGENTE.value,
            categoria=CategoriaAlerta.DECLARACIONES.value,
            accion_requerida="Presentar declaraciones pendientes inmediatamente para evitar multas y recargos.",
            consecuencia=f"Multa $1,810-$22,400 por mes + recargos 1.47% mensual (CFF Art. 82).",
            url_portal="https://wwwmat.sat.gob.mx/declaracion/23891/presenta-tu-declaracion-provisional-o-definitiva-de-impuestos-federales",
        ))

    return alertas


def check_employee_compliance(
    tiene_empleados: bool,
    empleados_imss: int = 0,
    empleados_total: int = 0,
    ultimo_pago_imss_bimestre: int = 0,
    bimestre_actual: int = 0,
) -> list[AlertaFiscal]:
    """Check employee-related compliance."""
    alertas = []

    if not tiene_empleados:
        return alertas

    # Employees not registered in IMSS
    if empleados_total > empleados_imss:
        faltantes = empleados_total - empleados_imss
        alertas.append(AlertaFiscal(
            titulo=f"{faltantes} empleado(s) sin registro IMSS",
            mensaje=f"Tienes {empleados_total} empleados pero solo {empleados_imss} en IMSS.",
            nivel=NivelAlerta.URGENTE.value,
            categoria=CategoriaAlerta.EMPLEADOS.value,
            accion_requerida="Registrar empleados faltantes en IMSS dentro de 5 días hábiles.",
            consecuencia="Multa de 20-350 VSMMGVZG ($5,576-$97,580) por empleado no registrado.",
            fundamento="Art. 304 Ley del Seguro Social",
        ))

    # IMSS bimonthly payment lag
    if bimestre_actual > 0 and ultimo_pago_imss_bimestre > 0:
        bimestres_atrasados = bimestre_actual - ultimo_pago_imss_bimestre
        if bimestres_atrasados > 1:
            alertas.append(AlertaFiscal(
                titulo=f"IMSS: {bimestres_atrasados} bimestres atrasados",
                mensaje=f"Último pago: bimestre {ultimo_pago_imss_bimestre}. Actual: {bimestre_actual}.",
                nivel=NivelAlerta.URGENTE.value,
                categoria=CategoriaAlerta.EMPLEADOS.value,
                accion_requerida="Pagar cuotas IMSS atrasadas + recargos.",
                consecuencia="Capitalización del adeudo + embargo posible.",
            ))

    return alertas


# ─── Main Health Check ────────────────────────────────────────────────

def generate_fiscal_health_report(
    regimen: str = "612",
    # Certificate dates
    efirma_expiry: Optional[date] = None,
    csd_expiry: Optional[date] = None,
    # Income data
    ingresos_acumulados: float = 0.0,
    deducciones_acumuladas: float = 0.0,
    mes_actual: int = 0,
    # Declarations
    meses_declarados: Optional[list[int]] = None,
    anio: int = 2026,
    # Employees
    tiene_empleados: bool = False,
    empleados_imss: int = 0,
    empleados_total: int = 0,
    # Reference
    reference_date: Optional[date] = None,
) -> ReporteAlertas:
    """Generate comprehensive fiscal health report.

    Runs ALL alert checks and produces a unified report.

    Returns:
        ReporteAlertas with all findings and health score.
    """
    hoy = reference_date or date.today()
    all_alerts = []

    # 1. Certificate checks
    all_alerts.extend(check_certificate_expiry(efirma_expiry, csd_expiry, hoy))

    # 2. RESICO cap
    if regimen == "625":
        all_alerts.extend(check_resico_income_cap(ingresos_acumulados, mes_actual, hoy))

    # 3. Deduction patterns (612 only)
    if regimen == "612" and ingresos_acumulados > 0:
        all_alerts.extend(check_deduction_patterns(
            ingresos_acumulados, deducciones_acumuladas, mes_actual
        ))

    # 4. Missing filings
    if meses_declarados is not None:
        all_alerts.extend(check_missing_filings(
            meses_declarados, anio, regimen, hoy
        ))

    # 5. Employee compliance
    if tiene_empleados:
        all_alerts.extend(check_employee_compliance(
            tiene_empleados, empleados_imss, empleados_total
        ))

    # Sort by severity
    nivel_orden = {
        NivelAlerta.URGENTE.value: 0,
        NivelAlerta.IMPORTANTE.value: 1,
        NivelAlerta.PREVENTIVA.value: 2,
        NivelAlerta.INFORMATIVA.value: 3,
    }
    all_alerts.sort(key=lambda a: nivel_orden.get(a.nivel, 9))

    # Count
    urgentes = sum(1 for a in all_alerts if a.nivel == NivelAlerta.URGENTE.value)
    importantes = sum(1 for a in all_alerts if a.nivel == NivelAlerta.IMPORTANTE.value)
    preventivas = sum(1 for a in all_alerts if a.nivel == NivelAlerta.PREVENTIVA.value)
    informativas = sum(1 for a in all_alerts if a.nivel == NivelAlerta.INFORMATIVA.value)

    # Health score
    score = 100 - (urgentes * 25) - (importantes * 10) - (preventivas * 3)
    score = max(0, min(100, score))

    return ReporteAlertas(
        fecha_reporte=hoy.isoformat(),
        regimen=regimen,
        total_alertas=len(all_alerts),
        urgentes=urgentes,
        importantes=importantes,
        preventivas=preventivas,
        informativas=informativas,
        alertas=all_alerts,
        score_salud_fiscal=score,
    )
