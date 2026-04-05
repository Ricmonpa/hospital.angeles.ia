# -*- coding: utf-8 -*-
"""
Motor RAG (Retrieval Augmented Generation) para búsqueda en tabuladores médicos
Usa Gemini para buscar información en documentos PDF de tabuladores de seguros
"""

import os
import json
from typing import Dict, Optional, List
import requests

def buscar_honorario_en_tabulador(
    aseguradora: str,
    plan_nombre: str,
    procedimiento: str,
    codigo_cpt: str = None,
    tabulador_id: int = None,
    contenido_tabulador: str = None,
    api_key: str = None
) -> Dict:
    """
    Busca el honorario de un procedimiento en un tabulador usando RAG con Gemini
    
    Args:
        aseguradora: Nombre de la aseguradora
        plan_nombre: Nombre del plan
        procedimiento: Nombre del procedimiento (ej: "Apendicectomía laparoscópica")
        codigo_cpt: Código CPT del procedimiento (opcional)
        tabulador_id: ID del tabulador en BD (opcional)
        contenido_tabulador: Texto extraído del PDF del tabulador (opcional)
        api_key: Clave API de Gemini
    
    Returns:
        Dict con:
        {
            'monto': float,
            'codigo_cpt': str,
            'descripcion': str,
            'fuente': str,
            'confianza': str
        }
    """
    
    if not api_key:
        return {
            'error': 'API key no proporcionada',
            'monto': None
        }
    
    # Si no hay contenido de tabulador, usar prompt genérico
    if not contenido_tabulador:
        contenido_tabulador = f"Tabulador de {aseguradora} para plan {plan_nombre}"
    
    prompt = f"""Eres un experto en seguros médicos mexicanos. Busca en el siguiente tabulador de honorarios médicos la información del procedimiento solicitado.

ASEGURADORA: {aseguradora}
PLAN: {plan_nombre}
PROCEDIMIENTO SOLICITADO: {procedimiento}
{f"CODIGO CPT: {codigo_cpt}" if codigo_cpt else ""}

CONTENIDO DEL TABULADOR:
{contenido_tabulador[:5000]}  # Limitar a 5000 caracteres para no exceder tokens

INSTRUCCIONES:
1. Busca el procedimiento "{procedimiento}" en el tabulador
2. Si hay código CPT {codigo_cpt if codigo_cpt else "(búscalo también)"}, úsalo para buscar de forma más precisa
3. Extrae el MONTO que paga la aseguradora por este procedimiento
4. Si no encuentras el procedimiento exacto, busca uno similar
5. Responde SOLO en formato JSON válido

Responde en formato JSON:
{{
  "monto": numero_o_null,
  "codigo_cpt": "codigo o null",
  "descripcion": "descripcion del procedimiento encontrado",
  "moneda": "MXN",
  "confianza": "alta/media/baja",
  "notas": "notas adicionales si aplica"
}}

IMPORTANTE: 
- Si NO encuentras el procedimiento, responde con monto: null y confianza: "baja"
- El monto debe ser un número (sin símbolos de peso)
- Si encuentras información similar, indícalo en notas
"""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    headers = {
        'Content-Type': 'application/json',
    }
    
    data = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "response_mime_type": "application/json"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                texto_respuesta = result['candidates'][0]['content']['parts'][0]['text']
                
                # Limpiar respuesta
                texto_respuesta = texto_respuesta.strip()
                if texto_respuesta.startswith('```json'):
                    texto_respuesta = texto_respuesta[7:]
                if texto_respuesta.endswith('```'):
                    texto_respuesta = texto_respuesta[:-3]
                texto_respuesta = texto_respuesta.strip()
                
                datos = json.loads(texto_respuesta)
                
                return {
                    'monto': datos.get('monto'),
                    'codigo_cpt': datos.get('codigo_cpt') or codigo_cpt,
                    'descripcion': datos.get('descripcion', procedimiento),
                    'moneda': datos.get('moneda', 'MXN'),
                    'confianza': datos.get('confianza', 'media'),
                    'notas': datos.get('notas', ''),
                    'fuente': f"{aseguradora} - {plan_nombre}"
                }
        else:
            print(f"Error en búsqueda RAG: {response.status_code} - {response.text}")
            return {
                'error': f"Error en API: {response.status_code}",
                'monto': None
            }
            
    except Exception as e:
        print(f"Error en búsqueda RAG: {e}")
        import traceback
        traceback.print_exc()
        return {
            'error': str(e),
            'monto': None
        }

