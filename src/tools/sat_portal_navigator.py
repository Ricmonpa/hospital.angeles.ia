"""OpenDoc - SAT Portal Navigator.

Automated read-only browser navigation of the Mexican SAT
(Servicio de Administración Tributaria) portal using Playwright.
Downloads CFDI XMLs and feeds them into the existing parser +
fiscal classifier pipeline.

GOLDEN RULE: This tool NEVER modifies anything on the SAT portal.
All operations are strictly read-only. Every action is logged
with timestamps and screenshots for full audit trail.

Security layers:
1. FORBIDDEN_SELECTORS — Blocks clicks on dangerous elements
2. Audit trail — Every step logged with screenshot
3. No credentials — User does login manually, tool only observes
"""

import asyncio
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from src.tools.cfdi_parser import parse_cfdi, CFDI
from src.tools.fiscal_classifier import classify_cfdi_offline, ClasificacionFiscal
from src.tools import sat_dom_selectors as S  # Verified live DOM selectors (2026-03-03)


# ---------------------------------------------------------------------------
# SAT Portal URLs (read-only navigation targets)
# Validated via live portal testing session (Feb 2026, CIEC auth)
# ---------------------------------------------------------------------------

# Portal CFDI — Factura Electrónica
SAT_PORTAL_BASE = "https://portalcfdi.facturaelectronica.sat.gob.mx"
SAT_LOGIN_URL = f"{SAT_PORTAL_BASE}/"
SAT_CFDI_HOME_URL = f"{SAT_PORTAL_BASE}/Consulta.aspx"
SAT_CFDI_RECIBIDOS_URL = f"{SAT_PORTAL_BASE}/ConsultaReceptor.aspx"
SAT_CFDI_EMITIDOS_URL = f"{SAT_PORTAL_BASE}/ConsultaEmisor.aspx"
SAT_DESCARGA_MASIVA_URL = f"{SAT_PORTAL_BASE}/ConsultaDescargaMasiva.aspx"
SAT_CANCELACION_URL = f"{SAT_PORTAL_BASE}/ConsultaCancelacion.aspx"

# Portal Retenciones (different subdomain: clouda.sat.gob.mx)
SAT_RETENCIONES_BASE = "https://prodretencioncontribuyente.clouda.sat.gob.mx"
SAT_RETENCIONES_URL = f"{SAT_RETENCIONES_BASE}/?oculta=1"
SAT_RETENCIONES_RECIBIDAS_URL = f"{SAT_RETENCIONES_BASE}/ConsultaReceptor"
SAT_RETENCIONES_EMITIDAS_URL = f"{SAT_RETENCIONES_BASE}/ConsultaEmisor"
SAT_RETENCIONES_MASIVA_URL = f"{SAT_RETENCIONES_BASE}/ConsultaDescargaMasiva"  # ⚠️ NO /ConsultaMasiva (da 503)
SAT_RETENCIONES_AUTH_HOST = "cfdiau.sat.gob.mx"   # SSO redirect host for Retenciones auth

# Portal SAT Principal
SAT_MAIN_BASE = "https://sat.gob.mx"
SAT_CONSTANCIA_INFO_URL = f"{SAT_MAIN_BASE}/portal/public/tramites/constancia-de-situacion-fiscal"
SAT_OPINION_CUMPLIMIENTO_URL = f"{SAT_MAIN_BASE}/portal/public/tramites/mas-tramites"

# Portal Autenticado — Buzón Tributario (wwwmat.sat.gob.mx)
SAT_BUZON_BASE = "https://wwwmat.sat.gob.mx"
SAT_BUZON_SERVICIOS_URL = f"{SAT_BUZON_BASE}/operacion/00834/servicios-disponibles-del-buzon-tributario"
SAT_CONSTANCIA_GENERATE_URL = f"{SAT_BUZON_BASE}/operacion/43824/reimprime-tus-acuses-del-rfc"
SAT_BUZON_LOGIN_URL = f"{SAT_BUZON_BASE}/personas/iniciar-sesion"
SAT_BUZON_DECLARACIONES_URL = f"{SAT_BUZON_BASE}/personas/declaraciones"

# ─── Phase 6.5: Complete SAT Ecosystem ────────────────────────────────

# Verificador de CFDI (PÚBLICO — no requiere login)
SAT_VERIFICADOR_BASE = "https://verificacfdi.facturaelectronica.sat.gob.mx"
SAT_VERIFICADOR_URL = f"{SAT_VERIFICADOR_BASE}/default.aspx"
SAT_VERIFICADOR_CCP_URL = f"{SAT_VERIFICADOR_BASE}/verificaccp/default.aspx"
SAT_VERIFICADOR_SOAP_URL = "https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc"

# Verificador de Retenciones (PÚBLICO)
SAT_VERIFICADOR_RETENCIONES_URL = "https://prodretencionverificacion.clouda.sat.gob.mx/"

# DeclaraSAT — Declaraciones Mensuales y Anual
SAT_DECLARACION_MENSUAL_612_URL = f"{SAT_BUZON_BASE}/declaracion/33006/presenta-tu-declaracion-de-actividades-empresariales-y-servicios-profesionales,-arrendamiento-e-iva,-personas-fisicas-de-2025-en-adelante-(simulador)"
SAT_DECLARACION_MENSUAL_RESICO_URL = f"{SAT_BUZON_BASE}/declaracion/53359/simulador-de-declaraciones-de-pagos-mensuales-y-definitivos"
SAT_DECLARACION_MENSUAL_LEGACY_URL = f"{SAT_BUZON_BASE}/declaracion/26984/declaracion-mensual-en-el-servicio-de-declaraciones-y-pagos"
SAT_DECLARACION_ANUAL_URL = f"{SAT_BUZON_BASE}/DeclaracionAnual/Paginas/default.htm"
SAT_LINEA_CAPTURA_URL = f"{SAT_BUZON_BASE}/declaracion/98410/contribuciones-que-puedes-pagar-con-linea-de-captura"

# Mi Portal SAT — Hub central de servicios
SAT_MI_PORTAL_BASE = "https://portalsat.plataforma.sat.gob.mx"
SAT_MI_PORTAL_LOGIN_URL = f"{SAT_MI_PORTAL_BASE}/SATAuthenticator/AuthLogin/showLogin.action"
SAT_MI_PORTAL_CERTISAT_URL = f"{SAT_MI_PORTAL_BASE}/certisat/"
SAT_MI_PORTAL_CERTIFICA_URL = f"{SAT_MI_PORTAL_BASE}/certifica/"

# CertiSAT Web — Certificados de Sello Digital (requiere e.firma)
SAT_CERTISAT_URL = "https://aplicacionesc.mat.sat.gob.mx/certisat/"

# Contabilidad Electrónica (solo Régimen 612, requiere e.firma)
SAT_CONTABILIDAD_ELECTRONICA_URL = f"{SAT_MAIN_BASE}/aplicacion/42150/envia-tu-contabilidad-electronica"
SAT_CONTABILIDAD_ELECTRONICA_AUTH_URL = f"{SAT_BUZON_BASE}/aplicacion/42150/envia-tu-contabilidad-electronica"

