# Mapa del Portal SAT - Obtenido por Live Testing (Feb 2026)

> Sesion de mapeo real con cuenta autenticada (RFC: MOPR881228EF9)
> Portal version: 4.5.0
> Autenticacion utilizada: CIEC (contrasena)

---

## 1. Portal CFDI - Factura Electronica

**Base URL**: `https://portalcfdi.facturaelectronica.sat.gob.mx`

### 1.1 Pagina Principal
- **URL**: `/Consulta.aspx`
- **Opciones disponibles**:
  1. Consultar Facturas Emitidas
  2. Consultar Facturas Recibidas
  3. Recuperar Descargas de CFDI
  4. Consultar Solicitudes de Cancelacion

### 1.2 Consultar Facturas Recibidas
- **URL**: `/ConsultaReceptor.aspx`
- **Formulario de busqueda**:
  - Radio: Folio Fiscal (UUID) — input text, placeholder "FOLIO FISCAL"
  - Radio: Fecha de Emision — dropdowns: Ano, Mes, Dia (opcional)
  - Hora Inicial: 3 dropdowns HH:MM:SS (default 00:00:00)
  - Hora Final: 3 dropdowns HH:MM:SS (default 23:59:59)
  - RFC Emisor: text input
  - RFC a cuenta terceros: text input
  - Estado del Comprobante: dropdown ("Seleccione un valor...")
  - Tipo de Comprobante (Complemento): dropdown ("Seleccione un valor...")
  - Boton: "Buscar CFDI"

- **Tabla de resultados (18 columnas)**:
  1. Checkbox (select all / individual)
  2. Acciones (3 iconos: ver detalle, descargar XML, ver documento)
  3. Folio Fiscal (UUID)
  4. RFC Emisor
  5. Nombre o Razon Social del Emisor
  6. RFC Receptor
  7. Nombre o Razon Social del Receptor
  8. Fecha de Emision (formato ISO: 2026-01-01T13:02:14)
  9. Fecha de Certificacion
  10. PAC que Certifico (RFC del PAC)
  11. Total (monto con $)
  12. Efecto del Comprobante (Ingreso, Egreso, etc.)
  13. Estatus de cancelacion (ej: "Cancelable sin aceptacion")
  14. Estado del Comprobante (Vigente, Cancelado)
  15. Estatus de Proceso de Cancelacion
  16. Fecha de Solicitud de la Cancelacion
  17. Fecha de Cancelacion
  18. RFC a cuenta de terceros

- **Botones post-tabla**:
  - "Descargar Seleccionados" — bulk XML download
  - "Descargar Metadata" — metadata export
  - "Exportar Resultados a PDF"

### 1.3 Consultar Facturas Emitidas
- **URL**: `/ConsultaEmisor.aspx`
- **Diferencias vs Recibidas**:
  - Fechas usan DATE RANGE PICKER (Fecha Inicial + Fecha Final con iconos calendario)
  - En lugar de dropdowns Ano/Mes/Dia
  - Filtro: "RFC Receptor" (en vez de "RFC Emisor")
  - Hora: mismos 3 dropdowns HH:MM:SS
  - Resto igual: RFC terceros, Estado Comprobante, Tipo Comprobante, Buscar CFDI

### 1.4 Recuperar Descargas de CFDI
- **URL**: `/ConsultaDescargaMasiva.aspx`
- Muestra descargas masivas de ultimos 3 dias
- Mensaje si vacio: "No existen registros de descargas desde los ultimos 3 dias a la fecha."

### 1.5 Consultar Solicitudes de Cancelacion
- **URL**: `/ConsultaCancelacion.aspx`
- Muestra solicitudes de cancelacion pendientes/procesadas
- Mensaje si vacio: "No existen registros que cumplan con los criterios de busqueda ingresados"

### 1.6 Menu "Consulta CFDI" (dropdown)
- Factura Electronica → va a /Consulta.aspx
- Retenciones e Inf. de Pagos → va a portal de retenciones

### 1.7 Menu "Generacion de CFDI" (dropdown)
- Configuracion de datos V 4.0
- **ZONA PROHIBIDA** — no explorar

---

## 2. Portal de Retenciones

**Base URL**: `https://prodretencioncontribuyente.clouda.sat.gob.mx`

- **URL entrada**: `/?oculta=1`
- **Nota**: Diferente subdominio (`clouda.sat.gob.mx`)
- **Opciones (radio buttons)**:
  1. Consultar CFDI de retenciones emitidas (default)
  2. Consultar CFDI de retenciones recibidas
  3. Recuperar descargas de CFDI de retenciones
- **Boton**: "Continuar"

---

