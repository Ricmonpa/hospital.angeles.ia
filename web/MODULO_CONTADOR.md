# 💼 Módulo Asistente Contable - Documentación

## 🎯 Visión General

El **Módulo Asistente Contable** transforma la gestión financiera del consultorio médico, automatizando la clasificación y conciliación de transacciones. El contador pasa de ser un capturador manual a un validador estratégico.

### Principio "Zero-Entry"
El contador **solo valida y descarga**, no captura manualmente.

---

## ✨ Características Implementadas (Fase 1)

### 1. 📊 Dashboard Financiero
- **Estadísticas en tiempo real**:
  - 💰 Ingresos totales
  - 💸 Gastos totales
  - 📈 Utilidad (P&L)
  - ⏳ Transacciones pendientes de validación

### 2. 🔍 Grid Dinámico de Transacciones
- **Tabla interactiva** con todas las transacciones
- **Filtros avanzados**:
  - Por tipo (Ingreso/Gasto)
  - Por estatus (Pendiente/Aprobado/Rechazado)
  - Por rango de fechas
  - Por clasificación fiscal
- **Exportación a CSV/Excel** con un clic
- **Vista tipo "Excel"** con ordenamiento y agrupación

### 3. 🤖 Motor de Clasificación Inteligente
- **Clasificación automática** de gastos usando IA
- **Aprendizaje continuo**: Cada validación del contador mejora el sistema
- **Reglas aprendidas**: El sistema recuerda patrones
  - Ejemplo: "Telcel" → "Deducible Operativo" (100%)
  - Ejemplo: "Gasolina + Pemex + Tarjeta" → "Deducible" (100%)
- **Sugerencias inteligentes** para gastos nuevos

### 4. ✓ Sistema de Validación Rápida
- **Interfaz Approve/Reject** para revisión rápida
- **Validación en 1 clic** para transacciones correctas
- **Edición rápida** para ajustes necesarios
- **Notas del contador** para documentar decisiones

### 5. 📥 Gestión de Transacciones
- **Crear nuevas transacciones** manualmente
- **Clasificación automática** al crear
- **Campos completos**:
  - Tipo (Ingreso/Gasto)
  - Fecha, Concepto, Proveedor
  - Monto, Método de pago
  - Clasificación fiscal
  - Porcentaje deducible

---

## 🗄️ Modelo de Datos

### Tabla: `transacciones`
```sql
- id: Identificador único
- medico_id: ID del médico (multi-tenant ready)
- tipo: 'ingreso' o 'gasto'
- fecha: Fecha de la transacción
- monto: Cantidad en pesos
- concepto: Descripción del movimiento
- proveedor: Nombre del proveedor/paciente
- cfdi_uuid: UUID del CFDI (para integración SAT futura)
- cfdi_vigente: Validación de vigencia
- clasificacion_ia: Clasificación sugerida por IA
- clasificacion_contador: Clasificación final del contador
- deducible_porcentaje: 0-100%
- estatus_validacion: 'pendiente', 'aprobado', 'rechazado', 'ajustado'
- notas_contador: Observaciones
- metodo_pago: 'efectivo', 'tarjeta', 'transferencia'
```

### Tabla: `reglas_clasificacion`
```sql
- patron_concepto: Patrón de texto a buscar
- proveedor: Nombre del proveedor
- clasificacion: Clasificación fiscal
- deducible_porcentaje: Porcentaje deducible
- frecuencia_uso: Contador de veces aplicada
```

---

## 🔌 API Endpoints

### GET `/contador`
Vista principal del módulo con dashboard y grid

### GET `/api/transacciones`
Obtener transacciones con filtros
- Query params: `tipo`, `estatus`, `fecha_desde`, `fecha_hasta`, `clasificacion`

### POST `/api/transacciones`
Crear nueva transacción
- Body: `{ tipo, fecha, monto, concepto, proveedor, metodo_pago }`
- Response: Incluye clasificación sugerida por IA

### POST `/api/transacciones/:id/validar`
Validar una transacción
- Body: `{ estatus, clasificacion, deducible_porcentaje, notas }`
- Efecto: Aprende la regla automáticamente

### POST `/api/clasificar_gasto`
Clasificar un gasto usando IA (Gemini)
- Body: `{ concepto, proveedor, monto }`
- Response: `{ clasificacion, deducible_porcentaje, justificacion }`

