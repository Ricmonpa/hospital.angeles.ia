# Hospital Ángeles IA

Monorepo del demo: suite web para médicos + herramientas fiscales (Python).

| Carpeta | Contenido |
|--------|-----------|
| **`web/`** | App **Flask** (UI, APIs, transcripción, Agente Contable, transacciones, seguros, legal, farmacovigilancia). **Railway: Root Directory = `web`** *o* raíz del repo con `railway.toml` / Dockerfile ya corregidos (no ejecutar `src.core.main` en producción). |
| **`src/`** | Módulos fiscales SAT / CFDI / calculadoras (Agente Contable). Importados desde `web/main.py`. |
| **`data/`** | Prompts (`SOUL.md`), conocimiento fiscal, plantillas. |
| **`tests/`** | Pruebas del paquete `src/`. |

Variables típicas en producción (`web`): `GEMINI_API_KEY`, `SESSION_SECRET`.

Repositorio: [github.com/Ricmonpa/hospital.angeles.ia](https://github.com/Ricmonpa/hospital.angeles.ia).
