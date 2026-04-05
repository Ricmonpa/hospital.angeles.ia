"""OpenDoc - Deduction Optimizer Engine.

Exhaustive deduction strategy for Mexican doctors (Régimen 612 & RESICO 625).
Analyzes expenses, calculates depreciation, validates payment methods, and
recommends the optimal fiscal strategy.

Based on: LISR 2026, LIVA, CFF, RMF 2026.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum
from datetime import datetime, date
import math

from .fiscal_tables import (
    TARIFA_ISR_MENSUAL as _TARIFA_ISR_CENTRAL,
    TARIFA_RESICO_MENSUAL as _TARIFA_RESICO_CENTRAL,
)


# ─── Enums ────────────────────────────────────────────────────────────

class TipoDeduccion(str, Enum):
    """Type of deduction."""
    OPERATIVA = "Deducción Operativa"          # Régimen 612 only
    INVERSION = "Inversión (Activo Fijo)"      # Régimen 612 — depreciation
    PERSONAL = "Deducción Personal"            # Annual declaration
    NO_DEDUCIBLE = "No Deducible"
    RESICO_NO_APLICA = "No aplica en RESICO"   # Reminder for RESICO users


class SubcategoriaGasto(str, Enum):
    """Granular expense subcategory for a doctor."""
    # Operational (Régimen 612)
    ARRENDAMIENTO = "Arrendamiento de Consultorio"
    SERVICIOS_BASICOS = "Servicios Básicos (Luz, Agua, Internet)"
    MATERIAL_CURACION = "Material de Curación y Consumibles"
    PAPELERIA = "Papelería y Oficina"
    LIMPIEZA = "Limpieza y Mantenimiento"
    PUBLICIDAD = "Publicidad y Marketing"
    SOFTWARE = "Software y Suscripciones"
    LAVANDERIA = "Lavandería y Uniformes"
    HONORARIOS_PROFESIONALES = "Honorarios Profesionales (Externos)"
    EDUCACION_MEDICA = "Educación Médica Continua"
    VIATICOS = "Viáticos y Gastos de Viaje"
    SEGUROS = "Seguros y Fianzas"
    GASTOS_FINANCIEROS = "Gastos Financieros y Bancarios"
    PERMISOS_LICENCIAS = "Permisos y Licencias"
    IMPUESTOS_DEDUCIBLES = "Impuestos Deducibles"
    RESTAURANTES = "Alimentos (91.5% con tarjeta)"
    NOMINA = "Nómina y Prestaciones"
    SEGURIDAD_SOCIAL = "Cuotas IMSS/INFONAVIT/SAR"
    PREVISION_SOCIAL = "Previsión Social"
    RECOLECCION_RPBI = "Recolección RPBI"

    # Inversiones (depreciation)
    EQUIPO_MEDICO = "Equipo Médico Electromecánico"
    INSTRUMENTAL = "Instrumental Quirúrgico"
    EQUIPO_COMPUTO = "Equipo de Cómputo"
    MOBILIARIO = "Mobiliario de Oficina/Consultorio"
    VEHICULO = "Vehículo"
    CONSTRUCCIONES = "Construcciones y Adecuaciones"

    # Personal (Annual)
    GASTOS_MEDICOS_PERSONAL = "Gastos Médicos Personales"
    COLEGIATURAS = "Colegiaturas"
    SEGURO_GMM_PERSONAL = "Seguro GMM Personal"
    APORTACIONES_RETIRO = "Aportaciones Complementarias Retiro"
    INTERESES_HIPOTECARIOS = "Intereses Hipotecarios"
    DONATIVOS = "Donativos"
    FUNERALES = "Gastos Funerales"

    # No deducible
    GASTO_PERSONAL = "Gasto Personal (No Deducible)"
    SIN_CFDI = "Sin CFDI (No Deducible)"


# ─── Depreciation Rates (Art. 31-38 LISR) ────────────────────────────

@dataclass
class TasaDepreciacion:
    """Depreciation rate for a type of asset."""
    tasa_anual: float        # Annual % (e.g., 10.0 = 10%)
    fundamento: str          # Legal basis
    descripcion: str         # Human-readable description
    tope_moi: Optional[float] = None  # Maximum deductible MOI (e.g., $175,000 for vehicles)
    vida_util_anos: int = 0  # Approximate useful life


TASAS_DEPRECIACION = {
    "equipo_medico": TasaDepreciacion(
        tasa_anual=10.0,
        fundamento="Art. 35 LISR",
        descripcion="Equipo médico electromecánico, instrumental, equipo de laboratorio",
        vida_util_anos=10,
    ),
    "equipo_computo": TasaDepreciacion(
        tasa_anual=30.0,
        fundamento="Art. 35 LISR",
        descripcion="Computadoras, laptops, tablets, impresoras, servidores, redes",
        vida_util_anos=4,  # ~3.3 years but round to 4
    ),
    "mobiliario": TasaDepreciacion(
        tasa_anual=10.0,
        fundamento="Art. 34-VI LISR",
        descripcion="Escritorios, sillas, archiveros, vitrinas, mesas de exploración",
        vida_util_anos=10,
    ),
    "vehiculo": TasaDepreciacion(
        tasa_anual=25.0,
        fundamento="Art. 36-II LISR",
        descripcion="Automóvil para uso profesional",
        tope_moi=175_000.0,
        vida_util_anos=4,
    ),
    "construcciones": TasaDepreciacion(
        tasa_anual=5.0,
        fundamento="Art. 34-I LISR",
        descripcion="Construcciones, adecuaciones al inmueble",
        vida_util_anos=20,
    ),
    "adecuaciones_arrendado": TasaDepreciacion(
        tasa_anual=0.0,  # Calculated based on lease term
        fundamento="Art. 36-VII LISR",
        descripcion="Mejoras a inmueble arrendado (se deprecian en plazo del contrato)",
        vida_util_anos=0,
    ),
}


# ─── SAT Product Code → Deduction Category Mapping ───────────────────

# Maps SAT ClaveProdServ prefixes to expense subcategories
# Used for automatic classification of expenses from CFDI conceptos
SAT_CODE_DEDUCTION_MAP = {
    # Arrendamiento
    "80131": SubcategoriaGasto.ARRENDAMIENTO,
    "80141": SubcategoriaGasto.ARRENDAMIENTO,

    # Servicios básicos
    "83111": SubcategoriaGasto.SERVICIOS_BASICOS,  # Electricidad, agua, telecom

    # Material de curación
    "42131": SubcategoriaGasto.MATERIAL_CURACION,  # Suministros médicos
    "42311": SubcategoriaGasto.MATERIAL_CURACION,  # Material de curación
    "42132": SubcategoriaGasto.MATERIAL_CURACION,  # Equipo de protección personal
    "42142": SubcategoriaGasto.MATERIAL_CURACION,  # Ropa desechable médica
    "42151": SubcategoriaGasto.MATERIAL_CURACION,  # Envases médicos
    "42152": SubcategoriaGasto.MATERIAL_CURACION,  # Suturas
    "42171": SubcategoriaGasto.MATERIAL_CURACION,  # Sondas y catéteres
    "42172": SubcategoriaGasto.MATERIAL_CURACION,  # Jeringas y agujas

    # Medicamentos (Tasa 0% IVA)
    "51101": SubcategoriaGasto.MATERIAL_CURACION,  # Medicamentos
    "51102": SubcategoriaGasto.MATERIAL_CURACION,  # Medicamentos biológicos
    "51111": SubcategoriaGasto.MATERIAL_CURACION,  # Vacunas
    "51141": SubcategoriaGasto.MATERIAL_CURACION,  # Anestésicos
    "51142": SubcategoriaGasto.MATERIAL_CURACION,  # Antibióticos
    "51191": SubcategoriaGasto.MATERIAL_CURACION,  # Material de curación

    # Papelería
    "44121": SubcategoriaGasto.PAPELERIA,
    "44103": SubcategoriaGasto.PAPELERIA,  # Consumibles de impresión
    "14111": SubcategoriaGasto.PAPELERIA,  # Papel

    # Limpieza
    "47131": SubcategoriaGasto.LIMPIEZA,  # Productos de limpieza
    "76111": SubcategoriaGasto.LIMPIEZA,  # Servicios de limpieza
    "72101": SubcategoriaGasto.LIMPIEZA,  # Mantenimiento de edificios

    # RPBI
    "76121": SubcategoriaGasto.RECOLECCION_RPBI,  # Gestión de residuos

    # Publicidad
    "82101": SubcategoriaGasto.PUBLICIDAD,
    "82111": SubcategoriaGasto.PUBLICIDAD,
    "82121": SubcategoriaGasto.PUBLICIDAD,

    # Software y suscripciones
    "81111": SubcategoriaGasto.SOFTWARE,  # Servicios de software
    "81112": SubcategoriaGasto.SOFTWARE,  # Internet services
    "43232": SubcategoriaGasto.SOFTWARE,  # Licencias de software

    # Lavandería
    "91111": SubcategoriaGasto.LAVANDERIA,
    "53101": SubcategoriaGasto.LAVANDERIA,  # Uniformes

    # Equipo médico (INVERSIÓN — depreciación 10%)
    "42181": SubcategoriaGasto.EQUIPO_MEDICO,  # Equipo médico
    "42182": SubcategoriaGasto.EQUIPO_MEDICO,  # Instrumentos médicos
    "42183": SubcategoriaGasto.EQUIPO_MEDICO,  # Equipo quirúrgico
    "42184": SubcategoriaGasto.EQUIPO_MEDICO,  # Equipo de rehabilitación
    "42191": SubcategoriaGasto.EQUIPO_MEDICO,  # Equipo de laboratorio
    "42192": SubcategoriaGasto.EQUIPO_MEDICO,  # Equipo de medición médica
    "42201": SubcategoriaGasto.EQUIPO_MEDICO,  # Equipo de radiología
    "42202": SubcategoriaGasto.EQUIPO_MEDICO,  # Equipo de ultrasonido
    "42203": SubcategoriaGasto.EQUIPO_MEDICO,  # Equipo de endoscopia
    "42271": SubcategoriaGasto.EQUIPO_MEDICO,  # Equipo de esterilización
    "42272": SubcategoriaGasto.EQUIPO_MEDICO,  # Autoclaves
    "42291": SubcategoriaGasto.EQUIPO_MEDICO,  # Equipo de oftalmología
    "42292": SubcategoriaGasto.EQUIPO_MEDICO,  # Equipo dental
    "42293": SubcategoriaGasto.EQUIPO_MEDICO,  # Equipo de audiología
    "42294": SubcategoriaGasto.EQUIPO_MEDICO,  # Equipo de cardiología
    "42295": SubcategoriaGasto.EQUIPO_MEDICO,  # Equipo de diagnóstico

    # Instrumental quirúrgico (INVERSIÓN — depreciación 10%)
    "42241": SubcategoriaGasto.INSTRUMENTAL,  # Instrumental
    "42242": SubcategoriaGasto.INSTRUMENTAL,
    "42251": SubcategoriaGasto.INSTRUMENTAL,
    "42261": SubcategoriaGasto.INSTRUMENTAL,

    # Equipo de cómputo (INVERSIÓN — depreciación 30%)
    "43211": SubcategoriaGasto.EQUIPO_COMPUTO,  # Computadoras
    "43212": SubcategoriaGasto.EQUIPO_COMPUTO,  # Accesorios
    "43221": SubcategoriaGasto.EQUIPO_COMPUTO,  # Impresoras
    "43222": SubcategoriaGasto.EQUIPO_COMPUTO,  # Equipo de red
    "43231": SubcategoriaGasto.EQUIPO_COMPUTO,  # Almacenamiento

    # Mobiliario (INVERSIÓN — depreciación 10%)
    "56101": SubcategoriaGasto.MOBILIARIO,  # Mobiliario de oficina
    "56111": SubcategoriaGasto.MOBILIARIO,  # Muebles de oficina
    "56112": SubcategoriaGasto.MOBILIARIO,  # Estantería

    # Vehículo (INVERSIÓN — depreciación 25%, tope $175,000)
    "25101": SubcategoriaGasto.VEHICULO,  # Automóviles
    "25102": SubcategoriaGasto.VEHICULO,
    "25111": SubcategoriaGasto.VEHICULO,
    "78181": SubcategoriaGasto.VEHICULO,  # Mantenimiento vehicular

    # Seguros
    "84131": SubcategoriaGasto.SEGUROS,

    # Gastos financieros
    "84121": SubcategoriaGasto.GASTOS_FINANCIEROS,

    # Educación médica continua
    "86101": SubcategoriaGasto.EDUCACION_MEDICA,
    "86111": SubcategoriaGasto.EDUCACION_MEDICA,
    "86132": SubcategoriaGasto.EDUCACION_MEDICA,

    # Honorarios profesionales
    "80111": SubcategoriaGasto.HONORARIOS_PROFESIONALES,
    "84111": SubcategoriaGasto.HONORARIOS_PROFESIONALES,  # Contabilidad

    # Nómina
    "80141": SubcategoriaGasto.NOMINA,

    # Permisos y licencias
    "80161": SubcategoriaGasto.PERMISOS_LICENCIAS,

    # Alimentos / restaurantes
    "90101": SubcategoriaGasto.RESTAURANTES,
    "90111": SubcategoriaGasto.RESTAURANTES,
}

# Maps subcategory to depreciation type
SUBCATEGORIA_TO_DEPRECIACION = {
    SubcategoriaGasto.EQUIPO_MEDICO: "equipo_medico",
    SubcategoriaGasto.INSTRUMENTAL: "equipo_medico",
    SubcategoriaGasto.EQUIPO_COMPUTO: "equipo_computo",
    SubcategoriaGasto.MOBILIARIO: "mobiliario",
    SubcategoriaGasto.VEHICULO: "vehiculo",
    SubcategoriaGasto.CONSTRUCCIONES: "construcciones",
}

# Which subcategories are investments (not immediate expenses)?
INVERSIONES = {
    SubcategoriaGasto.EQUIPO_MEDICO,
    SubcategoriaGasto.INSTRUMENTAL,
    SubcategoriaGasto.EQUIPO_COMPUTO,
    SubcategoriaGasto.MOBILIARIO,
    SubcategoriaGasto.VEHICULO,
    SubcategoriaGasto.CONSTRUCCIONES,
}


# ─── Data Classes ─────────────────────────────────────────────────────

@dataclass
class DepreciacionAnual:
    """Annual depreciation calculation for an asset."""
    moi: float                          # Monto Original de la Inversión
    moi_deducible: float                # MOI after cap (e.g., $175K for vehicles)
    tasa_anual: float                   # Annual rate %
    deduccion_anual: float              # Yearly deduction amount
    deduccion_mensual: float            # Monthly deduction amount
    meses_restantes: int                # Months remaining to fully depreciate
    acumulado_deducido: float           # Total deducted to date
    pendiente_deducir: float            # Remaining to deduct
    fecha_inicio: str                   # Start date of depreciation
    fundamento: str                     # Legal basis
    tipo_activo: str                    # Asset type description
    iva_no_acreditable: float = 0.0     # IVA added to MOI (not creditable)
    nota_estrategia: str = ""           # Strategic recommendation


@dataclass
class ValidacionPago:
    """Payment validation result."""
    es_deducible: bool
    forma_pago: str
    monto: float
    problema: str = ""
    recomendacion: str = ""
    fundamento: str = ""


@dataclass
class AnalisisDeduccion:
    """Complete deduction analysis for a single expense."""
    # Classification
    subcategoria: str
    tipo_deduccion: str                # TipoDeduccion value
    deducible_612: bool                # Deductible under Régimen 612?
    deducible_resico: bool             # Deductible under RESICO? (usually False)

    # Amounts
    monto_total: float
    monto_deducible: float
    porcentaje_deducible: float        # 0-100

    # Depreciation (if investment)
    depreciacion: Optional[DepreciacionAnual] = None

    # Payment validation
    validacion_pago: Optional[ValidacionPago] = None

    # Legal
    fundamento_legal: str = ""
    requisitos: list = field(default_factory=list)

    # Strategy
    recomendaciones: list = field(default_factory=list)
    alertas: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EstrategiaAnual:
    """Annual deduction strategy comparison: Régimen 612 vs RESICO."""
    # Income
    ingresos_totales: float
    ingresos_por_salarios: float = 0.0

    # Régimen 612 calculation
    deducciones_operativas_612: float = 0.0
    depreciacion_total_612: float = 0.0
    base_gravable_612: float = 0.0
    isr_estimado_612: float = 0.0

    # RESICO calculation
    base_gravable_resico: float = 0.0
    isr_estimado_resico: float = 0.0

    # Recommendation
    regimen_recomendado: str = ""
    ahorro_estimado: float = 0.0
    explicacion: str = ""

    # Details
    desglose_deducciones: list = field(default_factory=list)
    deducciones_personales: float = 0.0
    alertas: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ─── Core Functions ───────────────────────────────────────────────────

def classify_expense_by_sat_code(clave_prod_serv: str) -> SubcategoriaGasto:
    """Classify an expense by its SAT product/service code.

    Matches by 5-digit prefix from SAT_CODE_DEDUCTION_MAP.

    Args:
        clave_prod_serv: SAT ClaveProdServ (e.g., "42181502")

    Returns:
        SubcategoriaGasto enum value.
    """
    if not clave_prod_serv:
        return SubcategoriaGasto.GASTO_PERSONAL

    clave = str(clave_prod_serv).strip()

    # Try 5-digit prefix match
    prefix5 = clave[:5]
    if prefix5 in SAT_CODE_DEDUCTION_MAP:
        return SAT_CODE_DEDUCTION_MAP[prefix5]

    # Try broader category match (medical services → handled by cfdi_parser)
    if clave.startswith(("8510", "8511", "8512", "8513")):
        return SubcategoriaGasto.GASTOS_MEDICOS_PERSONAL

    return SubcategoriaGasto.GASTO_PERSONAL


def is_inversion(subcategoria: SubcategoriaGasto) -> bool:
    """Check if expense is an investment (requires depreciation)."""
    return subcategoria in INVERSIONES


def get_depreciation_type(subcategoria: SubcategoriaGasto) -> Optional[str]:
    """Get the depreciation type key for a subcategory."""
    return SUBCATEGORIA_TO_DEPRECIACION.get(subcategoria)


def validate_payment(
    forma_pago: str,
    monto: float,
    es_restaurante: bool = False,
) -> ValidacionPago:
    """Validate if a payment method makes the expense deductible.

    Args:
        forma_pago: CFDI payment method code ("01"=cash, "03"=transfer, etc.)
        monto: Total amount of the expense
        es_restaurante: Whether this is a restaurant expense

    Returns:
        ValidacionPago with deductibility assessment.
    """
    PAGO_BANCARIZADO = {"02", "03", "04", "05", "06", "28", "29"}  # Non-cash methods
    FORMA_PAGO_DESC = {
        "01": "Efectivo", "02": "Cheque nominativo",
        "03": "Transferencia", "04": "Tarjeta de crédito",
        "05": "Monedero electrónico", "28": "Tarjeta de débito",
        "29": "Tarjeta de servicios", "99": "Por definir",
    }

    desc = FORMA_PAGO_DESC.get(forma_pago, forma_pago or "No especificado")

    # Cash payments
    if forma_pago == "01":
        if monto > 2000:
            return ValidacionPago(
                es_deducible=False,
                forma_pago=desc,
                monto=monto,
                problema=f"Pago en efectivo de ${monto:,.2f} (>$2,000). NO DEDUCIBLE.",
                recomendacion="Pagar por transferencia, cheque nominativo o tarjeta.",
                fundamento="Art. 27 fracción III LISR",
            )
        return ValidacionPago(
            es_deducible=True,
            forma_pago=desc,
            monto=monto,
            recomendacion="Monto ≤$2,000 en efectivo es deducible, pero se recomienda bancarizar.",
            fundamento="Art. 27 fracción III LISR",
        )

    # Bancarized payments
    if forma_pago in PAGO_BANCARIZADO:
        if es_restaurante:
            return ValidacionPago(
                es_deducible=True,
                forma_pago=desc,
                monto=monto,
                recomendacion=f"Restaurante pagado con {desc}: 91.5% deducible (${monto * 0.915:,.2f}).",
                fundamento="Art. 28 fracción XX LISR",
            )
        return ValidacionPago(
            es_deducible=True,
            forma_pago=desc,
            monto=monto,
            fundamento="Art. 27 fracción III LISR",
        )

    # "Por definir" (99) or unknown
    return ValidacionPago(
        es_deducible=False,
        forma_pago=desc,
        monto=monto,
        problema="Forma de pago no definida o no reconocida.",
        recomendacion="Solicitar CFDI con forma de pago correcta o complemento de pago.",
        fundamento="Art. 27 fracción III LISR",
    )


def calculate_depreciation(
    moi: float,
    tipo_activo: str,
    fecha_adquisicion: Optional[str] = None,
    meses_en_uso: int = 0,
    iva_pagado: float = 0.0,
) -> DepreciacionAnual:
    """Calculate annual depreciation for an investment asset.

    The IVA paid on medical equipment is NOT creditable (doctor's services are exempt).
    So IVA becomes part of the MOI (cost).

    Args:
        moi: Monto Original de la Inversión (purchase price before IVA)
        tipo_activo: Key in TASAS_DEPRECIACION (e.g., "equipo_medico", "vehiculo")
        fecha_adquisicion: ISO date string of acquisition
        meses_en_uso: Months the asset has been in use
        iva_pagado: IVA paid (added to MOI since non-creditable)

    Returns:
        DepreciacionAnual with full calculation.
    """
    if tipo_activo not in TASAS_DEPRECIACION:
        raise ValueError(f"Tipo de activo desconocido: {tipo_activo}. "
                         f"Opciones: {list(TASAS_DEPRECIACION.keys())}")

    tasa = TASAS_DEPRECIACION[tipo_activo]

    # IVA not creditable for doctors (medical services are exempt)
    # So IVA becomes part of the MOI
    moi_total = moi + iva_pagado

    # Apply MOI cap (vehicles: $175,000)
    moi_deducible = moi_total
    nota = ""
    if tasa.tope_moi and moi_total > tasa.tope_moi:
        moi_deducible = tasa.tope_moi
        excedente = moi_total - tasa.tope_moi
        nota = (
            f"Tope MOI deducible: ${tasa.tope_moi:,.0f}. "
            f"Excedente de ${excedente:,.0f} NO es deducible nunca. "
            f"Evaluar arrendamiento puro ($200/día + IVA)."
        )

    # Annual deduction
    deduccion_anual = moi_deducible * (tasa.tasa_anual / 100)
    deduccion_mensual = deduccion_anual / 12

    # Calculate accumulated deduction and remaining
    acumulado = deduccion_mensual * meses_en_uso
    if acumulado > moi_deducible:
        acumulado = moi_deducible
    pendiente = moi_deducible - acumulado

    # Months remaining
    if deduccion_mensual > 0:
        meses_restantes = math.ceil(pendiente / deduccion_mensual)
    else:
        meses_restantes = 0

    # Strategic note
    if tipo_activo == "equipo_computo":
        nota = nota or "Tasa 30% es la más alta. Clasificar como cómputo todo lo que aplique (tablets, monitores, impresoras)."
    elif tipo_activo == "equipo_medico" and moi_total > 100_000:
        nota = nota or "Evaluar deducción inmediata (Art. 196-206 LISR) vs depreciación lineal 10% anual."

    return DepreciacionAnual(
        moi=moi_total,
        moi_deducible=moi_deducible,
        tasa_anual=tasa.tasa_anual,
        deduccion_anual=round(deduccion_anual, 2),
        deduccion_mensual=round(deduccion_mensual, 2),
        meses_restantes=meses_restantes,
        acumulado_deducido=round(acumulado, 2),
        pendiente_deducir=round(pendiente, 2),
        fecha_inicio=fecha_adquisicion or "",
        fundamento=tasa.fundamento,
        tipo_activo=tasa.descripcion,
        iva_no_acreditable=iva_pagado,
        nota_estrategia=nota,
    )


def analyze_deduction(
    monto: float,
    clave_prod_serv: str = "",
    forma_pago: str = "",
    descripcion: str = "",
    regimen: str = "612",
    es_inversion_flag: bool = False,
    fecha_adquisicion: Optional[str] = None,
    iva_pagado: float = 0.0,
) -> AnalisisDeduccion:
    """Analyze a single expense for optimal deductibility.

    Args:
        monto: Expense amount (before IVA)
        clave_prod_serv: SAT product/service code
        forma_pago: Payment method code (01=cash, 03=transfer, etc.)
        descripcion: Human-readable description
        regimen: Doctor's tax regime ("612" or "625")
        es_inversion_flag: Force treatment as investment
        fecha_adquisicion: Acquisition date for depreciation
        iva_pagado: IVA amount paid

    Returns:
        AnalisisDeduccion with complete analysis.
    """
    # Step 1: Classify by SAT code
    subcategoria = classify_expense_by_sat_code(clave_prod_serv)

    # Step 2: Determine deduction type
    es_inv = es_inversion_flag or is_inversion(subcategoria)

    if regimen == "625":
        tipo_deduccion = TipoDeduccion.RESICO_NO_APLICA
    elif es_inv:
        tipo_deduccion = TipoDeduccion.INVERSION
    else:
        tipo_deduccion = TipoDeduccion.OPERATIVA

    # Step 3: Validate payment
    es_restaurante = subcategoria == SubcategoriaGasto.RESTAURANTES
    validacion = validate_payment(forma_pago, monto, es_restaurante)

    # Step 4: Calculate amounts
    deducible_612 = validacion.es_deducible and regimen != "625"
    deducible_resico = False  # Operational deductions never apply in RESICO

    monto_deducible = monto
    porcentaje = 100.0

    if not validacion.es_deducible:
        monto_deducible = 0.0
        porcentaje = 0.0
    elif es_restaurante:
        monto_deducible = monto * 0.915
        porcentaje = 91.5
    elif subcategoria == SubcategoriaGasto.VEHICULO and es_inv:
        # Vehicle cap handled in depreciation
        pass

    # Step 5: Calculate depreciation if investment
    depreciacion = None
    if es_inv and deducible_612:
        dep_type = get_depreciation_type(subcategoria)
        if dep_type:
            depreciacion = calculate_depreciation(
                moi=monto,
                tipo_activo=dep_type,
                fecha_adquisicion=fecha_adquisicion,
                iva_pagado=iva_pagado,
            )

    # Step 6: Build requirements and recommendations
    requisitos = [
        "CFDI (XML) válido y vigente",
    ]
    recomendaciones = []
    alertas = []

    if monto > 2000:
        requisitos.append("Pago por sistema financiero (transferencia, tarjeta, cheque nominativo)")

    if es_inv:
        requisitos.append("Registrar como activo fijo en contabilidad")
        requisitos.append("Iniciar depreciación el mes siguiente a la adquisición")

    if subcategoria == SubcategoriaGasto.VEHICULO:
        requisitos.append("Bitácora de uso profesional")
        recomendaciones.append(
            "Documentar proporción de uso profesional vs personal (70-80% recomendado)"
        )
        if monto > 175_000:
            alertas.append(
                f"Vehículo de ${monto:,.0f} excede tope de $175,000. "
                f"Solo ${175_000:,.0f} es deducible. Evaluar leasing."
            )

    if regimen == "625":
        alertas.append(
            "RESICO no permite deducciones operativas. "
            "Si tus gastos superan 35-40% de ingresos, evaluar cambio a Régimen 612."
        )

    if not validacion.es_deducible:
        alertas.append(validacion.problema)

    # Legal basis
    fundamento = "Art. 27 LISR"
    if es_inv:
        fundamento = depreciacion.fundamento if depreciacion else "Art. 31-38 LISR"
    elif es_restaurante:
        fundamento = "Art. 28 fracción XX LISR"

    return AnalisisDeduccion(
        subcategoria=subcategoria.value,
        tipo_deduccion=tipo_deduccion.value,
        deducible_612=deducible_612,
        deducible_resico=deducible_resico,
        monto_total=monto,
        monto_deducible=round(monto_deducible, 2),
        porcentaje_deducible=porcentaje,
        depreciacion=depreciacion,
        validacion_pago=validacion,
        fundamento_legal=fundamento,
        requisitos=requisitos,
        recomendaciones=recomendaciones,
        alertas=alertas,
    )


# ─── ISR Calculation ─────────────────────────────────────────────────

# Imported from fiscal_tables.py (single source of truth)
# Kept as module-level aliases for backward compatibility
TARIFA_ISR_MENSUAL_2026 = _TARIFA_ISR_CENTRAL
TARIFA_RESICO_MENSUAL_2026 = _TARIFA_RESICO_CENTRAL


def calculate_isr_612_mensual(utilidad_mensual: float) -> float:
    """Calculate monthly ISR under Régimen 612 (progressive rate).

    Args:
        utilidad_mensual: Monthly taxable income (ingresos - deducciones)

    Returns:
        ISR amount for the month.
    """
    if utilidad_mensual <= 0:
        return 0.0

    for li, ls, cuota, tasa in TARIFA_ISR_MENSUAL_2026:
        if li <= utilidad_mensual <= ls:
            excedente = utilidad_mensual - li
            return round(cuota + (excedente * tasa / 100), 2)

    # Above maximum bracket
    last = TARIFA_ISR_MENSUAL_2026[-1]
    excedente = utilidad_mensual - last[0]
    return round(last[2] + (excedente * last[3] / 100), 2)


def calculate_isr_resico_mensual(ingresos_cobrados: float) -> float:
    """Calculate monthly ISR under RESICO (flat rate on gross income).

    Args:
        ingresos_cobrados: Monthly income effectively collected.

    Returns:
        ISR amount for the month.
    """
    if ingresos_cobrados <= 0:
        return 0.0

    for li, ls, tasa in TARIFA_RESICO_MENSUAL_2026:
        if li <= ingresos_cobrados <= ls:
            return round(ingresos_cobrados * tasa / 100, 2)

    # Above RESICO limit — should be expelled to 612
    return round(ingresos_cobrados * 2.50 / 100, 2)


def compare_regimes(
    ingresos_mensuales: float,
    deducciones_mensuales: float,
    depreciacion_mensual: float = 0.0,
) -> EstrategiaAnual:
    """Compare Régimen 612 vs RESICO for a doctor's monthly numbers.

    Annualizes the monthly figures and calculates estimated ISR under each regime.

    Args:
        ingresos_mensuales: Average monthly gross income (honorarios)
        deducciones_mensuales: Average monthly deductible expenses
        depreciacion_mensual: Average monthly depreciation

    Returns:
        EstrategiaAnual with comparison and recommendation.
    """
    ingresos_anuales = ingresos_mensuales * 12
    deducciones_anuales = deducciones_mensuales * 12
    depreciacion_anual = depreciacion_mensual * 12

    # Régimen 612
    total_deducciones_612 = deducciones_anuales + depreciacion_anual
    utilidad_612 = max(0, ingresos_anuales - total_deducciones_612)
    isr_612_mensual = calculate_isr_612_mensual(utilidad_612 / 12)
    isr_612_anual = isr_612_mensual * 12

    # RESICO
    isr_resico_mensual = calculate_isr_resico_mensual(ingresos_mensuales)
    isr_resico_anual = isr_resico_mensual * 12

    # Recommendation
    ahorro = abs(isr_612_anual - isr_resico_anual)
    if isr_612_anual < isr_resico_anual:
        recomendado = "Régimen 612 (Actividades Profesionales)"
        explicacion = (
            f"Régimen 612 te ahorra ~${ahorro:,.0f}/año porque tus deducciones "
            f"operativas (${total_deducciones_612:,.0f}) reducen significativamente "
            f"tu base gravable. Tus gastos representan el "
            f"{total_deducciones_612/ingresos_anuales*100:.0f}% de tus ingresos."
        )
    else:
        recomendado = "RESICO (Régimen 625)"
        explicacion = (
            f"RESICO te ahorra ~${ahorro:,.0f}/año. Tus deducciones "
            f"(${total_deducciones_612:,.0f}, {total_deducciones_612/ingresos_anuales*100:.0f}% de ingresos) "
            f"no son suficientes para que Régimen 612 sea más ventajoso."
        )

    # RESICO income cap check
    alertas = []
    if ingresos_anuales > 3_500_000:
        alertas.append(
            f"Ingresos anuales de ${ingresos_anuales:,.0f} exceden el tope RESICO de $3,500,000. "
            f"Expulsión automática a Régimen 612."
        )
        recomendado = "Régimen 612 (obligatorio — excede tope RESICO)"

    porcentaje_gastos = (total_deducciones_612 / ingresos_anuales * 100) if ingresos_anuales > 0 else 0

    if porcentaje_gastos > 30 and porcentaje_gastos < 40:
        alertas.append(
            f"Zona gris: tus gastos son {porcentaje_gastos:.0f}% de ingresos. "
            f"Ambos regímenes son similares. Considera el costo administrativo del 612."
        )

    return EstrategiaAnual(
        ingresos_totales=ingresos_anuales,
        deducciones_operativas_612=deducciones_anuales,
        depreciacion_total_612=depreciacion_anual,
        base_gravable_612=utilidad_612,
        isr_estimado_612=round(isr_612_anual, 2),
        base_gravable_resico=ingresos_anuales,
        isr_estimado_resico=round(isr_resico_anual, 2),
        regimen_recomendado=recomendado,
        ahorro_estimado=round(ahorro, 2),
        explicacion=explicacion,
        alertas=alertas,
    )


# ─── Personal Deductions (Annual Declaration) ────────────────────────

def calculate_personal_deduction_limit(ingresos_totales: float, uma_anual: float = 37_844.40) -> float:
    """Calculate the global personal deduction limit.

    Limit = lesser of: 15% of total income OR 5 annual UMAs

    Args:
        ingresos_totales: Total annual income across all regimes
        uma_anual: Annual UMA value (2026 estimate ~$37,844.40)

    Returns:
        Maximum deductible amount for personal deductions.
    """
    tope_porcentaje = ingresos_totales * 0.15
    tope_umas = uma_anual * 5
    return min(tope_porcentaje, tope_umas)


# ─── Convenience: Format for WhatsApp ────────────────────────────────

def format_deduction_whatsapp(analisis: AnalisisDeduccion) -> str:
    """Format a deduction analysis for WhatsApp delivery."""
    icon = "✅" if analisis.deducible_612 else "❌"

    lines = [
        f"{icon} {analisis.subcategoria}",
        f"   Tipo: {analisis.tipo_deduccion}",
        f"   Monto: ${analisis.monto_total:,.2f} → Deducible: ${analisis.monto_deducible:,.2f} ({analisis.porcentaje_deducible:.0f}%)",
        f"   📋 {analisis.fundamento_legal}",
    ]

    if analisis.depreciacion:
        d = analisis.depreciacion
        lines.append(f"   📊 Depreciación: {d.tasa_anual:.0f}% anual = ${d.deduccion_anual:,.2f}/año (${d.deduccion_mensual:,.2f}/mes)")
        if d.nota_estrategia:
            lines.append(f"   💡 {d.nota_estrategia}")

    if analisis.alertas:
        for a in analisis.alertas:
            lines.append(f"   🚨 {a}")

    if analisis.recomendaciones:
        for r in analisis.recomendaciones:
            lines.append(f"   → {r}")

    return "\n".join(lines)


def format_strategy_whatsapp(estrategia: EstrategiaAnual) -> str:
    """Format annual strategy comparison for WhatsApp."""
    lines = [
        "━━━ COMPARATIVO FISCAL ANUAL ━━━",
        "",
        f"💰 Ingresos anuales: ${estrategia.ingresos_totales:,.0f}",
        "",
        "📊 RÉGIMEN 612:",
        f"   Deducciones operativas: ${estrategia.deducciones_operativas_612:,.0f}",
        f"   Depreciación: ${estrategia.depreciacion_total_612:,.0f}",
        f"   Base gravable: ${estrategia.base_gravable_612:,.0f}",
        f"   ISR estimado: ${estrategia.isr_estimado_612:,.0f}",
        "",
        "📊 RESICO (625):",
        f"   Base gravable: ${estrategia.base_gravable_resico:,.0f} (ingresos brutos)",
        f"   ISR estimado: ${estrategia.isr_estimado_resico:,.0f}",
        "",
        f"✅ RECOMENDACIÓN: {estrategia.regimen_recomendado}",
        f"   Ahorro estimado: ${estrategia.ahorro_estimado:,.0f}/año",
        f"   {estrategia.explicacion}",
    ]

    if estrategia.alertas:
        lines.append("")
        for a in estrategia.alertas:
            lines.append(f"🚨 {a}")

    return "\n".join(lines)
