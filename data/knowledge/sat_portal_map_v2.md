# Mapa Completo del Ecosistema SAT — OpenDoc v2 (Feb 2026)

> Incluye: 12 portales SAT + 4 portales gobierno relacionados
> Combinación de: live testing (CIEC) + investigación web oficial
> Objetivo: OpenDoc actúe como contador completo del doctor

---

## RESUMEN DE PORTALES

| # | Portal | Dominio | Auth | Estado OpenDoc |
|---|--------|---------|------|----------------|
| 1 | Portal CFDI | portalcfdi.facturaelectronica.sat.gob.mx | CIEC/e.firma | ✅ Mapeado (live) |
| 2 | Retenciones | prodretencioncontribuyente.clouda.sat.gob.mx | CIEC/e.firma | ✅ Mapeado |
| 3 | Portal Principal | sat.gob.mx | Público + Auth | ✅ Mapeado |
| 4 | Buzón Tributario | wwwmat.sat.gob.mx | CIEC/e.firma | ✅ Mapeado (live) |
| 5 | Verificador CFDI | verificacfdi.facturaelectronica.sat.gob.mx | Público | ✅ Nuevo |
| 6 | DeclaraSAT | wwwmat.sat.gob.mx/declaracion/ | e.firma/CIEC | ✅ Nuevo |
| 7 | Mi Portal | portalsat.plataforma.sat.gob.mx | CIEC/e.firma | ✅ Nuevo |
| 8 | CertiSAT Web | aplicacionesc.mat.sat.gob.mx/certisat/ | e.firma | ✅ Nuevo |
| 9 | Contabilidad Electrónica | sat.gob.mx/aplicacion/42150 | e.firma | ✅ Nuevo |
| 10 | DIOT | pstcdi.clouda.sat.gob.mx | e.firma | ✅ Nuevo |
| 11 | Pagos Referenciados | sat.gob.mx/declaracion/20425 | CIEC/e.firma | ✅ Nuevo |
| 12 | Visor de Nómina | sat.gob.mx/declaracion/90887 | CIEC/e.firma | ✅ Nuevo |
| 13 | Verificador Retenciones | prodretencionverificacion.clouda.sat.gob.mx | Público | ✅ Nuevo |
| 14 | SAT ID | satid.sat.gob.mx | Biométrico | ⬜ Referencia |
| 15 | IMSS/IDSE | idse.imss.gob.mx | e.firma/NPIE | ⬜ Futuro |
| 16 | INFONAVIT | empresarios.infonavit.org.mx | e.firma | ⬜ Futuro |

---

## 1. Portal CFDI — Factura Electrónica [LIVE TESTED ✅]

**Base URL**: `https://portalcfdi.facturaelectronica.sat.gob.mx`
**Auth**: CIEC o e.firma
**Uso OpenDoc**: Descarga de XMLs emitidos y recibidos

### URLs mapeadas:
| Página | URL | Acción OpenDoc |
|--------|-----|----------------|
| Home | /Consulta.aspx | Navegación inicial |
| Recibidos | /ConsultaReceptor.aspx | 🔍 Buscar + descargar XMLs de gastos |
| Emitidos | /ConsultaEmisor.aspx | 🔍 Buscar + descargar XMLs de ingresos |
| Descarga Masiva | /ConsultaDescargaMasiva.aspx | 📦 Descarga bulk (últimos 3 días) |
| Cancelación | /ConsultaCancelacion.aspx | 👁️ Solo lectura — ver solicitudes |

### Tabla de resultados (18 columnas):
checkbox, acciones, folio_fiscal, rfc_emisor, nombre_emisor, rfc_receptor,
nombre_receptor, fecha_emision, fecha_certificacion, pac_certifico, total,
efecto_comprobante, estatus_cancelacion, estado_comprobante,
estatus_proceso_cancelacion, fecha_solicitud_cancelacion, fecha_cancelacion,
rfc_cuenta_terceros

---

## 2. Portal de Retenciones [MAPEADO ✅]

**Base URL**: `https://prodretencioncontribuyente.clouda.sat.gob.mx`
**Auth**: CIEC o e.firma
**Uso OpenDoc**: Consultar retenciones de ISR (10%) que hospitales/clínicas hacen al doctor

### URLs:
| Página | URL | Acción OpenDoc |
|--------|-----|----------------|
| Entrada | /?oculta=1 | Selección de tipo consulta |

