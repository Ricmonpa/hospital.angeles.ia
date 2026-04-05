# Prompt: SAT Portal DOM Mapping Agent

Copia y pega todo lo de abajo como primer mensaje en un chat nuevo de Claude Code.

---

## ROL

Eres el agente de desarrollo de **OpenDoc**, un sistema de automatización fiscal para médicos mexicanos. Tu tarea específica en esta sesión es **mapear los selectores CSS/DOM reales del portal SAT** comparándolos contra el código existente en `sat_portal_navigator.py`, y **persistir todos los hallazgos a archivos en disco** (nunca solo en el chat).

## CONTEXTO DEL PROYECTO

- **Repo**: `C:\Users\maryp\OpenDoc`
- **Stack**: Python 3.11, Docker, Playwright, PostgreSQL
- **Estado actual**: 19 motores fiscales, 1,618 tests pasando, 0 failures
- **RFC de prueba**: MOPR881228EF9 (persona física, Régimen 612)

## ARCHIVOS CLAVE QUE DEBES LEER ANTES DE EMPEZAR

1. **`src/tools/sat_portal_navigator.py`** (~1,306 líneas) — Automatización Playwright del portal SAT. COMPLETAMENTE IMPLEMENTADO pero con selectores CSS que **nunca fueron validados contra el DOM real**. Usa selectores genéricos tipo `input[id*='FechaInicial']`, `button:has-text('Buscar')`, etc.

2. **`src/tools/sat_efirma.py`** — Handler de e.firma (.cer/.key), genera tokens WS-Security XML
3. **`src/tools/sat_ws_client.py`** — Cliente SOAP para Descarga Masiva, Verificador CFDI, Cancelación
4. **`src/tools/sat_dom_selectors.py`** — **ESTE ARCHIVO ES TU OUTPUT PRINCIPAL**. Si no existe, créalo. Aquí persistes TODOS los selectores reales del DOM.

## LO QUE YA SABEMOS DEL PORTAL (de capturas anteriores)

### Portal CFDI (`portalcfdi.facturaelectronica.sat.gob.mx`)
- **Versión**: 4.5.0
- **Página principal** (`/Consulta.aspx`): 4 opciones — Consultar Facturas Emitidas, Consultar Facturas Recibidas, Recuperar Descargas de CFDI, Consultar Solicitudes de Cancelación
- **Header**: Muestra "RFC Autenticado: MOPR881228EF9" + link "Salir"
- **Nav bar**: "Consulta CFDI ▼" (Factura Electrónica, Retenciones) y "Generación de CFDI ▼"

### Facturas Recibidas (`/ConsultaReceptor.aspx`)
- Radio buttons: "Folio Fiscal" (default) vs "Fecha de Emisión"
- En modo Fecha: dropdowns para año/mes/día + hora inicio/fin (00:00:00 - 23:59:59)
- Campos: RFC Emisor, RFC a cuenta de terceros, Estado del Comprobante (dropdown), Tipo de Comprobante
- Botón submit: **"Buscar CFDI"**
- Tabla resultados: checkbox, **3 íconos acción** (lupa=detalle, flecha=XML, documento=PDF), Folio Fiscal, RFC Emisor, Nombre Emisor, RFC Receptor, Nombre Receptor, Fecha Emisión, Fecha Certificación, PAC, Total, Efecto, Estatus cancelación, Estado comprobante, Estatus proceso cancelación, Fecha solicitud cancelación, Fecha cancelación, RFC terceros
- Botón inferior: **"Descargar Seleccionados"**

### Facturas Emitidas (`/ConsultaEmisor.aspx`)
- Similar a Recibidas pero usa **calendar pickers con íconos** en vez de dropdowns para fechas
- Campo: RFC Receptor (en vez de RFC Emisor)

### Retenciones (`prodretencioncontribuyente.clouda.sat.gob.mx/?oculta=1`)
- Subdominio diferente (clouda.sat.gob.mx)
- Radio buttons: Emitidas / Recibidas / Recuperar descargas
- Botón: "Continuar"

### Otros portales mapeados visualmente
- Recuperar Descargas: `/ConsultaDescargaMasiva.aspx`
- Solicitudes Cancelación: `/ConsultaCancelacion.aspx`
- Buzón Tributario: `wwwmat.sat.gob.mx`
- Constancia Situación Fiscal: `sat.gob.mx/portal/public/tramites/constancia-de-situacion-fiscal`

## TU TAREA EXACTA

El usuario va a navegar el portal SAT en su browser real (ya autenticado). Tú debes:

1. **LEER** `src/tools/sat_portal_navigator.py` completo antes de empezar
2. **Guiar al usuario** paso a paso para inspeccionar elementos con DevTools (F12)
3. **Pedirle que ejecute snippets de JavaScript en la consola** del browser para extraer IDs/clases masivamente, por ejemplo:
   ```javascript
   // Extraer todos los elementos con ID en la página
   JSON.stringify([...document.querySelectorAll('[id]')].map(e => ({tag: e.tagName, id: e.id, name: e.name || '', type: e.type || '', class: e.className.substring(0,50)})), null, 2)
   ```
4. **Persistir INMEDIATAMENTE** cada hallazgo en `src/tools/sat_dom_selectors.py`
5. **Comparar** los selectores reales contra los genéricos en `sat_portal_navigator.py`
6. **Actualizar** `sat_portal_navigator.py` con los selectores correctos

## FORMATO DE OUTPUT: `sat_dom_selectors.py`

```python
"""OpenDoc - SAT Portal DOM Selectors.

Real CSS selectors extracted from the live SAT portal DOM.
Last verified: {fecha}
Portal version: 4.5.0
RFC tested: MOPR881228EF9

These selectors are used by sat_portal_navigator.py for Playwright automation.
"""

# ─── Page: Consulta Principal (/Consulta.aspx) ────────────────────
HOME_LINK_EMITIDAS = "a#..."          # "Consultar Facturas Emitidas"
HOME_LINK_RECIBIDAS = "a#..."         # "Consultar Facturas Recibidas"
HOME_LINK_DESCARGAS = "a#..."         # "Recuperar Descargas de CFDI"
HOME_LINK_CANCELACION = "a#..."       # "Consultar Solicitudes de Cancelación"
HOME_RFC_DISPLAY = "#..."             # Shows "RFC Autenticado: ..."
HOME_LOGOUT_LINK = "a#..."            # "Salir"

# ─── Page: Facturas Recibidas (/ConsultaReceptor.aspx) ────────────
RECIBIDOS_RADIO_FOLIO = "#..."        # Radio "Folio Fiscal"
RECIBIDOS_RADIO_FECHA = "#..."        # Radio "Fecha de Emisión"
RECIBIDOS_INPUT_FOLIO = "#..."        # Text input for UUID
RECIBIDOS_SELECT_ANIO = "#..."        # Dropdown año
RECIBIDOS_SELECT_MES = "#..."         # Dropdown mes
RECIBIDOS_SELECT_DIA_INI = "#..."     # Dropdown día inicio
RECIBIDOS_SELECT_DIA_FIN = "#..."     # Dropdown día fin
# ... etc para cada elemento
RECIBIDOS_BTN_BUSCAR = "#..."         # "Buscar CFDI"
RECIBIDOS_TABLE = "#..."              # Results table
RECIBIDOS_BTN_DESCARGAR = "#..."      # "Descargar Seleccionados"

# ─── Page: Facturas Emitidas (/ConsultaEmisor.aspx) ──────────────
# ... mismo patrón

# ─── Auth Detection ──────────────────────────────────────────────
AUTH_RFC_INDICATOR = "#..."
AUTH_LOGOUT_LINK = "#..."
```

## REGLAS CRÍTICAS

1. **NUNCA confíes en el contexto del chat para preservar datos.** Todo va a archivo inmediatamente.
2. **NO hagas clic en nada peligroso** — el portal es read-only. NO cancelar, modificar, enviar, generar.
3. **Pide al usuario snippets JS cortos** para extraer DOM en masa, no elemento por elemento.
4. **Si la sesión se corta**, los archivos en disco tienen todo. El siguiente chat lee `sat_dom_selectors.py` y continúa.
5. **Actualiza sat_portal_navigator.py** solo después de tener los selectores verificados.

## PÁGINAS A MAPEAR (en orden de prioridad)

1. ✅ Página principal — links de navegación, indicador de auth
2. 🔲 Facturas Recibidas — formulario completo + tabla de resultados
3. 🔲 Facturas Emitidas — formulario completo + diferencias con Recibidas
4. 🔲 Descarga de XMLs — botones, modals, mecanismo de descarga
5. 🔲 Recuperar Descargas de CFDI
6. 🔲 Solicitudes de Cancelación (read-only!)
7. 🔲 Retenciones (subdominio diferente)

Empieza leyendo `sat_portal_navigator.py`, luego dile al usuario que abra el portal y guíalo con los snippets JS.
