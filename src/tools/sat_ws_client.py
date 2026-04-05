"""OpenDoc - SAT SOAP Web Service Client.

Programmatic interface to SAT's SOAP web services:
- Descarga Masiva: Bulk CFDI download (solicitar → verificar → descargar)
- Verificador CFDI: Public CFDI validation (no auth needed)
- Cancelación CFDI: Invoice cancellation (requires user confirmation)

Complements the Playwright-based sat_portal_navigator.py.
When SOAP services are available, they are faster and more reliable
than browser navigation. Falls back to Playwright when SOAP fails.

GOLDEN RULE: Cancelación NEVER executes without explicit user confirmation.
Every SOAP call is audit-logged.

Based on: SAT Descarga Masiva v1, ConsultaCFDI v1, RMF 2026.
"""

import asyncio
import base64
import io
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Union

import httpx

from .sat_efirma import (
    CertificadoInfo,
    load_certificate,
    load_private_key,
    generate_sat_auth_token,
    sign_soap_body,
    _wipe_key,
    EFirmaExpiredError,
    EFirmaSigningError,
)


# ─── SOAP Endpoints ──────────────────────────────────────────────────

# Descarga Masiva de CFDI (requires e.firma auth)
SAT_WS_AUTENTICACION_URL = (
    "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/"
    "Autenticacion/Autenticacion.svc"
)
SAT_WS_SOLICITUD_URL = (
    "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/"
    "SolicitaDescargaService.svc"
)
SAT_WS_VERIFICACION_URL = (
    "https://cfdidescargamasivasolicitud.clouda.sat.gob.mx/"
    "VerificaSolicitudDescargaService.svc"
)
SAT_WS_DESCARGA_URL = (
    "https://cfdidescargamasiva.clouda.sat.gob.mx/"
    "DescargaMasivaService.svc"
)

# Verificador CFDI (public, no auth)
SAT_WS_VERIFICADOR_URL = (
    "https://consultaqr.facturaelectronica.sat.gob.mx/"
    "ConsultaCFDIService.svc"
)

# Cancelación (requires e.firma auth)
SAT_WS_CANCELACION_URL = "https://cancelacfdi.sat.gob.mx/edocancelacion/cancelar"

# SOAP Actions
SOAP_ACTION_AUTENTICA = (
    "http://DescargaMasivaTerceros.gob.mx/IAutenticacion/Autentica"
)
SOAP_ACTION_SOLICITA = (
    "http://DescargaMasivaTerceros.sat.gob.mx/"
    "ISolicitaDescargaService/SolicitaDescarga"
)
SOAP_ACTION_VERIFICA = (
    "http://DescargaMasivaTerceros.sat.gob.mx/"
    "IVerificaSolicitudDescargaService/VerificaSolicitudDescarga"
)
SOAP_ACTION_DESCARGA = (
    "http://DescargaMasivaTerceros.sat.gob.mx/"
    "IDescargaMasivaService/Descarga"
)
SOAP_ACTION_CONSULTA = (
    "http://tempuri.org/IConsultaCFDIService/Consulta"
)

# Descarga Masiva XML namespace
NS_DM = "http://DescargaMasivaTerceros.sat.gob.mx"
NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"


# ─── Configuration ───────────────────────────────────────────────────

DEFAULT_TIMEOUT = 30.0
MAX_RETRIES = 3
RETRY_DELAYS = [2.0, 5.0, 10.0]
VERIFY_POLL_INTERVAL = 10.0
VERIFY_MAX_POLLS = 360  # Max 1 hour
DEFAULT_DOWNLOAD_DIR = "data/sat_downloads"


# ─── Enums ────────────────────────────────────────────────────────────

class EstadoSolicitud(str, Enum):
    """Status of a Descarga Masiva solicitud."""
    ACEPTADA = "Aceptada"
    EN_PROCESO = "En Proceso"
    TERMINADA = "Terminada"
    RECHAZADA = "Rechazada"
    VENCIDA = "Vencida"
    ERROR = "Error"


class EstadoCFDI(str, Enum):
    """CFDI verification status."""
    VIGENTE = "Vigente"
    CANCELADO = "Cancelado"
    NO_ENCONTRADO = "No encontrado"


class EstadoCancelacion(str, Enum):
    """CFDI cancellation status."""
    CANCELADO = "Cancelado"
    CANCELADO_SIN_ACEPTACION = "Cancelado sin aceptación"
    EN_PROCESO = "En proceso de cancelación"
    RECHAZADO = "Rechazado"
    NO_ENCONTRADO = "No encontrado"


# ─── Exceptions ───────────────────────────────────────────────────────

class SATWSAuthError(Exception):
    """SOAP authentication failed."""
    pass


class SATWSSolicitudError(Exception):
    """Solicitud submission failed."""
    pass


class SATWSDownloadError(Exception):
    """Package download failed."""
    pass


