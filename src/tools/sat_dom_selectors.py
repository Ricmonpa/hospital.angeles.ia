"""OpenDoc - SAT Portal DOM Selectors.

Real CSS selectors extracted from the live SAT portal DOM via DevTools inspection.
These selectors are used by sat_portal_navigator.py for Playwright automation.

Last verified: 2026-03-03
Portal version: 4.5.0
RFC tested: MOPR881228EF9 (Persona Física, Régimen 612)

MAPPING STATUS:
  [✅] Página principal (/Consulta.aspx)
  [✅] Facturas Recibidas (/ConsultaReceptor.aspx)     — íconos por fila VERIFICADOS 2026-03-05
  [✅] Facturas Emitidas (/ConsultaEmisor.aspx)        — íconos por fila VERIFICADOS 2026-03-05
  [🔲] Descarga de XMLs
  [✅] Recuperar Descargas (/ConsultaDescargaMasiva.aspx)  — botones por fila PENDIENTES (sin descargas activas)
  [✅] Solicitudes de Cancelación (/ConsultaCancelacion.aspx)
  [✅] Retenciones — página inicial (/?oculta=1)
  [✅] Retenciones — ConsultaReceptor (/ConsultaReceptor)   — VERIFICADO 2026-03-05 (íconos por fila pendientes)
  [✅] Retenciones — ConsultaEmisor (/ConsultaEmisor)       — VERIFICADO 2026-03-05 (íconos por fila pendientes)
  [✅] Retenciones — ConsultaDescargaMasiva (/ConsultaDescargaMasiva) — VERIFICADO 2026-03-05 (sin descargas activas)

HOW TO VERIFY:
  Open DevTools (F12) → Console → paste the JS snippet for each page.
  Copy the JSON output and update the selectors below.
"""

# ---------------------------------------------------------------------------
# JS SNIPPETS — Paste these in browser DevTools console to extract selectors
# ---------------------------------------------------------------------------

# SNIPPET_ALL_IDS = """
# JSON.stringify(
#   [...document.querySelectorAll('[id]')].map(e => ({
#     tag: e.tagName,
#     id: e.id,
#     name: e.name || '',
#     type: e.type || '',
#     value: e.value || '',
#     text: e.innerText?.trim().substring(0, 60) || '',
#     cls: e.className?.toString().substring(0, 60) || ''
#   })),
#   null, 2
# )
# """

# SNIPPET_FORMS = """
# JSON.stringify(
#   [...document.querySelectorAll('input, select, textarea, button, a[href]')].map(e => ({
#     tag: e.tagName,
#     id: e.id || '',
#     name: e.name || '',
#     type: e.type || '',
#     value: e.value || e.getAttribute('value') || '',
#     text: e.innerText?.trim().substring(0, 60) || '',
#     href: e.href || '',
#     cls: e.className?.toString().substring(0, 60) || ''
#   })),
#   null, 2
# )
# """


# ===========================================================================
# PAGE: Página Principal (/Consulta.aspx)
# ===========================================================================
# STATUS: ✅ VERIFIED 2026-03-03 — RFC MOPR881228EF9
# NOTES: Los 4 links de navegación NO tienen ID propio — usar href como selector.
#        ASP.NET master page usa prefijo "ctl00_" para controles del master.

# Navigation links to sub-pages (sin ID — usar href)
HOME_LINK_EMITIDAS = "a[href='ConsultaEmisor.aspx']"       # "Consultar Facturas Emitidas"
HOME_LINK_RECIBIDAS = "a[href='ConsultaReceptor.aspx']"    # "Consultar Facturas Recibidas"
HOME_LINK_DESCARGAS = "a[href='ConsultaDescargaMasiva.aspx']"  # "Recuperar Descargas de CFDI"
HOME_LINK_CANCELACION = "a[href='ConsultaCancelacion.aspx']"   # "Consultar Solicitudes de Cancelación"

# Auth indicators
HOME_RFC_DISPLAY = "#ctl00_LblRfcAutenticado"   # SPAN.signin — "RFC Autenticado: MOPR881228EF9"
HOME_LOGOUT_LINK = "#anchorClose"               # A type=button — "Salir" → /logout.aspx?salir=y

# Nav bar
HOME_NAV_CONSULTA_CFDI = "a.dropdown-toggle[href='#']"  # "Consulta CFDI ▼" (primer dropdown)
HOME_NAV_GENERACION_CFDI = "#menuDesplegable"           # "Generación de CFDI ▼"
HOME_NAV_RETENCIONES = "a[href='https://prodretencioncontribuyente.clouda.sat.gob.mx/?oculta=1']"

# Content containers (útiles para wait_for_selector)
HOME_MAIN_PANEL = "#ctl00_MainContent_PnlConsulta"      # Panel con los 4 links
HOME_UPDATE_PANEL = "#ctl00_MainContent_UpnlBusqueda"   # UpdatePanel AJAX wrapper
HOME_BODY = "#cuerpo_principal"                          # Contenedor principal
HOME_LOADING = "#ctl00_MainContent_UpdateProgress1"      # "Espere un momento..." (AJAX spinner)

# Hidden auth field (verificar autenticación sin UI)
HOME_HDN_AUT = "#hdnAut"   # hidden input — value es base64 del RFC autenticado

# ASP.NET form (presente en todas las páginas del portal)
ASPNET_FORM = "#aspnetForm"
ASPNET_CSRF = "#__CSRFTOKEN"
ASPNET_VIEWSTATE = "#__VIEWSTATE"


