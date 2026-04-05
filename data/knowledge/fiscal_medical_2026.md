# Base de Conocimiento Fiscal para Profesionales de la Medicina en Mexico - Ejercicio 2026

> Fuente: Investigacion basada en normatividad oficial del gobierno de Mexico.
> Uso: Contexto para el clasificador fiscal de OpenDoc (Gemini).

---

## 1. Regimenes Fiscales Aplicables a Medicos

### 1.1 Regimen de Actividades Empresariales y Profesionales (Regimen 612)

- **Base gravable**: Utilidad fiscal = Ingresos acumulables - Deducciones autorizadas
- **Tarifa**: Progresiva (tasa marginal maxima segun tablas ISR)
- **Obligaciones**:
  - Contabilidad electronica mensual enviada al SAT
  - DIOT (Declaracion Informativa de Operaciones con Terceros)
  - Pagos provisionales mensuales
  - Declaracion anual en abril
- **Ventaja**: Deducciones operativas ilimitadas (gastos indispensables)
- **Desventaja**: Costo administrativo alto

### 1.2 Regimen Simplificado de Confianza (RESICO - Regimen 625)

- **Base gravable**: Ingresos facturados y efectivamente cobrados (flujo de efectivo bruto)
- **Tasas**: Fijas y reducidas (1.0% - 2.5%) segun tablas RESICO
- **Tope de ingresos**: $3,500,000 MXN anuales (superar = expulsion automatica a Regimen 612)
- **NO permite deducciones operativas** para calculo de ISR
- **Facilidades (RMF 2026, regla 3.13.16)**:
  - Relevados de contabilidad electronica mensual
  - Relevados de presentar DIOT
- **Causales de expulsion**:
  - Omision de presentacion de declaraciones
  - Falta de activacion/actualizacion del Buzon Tributario
  - Superar tope de ingresos
- **Compatibilidad**: Puede tributar RESICO + Sueldos y Salarios + Intereses + Arrendamiento simultaneamente

### 1.3 Convergencia de Regimenes (Pluriempleo Medico)

- Estandar de la industria: medico con plaza publica (IMSS/ISSSTE) + practica privada
- Declaracion Anual: ingresos NO se mezclan en base unica
  - RESICO: calculo estanco con tasas preferenciales
  - Sueldos y salarios: tarifa progresiva Art. 152 LISR
- Deducciones personales: aplican SOLO sobre ingresos por salarios (no sobre RESICO)

---

## 2. Tratamiento del IVA en Servicios de Salud

### 2.1 Exencion General (Art. 15 LIVA)

- **NO se paga IVA** por prestacion de servicios profesionales de medicina, hospitalarios, radiologia, laboratorios y estudios clinicos
- **Condicion absoluta**: Servicio prestado por persona fisica con titulo de medico expedido y registrado conforme a leyes profesionales de Mexico
- **Consecuencia (IVA no acreditable)**: El IVA que el medico paga en gastos operativos (renta, equipo, telefonia, consumibles) NO puede acreditarse ni solicitarse en devolucion. Se convierte en costo operativo directo.
- **Implicacion de negocio**: Integrar el 16% de sobrecosto al calcular punto de equilibrio y honorarios

### 2.2 Excepcion: Medicina Estetica y Cirugia Plastica (Criterio 7/IVA/N)

- Procedimientos cuyo proposito EXCLUSIVO sea embellecimiento fisico (no restitucion funcional, curacion o rehabilitacion) = **GRAVADOS al 16% IVA**
- Ejemplos:
  - Reconstruccion mamaria post-mastectomia oncologica = **EXENTO** (rehabilitatorio)
  - Aumento mamario estetico = **GRAVADO 16%** (embellecimiento)
- El medico estetico DEBE:
  - Segmentar facturacion (exento vs gravado)
  - Cobrar 16% IVA al paciente en procedimientos esteticos
  - Declarar y enterar IVA mensualmente
  - Puede acreditar IVA de insumos directamente atribuibles a cirugia gravada

### 2.3 Medicamentos y Material de Curacion

- Enajenacion de medicinas de patente: **Tasa 0% IVA**
- Medicamentos suministrados dentro de hospital a paciente internado: se absorben en servicio hospitalario = **EXENTOS**
- Medicamentos comprados en farmacia externa: **NO deducibles como deduccion personal** (solo si constan en factura hospitalaria global)

---

## 3. Facturacion Electronica CFDI 4.0

