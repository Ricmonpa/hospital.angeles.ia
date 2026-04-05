# Hospital Ángeles IA — aplicación web

Suite web para médicos: transcripción y notas SOAP, **Agente Contable** (fiscal), transacciones fiscales, seguros, legal y farmacovigilancia.

## Stack

- **Backend:** Flask (Python)
- **IA:** Google Gemini 2.0 Flash (REST); opcional Groq como fallback
- **Datos:** SQLite (`consultas.db`) en el directorio de la app
- **Frontend:** Jinja2, HTML/CSS/JS

## Variables de entorno

- `GEMINI_API_KEY` — obligatoria para funciones de IA
- `SESSION_SECRET` — sesiones Flask
- `GROQ_API_KEY` — opcional

## Ejecutar en local

```bash
cd web
pip install -r requirements.txt
cp .env.example .env   # editar claves
python main.py
```

## Despliegue (Railway)

**Root Directory del servicio:** `web`

Variables: `GEMINI_API_KEY`, `SESSION_SECRET` (y opcionales como arriba).

---

Hospital Ángeles IA · Gemini AI