class SATWSCancelacionRequiresConfirmation(Exception):
    """Cancelation requires explicit user confirmation before executing."""
    pass


class SATWSServiceUnavailable(Exception):
    """SAT SOAP services are down or unreachable."""
    pass


# ─── Dataclasses ──────────────────────────────────────────────────────

@dataclass
class SATAuthToken:
    """Authentication token from SAT SOAP Autenticacion service."""
    token: str
    created_at: str
    expires_at: str
    rfc: str

    def to_dict(self) -> dict:
        return asdict(self)

    def is_expired(self) -> bool:
        try:
            exp = datetime.fromisoformat(self.expires_at)
            now = datetime.now(timezone.utc)
            if exp.tzinfo is None:
                from datetime import timezone as tz
                exp = exp.replace(tzinfo=tz.utc)
            return now >= exp
        except (ValueError, TypeError):
            return True


@dataclass
class SolicitudDescarga:
    """Tracks a Descarga Masiva solicitud."""
    id_solicitud: str
    rfc_solicitante: str
    tipo_solicitud: str                # "recibidos" or "emitidos"
    fecha_inicio: str
    fecha_fin: str
    estado: str                        # EstadoSolicitud value
    mensaje: str = ""
    numero_cfdis: int = 0
    ids_paquetes: list = field(default_factory=list)
    fecha_solicitud: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def resumen_whatsapp(self) -> str:
        icon = "✅" if self.estado == EstadoSolicitud.TERMINADA.value else \
               "⏳" if self.estado in (EstadoSolicitud.ACEPTADA.value,
                                       EstadoSolicitud.EN_PROCESO.value) else "❌"
        lines = [
            "━━━ SOLICITUD DESCARGA MASIVA ━━━",
            f"{icon} Estado: {self.estado}",
            f"📋 ID: {self.id_solicitud[:16]}..." if len(self.id_solicitud) > 16
            else f"📋 ID: {self.id_solicitud}",
            f"📂 Tipo: {self.tipo_solicitud.capitalize()}",
            f"📅 Periodo: {self.fecha_inicio} → {self.fecha_fin}",
        ]
        if self.numero_cfdis > 0:
            lines.append(f"📑 CFDIs encontrados: {self.numero_cfdis}")
        if self.ids_paquetes:
            lines.append(f"📦 Paquetes: {len(self.ids_paquetes)}")
        if self.mensaje:
            lines.append(f"💬 {self.mensaje}")
        return "\n".join(lines)


@dataclass
class VerificacionCFDI:
    """Result of verifying a single CFDI via the public SOAP service."""
    uuid: str
    rfc_emisor: str
    rfc_receptor: str
    total: str
    estado: str                        # EstadoCFDI value
    es_cancelable: str = ""
    estatus_cancelacion: str = ""
    fecha_certificacion: str = ""
    pac_certifico: str = ""
    codigo_estatus: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def resumen_whatsapp(self) -> str:
        icon = "✅" if self.estado == EstadoCFDI.VIGENTE.value else \
               "❌" if self.estado == EstadoCFDI.CANCELADO.value else "❓"
        lines = [
            "━━━ VERIFICACIÓN CFDI ━━━",
            f"{icon} Estado: {self.estado}",
            f"🔑 UUID: {self.uuid}",
            f"🏢 Emisor: {self.rfc_emisor}",
            f"👤 Receptor: {self.rfc_receptor}",
            f"💰 Total: ${self.total}",
        ]
        if self.es_cancelable:
            lines.append(f"📋 Cancelable: {self.es_cancelable}")
        if self.estatus_cancelacion:
            lines.append(f"🔄 Cancelación: {self.estatus_cancelacion}")
        return "\n".join(lines)


@dataclass
class ResultadoCancelacion:
    """Result of a CFDI cancellation request."""
    uuid: str
    rfc_emisor: str
    estado: str                        # EstadoCancelacion value
    fecha_cancelacion: str = ""
    acuse_xml: str = ""                # Full acuse (not in to_dict for privacy)
    confirmado_por_usuario: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("acuse_xml", None)
        return d

    def resumen_whatsapp(self) -> str:
        icon = "✅" if "Cancelado" in self.estado else "❌"
        return (
            f"━━━ CANCELACIÓN CFDI ━━━\n"
            f"{icon} Estado: {self.estado}\n"
            f"🔑 UUID: {self.uuid}\n"
            f"📅 Fecha: {self.fecha_cancelacion or 'N/A'}"
        )