# DIOT — Operaciones con Terceros (solo Régimen 612, requiere e.firma)
SAT_DIOT_BASE = "https://pstcdi.clouda.sat.gob.mx"
SAT_DIOT_URL = SAT_DIOT_BASE
SAT_DIOT_INFO_URL = f"{SAT_MAIN_BASE}/declaracion/74295/presenta-tu-declaracion-informativa-de-operaciones-con-terceros-(diot)-"

# Pagos Referenciados — Línea de captura
SAT_PAGOS_REFERENCIADOS_URL = f"{SAT_MAIN_BASE}/declaracion/20425/bancos-autorizados-para-recibir-pagos-de-contribuciones-federales"

# Visor de Nómina — Patrón y Trabajador
SAT_VISOR_NOMINA_PATRON_URL = f"{SAT_MAIN_BASE}/declaracion/90887/consulta-el-visor-de-comprobantes-de-nomina-para-el-patron-"
SAT_VISOR_NOMINA_TRABAJADOR_URL = f"{SAT_MAIN_BASE}/declaracion/97720/consulta-el-visor-de-comprobantes-de-nomina-para-el-trabajador"

# SAT ID (biométrico — solo referencia)
SAT_ID_URL = "https://satid.sat.gob.mx/"

# Portales Gobierno Relacionados (futuro)
IMSS_IDSE_URL = "https://idse.imss.gob.mx"
INFONAVIT_EMPRESARIOS_URL = "https://empresarios.infonavit.org.mx"

# Legacy aliases (for backwards compatibility)
SAT_CONSTANCIA_URL = SAT_CONSTANCIA_INFO_URL
SAT_BUZON_URL = SAT_BUZON_SERVICIOS_URL

# ---------------------------------------------------------------------------
# SAT Portal Table Column Mapping (Facturas Recibidas — 18 columns)
# Discovered via live testing of ConsultaReceptor.aspx results table
# ---------------------------------------------------------------------------
RECIBIDOS_TABLE_COLUMNS = [
    "checkbox",                     # Select all / individual
    "acciones",                     # Icons: ver detalle, descargar XML, ver documento
    "folio_fiscal",                 # UUID
    "rfc_emisor",                   # RFC Emisor
    "nombre_emisor",                # Nombre o Razón Social del Emisor
    "rfc_receptor",                 # RFC Receptor
    "nombre_receptor",              # Nombre o Razón Social del Receptor
    "fecha_emision",                # ISO: 2026-01-01T13:02:14
    "fecha_certificacion",          # Fecha de Certificación
    "pac_certifico",                # RFC del PAC que Certificó
    "total",                        # Monto con $
    "efecto_comprobante",           # Ingreso, Egreso, etc.
    "estatus_cancelacion",          # Cancelable sin aceptación, etc.
    "estado_comprobante",           # Vigente, Cancelado
    "estatus_proceso_cancelacion",  # Estatus de Proceso de Cancelación
    "fecha_solicitud_cancelacion",  # Fecha de Solicitud de Cancelación
    "fecha_cancelacion",            # Fecha de Cancelación
    "rfc_cuenta_terceros",          # RFC a cuenta de terceros
]

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------
SAT_PAGE_TIMEOUT_MS = 30_000         # 30s per page load
SAT_SESSION_TIMEOUT_SEC = 300        # 5 min inactivity = session expired
SAT_ELEMENT_TIMEOUT_MS = 10_000      # 10s waiting for element
SAT_LOGIN_WAIT_TIMEOUT_SEC = 180     # 3 min max waiting for user login
SAT_LOGIN_POLL_INTERVAL_SEC = 2.0    # Poll every 2 seconds

# ---------------------------------------------------------------------------
# Read-only enforcement: selectors that MUST NEVER be clicked
# ---------------------------------------------------------------------------
FORBIDDEN_SELECTORS = [
    # Cancellation actions
    "input[value*='Cancelar']",
    "a[href*='Cancelacion']",
    "a[href*='cancelacion']",
    "button[id*='cancel']",
    "button[id*='Cancel']",
    # Modification actions
    "a[href*='Modificar']",
    "a[href*='modificar']",
    "input[value*='Modificar']",
    # Submission actions (forms that create/modify data)
    "input[type='submit'][value*='Enviar']",
    "input[type='submit'][value*='Guardar']",
    "input[type='submit'][value*='Confirmar']",
    "button[type='submit'][id*='enviar']",
    # Deletion actions
    "a[href*='Eliminar']",
    "input[value*='Eliminar']",
    "button[id*='delete']",
    # CFDI generation (creating new invoices)
    "a[href*='Generar']",
    "a[href*='generar']",
    "input[value*='Generar']",
    # Buzon Tributario write actions
    "a[href*='Responder']",
    "input[value*='Acuse']",
    # Verified specific dangerous element IDs — extracted from live DOM 2026-03-03
    # ConsultaEmisor.aspx — cancellation flow
    "#ctl00_MainContent_BtnCancelar",           # "Cancelar Seleccionados"
    "#ctl00_MainContent_btnCancelarModal",       # Submit in cancellation modal
    # ConsultaCancelacion.aspx — accept/reject cancellation requests
    "#BtnDeclinaCancelacion",                   # "Rechazar Seleccionados"
    "#BtnAceptaCancelacion",                    # "Aceptar Seleccionados"
    "#ctl00_MainContent_RechazaCancelacion",     # PostBack — executes rejection
    "#ctl00_MainContent_AceptaCancelacion",      # PostBack — executes acceptance
    # ConsultaEmisor.aspx — addenda upload
    "#integrar",                                # "Integrar" addenda submit
    # Retenciones (prodretencioncontribuyente.clouda.sat.gob.mx) — cancellation modals
    "#btnAlertDCCancelar",                      # "Cancelar seleccionados" (Retenciones)
    "#btnCancelar",                             # "Continuar" in cancellation confirmation modal
]

# ---------------------------------------------------------------------------
# Default directories
# ---------------------------------------------------------------------------
DEFAULT_DOWNLOAD_DIR = "/app/data/sat_downloads"
DEFAULT_SCREENSHOT_DIR = "/app/data/sat_screenshots"
DEFAULT_AUDIT_DIR = "/app/data/sat_audit"


# ===================================================================
# CUSTOM EXCEPTIONS
# ===================================================================

class SATReadOnlyViolation(Exception):
    """Raised when an operation would modify data on the SAT portal."""
    pass


class SATSessionExpired(Exception):
    """Raised when the SAT session has timed out."""
    pass


class SATCaptchaDetected(Exception):
    """Raised when a CAPTCHA blocks navigation and requires human intervention."""
    pass


# ===================================================================
# DATACLASSES
# ===================================================================

@dataclass
class SATNavigationStep:
    """A single recorded step in the SAT portal navigation."""
    timestamp: str
    action: str           # "navigate", "click", "wait", "screenshot", "download", "BLOCKED"
    url: str
    description: str
    screenshot_path: Optional[str] = None
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SATSession:
    """Represents an authenticated SAT portal session."""
    rfc: str
    session_type: str     # "CIEC" or "FIEL"
    authenticated: bool = False
    authenticated_at: Optional[str] = None
    last_activity: Optional[str] = None
    navigation_log: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        status = "Autenticado" if self.authenticated else "No autenticado"
        steps = len(self.navigation_log)
        return f"SAT Session | RFC: {self.rfc} | {status} | {steps} pasos registrados"

    def add_step(self, step: SATNavigationStep) -> None:
        """Append a navigation step and update last_activity."""
        self.navigation_log.append(step)
        self.last_activity = step.timestamp