# ===========================================================================
# PAGE: Facturas Recibidas (/ConsultaReceptor.aspx)
# ===========================================================================
# STATUS: ✅ VERIFIED 2026-03-03 — RFC MOPR881228EF9
# NOTES:
#   - Los dropdowns de fecha usan el componente "CldFecha" (UserControl reutilizable)
#   - ATENCIÓN: DdlAnio NO tiene prefijo ctl00_ (los demás sí) — bug/quirk del portal
#   - TxtRfcReceptor en realidad filtra por RFC EMISOR (el label lo confirma)
#   - Los campos de fecha inician con clase "aspNetDisabled" hasta seleccionar RdoFechas
#   - Hay 3 botones de descarga (no solo 1): XML, Metadata, PDF

# Search mode — radio buttons (mismo name, distinto value)
RECIBIDOS_RADIO_FOLIO = "#ctl00_MainContent_RdoFolioFiscal"  # value="RdoFolioFiscal" (default)
RECIBIDOS_RADIO_FECHA = "#ctl00_MainContent_RdoFechas"        # value="RdoFechas"

# Mode: Folio Fiscal
RECIBIDOS_INPUT_UUID = "#ctl00_MainContent_TxtUUID"           # type=text, class=form-control

# Mode: Fecha de Emisión — fecha INICIO
# ⚠️ DdlAnio no tiene prefijo ctl00_ (inconsistencia del portal)
RECIBIDOS_SELECT_ANIO = "#DdlAnio"                                    # Año (2011-2026+), default=2026
RECIBIDOS_SELECT_MES = "#ctl00_MainContent_CldFecha_DdlMes"           # Mes (01-12), default=01
RECIBIDOS_SELECT_DIA = "#ctl00_MainContent_CldFecha_DdlDia"           # Día (01-31), default=01
RECIBIDOS_SELECT_HORA_INI = "#ctl00_MainContent_CldFecha_DdlHora"     # Hora ini (00-23), default=00
RECIBIDOS_SELECT_MIN_INI = "#ctl00_MainContent_CldFecha_DdlMinuto"    # Minuto ini (00-59), default=00
RECIBIDOS_SELECT_SEG_INI = "#ctl00_MainContent_CldFecha_DdlSegundo"   # Segundo ini (00-59), default=00

# Fecha FIN
RECIBIDOS_SELECT_HORA_FIN = "#ctl00_MainContent_CldFecha_DdlHoraFin"    # Hora fin (00-23), default=23
RECIBIDOS_SELECT_MIN_FIN = "#ctl00_MainContent_CldFecha_DdlMinutoFin"   # Minuto fin (00-59), default=59
RECIBIDOS_SELECT_SEG_FIN = "#ctl00_MainContent_CldFecha_DdlSegundoFin"  # Segundo fin (00-59), default=59

# Date container (útil para wait_for_selector cuando se activa modo fecha)
RECIBIDOS_DATE_CONTAINER = "#ctl00_MainContent_CldFecha_UpnlSeleccionFecha"

# Optional filter fields
RECIBIDOS_INPUT_RFC_EMISOR = "#ctl00_MainContent_TxtRfcReceptor"      # ⚠️ ID dice Receptor, filtra EMISOR
RECIBIDOS_INPUT_RFC_TERCEROS = "#ctl00_MainContent_TxtRfcTercero"     # RFC a cuenta de terceros
RECIBIDOS_SELECT_ESTADO = "#ctl00_MainContent_DdlEstadoComprobante"   # values: -1(todos), Cancelado, Vigente
RECIBIDOS_SELECT_COMPLEMENTO = "#ddlComplementos"                      # Tipo Comprobante (Complemento)
RECIBIDOS_SELECT_ESTATUS_CANCEL = "#ddlVigente"    # Estatus cancelación: En Proceso, Rechazada, etc.
RECIBIDOS_SELECT_TIPO_CANCEL = "#ddlCancelado"     # Con aceptación / Sin aceptación / etc.

# Submit
RECIBIDOS_BTN_BUSCAR = "#ctl00_MainContent_BtnBusqueda"   # type=submit, value="Buscar CFDI"

# Error / validation containers
RECIBIDOS_VALIDATION = "#ctl00_MainContent_ValidationSummary1"  # class=errores
RECIBIDOS_PANEL_ERRORES = "#ctl00_MainContent_PnlErrores"       # class=erroruuid

# Results
RECIBIDOS_UPDATE_PANEL = "#ctl00_MainContent_UpnlResultados"    # UpdatePanel AJAX wrapper
RECIBIDOS_PANEL_RESULTADOS = "#ctl00_MainContent_PnlResultados" # Panel visible con resultados
RECIBIDOS_TABLE = "#ctl00_MainContent_tblResult"                # TABLE class=table table-responsive
RECIBIDOS_CHECKBOX_TODOS = "#seleccionador"                     # Checkbox "seleccionar todos"
RECIBIDOS_PAGINATION = "#ctl00_MainContent_pageNavPosition"     # Paginación (class=form-group)
RECIBIDOS_PANEL_NO_RESULTADOS = "#ctl00_MainContent_PnlNoResultados"  # "No existen registros..."