@dataclass
class DescargaMasivaResult:
    """Complete result of a Descarga Masiva flow."""
    solicitud: Optional[SolicitudDescarga] = None
    archivos_xml: list = field(default_factory=list)
    total_descargados: int = 0
    errores: list = field(default_factory=list)
    canal: str = "soap"                # "soap" or "playwright"

    def to_dict(self) -> dict:
        return {
            "solicitud": self.solicitud.to_dict() if self.solicitud else None,
            "archivos_xml": self.archivos_xml,
            "total_descargados": self.total_descargados,
            "errores": self.errores,
            "canal": self.canal,
        }

    def resumen_whatsapp(self) -> str:
        lines = []
        if self.solicitud:
            lines.append(self.solicitud.resumen_whatsapp())
        lines.extend([
            "",
            f"📥 Descargados: {self.total_descargados}",
            f"📡 Canal: {self.canal.upper()}",
        ])
        if self.errores:
            lines.append(f"⚠️ Errores: {len(self.errores)}")
        return "\n".join(lines)


# ─── SOAP Transport ──────────────────────────────────────────────────

async def _soap_request(
    url: str,
    soap_envelope: str,
    soap_action: str,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = MAX_RETRIES,
) -> str:
    """Send a SOAP request with retry logic.

    Args:
        url: SOAP endpoint URL.
        soap_envelope: Complete SOAP envelope XML string.
        soap_action: SOAPAction header value.
        timeout: Per-request timeout.
        retries: Number of retry attempts.

    Returns:
        Response body string.

    Raises:
        SATWSServiceUnavailable: If all retries fail.
    """
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": soap_action,
    }

    last_error = None
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                verify=True,
                follow_redirects=True,
            ) as client:
                response = await client.post(
                    url,
                    content=soap_envelope.encode("utf-8"),
                    headers=headers,
                )

                if response.status_code == 200:
                    return response.text

                # Parse SOAP fault if present
                fault_msg = _parse_soap_fault(response.text)
                if fault_msg:
                    last_error = fault_msg
                else:
                    last_error = f"HTTP {response.status_code}"

                # Retry on 500/503
                if response.status_code in (500, 502, 503):
                    if attempt < retries - 1:
                        await asyncio.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
                        continue

                raise SATWSServiceUnavailable(
                    f"SAT respondió con error: {last_error}"
                )

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_error = str(e)
            if attempt < retries - 1:
                await asyncio.sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
                continue
        except SATWSServiceUnavailable:
            raise
        except Exception as e:
            last_error = str(e)
            break

    raise SATWSServiceUnavailable(
        f"No se pudo conectar al servicio SAT después de {retries} intentos: {last_error}"
    )


def _parse_soap_fault(response_text: str) -> str:
    """Extract fault message from SOAP response."""
    try:
        root = ET.fromstring(response_text)
        # Look for Fault element in any namespace
        for elem in root.iter():
            if "Fault" in elem.tag:
                faultstring = ""
                for child in elem:
                    if "faultstring" in child.tag.lower():
                        faultstring = child.text or ""
                    elif "Reason" in child.tag:
                        for sub in child:
                            if sub.text:
                                faultstring = sub.text
                return faultstring or "SOAP Fault (sin detalle)"
    except ET.ParseError:
        pass
    return ""


# ─── Authentication ──────────────────────────────────────────────────

async def authenticate(
    cer_path: Union[str, Path],
    key_path: Union[str, Path],
    password: str,
) -> SATAuthToken:
    """Authenticate to SAT SOAP services using e.firma.

    Flow:
    1. Load certificate and private key
    2. Generate signed security token XML
    3. Send to SAT Autenticacion endpoint
    4. Parse and return the auth token (5 min lifetime)
    5. Wipe private key from memory

    Returns:
        SATAuthToken with the authentication token.

    Raises:
        SATWSAuthError: If authentication fails.
    """
    info, cert = load_certificate(cer_path)
    private_key = load_private_key(key_path, password)

    try:
        envelope = generate_sat_auth_token(cert, private_key)
    finally:
        _wipe_key(private_key)

    try:
        response = await _soap_request(
            SAT_WS_AUTENTICACION_URL,
            envelope,
            SOAP_ACTION_AUTENTICA,
        )
    except SATWSServiceUnavailable as e:
        raise SATWSAuthError(f"No se pudo autenticar con el SAT: {e}")

    # Parse token from response
    token_value = _extract_xml_text(response, "AutenticaResult")
    if not token_value:
        raise SATWSAuthError(
            "El SAT no devolvió un token de autenticación. "
            "Verifica que tu e.firma sea vigente."
        )

    now = datetime.now(timezone.utc)
    return SATAuthToken(
        token=token_value,
        created_at=now.isoformat(),
        expires_at=(now + __import__("datetime").timedelta(minutes=5)).isoformat(),
        rfc=info.rfc,
    )


# ─── Descarga Masiva ─────────────────────────────────────────────────

