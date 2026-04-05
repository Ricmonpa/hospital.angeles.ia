# -*- coding: utf-8 -*-
"""
Módulo de Farmacovigilancia y Seguridad Clínica (DDI).
Extracción de entidades con Gemini (solo orquestador) y validación dura contra mock/DB.
CERO alucinaciones clínicas: la IA no inventa interacciones; solo extrae datos del texto.
"""
import json
import re
import sys
import requests
from typing import Dict, List, Any, Optional, Tuple


def _log(msg: str):
    """Print que siempre se muestra en Railway (stderr + flush)."""
    print(f"[farmacovigilancia] {msg}", file=sys.stderr, flush=True)

# --- 1. MOCK DATA: Fuente de verdad para cruce (simula RxNav/DrugBank) ---

# Sustancias que pueden desencadenar alergia → fármacos que las contienen o son sinónimos
# Si el paciente tiene alergia a X y la receta contiene algún fármaco de la lista → ROJO
SUSTANCIAS_ALERGENICAS = {
    "sulfas": [
        "sulfametoxazol", "trimetoprim", "cotrimoxazol", "bactrim", "sulfadiazina",
        "sulfasalazina", "sulfacetamida", "sulfadoxina", "sulfisoxazol", "sulfa"
    ],
    "penicilina": [
        "penicilina", "amoxicilina", "ampicilina", "benzilpenicilina",
        "oxacilina", "cloxacilina", "dicloxacilina", "piperacilina"
    ],
    "ácido acetilsalicílico": ["ácido acetilsalicílico", "aspirina", "asa", "aas"],
    "ibuprofeno": ["ibuprofeno", "ibuprofeno"],
    "dipirona": ["dipirona", "metamizol", "novalgina"],
    "contraste yodado": ["contraste", "yodado", "medio de contraste"],
}

# Interacciones fármaco-fármaco: (sustancia_a, sustancia_b) → (nivel, mensaje)
# Orden alfabético normalizado para búsqueda bidireccional
INTERACCIONES_MOCK = [
    {
        "farmacos": ("warfarina", "ibuprofeno"),
        "nivel": "NARANJA",
        "mensaje": "AINE + anticoagulante: riesgo de sangrado. Considerar alternativa (paracetamol) o monitorizar INR.",
    },
    {
        "farmacos": ("warfarina", "aspirina"),
        "nivel": "ROJO",
        "mensaje": "Anticoagulante + AAS: riesgo grave de sangrado. Evitar combinación salvo indicación formal.",
    },
    {
        "farmacos": ("metformina", "contraste yodado"),
        "nivel": "NARANJA",
        "mensaje": "Metformina + contraste yodado: riesgo de acidosis láctica. Suspender metformina 48h antes y reanudar tras valorar función renal.",
    },
    {
        "farmacos": ("fluoxetina", "tramadol"),
        "nivel": "NARANJA",
        "mensaje": "ISRS + tramadol: riesgo de síndrome serotoninérgico. Vigilar si es necesario la combinación.",
    },
    {
        "farmacos": ("fluoxetina", "sertralina"),
        "nivel": "ROJO",
        "mensaje": "Dos ISRS: riesgo de síndrome serotoninérgico. No combinar dos inhibidores de recaptura de serotonina.",
    },
    {
        "farmacos": ("ketorolaco", "warfarina"),
        "nivel": "ROJO",
        "mensaje": "Ketorolaco + anticoagulante: riesgo alto de sangrado. Evitar combinación.",
    },
    {
        "farmacos": ("ibuprofeno", "naproxeno"),
        "nivel": "NARANJA",
        "mensaje": "Dos AINEs: mayor riesgo de sangrado digestivo y renal. Evitar uso concomitante.",
    },
]

# Alergenos reconocidos (lo que el paciente puede reportar) → clave en SUSTANCIAS_ALERGENICAS
ALERGENOS_NORMALIZADOS = [
    "sulfas", "sulfa", "penicilina", "aspirina", "ácido acetilsalicílico",
    "ibuprofeno", "dipirona", "metamizol", "contraste yodado", "novalgina", "aas", "asa"
]


