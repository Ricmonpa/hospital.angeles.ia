# Progreso de desarrollo: Módulo Farmacovigilancia (DDI)

**Última actualización:** 2026-03-12  
**Commit actual:** `6c70e5e` en `main`  
**Deploy:** Railway auto-deploy → https://web-production-5ca44.up.railway.app  
**Repo:** https://github.com/Ricmonpa/chinoin-ai-consultorio.git

---

## Estado actual: DEBUG en progreso

La UI y el endpoint funcionan. El bug principal (KeyError por llaves `{}` sin escapar en el prompt `.format()`) ya se corrigió. Pero **Gemini no está devolviendo entidades**: el response dice `error_extraccion: true`.

### Lo que SÍ funciona
- `GET /farmacovigilancia` → sirve `templates/farmacovigilancia.html` correctamente.
- `POST /api/validar_farmacovigilancia` → ya no devuelve 500; devuelve 200 con JSON.
- El mock de interacciones/alergias en `farmacovigilancia.py` está listo y probado conceptualmente.
- Navegación actualizada en dashboard, transcripcion, historial.

### Lo que falta resolver
- **`extraer_entidades_gemini()` devuelve que no pudo extraer entidades.** Posibles causas:
  1. La GEMINI_API_KEY en Railway podría estar expirada o tener cuota agotada.
  2. Gemini podría estar bloqueando el prompt (promptFeedback/safety).
  3. Algún otro issue de respuesta.
- **El último commit (`6c70e5e`) agrega un campo `_debug` al JSON de respuesta** que muestra exactamente por qué falló. Al hacer POST, revisar el campo `_debug` en la respuesta JSON (visible en DevTools > Network > Response).

### Cómo diagnosticar
1. Entrar a https://web-production-5ca44.up.railway.app/farmacovigilancia
2. Pegar el caso de prueba y pulsar "Validar farmacovigilancia"
3. En DevTools (F12 > Network), click en la request POST, ver "Response"
4. Buscar el campo `"_debug"` — ahí dice exactamente qué pasó:
   - `"GEMINI_API_KEY no configurada"` → falta la variable en Railway
   - `"Gemini HTTP 4xx: ..."` → key inválida, cuota, etc.
   - `"Sin candidates. promptFeedback=..."` → Gemini bloqueó el prompt (safety)
   - `"ok"` → extracción exitosa (el problema estaría en el cruce)

### Cómo corregir según diagnóstico
- **Key inválida/expirada:** regenerar en https://makersuite.google.com/app/apikey y actualizar la variable `GEMINI_API_KEY` en Railway.
- **Safety block:** ajustar `safetySettings` en el payload de Gemini (agregar `BLOCK_NONE` para categorías médicas).
- **Si `_debug` dice "ok" pero no hay detalles:** revisar lógica de cruce en `_evaluar_alergias` y `_evaluar_interacciones`.

### Una vez que Gemini funcione
- Quitar el campo `_debug` del response (dejar solo para logs de servidor).
- El flujo completo es: texto → Gemini extrae JSON → cruce Python vs mock → semáforo ROJO/NARANJA/VERDE.

---

## Archivos clave del módulo

| Archivo | Propósito |
|---------|-----------|
| `farmacovigilancia.py` | Mock DB (interacciones, alergias), extracción Gemini, lógica de cruce, semáforo |
| `templates/farmacovigilancia.html` | UI: textarea, botón, resultado semáforo, detalles, entidades |
| `main.py` (líneas ~215 y ~730) | Ruta `GET /farmacovigilancia` y endpoint `POST /api/validar_farmacovigilancia` |

## Historial de commits del módulo

```
6c70e5e  debug: devolver _debug en response para diagnosticar fallo Gemini
1177f4e  fix: restaurar return None en check de api_key
34c4c46  fix: escapar llaves JSON en prompt template para .format()  ← bug principal
0936d6f  debug: agregar traceback al error para diagnostico
4be4812  fix: blindar extraccion Gemini contra respuestas inesperadas
fd2033d  feat: Módulo Farmacovigilancia (DDI) — API, mock, front y resumen técnico
```

## Casos de prueba

### Caso 1 — ROJO (alergia sulfas + warfarina + ibuprofeno)
```
Paciente masculino de 58 años con fibrilación auricular en tratamiento crónico con warfarina 5 mg VO cada noche.
Alergia documentada a sulfas.
Se prescribe: Bactrim 800/160 mg VO cada 12h por 7 días, ibuprofeno 400 mg VO cada 8h.
```
Esperado: ROJO (alergia sulfas→Bactrim) + NARANJA (warfarina+ibuprofeno).

### Caso 2 — NARANJA (metformina + contraste yodado)
```
Paciente con diabetes tipo 2, tratamiento crónico metformina 850 mg. Se programa tomografía con contraste yodado IV.
```

### Caso 3 — VERDE
```
Paciente sin alergias ni tratamiento crónico. Se prescribe paracetamol 500 mg cada 6h.
```