# Per-row action icons — ✅ VERIFIED 2026-03-05
# Son SPAN (no <a> ni <img>) con onclick directo. Mismo ID en todas las filas.
# Para fila N usar: f"{RECIBIDOS_TABLE} tbody tr:nth-child(N) #BtnDescarga"
# Handlers JS:
#   Detalle → AccionCfdi('Detalle.aspx?Datos=...')
#   XML     → AccionCfdi('RecuperaCfdi.aspx?Datos=...')
#   PDF     → recuperaRepresentacionImpresa('...')
RECIBIDOS_ICON_DETALLE = "#BtnVerDetalle"   # SPAN.glyphicon-zoom-in.Interactivo — "Ver detalle"
RECIBIDOS_ICON_XML     = "#BtnDescarga"     # SPAN.glyphicon-cloud-download.Interactivo — "Descargar" XML
RECIBIDOS_ICON_PDF     = "#BtnRI"           # SPAN.glyphicon-file.Interactivo — "Recuperar Representación Impresa"
RECIBIDOS_ICON_CLASS   = "span.Interactivo" # Selector genérico para cualquier ícono interactivo por fila

# Bulk action buttons (visibles aunque no haya resultados)
RECIBIDOS_BTN_DESCARGAR = "#ctl00_MainContent_BtnDescargar"   # "Descargar Seleccionados"
RECIBIDOS_BTN_METADATA = "#ctl00_MainContent_BtnMetadata"     # "Descargar Metadata" (no estaba en spec)
RECIBIDOS_BTN_PDF = "#ctl00_MainContent_BtnImprimir"          # "Exportar Resultados a PDF"

# Loading spinner
RECIBIDOS_LOADING = "#ctl00_MainContent_UpdateProgress1"      # "Espere un momento..."

# Modal: RFC a cuenta de terceros
RECIBIDOS_MODAL_TERCEROS = "#modalCuentaTerceros"
RECIBIDOS_MODAL_TERCEROS_CERRAR = "#btnAlertDCCerrar"         # Botón "Cerrar"
RECIBIDOS_MODAL_TERCEROS_UUID = "#uuidConsultado"
RECIBIDOS_MODAL_TERCEROS_TBODY = "#datosTerceros"

# Hidden fields (estado interno)
RECIBIDOS_HF_INICIAL = "#hfInicialBool"          # "true" al cargar
RECIBIDOS_HF_DESCARGA = "#hfDescarga"
RECIBIDOS_HF_METADATA = "#hfParametrosMetadata"
RECIBIDOS_HDN_ACCION = "#hdnValAccion"


# ===========================================================================
# PAGE: Facturas Emitidas (/ConsultaEmisor.aspx)
# ===========================================================================
# STATUS: ✅ VERIFIED 2026-03-03 — RFC MOPR881228EF9
# NOTES:
#   - Fechas usan TEXT INPUT + ícono calendario (NO dropdowns año/mes/día como en Recibidas)
#   - Componente UserControl: CldFechaInicial2 (inicio) y CldFechaFinal2 (fin)
#   - RFC filter es "RFC Receptor" (en Recibidas era "RFC Emisor") — mismo ID TxtRfcReceptor
#   - ALERTA: Tiene BtnCancelar y modalCancelacion — SON PELIGROSOS, READ-ONLY no los toca
#   - Tiene modal "Addenda" para subir XMLs — también ignorar
#   - Hidden fields adicionales: hfCancelacion, hfJSONCancelacion, hfUrlDescarga

# Search mode — mismos IDs que Recibidas (mismo patrón ASP.NET)
EMITIDOS_RADIO_FOLIO = "#ctl00_MainContent_RdoFolioFiscal"   # value="RdoFolioFiscal"
EMITIDOS_RADIO_FECHA = "#ctl00_MainContent_RdoFechas"         # value="RdoFechas"

# Mode: Folio Fiscal
EMITIDOS_INPUT_UUID = "#ctl00_MainContent_TxtUUID"            # type=text, class=form-control

# Mode: Fecha — DIFERENTE A RECIBIDAS: text input + ícono calendario
# Fecha INICIAL
EMITIDOS_CAL_FECHA_INI_INPUT = "#ctl00_MainContent_CldFechaInicial2_Calendario_text"  # text input (dd/mm/yyyy)
EMITIDOS_CAL_FECHA_INI_ICON = "#ctl00_MainContent_CldFechaInicial2_BtnFecha2"         # IMG.icon-calendar
EMITIDOS_CAL_FECHA_INI_CONTAINER = "#ctl00_MainContent_CldFechaInicial2_UpnlSeleccionFecha"
EMITIDOS_SELECT_HORA_INI = "#ctl00_MainContent_CldFechaInicial2_DdlHora"     # Hora ini (00-23)
EMITIDOS_SELECT_MIN_INI = "#ctl00_MainContent_CldFechaInicial2_DdlMinuto"    # Minuto ini (00-59)
EMITIDOS_SELECT_SEG_INI = "#ctl00_MainContent_CldFechaInicial2_DdlSegundo"   # Segundo ini (00-59)