### 3.1 Parametros Obligatorios para Honorarios Medicos

| Campo | Valor Correcto | Nota |
|-------|---------------|------|
| Tipo de Comprobante | "I" (Ingreso) | Siempre para consultas/procedimientos |
| Uso del CFDI | "D01" (Honorarios medicos, dentales y gastos hospitalarios) | Para que sea deducible para el paciente |
| Uso CFDI alternativo | "P01" (Por definir) | Si paciente desconoce el uso. CFDI mantiene validez, NO requiere cancelacion |
| Metodo de Pago (contado) | "PUE" (Pago en una sola exhibicion) | Pago al momento |
| Clave de Unidad | "E48" (Unidad de servicio) | Obligatoria para servicios medicos |
| Objeto de Impuesto | "02" (Si objeto de impuesto) | Aun cuando sea exento |
| Factor IVA | "Exento" | Para servicios medicos exentos |

### 3.2 Catalogo de Claves de Productos/Servicios Medicos (SAT)

| Clave | Descripcion |
|-------|-------------|
| 85121600 | Servicios medicos de doctores especialistas |
| 85121502 | Servicios de consulta de medicos de atencion primaria |
| 85121601 | Servicios de ginecologia y obstetricia |
| 85121608 | Servicios de psicologia |
| 85101601 | Servicios de enfermeria |
| 85121800 | Laboratorios medicos |
| 85121701 | Servicios de psicoterapeutas |
| 85101503 | Servicios de consultorios medicos |
| 85101507 | Centros asistenciales de urgencia |

### 3.3 Forma de Pago y Deducibilidad para el Paciente

| Forma de Pago | Deducible para paciente? | Clave |
|---------------|-------------------------|-------|
| Efectivo | **NO** (pierde deduccion personal) | 01 |
| Cheque nominativo | SI | 02 |
| Transferencia electronica | SI | 03 |
| Tarjeta de credito | SI | 04 |
| Tarjeta de debito | SI | 28 |
| Monedero electronico | SI | 05 |

### 3.4 Retencion de ISR por Personas Morales (Art. 106 LISR)

- Cuando el medico factura a una **Persona Moral** (clinica, hospital, aseguradora):
  - La PM **retiene 10% de ISR** sobre monto bruto de honorarios
  - Ejemplo: Honorario $2,500 → Retencion $250 → Neto recibido $2,250
  - La retencion es **pago anticipado** (acreditamiento) que se aplica a favor en pago provisional mensual
- Cuando factura a **Persona Fisica**: No hay retencion

---

## 4. Deducciones

### 4.1 Deducciones Autorizadas (Operativas - Solo Regimen 612)

**Principio rector**: Estricta indispensabilidad (Art. 27 LISR)

Gastos deducibles del consultorio:
- Arrendamiento del local
- Equipo medico (ecografos, monitores, esterilizadores) — depreciacion
- Nomina del personal (enfermeras, secretarias, tecnicos)
- Cuotas IMSS e INFONAVIT de empleados
- Energia electrica e internet
- Material de curacion desechable y papeleria
- Seguro de responsabilidad civil profesional medica

**Candados antifraude**:
- Gastos > $2,000 MXN: **obligatorio** pago por sistema financiero (transferencia, cheque nominativo, tarjeta)
- Cada gasto debe estar amparado por XML valido (CFDI)
- **RESICO**: Estas deducciones NO aplican para disminuir base gravable

### 4.2 Tasas de Depreciacion de Inversiones (Art. 31-38 LISR)

| Tipo de Inversion | Tasa Anual |
|-------------------|------------|
| Equipo medico electromecanico | 10% |
| Equipo de computo | 30% |
| Vehiculos (tope deducible $175,000) | 25% |
| Mobiliario de oficina | 10% |

### 4.3 Deducciones Personales (Declaracion Anual - Todos los regimenes)

**Limite global**: Menor entre 15% de ingresos totales o 5 UMAs anualizadas

| Deduccion | Requisitos | Limite |
|-----------|-----------|--------|
| Honorarios medicos y dentales | Titulo profesional del prestador | Limite global |
| Gastos por discapacidad (>=50%) | CFDI con correlacion clinica | **SIN limite** (excepcion) |
| Medicinas hospitalarias | Solo si constan en factura del hospital | Limite global |
| Ortopedia, protesis, lentes graduados | Diagnostico medico | Limite global (lentes con sublimite) |
| Colegiaturas (preescolar-bachillerato) | CFDI con CURP del estudiante | Limites por nivel (fuera del global) |
| Transporte escolar | Obligatorio por reglamento escolar | Limite global |
| Aportaciones retiro (Afore/PPR) | Subcuenta voluntaria | 10% de ingresos, max 5 UMAs |
| Seguros de gastos medicos mayores | Primas de polizas independientes | Limite global |