def _normalizar(nombre: str) -> str:
    """Normaliza nombre de fármaco/sustancia para comparación: minúsculas, sin acentos, sin espacios extra."""
    if not nombre or not isinstance(nombre, str):
        return ""
    s = nombre.lower().strip()
    s = re.sub(r"\s+", " ", s)
    reemplazos = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u"}
    for a, b in reemplazos.items():
        s = s.replace(a, b)
    return s


def _contiene_sustancia(farmaco_normalizado: str, lista_sustancias: List[str]) -> bool:
    """True si el fármaco (nombre normalizado) está en la lista o contiene alguna sustancia de la lista."""
    for s in lista_sustancias:
        if s in farmaco_normalizado or farmaco_normalizado in s:
            return True
    return False


def _pertenece_a_alergeno(farmaco_normalizado: str, alergeno: str) -> bool:
    """True si el fármaco pertenece al grupo alérgeno (ej. sulfas, penicilina)."""
    lista = SUSTANCIAS_ALERGENICAS.get(alergeno, [])
    return _contiene_sustancia(farmaco_normalizado, [_normalizar(x) for x in lista])


# --- 2. Extracción con Gemini (solo entidades; sin inventar interacciones) ---

PROMPT_EXTRACCION = """Eres un extractor de entidades médicas. Tu ÚNICA tarea es extraer del texto siguiente tres listas, sin inventar ni inferir datos que no aparezcan explícitamente en el texto.

Reglas estrictas:
- Incluye SOLO lo que el texto menciona de forma clara.
- Si no se menciona receta actual, tratamiento crónico o alergias, devuelve un array vacío para ese campo.
- No inventes medicamentos, alergias ni interacciones.
- Nombres de medicamentos: usa el nombre genérico o el que aparezca en el texto (minúsculas, sin inventar).

Devuelve ÚNICAMENTE un JSON válido con esta estructura exacta (sin markdown, sin comentarios):
{{
  "receta_actual": [
    {{"nombre": "nombre del medicamento", "dosis": "dosis si se menciona o vacío", "via": "oral/iv/im/tópica/etc o vacío"}}
  ],
  "tratamiento_cronico": [
    {{"nombre": "nombre del medicamento"}}
  ],
  "alergias_conocidas": [
    "sustancia o familia (ej: Sulfas, Penicilina)"
  ]
}}

Texto del paciente/consulta:
---
{texto}
---
"""


