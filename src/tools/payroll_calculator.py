"""OpenDoc - Payroll Calculator (Nómina, IMSS, INFONAVIT, SAR).

Calculates employer obligations for a doctor with employees:
- ISR withholding (Art. 96 LISR) on employee wages
- IMSS employer + employee quotas (cuotas obrero-patronales)
- INFONAVIT contribution (5% employer)
- SAR/Afore (2% employer)
- State payroll tax (ISN) — Guanajuato model

Typical doctor employees: 1-3 (secretary, nurse, cleaning staff).

Based on: LISR 2026, Ley del Seguro Social, Ley INFONAVIT, Ley Estatal ISN.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum
import math

from .fiscal_tables import (  # noqa: F401 — re-exported for backward compat
    UMA_DIARIA_2026,
    UMA_MENSUAL_2026,
    UMA_ANUAL_2026,
    SALARIO_MINIMO_DIARIO_2026,
    SALARIO_MINIMO_MENSUAL_2026,
    TOPE_SBC_25_UMA,
    TARIFA_ISR_MENSUAL,
    SUBSIDIO_EMPLEO_MENSUAL,
)


# ─── IMSS Quotas (Cuotas Obrero-Patronales 2026) ─────────────────────

@dataclass
class CuotaIMSS:
    """IMSS contribution rates for a single insurance branch."""
    nombre: str
    tasa_patronal: float   # % employer pays
    tasa_obrero: float     # % employee pays
    base: str              # "SBC" (Salario Base de Cotización) or "diferencia" or "fija"
    tope_uma: float = 25.0  # Maximum SBC in UMAs (25 for most branches)
    nota: str = ""


# IMSS 2026 rates — these are BIMONTHLY in law but we calculate monthly
CUOTAS_IMSS = {
    "riesgos_trabajo": CuotaIMSS(
        nombre="Riesgos de Trabajo",
        tasa_patronal=0.54355,  # Class II base (medical offices)
        tasa_obrero=0.0,
        base="SBC",
        nota="Prima de riesgo clase II (consultorio médico). Varía según siniestralidad.",
    ),
    "enfermedades_maternidad_especie_fija": CuotaIMSS(
        nombre="Enf. y Maternidad - Cuota Fija Patronal",
        tasa_patronal=20.40,  # % of UMA (not SBC!)
        tasa_obrero=0.0,
        base="fija",
        nota="20.40% de UMA diaria × días del mes. Solo patrón.",
    ),
    "enfermedades_maternidad_especie_excedente": CuotaIMSS(
        nombre="Enf. y Maternidad - Excedente sobre 3 UMA",
        tasa_patronal=1.10,
        tasa_obrero=0.40,
        base="diferencia",  # SBC - 3 UMA
        nota="Sobre la diferencia del SBC que exceda 3 UMA diarias.",
    ),
    "enfermedades_maternidad_dinero": CuotaIMSS(
        nombre="Enf. y Maternidad - Prestaciones en Dinero",
        tasa_patronal=0.70,
        tasa_obrero=0.25,
        base="SBC",
    ),
    "invalidez_vida": CuotaIMSS(
        nombre="Invalidez y Vida",
        tasa_patronal=1.75,
        tasa_obrero=0.625,
        base="SBC",
    ),
    "guarderias_ps": CuotaIMSS(
        nombre="Guarderías y Prestaciones Sociales",
        tasa_patronal=1.0,
        tasa_obrero=0.0,
        base="SBC",
    ),
    "retiro": CuotaIMSS(
        nombre="Retiro (SAR)",
        tasa_patronal=2.0,
        tasa_obrero=0.0,
        base="SBC",
        nota="2% patronal. Se deposita en Afore del trabajador.",
    ),
    "cesantia_vejez": CuotaIMSS(
        nombre="Cesantía en Edad Avanzada y Vejez",
        tasa_patronal=3.150,  # 2026 rate (increasing yearly per reforma)
        tasa_obrero=1.125,
        base="SBC",
        nota="Tasa patronal sube gradualmente hasta 2030 (reforma de pensiones).",
    ),
}

# INFONAVIT
INFONAVIT_TASA_PATRONAL = 5.0  # 5% of SBC — employer only

# State Payroll Tax (ISN) — Guanajuato
ISN_TASA_GTO = 2.3       # 2.3% base
ISN_SOBRETASA_SOCIAL = 0.2  # 0.2% desarrollo social
ISN_SOBRETASA_PAZ = 0.1     # 0.1% paz pública
ISN_TOTAL_GTO = ISN_TASA_GTO + ISN_SOBRETASA_SOCIAL + ISN_SOBRETASA_PAZ  # 2.6%


# ─── Data Classes ─────────────────────────────────────────────────────

@dataclass
class Empleado:
    """Employee payroll data."""
    nombre: str
    puesto: str = ""                    # "Enfermera", "Secretaria", etc.
    salario_mensual_bruto: float = 0.0
    salario_diario: float = 0.0         # Calculated if not provided
    sbc_diario: float = 0.0             # Salario Base de Cotización (SBC) diario
    dias_trabajados: int = 30           # Days in period
    tiene_infonavit: bool = True
    aguinaldo_dias: int = 15            # Minimum by law
    vacaciones_dias: int = 12           # First year minimum (LFT 2023+)
    prima_vacacional_pct: float = 25.0  # 25% minimum by law


@dataclass
class DesgloseCuotasIMSS:
    """Detailed IMSS contribution breakdown."""
    riesgos_trabajo_patron: float = 0.0
    enfermedad_fija_patron: float = 0.0
    enfermedad_excedente_patron: float = 0.0
    enfermedad_excedente_obrero: float = 0.0
    enfermedad_dinero_patron: float = 0.0
    enfermedad_dinero_obrero: float = 0.0
    invalidez_vida_patron: float = 0.0
    invalidez_vida_obrero: float = 0.0
    guarderias_patron: float = 0.0
    retiro_patron: float = 0.0
    cesantia_patron: float = 0.0
    cesantia_obrero: float = 0.0

    @property
    def total_patronal(self) -> float:
        return (self.riesgos_trabajo_patron + self.enfermedad_fija_patron +
                self.enfermedad_excedente_patron + self.enfermedad_dinero_patron +
                self.invalidez_vida_patron + self.guarderias_patron +
                self.retiro_patron + self.cesantia_patron)

    @property
    def total_obrero(self) -> float:
        return (self.enfermedad_excedente_obrero + self.enfermedad_dinero_obrero +
                self.invalidez_vida_obrero + self.cesantia_obrero)

    @property
    def total(self) -> float:
        return self.total_patronal + self.total_obrero


@dataclass
class NominaEmpleado:
    """Complete payroll calculation for one employee."""
    nombre: str
    puesto: str = ""

    # Gross pay
    salario_bruto: float = 0.0
    sbc_diario: float = 0.0
    dias: int = 30

    # ISR withholding
    base_gravable_isr: float = 0.0
    isr_antes_subsidio: float = 0.0
    subsidio_empleo: float = 0.0
    isr_a_retener: float = 0.0

    # IMSS employee share
    imss_obrero: float = 0.0

    # Net pay
    salario_neto: float = 0.0

    # Employer costs (on top of gross salary)
    imss_patronal: float = 0.0
    infonavit: float = 0.0
    isn_estatal: float = 0.0
    costo_total_patron: float = 0.0

    # Detail
    desglose_imss: Optional[DesgloseCuotasIMSS] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResumenNomina:
    """Summary payroll calculation for all employees."""
    mes: int
    anio: int
    rfc_patron: str

    # Totals
    num_empleados: int = 0
    total_salarios_brutos: float = 0.0
    total_isr_retenido: float = 0.0
    total_imss_patronal: float = 0.0
    total_imss_obrero: float = 0.0
    total_infonavit: float = 0.0
    total_isn: float = 0.0
    total_neto_empleados: float = 0.0
    total_costo_patron: float = 0.0

    # Per-employee detail
    empleados: list = field(default_factory=list)

    # Alerts
    alertas: list = field(default_factory=list)
    notas: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def resumen_whatsapp(self) -> str:
        """WhatsApp-friendly payroll summary."""
        mes_nombre = [
            "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
        ]
        nombre = mes_nombre[self.mes] if 1 <= self.mes <= 12 else str(self.mes)

        lines = [
            f"━━━ NÓMINA {nombre.upper()} {self.anio} ━━━",
            f"📋 Patrón: {self.rfc_patron}",
            f"👥 Empleados: {self.num_empleados}",
            "",
            "💰 RESUMEN:",
            f"   Salarios brutos: ${self.total_salarios_brutos:,.2f}",
            f"   ISR retenido: ${self.total_isr_retenido:,.2f}",
            f"   IMSS obrero: ${self.total_imss_obrero:,.2f}",
            f"   Neto a empleados: ${self.total_neto_empleados:,.2f}",
            "",
            "🏢 COSTO PATRONAL:",
            f"   IMSS patrón: ${self.total_imss_patronal:,.2f}",
            f"   INFONAVIT: ${self.total_infonavit:,.2f}",
            f"   ISN estatal: ${self.total_isn:,.2f}",
            f"   ═══════════════════",
            f"   💵 COSTO TOTAL: ${self.total_costo_patron:,.2f}",
        ]

        if self.empleados:
            lines.append("")
            lines.append("DETALLE POR EMPLEADO:")
            for e in self.empleados:
                if isinstance(e, dict):
                    nombre_e = e.get("nombre", "")
                    puesto = e.get("puesto", "")
                    bruto = e.get("salario_bruto", 0)
                    neto = e.get("salario_neto", 0)
                    costo = e.get("costo_total_patron", 0)
                else:
                    nombre_e = e.nombre
                    puesto = e.puesto
                    bruto = e.salario_bruto
                    neto = e.salario_neto
                    costo = e.costo_total_patron
                lines.append(
                    f"   • {nombre_e} ({puesto}): "
                    f"Bruto ${bruto:,.0f} → Neto ${neto:,.0f} "
                    f"(Costo patrón: ${costo:,.0f})"
                )

        if self.alertas:
            lines.append("")
            for a in self.alertas:
                lines.append(f"🚨 {a}")

        lines.extend([
            "",
            f"📅 ISR: enterar día 17 del mes siguiente",
            f"📅 IMSS: pago bimestral (17 del mes siguiente al bimestre)",
            f"📅 ISN: día 22 del mes siguiente",
        ])

        return "\n".join(lines)


# ─── Core Calculation Functions ───────────────────────────────────────

def _calculate_sbc(empleado: Empleado) -> float:
    """Calculate Salario Base de Cotización (SBC) diario.

    SBC = Salario diario + Factor de integración
    Factor = 1 + aguinaldo/365 + prima_vacacional * vacaciones/365

    Args:
        empleado: Employee data

    Returns:
        SBC diario (capped at 25 UMA if needed).
    """
    if empleado.sbc_diario > 0:
        return min(empleado.sbc_diario, TOPE_SBC_25_UMA)

    sd = empleado.salario_diario
    if sd <= 0:
        sd = empleado.salario_mensual_bruto / 30.4

    # Integration factor
    aguinaldo_factor = empleado.aguinaldo_dias / 365
    pv_factor = (empleado.prima_vacacional_pct / 100) * empleado.vacaciones_dias / 365
    factor_integracion = 1 + aguinaldo_factor + pv_factor

    sbc = sd * factor_integracion

    # Cap at 25 UMA
    return min(sbc, TOPE_SBC_25_UMA)


def calculate_isr_withholding(ingreso_mensual: float) -> dict:
    """Calculate ISR withholding for an employee (Art. 96 LISR).

    Applies the monthly ISR tariff minus employment subsidy.

    Args:
        ingreso_mensual: Monthly gross taxable income.

    Returns:
        Dict with isr_bruto, subsidio, isr_neto.
    """
    if ingreso_mensual <= 0:
        return {"isr_bruto": 0.0, "subsidio": 0.0, "isr_neto": 0.0}

    # Calculate ISR from tariff
    isr = 0.0
    for li, ls, cuota, tasa in TARIFA_ISR_MENSUAL:
        if li <= ingreso_mensual <= ls:
            excedente = ingreso_mensual - li
            isr = cuota + (excedente * tasa / 100)
            break
    else:
        last = TARIFA_ISR_MENSUAL[-1]
        excedente = ingreso_mensual - last[0]
        isr = last[2] + (excedente * last[3] / 100)

    # Calculate employment subsidy
    subsidio = 0.0
    for li, ls, sub in SUBSIDIO_EMPLEO_MENSUAL:
        if li <= ingreso_mensual <= ls:
            subsidio = sub
            break

    isr_neto = max(0, isr - subsidio)

    return {
        "isr_bruto": round(isr, 2),
        "subsidio": round(subsidio, 2),
        "isr_neto": round(isr_neto, 2),
    }


def calculate_imss_quotas(sbc_diario: float, dias: int = 30) -> DesgloseCuotasIMSS:
    """Calculate all IMSS employer + employee quotas.

    Args:
        sbc_diario: Salario Base de Cotización diario (already capped at 25 UMA)
        dias: Days in the period (usually 30)

    Returns:
        DesgloseCuotasIMSS with full breakdown.
    """
    desglose = DesgloseCuotasIMSS()

    # Base amounts
    sbc_mensual = sbc_diario * dias
    uma_mensual = UMA_DIARIA_2026 * dias

    # 1. Riesgos de Trabajo (patron only, on SBC)
    rt = CUOTAS_IMSS["riesgos_trabajo"]
    desglose.riesgos_trabajo_patron = round(sbc_mensual * rt.tasa_patronal / 100, 2)

    # 2. Enfermedad y Maternidad - Cuota Fija (patron only, on UMA!)
    ef = CUOTAS_IMSS["enfermedades_maternidad_especie_fija"]
    desglose.enfermedad_fija_patron = round(uma_mensual * ef.tasa_patronal / 100, 2)

    # 3. Enfermedad y Maternidad - Excedente (on SBC - 3 UMA)
    ee = CUOTAS_IMSS["enfermedades_maternidad_especie_excedente"]
    excedente_3uma = max(0, sbc_diario - (UMA_DIARIA_2026 * 3))
    base_excedente = excedente_3uma * dias
    desglose.enfermedad_excedente_patron = round(base_excedente * ee.tasa_patronal / 100, 2)
    desglose.enfermedad_excedente_obrero = round(base_excedente * ee.tasa_obrero / 100, 2)

    # 4. Enfermedad y Maternidad - Prestaciones en Dinero (on SBC)
    ed = CUOTAS_IMSS["enfermedades_maternidad_dinero"]
    desglose.enfermedad_dinero_patron = round(sbc_mensual * ed.tasa_patronal / 100, 2)
    desglose.enfermedad_dinero_obrero = round(sbc_mensual * ed.tasa_obrero / 100, 2)

    # 5. Invalidez y Vida (on SBC)
    iv = CUOTAS_IMSS["invalidez_vida"]
    desglose.invalidez_vida_patron = round(sbc_mensual * iv.tasa_patronal / 100, 2)
    desglose.invalidez_vida_obrero = round(sbc_mensual * iv.tasa_obrero / 100, 2)

    # 6. Guarderías y PS (patron only, on SBC)
    gp = CUOTAS_IMSS["guarderias_ps"]
    desglose.guarderias_patron = round(sbc_mensual * gp.tasa_patronal / 100, 2)

    # 7. Retiro/SAR (patron only, on SBC)
    ret = CUOTAS_IMSS["retiro"]
    desglose.retiro_patron = round(sbc_mensual * ret.tasa_patronal / 100, 2)

    # 8. Cesantía en Edad Avanzada y Vejez (on SBC)
    cv = CUOTAS_IMSS["cesantia_vejez"]
    desglose.cesantia_patron = round(sbc_mensual * cv.tasa_patronal / 100, 2)
    desglose.cesantia_obrero = round(sbc_mensual * cv.tasa_obrero / 100, 2)

    return desglose


def calculate_employee_payroll(
    empleado: Empleado,
    include_isn: bool = False,
    tasa_isn: float = ISN_TOTAL_GTO,
) -> NominaEmpleado:
    """Calculate complete payroll for one employee.

    Args:
        empleado: Employee data
        include_isn: Include state payroll tax (ISN)
        tasa_isn: State payroll tax rate (default: Guanajuato 2.6%)

    Returns:
        NominaEmpleado with all calculations.
    """
    # Calculate SBC
    sbc = _calculate_sbc(empleado)
    dias = empleado.dias_trabajados
    salario_bruto = empleado.salario_mensual_bruto

    if salario_bruto <= 0:
        salario_bruto = empleado.salario_diario * dias

    # ISR withholding
    isr_result = calculate_isr_withholding(salario_bruto)

    # IMSS quotas
    imss = calculate_imss_quotas(sbc, dias)

    # INFONAVIT (5% on SBC, patron only)
    infonavit = round(sbc * dias * INFONAVIT_TASA_PATRONAL / 100, 2) if empleado.tiene_infonavit else 0.0

    # ISN (state payroll tax)
    isn = round(salario_bruto * tasa_isn / 100, 2) if include_isn else 0.0

    # Net salary
    salario_neto = round(salario_bruto - isr_result["isr_neto"] - imss.total_obrero, 2)

    # Total employer cost
    costo_patron = round(salario_bruto + imss.total_patronal + infonavit + isn, 2)

    return NominaEmpleado(
        nombre=empleado.nombre,
        puesto=empleado.puesto,
        salario_bruto=salario_bruto,
        sbc_diario=round(sbc, 2),
        dias=dias,
        base_gravable_isr=salario_bruto,
        isr_antes_subsidio=isr_result["isr_bruto"],
        subsidio_empleo=isr_result["subsidio"],
        isr_a_retener=isr_result["isr_neto"],
        imss_obrero=imss.total_obrero,
        salario_neto=salario_neto,
        imss_patronal=imss.total_patronal,
        infonavit=infonavit,
        isn_estatal=isn,
        costo_total_patron=costo_patron,
        desglose_imss=imss,
    )


def calculate_payroll(
    mes: int,
    anio: int,
    rfc_patron: str,
    empleados: list[Empleado],
    include_isn: bool = False,
    tasa_isn: float = ISN_TOTAL_GTO,
) -> ResumenNomina:
    """Calculate complete payroll for all employees.

    Args:
        mes: Month (1-12)
        anio: Year
        rfc_patron: Doctor's RFC (employer)
        empleados: List of employees
        include_isn: Include state payroll tax
        tasa_isn: State payroll tax rate

    Returns:
        ResumenNomina with full payroll.
    """
    alertas = []
    notas = []

    nominas = []
    for emp in empleados:
        nomina = calculate_employee_payroll(emp, include_isn, tasa_isn)
        nominas.append(nomina)

    # Totals
    total_brutos = sum(n.salario_bruto for n in nominas)
    total_isr = sum(n.isr_a_retener for n in nominas)
    total_imss_patron = sum(n.imss_patronal for n in nominas)
    total_imss_obrero = sum(n.imss_obrero for n in nominas)
    total_infonavit = sum(n.infonavit for n in nominas)
    total_isn = sum(n.isn_estatal for n in nominas)
    total_neto = sum(n.salario_neto for n in nominas)
    total_costo = sum(n.costo_total_patron for n in nominas)

    # Alerts
    for n in nominas:
        if n.salario_bruto < SALARIO_MINIMO_MENSUAL_2026:
            alertas.append(
                f"{n.nombre}: Salario ${n.salario_bruto:,.2f} por debajo del "
                f"mínimo (${SALARIO_MINIMO_MENSUAL_2026:,.2f}/mes). "
                f"Ajustar inmediatamente."
            )

    if len(empleados) > 0:
        costo_extra_pct = ((total_costo - total_brutos) / total_brutos * 100) if total_brutos > 0 else 0
        notas.append(
            f"Costo patronal adicional: {costo_extra_pct:.1f}% sobre salarios brutos "
            f"(IMSS + INFONAVIT + ISN). "
            f"Por cada $1 de salario, pagas ~${1 + costo_extra_pct/100:.2f} total."
        )

    notas.append(
        "Nómina es 100% deducible en Régimen 612 (Art. 27 LISR). "
        "IMSS e INFONAVIT patronal también son deducibles."
    )

    # Convert to dicts for serialization
    empleados_data = [n.to_dict() for n in nominas]

    return ResumenNomina(
        mes=mes,
        anio=anio,
        rfc_patron=rfc_patron.strip().upper(),
        num_empleados=len(nominas),
        total_salarios_brutos=round(total_brutos, 2),
        total_isr_retenido=round(total_isr, 2),
        total_imss_patronal=round(total_imss_patron, 2),
        total_imss_obrero=round(total_imss_obrero, 2),
        total_infonavit=round(total_infonavit, 2),
        total_isn=round(total_isn, 2),
        total_neto_empleados=round(total_neto, 2),
        total_costo_patron=round(total_costo, 2),
        empleados=empleados_data,
        alertas=alertas,
        notas=notas,
    )
