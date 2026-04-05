# 🛡️ Módulo Asistente Legal - Documentación

## 🎯 Visión General

El **Módulo Asistente Legal** es el "Escudo Blindado del Consultorio". No es un archivador de PDFs, es un **Motor de Cumplimiento Activo** que integra la legalidad en el flujo clínico diario, protegiendo al médico contra demandas (Mala Praxis), multas (COFEPRIS/SAT) y problemas laborales.

### Filosofía: "Legalidad sin Fricción"

- **Para el Doctor**: "Yo solo atiendo pacientes, el sistema se asegura de que firme lo que tenga que firmar."
- **Para el Abogado**: "Tengo un panel de control que me avisa si el doctor está en riesgo, antes de que llegue la demanda."

---

## ✨ Funcionalidades Implementadas

### 1. ✍️ Generador de Consentimiento Informado "On-The-Fly"

**Ruta:** `/legal`

**Características:**
- El doctor indica el procedimiento (ej: "Biopsia de Piel")
- El sistema busca la plantilla aprobada por el abogado
- La IA personaliza automáticamente con datos del paciente, fecha, riesgos y nombre del doctor
- Firma digital en tablet/móvil con canvas de firma
- Estampa fecha, hora y geolocalización (Cumplimiento NOM-151)
- Se guarda automáticamente en el expediente

**API:**
- `POST /api/legal/generar_consentimiento` - Genera consentimiento personalizado
- `POST /api/legal/firmar_documento` - Guarda documento firmado

### 2. 🕵️‍♂️ El "Auditor Silencioso" (Compliance Check)

**Ruta:** `/legal/abogado` → Tab "Auditoría"

**Características:**
- Cruza automáticamente Agenda/Notas Clínicas con Documentos Legales
- Lógica: Si hubo una cirugía el martes a las 10:00 AM... ¿Existe un Consentimiento Informado firmado con fecha anterior?
- Semáforo de Riesgo:
  - 🟢 Verde: Expediente completo
  - 🔴 Rojo: "Alerta: 3 Cirugías de la semana pasada sin Consentimiento firmado. Riesgo Alto."

**API:**
- `POST /api/legal/auditoria_cumplimiento` - Ejecuta auditoría de cumplimiento

**Script Nocturno:**
- `auditoria_nocturna.py` - Ejecuta auditoría automática (configurar como cron job)

### 3. 🤝 Bóveda de Recursos Humanos (Contratos Staff)

**Ruta:** `/legal` → Sección "Contratos por Vencer"

**Características:**
- Gestión de contratos de empleados/asistentes/enfermeras
- Alertas de vencimiento: "El contrato de prueba de la Asistente María vence en 3 días"
- Registro de incidencias laborales (faltas, retardos, quejas)
- Crea antecedentes legales con fecha y hora para despido justificado

**API:**
- `GET /api/legal/contratos` - Obtiene contratos
- `POST /api/legal/contratos` - Crea contrato
- `POST /api/legal/incidencias` - Registra incidencia laboral

### 4. 🚨 Botón de Pánico Legal (Respuesta a Crisis)

**Ruta:** `/legal` → Botón flotante "🚨 Asistencia Urgente"

**Características:**
- ¿Llegó una inspección de COFEPRIS? ¿Un paciente amenazó con demandar?
- El Doctor presiona el botón "Asistencia Urgente"
- El Abogado recibe una alerta prioritaria
- La App despliega una "Guía de Reacción Rápida" pre-cargada:
  - "Qué hacer si llega un inspector"
  - "Qué documentos mostrar y cuáles no"
  - "Guion de silencio"

**API:**
- `POST /api/legal/panico` - Activa botón de pánico

### 5. ⚖️ La Interfaz del Abogado (Command Center)

**Ruta:** `/legal/abogado`

**Características:**

#### Dashboard de Cumplimiento
- Gráfica de pastel: "% de Expedientes que cumplen la NOM-004"
- Estadísticas en tiempo real:
  - Total consultas
  - Consultas con consentimiento
  - Alertas activas por severidad
  - Contratos por vencer

#### Gestor de Plantillas
- Editor donde el abogado sube/actualiza contratos y consentimientos
- Si cambia una ley, actualiza la plantilla y automáticamente todos los doctores usan la versión nueva

#### Bitácora de Auditoría
- Registro inmutable de quién accedió a qué expediente
- Vital para defensa de privacidad de datos

**API:**
- `GET /api/legal/plantillas` - Obtiene plantillas
- `POST /api/legal/plantillas` - Crea/actualiza plantilla
- `GET /api/legal/alertas` - Obtiene alertas
- `POST /api/legal/alertas/<id>/resolver` - Resuelve alerta
- `GET /api/legal/estadisticas_cumplimiento` - Estadísticas

---

## 🗄️ Modelo de Datos

### Tablas Principales

1. **plantillas_legales** - Plantillas de consentimientos y contratos
2. **documentos_firmados** - Documentos firmados con metadatos (fecha, hora, geolocalización)
3. **log_auditoria** - Registro inmutable de accesos
4. **contratos_staff** - Contratos de empleados
5. **incidencias_laborales** - Registro de faltas y problemas
6. **alertas_legales** - Alertas de riesgo detectadas
7. **guias_reaccion_rapida** - Guías para botón de pánico

