# Chinoin AI Consultorio Manager

## Descripción General
Kit de herramientas de gestión médica con inteligencia artificial desarrollado para **CHINOIN**, empresa farmacéutica mexicana. Esta aplicación web proporciona herramientas gratuitas para médicos que automatizan la documentación clínica y ofrecen asesoría fiscal/legal.

## Estado del Proyecto
**Versión:** MVP 1.0  
**Fecha:** Octubre 2025  
**Estado:** ✅ Funcional con IA real (Gemini)

## Tecnologías Utilizadas

### Backend
- **Framework:** Flask (Python 3.11)
- **IA:** Google Gemini 2.0 Flash Exp
- **Librerías:** google-genai, Flask

### Frontend
- **HTML5** con templates Jinja2
- **CSS3** personalizado con gradientes y animaciones
- **JavaScript** vanilla para interactividad
- **Diseño:** Responsive, mobile-first

### Infraestructura
- **Servidor:** Flask development server (Puerto 5000)
- **Almacenamiento:** En memoria (diccionarios Python)
- **Secrets:** Replit Secrets para GEMINI_API_KEY

## Arquitectura del Proyecto

```
.
├── main.py                      # Aplicación Flask principal
├── templates/
│   ├── dashboard.html          # Página principal con resumen
│   ├── transcripcion.html      # Transcriptor de consultas con IA
│   └── asesoria.html           # Asistente legal/contable
├── static/
│   ├── style.css               # Estilos con branding CHINOIN
│   └── images/
│       └── logo.png            # Logo corporativo CHINOIN
└── replit.md                   # Este archivo
```

## Funcionalidades Principales

### 1. 🎤 Transcriptor de Consultas (IA) - Feature Estrella ✅ CON GRABACIÓN DE AUDIO REAL
**Ruta:** `/transcripcion`

- **Función:** ¡GRABA consultas médicas con un clic y genera notas SOAP automáticamente!
- **Tecnología:** MediaRecorder API + Gemini 2.0 Flash Exp
- **Flujo completo:**
  1. Médico hace clic en el micrófono 🎤
  2. Audio se graba en tiempo real (con visualización y timer)
  3. Al detener, el audio se envía a Gemini
  4. Gemini transcribe el audio a texto
  5. Gemini genera notas SOAP estructuradas
- **Formato de salida:** SOAP (Subjetivo, Objetivo, Análisis, Plan)
- **Extrae automáticamente:**
  - Transcripción completa de la conversación
  - Síntomas reportados por el paciente
  - Hallazgos de exploración física
  - Diagnóstico sugerido
  - Plan de tratamiento con medicamentos y dosis
  - Verificación de cumplimiento médico-legal
- **Cumplimiento:** Incluye recordatorio de consentimiento informado (NOM-004-SSA3-2012)

### 2. ⚖️ Asistente Legal/Contable
**Ruta:** `/asesoria`

- **Función:** Chatbot especializado en normativas fiscales mexicanas para médicos
- **Temas cubiertos:**
  - Deducibilidad de gastos (gasolina, renta, material médico)
  - CFDI (facturación electrónica)
  - ISR e IVA aplicables a honorarios médicos
  - Cumplimiento legal (avisos de privacidad, consentimientos)
- **Base de conocimiento:** Normativas actualizadas de SAT y leyes mexicanas

### 3. 📊 Dashboard de Gestión
**Ruta:** `/`

- Resumen de actividad médica
- Alertas de cumplimiento fiscal y legal
- Resumen financiero rápido
- Acceso al portal CHINOIN
- Contador de consultas procesadas

## Branding y Diseño

### Colores Corporativos CHINOIN
- **Naranja principal:** `#FF6B4A` (marca CHINOIN)
- **Negro/Gris oscuro:** `#000000`, `#1a1a1a`, `#2d2d2d`
- **Acentos:** Gradientes naranja-negro para efecto premium

### Características de UI/UX
- Diseño profesional farmacéutico
- Cards con hover effects y sombras
- Navegación intuitiva con 3 secciones principales
- Responsive design (desktop/tablet/mobile)
- Feedback visual en botones y acciones

## Flujo de Uso Típico