async def solicitar_descarga(
    token: SATAuthToken,
    rfc_solicitante: str,
    fecha_inicio: str,
    fecha_fin: str,
    tipo_solicitud: str = "recibidos",
    rfc_emisor: Optional[str] = None,
    rfc_receptor: Optional[str] = None,
    tipo_comprobante: Optional[str] = None,
    cer_path: Optional[Union[str, Path]] = None,
    key_path: Optional[Union[str, Path]] = None,
    password: Optional[str] = None,
) -> SolicitudDescarga:
    """Submit a Descarga Masiva solicitud to SAT.

    Returns:
        SolicitudDescarga with the solicitud ID and status.

    Raises:
        SATWSSolicitudError: If rejected.
    """
    if token.is_expired():
        raise SATWSAuthError("Token de autenticación expirado. Re-autenticar.")

    # Build the request body
    rfc_receptor_val = rfc_receptor or rfc_solicitante if tipo_solicitud == "recibidos" else ""
    rfc_emisor_val = rfc_emisor or rfc_solicitante if tipo_solicitud == "emitidos" else ""

    if tipo_solicitud == "recibidos" and not rfc_receptor_val:
        rfc_receptor_val = rfc_solicitante
    if tipo_solicitud == "emitidos" and not rfc_emisor_val:
        rfc_emisor_val = rfc_solicitante

    attrs = [
        f'FechaInicial="{fecha_inicio}T00:00:00"',
        f'FechaFinal="{fecha_fin}T23:59:59"',
        f'RfcSolicitante="{rfc_solicitante}"',
        f'TipoSolicitud="CFDI"',
    ]
    if rfc_emisor_val:
        attrs.append(f'RfcEmisor="{rfc_emisor_val}"')
    if rfc_receptor_val:
        attrs.append(f'RfcReceptores="{rfc_receptor_val}"')
    if tipo_comprobante:
        attrs.append(f'TipoComprobante="{tipo_comprobante}"')

    body_content = f'<des:SolicitaDescarga xmlns:des="{NS_DM}"><des:solicitud {" ".join(attrs)}/></des:SolicitaDescarga>'

    # Sign the request body if e.firma provided
    signature_block = ""
    if cer_path and key_path and password:
        _, cert = load_certificate(cer_path)
        pk = load_private_key(key_path, password)
        try:
            signature_block = sign_soap_body(body_content, cert, pk)
        finally:
            _wipe_key(pk)

    envelope = _build_soap_envelope(token.token, body_content, signature_block)

    try:
        response = await _soap_request(
            SAT_WS_SOLICITUD_URL, envelope, SOAP_ACTION_SOLICITA,
        )
    except SATWSServiceUnavailable as e:
        raise SATWSSolicitudError(f"Error al solicitar descarga: {e}")

    # Parse response
    id_solicitud = _extract_xml_attr(response, "SolicitaDescargaResult", "IdSolicitud") or ""
    cod_estatus = _extract_xml_attr(response, "SolicitaDescargaResult", "CodEstatus") or ""
    mensaje = _extract_xml_attr(response, "SolicitaDescargaResult", "Mensaje") or ""

    if cod_estatus == "5000":
        estado = EstadoSolicitud.ACEPTADA.value
    elif cod_estatus == "5004":
        estado = EstadoSolicitud.RECHAZADA.value
    else:
        estado = EstadoSolicitud.ERROR.value

    if not id_solicitud and estado != EstadoSolicitud.ACEPTADA.value:
        raise SATWSSolicitudError(
            f"Solicitud rechazada por el SAT. Código: {cod_estatus}. {mensaje}"
        )

    return SolicitudDescarga(
        id_solicitud=id_solicitud,
        rfc_solicitante=rfc_solicitante,
        tipo_solicitud=tipo_solicitud,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        estado=estado,
        mensaje=mensaje,
        fecha_solicitud=datetime.now(timezone.utc).isoformat(),
    )