def extraer_entidades_gemini(texto: str, api_key: Optional[str]) -> Dict[str, Any]:
    """
    Llama a la API de Gemini para extraer receta_actual, tratamiento_cronico y alergias_conocidas.
    Siempre devuelve un dict con "ok" (bool) y "_debug" (str).
    Si ok=True, incluye receta_actual, tratamiento_cronico, alergias_conocidas.
    """
    if not api_key:
        _log("NO API KEY")
        return {"ok": False, "_debug": "GEMINI_API_KEY no configurada en el servidor"}
    if not texto or not texto.strip():
        _log("Texto vacío")
        return {"ok": False, "_debug": "Texto vacío"}

    _log(f"Llamando Gemini con {len(texto)} chars de texto")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    prompt = PROMPT_EXTRACCION.format(texto=texto.strip())
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"},
    }
    try:
        r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
        _log(f"Gemini status={r.status_code}")
        if r.status_code != 200:
            body = r.text[:300]
            _log(f"Gemini error: {body}")
            return {"ok": False, "_debug": f"Gemini HTTP {r.status_code}: {body}"}
        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates:
            finish = data.get("promptFeedback", {})
            _log(f"Sin candidates. promptFeedback={finish}")
            return {"ok": False, "_debug": f"Sin candidates. promptFeedback={json.dumps(finish)[:300]}"}

        candidate = candidates[0]
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        if not parts:
            _log(f"Sin parts. finishReason={candidate.get('finishReason')}")
            return {"ok": False, "_debug": f"Sin parts. finishReason={candidate.get('finishReason')}"}

        raw_text = parts[0].get("text") or ""
        _log(f"Gemini raw (200c): {raw_text[:200]}")
        if not raw_text.strip():
            return {"ok": False, "_debug": "Gemini devolvió text vacío"}

        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        parsed = json.loads(cleaned)
        if not isinstance(parsed, dict):
            return {"ok": False, "_debug": f"JSON parseado no es dict: {type(parsed).__name__}"}

        _log(f"Extracción OK: {len(parsed.get('receta_actual',[]))} receta, {len(parsed.get('tratamiento_cronico',[]))} crónicos, {len(parsed.get('alergias_conocidas',[]))} alergias")
        return {
            "ok": True,
            "_debug": "ok",
            "receta_actual": _asegurar_lista(parsed.get("receta_actual"), dict),
            "tratamiento_cronico": _asegurar_lista(parsed.get("tratamiento_cronico"), dict),
            "alergias_conocidas": _asegurar_lista(parsed.get("alergias_conocidas"), str),
        }
    except json.JSONDecodeError as e:
        _log(f"JSON inválido: {e}")
        return {"ok": False, "_debug": f"JSON inválido de Gemini: {e}"}
    except Exception as e:
        _log(f"Error: {type(e).__name__}: {e}")
        return {"ok": False, "_debug": f"{type(e).__name__}: {e}"}


def _asegurar_lista(val, tipo_elemento):
    if val is None:
        return []
    if not isinstance(val, list):
        return []
    out = []
    for x in val:
        if tipo_elemento is str and isinstance(x, str):
            out.append(x.strip())
        elif tipo_elemento is dict and isinstance(x, dict):
            out.append(x)
    return out


# --- 3. Lógica de cruce (validación dura) ---

def _obtener_nombres_receta(receta_actual: List[Dict]) -> List[str]:
    """Extrae nombres normalizados de receta_actual."""
    nombres = []
    for item in receta_actual:
        if isinstance(item, dict) and item.get("nombre"):
            nombres.append(_normalizar(str(item["nombre"])))
    return nombres


def _obtener_nombres_cronicos(tratamiento_cronico: List[Dict]) -> List[str]:
    """Extrae nombres normalizados de tratamiento_cronico."""
    nombres = []
    for item in tratamiento_cronico:
        if isinstance(item, dict) and item.get("nombre"):
            nombres.append(_normalizar(str(item["nombre"])))
    return nombres


def _evaluar_alergias(
    nombres_receta: List[str],
    alergias_conocidas: List[str],
) -> List[Dict[str, Any]]:
    """Cruza receta vs alergias. Retorna lista de hallazgos (nivel ROJO)."""
    detalles = []
    alergias_norm = [_normalizar(a) for a in alergias_conocidas if a]
    for nombre in nombres_receta:
        if not nombre:
            continue
        for alergeno_key, sustancias in SUSTANCIAS_ALERGENICAS.items():
            if _contiene_sustancia(nombre, [_normalizar(s) for s in sustancias]):
                # Ver si el paciente reportó alergia a este grupo
                for aler in alergias_norm:
                    if (
                        alergeno_key in aler
                        or aler in alergeno_key
                        or _contiene_sustancia(aler, [_normalizar(s) for s in sustancias])
                    ):
                        detalles.append({
                            "tipo": "alergia",
                            "nivel": "ROJO",
                            "farmaco": nombre,
                            "alergeno_reportado": aler,
                            "mensaje": f"Contraindicación absoluta: el paciente refiere alergia a '{aler}' y la receta incluye un fármaco relacionado ({nombre}). No prescribir.",
                        })
                        break
    return detalles