@dataclass
class CFDIDownloadResult:
    """Result of downloading CFDIs from the SAT portal."""
    tipo: str             # "recibidos" or "emitidos"
    fecha_inicio: str
    fecha_fin: str
    total_encontrados: int = 0
    total_descargados: int = 0
    archivos_xml: list = field(default_factory=list)
    errores: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        return (
            f"CFDI {self.tipo.capitalize()} | "
            f"{self.fecha_inicio} → {self.fecha_fin} | "
            f"{self.total_descargados}/{self.total_encontrados} descargados"
        )


@dataclass
class ConstanciaSituacionFiscal:
    """Data captured from Constancia de Situación Fiscal page."""
    rfc: str
    nombre: str
    regimen_fiscal: str
    regimen_desc: str
    codigo_postal: str
    estatus_padron: str       # "Activo", "Suspendido", etc.
    fecha_inicio_operaciones: Optional[str] = None
    obligaciones: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        return (
            f"Constancia | {self.nombre} | RFC: {self.rfc} | "
            f"{self.estatus_padron} | Régimen: {self.regimen_desc}"
        )


@dataclass
class BuzonNotificacion:
    """A single notification from Buzón Tributario."""
    tipo: str
    fecha: str
    asunto: str
    leida: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BuzonTributarioResult:
    """Notifications from Buzón Tributario."""
    total_notificaciones: int = 0
    no_leidas: int = 0
    notificaciones: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        return (
            f"Buzón Tributario | {self.total_notificaciones} notificaciones | "
            f"{self.no_leidas} sin leer"
        )


@dataclass
class SATPortalResult:
    """Complete result of a SAT portal navigation session."""
    session: SATSession
    cfdis_recibidos: Optional[CFDIDownloadResult] = None
    cfdis_emitidos: Optional[CFDIDownloadResult] = None
    constancia: Optional[ConstanciaSituacionFiscal] = None
    buzon: Optional[BuzonTributarioResult] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        parts = [self.session.summary()]
        if self.cfdis_recibidos:
            parts.append(f"  📥 {self.cfdis_recibidos.summary()}")
        if self.cfdis_emitidos:
            parts.append(f"  📤 {self.cfdis_emitidos.summary()}")
        if self.constancia:
            parts.append(f"  📋 {self.constancia.summary()}")
        if self.buzon:
            parts.append(f"  📬 {self.buzon.summary()}")
        return "\n".join(parts)


# ===================================================================
# INTERNAL HELPER FUNCTIONS
# ===================================================================

def _now_iso() -> str:
    """Return current timestamp in ISO format."""
    return datetime.now().isoformat()