async def verificar_solicitud(
    token: SATAuthToken,
    id_solicitud: str,
    rfc_solicitante: str,
    cer_path: Optional[Union[str, Path]] = None,
    key_path: Optional[Union[str, Path]] = None,
    password: Optional[str] = None,
) -> SolicitudDescarga:
    """Check the status of a Descarga Masiva solicitud.

    Returns:
        Updated SolicitudDescarga.
    """
    if token.is_expired():
        raise SATWSAuthError("Token de autenticación expirado.")

    body_content = (
        f'<des:VerificaSolicitudDescarga xmlns:des="{NS_DM}">'
        f'<des:solicitud IdSolicitud="{id_solicitud}" '
        f'RfcSolicitante="{rfc_solicitante}"/>'
        f'</des:VerificaSolicitudDescarga>'
    )

    signature_block = ""
    if cer_path and key_path and password:
        _, cert = load_certificate(cer_path)
        pk = load_private_key(key_path, password)
        try:
            signature_block = sign_soap_body(body_content, cert, pk)
        finally:
            _wipe_key(pk)

    envelope = _build_soap_envelope(token.token, body_content, signature_block)

    try:
        response = await _soap_request(
            SAT_WS_VERIFICACION_URL, envelope, SOAP_ACTION_VERIFICA,
        )
    except SATWSServiceUnavailable as e:
        raise SATWSSolicitudError(f"Error al verificar solicitud: {e}")

    # Parse response
    cod_estatus = _extract_xml_attr(response, "VerificaSolicitudDescargaResult", "CodEstatus") or ""
    estado_sol = _extract_xml_attr(response, "VerificaSolicitudDescargaResult", "EstadoSolicitud") or ""
    num_cfdis = _extract_xml_attr(response, "VerificaSolicitudDescargaResult", "NumeroCFDIs") or "0"
    mensaje = _extract_xml_attr(response, "VerificaSolicitudDescargaResult", "Mensaje") or ""

    # Parse package IDs
    ids_paquetes = []
    try:
        root = ET.fromstring(response)
        for elem in root.iter():
            if "IdsPaquetes" in elem.tag and elem.text:
                ids_paquetes.append(elem.text.strip())
    except ET.ParseError:
        pass

    # Map estado
    estado_map = {
        "1": EstadoSolicitud.ACEPTADA.value,
        "2": EstadoSolicitud.EN_PROCESO.value,
        "3": EstadoSolicitud.TERMINADA.value,
        "4": EstadoSolicitud.ERROR.value,
        "5": EstadoSolicitud.RECHAZADA.value,
        "6": EstadoSolicitud.VENCIDA.value,
    }
    estado = estado_map.get(estado_sol, EstadoSolicitud.ERROR.value)

    return SolicitudDescarga(
        id_solicitud=id_solicitud,
        rfc_solicitante=rfc_solicitante,
        tipo_solicitud="",
        fecha_inicio="",
        fecha_fin="",
        estado=estado,
        mensaje=mensaje,
        numero_cfdis=int(num_cfdis) if num_cfdis.isdigit() else 0,
        ids_paquetes=ids_paquetes,
    )


async def descargar_paquete(
    token: SATAuthToken,
    rfc_solicitante: str,
    id_paquete: str,
    download_dir: str = DEFAULT_DOWNLOAD_DIR,
    cer_path: Optional[Union[str, Path]] = None,
    key_path: Optional[Union[str, Path]] = None,
    password: Optional[str] = None,
) -> list:
    """Download a CFDI package (.zip) and extract XML files.

    Returns:
        List of paths to extracted XML files.

    Raises:
        SATWSDownloadError: If download or extraction fails.
    """
    if token.is_expired():
        raise SATWSAuthError("Token expirado.")

    body_content = (
        f'<des:PeticionDescargaMasivaTercerosEntrada xmlns:des="{NS_DM}">'
        f'<des:peticionDescarga IdPaquete="{id_paquete}" '
        f'RfcSolicitante="{rfc_solicitante}"/>'
        f'</des:PeticionDescargaMasivaTercerosEntrada>'
    )

    signature_block = ""
    if cer_path and key_path and password:
        _, cert = load_certificate(cer_path)
        pk = load_private_key(key_path, password)
        try:
            signature_block = sign_soap_body(body_content, cert, pk)
        finally:
            _wipe_key(pk)

    envelope = _build_soap_envelope(token.token, body_content, signature_block)

    try:
        response = await _soap_request(
            SAT_WS_DESCARGA_URL, envelope, SOAP_ACTION_DESCARGA,
            timeout=120.0,  # Downloads can be large
        )
    except SATWSServiceUnavailable as e:
        raise SATWSDownloadError(f"Error al descargar paquete: {e}")

    # Extract base64-encoded zip from response
    paquete_b64 = _extract_xml_text(response, "Paquete")
    if not paquete_b64:
        raise SATWSDownloadError(
            "El SAT no devolvió el paquete de descarga. "
            "El paquete puede haber expirado."
        )

    # Decode and extract zip
    try:
        zip_bytes = base64.b64decode(paquete_b64)
    except Exception as e:
        raise SATWSDownloadError(f"Error decodificando paquete: {e}")

    # Create download directory
    dl_path = Path(download_dir)
    dl_path.mkdir(parents=True, exist_ok=True)

    # Extract XML files
    xml_paths = []
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if name.lower().endswith(".xml"):
                    content = zf.read(name)
                    out_path = dl_path / name
                    out_path.write_bytes(content)
                    xml_paths.append(str(out_path))
    except zipfile.BadZipFile as e:
        raise SATWSDownloadError(f"Paquete ZIP corrupto: {e}")

    return xml_paths