# Fecha FINAL
EMITIDOS_CAL_FECHA_FIN_INPUT = "#ctl00_MainContent_CldFechaFinal2_Calendario_text"    # text input
EMITIDOS_CAL_FECHA_FIN_ICON = "#ctl00_MainContent_CldFechaFinal2_BtnFecha2"           # IMG.icon-calendar
EMITIDOS_CAL_FECHA_FIN_CONTAINER = "#ctl00_MainContent_CldFechaFinal2_UpnlSeleccionFecha"
EMITIDOS_SELECT_HORA_FIN = "#ctl00_MainContent_CldFechaFinal2_DdlHora"       # Hora fin (00-23)
EMITIDOS_SELECT_MIN_FIN = "#ctl00_MainContent_CldFechaFinal2_DdlMinuto"      # Minuto fin (00-59)
EMITIDOS_SELECT_SEG_FIN = "#ctl00_MainContent_CldFechaFinal2_DdlSegundo"     # Segundo fin (00-59)

# Hidden fields de fecha
EMITIDOS_HF_FECHA_INI = "#hfInicial"    # Se llena al seleccionar fecha en calendario
EMITIDOS_HF_FECHA_FIN = "#hfFinal"      # Se llena al seleccionar fecha en calendario

# Optional filter fields (mismos IDs que Recibidas)
EMITIDOS_INPUT_RFC_RECEPTOR = "#ctl00_MainContent_TxtRfcReceptor"     # RFC Receptor (filtro)
EMITIDOS_INPUT_RFC_TERCEROS = "#ctl00_MainContent_TxtRfcTercero"      # RFC a cuenta terceros
EMITIDOS_SELECT_ESTADO = "#ctl00_MainContent_DdlEstadoComprobante"    # values: -1, Cancelado, Vigente
EMITIDOS_SELECT_COMPLEMENTO = "#ddlComplementos"                       # Tipo Comprobante
EMITIDOS_SELECT_ESTATUS_CANCEL = "#ddlVigente"
EMITIDOS_SELECT_TIPO_CANCEL = "#ddlCancelado"

# Submit
EMITIDOS_BTN_BUSCAR = "#ctl00_MainContent_BtnBusqueda"   # type=submit, value="Buscar CFDI"

# Error / validation
EMITIDOS_VALIDATION = "#ctl00_MainContent_ValidationSummary1"
EMITIDOS_PANEL_ERRORES = "#ctl00_MainContent_PnlErrores"

# Results (misma estructura que Recibidas)
EMITIDOS_UPDATE_PANEL = "#ctl00_MainContent_UpnlResultados"
EMITIDOS_PANEL_RESULTADOS = "#ctl00_MainContent_PnlResultados"
EMITIDOS_TABLE = "#ctl00_MainContent_tblResult"
EMITIDOS_CHECKBOX_TODOS = "#seleccionador"
EMITIDOS_PAGINATION = "#ctl00_MainContent_pageNavPosition"
EMITIDOS_PANEL_NO_RESULTADOS = "#ctl00_MainContent_PnlNoResultados"

# Per-row icons — mismos IDs que Recibidas (mismo patrón ASP.NET) ✅ VERIFIED 2026-03-05
EMITIDOS_ICON_DETALLE = "#BtnVerDetalle"   # SPAN.glyphicon-zoom-in.Interactivo
EMITIDOS_ICON_XML     = "#BtnDescarga"     # SPAN.glyphicon-cloud-download.Interactivo
EMITIDOS_ICON_PDF     = "#BtnRI"           # SPAN.glyphicon-file.Interactivo
EMITIDOS_ICON_CLASS   = "span.Interactivo" # Selector genérico por fila

# Bulk action buttons
EMITIDOS_BTN_DESCARGAR = "#ctl00_MainContent_BtnDescargar"   # "Descargar Seleccionados"
EMITIDOS_BTN_METADATA = "#ctl00_MainContent_BtnMetadata"     # "Descargar Metadata"
EMITIDOS_BTN_PDF = "#ctl00_MainContent_BtnImprimir"          # "Exportar Resultados a PDF"

# ⛔ FORBIDDEN — NUNCA CLICKEAR (solo en Emitidas, no en Recibidas)
EMITIDOS_BTN_CANCELAR = "#ctl00_MainContent_BtnCancelar"             # "Cancelar Seleccionados" — PELIGROSO
EMITIDOS_BTN_CANCELAR_MODAL = "#ctl00_MainContent_btnCancelarModal"  # submit en modal cancelación — PELIGROSO
EMITIDOS_MODAL_CANCELACION = "#modalCancelacion"                      # Modal de motivos de cancelación

# Modal Addenda (ignorar en modo read-only)
EMITIDOS_MODAL_ADDENDA = "#modalExito"
EMITIDOS_ADDENDA_FILE = "#addenda"        # file input
EMITIDOS_ADDENDA_TEXT = "#textAddenda"    # text input
EMITIDOS_BTN_INTEGRAR = "#integrar"       # submit "Integrar" — NO TOCAR

# Download link (aparece tras procesar)
EMITIDOS_LINK_DESCARGA = "#descarga-archivo"   # A.btn.btn-primary — "Guardar"

# Loading
EMITIDOS_LOADING = "#ctl00_MainContent_UpdateProgress1"


# ===========================================================================
# PAGE: Recuperar Descargas (/ConsultaDescargaMasiva.aspx)
# ===========================================================================
# STATUS: ✅ VERIFIED 2026-03-03 — RFC MOPR881228EF9
# NOTES:
#   - NO tiene formulario de búsqueda — muestra automáticamente descargas de los últimos 3 días
#   - Al momento del mapping no había descargas pendientes (mensaje vacío)
#   - La descarga se dispara vía PostBack: setLinkButtonDescarga
#   - La tabla de resultados (DivContenedor/ContenedorDinamico) aparece solo cuando hay descargas
#   - Íconos/botones por fila PENDIENTES — requieren descargas activas para mapear