def consultar_cobertura_procedimiento(
    aseguradora: str,
    plan_nombre: str,
    procedimiento: str,
    contenido_condiciones: str = None,
    api_key: str = None
) -> Dict:
    """
    Consulta si un procedimiento está cubierto por el seguro usando las condiciones generales
    
    Args:
        aseguradora: Nombre de la aseguradora
        plan_nombre: Nombre del plan
        procedimiento: Nombre del procedimiento
        contenido_condiciones: Texto de condiciones generales (opcional)
        api_key: Clave API de Gemini
    
    Returns:
        Dict con:
        {
            'cubierto': bool,
            'requisitos': str,
            'periodo_espera': str,
            'exclusiones': str,
            'confianza': str
        }
    """
    
    if not api_key:
        return {
            'error': 'API key no proporcionada',
            'cubierto': None
        }
    
    if not contenido_condiciones:
        contenido_condiciones = f"Condiciones generales de {aseguradora} para plan {plan_nombre}"
    
    prompt = f"""Eres un experto en seguros médicos mexicanos. Analiza las condiciones generales del seguro para determinar si el procedimiento está cubierto.

ASEGURADORA: {aseguradora}
PLAN: {plan_nombre}
PROCEDIMIENTO: {procedimiento}

CONDICIONES GENERALES:
{contenido_condiciones[:5000]}

INSTRUCCIONES:
1. Determina si el procedimiento "{procedimiento}" está cubierto por este seguro
2. Si está cubierto, indica si hay requisitos especiales (periodo de espera, autorización previa, etc.)
3. Si NO está cubierto, indica las razones o exclusiones
4. Responde SOLO en formato JSON válido

Responde en formato JSON:
{{
  "cubierto": true_o_false,
  "requisitos": "texto de requisitos si aplica",
  "periodo_espera": "periodo de espera si aplica (ej: '2 años')",
  "exclusiones": "exclusiones si no está cubierto",
  "confianza": "alta/media/baja"
}}
"""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    headers = {
        'Content-Type': 'application/json',
    }
    
    data = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "response_mime_type": "application/json"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                texto_respuesta = result['candidates'][0]['content']['parts'][0]['text']
                
                # Limpiar respuesta
                texto_respuesta = texto_respuesta.strip()
                if texto_respuesta.startswith('```json'):
                    texto_respuesta = texto_respuesta[7:]
                if texto_respuesta.endswith('```'):
                    texto_respuesta = texto_respuesta[:-3]
                texto_respuesta = texto_respuesta.strip()
                
                datos = json.loads(texto_respuesta)
                
                return {
                    'cubierto': datos.get('cubierto', False),
                    'requisitos': datos.get('requisitos', ''),
                    'periodo_espera': datos.get('periodo_espera', ''),
                    'exclusiones': datos.get('exclusiones', ''),
                    'confianza': datos.get('confianza', 'media')
                }
        else:
            print(f"Error en consulta de cobertura: {response.status_code} - {response.text}")
            return {
                'error': f"Error en API: {response.status_code}",
                'cubierto': None
            }
            
    except Exception as e:
        print(f"Error en consulta de cobertura: {e}")
        import traceback
        traceback.print_exc()
        return {
            'error': str(e),
            'cubierto': None
        }

