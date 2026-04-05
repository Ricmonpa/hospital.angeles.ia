# -*- coding: utf-8 -*-
"""
Clasificaciones fiscales según legislación mexicana para el módulo del contador.
Cada clasificación tiene asociado su porcentaje de deducibilidad por defecto.
"""

# Clasificaciones para INGRESOS
CLASIFICACIONES_INGRESOS = {
    "Honorarios Médicos (Art. 100 LISR)": {
        "deducible_porcentaje": 0,  # Los ingresos no son deducibles
        "tipo": "ingreso",
        "descripcion": "Honorarios por servicios médicos profesionales"
    },
    "Otros servicios profesionales": {
        "deducible_porcentaje": 0,
        "tipo": "ingreso",
        "descripcion": "Otros servicios profesionales distintos a honorarios médicos"
    },
    "Ingresos exentos": {
        "deducible_porcentaje": 0,
        "tipo": "ingreso",
        "descripcion": "Ingresos exentos de impuestos"
    }
}

# Clasificaciones para GASTOS DEDUCIBLES
CLASIFICACIONES_GASTOS_DEDUCIBLES = {
    "Material de curación": {
        "deducible_porcentaje": 100,
        "tipo": "gasto",
        "descripcion": "Material médico y de curación necesario para la práctica profesional"
    },
    "Renta de consultorio": {
        "deducible_porcentaje": 100,
        "tipo": "gasto",
        "descripcion": "Renta del local donde se ejerce la actividad profesional"
    },
    "Servicios profesionales - Asistente": {
        "deducible_porcentaje": 100,
        "tipo": "gasto",
        "descripcion": "Servicios de asistente médico o personal de apoyo"
    },
    "Cuotas colegios médicos": {
        "deducible_porcentaje": 100,
        "tipo": "gasto",
        "descripcion": "Cuotas de colegios médicos y asociaciones profesionales"
    },
    "Depreciación equipo médico": {
        "deducible_porcentaje": 100,
        "tipo": "gasto",
        "descripcion": "Depreciación de equipos médicos e instrumentales"
    },
    "Papelería y artículos escritorio": {
        "deducible_porcentaje": 100,
        "tipo": "gasto",
        "descripcion": "Material de oficina y papelería para el consultorio"
    },
    "Teléfono e internet": {
        "deducible_porcentaje": 100,
        "tipo": "gasto",
        "descripcion": "Servicios de telefonía e internet necesarios para la actividad"
    },
    "Gasolina y peajes": {
        "deducible_porcentaje": 50,
        "tipo": "gasto",
        "descripcion": "Combustible y peajes (deducible al 50% con documentación)"
    },
    "Comidas con documentación": {
        "deducible_porcentaje": 50,
        "tipo": "gasto",
        "descripcion": "Comidas de trabajo con documentación completa (CFDI)"
    },
    "Seguros": {
        "deducible_porcentaje": 100,
        "tipo": "gasto",
        "descripcion": "Primas de seguros relacionados con la actividad profesional"
    },
    "Capacitación y congresos": {
        "deducible_porcentaje": 100,
        "tipo": "gasto",
        "descripcion": "Cursos, congresos y capacitación médica"
    },
    "Publicidad": {
        "deducible_porcentaje": 100,
        "tipo": "gasto",
        "descripcion": "Gastos de publicidad y promoción del consultorio"
    }
}

# Clasificaciones para GASTOS NO DEDUCIBLES
CLASIFICACIONES_GASTOS_NO_DEDUCIBLES = {
    "Gastos personales": {
        "deducible_porcentaje": 0,
        "tipo": "gasto",
        "descripcion": "Gastos de carácter personal no relacionados con la actividad profesional"
    },
    "Gastos sin CFDI": {
        "deducible_porcentaje": 0,
        "tipo": "gasto",
        "descripcion": "Gastos que no cuentan con Comprobante Fiscal Digital"
    },
    "Multas y recargos": {
        "deducible_porcentaje": 0,
        "tipo": "gasto",
        "descripcion": "Multas, recargos y sanciones fiscales"
    },
    "Ropa personal": {
        "deducible_porcentaje": 0,
        "tipo": "gasto",
        "descripcion": "Vestimenta personal no relacionada con la actividad profesional"
    }
}

# Diccionario unificado para búsqueda rápida
TODAS_CLASIFICACIONES = {
    **CLASIFICACIONES_INGRESOS,
    **CLASIFICACIONES_GASTOS_DEDUCIBLES,
    **CLASIFICACIONES_GASTOS_NO_DEDUCIBLES
}

def obtener_clasificaciones_por_tipo(tipo: str) -> dict:
    """
    Obtiene las clasificaciones disponibles para un tipo de transacción.
    
    Args:
        tipo: 'ingreso' o 'gasto'
    
    Returns:
        Diccionario con clasificaciones disponibles
    """
    if tipo == "ingreso":
        return CLASIFICACIONES_INGRESOS
    elif tipo == "gasto":
        return {**CLASIFICACIONES_GASTOS_DEDUCIBLES, **CLASIFICACIONES_GASTOS_NO_DEDUCIBLES}
    else:
        return {}

def obtener_porcentaje_deducible(clasificacion: str) -> int:
    """
    Obtiene el porcentaje de deducibilidad por defecto para una clasificación.
    
    Args:
        clasificacion: Nombre de la clasificación
    
    Returns:
        Porcentaje de deducibilidad (0-100)
    """
    clasif_data = TODAS_CLASIFICACIONES.get(clasificacion)
    if clasif_data:
        return clasif_data.get("deducible_porcentaje", 0)
    return 0

def obtener_lista_clasificaciones_por_tipo(tipo: str) -> list:
    """
    Obtiene una lista de nombres de clasificaciones para un tipo.
    Útil para dropdowns en el frontend.
    
    Args:
        tipo: 'ingreso' o 'gasto'
    
    Returns:
        Lista de nombres de clasificaciones
    """
    clasificaciones = obtener_clasificaciones_por_tipo(tipo)
    return list(clasificaciones.keys())

def validar_clasificacion(clasificacion: str, tipo: str) -> bool:
    """
    Valida que una clasificación sea válida para el tipo de transacción.
    
    Args:
        clasificacion: Nombre de la clasificación
        tipo: 'ingreso' o 'gasto'
    
    Returns:
        True si la clasificación es válida para el tipo
    """
    clasificaciones = obtener_clasificaciones_por_tipo(tipo)
    return clasificacion in clasificaciones