### Opciones (radio buttons):
1. Consultar CFDI de retenciones emitidas
2. Consultar CFDI de retenciones recibidas ← **CLAVE para el doctor**
3. Recuperar descargas de CFDI de retenciones

---

## 3. Portal SAT Principal [MAPEADO ✅]

**Base URL**: `https://sat.gob.mx`
**Auth**: Mixto (público + autenticado)

### URLs:
| Página | URL | Acción OpenDoc |
|--------|-----|----------------|
| Home | /portal/public/home | Punto de entrada |
| Personas Físicas | /portal/public/personas-fisicas | Info de régimen |
| Trámites | /portal/public/tramites-y-servicios | Hub de servicios |
| Declaraciones PF | /portal/public/tramites/declaraciones-pf | Links a declaraciones |
| Constancia CSF (info) | /portal/public/tramites/constancia-de-situacion-fiscal | Generar constancia |
| Opinión Cumplimiento | /portal/public/tramites/mas-tramites | Verificar status fiscal |
| CSD (info) | /portal/public/tramites/certificado-de-sello-digital | Info sobre CSD |
| Contab. Electr. (info) | /portal/public/tramites/contabilidad-electronica | Info sobre envío |

---

## 4. Buzón Tributario [LIVE TESTED ✅]

**Base URL**: `https://wwwmat.sat.gob.mx`
**Auth**: CIEC o e.firma
**Uso OpenDoc**: Verificar habilitación, leer notificaciones, descargar acuses

### URLs:
| Página | URL | Acción OpenDoc |
|--------|-----|----------------|
| Servicios Buzón | /operacion/00834/servicios-disponibles-del-buzon-tributario | Hub de servicios |
| Acuses RFC | /operacion/43824/reimprime-tus-acuses-del-rfc | Generar constancia |
| Login personas | /personas/iniciar-sesion | Punto de autenticación |
| Declaraciones personas | /personas/declaraciones | Hub de declaraciones |

### Servicios disponibles en Buzón:
- Contabilidad electrónica
- Fiscalización electrónica
- Devoluciones y compensaciones
- Recurso de revocación en línea
- Consultas y autorizaciones
- Donatarias autorizadas
- Avisos y monederos electrónicos

---

## 5. Verificador de CFDI [NUEVO ✅]

**Base URL**: `https://verificacfdi.facturaelectronica.sat.gob.mx`
**Auth**: PÚBLICO (no requiere login)
**Uso OpenDoc**: Validar autenticidad de facturas recibidas antes de deducirlas

### URLs:
| Página | URL | Acción OpenDoc |
|--------|-----|----------------|
| Verificador principal | /default.aspx | Verificar CFDI por UUID |
| Verificador CCP | /verificaccp/default.aspx | Verificar Carta Porte |

### Campos del formulario:
- Folio Fiscal (UUID): text input
- RFC Emisor: text input
- RFC Receptor: text input
- Total: text input (monto del CFDI)
- Captcha: imagen + text input ⚠️ **Requiere humano**
- Botón: "Verificar CFDI"

### Datos retornados:
- Estado del CFDI (Vigente / Cancelado / No encontrado)
- RFC emisor y receptor
- Fecha emisión y certificación
- PAC que certificó
- Total
- Efecto del comprobante
- Estatus de cancelación

### Web Service (API):
- **URL SOAP**: `https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc`
- Permite verificación programática sin captcha
- Parámetros: expresión impresa (UUID, RFC emisor, RFC receptor, total)

---

## 6. DeclaraSAT — Declaraciones Mensuales y Anual [NUEVO ✅]

**Base URL**: `https://wwwmat.sat.gob.mx` (mismo dominio que Buzón)
**Auth**: CIEC o e.firma (e.firma requerida para enviar)
**Uso OpenDoc**: Preparar y prellenar declaraciones provisionales y anual

### URLs — Declaraciones Mensuales:
| Declaración | URL | Régimen |
|-------------|-----|---------|
| Provisional mensual (legacy) | /declaracion/26984/declaracion-mensual-en-el-servicio-de-declaraciones-y-pagos | 612 |
| Actividades prof. + IVA (2025+) | /declaracion/33006/presenta-tu-declaracion-de-actividades-empresariales-y-servicios-profesionales,-arrendamiento-e-iva,-personas-fisicas-de-2025-en-adelante-(simulador) | 612 |
| RESICO mensual | /declaracion/53359/simulador-de-declaraciones-de-pagos-mensuales-y-definitivos | 625 |

