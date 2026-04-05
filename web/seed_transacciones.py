#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para poblar la base de datos con transacciones de ejemplo
para demostrar el módulo del contador
"""

from database import TransaccionDB
from datetime import datetime, timedelta
import random

def seed_transacciones():
    db = TransaccionDB()
    
    print("🌱 Poblando base de datos con transacciones de ejemplo...")
    
    # Transacciones de ejemplo - Ingresos
    ingresos = [
        {
            'tipo': 'ingreso',
            'fecha': (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'),
            'monto': 1500.00,
            'concepto': 'Consulta médica general',
            'proveedor': 'Paciente: Juan Pérez',
            'metodo_pago': 'tarjeta',
            'forma_pago': 'Tarjeta de crédito'
        },
        {
            'tipo': 'ingreso',
            'fecha': (datetime.now() - timedelta(days=4)).strftime('%Y-%m-%d'),
            'monto': 2500.00,
            'concepto': 'Consulta de especialidad',
            'proveedor': 'Paciente: María González',
            'metodo_pago': 'transferencia',
            'forma_pago': 'Transferencia bancaria'
        },
        {
            'tipo': 'ingreso',
            'fecha': (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d'),
            'monto': 1800.00,
            'concepto': 'Consulta médica general',
            'proveedor': 'Paciente: Carlos Ramírez',
            'metodo_pago': 'efectivo',
            'forma_pago': 'Efectivo'
        },
        {
            'tipo': 'ingreso',
            'fecha': (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d'),
            'monto': 3000.00,
            'concepto': 'Procedimiento menor',
            'proveedor': 'Paciente: Ana López',
            'metodo_pago': 'tarjeta',
            'forma_pago': 'Tarjeta de débito'
        },
        {
            'tipo': 'ingreso',
            'fecha': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
            'monto': 1500.00,
            'concepto': 'Consulta médica general',
            'proveedor': 'Paciente: Roberto Sánchez',
            'metodo_pago': 'transferencia',
            'forma_pago': 'Transferencia bancaria'
        }
    ]
    
    # Transacciones de ejemplo - Gastos
    gastos = [
        {
            'tipo': 'gasto',
            'fecha': (datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d'),
            'monto': 8500.00,
            'concepto': 'Renta de consultorio',
            'proveedor': 'Inmobiliaria del Centro',
            'metodo_pago': 'transferencia',
            'forma_pago': 'Transferencia bancaria'
        },
        {
            'tipo': 'gasto',
            'fecha': (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'),
            'monto': 450.00,
            'concepto': 'Gasolina',
            'proveedor': 'Pemex',
            'metodo_pago': 'tarjeta',
            'forma_pago': 'Tarjeta de crédito'
        },
        {
            'tipo': 'gasto',
            'fecha': (datetime.now() - timedelta(days=4)).strftime('%Y-%m-%d'),
            'monto': 1200.00,
            'concepto': 'Material médico - Guantes y cubrebocas',
            'proveedor': 'Distribuidora Médica SA',
            'metodo_pago': 'tarjeta',
            'forma_pago': 'Tarjeta de crédito'
        },
        {
            'tipo': 'gasto',
            'fecha': (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d'),
            'monto': 350.00,
            'concepto': 'Servicio de internet',
            'proveedor': 'Telcel',
            'metodo_pago': 'tarjeta',
            'forma_pago': 'Tarjeta de débito'
        },
        {
            'tipo': 'gasto',
            'fecha': (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d'),
            'monto': 2800.00,
            'concepto': 'Curso de actualización médica',
            'proveedor': 'Colegio Médico Nacional',
            'metodo_pago': 'transferencia',
            'forma_pago': 'Transferencia bancaria'
        },
        {
            'tipo': 'gasto',
            'fecha': (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
            'monto': 650.00,
            'concepto': 'Material de oficina',
            'proveedor': 'Office Depot',
            'metodo_pago': 'tarjeta',
            'forma_pago': 'Tarjeta de crédito'
        },
        {
            'tipo': 'gasto',
            'fecha': datetime.now().strftime('%Y-%m-%d'),
            'monto': 280.00,
            'concepto': 'Gasolina',
            'proveedor': 'Pemex',
            'metodo_pago': 'efectivo',
            'forma_pago': 'Efectivo'
        }
    ]
    
    # Guardar ingresos
    for ingreso in ingresos:
        transaccion_id = db.guardar_transaccion(ingreso)
        print("✅ Ingreso creado: ID {} - {} - ${}".format(transaccion_id, ingreso['concepto'], ingreso['monto']))
    
    # Guardar gastos con clasificación IA
    for gasto in gastos:
        # Clasificar automáticamente
        clasificacion = db.clasificar_con_ia(gasto['concepto'], gasto['proveedor'])
        gasto['clasificacion_ia'] = clasificacion['clasificacion']
        gasto['deducible_porcentaje'] = clasificacion['deducible_porcentaje']
        
        transaccion_id = db.guardar_transaccion(gasto)
        print("✅ Gasto creado: ID {} - {} - ${} - Clasificación: {}".format(transaccion_id, gasto['concepto'], gasto['monto'], clasificacion['clasificacion']))
    
    # Crear algunas reglas de clasificación aprendidas
    print("\n🧠 Creando reglas de clasificación aprendidas...")
    
    import sqlite3
    with sqlite3.connect(db.db_path) as conn:
        reglas = [
            ('Renta de consultorio', 'Inmobiliaria del Centro', 'Renta Consultorio', 100),
            ('Gasolina', 'Pemex', 'Gasolina', 100),
            ('Material médico', '', 'Material Médico', 100),
            ('Curso', '', 'Servicios Profesionales', 100),
            ('internet', 'Telcel', 'Deducible Operativo', 100),
        ]
        
        for patron, proveedor, clasificacion, deducible in reglas:
            conn.execute('''
                INSERT INTO reglas_clasificacion (patron_concepto, proveedor, clasificacion, deducible_porcentaje, frecuencia_uso)
                VALUES (?, ?, ?, ?, ?)
            ''', (patron, proveedor, clasificacion, deducible, random.randint(3, 10)))
        
        conn.commit()
    
    print("✅ Reglas de clasificación creadas")
    
    # Validar algunas transacciones automáticamente
    print("\n✓ Validando algunas transacciones...")
    
    import time
    time.sleep(0.5)  # Esperar un poco para evitar bloqueos
    
    transacciones = db.obtener_transacciones(limite=5)
    for i, trans in enumerate(transacciones[:2]):
        validacion = {
            'estatus': 'aprobado',
            'clasificacion': trans.get('clasificacion_ia', 'Deducible Operativo'),
            'deducible_porcentaje': trans.get('deducible_porcentaje', 100),
            'notas': 'Validado automáticamente en seed',
            'validado_por': 'sistema'
        }
        try:
            db.validar_transaccion(trans['id'], validacion)
            print("✓ Transacción {} validada".format(trans['id']))
        except Exception as e:
            print("⚠️ Error validando transacción {}: {}".format(trans['id'], str(e)))
    
    # Mostrar estadísticas
    print("\n📊 Estadísticas generadas:")
    stats = db.obtener_estadisticas_financieras()
    print("   💰 Ingresos totales: ${}".format(stats['ingresos_totales']))
    print("   💸 Gastos totales: ${}".format(stats['gastos_totales']))
    print("   📊 Utilidad: ${}".format(stats['utilidad']))
    print("   ⏳ Pendientes de validación: {}".format(stats['pendientes_validacion']))
    
    print("\n✨ ¡Base de datos poblada exitosamente!")
    print("🚀 Ahora puedes acceder a /contador para ver el módulo en acción")

if __name__ == '__main__':
    seed_transacciones()
