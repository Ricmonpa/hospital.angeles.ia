# Chinoin AI Consultorio — Resumen técnico (para devs)

**Producto:** SaaS B2B para clínicas/hospitales (Practice OS). MVP con transcripción de consultas, notas SOAP, contador fiscal, seguros, legal y farmacovigilancia.

---

## Stack

| Capa | Tech |
|------|------|
| Backend | Flask (Python 3.x) |
| DB | SQLite (`consultas.db`) |
| IA | Google Gemini 2.0 Flash (REST). Opcional: Groq como fallback |
| Front | HTML/CSS/JS, plantillas Jinja2 en `templates/`, estáticos en `static/` |
| Deploy | Railway (Procfile, `PORT` env) |

---

## Estructura relevante

```
main.py                 # App Flask, rutas y APIs (orquestación)
database.py             # 4 clases: ConsultaDB, TransaccionDB, SeguroDB, LegalDB
farmacovigilancia.py    # DDI: extracción Gemini + mock interacciones/alergias
clasificaciones_fiscales.py
formas_pago_sat.py
seguro_ocr.py / seguro_rag.py / seguro_informe.py / seguro_pdf.py
auditoria_nocturna.py
templates/              # dashboard, transcripcion, historial, contador, legal, seguros, etc.
requirements.txt
.env                    # GEMINI_API_KEY, SESSION_SECRET, GROQ_API_KEY (opcional)
```

---

## Módulos / dominios

- **Consultas:** transcripción audio → Gemini; generación SOAP; historial y búsqueda. Tabla `consultas`.
- **Contador:** transacciones (ingreso/gasto), reglas de clasificación, validación, export CSV/Excel. Tablas `transacciones`, `reglas_clasificacion`.
- **Seguros:** OCR credenciales (Gemini Vision), RAG tabuladores, informes PDF. Tablas en `SeguroDB`.
- **Legal:** consentimientos, documentos firmados, contratos staff, alertas, auditoría. Tablas en `LegalDB`.
- **Farmacovigilancia:** `POST /api/validar_farmacovigilancia` — texto → Gemini (solo extracción JSON) → cruce contra mock (alergias + DDI) → semáforo ROJO/NARANJA/VERDE.

---

## Cómo correr

```bash
cp .env.example .env   # Editar con GEMINI_API_KEY y SESSION_SECRET
pip install -r requirements.txt
python main.py
# App en http://localhost:5555 (o PORT)
```

---

## Env mínima

- `GEMINI_API_KEY` — obligatorio para IA (transcripción, SOAP, clasificación, farmacovigilancia, seguros).
- `SESSION_SECRET` — sesiones Flask.
- `GROQ_API_KEY` — opcional; fallback de IA.

---

## APIs útiles (ejemplos)

- `POST /api/transcribir_audio` — audio → transcripción.
- `POST /procesar_consulta` — texto consulta → SOAP + diagnóstico.
- `POST /api/validar_farmacovigilancia` — texto receta/SOAP → `{ nivel, mensaje, detalles, entidades_extraidas }`.
- `GET/POST /api/transacciones`, `POST /api/transacciones/<id>/validar`, `POST /api/clasificar_gasto`.
- Seguros: `POST /api/seguros/procesar_credencial`, `POST /api/seguros/buscar_honorario`, etc.
- Legal: rutas bajo `/legal`, `/api/legal/*`.

---

## Notas para integración

- Toda la lógica de negocio está en módulos Python; `main.py` delega (evitar lógica pesada en rutas).
- Gemini se usa con `response_mime_type: application/json` donde se requiere JSON estricto (SOAP, farmacovigilancia).
- Farmacovigilancia: cero alucinación clínica; Gemini solo extrae entidades; la validación DDI/alergias es lógica Python + mock (futuro: RxNav/DrugBank).