# Containers principales
DESCARGAS_PANEL_CONSULTA = "#ctl00_MainContent_PnlConsulta"         # Panel principal
DESCARGAS_UPDATE_PANEL = "#ctl00_MainContent_UpnlResultados"         # UpdatePanel AJAX
DESCARGAS_PANEL_RESULTADOS = "#ctl00_MainContent_PnlResultados"      # Panel resultados (class=col-md-12)
DESCARGAS_PANEL_LIMITE = "#ctl00_MainContent_PnlLimiteRegistros"     # Info sobre límite de registros
DESCARGAS_CONTENEDOR = "#DivContenedor"                               # class=resultados col-md-12
DESCARGAS_CONTENEDOR_DINAMICO = "#ContenedorDinamico"                # class=col-md-12 (filas dinámicas)
DESCARGAS_PANEL_NO_RESULTADOS = "#ctl00_MainContent_PnlNoResultados" # "No existen registros de descargas..."

# Trigger de descarga (PostBack — no es un <button> normal)
DESCARGAS_LINK_DESCARGA = "#setLinkButtonDescarga"   # A.btn.btn-link → javascript:__doPostBack(...)

# Hidden fields de estado
DESCARGAS_HF_FOLIO = "#hfFolioDescargaActual"       # Folio de la descarga en curso
DESCARGAS_HF_URL = "#hfUrlDescargaActual"            # URL de descarga

# Loading
DESCARGAS_LOADING = "#ctl00_MainContent_UpdateProgress1"

# Por fila (PENDIENTE — requiere descargas activas)
DESCARGAS_TABLE = "???"              # TABLE con filas de descargas (TBD)
DESCARGAS_ROW_BTN = "???"            # Botón de descarga por fila (TBD)
DESCARGAS_ROW_STATUS = "???"         # Columna estatus por fila (TBD)


# ===========================================================================
# PAGE: Solicitudes de Cancelación (/ConsultaCancelacion.aspx)
# ===========================================================================
# STATUS: ✅ VERIFIED 2026-03-03 — RFC MOPR881228EF9
# NOTES:
#   - NO tiene formulario de búsqueda — auto-carga solicitudes pendientes del RFC
#   - ⛔⛔⛔ EXTREMADAMENTE PELIGROSO: tiene botones Aceptar/Rechazar cancelaciones
#   - Los modales de confirmación disparan PostBack que EJECUTA la cancelación/rechazo
#   - El checkbox de selección tiene ID diferente: "seleccionSoliCancela" (no "seleccionador")
#   - Paginación ID diferente: page_NavPosition (con guión bajo, no camelCase)
#   - Sin descargas activas al momento del mapping — tabla aparece vacía

# Containers (mismo patrón que otras páginas)
CANCELACION_PANEL_CONSULTA = "#ctl00_MainContent_PnlConsulta"
CANCELACION_UPDATE_PANEL = "#ctl00_MainContent_UpnlResultados"
CANCELACION_PANEL_RESULTADOS = "#ctl00_MainContent_PnlResultados"
CANCELACION_CONTENEDOR = "#DivContenedor"
CANCELACION_CONTENEDOR_DINAMICO = "#ContenedorDinamico"
CANCELACION_PANEL_NO_RESULTADOS = "#ctl00_MainContent_PnlNoResultados"

# Results table
CANCELACION_TABLE = "#ctl00_MainContent_tblResult"          # TABLE class=table table-responsive
CANCELACION_CHECKBOX_TODOS = "#seleccionSoliCancela"        # ⚠️ ID diferente a otras páginas
CANCELACION_PAGINATION = "#ctl00_MainContent_page_NavPosition"  # ⚠️ guión bajo, no camelCase

# Navigation
CANCELACION_BTN_REGRESAR = "#ctl00_MainContent_HlinkIrInicio"   # A.regreso.btn.btn-default — "Regresar Inicio"

# ⛔⛔⛔ FORBIDDEN — NUNCA CLICKEAR — ejecutan acciones irreversibles sobre cancelaciones reales
CANCELACION_BTN_RECHAZAR = "#BtnDeclinaCancelacion"              # INPUT type=button "Rechazar Seleccionados"
CANCELACION_BTN_ACEPTAR = "#BtnAceptaCancelacion"                # INPUT type=button "Aceptar Seleccionados"
CANCELACION_MODAL_RECHAZAR = "#ModalConfirmarRechazoCancelcion"  # Modal confirmación rechazo
CANCELACION_MODAL_ACEPTAR = "#ModalConfirmarAceptarCancelacion"  # Modal confirmación aceptación
CANCELACION_CONFIRMAR_RECHAZO = "#ctl00_MainContent_RechazaCancelacion"   # A PostBack — EJECUTA rechazo
CANCELACION_CONFIRMAR_ACEPTAR = "#ctl00_MainContent_AceptaCancelacion"    # A PostBack — EJECUTA aceptación