def _ensure_dir(path: str) -> Path:
    """Ensure directory exists, create if needed."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


async def _take_nav_screenshot(
    page: Page,
    session: SATSession,
    action: str,
    description: str,
    screenshot_dir: str = DEFAULT_SCREENSHOT_DIR,
) -> SATNavigationStep:
    """Take a screenshot and record a navigation step for audit trail."""
    timestamp = _now_iso()
    step_num = len(session.navigation_log) + 1

    # Build screenshot path
    date_str = datetime.now().strftime("%Y-%m-%d")
    session_dir = _ensure_dir(
        f"{screenshot_dir}/{session.rfc}_{date_str}"
    )
    screenshot_filename = f"step_{step_num:03d}_{action}.png"
    screenshot_path = str(session_dir / screenshot_filename)

    try:
        await page.screenshot(path=screenshot_path, full_page=False)
    except Exception:
        screenshot_path = None

    step = SATNavigationStep(
        timestamp=timestamp,
        action=action,
        url=page.url,
        description=description,
        screenshot_path=screenshot_path,
        success=True,
    )
    session.add_step(step)
    return step


def _is_forbidden(selector: str) -> bool:
    """Check if a selector matches any forbidden pattern."""
    selector_lower = selector.lower()
    for forbidden in FORBIDDEN_SELECTORS:
        # Direct match
        if selector_lower == forbidden.lower():
            return True
        # Check if the key identifying parts match
        # e.g., "Cancelar" in selector
        forbidden_lower = forbidden.lower()
        for keyword in ["cancelar", "cancelacion", "modificar", "eliminar",
                        "enviar", "guardar", "confirmar", "generar", "responder"]:
            if keyword in selector_lower and keyword in forbidden_lower:
                return True
    return False


async def _safe_click(
    page: Page,
    selector: str,
    session: SATSession,
    description: str = "",
) -> None:
    """Click an element ONLY if it is not in the forbidden selectors list.

    Every click passes through this function for read-only enforcement.

    Raises:
        SATReadOnlyViolation: If the selector matches a forbidden action.
    """
    # Layer 1: Check forbidden selectors
    if _is_forbidden(selector):
        step = SATNavigationStep(
            timestamp=_now_iso(),
            action="BLOCKED",
            url=page.url,
            description=f"BLOQUEADO: Click prohibido en '{selector}'",
            success=False,
            error="Read-only violation prevented",
        )
        session.add_step(step)
        raise SATReadOnlyViolation(
            f"Cannot click forbidden selector: {selector}"
        )

    # Layer 2: Log the click BEFORE executing
    step = SATNavigationStep(
        timestamp=_now_iso(),
        action="click",
        url=page.url,
        description=description or f"Click: {selector}",
        success=True,
    )
    session.add_step(step)

    # Layer 3: Execute
    await page.click(selector, timeout=SAT_ELEMENT_TIMEOUT_MS)


async def _check_session_alive(page: Page, session: SATSession) -> bool:
    """Check if the SAT session is still active.

    Detects session expiry by:
    1. Time since last activity
    2. Redirect to login page
    3. Missing authenticated elements
    """
    # Check 1: Time-based expiry
    if session.last_activity:
        try:
            last = datetime.fromisoformat(session.last_activity)
            elapsed = (datetime.now() - last).total_seconds()
            if elapsed > SAT_SESSION_TIMEOUT_SEC:
                return False
        except ValueError:
            pass

    # Check 2: URL-based — redirected to login?
    current_url = page.url.lower()
    if "login" in current_url or "expired" in current_url:
        return False

    # Check 3: Element-based — still see authenticated indicators?
    is_auth, _ = await detect_auth_state(page)
    return is_auth


# ===================================================================
# AUTHENTICATION DETECTION
# ===================================================================

async def detect_auth_state(page: Page) -> tuple:
    """Detect whether the user is logged into the SAT portal.

    Uses multiple signals for confidence:
    - RFC visible on page
    - Logout link/button present
    - Navigation menu present

    Returns:
        Tuple of (is_authenticated: bool, rfc_found: str)
    """
    signals = 0
    rfc_found = ""

    current_url = page.url.lower()

    # Signal 1: URL check — login page means not authenticated
    if "login" in current_url and "consulta" not in current_url:
        return False, ""

    # Signal 2: Look for RFC display element (#ctl00_LblRfcAutenticado — SPAN.signin)
    try:
        rfc_el = await page.query_selector(S.AUTH_RFC_INDICATOR)
        if rfc_el:
            text = await rfc_el.inner_text()
            text = text.strip()
            # RFC pattern: 3-4 letters + 6 digits + 3 alphanum
            if len(text) >= 12 and len(text) <= 13:
                rfc_found = text
                signals += 1
    except Exception:
        pass

    # Signal 3: Look for logout link (#anchorClose — "Salir")
    try:
        logout = await page.query_selector(S.AUTH_LOGOUT_LINK)
        if logout:
            signals += 1
    except Exception:
        pass

    # Signal 4: Look for portal main content panel (only present when authenticated)
    try:
        menu = await page.query_selector(S.HOME_MAIN_PANEL)
        if menu:
            signals += 1
    except Exception:
        pass

    # At least 2 signals for confidence
    authenticated = signals >= 2
    return authenticated, rfc_found


async def detect_captcha(page: Page) -> bool:
    """Detect if a CAPTCHA is present on the current page.

    Returns True if CAPTCHA found, allowing caller to pause
    and request user intervention.
    """
    captcha_selectors = [
        "img[src*='captcha']",
        "img[src*='Captcha']",
        "[id*='captcha']",
        "[class*='captcha']",
        "[id*='recaptcha']",
        "iframe[src*='recaptcha']",
        "iframe[src*='captcha']",
    ]
    for sel in captcha_selectors:
        try:
            el = await page.query_selector(sel)
            if el:
                return True
        except Exception:
            pass
    return False


# ===================================================================
# BROWSER SETUP
# ===================================================================

async def create_sat_browser(
    headless: bool = True,
    download_dir: str = DEFAULT_DOWNLOAD_DIR,
) -> tuple:
    """Create and configure a Playwright browser for SAT navigation.

    Returns:
        Tuple of (playwright_instance, browser, context, page)
    """
    _ensure_dir(download_dir)

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="es-MX",
        timezone_id="America/Mexico_City",
        accept_downloads=True,
    )
    # Set default timeouts
    context.set_default_timeout(SAT_PAGE_TIMEOUT_MS)
    context.set_default_navigation_timeout(SAT_PAGE_TIMEOUT_MS)

    page = await context.new_page()
    return pw, browser, context, page


# ===================================================================
# LOGIN WAIT
# ===================================================================

async def wait_for_user_login(
    page: Page,
    timeout_seconds: int = SAT_LOGIN_WAIT_TIMEOUT_SEC,
    poll_interval: float = SAT_LOGIN_POLL_INTERVAL_SEC,
) -> SATSession:
    """Navigate to SAT portal and wait for user to complete login.

    The tool does NOT handle credentials. It opens the login page,
    then polls until it detects the user has authenticated.

    Returns:
        SATSession with authenticated=True and detected RFC.

    Raises:
        TimeoutError: If user doesn't login within timeout.
        SATCaptchaDetected: If CAPTCHA blocks the login page.
    """
    # Navigate to login page
    await page.goto(SAT_LOGIN_URL, wait_until="domcontentloaded")

    session = SATSession(rfc="", session_type="unknown")

    step = SATNavigationStep(
        timestamp=_now_iso(),
        action="navigate",
        url=page.url,
        description="Portal SAT abierto, esperando autenticación del usuario",
    )
    session.add_step(step)

    # Poll for authentication
    elapsed = 0.0
    while elapsed < timeout_seconds:
        # Check for CAPTCHA
        if await detect_captcha(page):
            raise SATCaptchaDetected(
                "CAPTCHA detectado en el portal SAT. "
                "Requiere intervención humana."
            )

        # Check authentication
        is_auth, rfc = await detect_auth_state(page)
        if is_auth:
            session.rfc = rfc
            session.authenticated = True
            session.authenticated_at = _now_iso()
            session.last_activity = _now_iso()

            # Detect auth type from URL or page content
            if "fiel" in page.url.lower() or "firma" in page.url.lower():
                session.session_type = "FIEL"
            else:
                session.session_type = "CIEC"

            step = SATNavigationStep(
                timestamp=_now_iso(),
                action="auth_detected",
                url=page.url,
                description=f"Autenticación detectada | RFC: {rfc} | Tipo: {session.session_type}",
            )
            session.add_step(step)
            return session

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    raise TimeoutError(
        f"El usuario no completó el login en {timeout_seconds} segundos"
    )


# ===================================================================
# CFDI DOWNLOAD NAVIGATION
# ===================================================================

async def _download_cfdi_xml(
    page: Page,
    session: SATSession,
    download_button_selector: str,
    download_dir: str,
    cfdi_uuid: str = "unknown",
) -> Optional[str]:
    """Download a single CFDI XML from a search result row.

    Returns:
        Path to downloaded file, or None if download failed.
    """
    try:
        async with page.expect_download(
            timeout=SAT_ELEMENT_TIMEOUT_MS
        ) as download_info:
            await _safe_click(
                page, download_button_selector, session,
                description=f"Descarga XML CFDI {cfdi_uuid}",
            )
        download = await download_info.value

        # Save with meaningful name
        filename = download.suggested_filename or f"{cfdi_uuid}.xml"
        save_path = str(Path(download_dir) / filename)
        await download.save_as(save_path)

        # Verify valid XML
        try:
            ET.parse(save_path)
        except ET.ParseError:
            return None

        return save_path

    except Exception as e:
        step = SATNavigationStep(
            timestamp=_now_iso(),
            action="download_error",
            url=page.url,
            description=f"Error descargando CFDI {cfdi_uuid}: {str(e)}",
            success=False,
            error=str(e),
        )
        session.add_step(step)
        return None


async def navigate_cfdi_recibidos(
    page: Page,
    session: SATSession,
    fecha_inicio: str,
    fecha_fin: str,
    rfc_emisor: Optional[str] = None,
    download_dir: str = DEFAULT_DOWNLOAD_DIR,
) -> CFDIDownloadResult:
    """Navigate to CFDI Recibidos, apply filters, and download XMLs.

    Read-only operations only:
    1. Navigate to ConsultaReceptor.aspx
    2. Set date range filters
    3. Optionally filter by emisor RFC
    4. Click search
    5. Download each XML
    6. Screenshot at each step for audit

    Raises:
        SATSessionExpired: If session times out during navigation.
    """
    result = CFDIDownloadResult(
        tipo="recibidos",
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    # Ensure download directory exists
    dl_dir = _ensure_dir(f"{download_dir}/{session.rfc}/recibidos")

    # Check session before starting
    if not await _check_session_alive(page, session):
        raise SATSessionExpired("Sesión SAT expirada antes de consultar recibidos")

    # Step 1: Navigate to CFDI Recibidos page
    await page.goto(SAT_CFDI_RECIBIDOS_URL, wait_until="domcontentloaded")
    await _take_nav_screenshot(
        page, session, "navigate",
        "Navegando a consulta de CFDI Recibidos",
    )

    # Step 2: Select date mode and fill dropdowns
    # NOTE: ConsultaReceptor uses SELECT dropdowns (año/mes/día + time range),
    # NOT text inputs. The form searches within a single day (fecha_inicio).
    # fecha_fin is parsed for consistency but the portal only takes one date.
    try:
        # Activate date mode radio button
        await page.click(S.RECIBIDOS_RADIO_FECHA)
        await page.wait_for_selector(
            S.RECIBIDOS_DATE_CONTAINER, state="visible", timeout=SAT_ELEMENT_TIMEOUT_MS
        )

        # Parse date: expected format YYYY-MM-DD
        fi_parts = fecha_inicio.split("-")   # ["YYYY", "MM", "DD"]

        # Fill dropdowns for start date
        # DdlAnio has no ctl00_ prefix — portal inconsistency, use S constant
        await page.select_option(S.RECIBIDOS_SELECT_ANIO, fi_parts[0])
        await page.select_option(S.RECIBIDOS_SELECT_MES, fi_parts[1])
        await page.select_option(S.RECIBIDOS_SELECT_DIA, fi_parts[2])
        # Leave time range at defaults: 00:00:00 → 23:59:59 (full day)

        # Optional: filter by emisor RFC
        # NOTE: TxtRfcReceptor is the ID but it filters by RFC EMISOR (portal quirk)
        if rfc_emisor:
            await page.fill(S.RECIBIDOS_INPUT_RFC_EMISOR, rfc_emisor)

        await _take_nav_screenshot(
            page, session, "fill_filters",
            f"Filtros aplicados: {fecha_inicio} → {fecha_fin}",
        )

    except Exception as e:
        result.errores.append(f"Error aplicando filtros: {str(e)}")
        return result

    # Step 3: Click search button
    try:
        await _safe_click(page, S.RECIBIDOS_BTN_BUSCAR, session, "Buscar CFDI Recibidos")

        # Wait for results to load
        await page.wait_for_load_state("networkidle", timeout=SAT_PAGE_TIMEOUT_MS)
        await _take_nav_screenshot(
            page, session, "search_results",
            "Resultados de búsqueda CFDI Recibidos",
        )

    except SATReadOnlyViolation:
        raise
    except Exception as e:
        result.errores.append(f"Error en búsqueda: {str(e)}")
        return result

    # Step 4: Count and download results
    try:
        # Wait for UpdatePanel AJAX to finish
        await page.wait_for_selector(
            S.RECIBIDOS_UPDATE_PANEL, state="visible", timeout=SAT_PAGE_TIMEOUT_MS
        )

        # Look for result rows in the verified table
        rows = await page.query_selector_all(
            f"{S.RECIBIDOS_TABLE} tbody tr"
        )
        result.total_encontrados = len(rows)

        await _take_nav_screenshot(
            page, session, "results_count",
            f"Encontrados: {result.total_encontrados} CFDIs",
        )

        # Download each XML — icon verified: SPAN#BtnDescarga (glyphicon-cloud-download)
        for i, row in enumerate(rows):
            xml_link = await row.query_selector(S.RECIBIDOS_ICON_XML)
            if xml_link:
                row_text = await row.inner_text()
                uuid = _extract_uuid_from_text(row_text)

                file_path = await _download_cfdi_xml(
                    page, session,
                    f"{S.RECIBIDOS_TABLE} tbody tr:nth-child({i + 1}) {S.RECIBIDOS_ICON_XML}",
                    str(dl_dir),
                    cfdi_uuid=uuid or f"recibido_{i + 1}",
                )
                if file_path:
                    result.archivos_xml.append(file_path)
                    result.total_descargados += 1

    except SATReadOnlyViolation:
        raise
    except Exception as e:
        result.errores.append(f"Error descargando XMLs: {str(e)}")

    return result


async def navigate_cfdi_emitidos(
    page: Page,
    session: SATSession,
    fecha_inicio: str,
    fecha_fin: str,
    rfc_receptor: Optional[str] = None,
    download_dir: str = DEFAULT_DOWNLOAD_DIR,
) -> CFDIDownloadResult:
    """Navigate to CFDI Emitidos, apply filters, and download XMLs.

    Same pattern as recibidos but on ConsultaEmisor.aspx.
    """
    result = CFDIDownloadResult(
        tipo="emitidos",
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    dl_dir = _ensure_dir(f"{download_dir}/{session.rfc}/emitidos")

    if not await _check_session_alive(page, session):
        raise SATSessionExpired("Sesión SAT expirada antes de consultar emitidos")

    # Navigate to emitidos page
    await page.goto(SAT_CFDI_EMITIDOS_URL, wait_until="domcontentloaded")
    await _take_nav_screenshot(
        page, session, "navigate",
        "Navegando a consulta de CFDI Emitidos",
    )

    # Fill filters
    # NOTE: ConsultaEmisor uses TEXT INPUTS + calendar icon (not dropdowns like Recibidas).
    # Dates must be in DD/MM/YYYY format for the calendar text input.
    try:
        # Activate date mode radio button
        await page.click(S.EMITIDOS_RADIO_FECHA)
        await page.wait_for_selector(
            S.EMITIDOS_CAL_FECHA_INI_CONTAINER, state="visible",
            timeout=SAT_ELEMENT_TIMEOUT_MS
        )

        # Convert YYYY-MM-DD to DD/MM/YYYY (format expected by calendar input)
        def to_ddmmyyyy(iso_date: str) -> str:
            parts = iso_date.split("-")
            return f"{parts[2]}/{parts[1]}/{parts[0]}"

        await page.fill(S.EMITIDOS_CAL_FECHA_INI_INPUT, to_ddmmyyyy(fecha_inicio))
        await page.fill(S.EMITIDOS_CAL_FECHA_FIN_INPUT, to_ddmmyyyy(fecha_fin))

        # Optional: filter by receptor RFC
        if rfc_receptor:
            await page.fill(S.EMITIDOS_INPUT_RFC_RECEPTOR, rfc_receptor)

        await _take_nav_screenshot(
            page, session, "fill_filters",
            f"Filtros emitidos: {fecha_inicio} → {fecha_fin}",
        )

    except Exception as e:
        result.errores.append(f"Error aplicando filtros emitidos: {str(e)}")
        return result

    # Search
    try:
        await _safe_click(page, S.EMITIDOS_BTN_BUSCAR, session, "Buscar CFDI Emitidos")
        await page.wait_for_load_state("networkidle", timeout=SAT_PAGE_TIMEOUT_MS)
        await _take_nav_screenshot(
            page, session, "search_results",
            "Resultados de búsqueda CFDI Emitidos",
        )
    except SATReadOnlyViolation:
        raise
    except Exception as e:
        result.errores.append(f"Error en búsqueda emitidos: {str(e)}")
        return result

    # Download results
    try:
        # Wait for UpdatePanel AJAX to finish
        await page.wait_for_selector(
            S.EMITIDOS_UPDATE_PANEL, state="visible", timeout=SAT_PAGE_TIMEOUT_MS
        )

        rows = await page.query_selector_all(
            f"{S.EMITIDOS_TABLE} tbody tr"
        )
        result.total_encontrados = len(rows)

        # Download each XML — icon verified: SPAN#BtnDescarga (glyphicon-cloud-download)
        for i, row in enumerate(rows):
            xml_link = await row.query_selector(S.EMITIDOS_ICON_XML)
            if xml_link:
                row_text = await row.inner_text()
                uuid = _extract_uuid_from_text(row_text)

                file_path = await _download_cfdi_xml(
                    page, session,
                    f"{S.EMITIDOS_TABLE} tbody tr:nth-child({i + 1}) {S.EMITIDOS_ICON_XML}",
                    str(dl_dir),
                    cfdi_uuid=uuid or f"emitido_{i + 1}",
                )
                if file_path:
                    result.archivos_xml.append(file_path)
                    result.total_descargados += 1

    except SATReadOnlyViolation:
        raise
    except Exception as e:
        result.errores.append(f"Error descargando XMLs emitidos: {str(e)}")

    return result


def _extract_uuid_from_text(text: str) -> Optional[str]:
    """Extract a UUID from text (format: 8-4-4-4-12 hex)."""
    import re
    pattern = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    match = re.search(pattern, text)
    return match.group(0) if match else None


# ===================================================================
# CONSTANCIA DE SITUACIÓN FISCAL
# ===================================================================

async def navigate_constancia(
    page: Page,
    session: SATSession,
) -> ConstanciaSituacionFiscal:
    """Navigate to Constancia de Situación Fiscal and extract data.

    Reads on-screen data only — does NOT download PDF or modify anything.
    """
    if not await _check_session_alive(page, session):
        raise SATSessionExpired("Sesión SAT expirada antes de consultar constancia")

    await page.goto(SAT_CONSTANCIA_URL, wait_until="domcontentloaded")
    await _take_nav_screenshot(
        page, session, "navigate",
        "Navegando a Constancia de Situación Fiscal",
    )

    # Extract data from page elements
    rfc = await _get_text_by_selectors(page, [
        "[id*='RFC'], [id*='rfc']",
        "td:has-text('RFC') + td",
        "span:has-text('RFC') + span",
    ]) or session.rfc

    nombre = await _get_text_by_selectors(page, [
        "[id*='Nombre'], [id*='nombre']",
        "td:has-text('Nombre') + td",
        "td:has-text('Razón Social') + td",
    ]) or ""

    regimen = await _get_text_by_selectors(page, [
        "[id*='Regimen'], [id*='regimen']",
        "td:has-text('Régimen') + td",
    ]) or ""

    cp = await _get_text_by_selectors(page, [
        "[id*='CodigoPostal'], [id*='codigo']",
        "td:has-text('Código Postal') + td",
    ]) or ""

    estatus = await _get_text_by_selectors(page, [
        "[id*='Estatus'], [id*='estatus']",
        "td:has-text('Estatus') + td",
        "td:has-text('Estado') + td",
    ]) or "Desconocido"

    fecha_inicio = await _get_text_by_selectors(page, [
        "[id*='FechaInicio'], [id*='fechaInicio']",
        "td:has-text('Fecha de Inicio') + td",
    ])

    await _take_nav_screenshot(
        page, session, "constancia_captured",
        f"Constancia capturada: {nombre} | {estatus}",
    )

    return ConstanciaSituacionFiscal(
        rfc=rfc.strip(),
        nombre=nombre.strip(),
        regimen_fiscal=regimen.strip(),
        regimen_desc=regimen.strip(),
        codigo_postal=cp.strip(),
        estatus_padron=estatus.strip(),
        fecha_inicio_operaciones=fecha_inicio.strip() if fecha_inicio else None,
    )


async def _get_text_by_selectors(
    page: Page,
    selectors: list,
) -> Optional[str]:
    """Try multiple selectors, return text of first match."""
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el:
                text = await el.inner_text()
                if text and text.strip():
                    return text.strip()
        except Exception:
            pass
    return None


# ===================================================================
# BUZÓN TRIBUTARIO
# ===================================================================

async def navigate_buzon_tributario(
    page: Page,
    session: SATSession,
) -> BuzonTributarioResult:
    """Navigate to Buzón Tributario and list notifications.

    READ-ONLY: Only reads notification list.
    NEVER marks as read or responds to anything.
    """
    if not await _check_session_alive(page, session):
        raise SATSessionExpired("Sesión SAT expirada antes de consultar buzón")

    await page.goto(SAT_BUZON_URL, wait_until="domcontentloaded")
    await _take_nav_screenshot(
        page, session, "navigate",
        "Navegando a Buzón Tributario",
    )

    result = BuzonTributarioResult()
    notificaciones = []

    try:
        # Look for notification rows
        rows = await page.query_selector_all(
            "table tbody tr, [class*='notificacion'], "
            "[class*='mensaje'], .list-item"
        )

        for row in rows:
            try:
                text = await row.inner_text()
                if text and text.strip():
                    # Try to parse notification structure
                    notif = BuzonNotificacion(
                        tipo="Notificación",
                        fecha="",
                        asunto=text.strip()[:200],  # Limit length
                        leida=False,
                    )
                    notificaciones.append(notif)
            except Exception:
                pass

        result.notificaciones = [n.to_dict() for n in notificaciones]
        result.total_notificaciones = len(notificaciones)
        result.no_leidas = sum(1 for n in notificaciones if not n.leida)

    except Exception as e:
        step = SATNavigationStep(
            timestamp=_now_iso(),
            action="buzon_error",
            url=page.url,
            description=f"Error leyendo buzón: {str(e)}",
            success=False,
            error=str(e),
        )
        session.add_step(step)

    await _take_nav_screenshot(
        page, session, "buzon_read",
        f"Buzón: {result.total_notificaciones} notificaciones leídas",
    )

    return result


# ===================================================================
# PIPELINE INTEGRATION
# ===================================================================

async def process_downloaded_cfdis(
    download_result: CFDIDownloadResult,
    doctor_rfc: str,
    use_gemini: bool = False,
) -> list:
    """Feed downloaded CFDI XMLs into the existing parser + classifier pipeline.

    For each downloaded XML file:
    1. parse_cfdi(xml_path) -> CFDI      [from cfdi_parser.py]
    2. classify_cfdi_offline(cfdi) -> ClasificacionFiscal  [from fiscal_classifier.py]

    Args:
        download_result: Result from navigate_cfdi_recibidos/emitidos
        doctor_rfc: The doctor's RFC for classification context
        use_gemini: If True, use Gemini API (slower, more accurate).
                    Default False for batch processing efficiency.

    Returns:
        List of (CFDI, ClasificacionFiscal) tuples
    """
    results = []

    for xml_path in download_result.archivos_xml:
        try:
            # Step 1: Parse the XML
            cfdi = parse_cfdi(xml_path)

            # Step 2: Classify
            if use_gemini:
                from src.tools.fiscal_classifier import classify_cfdi
                clasificacion = classify_cfdi(cfdi, doctor_rfc=doctor_rfc)
            else:
                clasificacion = classify_cfdi_offline(cfdi, doctor_rfc=doctor_rfc)

            results.append((cfdi, clasificacion))

        except Exception as e:
            download_result.errores.append(
                f"Error procesando {xml_path}: {str(e)}"
            )

    return results


# ===================================================================
# FULL ORCHESTRATOR
# ===================================================================

async def navigate_retenciones_recibidas(
    page: Page,
    session: SATSession,
    fecha_inicio: str,
    fecha_fin: str,
    rfc_emisor: Optional[str] = None,
    download_dir: str = DEFAULT_DOWNLOAD_DIR,
) -> CFDIDownloadResult:
    """Navigate to Retenciones Recibidas portal and download XMLs.

    Two-step navigation:
      1. Land on /?oculta=1 → select Recibidas radio → Continuar
      2. Fill date filters on /ConsultaReceptor → Buscar CFDI → download

    Args:
        fecha_inicio: "YYYY-MM-DD" — start date (maps to year/month/day dropdowns)
        fecha_fin:    "YYYY-MM-DD" — end date (maps to year/month/day dropdowns)
        rfc_emisor:   Optional RFC filter for the issuer of the retention

    NOTE: Retenciones uses a different subdomain (prodretencioncontribuyente.clouda.sat.gob.mx)
    with shared SSO via cfdiau.sat.gob.mx. Open this tab while CFDI session is active
    to inherit the SSO cookie without re-authentication.

    Raises:
        SATSessionExpired: If session is not authenticated.
    """
    result = CFDIDownloadResult(
        tipo="retenciones_recibidas",
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    dl_dir = _ensure_dir(f"{download_dir}/{session.rfc}/retenciones/recibidas")

    # --- Step 1: Navigate to Retenciones home page ---
    await page.goto(SAT_RETENCIONES_URL, wait_until="domcontentloaded")
    await _take_nav_screenshot(page, session, "reten_home", "Retenciones — página inicial")

    # Detect SSO redirect (auth required) — wait up to 60s for user to log in
    if SAT_RETENCIONES_AUTH_HOST in page.url:
        logger.info("Retenciones SSO redirect detected — waiting for user login (CAPTCHA)")
        try:
            await page.wait_for_url(
                f"**{SAT_RETENCIONES_BASE}**",
                timeout=60_000,
            )
        except Exception:
            result.errores.append("Retenciones auth timeout — user did not complete login")
            return result
        await _take_nav_screenshot(page, session, "reten_auth_ok", "Retenciones — autenticado")

    # Verify auth indicator exists
    rfc_el = await page.query_selector(S.RETENCIONES_RFC_DISPLAY)
    if not rfc_el:
        result.errores.append("Retenciones auth indicator not found — not authenticated")
        return result

    # --- Step 2: Select Recibidas radio and click Continuar ---
    try:
        await page.click(S.RETENCIONES_RADIO_RECIBIDAS)
        await _safe_click(
            page, S.RETENCIONES_BTN_CONTINUAR, session,
            "Retenciones — Continuar a ConsultaReceptor",
        )
        await page.wait_for_url(f"**{SAT_RETENCIONES_RECIBIDAS_URL}**", timeout=SAT_PAGE_TIMEOUT_MS)
        await page.wait_for_load_state("domcontentloaded")
        await _take_nav_screenshot(page, session, "reten_rec_form", "Retenciones ConsultaReceptor — formulario")
    except SATReadOnlyViolation:
        raise
    except Exception as e:
        result.errores.append(f"Error navegando a ConsultaReceptor: {str(e)}")
        return result

    # --- Step 3: Fill date filters ---
    # Retenciones ConsultaReceptor uses year/month/day dropdowns (unlike CFDI ConsultaEmisor)
    try:
        await page.click(S.RETEN_REC_RADIO_FECHA)

        fi = fecha_inicio.split("-")  # YYYY-MM-DD → ["YYYY", "MM", "DD"]
        ff = fecha_fin.split("-")

        await page.select_option(S.RETEN_REC_SELECT_ANIO, fi[0])
        await page.select_option(S.RETEN_REC_SELECT_MES, fi[1])
        await page.select_option(S.RETEN_REC_SELECT_DIA, fi[2])

        if rfc_emisor:
            await page.fill(S.RETEN_REC_INPUT_RFC_EMISOR, rfc_emisor.upper())

        await _take_nav_screenshot(
            page, session, "reten_rec_filters",
            f"Retenciones Recibidas — filtros: {fecha_inicio}",
        )
    except Exception as e:
        result.errores.append(f"Error llenando filtros Retenciones: {str(e)}")
        return result

    # --- Step 4: Click Buscar CFDI ---
    try:
        await _safe_click(page, S.RETEN_REC_BTN_BUSCAR, session, "Retenciones — Buscar CFDI")
        await page.wait_for_load_state("networkidle", timeout=SAT_PAGE_TIMEOUT_MS)
        await _take_nav_screenshot(page, session, "reten_rec_results", "Retenciones Recibidas — resultados")
    except SATReadOnlyViolation:
        raise
    except Exception as e:
        result.errores.append(f"Error en búsqueda Retenciones: {str(e)}")
        return result

    # --- Step 5: Check for results ---
    no_res = await page.query_selector(S.RETEN_REC_PANEL_NO_RESULTADOS)
    if no_res and await no_res.is_visible():
        result.total_encontrados = 0
        return result

    rows = await page.query_selector_all(f"{S.RETEN_REC_TABLE} tbody tr")
    result.total_encontrados = len(rows)

    await _take_nav_screenshot(
        page, session, "reten_rec_count",
        f"Retenciones recibidas encontradas: {result.total_encontrados}",
    )

    # --- Step 6: Download XMLs ---
    # Per-row icon IDs are pending verification (RFC de prueba sin retenciones).
    # Attempt download via per-row icon first; fall back to bulk #descargarSel.
    try:
        for i, row in enumerate(rows):
            row_text = await row.inner_text()
            uuid = _extract_uuid_from_text(row_text)

            # Try per-row XML icon (same SPAN IDs as CFDI portal — to confirm when data available)
            xml_icon = await row.query_selector(S.RETEN_REC_ICON_XML) if S.RETEN_REC_ICON_XML != "???" else None
            if xml_icon:
                file_path = await _download_cfdi_xml(
                    page, session,
                    f"{S.RETEN_REC_TABLE} tbody tr:nth-child({i + 1}) {S.RETEN_REC_ICON_XML}",
                    str(dl_dir),
                    cfdi_uuid=uuid or f"retencion_recibida_{i + 1}",
                )
                if file_path:
                    result.archivos_xml.append(file_path)
                    result.total_descargados += 1

    except SATReadOnlyViolation:
        raise
    except Exception as e:
        result.errores.append(f"Error descargando XMLs Retenciones: {str(e)}")

    return result


async def navigate_retenciones_emitidas(
    page: Page,
    session: SATSession,
    fecha_inicio: str,
    fecha_fin: str,
    rfc_receptor: Optional[str] = None,
    download_dir: str = DEFAULT_DOWNLOAD_DIR,
) -> CFDIDownloadResult:
    """Navigate to Retenciones Emitidas portal and download XMLs.

    Two-step navigation:
      1. Land on /?oculta=1 → select Emitidas radio → Continuar
      2. Fill date filters on /ConsultaEmisor → Buscar CFDI → download

    Args:
        fecha_inicio: "YYYY-MM-DD" — start date (DD/MM/YYYY text input)
        fecha_fin:    "YYYY-MM-DD" — end date (DD/MM/YYYY text input)
        rfc_receptor: Optional RFC filter for the recipient of the retention

    NOTE: ConsultaEmisor uses TEXT INPUT for dates (not dropdowns like ConsultaReceptor).
    Format: DD/MM/YYYY.

    Raises:
        SATSessionExpired: If session is not authenticated.
    """
    result = CFDIDownloadResult(
        tipo="retenciones_emitidas",
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    dl_dir = _ensure_dir(f"{download_dir}/{session.rfc}/retenciones/emitidas")

    # --- Step 1: Navigate to Retenciones home page ---
    await page.goto(SAT_RETENCIONES_URL, wait_until="domcontentloaded")
    await _take_nav_screenshot(page, session, "reten_emi_home", "Retenciones — página inicial")

    # Detect SSO redirect
    if SAT_RETENCIONES_AUTH_HOST in page.url:
        logger.info("Retenciones SSO redirect detected — waiting for user login")
        try:
            await page.wait_for_url(f"**{SAT_RETENCIONES_BASE}**", timeout=60_000)
        except Exception:
            result.errores.append("Retenciones auth timeout — user did not complete login")
            return result
        await _take_nav_screenshot(page, session, "reten_emi_auth_ok", "Retenciones — autenticado")

    rfc_el = await page.query_selector(S.RETENCIONES_RFC_DISPLAY)
    if not rfc_el:
        result.errores.append("Retenciones auth indicator not found — not authenticated")
        return result

    # --- Step 2: Select Emitidas radio and click Continuar ---
    try:
        await page.click(S.RETENCIONES_RADIO_EMITIDAS)
        await _safe_click(
            page, S.RETENCIONES_BTN_CONTINUAR, session,
            "Retenciones — Continuar a ConsultaEmisor",
        )
        await page.wait_for_url(f"**{SAT_RETENCIONES_EMITIDAS_URL}**", timeout=SAT_PAGE_TIMEOUT_MS)
        await page.wait_for_load_state("domcontentloaded")
        await _take_nav_screenshot(page, session, "reten_emi_form", "Retenciones ConsultaEmisor — formulario")
    except SATReadOnlyViolation:
        raise
    except Exception as e:
        result.errores.append(f"Error navegando a ConsultaEmisor: {str(e)}")
        return result

    # --- Step 3: Fill date filters ---
    # ConsultaEmisor uses TEXT INPUT for dates (format: DD/MM/YYYY)
    try:
        await page.click(S.RETEN_EMI_RADIO_FECHA)

        # Convert YYYY-MM-DD → DD/MM/YYYY for text input
        def _iso_to_ddmmyyyy(iso: str) -> str:
            parts = iso.split("-")
            return f"{parts[2]}/{parts[1]}/{parts[0]}"

        await page.fill(S.RETEN_EMI_FECHA_INI, _iso_to_ddmmyyyy(fecha_inicio))
        await page.fill(S.RETEN_EMI_FECHA_FIN, _iso_to_ddmmyyyy(fecha_fin))

        if rfc_receptor:
            await page.fill(S.RETEN_EMI_INPUT_RFC_RECEPTOR, rfc_receptor.upper())

        await _take_nav_screenshot(
            page, session, "reten_emi_filters",
            f"Retenciones Emitidas — filtros: {fecha_inicio}",
        )
    except Exception as e:
        result.errores.append(f"Error llenando filtros Retenciones Emitidas: {str(e)}")
        return result

    # --- Step 4: Click Buscar CFDI ---
    try:
        await _safe_click(page, S.RETEN_EMI_BTN_BUSCAR, session, "Retenciones Emitidas — Buscar CFDI")
        await page.wait_for_load_state("networkidle", timeout=SAT_PAGE_TIMEOUT_MS)
        await _take_nav_screenshot(page, session, "reten_emi_results", "Retenciones Emitidas — resultados")
    except SATReadOnlyViolation:
        raise
    except Exception as e:
        result.errores.append(f"Error en búsqueda Retenciones Emitidas: {str(e)}")
        return result

    # --- Step 5: Check for results ---
    no_res = await page.query_selector(S.RETEN_EMI_PANEL_NO_RESULTADOS)
    if no_res and await no_res.is_visible():
        result.total_encontrados = 0
        return result

    rows = await page.query_selector_all(f"{S.RETEN_EMI_TABLE} tbody tr")
    result.total_encontrados = len(rows)

    await _take_nav_screenshot(
        page, session, "reten_emi_count",
        f"Retenciones emitidas encontradas: {result.total_encontrados}",
    )

    # --- Step 6: Download XMLs ---
    try:
        for i, row in enumerate(rows):
            row_text = await row.inner_text()
            uuid = _extract_uuid_from_text(row_text)

            xml_icon = await row.query_selector(S.RETEN_EMI_ICON_XML) if S.RETEN_EMI_ICON_XML != "???" else None
            if xml_icon:
                file_path = await _download_cfdi_xml(
                    page, session,
                    f"{S.RETEN_EMI_TABLE} tbody tr:nth-child({i + 1}) {S.RETEN_EMI_ICON_XML}",
                    str(dl_dir),
                    cfdi_uuid=uuid or f"retencion_emitida_{i + 1}",
                )
                if file_path:
                    result.archivos_xml.append(file_path)
                    result.total_descargados += 1

    except SATReadOnlyViolation:
        raise
    except Exception as e:
        result.errores.append(f"Error descargando XMLs Retenciones Emitidas: {str(e)}")

    return result


async def full_sat_navigation(
    rfc: str,
    fecha_inicio: str,
    fecha_fin: str,
    headless: bool = True,
    include_constancia: bool = True,
    include_buzon: bool = True,
    download_dir: str = DEFAULT_DOWNLOAD_DIR,
) -> SATPortalResult:
    """Complete SAT portal navigation session.

    Main entry point orchestrating the full flow:
    1. Create browser
    2. Navigate to SAT portal
    3. Wait for user login
    4. Download CFDI Recibidos
    5. Download CFDI Emitidos
    6. Capture Constancia de Situación Fiscal (optional)
    7. Check Buzón Tributario (optional)
    8. Close browser
    9. Return complete results

    The user must complete login manually. This tool only
    observes and downloads — never modifies anything.
    """
    pw, browser, context, page = await create_sat_browser(
        headless=headless,
        download_dir=download_dir,
    )

    try:
        # Wait for user login
        session = await wait_for_user_login(page)

        portal_result = SATPortalResult(session=session)

        # Download CFDI Recibidos
        try:
            portal_result.cfdis_recibidos = await navigate_cfdi_recibidos(
                page, session, fecha_inicio, fecha_fin,
                download_dir=download_dir,
            )
        except SATSessionExpired:
            portal_result.session.authenticated = False
            return portal_result

        # Download CFDI Emitidos
        try:
            portal_result.cfdis_emitidos = await navigate_cfdi_emitidos(
                page, session, fecha_inicio, fecha_fin,
                download_dir=download_dir,
            )
        except SATSessionExpired:
            portal_result.session.authenticated = False
            return portal_result

        # Constancia de Situación Fiscal
        if include_constancia:
            try:
                portal_result.constancia = await navigate_constancia(
                    page, session,
                )
            except (SATSessionExpired, Exception):
                pass  # Non-critical, continue

        # Buzón Tributario
        if include_buzon:
            try:
                portal_result.buzon = await navigate_buzon_tributario(
                    page, session,
                )
            except (SATSessionExpired, Exception):
                pass  # Non-critical, continue

        return portal_result

    finally:
        await browser.close()
        await pw.stop()