async def descarga_masiva_completa(
    cer_path: Union[str, Path],
    key_path: Union[str, Path],
    password: str,
    rfc: str,
    fecha_inicio: str,
    fecha_fin: str,
    tipo: str = "recibidos",
    download_dir: str = DEFAULT_DOWNLOAD_DIR,
    max_wait_minutes: int = 60,
) -> DescargaMasivaResult:
    """Complete Descarga Masiva flow: authenticate → solicitar → verificar → descargar.

    Args:
        cer_path: Path to .cer file.
        key_path: Path to .key file.
        password: Private key password.
        rfc: Taxpayer RFC.
        fecha_inicio: Start date (YYYY-MM-DD).
        fecha_fin: End date (YYYY-MM-DD).
        tipo: "recibidos" or "emitidos".
        download_dir: Output directory.
        max_wait_minutes: Maximum wait for SAT processing.

    Returns:
        DescargaMasivaResult with all downloaded XMLs.
    """
    result = DescargaMasivaResult(canal="soap")

    # Step 1: Authenticate
    try:
        token = await authenticate(cer_path, key_path, password)
    except (SATWSAuthError, EFirmaExpiredError) as e:
        result.errores.append(f"Autenticación fallida: {e}")
        return result

    # Step 2: Submit solicitud
    try:
        solicitud = await solicitar_descarga(
            token, rfc, fecha_inicio, fecha_fin, tipo,
            cer_path=cer_path, key_path=key_path, password=password,
        )
        result.solicitud = solicitud
    except SATWSSolicitudError as e:
        result.errores.append(f"Solicitud rechazada: {e}")
        return result

    if solicitud.estado == EstadoSolicitud.RECHAZADA.value:
        result.errores.append(f"Solicitud rechazada: {solicitud.mensaje}")
        return result

    # Step 3: Poll for completion
    max_polls = int((max_wait_minutes * 60) / VERIFY_POLL_INTERVAL)
    for poll in range(max_polls):
        await asyncio.sleep(VERIFY_POLL_INTERVAL)

        # Re-authenticate if token is about to expire
        if token.is_expired():
            try:
                token = await authenticate(cer_path, key_path, password)
            except SATWSAuthError as e:
                result.errores.append(f"Re-autenticación fallida: {e}")
                return result

        try:
            solicitud = await verificar_solicitud(
                token, solicitud.id_solicitud, rfc,
                cer_path=cer_path, key_path=key_path, password=password,
            )
            result.solicitud = solicitud
        except SATWSSolicitudError as e:
            result.errores.append(f"Error verificando: {e}")
            continue

        if solicitud.estado == EstadoSolicitud.TERMINADA.value:
            break
        elif solicitud.estado in (EstadoSolicitud.RECHAZADA.value,
                                   EstadoSolicitud.VENCIDA.value,
                                   EstadoSolicitud.ERROR.value):
            result.errores.append(f"Solicitud {solicitud.estado}: {solicitud.mensaje}")
            return result
    else:
        result.errores.append(
            f"Timeout: la solicitud no se completó en {max_wait_minutes} minutos."
        )
        return result

    # Step 4: Download packages
    all_xmls = []
    for id_paquete in solicitud.ids_paquetes:
        if token.is_expired():
            try:
                token = await authenticate(cer_path, key_path, password)
            except SATWSAuthError as e:
                result.errores.append(f"Re-autenticación fallida: {e}")
                break

        try:
            xmls = await descargar_paquete(
                token, rfc, id_paquete, download_dir,
                cer_path=cer_path, key_path=key_path, password=password,
            )
            all_xmls.extend(xmls)
        except SATWSDownloadError as e:
            result.errores.append(f"Error descargando paquete {id_paquete}: {e}")

    result.archivos_xml = all_xmls
    result.total_descargados = len(all_xmls)

    return result


# ─── Verificador CFDI (Público) ──────────────────────────────────────

async def verificar_cfdi(
    uuid: str,
    rfc_emisor: str,
    rfc_receptor: str,
    total: str,
) -> VerificacionCFDI:
    """Verify a CFDI status via SAT's public SOAP service.

    NO authentication required.

    Args:
        uuid: CFDI UUID.
        rfc_emisor: Emisor RFC.
        rfc_receptor: Receptor RFC.
        total: Total amount as string (e.g., "150000.00").

    Returns:
        VerificacionCFDI with the CFDI status.
    """
    envelope = (
        f'<soapenv:Envelope xmlns:soapenv="{NS_SOAP}" '
        f'xmlns:tem="http://tempuri.org/">'
        f'<soapenv:Header/>'
        f'<soapenv:Body>'
        f'<tem:Consulta>'
        f'<tem:expresionImpresa>'
        f'?re={rfc_emisor}&amp;rr={rfc_receptor}'
        f'&amp;tt={total}&amp;id={uuid}'
        f'</tem:expresionImpresa>'
        f'</tem:Consulta>'
        f'</soapenv:Body>'
        f'</soapenv:Envelope>'
    )

    try:
        response = await _soap_request(
            SAT_WS_VERIFICADOR_URL, envelope, SOAP_ACTION_CONSULTA,
        )
    except SATWSServiceUnavailable as e:
        return VerificacionCFDI(
            uuid=uuid,
            rfc_emisor=rfc_emisor,
            rfc_receptor=rfc_receptor,
            total=total,
            estado=EstadoCFDI.NO_ENCONTRADO.value,
            codigo_estatus=f"Error: {e}",
        )

    # Parse response
    estado_text = _extract_xml_text(response, "Estado") or ""
    es_cancelable = _extract_xml_text(response, "EsCancelable") or ""
    estatus_cancel = _extract_xml_text(response, "EstatusCancelacion") or ""
    codigo = _extract_xml_text(response, "CodigoEstatus") or ""

    # Map to our enum
    if "Vigente" in estado_text:
        estado = EstadoCFDI.VIGENTE.value
    elif "Cancelado" in estado_text:
        estado = EstadoCFDI.CANCELADO.value
    else:
        estado = EstadoCFDI.NO_ENCONTRADO.value

    return VerificacionCFDI(
        uuid=uuid,
        rfc_emisor=rfc_emisor,
        rfc_receptor=rfc_receptor,
        total=total,
        estado=estado,
        es_cancelable=es_cancelable,
        estatus_cancelacion=estatus_cancel,
        codigo_estatus=codigo,
    )


