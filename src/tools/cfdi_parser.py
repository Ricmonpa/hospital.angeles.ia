"""OpenDoc - CFDI XML Parser.

Parses real Mexican CFDI (Comprobante Fiscal Digital por Internet)
XML files versions 3.3 and 4.0. Extracts all fiscal data needed
for tax classification, deductibility analysis, and reporting.

Supports:
- CFDI 3.3 (legacy, still valid)
- CFDI 4.0 (current standard)
- Complemento de Timbre Fiscal Digital 1.1
- Complemento de Impuestos Locales
- Complemento de Pagos (receipts)
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from datetime import datetime


# SAT XML Namespaces
NS = {
    "cfdi3": "http://www.sat.gob.mx/cfd/3",
    "cfdi4": "http://www.sat.gob.mx/cfd/4",
    "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
    "implocal": "http://www.sat.gob.mx/implocal",
    "pago20": "http://www.sat.gob.mx/Pagos20",
    "pago10": "http://www.sat.gob.mx/Pagos",
}

# SAT catalog: Régimen Fiscal
REGIMEN_FISCAL = {
    "601": "General de Ley Personas Morales",
    "603": "Personas Morales con Fines no Lucrativos",
    "605": "Sueldos y Salarios e Ingresos Asimilados a Salarios",
    "606": "Arrendamiento",
    "607": "Régimen de Enajenación o Adquisición de Bienes",
    "608": "Demás ingresos",
    "610": "Residentes en el Extranjero sin EP",
    "611": "Ingresos por Dividendos",
    "612": "Personas Físicas con Actividades Empresariales y Profesionales",
    "614": "Ingresos por intereses",
    "615": "Régimen de los ingresos por obtención de premios",
    "616": "Sin obligaciones fiscales",
    "620": "Sociedades Cooperativas de Producción",
    "621": "Incorporación Fiscal",
    "622": "Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras",
    "623": "Opcional para Grupos de Sociedades",
    "624": "Coordinados",
    "625": "Régimen Simplificado de Confianza (RESICO)",
    "626": "RESICO Personas Morales",
}

# SAT catalog: Uso CFDI
USO_CFDI = {
    "G01": "Adquisición de mercancías",
    "G02": "Devoluciones, descuentos o bonificaciones",
    "G03": "Gastos en general",
    "I01": "Construcciones",
    "I02": "Mobiliario y equipo de oficina por inversiones",
    "I03": "Equipo de transporte",
    "I04": "Equipo de cómputo y accesorios",
    "I05": "Dados, troqueles, moldes, matrices y herramental",
    "I06": "Comunicaciones telefónicas",
    "I07": "Comunicaciones satelitales",
    "I08": "Otra maquinaria y equipo",
    "D01": "Honorarios médicos, dentales y gastos hospitalarios",
    "D02": "Gastos médicos por incapacidad o discapacidad",
    "D03": "Gastos funerales",
    "D04": "Donativos",
    "D05": "Intereses reales efectivamente pagados por créditos hipotecarios",
    "D06": "Aportaciones voluntarias al SAR",
    "D07": "Primas por seguros de gastos médicos",
    "D08": "Gastos de transportación escolar obligatoria",
    "D09": "Depósitos en cuentas para el ahorro",
    "D10": "Pagos por servicios educativos (colegiaturas)",
    "S01": "Sin efectos fiscales",
    "CP01": "Pagos",
    "CN01": "Nómina",
}

# SAT catalog: Tipo de Comprobante
TIPO_COMPROBANTE = {
    "I": "Ingreso",
    "E": "Egreso",
    "T": "Traslado",
    "N": "Nómina",
    "P": "Pago",
}

# SAT catalog: Forma de Pago
FORMA_PAGO = {
    "01": "Efectivo",
    "02": "Cheque nominativo",
    "03": "Transferencia electrónica de fondos",
    "04": "Tarjeta de crédito",
    "05": "Monedero electrónico",
    "06": "Dinero electrónico",
    "08": "Vales de despensa",
    "12": "Dación en pago",
    "13": "Pago por subrogación",
    "14": "Pago por consignación",
    "15": "Condonación",
    "17": "Compensación",
    "23": "Novación",
    "24": "Confusión",
    "25": "Remisión de deuda",
    "26": "Prescripción o caducidad",
    "27": "A satisfacción del acreedor",
    "28": "Tarjeta de débito",
    "29": "Tarjeta de servicios",
    "30": "Aplicación de anticipos",
    "31": "Intermediario pagos",
    "99": "Por definir",
}

# SAT catalog: Claves de Productos/Servicios Médicos
# Extracted from Anexo 20, CFDI 4.0 — medical service categories
CLAVES_MEDICAS_SAT = {
    "85121600": "Servicios médicos de doctores especialistas",
    "85121502": "Servicios de consulta de médicos de atención primaria",
    "85121601": "Servicios de ginecología y obstetricia",
    "85121602": "Servicios de oftalmología",
    "85121603": "Servicios de otorrinolaringología",
    "85121604": "Servicios de cardiología",
    "85121605": "Servicios de dermatología",
    "85121606": "Servicios de ortopedia",
    "85121607": "Servicios de urología",
    "85121608": "Servicios de psicología",
    "85121609": "Servicios de psiquiatría",
    "85121610": "Servicios de pediatría",
    "85121611": "Servicios de endocrinología",
    "85121612": "Servicios de gastroenterología",
    "85121613": "Servicios de neumología",
    "85121614": "Servicios de neurología",
    "85121615": "Servicios de oncología",
    "85121700": "Servicios de cirujanos",
    "85121701": "Servicios de psicoterapeutas",
    "85121800": "Laboratorios médicos",
    "85101500": "Servicios de centros de salud",
    "85101501": "Servicios de hospitales",
    "85101503": "Servicios de consultorios médicos",
    "85101507": "Centros asistenciales de urgencia",
    "85101601": "Servicios de enfermería",
    "85111500": "Servicios de odontología",
    "85111501": "Servicios de odontología general",
    "85111502": "Servicios de ortodoncia",
    "85111503": "Servicios de endodoncia",
    "85111504": "Servicios de periodoncia",
    "85121900": "Servicios de nutrición",
    "85122000": "Servicios de optometría",
    "85131600": "Servicios de rehabilitación",
}

# Medical SAT code prefixes (for partial matching)
MEDICAL_CODE_PREFIXES = ("8510", "8511", "8512", "8513")


def is_medical_service(clave_prod_serv: str) -> bool:
    """Check if a SAT product/service code corresponds to a medical service."""
    if not clave_prod_serv:
        return False
    clave = str(clave_prod_serv).strip()
    if clave in CLAVES_MEDICAS_SAT:
        return True
    return clave.startswith(MEDICAL_CODE_PREFIXES)


def get_medical_service_name(clave_prod_serv: str) -> str:
    """Get the description for a medical SAT product/service code.

    Returns the catalog description if found, or empty string if not a medical code.
    """
    if not clave_prod_serv:
        return ""
    return CLAVES_MEDICAS_SAT.get(str(clave_prod_serv).strip(), "")


@dataclass
class ConceptoCFDI:
    """A single line item in a CFDI."""
    clave_prod_serv: str = ""
    no_identificacion: Optional[str] = None
    cantidad: float = 0.0
    clave_unidad: str = ""
    unidad: Optional[str] = None
    descripcion: str = ""
    valor_unitario: float = 0.0
    importe: float = 0.0
    descuento: float = 0.0
    # Tax breakdown per concept
    iva_tasa: Optional[float] = None
    iva_importe: Optional[float] = None
    isr_retencion: Optional[float] = None
    iva_retencion: Optional[float] = None
    exento: bool = False


@dataclass
class TimbreFiscal:
    """Timbre Fiscal Digital (SAT digital stamp)."""
    uuid: str = ""
    fecha_timbrado: str = ""
    rfc_prov_certif: str = ""
    no_certificado_sat: str = ""


@dataclass
class CFDI:
    """Complete parsed CFDI document."""
    # Version
    version: str = ""

    # Header
    folio: Optional[str] = None
    serie: Optional[str] = None
    fecha: str = ""
    fecha_dt: Optional[datetime] = None
    lugar_expedicion: str = ""
    tipo_comprobante: str = ""
    tipo_comprobante_desc: str = ""

    # Payment
    forma_pago: Optional[str] = None
    forma_pago_desc: str = ""
    metodo_pago: Optional[str] = None  # PUE or PPD
    moneda: str = "MXN"
    tipo_cambio: Optional[float] = None

    # Emisor
    emisor_rfc: str = ""
    emisor_nombre: str = ""
    emisor_regimen: str = ""
    emisor_regimen_desc: str = ""

    # Receptor
    receptor_rfc: str = ""
    receptor_nombre: str = ""
    receptor_uso_cfdi: str = ""
    receptor_uso_cfdi_desc: str = ""
    receptor_regimen: Optional[str] = None      # CFDI 4.0
    receptor_domicilio: Optional[str] = None     # CFDI 4.0

    # Amounts
    subtotal: float = 0.0
    descuento: float = 0.0
    total: float = 0.0

    # Taxes
    iva_trasladado: float = 0.0
    iva_retenido: float = 0.0
    isr_retenido: float = 0.0
    impuestos_locales_traslados: float = 0.0
    impuestos_locales_retenciones: float = 0.0
    exento_iva: bool = False

    # Line items
    conceptos: list = field(default_factory=list)

    # Timbre Fiscal
    timbre: Optional[TimbreFiscal] = None

    # Derived
    neto_a_cobrar: float = 0.0  # Total after retentions

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("fecha_dt", None)
        return d

    def summary(self) -> str:
        """One-line summary for WhatsApp."""
        return (
            f"{self.fecha[:10]} | {self.emisor_nombre} → {self.receptor_nombre} | "
            f"${self.total:,.2f} {self.moneda} | "
            f"{self.tipo_comprobante_desc} | "
            f"UUID: {self.timbre.uuid[:8] if self.timbre else 'N/A'}..."
        )

    def fiscal_summary(self) -> str:
        """Multi-line fiscal summary for the doctor."""
        lines = [
            f"📄 CFDI {self.version} — {self.tipo_comprobante_desc}",
            f"📅 {self.fecha[:10]}  |  Folio: {self.folio or 'S/N'}",
            f"🏢 Emisor: {self.emisor_nombre} ({self.emisor_rfc})",
            f"   Régimen: {self.emisor_regimen_desc}",
            f"👤 Receptor: {self.receptor_nombre} ({self.receptor_rfc})",
            f"   Uso CFDI: {self.receptor_uso_cfdi} — {self.receptor_uso_cfdi_desc}",
            f"",
            f"💰 Subtotal:     ${self.subtotal:>12,.2f}",
        ]
        if self.descuento > 0:
            lines.append(f"   Descuento:    ${self.descuento:>12,.2f}")
        if self.iva_trasladado > 0:
            lines.append(f"   IVA traslado: ${self.iva_trasladado:>12,.2f}")
        if self.exento_iva:
            lines.append(f"   IVA:          EXENTO")
        if self.isr_retenido > 0:
            lines.append(f"   ISR retenido: ${self.isr_retenido:>12,.2f}")
        if self.iva_retenido > 0:
            lines.append(f"   IVA retenido: ${self.iva_retenido:>12,.2f}")
        lines.append(f"   TOTAL:        ${self.total:>12,.2f}")
        if self.isr_retenido > 0 or self.iva_retenido > 0:
            self.neto_a_cobrar = self.total - self.isr_retenido - self.iva_retenido
            lines.append(f"   Neto a cobrar:${self.neto_a_cobrar:>12,.2f}")
        lines.append(f"")
        lines.append(f"🔑 UUID: {self.timbre.uuid if self.timbre else 'N/A'}")
        lines.append(f"💳 Pago: {self.forma_pago_desc} | {self.metodo_pago or 'N/A'}")
        return "\n".join(lines)


def _get_root(xml_path: str | Path) -> tuple[ET.Element, str]:
    """Parse XML and detect CFDI version."""
    tree = ET.parse(str(xml_path))
    root = tree.getroot()

    # Detect version from namespace or attribute
    tag = root.tag
    if "cfd/4" in tag:
        return root, "4.0"
    elif "cfd/3" in tag:
        return root, "3.3"

    # Fallback: check Version attribute
    version = root.get("Version", "")
    return root, version


def _parse_conceptos(root: ET.Element, ns_prefix: str) -> list[ConceptoCFDI]:
    """Parse all Concepto elements."""
    conceptos = []
    ns = ns_prefix

    for concepto_el in root.findall(f".//{{{NS[ns]}}}Concepto"):
        c = ConceptoCFDI(
            clave_prod_serv=concepto_el.get("ClaveProdServ", ""),
            no_identificacion=concepto_el.get("NoIdentificacion"),
            cantidad=float(concepto_el.get("Cantidad", "0")),
            clave_unidad=concepto_el.get("ClaveUnidad", ""),
            unidad=concepto_el.get("Unidad"),
            descripcion=concepto_el.get("Descripcion", ""),
            valor_unitario=float(concepto_el.get("ValorUnitario", "0")),
            importe=float(concepto_el.get("Importe", "0")),
            descuento=float(concepto_el.get("Descuento", "0")),
        )

        # Parse per-concept taxes
        for traslado in concepto_el.findall(f".//{{{NS[ns]}}}Traslado"):
            impuesto = traslado.get("Impuesto", "")
            tipo_factor = traslado.get("TipoFactor", "")
            if tipo_factor == "Exento":
                c.exento = True
            elif impuesto == "002":  # IVA
                c.iva_tasa = float(traslado.get("TasaOCuota", "0"))
                c.iva_importe = float(traslado.get("Importe", "0"))

        for retencion in concepto_el.findall(f".//{{{NS[ns]}}}Retencion"):
            impuesto = retencion.get("Impuesto", "")
            importe = float(retencion.get("Importe", "0"))
            if impuesto == "001":  # ISR
                c.isr_retencion = importe
            elif impuesto == "002":  # IVA
                c.iva_retencion = importe

        conceptos.append(c)

    return conceptos


def _parse_timbre(root: ET.Element) -> Optional[TimbreFiscal]:
    """Parse TimbreFiscalDigital complement."""
    tfd = root.find(f".//{{{NS['tfd']}}}TimbreFiscalDigital")
    if tfd is None:
        return None
    return TimbreFiscal(
        uuid=tfd.get("UUID", ""),
        fecha_timbrado=tfd.get("FechaTimbrado", ""),
        rfc_prov_certif=tfd.get("RfcProvCertif", ""),
        no_certificado_sat=tfd.get("NoCertificadoSAT", ""),
    )


def _parse_impuestos_locales(root: ET.Element) -> tuple[float, float]:
    """Parse ImpuestosLocales complement."""
    imp = root.find(f".//{{{NS['implocal']}}}ImpuestosLocales")
    if imp is None:
        return 0.0, 0.0
    return (
        float(imp.get("TotaldeTraslados", "0")),
        float(imp.get("TotaldeRetenciones", "0")),
    )


def parse_cfdi(xml_path: str | Path) -> CFDI:
    """Parse a CFDI XML file and return a structured CFDI object.

    Args:
        xml_path: Path to the CFDI XML file.

    Returns:
        CFDI object with all extracted fiscal data.

    Raises:
        FileNotFoundError: If the XML file doesn't exist.
        ET.ParseError: If the XML is malformed.
    """
    path = Path(xml_path)
    if not path.exists():
        raise FileNotFoundError(f"CFDI XML not found: {path}")

    root, version = _get_root(path)
    ns = "cfdi4" if version == "4.0" else "cfdi3"

    # Emisor
    emisor = root.find(f".//{{{NS[ns]}}}Emisor")
    emisor_rfc = emisor.get("Rfc", "") if emisor is not None else ""
    emisor_nombre = emisor.get("Nombre", "") if emisor is not None else ""
    emisor_regimen = emisor.get("RegimenFiscal", "") if emisor is not None else ""

    # Receptor
    receptor = root.find(f".//{{{NS[ns]}}}Receptor")
    receptor_rfc = receptor.get("Rfc", "") if receptor is not None else ""
    receptor_nombre = receptor.get("Nombre", "") if receptor is not None else ""
    receptor_uso = receptor.get("UsoCFDI", "") if receptor is not None else ""
    receptor_regimen = receptor.get("RegimenFiscalReceptor", "") if receptor is not None else None
    receptor_domicilio = receptor.get("DomicilioFiscalReceptor", "") if receptor is not None else None

    # Global taxes
    impuestos = root.find(f".//{{{NS[ns]}}}Impuestos")
    iva_trasladado = 0.0
    iva_retenido = 0.0
    isr_retenido = 0.0
    exento = False

    if impuestos is not None:
        # Traslados (totals)
        for t in impuestos.findall(f".//{{{NS[ns]}}}Traslado"):
            if t.get("TipoFactor") == "Exento":
                exento = True
            elif t.get("Impuesto") == "002":
                iva_trasladado += float(t.get("Importe", "0"))
        # Retenciones (totals)
        for r in impuestos.findall(f".//{{{NS[ns]}}}Retencion"):
            imp = r.get("Impuesto", "")
            importe = float(r.get("Importe", "0"))
            if imp == "001":
                isr_retenido += importe
            elif imp == "002":
                iva_retenido += importe

    # Also check per-concept for exento flag
    conceptos = _parse_conceptos(root, ns)
    if any(c.exento for c in conceptos):
        exento = True

    # Impuestos locales
    imp_local_traslados, imp_local_retenciones = _parse_impuestos_locales(root)

    # Timbre
    timbre = _parse_timbre(root)

    # Parse date
    fecha = root.get("Fecha", "")
    try:
        fecha_dt = datetime.fromisoformat(fecha)
    except (ValueError, TypeError):
        fecha_dt = None

    subtotal = float(root.get("SubTotal", "0"))
    total = float(root.get("Total", "0"))

    cfdi = CFDI(
        version=version,
        folio=root.get("Folio"),
        serie=root.get("Serie"),
        fecha=fecha,
        fecha_dt=fecha_dt,
        lugar_expedicion=root.get("LugarExpedicion", ""),
        tipo_comprobante=root.get("TipoDeComprobante", ""),
        tipo_comprobante_desc=TIPO_COMPROBANTE.get(root.get("TipoDeComprobante", ""), ""),
        forma_pago=root.get("FormaPago"),
        forma_pago_desc=FORMA_PAGO.get(root.get("FormaPago", ""), ""),
        metodo_pago=root.get("MetodoPago"),
        moneda=root.get("Moneda", "MXN"),
        tipo_cambio=float(root.get("TipoCambio")) if root.get("TipoCambio") else None,
        emisor_rfc=emisor_rfc,
        emisor_nombre=emisor_nombre,
        emisor_regimen=emisor_regimen,
        emisor_regimen_desc=REGIMEN_FISCAL.get(emisor_regimen, ""),
        receptor_rfc=receptor_rfc,
        receptor_nombre=receptor_nombre,
        receptor_uso_cfdi=receptor_uso,
        receptor_uso_cfdi_desc=USO_CFDI.get(receptor_uso, ""),
        receptor_regimen=receptor_regimen,
        receptor_domicilio=receptor_domicilio,
        subtotal=subtotal,
        descuento=float(root.get("Descuento", "0")),
        total=total,
        iva_trasladado=iva_trasladado,
        iva_retenido=iva_retenido,
        isr_retenido=isr_retenido,
        impuestos_locales_traslados=imp_local_traslados,
        impuestos_locales_retenciones=imp_local_retenciones,
        exento_iva=exento,
        conceptos=conceptos,
        timbre=timbre,
        neto_a_cobrar=total - isr_retenido - iva_retenido,
    )

    return cfdi


def parse_cfdi_string(xml_string: str) -> CFDI:
    """Parse a CFDI from an XML string (for API/WhatsApp uploads).

    Args:
        xml_string: The CFDI XML content as a string.

    Returns:
        CFDI object with all extracted fiscal data.
    """
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as f:
        f.write(xml_string)
        f.flush()
        return parse_cfdi(f.name)