# ===========================================================================
# PAGE: Retenciones (prodretencioncontribuyente.clouda.sat.gob.mx/?oculta=1)
# ===========================================================================
# STATUS: ✅ VERIFIED 2026-03-03 — RFC MOPR881228EF9
# NOTES:
#   - Subdominio diferente: clouda.sat.gob.mx — requiere auth separada (SSO cfdiau.sat.gob.mx)
#   - ⚠️ SIN prefijo ctl00_ — todos los IDs son directamente MainContent_*
#   - ⚠️ Auth indicators DISTINTOS al portal CFDI principal (IDs diferentes)
#   - form1 (no aspnetForm), sin __CSRFTOKEN
#   - Contiene modales de cancelación — FORBIDDEN
#   - Botón submit dice "Continuar" (no "Buscar")

# Auth indicators — DIFERENTES al portal principal
RETENCIONES_RFC_DISPLAY = "#LblRfcAutenticado"          # SPAN.user-credencials__name — "RFC autenticado: {RFC}"
RETENCIONES_LOGOUT_LINK = "#LnkBtnCierraSesion"         # A.pull-right — "Salir"
RETENCIONES_HDN_AUT = "#hdnAut"                         # hidden — base64(RFC) — mismo que portal CFDI
RETENCIONES_MAIN_PANEL = "#MainContent_PnlConsulta"     # Panel principal (sin ctl00_)

# Radio buttons — selección de tipo de consulta
RETENCIONES_RADIO_EMITIDAS = "#MainContent_RdoTipoBusquedaEmisor"   # value="RdoTipoBusquedaEmisor" (default)
RETENCIONES_RADIO_RECIBIDAS = "#MainContent_RdoTipoBusquedaReceptor" # value="RdoTipoBusquedaReceptor"
RETENCIONES_RADIO_DESCARGAS = "#MainContent_RdoTipoConsultaMasiva"   # value="RdoTipoConsultaMasiva"

# Submit — "Continuar" (no "Buscar")
RETENCIONES_BTN_CONTINUAR = "#MainContent_BtnBusqueda"  # INPUT type=submit, value="Continuar"

# Form
RETENCIONES_FORM = "#form1"   # ⚠️ No es aspnetForm como en portal CFDI

# Modales informativos
RETENCIONES_MODAL_PROCESO = "#ventanaProceso"           # Loading modal
RETENCIONES_MODAL_ALERTA = "#ventanaModalSat"           # Alert modal — "Retenciones"
RETENCIONES_MODAL_ALERTA_CERRAR = "#btnAlertaCerrar"    # BUTTON — "Cerrar"

# ⛔ FORBIDDEN — Modales de cancelación de Retenciones
RETENCIONES_MODAL_CANCELACION = "#ventanaDatosCancelacion"      # Modal "Registro de Motivo de cancelación"
RETENCIONES_MODAL_CONFIRM_CANCEL = "#ventanaConfirmarCancelacion"  # Modal "Confirmación de la cancelación"
RETENCIONES_BTN_CANCELAR_SELEC = "#btnAlertDCCancelar"           # ⛔ "Cancelar seleccionados"
RETENCIONES_BTN_CONTINUAR_CANCEL = "#btnCancelar"                 # ⛔ "Continuar" en modal confirmación cancelación


# ===========================================================================
# PAGE: Retenciones — ConsultaReceptor (/ConsultaReceptor)
# ===========================================================================
# STATUS: ✅ VERIFIED 2026-03-05 — RFC MOPR881228EF9
# NOTES:
#   - Página secundaria, se llega después de seleccionar RdoTipoBusquedaReceptor + Continuar
#   - SIN prefijo ctl00_ ni MainContent_ (excepto DdlEstadoComprobante)
#   - ⚠️ IDs radicalmente distintos a CFDI: rbtnFolioFiscal / rbtnFiltros (no RdoFolioFiscal / RdoFechas)
#   - ⚠️ Fecha usa dropdowns directos: selAnio / selMes / selDia (sin componente CldFecha)
#   - ⚠️ Botón Buscar SIN ID — usar button.btn-primary (onclick="ocultaResultados()")
#   - ⚠️ Tabla de resultados: #tablaRetenciones (no #tblResult como en CFDI)
#   - ⚠️ Panel sin resultados: #divNoResultadosReceptor (no PnlNoResultados)

# Search mode radios
RETEN_REC_RADIO_FOLIO = "#rbtnFolioFiscal"   # radio — "Folio fiscal*" (default activo)
RETEN_REC_RADIO_FECHA = "#rbtnFiltros"        # radio — "Fecha de emisión*"

# Mode: Folio fiscal
RETEN_REC_INPUT_UUID = "#txtFolio"            # text input — UUID del folio

# Mode: Fecha — dropdowns (año/mes/día por separado, sin componente CldFecha)
RETEN_REC_SELECT_ANIO = "#selAnio"           # SELECT Año (2014-2026)
RETEN_REC_SELECT_MES  = "#selMes"            # SELECT Mes (01-12)
RETEN_REC_SELECT_DIA  = "#selDia"            # SELECT Día (01-31)
RETEN_REC_SELECT_HORA_INI = "#selHorIni"     # SELECT Hora inicial (00-23)
RETEN_REC_SELECT_MIN_INI  = "#selMinIni"     # SELECT Minuto inicial (00-59)
RETEN_REC_SELECT_SEG_INI  = "#selSegIni"     # SELECT Segundo inicial (00-59)
RETEN_REC_SELECT_HORA_FIN = "#selHorFin"     # SELECT Hora final (00-23)
RETEN_REC_SELECT_MIN_FIN  = "#selMinFin"     # SELECT Minuto final (00-59)
RETEN_REC_SELECT_SEG_FIN  = "#selSegFin"     # SELECT Segundo final (00-59)

