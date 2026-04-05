"""OpenDoc - Tax Calendar Engine (Calendario Fiscal).

Generates the complete fiscal obligation calendar for a Mexican doctor.
Knows EVERY deadline, EVERY filing, and proactively alerts before due dates.

This is the "brain" that tells the doctor:
- What to file
- When to file it
- Where to file it (SAT portal URL)
- What data is needed
- What happens if you miss it (multas)

Supports: Régimen 612, RESICO 625, and hybrid scenarios.

Based on: CFF 2026, LISR, LIVA, Ley del Seguro Social, RMF 2026.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from datetime import date, timedelta
import calendar


# ─── Enums ────────────────────────────────────────────────────────────

class Frecuencia(str, Enum):
    MENSUAL = "Mensual"
    BIMESTRAL = "Bimestral"
    TRIMESTRAL = "Trimestral"
    ANUAL = "Anual"
    EVENTUAL = "Eventual"


class Prioridad(str, Enum):
    CRITICA = "Crítica"       # Missing = multa + recargos
    ALTA = "Alta"             # Missing = audit risk
    MEDIA = "Media"           # Important but not fined directly
    BAJA = "Baja"             # Informative / optional


class EstadoObligacion(str, Enum):
    PENDIENTE = "Pendiente"
    EN_PROGRESO = "En Progreso"
    COMPLETADA = "Completada"
    VENCIDA = "Vencida"
    NO_APLICA = "No Aplica"


# ─── Obligation Definitions ──────────────────────────────────────────

@dataclass
class ObligacionFiscal:
    """A single fiscal obligation."""
    nombre: str
    descripcion: str
    frecuencia: str
    dia_limite: int                    # Day of month (17, 22, etc.)
    regimenes: list                    # ["612", "625"] or ["612"]
    prioridad: str
    portal_url: str = ""               # SAT portal URL
    fundamento: str = ""               # Legal basis
    multa_omision: str = ""            # Penalty for missing
    datos_necesarios: list = field(default_factory=list)
    notas: list = field(default_factory=list)
    aplica_resico: bool = True


@dataclass
class EventoCalendario:
    """A calendar event (specific date obligation)."""
    fecha: str                         # ISO date
    nombre: str
    descripcion: str
    prioridad: str
    estado: str = EstadoObligacion.PENDIENTE.value
    portal_url: str = ""
    regimen: str = ""
    dias_restantes: int = 0
    multa_omision: str = ""
    datos_necesarios: list = field(default_factory=list)
    notas: list = field(default_factory=list)


# ─── Master Obligation Catalog ───────────────────────────────────────

OBLIGACIONES_MENSUALES = [
    ObligacionFiscal(
        nombre="Pago Provisional ISR",
        descripcion="Declaración y pago provisional mensual de ISR (Personas Físicas)",
        frecuencia=Frecuencia.MENSUAL.value,
        dia_limite=17,
        regimenes=["612", "625"],
        prioridad=Prioridad.CRITICA.value,
        portal_url="https://wwwmat.sat.gob.mx/declaracion/23891/presenta-tu-declaracion-provisional-o-definitiva-de-impuestos-federales",
        fundamento="Art. 106 LISR (612), Art. 113-E LISR (RESICO)",
        multa_omision="Recargos 1.47% mensual + actualización + multa $1,810-$22,400 CFF Art. 82",
        datos_necesarios=[
            "Ingresos facturados del mes",
            "Deducciones autorizadas (solo 612)",
            "Retenciones ISR de Personas Morales",
            "Pagos provisionales anteriores (acumulado)",
        ],
        notas=["Base acumulada para 612", "Base mensual para RESICO"],
    ),
    ObligacionFiscal(
        nombre="Declaración Mensual IVA",
        descripcion="Declaración definitiva mensual de IVA",
        frecuencia=Frecuencia.MENSUAL.value,
        dia_limite=17,
        regimenes=["612"],
        prioridad=Prioridad.CRITICA.value,
        portal_url="https://wwwmat.sat.gob.mx/declaracion/23891/presenta-tu-declaracion-provisional-o-definitiva-de-impuestos-federales",
        fundamento="Art. 5-D LIVA",
        multa_omision="Recargos + multa CFF Art. 82",
        datos_necesarios=[
            "IVA causado (actos gravados al 16%)",
            "IVA acreditable (solo si tiene actos gravados)",
            "IVA retenido",
            "Actos exentos (servicios médicos)",
        ],
        notas=[
            "Mayoría de médicos: IVA $0 (servicios exentos Art. 15 LIVA)",
            "Estética/cosmética: SÍ causa IVA 16%",
        ],
        aplica_resico=False,
    ),
    ObligacionFiscal(
        nombre="DIOT",
        descripcion="Declaración Informativa de Operaciones con Terceros",
        frecuencia=Frecuencia.MENSUAL.value,
        dia_limite=17,
        regimenes=["612"],
        prioridad=Prioridad.ALTA.value,
        portal_url="https://pstcdi.clouda.sat.gob.mx",
        fundamento="Art. 32 LIVA",
        multa_omision="Multa $11,790-$23,570 por mes omitido (CFF Art. 81-XXVI)",
        datos_necesarios=[
            "CFDIs de gastos del mes (agrupados por RFC proveedor)",
            "IVA pagado por proveedor (16%, 8%, tasa 0%, exento)",
            "IVA retenido (si aplica)",
        ],
        notas=["RESICO está relevado (RMF regla 3.13.16)", "Nueva plataforma desde agosto 2025"],
        aplica_resico=False,
    ),
    ObligacionFiscal(
        nombre="Contabilidad Electrónica",
        descripcion="Envío mensual de balanza de comprobación al SAT",
        frecuencia=Frecuencia.MENSUAL.value,
        dia_limite=22,
        regimenes=["612"],
        prioridad=Prioridad.ALTA.value,
        portal_url="https://www.sat.gob.mx/aplicacion/42150/envia-tu-contabilidad-electronica",
        fundamento="Art. 28-III CFF, RMF 2.8.1.5",
        multa_omision="Multa $6,230-$18,680 (CFF Art. 84-H)",
        datos_necesarios=[
            "Catálogo de cuentas (XML)",
            "Balanza de comprobación mensual (XML)",
        ],
        notas=[
            "Plazo: día 22 del mes siguiente (3, 5, 8 del segundo mes siguiente para enero, feb, marzo)",
            "RESICO NO presenta contabilidad electrónica",
        ],
        aplica_resico=False,
    ),
    ObligacionFiscal(
        nombre="ISN Estatal (Nómina)",
        descripcion="Impuesto Sobre Nóminas estatal — solo si tiene empleados",
        frecuencia=Frecuencia.MENSUAL.value,
        dia_limite=22,
        regimenes=["612", "625"],
        prioridad=Prioridad.ALTA.value,
        portal_url="",
        fundamento="Ley de Hacienda estatal",
        multa_omision="Recargos + multas estatales",
        datos_necesarios=["Nómina del mes", "Total de remuneraciones pagadas"],
        notas=["Solo aplica si tiene empleados", "Tasa varía por estado (Guanajuato: 2.6%)"],
    ),
    ObligacionFiscal(
        nombre="Retención ISR Empleados",
        descripcion="Entero de ISR retenido a empleados",
        frecuencia=Frecuencia.MENSUAL.value,
        dia_limite=17,
        regimenes=["612", "625"],
        prioridad=Prioridad.CRITICA.value,
        portal_url="https://wwwmat.sat.gob.mx/declaracion/23891/presenta-tu-declaracion-provisional-o-definitiva-de-impuestos-federales",
        fundamento="Art. 96 LISR",
        multa_omision="Recargos + multa + posible delito de defraudación fiscal equiparada",
        datos_necesarios=["ISR retenido por nómina del mes"],
        notas=["Solo aplica si tiene empleados con nómina"],
    ),
]

OBLIGACIONES_BIMESTRALES = [
    ObligacionFiscal(
        nombre="Cuotas IMSS",
        descripcion="Pago bimestral de cuotas obrero-patronales IMSS",
        frecuencia=Frecuencia.BIMESTRAL.value,
        dia_limite=17,
        regimenes=["612", "625"],
        prioridad=Prioridad.CRITICA.value,
        portal_url="https://www.imss.gob.mx/patrones/sua",
        fundamento="Art. 39 Ley del Seguro Social",
        multa_omision="Recargos 1.47% mensual + capitalización de adeudo + posible embargo",
        datos_necesarios=[
            "SUA (Sistema Único de Autodeterminación) actualizado",
            "SBC de cada empleado",
            "Movimientos afiliatorios del bimestre",
        ],
        notas=[
            "Bimestres: ene-feb, mar-abr, may-jun, jul-ago, sep-oct, nov-dic",
            "Solo aplica si tiene empleados registrados en IMSS",
        ],
    ),
    ObligacionFiscal(
        nombre="Aportaciones INFONAVIT",
        descripcion="Pago bimestral de aportaciones patronales INFONAVIT",
        frecuencia=Frecuencia.BIMESTRAL.value,
        dia_limite=17,
        regimenes=["612", "625"],
        prioridad=Prioridad.CRITICA.value,
        portal_url="https://empresarios.infonavit.org.mx",
        fundamento="Art. 29 Ley INFONAVIT",
        multa_omision="Recargos + multa + embargo",
        datos_necesarios=["5% sobre SBC de cada empleado"],
        notas=["Se paga junto con IMSS vía SUA"],
    ),
]

OBLIGACIONES_ANUALES = [
    ObligacionFiscal(
        nombre="Declaración Anual PF",
        descripcion="Declaración anual de Impuesto Sobre la Renta",
        frecuencia=Frecuencia.ANUAL.value,
        dia_limite=30,  # April 30
        regimenes=["612", "625"],
        prioridad=Prioridad.CRITICA.value,
        portal_url="https://wwwmat.sat.gob.mx/declaracion/23891/presenta-tu-declaracion-provisional-o-definitiva-de-impuestos-federales",
        fundamento="Art. 150 LISR (612), Art. 113-F LISR (RESICO)",
        multa_omision="Multa $1,810-$22,400 + recargos sobre ISR no pagado",
        datos_necesarios=[
            "Ingresos anuales acumulados",
            "Deducciones autorizadas anuales (612)",
            "Deducciones personales (ambos regímenes)",
            "Retenciones ISR del ejercicio",
            "Pagos provisionales efectuados",
            "Constancias de retención de Personas Morales",
        ],
        notas=["Fecha límite: 30 de abril", "RESICO: declaración simplificada"],
    ),
    ObligacionFiscal(
        nombre="Constancias de Retención",
        descripcion="Emitir constancias de retención ISR a empleados",
        frecuencia=Frecuencia.ANUAL.value,
        dia_limite=15,  # February 15
        regimenes=["612", "625"],
        prioridad=Prioridad.ALTA.value,
        portal_url="",
        fundamento="Art. 99-III LISR",
        multa_omision="Multa CFF",
        datos_necesarios=["Nómina anual por empleado", "ISR retenido anual"],
        notas=["Solo si tiene empleados", "Fecha límite: 15 de febrero"],
    ),
    ObligacionFiscal(
        nombre="DIOT Anual (Resumen)",
        descripcion="Información de operaciones con terceros — resumen anual",
        frecuencia=Frecuencia.ANUAL.value,
        dia_limite=15,  # February 15
        regimenes=["612"],
        prioridad=Prioridad.ALTA.value,
        portal_url="https://pstcdi.clouda.sat.gob.mx",
        fundamento="Art. 32 LIVA",
        multa_omision="Multa por información incompleta",
        datos_necesarios=["DIOT mensual de los 12 meses"],
        notas=["Se genera automáticamente si se presentaron las mensuales"],
        aplica_resico=False,
    ),
    ObligacionFiscal(
        nombre="Actualización de e.firma",
        descripcion="Renovar certificado de e.firma (FIEL) antes del vencimiento",
        frecuencia=Frecuencia.EVENTUAL.value,
        dia_limite=0,
        regimenes=["612", "625"],
        prioridad=Prioridad.CRITICA.value,
        portal_url="https://www.sat.gob.mx/tramites/16703/renueva-tu-e.firma-(antes-firma-electronica)",
        fundamento="Art. 17-D CFF",
        multa_omision="Sin e.firma no puedes facturar ni declarar — paraliza tu actividad",
        datos_necesarios=[
            "e.firma vigente (para renovar en línea)",
            "O cita SAT (si ya venció)",
        ],
        notas=[
            "Vigencia: 4 años",
            "Renovable en línea hasta 1 año antes del vencimiento",
            "Si vence, requiere cita presencial SAT",
        ],
    ),
    ObligacionFiscal(
        nombre="Renovación CSD",
        descripcion="Renovar Certificado de Sello Digital para facturación",
        frecuencia=Frecuencia.EVENTUAL.value,
        dia_limite=0,
        regimenes=["612", "625"],
        prioridad=Prioridad.CRITICA.value,
        portal_url="https://aplicacionesc.mat.sat.gob.mx/certisat/",
        fundamento="Art. 29 CFF",
        multa_omision="Sin CSD vigente no puedes emitir CFDIs",
        datos_necesarios=["e.firma vigente", "CertiSAT web"],
        notas=["Vigencia: 4 años", "Renovable en línea con e.firma"],
    ),
]


# ─── Bimester Mapping ────────────────────────────────────────────────

BIMESTRES = {
    1: (1, 2, "Enero-Febrero"),
    2: (3, 4, "Marzo-Abril"),
    3: (5, 6, "Mayo-Junio"),
    4: (7, 8, "Julio-Agosto"),
    5: (9, 10, "Septiembre-Octubre"),
    6: (11, 12, "Noviembre-Diciembre"),
}


def _get_bimestre(mes: int) -> int:
    """Get bimester number (1-6) for a month."""
    return (mes + 1) // 2


def _bimestre_payment_month(bimestre: int) -> int:
    """Month when bimester payment is due (month after bimester ends)."""
    _, mes_fin, _ = BIMESTRES[bimestre]
    return mes_fin + 1 if mes_fin < 12 else 1


# ─── Calendar Generation ─────────────────────────────────────────────

def _adjust_deadline(anio: int, mes: int, dia: int) -> date:
    """Adjust deadline: if falls on weekend/holiday, next business day.

    Note: Official Mexican holidays are not exhaustive here.
    The SAT typically pushes to next business day.
    """
    # Cap day to last day of month
    last_day = calendar.monthrange(anio, mes)[1]
    dia_real = min(dia, last_day)

    fecha = date(anio, mes, dia_real)

    # If weekend, push to Monday
    while fecha.weekday() >= 5:  # 5=Saturday, 6=Sunday
        fecha += timedelta(days=1)

    return fecha


def generate_monthly_calendar(
    mes: int,
    anio: int,
    regimen: str = "612",
    tiene_empleados: bool = True,
    reference_date: Optional[date] = None,
) -> list[EventoCalendario]:
    """Generate all fiscal obligations for a specific month.

    Args:
        mes: Month (1-12) — the period being declared
        anio: Year
        regimen: "612" or "625"
        tiene_empleados: Whether doctor has employees
        reference_date: Today's date for calculating days remaining

    Returns:
        List of EventoCalendario sorted by date.
    """
    hoy = reference_date or date.today()
    eventos = []

    # Monthly obligations — due in the FOLLOWING month
    mes_pago = mes + 1 if mes < 12 else 1
    anio_pago = anio if mes < 12 else anio + 1

    for ob in OBLIGACIONES_MENSUALES:
        # Check if applies to this régimen
        if regimen not in ob.regimenes:
            continue

        # Skip employee-specific if no employees
        if not tiene_empleados and ob.nombre in [
            "ISN Estatal (Nómina)", "Retención ISR Empleados"
        ]:
            continue

        fecha = _adjust_deadline(anio_pago, mes_pago, ob.dia_limite)
        dias_restantes = (fecha - hoy).days

        estado = EstadoObligacion.PENDIENTE.value
        if dias_restantes < 0:
            estado = EstadoObligacion.VENCIDA.value
        elif dias_restantes <= 3:
            estado = EstadoObligacion.PENDIENTE.value  # Urgent but still pending

        eventos.append(EventoCalendario(
            fecha=fecha.isoformat(),
            nombre=ob.nombre,
            descripcion=f"{ob.descripcion} — Periodo: {_mes_nombre(mes)} {anio}",
            prioridad=ob.prioridad,
            estado=estado,
            portal_url=ob.portal_url,
            regimen=regimen,
            dias_restantes=dias_restantes,
            multa_omision=ob.multa_omision,
            datos_necesarios=ob.datos_necesarios,
            notas=ob.notas,
        ))

    # Bimonthly obligations — due month after bimester ends
    bim = _get_bimestre(mes)
    _, mes_fin_bim, nombre_bim = BIMESTRES[bim]

    if mes == mes_fin_bim and tiene_empleados:
        mes_pago_bim = _bimestre_payment_month(bim)
        anio_pago_bim = anio if mes_pago_bim > mes else anio + 1

        for ob in OBLIGACIONES_BIMESTRALES:
            if regimen not in ob.regimenes:
                continue

            fecha = _adjust_deadline(anio_pago_bim, mes_pago_bim, ob.dia_limite)
            dias_restantes = (fecha - hoy).days

            estado = EstadoObligacion.PENDIENTE.value
            if dias_restantes < 0:
                estado = EstadoObligacion.VENCIDA.value

            eventos.append(EventoCalendario(
                fecha=fecha.isoformat(),
                nombre=ob.nombre,
                descripcion=f"{ob.descripcion} — Bimestre: {nombre_bim} {anio}",
                prioridad=ob.prioridad,
                estado=estado,
                portal_url=ob.portal_url,
                regimen=regimen,
                dias_restantes=dias_restantes,
                multa_omision=ob.multa_omision,
                datos_necesarios=ob.datos_necesarios,
                notas=ob.notas,
            ))

    # Sort by date, then priority
    prioridad_orden = {
        Prioridad.CRITICA.value: 0,
        Prioridad.ALTA.value: 1,
        Prioridad.MEDIA.value: 2,
        Prioridad.BAJA.value: 3,
    }
    eventos.sort(key=lambda e: (e.fecha, prioridad_orden.get(e.prioridad, 9)))

    return eventos


def generate_annual_calendar(
    anio: int,
    regimen: str = "612",
    tiene_empleados: bool = True,
    reference_date: Optional[date] = None,
) -> list[EventoCalendario]:
    """Generate the full annual fiscal calendar.

    Args:
        anio: Year
        regimen: "612" or "625"
        tiene_empleados: Whether doctor has employees
        reference_date: Today's date

    Returns:
        All events for the year, sorted chronologically.
    """
    hoy = reference_date or date.today()
    eventos = []

    # All 12 months of monthly obligations
    for mes in range(1, 13):
        monthly = generate_monthly_calendar(
            mes, anio, regimen, tiene_empleados, hoy
        )
        eventos.extend(monthly)

    # Annual obligations
    for ob in OBLIGACIONES_ANUALES:
        if regimen not in ob.regimenes:
            continue
        if not tiene_empleados and ob.nombre == "Constancias de Retención":
            continue
        if not ob.aplica_resico and regimen == "625":
            continue

        # Determine month for annual obligations
        if ob.nombre == "Declaración Anual PF":
            fecha = _adjust_deadline(anio + 1, 4, 30)  # April 30 of next year
        elif ob.nombre == "Constancias de Retención":
            fecha = _adjust_deadline(anio + 1, 2, 15)  # Feb 15 of next year
        elif ob.nombre == "DIOT Anual (Resumen)":
            fecha = _adjust_deadline(anio + 1, 2, 15)
        else:
            continue  # Skip eventual obligations (e.firma, CSD)

        dias_restantes = (fecha - hoy).days
        estado = EstadoObligacion.VENCIDA.value if dias_restantes < 0 else EstadoObligacion.PENDIENTE.value

        eventos.append(EventoCalendario(
            fecha=fecha.isoformat(),
            nombre=ob.nombre,
            descripcion=f"{ob.descripcion} — Ejercicio {anio}",
            prioridad=ob.prioridad,
            estado=estado,
            portal_url=ob.portal_url,
            regimen=regimen,
            dias_restantes=dias_restantes,
            multa_omision=ob.multa_omision,
            datos_necesarios=ob.datos_necesarios,
            notas=ob.notas,
        ))

    # Deduplicate by (fecha, nombre)
    seen = set()
    unique = []
    for e in eventos:
        key = (e.fecha, e.nombre)
        if key not in seen:
            seen.add(key)
            unique.append(e)

    unique.sort(key=lambda e: e.fecha)
    return unique


def get_upcoming_deadlines(
    regimen: str = "612",
    tiene_empleados: bool = True,
    dias_adelante: int = 30,
    reference_date: Optional[date] = None,
) -> list[EventoCalendario]:
    """Get upcoming deadlines within N days.

    Args:
        regimen: "612" or "625"
        tiene_empleados: Whether doctor has employees
        dias_adelante: Look-ahead window in days
        reference_date: Today's date

    Returns:
        Upcoming events sorted by urgency.
    """
    hoy = reference_date or date.today()
    anio = hoy.year
    mes = hoy.month

    # Generate current and next month
    eventos = []
    for m_offset in range(3):  # Current + next 2 months
        m = ((mes - 1 + m_offset) % 12) + 1
        a = anio + ((mes - 1 + m_offset) // 12)
        monthly = generate_monthly_calendar(m, a, regimen, tiene_empleados, hoy)
        eventos.extend(monthly)

    # Filter to within window
    upcoming = [
        e for e in eventos
        if 0 <= e.dias_restantes <= dias_adelante
    ]

    # Sort by urgency (fewer days remaining first)
    upcoming.sort(key=lambda e: (e.dias_restantes, e.fecha))
    return upcoming


def get_overdue_obligations(
    regimen: str = "612",
    tiene_empleados: bool = True,
    reference_date: Optional[date] = None,
) -> list[EventoCalendario]:
    """Get overdue (vencidas) obligations.

    Args:
        regimen: "612" or "625"
        tiene_empleados: Whether doctor has employees
        reference_date: Today's date

    Returns:
        Overdue events sorted by how overdue they are.
    """
    hoy = reference_date or date.today()

    # Check current month and previous month
    eventos = []
    for m_offset in range(-2, 1):
        m = ((hoy.month - 1 + m_offset) % 12) + 1
        a = hoy.year + ((hoy.month - 1 + m_offset) // 12)
        monthly = generate_monthly_calendar(m, a, regimen, tiene_empleados, hoy)
        eventos.extend(monthly)

    overdue = [e for e in eventos if e.dias_restantes < 0]
    overdue.sort(key=lambda e: e.dias_restantes)  # Most overdue first
    return overdue


# ─── WhatsApp Formatting ─────────────────────────────────────────────

def _mes_nombre(mes: int) -> str:
    nombres = [
        "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]
    return nombres[mes] if 1 <= mes <= 12 else str(mes)


def format_monthly_calendar_whatsapp(
    mes: int,
    anio: int,
    regimen: str = "612",
    tiene_empleados: bool = True,
    reference_date: Optional[date] = None,
) -> str:
    """Generate WhatsApp-friendly monthly calendar."""
    eventos = generate_monthly_calendar(mes, anio, regimen, tiene_empleados, reference_date)

    lines = [
        f"━━━ CALENDARIO FISCAL {_mes_nombre(mes).upper()} {anio} ━━━",
        f"📋 Régimen: {regimen}",
        "",
    ]

    if not eventos:
        lines.append("Sin obligaciones este mes.")
        return "\n".join(lines)

    for e in eventos:
        icon = "🔴" if e.prioridad == Prioridad.CRITICA.value else "🟡" if e.prioridad == Prioridad.ALTA.value else "🟢"
        estado_icon = "⏰" if e.dias_restantes <= 5 and e.dias_restantes >= 0 else "❌" if e.dias_restantes < 0 else "📅"

        lines.append(f"{icon} {e.nombre}")
        lines.append(f"   {estado_icon} Fecha límite: {e.fecha}")

        if e.dias_restantes < 0:
            lines.append(f"   ⚠️ VENCIDA hace {abs(e.dias_restantes)} días")
        elif e.dias_restantes == 0:
            lines.append(f"   🚨 VENCE HOY")
        elif e.dias_restantes <= 5:
            lines.append(f"   ⏰ Faltan {e.dias_restantes} días")
        else:
            lines.append(f"   Faltan {e.dias_restantes} días")

        lines.append("")

    # Summary
    criticas = sum(1 for e in eventos if e.prioridad == Prioridad.CRITICA.value)
    vencidas = sum(1 for e in eventos if e.dias_restantes < 0)

    lines.append(f"📊 Total: {len(eventos)} obligaciones ({criticas} críticas)")
    if vencidas > 0:
        lines.append(f"🚨 {vencidas} VENCIDAS — regularizar inmediatamente")

    return "\n".join(lines)


def format_upcoming_whatsapp(
    regimen: str = "612",
    tiene_empleados: bool = True,
    dias_adelante: int = 30,
    reference_date: Optional[date] = None,
) -> str:
    """Format upcoming deadlines for WhatsApp."""
    hoy = reference_date or date.today()
    upcoming = get_upcoming_deadlines(regimen, tiene_empleados, dias_adelante, hoy)

    lines = [
        f"━━━ PRÓXIMOS VENCIMIENTOS ━━━",
        f"📅 Próximos {dias_adelante} días desde {hoy.isoformat()}",
        "",
    ]

    if not upcoming:
        lines.append("Sin vencimientos próximos. Todo en orden.")
        return "\n".join(lines)

    for e in upcoming:
        urgency = "🔴" if e.dias_restantes <= 3 else "🟡" if e.dias_restantes <= 7 else "📅"
        lines.append(f"{urgency} {e.nombre} — {e.fecha} ({e.dias_restantes} días)")

    return "\n".join(lines)