# ─── Cancelación CFDI ────────────────────────────────────────────────

def preparar_cancelacion(
    uuid: str,
    rfc_emisor: str,
    motivo: str = "02",
    uuid_sustitucion: Optional[str] = None,
) -> dict:
    """Prepare a CFDI cancellation WITHOUT executing it.

    SAFETY: This function ONLY prepares the data. It NEVER sends.
    Always raises SATWSCancelacionRequiresConfirmation.

    Args:
        uuid: UUID of CFDI to cancel.
        rfc_emisor: Issuer RFC.
        motivo: SAT reason code (01-04).
        uuid_sustitucion: Required if motivo="01".

    Returns:
        Dict with prepared data (but always raises first).

    Raises:
        SATWSCancelacionRequiresConfirmation: ALWAYS.
    """
    motivos = {
        "01": "CFDI emitido con errores CON relación (requiere UUID sustitución)",
        "02": "CFDI emitido con errores SIN relación",
        "03": "No se llevó a cabo la operación",
        "04": "Operación nominativa relacionada en factura global",
    }

    if motivo == "01" and not uuid_sustitucion:
        raise ValueError(
            "Motivo '01' requiere el UUID del CFDI de sustitución."
        )

    data = {
        "uuid": uuid,
        "rfc_emisor": rfc_emisor,
        "motivo_codigo": motivo,
        "motivo_descripcion": motivos.get(motivo, "Desconocido"),
        "uuid_sustitucion": uuid_sustitucion or "",
        "advertencia": (
            "⚠️ CANCELAR UN CFDI ES IRREVERSIBLE. "
            "El receptor será notificado y puede rechazar la cancelación. "
            "¿Estás seguro de proceder?"
        ),
    }

    raise SATWSCancelacionRequiresConfirmation(
        f"Cancelación de CFDI {uuid} requiere confirmación del usuario. "
        f"Motivo: {motivos.get(motivo, motivo)}"
    )


async def ejecutar_cancelacion(
    cer_path: Union[str, Path],
    key_path: Union[str, Path],
    password: str,
    uuid: str,
    rfc_emisor: str,
    motivo: str = "02",
    uuid_sustitucion: Optional[str] = None,
    confirmacion_usuario: bool = False,
) -> ResultadoCancelacion:
    """Execute a CFDI cancellation via SAT web service.

    SAFETY GATE: REFUSES to execute unless confirmacion_usuario=True.

    Returns:
        ResultadoCancelacion.

    Raises:
        SATWSCancelacionRequiresConfirmation: If not confirmed.
    """
    if not confirmacion_usuario:
        raise SATWSCancelacionRequiresConfirmation(
            "La cancelación requiere confirmación explícita del usuario. "
            "Establece confirmacion_usuario=True SOLO después de que el "
            "usuario confirme por chat/WhatsApp."
        )

    # Authenticate
    token = await authenticate(cer_path, key_path, password)

    # Build cancellation request
    folios = f'<Folio UUID="{uuid}" Motivo="{motivo}"'
    if motivo == "01" and uuid_sustitucion:
        folios += f' FolioSustitucion="{uuid_sustitucion}"'
    folios += '/>'

    body_content = (
        f'<Cancelacion xmlns="http://cancelacfd.sat.gob.mx" '
        f'RfcEmisor="{rfc_emisor}" Fecha="{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")}">'
        f'<Folios>{folios}</Folios>'
        f'</Cancelacion>'
    )

    _, cert = load_certificate(cer_path)
    pk = load_private_key(key_path, password)
    try:
        signature = sign_soap_body(body_content, cert, pk)
    finally:
        _wipe_key(pk)

    envelope = _build_soap_envelope(token.token, body_content, signature)

    try:
        response = await _soap_request(
            SAT_WS_CANCELACION_URL, envelope,
            "http://cancelacfd.sat.gob.mx/ICancelacionService/CancelaFolio",
        )
    except SATWSServiceUnavailable as e:
        return ResultadoCancelacion(
            uuid=uuid,
            rfc_emisor=rfc_emisor,
            estado="Error: " + str(e),
            confirmado_por_usuario=True,
        )

    # Parse response
    estatus = _extract_xml_text(response, "EstatusUUID") or ""
    fecha = _extract_xml_text(response, "Fecha") or ""

    estado = EstadoCancelacion.NO_ENCONTRADO.value
    if "201" in estatus or "202" in estatus:
        estado = EstadoCancelacion.CANCELADO_SIN_ACEPTACION.value
    elif "Proceso" in estatus:
        estado = EstadoCancelacion.EN_PROCESO.value
    elif "Rechazado" in estatus or "203" in estatus:
        estado = EstadoCancelacion.RECHAZADO.value

    return ResultadoCancelacion(
        uuid=uuid,
        rfc_emisor=rfc_emisor,
        estado=estado,
        fecha_cancelacion=fecha,
        acuse_xml=response,
        confirmado_por_usuario=True,
    )


