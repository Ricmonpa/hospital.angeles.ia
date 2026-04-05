# -*- coding: utf-8 -*-
"""
Procesamiento de PDFs de tabuladores médicos
Extracción de texto y procesamiento de tabuladores de seguros
"""

import os
import hashlib
from typing import Dict, Optional, List
import pdfplumber
from datetime import datetime

def extraer_texto_pdf(pdf_bytes: bytes) -> Dict:
    """
    Extrae texto de un PDF de tabulador médico
    
    Args:
        pdf_bytes: Bytes del archivo PDF
    
    Returns:
        Dict con:
        {
            'texto': str,
            'num_paginas': int,
            'error': str (si hay error)
        }
    """
    
    try:
        # Guardar temporalmente para pdfplumber
        import tempfile
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(pdf_bytes)
            temp_path = temp_file.name
        
        try:
            texto_completo = []
            num_paginas = 0
            
            with pdfplumber.open(temp_path) as pdf:
                num_paginas = len(pdf.pages)
                
                for i, page in enumerate(pdf.pages):
                    texto_pagina = page.extract_text()
                    if texto_pagina:
                        texto_completo.append(f"--- PÁGINA {i+1} ---\n{texto_pagina}\n")
            
            texto_final = "\n".join(texto_completo)
            
            # Limpiar archivo temporal
            os.unlink(temp_path)
            
            return {
                'texto': texto_final,
                'num_paginas': num_paginas,
                'error': None
            }
            
        except Exception as e:
            # Limpiar archivo temporal en caso de error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e
            
    except Exception as e:
        return {
            'texto': '',
            'num_paginas': 0,
            'error': f"Error al extraer texto del PDF: {str(e)}"
        }

def calcular_hash_pdf(pdf_bytes: bytes) -> str:
    """
    Calcula hash SHA256 de un PDF para detectar duplicados
    
    Args:
        pdf_bytes: Bytes del archivo PDF
    
    Returns:
        Hash SHA256 en hexadecimal
    """
    return hashlib.sha256(pdf_bytes).hexdigest()

def detectar_aseguradora_del_texto(texto: str) -> Optional[str]:
    """
    Intenta detectar la aseguradora del texto del PDF
    
    Args:
        texto: Texto extraído del PDF
    
    Returns:
        Nombre de la aseguradora detectada o None
    """
    texto_lower = texto.lower()
    
    # Mapeo de palabras clave a aseguradoras
    detectores = {
        'gnp': ['gnp', 'grupo nacional provincial'],
        'axa': ['axa', 'axa seguros'],
        'monterrey': ['seguros monterrey', 'monterrey', 'seguro monterrey'],
        'metlife': ['metlife', 'met life', 'met life méxico'],
        'banorte': ['banorte seguros', 'seguros banorte'],
        'qualitas': ['qualitas', 'qualitas compaña'],
        'plan': ['plan seguros', 'plan seguros de méxico'],
        'mapfre': ['mapfre'],
        'zurich': ['zurich']
    }
    
    for aseguradora, palabras_clave in detectores.items():
        for palabra in palabras_clave:
            if palabra in texto_lower:
                # Normalizar nombre
                mapeo_nombres = {
                    'gnp': 'GNP',
                    'axa': 'AXA',
                    'monterrey': 'Seguros Monterrey',
                    'metlife': 'MetLife',
                    'banorte': 'Banorte',
                    'qualitas': 'Qualitas',
                    'plan': 'Plan Seguros',
                    'mapfre': 'Mapfre',
                    'zurich': 'Zurich'
                }
                return mapeo_nombres.get(aseguradora, aseguradora.title())
    
    return None

def detectar_tipo_documento(texto: str) -> str:
    """
    Detecta si el documento es un tabulador o condiciones generales
    
    Args:
        texto: Texto extraído del PDF
    
    Returns:
        'tabulador' o 'condiciones_generales'
    """
    texto_lower = texto.lower()
    
    # Palabras clave para tabulador
    keywords_tabulador = [
        'tabulador', 'honorarios', 'honorario médico', 'cpt', 'procedimiento',
        'código', 'tarifa', 'precio', 'costo', 'monto', '$', 'pesos'
    ]
    
    # Palabras clave para condiciones generales
    keywords_condiciones = [
        'condiciones generales', 'términos y condiciones', 'cobertura',
        'exclusiones', 'periodo de espera', 'deducible', 'coaseguro',
        'vigencia', 'póliza', 'poliza', 'cláusula'
    ]
    
    count_tabulador = sum(1 for kw in keywords_tabulador if kw in texto_lower)
    count_condiciones = sum(1 for kw in keywords_condiciones if kw in texto_lower)
    
    if count_tabulador > count_condiciones:
        return 'tabulador'
    else:
        return 'condiciones_generales'

