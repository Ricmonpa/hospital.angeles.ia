# -*- coding: utf-8 -*-
"""
Formas de pago válidas según el SAT (México).
Catálogo de formas de pago para CFDI.
"""

FORMAS_PAGO_SAT = {
    "01": {
        "codigo": "01",
        "descripcion": "Efectivo",
        "es_efectivo": True
    },
    "02": {
        "codigo": "02",
        "descripcion": "Cheque nominativo",
        "es_efectivo": False
    },
    "03": {
        "codigo": "03",
        "descripcion": "Transferencia electrónica",
        "es_efectivo": False
    },
    "04": {
        "codigo": "04",
        "descripcion": "Tarjeta de crédito",
        "es_efectivo": False
    },
    "28": {
        "codigo": "28",
        "descripcion": "Tarjeta de débito",
        "es_efectivo": False
    },
    "99": {
        "codigo": "99",
        "descripcion": "Por definir",
        "es_efectivo": False
    }
}

def obtener_formas_pago() -> list:
    """
    Obtiene lista de formas de pago para dropdowns.
    
    Returns:
        Lista de tuplas (codigo_descripcion, codigo)
    """
    return [
        f"{codigo} - {datos['descripcion']}"
        for codigo, datos in FORMAS_PAGO_SAT.items()
    ]

def obtener_codigo_forma_pago(forma_pago_str: str) -> str:
    """
    Extrae el código de una forma de pago en formato "01 - Efectivo".
    
    Args:
        forma_pago_str: String con formato "CODIGO - DESCRIPCION"
    
    Returns:
        Código de la forma de pago (ej: "01")
    """
    if not forma_pago_str:
        return ""
    partes = forma_pago_str.split(" - ")
    return partes[0] if partes else ""

def es_efectivo(forma_pago_str: str) -> bool:
    """
    Verifica si una forma de pago es efectivo.
    
    Args:
        forma_pago_str: String con formato "CODIGO - DESCRIPCION" o solo código
    
    Returns:
        True si es efectivo
    """
    codigo = obtener_codigo_forma_pago(forma_pago_str)
    if codigo in FORMAS_PAGO_SAT:
        return FORMAS_PAGO_SAT[codigo]["es_efectivo"]
    return False

def validar_forma_pago(forma_pago_str: str) -> bool:
    """
    Valida que una forma de pago sea válida según el SAT.
    
    Args:
        forma_pago_str: String con formato "CODIGO - DESCRIPCION" o solo código
    
    Returns:
        True si es válida
    """
    codigo = obtener_codigo_forma_pago(forma_pago_str)
    return codigo in FORMAS_PAGO_SAT

def validar_deducibilidad_efectivo(monto: float, forma_pago: str) -> dict:
    """
    Valida si un gasto en efectivo es deducible.
    Según la ley, gastos en efectivo mayores a $2,000 NO son deducibles.
    
    Args:
        monto: Monto de la transacción
        forma_pago: Forma de pago
    
    Returns:
        Dict con 'es_deducible' (bool) y 'mensaje' (str)
    """
    if not es_efectivo(forma_pago):
        return {
            "es_deducible": True,
            "mensaje": "",
            "warning": False
        }
    
    if monto > 2000:
        return {
            "es_deducible": False,
            "mensaje": "⚠️ Gastos en efectivo mayores a $2,000 no son deducibles según la legislación fiscal mexicana.",
            "warning": True
        }
    
    return {
        "es_deducible": True,
        "mensaje": "",
        "warning": False
    }