# Optional filters
RETEN_REC_INPUT_RFC_EMISOR = "#txtEmisor"                       # text — RFC del emisor
RETEN_REC_SELECT_ESTADO = "#MainContent_DdlEstadoComprobante"   # SELECT estado (Cancelado/Vigente)
RETEN_REC_SELECT_TIPO   = "#ddlComplementos"                    # SELECT tipo de comprobante

# Submit — ⚠️ SIN ID. Usar selector CSS o texto
RETEN_REC_BTN_BUSCAR = "button.btn-primary"   # BUTTON — "Buscar CFDI", onclick="ocultaResultados()"

# Results
RETEN_REC_TABLE             = "#tablaRetenciones"           # TABLE con resultados (≠ #tblResult del CFDI)
RETEN_REC_PANEL_NO_RESULTADOS = "#divNoResultadosReceptor"  # DIV "No existen registros..."
RETEN_REC_CHECKBOX_TODOS    = "???"                         # Checkbox "todos" — requiere resultados activos
RETEN_REC_PAGINATION        = "???"                         # Paginación — requiere resultados activos

# Bulk action buttons (visibles en página)
RETEN_REC_BTN_DESCARGAR    = "#descargarSel"        # button — "Descargar seleccionados" (XML)
RETEN_REC_BTN_METADATA     = "#descargarMetadatos"  # button — "Descargar Metadatos"
RETEN_REC_BTN_PDF          = "#exportarRes"         # button — "Exportar resultados a PDF"

# Per-row icons (requieren resultados activos — RFC MOPR881228EF9 no tiene retenciones recibidas)
# ⚠️ Probablemente son los mismos SPAN IDs que en CFDI dado que es el mismo framework
RETEN_REC_ICON_DETALLE = "???"   # probablemente #BtnVerDetalle (igual que CFDI)
RETEN_REC_ICON_XML     = "???"   # probablemente #BtnDescarga
RETEN_REC_ICON_PDF     = "???"   # probablemente #BtnRI


# ===========================================================================
# PAGE: Retenciones — ConsultaEmisor (/ConsultaEmisor)
# ===========================================================================
# STATUS: ✅ VERIFIED 2026-03-05 — RFC MOPR881228EF9
# NOTES:
#   - Llegar vía RdoTipoBusquedaEmisor + Continuar desde página inicial
#   - ⚠️ Fecha usa TEXT INPUT (no dropdowns como ConsultaReceptor): fecIniEmi / fecFinEmi
#   - ⚠️ UUID input: #txtUuid (ConsultaReceptor usaba #txtFolio)
#   - ⚠️ RFC filter: #txtReceptor (ConsultaReceptor usaba #txtEmisor)
#   - ⚠️ Estado: #selEstadoComprobante (sin prefijo, ConsultaReceptor usaba #MainContent_DdlEstadoComprobante)
#   - ⚠️ Tipo: #selComplementos (ConsultaReceptor usaba #ddlComplementos)
#   - ⚠️ No resultados: #divNoResultados (ConsultaReceptor usaba #divNoResultadosReceptor)
#   - ⛔ Tiene #cancelarSel — "Cancelar seleccionados" — FORBIDDEN
#   - Botón Buscar SIN ID — mismo patrón: button.btn-primary, onclick="ocultaResultados()"

# Search mode radios
RETEN_EMI_RADIO_FOLIO = "#rbtnFolioFiscal"   # radio — "Folio fiscal*" (default activo)
RETEN_EMI_RADIO_FECHA = "#rbtnFiltros"        # radio — "Fecha de emisión*"

# Mode: Folio fiscal
RETEN_EMI_INPUT_UUID = "#txtUuid"             # text input UUID ⚠️ (Receptor usa #txtFolio)

# Mode: Fecha — ⚠️ TEXT INPUT (no dropdowns como en ConsultaReceptor)
RETEN_EMI_FECHA_INI = "#fecIniEmi"           # text input fecha inicio — formato DD/MM/YYYY ✅ VERIFICADO
RETEN_EMI_FECHA_FIN = "#fecFinEmi"           # text input fecha fin   — formato DD/MM/YYYY ✅ VERIFICADO
RETEN_EMI_SELECT_HORA_INI = "#selHorIni"     # SELECT Hora inicial (00-23)
RETEN_EMI_SELECT_MIN_INI  = "#selMinIni"     # SELECT Minuto inicial (00-59)
RETEN_EMI_SELECT_SEG_INI  = "#selSegIni"     # SELECT Segundo inicial (00-59)
RETEN_EMI_SELECT_HORA_FIN = "#selHorFin"     # SELECT Hora final (00-23)
RETEN_EMI_SELECT_MIN_FIN  = "#selMinFin"     # SELECT Minuto final (00-59)
RETEN_EMI_SELECT_SEG_FIN  = "#selSegFin"     # SELECT Segundo final (00-59)

# Optional filters
RETEN_EMI_INPUT_RFC_RECEPTOR = "#txtReceptor"           # text — RFC del receptor ⚠️ (Receptor usa #txtEmisor)
RETEN_EMI_SELECT_ESTADO = "#selEstadoComprobante"        # SELECT estado (Cancelado/Vigente)
RETEN_EMI_SELECT_TIPO   = "#selComplementos"             # SELECT tipo de comprobante