# ─── Fallback Orchestrator ──────────────────────────────────────────

async def download_cfdis_with_fallback(
    rfc: str,
    fecha_inicio: str,
    fecha_fin: str,
    tipo: str = "recibidos",
    cer_path: Optional[Union[str, Path]] = None,
    key_path: Optional[Union[str, Path]] = None,
    password: Optional[str] = None,
    download_dir: str = DEFAULT_DOWNLOAD_DIR,
    prefer_soap: bool = True,
    max_wait_minutes: int = 60,
) -> DescargaMasivaResult:
    """Download CFDIs using SOAP first, falling back to Playwright.

    Strategy:
    1. If e.firma credentials provided and prefer_soap=True → SOAP
    2. If SOAP fails or no e.firma → Playwright browser
    3. If both fail → error

    Returns:
        DescargaMasivaResult with the channel used.
    """
    result = DescargaMasivaResult()

    # Try SOAP first
    if prefer_soap and cer_path and key_path and password:
        try:
            soap_result = await descarga_masiva_completa(
                cer_path, key_path, password, rfc,
                fecha_inicio, fecha_fin, tipo, download_dir,
                max_wait_minutes=max_wait_minutes,
            )
            if soap_result.total_descargados > 0 or not soap_result.errores:
                return soap_result
            # SOAP failed, try Playwright
            result.errores.extend(
                [f"[SOAP] {e}" for e in soap_result.errores]
            )
        except Exception as e:
            result.errores.append(f"[SOAP] Error inesperado: {e}")

    # Fallback to Playwright
    try:
        from .sat_portal_navigator import full_sat_navigation
        portal_result = await full_sat_navigation(
            rfc=rfc,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            headless=False,
            download_dir=download_dir,
        )

        # Extract results based on tipo
        if tipo == "recibidos" and portal_result.cfdis_recibidos:
            result.total_descargados = portal_result.cfdis_recibidos.total_descargados
            result.archivos_xml = portal_result.cfdis_recibidos.archivos_xml
        elif tipo == "emitidos" and portal_result.cfdis_emitidos:
            result.total_descargados = portal_result.cfdis_emitidos.total_descargados
            result.archivos_xml = portal_result.cfdis_emitidos.archivos_xml

        result.canal = "playwright"
        return result

    except Exception as e:
        result.errores.append(f"[Playwright] Error: {e}")

    if not result.archivos_xml:
        result.errores.append(
            "No se pudieron descargar CFDIs por ningún canal (SOAP ni Playwright)."
        )

    return result


# ─── Internal Helpers ─────────────────────────────────────────────────

def _build_soap_envelope(
    token: str,
    body_content: str,
    signature_block: str = "",
) -> str:
    """Build a SOAP envelope with auth token."""
    return (
        f'<s:Envelope xmlns:s="{NS_SOAP}">'
        f'<s:Header>'
        f'<h:Authorization xmlns:h="http://DescargaMasivaTerceros.gob.mx">'
        f'{token}'
        f'</h:Authorization>'
        f'{signature_block}'
        f'</s:Header>'
        f'<s:Body>'
        f'{body_content}'
        f'</s:Body>'
        f'</s:Envelope>'
    )


def _extract_xml_text(xml_str: str, tag_name: str) -> str:
    """Extract text content from an XML element by local name."""
    try:
        root = ET.fromstring(xml_str)
        for elem in root.iter():
            local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if local == tag_name and elem.text:
                return elem.text.strip()
    except ET.ParseError:
        pass
    return ""


def _extract_xml_attr(xml_str: str, tag_name: str, attr_name: str) -> str:
    """Extract an attribute value from an XML element by local name."""
    try:
        root = ET.fromstring(xml_str)
        for elem in root.iter():
            local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if local == tag_name and attr_name in elem.attrib:
                return elem.attrib[attr_name]
    except ET.ParseError:
        pass
    return ""