### URLs — Declaración Anual:
| Declaración | URL |
|-------------|-----|
| Anual PF (DeclaraSAT) | /DeclaracionAnual/Paginas/default.htm |
| Línea de captura | /declaracion/98410/contribuciones-que-puedes-pagar-con-linea-de-captura |

### Flujo de Declaración Provisional Mensual (Régimen 612):
1. Login con CIEC o e.firma
2. Seleccionar periodo (mes/año)
3. Capturar ingresos acumulables del mes
4. Capturar deducciones autorizadas del mes
5. Sistema calcula ISR (tarifa progresiva)
6. Capturar IVA causado y acreditable (si aplica)
7. Capturar retenciones de ISR (10% de hospitales)
8. Sistema genera línea de captura
9. Firmar con e.firma y enviar
10. Pagar en banco antes del día 17

### Flujo de Declaración Provisional RESICO:
1. Login
2. Seleccionar periodo
3. Ingresos cobrados del mes (prellenado por SAT)
4. Sistema aplica tasa RESICO (1-2.5%)
5. Genera línea de captura
6. Firmar y enviar

### Campos principales de la declaración mensual 612:
- **ISR**: Ingresos acumulables, deducciones autorizadas, utilidad fiscal, pagos provisionales anteriores, retenciones ISR, ISR a cargo/favor
- **IVA**: Valor de actos gravados 16%, exentos, tasa 0%, IVA causado, IVA acreditable, IVA retenido, IVA a cargo/favor

---

## 7. Mi Portal SAT [NUEVO ✅]

**Base URL**: `https://portalsat.plataforma.sat.gob.mx`
**Auth**: CIEC o e.firma
**Uso OpenDoc**: Hub central — acceso a múltiples servicios

### URLs:
| Página | URL |
|--------|-----|
| Login | /SATAuthenticator/AuthLogin/showLogin.action |
| CertiSAT (desde Mi Portal) | /certisat/ |
| Certifica (SOLCEDI) | /certifica/ |

### Servicios accesibles desde Mi Portal:
- Servicio de declaraciones y pagos
- Consulta de obligaciones fiscales
- Constancia de situación fiscal
- Opinión de cumplimiento
- CertiSAT Web
- Certifica (antes SOLCEDI)
- Buzón Tributario
- Consulta de adeudos fiscales

---

## 8. CertiSAT Web — Certificados Digitales [NUEVO ✅]

**Base URL**: `https://aplicacionesc.mat.sat.gob.mx/certisat/`
**Auth**: e.firma (obligatoria — no funciona con CIEC)
**Uso OpenDoc**: Verificar vigencia de CSD para facturación

### URLs:
| Página | URL |
|--------|-----|
| Portal principal | /certisat/ |
| Desde Mi Portal | portalsat.plataforma.sat.gob.mx/certisat/ |

### Servicios disponibles:
- Solicitud de Certificado de Sello Digital (CSD)
- Revocación de CSD
- Revocación de e.firma
- Recuperación de certificados
- Renovación de e.firma
- Seguimiento de solicitudes

### Lo que OpenDoc PUEDE hacer (lectura):
- ✅ Verificar que el CSD esté vigente
- ✅ Consultar fecha de vencimiento
- ✅ Alertar si el CSD está por vencer

### Lo que OpenDoc NO PUEDE hacer (escritura):
- ❌ Generar nuevo CSD
- ❌ Revocar certificados
- ❌ Renovar e.firma

---

## 9. Contabilidad Electrónica [NUEVO ✅]

**Base URL**: `https://www.sat.gob.mx/aplicacion/42150/envia-tu-contabilidad-electronica`
**Portal autenticado**: `https://wwwmat.sat.gob.mx/aplicacion/42150/envia-tu-contabilidad-electronica`
**Auth**: e.firma (obligatoria)
**Uso OpenDoc**: Solo Régimen 612 — envío mensual obligatorio

### Obligaciones:
- **Catálogo de cuentas** (una vez, con código agrupador SAT)
- **Balanza de comprobación** (mensual, antes del día 25 del mes siguiente)
- **Pólizas y auxiliares** (solo cuando SAT las requiere — auditoría)