def extraer_plan_del_texto(texto: str) -> Optional[str]:
    """
    Intenta extraer el nombre del plan del texto del PDF
    
    Args:
        texto: Texto extraído del PDF
    
    Returns:
        Nombre del plan o None
    """
    texto_lower = texto.lower()
    
    # Buscar patrones comunes de planes
    planes_comunes = [
        'línea azul', 'línea azul premium', 'plan alfa', 'plan beta',
        'plan dorado', 'plan plata', 'plan oro', 'plan premium',
        'plan básico', 'plan estándar', 'plan plus'
    ]
    
    for plan in planes_comunes:
        if plan in texto_lower:
            return plan.title()
    
    # Buscar después de palabras clave
    keywords_plan = ['plan:', 'plan ', 'producto:', 'línea:']
    for keyword in keywords_plan:
        idx = texto_lower.find(keyword)
        if idx != -1:
            # Extraer siguiente palabra(s)
            inicio = idx + len(keyword)
            fin = min(inicio + 50, len(texto))
            posible_plan = texto[inicio:fin].strip().split('\n')[0].split()[0:3]
            if posible_plan:
                return ' '.join(posible_plan).title()
    
    return None

def extraer_fecha_vigencia(texto: str) -> Optional[str]:
    """
    Intenta extraer fecha de vigencia del texto del PDF
    
    Args:
        texto: Texto extraído del PDF
    
    Returns:
        Fecha en formato YYYY-MM-DD o None
    """
    import re
    from datetime import datetime
    
    # Buscar patrones de fecha
    patrones_fecha = [
        r'vigencia[:\s]+(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})',
        r'vigente[:\s]+(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})',
        r'válido[:\s]+(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})',
        r'año[:\s]+(\d{4})',
        r'(\d{4})[:\s]+vigencia'
    ]
    
    for patron in patrones_fecha:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            grupos = match.groups()
            if len(grupos) == 3:  # DD/MM/YYYY
                try:
                    dia, mes, año = grupos
                    fecha = datetime(int(año), int(mes), int(dia))
                    return fecha.strftime('%Y-%m-%d')
                except:
                    pass
            elif len(grupos) == 1:  # Solo año
                try:
                    año = grupos[0]
                    return f"{año}-01-01"  # Asumir inicio de año
                except:
                    pass
    
    return None

def procesar_tabulador_pdf(pdf_bytes: bytes, nombre_archivo: str) -> Dict:
    """
    Procesa un PDF de tabulador completo
    
    Args:
        pdf_bytes: Bytes del archivo PDF
        nombre_archivo: Nombre original del archivo
    
    Returns:
        Dict con información extraída:
        {
            'texto': str,
            'num_paginas': int,
            'hash': str,
            'aseguradora': str o None,
            'tipo_documento': str,
            'plan': str o None,
            'fecha_vigencia': str o None,
            'error': str o None
        }
    """
    
    # Extraer texto
    resultado_extraccion = extraer_texto_pdf(pdf_bytes)
    
    if resultado_extraccion['error']:
        return {
            'error': resultado_extraccion['error'],
            'texto': '',
            'num_paginas': 0
        }
    
    texto = resultado_extraccion['texto']
    
    # Calcular hash
    hash_pdf = calcular_hash_pdf(pdf_bytes)
    
    # Detectar información
    aseguradora = detectar_aseguradora_del_texto(texto)
    tipo_documento = detectar_tipo_documento(texto)
    plan = extraer_plan_del_texto(texto)
    fecha_vigencia = extraer_fecha_vigencia(texto)
    
    return {
        'texto': texto,
        'num_paginas': resultado_extraccion['num_paginas'],
        'hash': hash_pdf,
        'aseguradora': aseguradora,
        'tipo_documento': tipo_documento,
        'plan': plan,
        'fecha_vigencia': fecha_vigencia,
        'nombre_archivo': nombre_archivo,
        'error': None
    }