# Submit — SIN ID (mismo patrón que ConsultaReceptor)
RETEN_EMI_BTN_BUSCAR = "button.btn-primary"   # BUTTON — "Buscar CFDI", onclick="ocultaResultados()"

# Results
RETEN_EMI_TABLE             = "#tablaRetenciones"    # TABLE resultados (mismo ID que ConsultaReceptor)
RETEN_EMI_PANEL_NO_RESULTADOS = "#divNoResultados"   # DIV sin resultados ⚠️ (Receptor usa #divNoResultadosReceptor)
RETEN_EMI_CHECKBOX_TODOS    = "???"                  # requiere resultados activos
RETEN_EMI_PAGINATION        = "???"                  # requiere resultados activos

# Bulk action buttons
RETEN_EMI_BTN_DESCARGAR  = "#descargarSel"       # button — "Descargar seleccionados" (XML)
RETEN_EMI_BTN_METADATA   = "#descargarMetadatos" # button — "Descargar Metadatos"
RETEN_EMI_BTN_PDF        = "#exportarRes"         # button — "Exportar resultados a PDF"

# ⛔ FORBIDDEN
RETEN_EMI_BTN_CANCELAR   = "#cancelarSel"         # ⛔ "Cancelar seleccionados" — NUNCA CLICKEAR

# Per-row icons (requieren resultados activos — RFC MOPR881228EF9 no tiene retenciones emitidas)
# ⚠️ Probablemente son los mismos SPAN IDs que en CFDI dado que es el mismo framework
RETEN_EMI_ICON_DETALLE = "???"   # probablemente #BtnVerDetalle
RETEN_EMI_ICON_XML     = "???"   # probablemente #BtnDescarga
RETEN_EMI_ICON_PDF     = "???"   # probablemente #BtnRI


# ===========================================================================
# PAGE: Retenciones — ConsultaDescargaMasiva (/ConsultaDescargaMasiva)
# ===========================================================================
# STATUS: ✅ VERIFIED 2026-03-05 — RFC MOPR881228EF9
# NOTES:
#   - ⚠️ URL REAL es /ConsultaDescargaMasiva (no /ConsultaMasiva — esa da 503)
#   - Llegar vía RdoTipoConsultaMasiva + Continuar desde página inicial
#   - NO tiene formulario de búsqueda — muestra descargas de los últimos 3 días automáticamente
#   - Sin descargas activas al momento del mapping — tabla vacía (0 filas)
#   - Columnas de tabla: "Descargar paquete | Folio de descarga | RFC contribuyente |
#     Tipo Descarga | Cantidad de documentos | Fecha de la solicitud de descarga"
#   - Descarga vía #setLinkButtonDescarga (A link, mismo patrón que CFDI DescargaMasiva)
#   - Hidden fields: hfFolioDescargaActual, hfUrlDescargaActual, hfToken

RETEN_MASIVA_TABLE              = "#tablaDescarga"          # TABLE con filas de descarga
RETEN_MASIVA_PANEL_NO_RESULTADOS = "#divNoResultados"        # "No existen registros de descargas..."
RETEN_MASIVA_PANEL_RESULTADOS   = "#divResultados"           # DIV con tabla cuando hay descargas
RETEN_MASIVA_BTN_DESCARGAR      = "#setLinkButtonDescarga"   # A link — "Descargar paquete"
RETEN_MASIVA_HF_FOLIO           = "#hfFolioDescargaActual"   # hidden — folio de descarga activa
RETEN_MASIVA_HF_URL             = "#hfUrlDescargaActual"     # hidden — URL del paquete
RETEN_MASIVA_HF_TOKEN           = "#hfToken"                 # hidden — token de descarga


# ===========================================================================
# AUTH DETECTION (cross-page)
# ===========================================================================
# STATUS: ✅ VERIFIED 2026-03-03

AUTH_RFC_INDICATOR = "#ctl00_LblRfcAutenticado"  # SPAN.signin — texto "RFC Autenticado: {RFC}"
AUTH_LOGOUT_LINK = "#anchorClose"                # A — "Salir" → /logout.aspx?salir=y
AUTH_HDN_RFC = "#hdnAut"                         # hidden input — base64(RFC), alternativa programática
AUTH_LOGIN_FORM = "#aspnetForm"                  # El form existe en todas las páginas (auth y no-auth)


# ===========================================================================
# CAPTCHA + LOGIN (cross-page)
# ===========================================================================
# STATUS: ✅ VERIFIED 2026-03-05 — observado en login cfdiau.sat.gob.mx

LOGIN_INPUT_RFC = "input[name*='Ecom_User_ID'], input[id*='RFC']"  # Campo RFC en login
LOGIN_INPUT_PASSWORD = "input[type='password']"                      # Campo contraseña
LOGIN_INPUT_EFIRMA = "input[id*='dynamic'], input[id*='efirma']"    # Clave dinámica e.firma
LOGIN_CAPTCHA_IMG = "img[id*='captcha'], img[id*='Captcha']"        # Imagen CAPTCHA
LOGIN_CAPTCHA_INPUT = "input[id*='captcha'], input[id*='Captcha']"  # Input texto captcha
LOGIN_BTN_ENVIAR = "input[type='submit'][value*='Enviar'], button[id*='submit']"  # Botón Enviar
LOGIN_BTN_EFIRMA = "input[type='submit'][value*='e.firma'], button[id*='efirma']" # Botón e.firma