## 3. Portal SAT Principal

**Base URL**: `https://sat.gob.mx`

### 3.1 Navegacion principal
- **URL home**: `/portal/public/home`
- **Barra**: Inicio | Tramites y servicios | Personas | Empresas | Buscar

### 3.2 Seccion Personas
- **URL**: `/portal/public/personas-fisicas`
- **Regimenes relevantes**:
  - Personas Fisicas con Actividades Empresariales y Profesionales (612)
  - Regimen Simplificado de Confianza (RESICO 625)
- **Minisitios**: Declaracion Anual, Deducciones personales, Factura, Catalogo Minisitios

### 3.3 Tramites y Servicios
- **URL**: `/portal/public/tramites-y-servicios`
- **Tarjetas principales**:
  - RFC, personas
  - e.firma, personas
  - Declaraciones para personas
  - Cita
  - Factura electronica
  - RFC, empresas
  - e.firma, empresas
  - Declaraciones para empresas
  - Adeudos fiscales
  - Mas tramites y servicios

### 3.4 Mas Tramites — Constancias, devoluciones y notificaciones
- **URL**: `/portal/public/tramites/mas-tramites`
- **Servicios**:
  - **Opinion del cumplimiento** → clave para aseguradoras
  - **Notificaciones** → buzon tributario
  - **Devoluciones y compensaciones**
  - Recurso de revocacion en linea
  - Consultas y autorizaciones (juridica)
  - Donatarias autorizadas
  - **Constancia de Situacion Fiscal** → documento esencial

### 3.5 Constancia de Situacion Fiscal
- **URL info**: `/portal/public/tramites/constancia-de-situacion-fiscal`
- **Contenido del documento**: CIF con QR, RFC, nombre, lugar/fecha, CURP, domicilio, regimen fiscal
- **Requisitos online**: Contrasena o e.firma
- **Flujo**:
  1. Ingresa al servicio (link externo)
  2. Selecciona "Generar Constancia"
  3. Descarga PDF
- **5 vias de obtencion**: Web, SAT Movil, SAT ID, Oficina Virtual, Cedula datos fiscales

---

## 4. Portal Autenticado — Buzon Tributario

**Base URL**: `https://wwwmat.sat.gob.mx`

### 4.1 Reimpresion de Acuses / Generar Constancia
- **URL**: `/operacion/43824/reimprime-tus-acuses-del-rfc`
- **Formulario**:
  - Tipo de tramite: dropdown
  - Fecha inicial / Fecha final: date pickers
  - Numero de folio: text input
- **Botones**: Limpiar, Buscar (azul), **Generar Constancia**
- **Tabla**: Tipo tramite | Numero folio | Fecha operacion | Canal | Reimprimir

### 4.2 Servicios Disponibles del Buzon Tributario
- **URL**: `/operacion/00834/servicios-disponibles-del-buzon-tributario`
- **Tramites**:
  - Contabilidad electronica
  - Fiscalizacion electronica
  - Devoluciones y Compensaciones
  - Recurso de revocacion en linea
  - Consultas y autorizaciones (juridica)
  - Donatarias autorizadas
- **Avisos**:
  - Avisos
  - Monederos electronicos
- **Decretos**:
  - Sociedades Cooperativas
  - Prestacion de servicios parciales de construccion

---

## 5. Metodos de Autenticacion

| Metodo | Que es | Que permite |
|--------|--------|-------------|
| CIEC | RFC + contrasena | Acceso basico: consultas, constancia |
| e.firma | Archivos .cer + .key + contrasena | Acceso completo: CFDIs, constancia, buzon, declaraciones |

**Hallazgo**: La CIEC permitio acceso al portal CFDI completo y al portal autenticado (wwwmat.sat.gob.mx). No fue necesaria la e.firma para consulta.

---

## 6. Datos Reales Observados

- **RFC autenticado**: MOPR881228EF9 (Ricardo Moncada Palafox)
- **CFDIs recibidos enero 2026**: 5 documentos
  - 3 de Google Cloud Mexico (GCM221031837) - PAC: EME000602QR9
  - 2 de Bancoppel (BSI061110963) - PAC: INT020124V62
- **Montos**: $0.09, $0.02, $9.30, $0.00, $6.96
- **Todos**: Tipo Ingreso, Vigente, Cancelable sin aceptacion

---

## 7. Zonas Prohibidas (NO automatizar escritura)

- Generacion de CFDI (emision de facturas)
- Cancelacion de CFDIs
- Modificacion de datos fiscales
- CertiSAT Web
- Enviar/Firmar declaraciones
- Responder notificaciones del buzon
- Marcar notificaciones como leidas