---

## 🚀 Configuración y Uso

### 1. Inicialización

El módulo se inicializa automáticamente al importar `LegalDB`:

```python
from database import LegalDB
legal_db = LegalDB()
```

### 2. Script de Auditoría Nocturna

Para ejecutar automáticamente la auditoría cada noche:

```bash
# Ejecutar manualmente
python auditoria_nocturna.py

# Configurar como cron job (ejecutar a las 2 AM diariamente)
0 2 * * * /usr/bin/python3 /ruta/a/auditoria_nocturna.py
```

### 3. Crear Primera Plantilla

1. Ir a `/legal/abogado`
2. Tab "Plantillas"
3. Click en "➕ Nueva Plantilla"
4. Llenar formulario:
   - Tipo: Consentimiento Informado
   - Nombre: "Consentimiento Biopsia"
   - Procedimiento: "Biopsia"
   - Contenido: Usar placeholders `[NOMBRE_PACIENTE]`, `[PROCEDIMIENTO]`, `[MEDICO]`, `[FECHA]`

### 4. Generar Primer Consentimiento

1. Ir a `/legal`
2. Llenar formulario:
   - Procedimiento: "Biopsia de Piel"
   - Nombre del Paciente: "Juan Pérez"
3. Click en "Generar Consentimiento"
4. El paciente firma en el canvas
5. Click en "Firmar y Guardar"

---

## 📊 Flujo de Trabajo Típico

### Para el Médico:

1. **Durante la consulta:**
   - El médico indica el procedimiento en el transcriptor
   - Si requiere consentimiento, el sistema sugiere generarlo

2. **Generar consentimiento:**
   - Click en "Generar Consentimiento Informado"
   - El sistema busca la plantilla y personaliza
   - El paciente firma en tablet/móvil
   - Se guarda automáticamente

3. **Ver alertas:**
   - El dashboard muestra alertas de riesgo
   - El médico puede ver qué falta

### Para el Abogado:

1. **Revisar dashboard:**
   - Ver porcentaje de cumplimiento NOM-004
   - Ver alertas activas por severidad

2. **Ejecutar auditoría:**
   - Click en "Ejecutar Auditoría de Cumplimiento"
   - El sistema cruza consultas vs documentos
   - Crea alertas automáticamente

3. **Gestionar plantillas:**
   - Crear/actualizar plantillas de consentimientos
   - Si cambia una ley, actualizar plantilla
   - Todos los médicos usan la versión nueva automáticamente

4. **Resolver alertas:**
   - Revisar alertas de riesgo
   - Resolver con notas
   - Asesorar al médico si es necesario

---

## 🔒 Cumplimiento Legal

### NOM-004-SSA3-2012
- Consentimiento informado obligatorio para procedimientos invasivos
- El sistema verifica automáticamente si existe consentimiento

### NOM-151-SCFI-2016
- Firma digital con fecha, hora y geolocalización
- Hash del documento para integridad
- Registro inmutable en log de auditoría

### LFPDPPP
- Aviso de privacidad (plantillas disponibles)
- Registro de accesos a datos personales

---

## 🎨 Interfaz de Usuario

### Vista del Médico (`/legal`)
- Generador de consentimientos
- Canvas de firma digital
- Vista de alertas
- Registro de incidencias laborales
- Botón de pánico flotante

### Vista del Abogado (`/legal/abogado`)
- Dashboard de cumplimiento con KPIs
- Gestor de plantillas
- Lista de alertas
- Bitácora de auditoría
- Ejecución de auditorías

---

## 🔧 Tecnologías Utilizadas

- **Backend:** Flask (Python)
- **Base de datos:** SQLite
- **Firma digital:** Signature Pad (JavaScript)
- **IA:** Google Gemini 2.0 Flash (personalización de documentos)
- **Frontend:** HTML5, CSS3, JavaScript vanilla

---

## 📝 Notas de Implementación

### Fase 1 (MVP) - Completada ✅

- ✅ Generador de consentimientos con IA
- ✅ Firma digital con canvas
- ✅ Auditoría de cumplimiento
- ✅ Gestión de contratos y alertas
- ✅ Botón de pánico
- ✅ Dashboard del abogado
- ✅ Script de auditoría nocturna

### Fase 2 (Futuro) - Pendiente

- [ ] Integración con WhatsApp para envío de consentimientos
- [ ] Notificaciones push al abogado
- [ ] Exportación de documentos a PDF
- [ ] Integración con firma electrónica avanzada (e.firma SAT)
- [ ] Dashboard de métricas avanzadas
- [ ] Integración con expediente clínico electrónico

---

## 🆘 Soporte

Para problemas o preguntas sobre el módulo legal:
1. Revisar esta documentación
2. Ver logs en consola del servidor
3. Ejecutar auditoría manual desde el panel del abogado

---

**Desarrollado para CHINOIN®**  
Powered by Google Gemini AI

