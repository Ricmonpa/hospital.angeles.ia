# 🛡️ Módulo de Inteligencia Aseguradora

## 📋 Descripción General

El **Módulo de Seguros** transforma la gestión de seguros médicos en el consultorio, automatizando la decodificación de pólizas, búsqueda de honorarios y generación de informes médicos. El objetivo es responder rápidamente: "¿Cuánto me van a pagar?" y "¿Cuánto tiene que pagar el paciente?".

---

## ✨ Características Implementadas

### 1. 📸 Escáner Decodificador de Credenciales

**Funcionalidad:**
- Procesamiento OCR de credenciales de seguro usando Gemini Vision API
- Extracción automática de información:
  - Aseguradora (GNP, AXA, Seguros Monterrey, MetLife, Banorte)
  - Número de póliza
  - Nombre del plan
  - Nivel hospitalario
  - Nombre del paciente (si está visible)
  - Vigencia

**Características:**
- Soporte para imágenes desde web o upload
- Normalización automática de nombres de aseguradoras
- Consulta automática de información del plan (deducible, coaseguro, hospitales)
- Guardado en base de datos para historial

**Flujo:**
1. Usuario sube foto de credencial
2. IA extrae datos usando OCR
3. Sistema consulta información del plan
4. Muestra tarjeta de resumen con deducible, coaseguro y hospitales

---

### 2. 💰 Buscador Inteligente de Honorarios (RAG)

**Funcionalidad:**
- Búsqueda en tabuladores médicos usando RAG (Retrieval Augmented Generation)
- Motor de búsqueda semántica con Gemini
- Consulta de honorarios por procedimiento y aseguradora

**Características:**
- Búsqueda por nombre de procedimiento
- Búsqueda por código CPT (opcional)
- Filtrado por aseguradora y plan
- Retorna monto, descripción, código CPT y nivel de confianza

**Flujo:**
1. Doctor/asistente pregunta: "¿Cuánto paga GNP Línea Azul por una Apendicectomía laparoscópica?"
2. Sistema busca en tabuladores cargados (PDFs)
3. IA extrae información relevante usando RAG
4. Responde con monto y detalles del procedimiento

**API de Consulta de Cobertura:**
- Consulta si un procedimiento está cubierto
- Revisa condiciones generales del seguro
- Indica requisitos, periodos de espera y exclusiones

---

### 3. 📝 Generador de Informe Médico Automático

**Funcionalidad:**
- Generación automática de informes médicos en PDF
- Llenado automático desde datos de la consulta (SOAP notes)
- Compatible con múltiples aseguradoras

**Características:**
- Toma datos de la consulta (ID de consulta)
- Llena automáticamente campos:
  - Datos del paciente
  - Datos del seguro (desde credencial procesada)
  - Diagnóstico y código CIE-10
  - Procedimiento y código CPT
  - Resumen clínico (desde SOAP notes)
  - Tratamiento
- Genera PDF listo para imprimir y firmar
- Formato profesional y estándar

**Flujo:**
1. Doctor completa consulta y genera notas SOAP
2. Doctor selecciona consulta y credencial de seguro
3. Sistema genera PDF automáticamente
4. PDF descargado listo para imprimir/firmar

---

## 🗄️ Modelo de Datos

### Tabla: `credenciales_seguros`
- Almacena credenciales procesadas
- Campos: aseguradora, póliza, plan, deducible, coaseguro, hospitales

### Tabla: `tabuladores`
- Almacena PDFs de tabuladores cargados
- Campos: aseguradora, plan, tipo_documento, contenido_texto, fecha_vigencia

### Tabla: `informes_medicos`
- Almacena informes generados
- Campos: consulta_id, credencial_id, aseguradora, diagnóstico, procedimiento

### Tabla: `consultas_honorarios`
- Historial de búsquedas de honorarios
- Campos: aseguradora, plan, procedimiento, monto_encontrado

---

## 🔌 Endpoints API

### POST `/api/seguros/procesar_credencial`
Procesa una imagen de credencial de seguro usando OCR.

**Body:** FormData con campo `imagen`
**Respuesta:**
```json
{
  "success": true,
  "credencial_id": 123,
  "datos": {
    "aseguradora": "GNP",
    "numero_poliza": "123456",
    "plan_nombre": "Línea Azul Premium",
    "deducible_estimado": 15000,
    "coaseguro_porcentaje": 10,
    "hospitales_red": "Hospital Ángeles, Médica Sur"
  }
}
```

### POST `/api/seguros/buscar_honorario`
Busca honorario de un procedimiento en tabuladores.

