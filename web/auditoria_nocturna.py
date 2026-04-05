#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Auditoría Nocturna - Asistente Legal
Ejecuta auditoría automática de cumplimiento legal cruzando consultas vs documentos firmados.

Uso:
    python auditoria_nocturna.py
    
O configurar como cron job para ejecutar diariamente:
    0 2 * * * /usr/bin/python3 /ruta/a/auditoria_nocturna.py
"""

import os
import sys
from datetime import datetime
from database import ConsultaDB, LegalDB

def ejecutar_auditoria_nocturna():
    """Ejecuta la auditoría de cumplimiento legal"""
    print(f"[{datetime.now()}] Iniciando auditoría nocturna de cumplimiento legal...")
    
    # Inicializar bases de datos
    db = ConsultaDB()
    legal_db = LegalDB()
    
    medico_id = 'default'  # En producción, iterar sobre todos los médicos
    
    try:
        # Obtener consultas recientes (últimos 30 días)
        consultas = db.obtener_consultas(medico_id=medico_id, limite=1000)
        print(f"[INFO] Revisando {len(consultas)} consultas...")
        
        # Obtener documentos firmados
        documentos = legal_db.obtener_documentos_firmados(medico_id=medico_id, limite=1000)
        print(f"[INFO] Encontrados {len(documentos)} documentos firmados...")
        
        # Crear mapa de consultas con consentimiento
        consultas_con_consentimiento = set()
        for doc in documentos:
            if doc.get('consulta_id') and doc.get('tipo_documento') == 'consentimiento_informado':
                consultas_con_consentimiento.add(doc['consulta_id'])
        
        print(f"[INFO] {len(consultas_con_consentimiento)} consultas tienen consentimiento firmado")
        
        # Identificar consultas sin consentimiento
        alertas_creadas = 0
        procedimientos_requieren_consentimiento = [
            'cirugía', 'biopsia', 'endoscopia', 'colonoscopia', 
            'operación', 'intervención', 'quirúrgico', 'anestesia',
            'procedimiento invasivo', 'extracción', 'inyección'
        ]
        
        for consulta in consultas:
            consulta_id = consulta.get('id')
            diagnostico = consulta.get('diagnostico', '').lower()
            tratamiento = consulta.get('tratamiento', '').lower()
            transcripcion = consulta.get('transcripcion', '').lower()
            
            # Verificar si requiere consentimiento
            requiere_consentimiento = any(
                proc in diagnostico or proc in tratamiento or proc in transcripcion 
                for proc in procedimientos_requieren_consentimiento
            )
            
            if requiere_consentimiento and consulta_id not in consultas_con_consentimiento:
                # Verificar si ya existe una alerta para esta consulta
                alertas_existentes = legal_db.obtener_alertas_legales(
                    medico_id=medico_id, 
                    estado='activa', 
                    limite=1000
                )
                ya_existe = any(
                    a.get('entidad_id') == consulta_id and a.get('estado') == 'activa' 
                    for a in alertas_existentes
                )
                
                if not ya_existe:
                    legal_db.crear_alerta_legal({
                        'medico_id': medico_id,
                        'tipo_alerta': 'consentimiento_faltante',
                        'severidad': 'alta',
                        'titulo': f'Consentimiento faltante para consulta #{consulta_id}',
                        'descripcion': f'La consulta del {consulta.get("fecha_consulta", "")} requiere consentimiento informado pero no se encontró documento firmado. Procedimiento detectado: {diagnostico[:50]}...',
                        'entidad_tipo': 'consulta',
                        'entidad_id': consulta_id
                    })
                    alertas_creadas += 1
                    print(f"[ALERTA] Creada alerta para consulta #{consulta_id}")
        
        # Verificar contratos por vencer
        contratos_vencer = legal_db.obtener_contratos_por_vencer(medico_id=medico_id, dias=30)
        for contrato in contratos_vencer:
            dias_restantes = int(contrato.get('dias_restantes', 0))
            
            # Verificar si ya existe alerta
            alertas_existentes = legal_db.obtener_alertas_legales(
                medico_id=medico_id, 
                estado='activa', 
                limite=1000
            )
            ya_existe = any(
                a.get('entidad_id') == contrato.get('id') and 
                a.get('tipo_alerta') == 'contrato_vencido'
                for a in alertas_existentes
            )
            
            if not ya_existe:
                severidad = 'media' if dias_restantes > 7 else 'alta'
                legal_db.crear_alerta_legal({
                    'medico_id': medico_id,
                    'tipo_alerta': 'contrato_vencido',
                    'severidad': severidad,
                    'titulo': f'Contrato de {contrato.get("empleado_nombre")} vence en {dias_restantes} días',
                    'descripcion': f'El contrato de {contrato.get("empleado_nombre")} ({contrato.get("puesto", "N/A")}) vence en {dias_restantes} días. ¿Renovar o terminar?',
                    'entidad_tipo': 'contrato_staff',
                    'entidad_id': contrato.get('id')
                })
                print(f"[ALERTA] Creada alerta para contrato de {contrato.get('empleado_nombre')}")
        
        print(f"[{datetime.now()}] ✅ Auditoría completada.")
        print(f"[RESUMEN] Alertas creadas: {alertas_creadas}")
        print(f"[RESUMEN] Contratos por vencer: {len(contratos_vencer)}")
        print(f"[RESUMEN] Consultas revisadas: {len(consultas)}")
        print(f"[RESUMEN] Consultas con consentimiento: {len(consultas_con_consentimiento)}")
        
        return {
            'success': True,
            'alertas_creadas': alertas_creadas,
            'total_consultas_revisadas': len(consultas),
            'consultas_con_consentimiento': len(consultas_con_consentimiento),
            'contratos_por_vencer': len(contratos_vencer)
        }
        
    except Exception as e:
        print(f"[ERROR] Error en auditoría: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }

if __name__ == '__main__':
    resultado = ejecutar_auditoria_nocturna()
    sys.exit(0 if resultado.get('success') else 1)