### Formato de archivos:
- XML comprimido en .ZIP
- Nomenclatura específica por tipo y periodo
- Ejemplo: `RFC123456789_CT_2026_01.zip` (catálogo enero 2026)

### Lo que OpenDoc PUEDE hacer:
- ✅ Generar los XMLs de contabilidad electrónica
- ✅ Validar estructura antes de envío
- ✅ Alertar fechas límite de envío (día 25)

### Quién está obligado:
- Personas físicas con ingresos >$2,000,000 en Régimen 612
- RESICO: **RELEVADO** (RMF 2026, regla 3.13.16)

---

## 10. DIOT — Declaración Informativa de Operaciones con Terceros [NUEVO ✅]

**Base URL (nuevo 2025+)**: `https://pstcdi.clouda.sat.gob.mx`
**Auth**: e.firma (obligatoria)
**Uso OpenDoc**: Solo Régimen 612 — reporte mensual de IVA por proveedor

### Cambio importante (agosto 2025):
- A partir de agosto 2025, la DIOT se presenta ÚNICAMENTE por la nueva plataforma digital
- Ya NO se usa el software DEM (Documentos Electrónicos Múltiples)

### URLs:
| Página | URL |
|--------|-----|
| Portal DIOT (nuevo) | pstcdi.clouda.sat.gob.mx |
| Info DIOT | sat.gob.mx/declaracion/74295/presenta-tu-declaracion-informativa-de-operaciones-con-terceros-(diot)- |

### Contenido de la DIOT (por cada proveedor):
- RFC del proveedor (tercero)
- Monto de operaciones gravadas al 16%
- Monto de operaciones gravadas al 8% (frontera)
- Monto de operaciones a tasa 0%
- Monto de operaciones exentas
- IVA retenido

### Opciones de captura:
- **Carga masiva**: archivo .txt con layout específico
- **Captura manual**: hasta 40 registros online
- **Mixta**: combinación de ambas

### Fecha límite: Día 17 del mes siguiente (con facilidad: último día del mes — RMF 2026)

### Quién está obligado:
- Régimen 612: **OBLIGATORIO**
- RESICO: **RELEVADO** (RMF 2026, regla 3.13.16)

---

## 11. Pagos Referenciados — Línea de Captura [NUEVO ✅]

**Base URL**: `https://www.sat.gob.mx/declaracion/20425/bancos-autorizados-para-recibir-pagos-de-contribuciones-federales`
**Auth**: Varía (CIEC para consulta, e.firma para generar)
**Uso OpenDoc**: Generar línea de captura para pago de impuestos

### Flujo:
1. Declaración genera cantidad a pagar
2. Sistema genera línea de captura (cadena alfanumérica)
3. Doctor paga en banco (ventanilla o banca electrónica)
4. Bancos autorizados reciben pago referenciado

### Tipos de pago:
| Tipo | Descripción |
|------|-------------|
| Pago referenciado | ISR, IVA mensual — generado por DeclaraSAT |
| DPA | Derechos, Productos y Aprovechamientos |
| Línea de captura | Para créditos fiscales, multas, recargos |

### Vigencia de línea de captura:
- Generalmente válida hasta el día 17 del mes
- Extemporánea: se genera nueva con actualización y recargos

### Lo que OpenDoc PUEDE hacer:
- ✅ Recordar al doctor la fecha límite de pago
- ✅ Calcular el monto estimado antes de entrar a DeclaraSAT
- ✅ Alertar si la línea de captura está por vencer

---

## 12. Visor de Nómina [NUEVO ✅]

**Base URL (patrón)**: `https://www.sat.gob.mx/declaracion/90887/consulta-el-visor-de-comprobantes-de-nomina-para-el-patron-`
**Base URL (trabajador)**: `https://www.sat.gob.mx/declaracion/97720/consulta-el-visor-de-comprobantes-de-nomina-para-el-trabajador`
**Auth**: CIEC o e.firma
**Uso OpenDoc**: Verificar nómina timbrada vs retenciones realmente enteradas

### Vista Patrón (doctor como empleador):
- Consultar pagos acumulados a trabajadores
- Verificar información individual por empleado
- Conciliar ISR retenido vs ISR enterado en provisionales
- Datos disponibles desde 2018

