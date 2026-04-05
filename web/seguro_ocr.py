# -*- coding: utf-8 -*-
"""
Módulo de procesamiento OCR para credenciales de seguro médico
Usa Gemini Vision API para extraer información de imágenes de credenciales
"""

import os
import base64
import requests
from typing import Dict, Optional
from PIL import Image
import io

def extraer_datos_credencial_imagen(imagen_bytes: bytes, api_key: str) -> Dict:
    """
    Extrae datos de una credencial de seguro usando Gemini Vision API
    
    Args:
        imagen_bytes: Bytes de la imagen de la credencial
        api_key: Clave API de Gemini
    
    Returns:
        Dict con los datos extraídos:
        {
            'aseguradora': str,
            'numero_poliza': str,
            'plan_nombre': str,
            'nivel_hospitalario': str,
            'paciente_nombre': str,
            'vigencia': str,
            'datos_adicionales': dict
        }
    """
    
    # Convertir imagen a base64
    imagen_base64 = base64.b64encode(imagen_bytes).decode('utf-8')
    
    # Detectar tipo MIME
    try:
        imagen_pil = Image.open(io.BytesIO(imagen_bytes))
        mime_type = f"image/{imagen_pil.format.lower()}" if imagen_pil.format else "image/jpeg"
    except:
        mime_type = "image/jpeg"
    
    prompt = """Analiza esta credencial de seguro médico mexicano y extrae la siguiente información en formato JSON:

1. aseguradora: Nombre de la compañía aseguradora (ej: GNP, AXA, Seguros Monterrey, MetLife, Banorte)
2. numero_poliza: Número de póliza o de afiliación
3. plan_nombre: Nombre del plan (ej: "Línea Azul Premium", "Plan Alfa", "Plan Dorado")
4. nivel_hospitalario: Nivel de atención hospitalario si está visible (ej: Nivel 1, Nivel 2, Nivel 3, Clínica, Hospital)
5. paciente_nombre: Nombre completo del paciente si está visible
6. vigencia: Fecha de vigencia si está visible
7. datos_adicionales: Cualquier otro dato relevante como número de tarjeta, clave de beneficiario, etc.

IMPORTANTE: 
- Responde SOLO en formato JSON válido
- Si algún campo no está visible o no puedes identificarlo, usa null
- Para aseguradora, usa nombres estándar: GNP, AXA, Seguros Monterrey (o Monterrey), MetLife, Banorte
- Para plan_nombre, extrae el nombre exacto del plan como aparece

Formato de respuesta:
{
  "aseguradora": "nombre",
  "numero_poliza": "numero",
  "plan_nombre": "plan",
  "nivel_hospitalario": "nivel o null",
  "paciente_nombre": "nombre o null",
  "vigencia": "fecha o null",
  "datos_adicionales": {}
}"""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    headers = {
        'Content-Type': 'application/json',
    }
    
    data = {
        "contents": [{
            "parts": [
                {
                    "text": prompt
                },
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": imagen_base64
                    }
                }
            ]
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
                
                # Limpiar respuesta (puede venir con markdown)
                texto_respuesta = texto_respuesta.strip()
                if texto_respuesta.startswith('```json'):
                    texto_respuesta = texto_respuesta[7:]
                if texto_respuesta.endswith('```'):
                    texto_respuesta = texto_respuesta[:-3]
                texto_respuesta = texto_respuesta.strip()
                
                import json
                datos = json.loads(texto_respuesta)
                
                # Normalizar nombres de aseguradoras
                aseguradora = datos.get('aseguradora', '')
                if aseguradora:
                    aseguradora = normalizar_nombre_aseguradora(aseguradora)
                    datos['aseguradora'] = aseguradora
                
                return datos
        else:
            print(f"Error en OCR de credencial: {response.status_code} - {response.text}")
            return {}
            
    except Exception as e:
        print(f"Error procesando credencial con OCR: {e}")
        import traceback
        traceback.print_exc()
        return {}

def normalizar_nombre_aseguradora(nombre: str) -> str:
    """
    Normaliza el nombre de una aseguradora a nombres estándar
    """
    nombre_lower = nombre.lower().strip()
    
    # Mapeo de variantes a nombres estándar
    mapeo = {
        'gnp': 'GNP',
        'axa': 'AXA',
        'metlife': 'MetLife',
        'met life': 'MetLife',
        'monterrey': 'Seguros Monterrey',
        'seguros monterrey': 'Seguros Monterrey',
        'seguro monterrey': 'Seguros Monterrey',
        'banorte': 'Banorte',
        'seguros banorte': 'Banorte',
        'qualitas': 'Qualitas',
        'plan seguros': 'Plan Seguros',
        'plan seguros de méxico': 'Plan Seguros',
        'mapfre': 'Mapfre',
        'zurich': 'Zurich'
    }
    
    # Buscar coincidencia exacta o parcial
    for variante, estandar in mapeo.items():
        if variante in nombre_lower:
            return estandar
    
    # Si no hay match, capitalizar primera letra de cada palabra
    return nombre.title()

def consultar_info_plan(aseguradora: str, plan_nombre: str) -> Dict:
    """
    Consulta información estimada de un plan de seguro (deducible, coaseguro, hospitales)
    Basado en conocimiento pre-cargado de tabuladores
    
    Esta función puede ser mejorada cuando se carguen tabuladores reales
    """
    
    # Datos de ejemplo/predefinidos para las principales aseguradoras
    # En producción, esto vendría de la base de datos de tabuladores
    planes_estimados = {
        'GNP': {
            'Línea Azul': {
                'deducible_estimado': 25000,
                'coaseguro_porcentaje': 10,
                'hospitales_red': 'Hospital Ángeles, Médica Sur, Hospital ABC'
            },
            'Línea Azul Premium': {
                'deducible_estimado': 15000,
                'coaseguro_porcentaje': 10,
                'hospitales_red': 'Hospital Ángeles, Médica Sur, Hospital ABC, Star Médica'
            },
            'default': {
                'deducible_estimado': 30000,
                'coaseguro_porcentaje': 10,
                'hospitales_red': 'Hospital Ángeles, Médica Sur'
            }
        },
        'AXA': {
            'default': {
                'deducible_estimado': 20000,
                'coaseguro_porcentaje': 10,
                'hospitales_red': 'Hospital Ángeles, Médica Sur'
            }
        },
        'Seguros Monterrey': {
            'Plan Alfa': {
                'deducible_estimado': 25000,
                'coaseguro_porcentaje': 10,
                'hospitales_red': 'Hospital Ángeles, Médica Sur, Hospital Christus Muguerza'
            },
            'default': {
                'deducible_estimado': 30000,
                'coaseguro_porcentaje': 10,
                'hospitales_red': 'Hospital Ángeles, Médica Sur'
            }
        },
        'MetLife': {
            'default': {
                'deducible_estimado': 25000,
                'coaseguro_porcentaje': 15,
                'hospitales_red': 'Hospital Ángeles, Médica Sur'
            }
        },
        'Banorte': {
            'default': {
                'deducible_estimado': 30000,
                'coaseguro_porcentaje': 10,
                'hospitales_red': 'Hospital Ángeles, Médica Sur'
            }
        }
    }
    
    # Buscar información del plan
    if aseguradora in planes_estimados:
        planes_aseguradora = planes_estimados[aseguradora]
        
        # Buscar plan específico
        if plan_nombre and plan_nombre in planes_aseguradora:
            return planes_aseguradora[plan_nombre]
        
        # Usar default de la aseguradora
        if 'default' in planes_aseguradora:
            return planes_aseguradora['default']
    
    # Default genérico
    return {
        'deducible_estimado': 30000,
        'coaseguro_porcentaje': 10,
        'hospitales_red': 'Hospital Ángeles, Médica Sur'
    }