**Regla critica**: TODAS requieren pago bancarizado. Efectivo = nulidad de deduccion.
**RESICO + Salarios**: Deducciones personales aplican SOLO sobre calculo de ingresos por salarios.

---

## 5. Calendario de Obligaciones Fiscales

### 5.1 Federales (SAT)

| Obligacion | Periodicidad | Fecha limite |
|------------|-------------|-------------|
| Pago provisional ISR | Mensual | Dia 17 del mes siguiente |
| Declaracion IVA | Mensual | Dia 17 del mes siguiente |
| DIOT (solo Regimen 612) | Mensual | Dia 17 del mes siguiente |
| Contabilidad electronica (solo 612) | Mensual | Envio al SAT |
| Declaracion Anual PF | Anual | Abril |

### 5.2 Estatales (Modelo Guanajuato)

| Obligacion | Periodicidad | Fecha limite | Tasa |
|------------|-------------|-------------|------|
| Impuesto Cedular sobre honorarios | Mensual | Dia 22 del mes siguiente | 2% sobre utilidad |
| Impuesto sobre Nominas (ISN) | Mensual | Dia 22 del mes siguiente | ~2.3% + sobretasas |
| ISN sobretasa desarrollo social | Mensual | Dia 22 | 0.2% |
| ISN sobretasa paz publica | Mensual | Dia 22 | 0.1% |

### 5.3 Alertas RMF 2026

- Cancelacion CFDI: ventana de 24 horas reforzada
- Tasa de recargos mensual: 2.07% (aumento vs 2025)
- Buzon Tributario: activacion OBLIGATORIA (causal de expulsion de RESICO si no esta activo)

---

## 6. Opinion del Cumplimiento (Art. 32-D CFF, Regla 2.1.36 RMF)

### Que es
Certificado digital del SAT que avala la salud tributaria del contribuyente.

### Requisitos para Opinion "Positiva"
- Todas las declaraciones presentadas en tiempo
- Ningun credito fiscal firme pendiente
- Estatus "localizable" en domicilio fiscal
- Buzon Tributario habilitado, activo y validado (SMS + correo electronico)

### Consecuencias de Opinion "Negativa"
- Aseguradoras de gastos medicos: **bloqueo para alta en redes medicas** y pago de tabuladores
- Licitaciones gubernamentales de salud: **bloqueadas**
- Subsidios y estimulos financieros: **inaccesibles**

---

## 7. Consultorios Adyacentes a Farmacias (CAF)

- Consulta medica = servicio profesional independiente
- Venta de medicamentos = actividad empresarial de comercio
- Ambas actividades permitidas bajo RESICO
- Facturacion y tratamiento IVA: **cuentas separadas**
- Consulta: CFDI con claves de servicios medicos
- Farmacia: CFDI con claves de productos farmaceuticos

---

## 8. Impuestos Estatales y Municipales (Modelo Guanajuato 2026)

### 8.1 Permisos Municipales para Consultorio (Ejemplo: Leon, Gto.)

1. **Alineamiento y Numero Oficial** — Registro catastral del inmueble
2. **Permiso de Uso de Suelo** — Autoriza vocacion comercial/medica
   - Requisitos: formato solicitud, escrituras, identificacion, contrato arrendamiento
   - Costo: ~$2,041.42 MXN (intensidad baja, <600 m2)
3. **Visto Bueno de Proteccion Civil** — Plan de contingencia, rutas evacuacion, simulacros
4. **Aviso de Funcionamiento COPRISEG** — Cumplimiento NOM, medico responsable sanitario, manejo RPBI
5. **Permisos especiales** — Para centros de rehabilitacion/psiquiatricos: reportes fotograficos, croquis, proyecto arquitectonico

### 8.2 Impuesto sobre Nominas (ISN) - Detalles

- Base gravable incluye: sueldos, horas extras, premios, comisiones, vales despensa, comedor, transporte, seguros de vida/GMM como prestacion
- Honorarios asimilados a salarios: se suman a base ISN
- **Subcontratacion (outsourcing)**: clinica tiene responsabilidad solidaria, debe retener ISN del personal externo