def _evaluar_interacciones(
    nombres_receta: List[str],
    nombres_cronicos: List[str],
) -> List[Dict[str, Any]]:
    """Cruza todos los fármacos (receta + crónicos) contra INTERACCIONES_MOCK."""
    todos = list(set(nombres_receta + nombres_cronicos))
    detalles = []
    for ia in INTERACCIONES_MOCK:
        fa, fb = ia["farmacos"]
        fa_n, fb_n = _normalizar(fa), _normalizar(fb)
        match_a = any(fa_n in n or n in fa_n for n in todos)
        match_b = any(fb_n in n or n in fb_n for n in todos)
        if match_a and match_b:
            detalles.append({
                "tipo": "interaccion",
                "nivel": ia["nivel"],
                "farmacos": [fa, fb],
                "mensaje": ia["mensaje"],
            })
    return detalles


def validar_farmacovigilancia(entidades: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ejecuta el cruce contra mock. Devuelve nivel semafórico y detalles.
    entidades: { "receta_actual": [...], "tratamiento_cronico": [...], "alergias_conocidas": [...] }
    """
    receta = entidades.get("receta_actual") or []
    cronicos = entidades.get("tratamiento_cronico") or []
    alergias = entidades.get("alergias_conocidas") or []

    nombres_receta = _obtener_nombres_receta(receta)
    nombres_cronicos = _obtener_nombres_cronicos(cronicos)

    detalles_alergia = _evaluar_alergias(nombres_receta, alergias)
    detalles_interaccion = _evaluar_interacciones(nombres_receta, nombres_cronicos)

    todos_detalles = detalles_alergia + detalles_interaccion

    # Determinar nivel global: ROJO > NARANJA > VERDE
    nivel_final = "VERDE"
    mensaje_global = "Sin interacciones ni alergias detectadas con los datos disponibles. Validar con fuentes oficiales en producción."

    if any(d.get("nivel") == "ROJO" for d in todos_detalles):
        nivel_final = "ROJO"
        mensaje_global = "Contraindicación o riesgo vital detectado. Revisar detalles y no prescribir sin ajuste."
    elif any(d.get("nivel") == "NARANJA" for d in todos_detalles):
        nivel_final = "NARANJA"
        mensaje_global = "Interacción severa detectada. Requiere ajuste de dosis, monitorización o cambio de tratamiento."

    if not todos_detalles and (nombres_receta or nombres_cronicos):
        mensaje_global = "Receta y tratamiento crónico revisados. No se encontraron interacciones en la base actual. Mantener criterio clínico."

    return {
        "nivel": nivel_final,
        "mensaje": mensaje_global,
        "detalles": todos_detalles,
        "entidades_extraidas": {
            "receta_actual": receta,
            "tratamiento_cronico": cronicos,
            "alergias_conocidas": alergias,
        },
    }


def ejecutar_validacion_completa(texto: str, api_key: Optional[str]) -> Dict[str, Any]:
    """
    Flujo completo: extracción Gemini + validación dura.
    Si Gemini falla, devuelve nivel VERDE con mensaje de precaución y entidades vacías.
    Nunca lanza excepciones: siempre devuelve un dict válido.
    """
    _empty = {
        "nivel": "VERDE",
        "detalles": [],
        "entidades_extraidas": {"receta_actual": [], "tratamiento_cronico": [], "alergias_conocidas": []},
    }
    try:
        resultado_gemini = extraer_entidades_gemini(texto, api_key)
        debug_msg = resultado_gemini.get("_debug", "")
        if not resultado_gemini.get("ok"):
            _empty["mensaje"] = "No fue posible extraer entidades del texto. Revise el contenido o intente de nuevo."
            _empty["error_extraccion"] = True
            _empty["_debug"] = debug_msg
            return _empty
        resultado_gemini.pop("ok", None)
        resultado_gemini.pop("_debug", None)
        result = validar_farmacovigilancia(resultado_gemini)
        result["_debug"] = debug_msg
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        _empty["mensaje"] = f"Error interno en validación: {type(e).__name__}: {e}"
        _empty["error_interno"] = True
        return _empty