### Vista Trabajador (doctor como empleado de hospital/IMSS):
- Consultar recibos de nómina recibidos
- Verificar retenciones ISR de su empleo
- Datos para declaración anual

### Lo que OpenDoc PUEDE hacer:
- ✅ Verificar que la nómina esté correctamente timbrada
- ✅ Conciliar totales de nómina vs declaraciones
- ✅ Alertar discrepancias entre timbrado y pago de retenciones

---

## 13. Verificador de Retenciones [NUEVO ✅]

**Base URL**: `https://prodretencionverificacion.clouda.sat.gob.mx`
**Auth**: Público
**Uso OpenDoc**: Verificar autenticidad de constancias de retención

---

## 14. SAT ID [REFERENCIA]

**Base URL**: `https://satid.sat.gob.mx`
**Auth**: Biométrico (reconocimiento facial)
**Servicios**: Renovación de contraseña, generación de constancia, otros trámites básicos
**OpenDoc**: No aplica — requiere presencia física del doctor

---

## MÉTODOS DE AUTENTICACIÓN

| Método | Acceso | Portales |
|--------|--------|----------|
| CIEC (contraseña) | Básico | CFDI, Retenciones, Buzón, Constancia, Visor Nómina |
| e.firma (.cer + .key) | Completo | TODO: DeclaraSAT, CertiSAT, Contab. Electrónica, DIOT, + todo lo anterior |
| SAT ID | Biométrico | Trámites básicos de identidad |
| Contraseña + CAPTCHA | Público | Verificador CFDI |

**Regla para OpenDoc**: e.firma necesaria para CUALQUIER operación de envío/firma.
CIEC suficiente para TODAS las consultas y descargas.

---

## ZONAS PROHIBIDAS (OpenDoc = Solo lectura)

| Acción | Portal | Razón |
|--------|--------|-------|
| Emitir CFDI | Portal CFDI | Generación de facturas |
| Cancelar CFDI | Portal CFDI | Modificación irreversible |
| Enviar declaraciones | DeclaraSAT | Firma = compromiso legal |
| Pagar impuestos | Bancos | Transacción financiera |
| Generar/revocar CSD | CertiSAT | Seguridad crítica |
| Revocar e.firma | CertiSAT | Seguridad crítica |
| Modificar datos RFC | Mi Portal | Datos del contribuyente |
| Responder notificaciones | Buzón | Implicación legal |
| Dar alta/baja empleados | IMSS/IDSE | Obligación patronal |

**OpenDoc SÍ puede**:
- ✅ Preparar/prellenar datos para declaraciones
- ✅ Calcular montos de impuestos
- ✅ Generar XMLs de contabilidad electrónica
- ✅ Preparar layout DIOT
- ✅ Alertar fechas límite
- ✅ Descargar y analizar CFDIs
- ✅ Verificar autenticidad de facturas
- ✅ Conciliar nómina
- ✅ Recomendar régimen óptimo

**El doctor firma/envía/paga** — OpenDoc prepara todo.

---

## CALENDARIO MENSUAL DEL CONTADOR-BOT

| Día | Acción | Portal |
|-----|--------|--------|
| 1-10 | Descargar CFDIs del mes anterior (emitidos + recibidos) | Portal CFDI |
| 1-10 | Clasificar y analizar gastos/ingresos | OpenDoc (interno) |
| 1-10 | Calcular ISR provisional + IVA | OpenDoc (interno) |
| 1-10 | Preparar DIOT (solo 612) | OpenDoc → pstcdi.clouda.sat.gob.mx |
| 11-15 | Prellenar declaración mensual | OpenDoc → DeclaraSAT |
| 15-17 | Doctor firma y envía declaración | DeclaraSAT (manual) |
| 15-17 | Doctor paga línea de captura | Banco (manual) |
| 17 | ⚠️ FECHA LÍMITE pagos provisionales | — |
| 18-22 | Impuesto cedular estatal (Gto: día 22) | Portal estatal |
| 20-25 | Enviar contabilidad electrónica (solo 612) | Buzón Tributario |
| 25 | ⚠️ FECHA LÍMITE contabilidad electrónica | — |
| Continuo | Verificar Buzón Tributario (notificaciones) | Buzón |
| Continuo | Verificar vigencia CSD | CertiSAT |
| Continuo | Opinión de cumplimiento | sat.gob.mx |