1. **Médico accede al dashboard** → Ve alertas y resumen
2. **Inicia transcripción de consulta** → Hace clic en el botón 🎤 para grabar
3. **Graba la consulta en tiempo real** → Conversa normalmente con el paciente
4. **Detiene la grabación** → IA transcribe y procesa con Gemini automáticamente
5. **Recibe transcripción + notas SOAP** → Todo aparece en pantalla en segundos
6. **Médico copia las notas** → Las integra a su sistema de expedientes
7. **Consulta dudas fiscales** → Asistente responde sobre CFDI, deducciones, etc.

## Configuración de Secrets

### Variables de Entorno Requeridas
- `GEMINI_API_KEY`: Clave API de Google Gemini (obligatoria)
- `SESSION_SECRET`: Clave secreta de Flask (opcional, tiene default)

## Endpoints API

### GET `/`
Renderiza el dashboard principal

### GET `/transcripcion`
Renderiza la interfaz del transcriptor

### POST `/procesar_consulta`
**Body JSON:**
```json
{
  "consulta_texto": "Médico: Buenos días... Paciente: ..."
}
```
**Respuesta:**
```json
{
  "soap_output": "S (Subjetivo): ...",
  "diagnostico": "Faringitis viral",
  "plan": "Paracetamol 500mg...",
  "cumplimiento": "Verificado"
}
```

### GET `/asesoria`
Renderiza la interfaz del asistente legal

### POST `/api/transcribir_audio`
**Body:** FormData con archivo de audio (WebM format)
**Respuesta:**
```json
{
  "transcription": "Médico: Buenos días... Paciente: ...",
  "soap_output": "S (Subjetivo): ...\nO (Objetivo): ...",
  "diagnostico": "Faringitis viral",
  "plan": "Paracetamol 500mg...",
  "cumplimiento": "Verificado"
}
```

### POST `/consultar_norma`
**Body JSON:**
```json
{
  "pregunta": "¿Es deducible la gasolina?"
}
```
**Respuesta:**
```json
{
  "respuesta": "La gasolina es deducible al 100%..."
}
```

## Limitaciones Actuales (MVP)

- ✅ **Almacenamiento temporal:** Las consultas se guardan en memoria (se pierden al reiniciar)
- ✅ **Sin autenticación:** No hay login de usuarios
- ✅ **Sin persistencia:** No hay base de datos
- ✅ **Servidor de desarrollo:** No está optimizado para producción

## Próximas Fases Sugeridas

### Fase 2 - Persistencia
- [ ] Agregar PostgreSQL para historial de consultas
- [ ] Sistema de usuarios con autenticación
- [ ] Exportación de reportes en PDF

### Fase 3 - Funcionalidades Avanzadas
- [ ] Generación automática de CFDI
- [ ] Calculadora de impuestos y declaración anual
- [ ] Sistema de alertas automáticas NOM-004
- [ ] Integración con inventario farmacéutico CHINOIN

### Fase 4 - Optimización
- [ ] Migrar a servidor WSGI (Gunicorn)
- [ ] Implementar caché para respuestas frecuentes
- [ ] Analytics de uso
- [ ] App móvil nativa

## Notas de Desarrollo

### Prompts de IA Optimizados
Los prompts en `main.py` están diseñados para:
- Generar formato SOAP médico correcto
- Extraer información crítica (dosis, medicamentos)
- Verificar cumplimiento normativo
- Responder con terminología médica mexicana

### Manejo de Errores
- Validación de JSON en todas las rutas POST
- Try-catch en llamadas a Gemini
- Mensajes de error amigables al usuario
- Verificación de respuestas de IA antes de procesar

## Créditos
Desarrollado para **CHINOIN®**  
Powered by **Google Gemini AI**  
Framework: **Flask**

---

## Cómo Usar

1. **Iniciar servidor:** Ya está configurado automáticamente
2. **Acceder:** La URL se muestra en el webview
3. **Probar transcriptor:** Copiar ejemplo de diálogo médico
4. **Verificar resultados:** La IA genera notas SOAP en segundos

---

**Última actualización:** Octubre 2025  
**Mantenedor:** Proyecto CHINOIN AI