**Body:**
```json
{
  "aseguradora": "GNP",
  "plan_nombre": "Línea Azul Premium",
  "procedimiento": "Apendicectomía laparoscópica",
  "codigo_cpt": "44970"
}
```

**Respuesta:**
```json
{
  "success": true,
  "resultado": {
    "monto": 18500,
    "codigo_cpt": "44970",
    "descripcion": "Apendicectomía laparoscópica",
    "moneda": "MXN",
    "confianza": "alta",
    "fuente": "GNP - Línea Azul Premium"
  }
}
```

### POST `/api/seguros/consultar_cobertura`
Consulta si un procedimiento está cubierto por el seguro.

**Body:**
```json
{
  "aseguradora": "GNP",
  "plan_nombre": "Línea Azul Premium",
  "procedimiento": "Cirugía de catarata"
}
```

**Respuesta:**
```json
{
  "success": true,
  "resultado": {
    "cubierto": true,
    "requisitos": "Autorización previa requerida",
    "periodo_espera": "2 años",
    "exclusiones": "",
    "confianza": "alta"
  }
}
```

### POST `/api/seguros/generar_informe`
Genera informe médico en PDF automáticamente.

**Body:**
```json
{
  "consulta_id": 123,
  "credencial_seguro_id": 456,
  "aseguradora": "GNP",
  "procedimiento": "Cirugía",
  "codigo_cpt": "12345",
  "codigo_cie10": "A00.0"
}
```

**Respuesta:** PDF descargable

---

## 📦 Archivos del Módulo

### Backend
- `database.py`: Clase `SeguroDB` para gestión de datos
- `seguro_ocr.py`: Procesamiento OCR de credenciales con Gemini Vision
- `seguro_rag.py`: Motor RAG para búsqueda en tabuladores
- `seguro_informe.py`: Generador de PDFs de informes médicos
- `main.py`: Endpoints API del módulo

### Frontend
- `templates/seguros.html`: Interfaz completa del módulo

---

## 🚀 Uso del Módulo

### Escáner Decodificador
1. Ir a pestaña "📸 Escáner Decodificador"
2. Subir foto de credencial (arrastrar o seleccionar)
3. Hacer clic en "Procesar Credencial con IA"
4. Ver resumen automático con deducible, coaseguro y hospitales

### Buscador de Honorarios
1. Ir a pestaña "💰 Buscador de Honorarios"
2. Seleccionar aseguradora
3. Ingresar nombre del procedimiento
4. (Opcional) Ingresar código CPT
5. Hacer clic en "Buscar Honorario"
6. Ver resultado con monto y detalles

### Generar Informe
1. Ir a pestaña "📝 Generar Informe Médico"
2. Ingresar ID de consulta
3. Seleccionar aseguradora
4. Completar campos opcionales (procedimiento, códigos, etc.)
5. Hacer clic en "Generar Informe PDF"
6. PDF se descarga automáticamente

---

## 🔧 Configuración Técnica

### Dependencias
- `reportlab`: Generación de PDFs
- `Pillow`: Procesamiento de imágenes
- `PyPDF2`, `pdfplumber`: Lectura de PDFs (para futuros tabuladores)
- `Google Gemini API`: OCR y RAG

### Variables de Entorno
- `GEMINI_API_KEY`: Clave API de Google Gemini (requerida)

---

## 📈 Próximos Pasos (Fase 2)

### Mejoras Planeadas
- [ ] Cargar tabuladores PDF desde interfaz
- [ ] Extracción automática de texto de PDFs
- [ ] Sistema de embeddings para búsqueda semántica mejorada
- [ ] Templates personalizados por aseguradora
- [ ] Integración con WhatsApp bot
- [ ] Sistema de caché para consultas frecuentes
- [ ] Dashboard de estadísticas de honorarios

---

## 💡 Flujo de Valor para el Doctor

### Escenario Real de Uso:

1. **Recepción**: Paciente llega. Asistente toma foto a credencial desde WhatsApp o web
2. **Procesamiento**: Bot responde: "Paciente con Seguros Monterrey, Plan Alfa. Deducible $25,000. Coaseguro 10%."
3. **Consulta**: Doctor atiende. Usa Transcriptor de IA para notas SOAP
4. **Cierre**: Doctor pregunta: "¿Cubre este seguro la cirugía de catarata?"
5. **Respuesta**: Sistema revisa condiciones y responde: "Sí, pero requiere periodo de espera de 2 años"
6. **Salida**: Doctor hace clic en "Generar Informe Médico". Paciente se va con PDF listo

---

**Desarrollado para CHINOIN®**  
Powered by Google Gemini AI