### GET `/api/estadisticas_financieras`
Obtener estadísticas del periodo
- Query params: `fecha_desde`, `fecha_hasta`

### GET `/api/exportar_transacciones`
Exportar transacciones a CSV
- Query params: filtros opcionales

---

## 🚀 Flujo de Trabajo del Contador

### Día a Día (Simplificado)

1. **Carga Automática** (Asistente/Doctor)
   - Sube tickets y documentos vía web
   - Sistema descarga CFDIs del SAT (futuro)

2. **Clasificación IA** (Automático)
   - La IA pre-clasifica todos los gastos
   - Aplica reglas aprendidas
   - Sugiere porcentaje deducible

3. **Validación** (Contador - 5 minutos)
   - Entra al panel de "Pendientes"
   - Revisa sugerencias de IA
   - Aprueba con 1 clic o ajusta
   - **80% de transacciones aprobadas sin edición**

4. **Reporte** (Contador - 1 clic)
   - Genera reporte mensual/anual
   - Exporta a Excel si necesita
   - Solo incluye transacciones validadas

### Ahorro de Tiempo Estimado
- **Antes**: 10 horas/mes en captura y clasificación
- **Ahora**: 4 horas/mes en validación
- **Ahorro**: 60% del tiempo

---

## 🧠 Sistema de Aprendizaje

### Cómo Aprende el Sistema

1. **Primera vez**: Contador clasifica "Gasolina - Pemex" como "Deducible 100%"
2. **Sistema aprende**: Guarda regla `Gasolina + Pemex → Deducible 100%`
3. **Próxima vez**: Detecta "Gasolina - Pemex" automáticamente
4. **Mejora continua**: Cada validación refuerza el patrón

### Niveles de Confianza
- **Alta**: Regla exacta encontrada (mismo concepto + proveedor)
- **Media**: Similitud de concepto encontrada
- **Baja**: Sin regla, usa clasificación por defecto o Gemini IA

---

## 📈 Próximas Fases (Roadmap)

### Fase 2: Integración SAT (Semanas 5-8)
- [ ] Conexión con API del SAT
- [ ] Descarga automática de CFDIs
- [ ] Validación de vigencia en tiempo real
- [ ] Conciliación automática con ingresos registrados

### Fase 3: IA Avanzada (Semanas 9-12)
- [ ] Clasificación con Gemini para casos complejos
- [ ] Detección de anomalías fiscales
- [ ] Sugerencias proactivas de optimización
- [ ] Integración WhatsApp para consultas del contador

### Fase 4: Reportes Avanzados (Semanas 13-16)
- [ ] Reportes fiscales automáticos
- [ ] Declaraciones pre-llenadas
- [ ] Análisis de tendencias
- [ ] Alertas de cumplimiento

---

## 🎓 Guía de Uso Rápido

### Para el Contador

1. **Acceder al módulo**: `/contador`
2. **Ver pendientes**: Filtrar por "Estatus: Pendiente"
3. **Validar rápido**: Clic en ✓ para aprobar o ✗ para rechazar
4. **Editar si necesario**: Clic en ✎ para ajustar clasificación
5. **Exportar**: Clic en "Exportar CSV" para llevar a Excel

### Para el Doctor/Asistente

1. **Agregar transacción**: Clic en "➕ Nueva Transacción"
2. **Llenar datos**: Tipo, fecha, concepto, monto
3. **Guardar**: El sistema clasifica automáticamente
4. **Listo**: El contador validará después

---

## 🔒 Seguridad y Cumplimiento

- ✅ Datos almacenados localmente (SQLite)
- ✅ Preparado para multi-tenant (medico_id)
- ✅ Auditoría completa (created_at, updated_at, validado_por)
- ✅ Respaldo de decisiones (notas_contador)
- ✅ Cumplimiento fiscal mexicano

---

## 📞 Soporte

Para dudas o sugerencias sobre el módulo:
- Documentación técnica: Este archivo
- Código fuente: `database.py` (clase TransaccionDB), `main.py` (endpoints)
- Interfaz: `templates/contador.html`

---

**Hospital Ángeles IA**  
Powered by Google Gemini AI  
Versión 1.0 - Fase 1 Completada ✅
