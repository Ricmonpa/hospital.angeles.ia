# -*- coding: utf-8 -*-
import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional

class ConsultaDB:
    def __init__(self, db_path: str = "consultas.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inicializa la base de datos y crea las tablas necesarias"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS consultas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha_consulta DATETIME DEFAULT CURRENT_TIMESTAMP,
                    medico_id TEXT DEFAULT 'default',
                    paciente_nombre TEXT,
                    transcripcion TEXT NOT NULL,
                    soap_subjetivo TEXT,
                    soap_objetivo TEXT,
                    soap_analisis TEXT,
                    soap_plan TEXT,
                    diagnostico TEXT,
                    tratamiento TEXT,
                    cumplimiento_estado TEXT,
                    audio_duracion INTEGER,
                    notas_adicionales TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Índices para búsquedas rápidas
            conn.execute('CREATE INDEX IF NOT EXISTS idx_fecha ON consultas(fecha_consulta)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_medico ON consultas(medico_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_diagnostico ON consultas(diagnostico)')
            
            conn.commit()
    
    def guardar_consulta(self, consulta_data: Dict) -> int:
        """Guarda una nueva consulta y retorna el ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO consultas (
                    medico_id, paciente_nombre, transcripcion,
                    soap_subjetivo, soap_objetivo, soap_analisis, soap_plan,
                    diagnostico, tratamiento, cumplimiento_estado,
                    audio_duracion, notas_adicionales
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                consulta_data.get('medico_id', 'default'),
                consulta_data.get('paciente_nombre', ''),
                consulta_data.get('transcripcion', ''),
                consulta_data.get('soap_subjetivo', ''),
                consulta_data.get('soap_objetivo', ''),
                consulta_data.get('soap_analisis', ''),
                consulta_data.get('soap_plan', ''),
                consulta_data.get('diagnostico', ''),
                consulta_data.get('tratamiento', ''),
                consulta_data.get('cumplimiento_estado', ''),
                consulta_data.get('audio_duracion', 0),
                consulta_data.get('notas_adicionales', '')
            ))
            return cursor.lastrowid
    
    def obtener_consultas(self, medico_id: str = 'default', limite: int = 50) -> List[Dict]:
        """Obtiene las consultas más recientes de un médico"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM consultas 
                WHERE medico_id = ? 
                ORDER BY fecha_consulta DESC 
                LIMIT ?
            ''', (medico_id, limite))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def obtener_consulta(self, consulta_id: int) -> Optional[Dict]:
        """Obtiene una consulta específica por ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM consultas WHERE id = ?', (consulta_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def actualizar_consulta(self, consulta_id: int, datos: Dict) -> bool:
        """Actualiza una consulta existente"""
        campos = []
        valores = []
        
        for campo, valor in datos.items():
            if campo in ['soap_subjetivo', 'soap_objetivo', 'soap_analisis', 'soap_plan', 
                        'diagnostico', 'tratamiento', 'notas_adicionales', 'paciente_nombre']:
                campos.append(f"{campo} = ?")
                valores.append(valor)
        
        if not campos:
            return False
        
        campos.append("updated_at = CURRENT_TIMESTAMP")
        valores.append(consulta_id)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(f'''
                UPDATE consultas 
                SET {', '.join(campos)}
                WHERE id = ?
            ''', valores)
            return cursor.rowcount > 0
    
    def buscar_consultas(self, termino: str, medico_id: str = 'default') -> List[Dict]:
        """Busca consultas por término en transcripción, diagnóstico o notas SOAP"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM consultas 
                WHERE medico_id = ? AND (
                    transcripcion LIKE ? OR 
                    diagnostico LIKE ? OR 
                    soap_subjetivo LIKE ? OR 
                    soap_analisis LIKE ?
                )
                ORDER BY fecha_consulta DESC
            ''', (medico_id, f'%{termino}%', f'%{termino}%', f'%{termino}%', f'%{termino}%'))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def obtener_estadisticas(self, medico_id: str = 'default') -> Dict:
        """Obtiene estadísticas básicas de consultas"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total_consultas,
                    COUNT(DISTINCT DATE(fecha_consulta)) as dias_activos,
                    AVG(audio_duracion) as duracion_promedio
                FROM consultas 
                WHERE medico_id = ?
            ''', (medico_id,))
            
            stats = cursor.fetchone()
            
            # Top 5 diagnósticos más frecuentes
            cursor = conn.execute('''
                SELECT diagnostico, COUNT(*) as frecuencia
                FROM consultas 
                WHERE medico_id = ? AND diagnostico != ''
                GROUP BY diagnostico
                ORDER BY frecuencia DESC
                LIMIT 5
            ''', (medico_id,))
            
            top_diagnosticos = cursor.fetchall()
            
            return {
                'total_consultas': stats[0] or 0,
                'dias_activos': stats[1] or 0,
                'duracion_promedio': round(stats[2] or 0, 1),
                'top_diagnosticos': [{'diagnostico': d[0], 'frecuencia': d[1]} for d in top_diagnosticos]
            }
    
    def eliminar_consulta(self, consulta_id: int) -> bool:
        """Elimina una consulta (usar con cuidado)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('DELETE FROM consultas WHERE id = ?', (consulta_id,))
            return cursor.rowcount > 0

class TransaccionDB:
    """Gestión de transacciones financieras (ingresos y gastos) para el módulo del contador"""
    
    def __init__(self, db_path: str = "consultas.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inicializa las tablas de transacciones financieras"""
        with sqlite3.connect(self.db_path) as conn:
            # Tabla de transacciones (ingresos y gastos)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS transacciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    medico_id TEXT DEFAULT 'default',
                    tipo TEXT NOT NULL CHECK(tipo IN ('ingreso', 'gasto')),
                    fecha DATE NOT NULL,
                    monto REAL NOT NULL,
                    concepto TEXT NOT NULL,
                    proveedor TEXT,
                    cfdi_uuid TEXT,
                    cfdi_xml_path TEXT,
                    cfdi_pdf_path TEXT,
                    cfdi_vigente BOOLEAN DEFAULT 1,
                    clasificacion_ia TEXT,
                    clasificacion_contador TEXT,
                    deducible_porcentaje INTEGER DEFAULT 0,
                    estatus_validacion TEXT DEFAULT 'pendiente' CHECK(estatus_validacion IN ('pendiente', 'aprobado', 'rechazado', 'ajustado')),
                    notas_contador TEXT,
                    metodo_pago TEXT,
                    forma_pago TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    validado_por TEXT,
                    validado_at DATETIME
                )
            ''')
            
            # Tabla de reglas de clasificación aprendidas
            conn.execute('''
                CREATE TABLE IF NOT EXISTS reglas_clasificacion (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    medico_id TEXT DEFAULT 'default',
                    patron_concepto TEXT NOT NULL,
                    proveedor TEXT,
                    clasificacion TEXT NOT NULL,
                    deducible_porcentaje INTEGER DEFAULT 0,
                    frecuencia_uso INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Índices para búsquedas rápidas
            conn.execute('CREATE INDEX IF NOT EXISTS idx_trans_fecha ON transacciones(fecha)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_trans_tipo ON transacciones(tipo)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_trans_estatus ON transacciones(estatus_validacion)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_trans_medico ON transacciones(medico_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_reglas_medico ON reglas_clasificacion(medico_id)')
            
            conn.commit()
    
    def guardar_transaccion(self, transaccion_data: Dict) -> int:
        """Guarda una nueva transacción"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO transacciones (
                    medico_id, tipo, fecha, monto, concepto, proveedor,
                    cfdi_uuid, cfdi_xml_path, cfdi_pdf_path, cfdi_vigente,
                    clasificacion_ia, deducible_porcentaje, metodo_pago, forma_pago
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                transaccion_data.get('medico_id', 'default'),
                transaccion_data.get('tipo'),
                transaccion_data.get('fecha'),
                transaccion_data.get('monto'),
                transaccion_data.get('concepto'),
                transaccion_data.get('proveedor', ''),
                transaccion_data.get('cfdi_uuid', ''),
                transaccion_data.get('cfdi_xml_path', ''),
                transaccion_data.get('cfdi_pdf_path', ''),
                transaccion_data.get('cfdi_vigente', 1),
                transaccion_data.get('clasificacion_ia', ''),
                transaccion_data.get('deducible_porcentaje', 0),
                transaccion_data.get('metodo_pago', ''),
                transaccion_data.get('forma_pago', '')
            ))
            return cursor.lastrowid
    
    def obtener_transacciones(self, filtros: Dict = None, limite: int = 100) -> List[Dict]:
        """Obtiene transacciones con filtros opcionales"""
        query = 'SELECT * FROM transacciones WHERE medico_id = ?'
        params = [filtros.get('medico_id', 'default') if filtros else 'default']
        
        if filtros:
            if filtros.get('tipo'):
                query += ' AND tipo = ?'
                params.append(filtros['tipo'])
            if filtros.get('estatus_validacion'):
                query += ' AND estatus_validacion = ?'
                params.append(filtros['estatus_validacion'])
            if filtros.get('fecha_desde'):
                query += ' AND fecha >= ?'
                params.append(filtros['fecha_desde'])
            if filtros.get('fecha_hasta'):
                query += ' AND fecha <= ?'
                params.append(filtros['fecha_hasta'])
            if filtros.get('clasificacion'):
                query += ' AND (clasificacion_ia = ? OR clasificacion_contador = ?)'
                params.extend([filtros['clasificacion'], filtros['clasificacion']])
            if filtros.get('cfdi_uuid'):
                query += ' AND cfdi_uuid = ?'
                params.append(filtros['cfdi_uuid'])
        
        query += ' ORDER BY fecha DESC LIMIT ?'
        params.append(limite)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def validar_transaccion(self, transaccion_id: int, validacion_data: Dict) -> bool:
        """Valida una transacción (aprueba, rechaza o ajusta)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                UPDATE transacciones 
                SET estatus_validacion = ?,
                    clasificacion_contador = ?,
                    deducible_porcentaje = ?,
                    notas_contador = ?,
                    validado_por = ?,
                    validado_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                validacion_data.get('estatus', 'aprobado'),
                validacion_data.get('clasificacion', ''),
                validacion_data.get('deducible_porcentaje', 0),
                validacion_data.get('notas', ''),
                validacion_data.get('validado_por', 'contador'),
                transaccion_id
            ))
            
            # Si se aprueba, aprender la regla
            if validacion_data.get('estatus') == 'aprobado' and validacion_data.get('clasificacion'):
                self._aprender_regla(transaccion_id, validacion_data)
            
            return cursor.rowcount > 0
    
    def _aprender_regla(self, transaccion_id: int, validacion_data: Dict):
        """Aprende una regla de clasificación basada en la validación del contador"""
        with sqlite3.connect(self.db_path) as conn:
            # Obtener la transacción
            cursor = conn.execute('SELECT concepto, proveedor, medico_id FROM transacciones WHERE id = ?', (transaccion_id,))
            trans = cursor.fetchone()
            if not trans:
                return
            
            concepto, proveedor, medico_id = trans
            
            # Verificar si ya existe una regla similar
            cursor = conn.execute('''
                SELECT id, frecuencia_uso FROM reglas_clasificacion 
                WHERE medico_id = ? AND patron_concepto = ? AND proveedor = ?
            ''', (medico_id, concepto, proveedor or ''))
            
            regla_existente = cursor.fetchone()
            
            if regla_existente:
                # Incrementar frecuencia
                conn.execute('''
                    UPDATE reglas_clasificacion 
                    SET frecuencia_uso = frecuencia_uso + 1,
                        clasificacion = ?,
                        deducible_porcentaje = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (validacion_data['clasificacion'], validacion_data.get('deducible_porcentaje', 0), regla_existente[0]))
            else:
                # Crear nueva regla
                conn.execute('''
                    INSERT INTO reglas_clasificacion (
                        medico_id, patron_concepto, proveedor, clasificacion, deducible_porcentaje
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (medico_id, concepto, proveedor or '', validacion_data['clasificacion'], validacion_data.get('deducible_porcentaje', 0)))
            
            conn.commit()
    
    def clasificar_con_ia(self, concepto: str, proveedor: str = '', medico_id: str = 'default') -> Dict:
        """Clasifica una transacción usando reglas aprendidas"""
        with sqlite3.connect(self.db_path) as conn:
            # Buscar regla exacta
            cursor = conn.execute('''
                SELECT clasificacion, deducible_porcentaje, frecuencia_uso
                FROM reglas_clasificacion 
                WHERE medico_id = ? AND patron_concepto = ? AND proveedor = ?
                ORDER BY frecuencia_uso DESC
                LIMIT 1
            ''', (medico_id, concepto, proveedor))
            
            regla = cursor.fetchone()
            
            if regla:
                return {
                    'clasificacion': regla[0],
                    'deducible_porcentaje': regla[1],
                    'confianza': 'alta',
                    'metodo': 'regla_aprendida'
                }
            
            # Buscar regla por similitud de concepto
            cursor = conn.execute('''
                SELECT clasificacion, deducible_porcentaje, frecuencia_uso
                FROM reglas_clasificacion 
                WHERE medico_id = ? AND (
                    patron_concepto LIKE ? OR ? LIKE patron_concepto
                )
                ORDER BY frecuencia_uso DESC
                LIMIT 1
            ''', (medico_id, f'%{concepto}%', f'%{concepto}%'))
            
            regla_similar = cursor.fetchone()
            
            if regla_similar:
                return {
                    'clasificacion': regla_similar[0],
                    'deducible_porcentaje': regla_similar[1],
                    'confianza': 'media',
                    'metodo': 'similitud'
                }
            
            # Sin regla, usar clasificación por defecto
            return {
                'clasificacion': 'Sin clasificar',
                'deducible_porcentaje': 0,
                'confianza': 'baja',
                'metodo': 'default'
            }
    
    def obtener_estadisticas_financieras(self, medico_id: str = 'default', fecha_desde: str = None, fecha_hasta: str = None) -> Dict:
        """Obtiene estadísticas financieras para el dashboard del contador"""
        with sqlite3.connect(self.db_path) as conn:
            query_base = 'SELECT tipo, SUM(monto) as total FROM transacciones WHERE medico_id = ?'
            params = [medico_id]
            
            if fecha_desde:
                query_base += ' AND fecha >= ?'
                params.append(fecha_desde)
            if fecha_hasta:
                query_base += ' AND fecha <= ?'
                params.append(fecha_hasta)
            
            query_base += ' GROUP BY tipo'
            
            cursor = conn.execute(query_base, params)
            totales = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Transacciones pendientes de validación
            cursor = conn.execute('''
                SELECT COUNT(*) FROM transacciones 
                WHERE medico_id = ? AND estatus_validacion = 'pendiente'
            ''', (medico_id,))
            pendientes = cursor.fetchone()[0]
            
            # Top gastos deducibles
            cursor = conn.execute('''
                SELECT clasificacion_contador, SUM(monto * deducible_porcentaje / 100.0) as monto_deducible
                FROM transacciones 
                WHERE medico_id = ? AND tipo = 'gasto' AND estatus_validacion = 'aprobado'
                GROUP BY clasificacion_contador
                ORDER BY monto_deducible DESC
                LIMIT 5
            ''', (medico_id,))
            top_deducibles = [{'clasificacion': row[0], 'monto': row[1]} for row in cursor.fetchall()]
            
            return {
                'ingresos_totales': totales.get('ingreso', 0),
                'gastos_totales': totales.get('gasto', 0),
                'utilidad': totales.get('ingreso', 0) - totales.get('gasto', 0),
                'pendientes_validacion': pendientes,
                'top_deducibles': top_deducibles
            }

class SeguroDB:
    """Gestión de datos de seguros médicos (credenciales, tabuladores, informes)"""
    
    def __init__(self, db_path: str = "consultas.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inicializa las tablas de seguros"""
        with sqlite3.connect(self.db_path) as conn:
            # Tabla de credenciales de seguro procesadas
            conn.execute('''
                CREATE TABLE IF NOT EXISTS credenciales_seguros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    medico_id TEXT DEFAULT 'default',
                    paciente_id INTEGER,
                    paciente_nombre TEXT,
                    aseguradora TEXT NOT NULL,
                    numero_poliza TEXT NOT NULL,
                    plan_nombre TEXT,
                    nivel_hospitalario TEXT,
                    deducible_estimado REAL,
                    coaseguro_porcentaje REAL,
                    hospitales_red TEXT,
                    imagen_path TEXT,
                    datos_extractos TEXT,
                    fecha_procesamiento DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de tabuladores cargados (PDFs)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tabuladores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    aseguradora TEXT NOT NULL,
                    plan_nombre TEXT,
                    tipo_documento TEXT CHECK(tipo_documento IN ('tabulador', 'condiciones_generales')),
                    archivo_path TEXT NOT NULL,
                    archivo_hash TEXT,
                    fecha_vigencia DATE,
                    contenido_texto TEXT,
                    contenido_embedding TEXT,
                    fecha_carga DATETIME DEFAULT CURRENT_TIMESTAMP,
                    activo BOOLEAN DEFAULT 1
                )
            ''')
            
            # Tabla de informes médicos generados
            conn.execute('''
                CREATE TABLE IF NOT EXISTS informes_medicos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    consulta_id INTEGER,
                    credencial_seguro_id INTEGER,
                    aseguradora TEXT NOT NULL,
                    paciente_nombre TEXT,
                    numero_poliza TEXT,
                    diagnostico TEXT,
                    procedimiento TEXT,
                    codigo_cpt TEXT,
                    codigo_cie10 TEXT,
                    informe_pdf_path TEXT,
                    fecha_generacion DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de consultas de honorarios (búsquedas en tabuladores)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS consultas_honorarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    medico_id TEXT DEFAULT 'default',
                    aseguradora TEXT,
                    plan_nombre TEXT,
                    procedimiento TEXT,
                    codigo_cpt TEXT,
                    monto_encontrado REAL,
                    fuente_tabulador_id INTEGER,
                    fecha_consulta DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Índices
            conn.execute('CREATE INDEX IF NOT EXISTS idx_credencial_aseguradora ON credenciales_seguros(aseguradora)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_credencial_poliza ON credenciales_seguros(numero_poliza)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_credencial_paciente ON credenciales_seguros(paciente_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_tabulador_aseguradora ON tabuladores(aseguradora)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_tabulador_activo ON tabuladores(activo)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_informe_consulta ON informes_medicos(consulta_id)')
            
            conn.commit()
    
    def guardar_credencial(self, credencial_data: Dict) -> int:
        """Guarda una credencial de seguro procesada"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO credenciales_seguros (
                    medico_id, paciente_id, paciente_nombre,
                    aseguradora, numero_poliza, plan_nombre, nivel_hospitalario,
                    deducible_estimado, coaseguro_porcentaje, hospitales_red,
                    imagen_path, datos_extractos
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                credencial_data.get('medico_id', 'default'),
                credencial_data.get('paciente_id'),
                credencial_data.get('paciente_nombre', ''),
                credencial_data.get('aseguradora', ''),
                credencial_data.get('numero_poliza', ''),
                credencial_data.get('plan_nombre', ''),
                credencial_data.get('nivel_hospitalario', ''),
                credencial_data.get('deducible_estimado'),
                credencial_data.get('coaseguro_porcentaje'),
                credencial_data.get('hospitales_red', ''),
                credencial_data.get('imagen_path', ''),
                credencial_data.get('datos_extractos', '')
            ))
            return cursor.lastrowid
    
    def obtener_credencial(self, credencial_id: int) -> Optional[Dict]:
        """Obtiene una credencial por ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM credenciales_seguros WHERE id = ?', (credencial_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def obtener_credenciales(self, medico_id: str = 'default', limite: int = 50) -> List[Dict]:
        """Obtiene las credenciales más recientes"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM credenciales_seguros 
                WHERE medico_id = ?
                ORDER BY fecha_procesamiento DESC 
                LIMIT ?
            ''', (medico_id, limite))
            return [dict(row) for row in cursor.fetchall()]
    
    def guardar_tabulador(self, tabulador_data: Dict) -> int:
        """Guarda información de un tabulador PDF cargado"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO tabuladores (
                    aseguradora, plan_nombre, tipo_documento,
                    archivo_path, archivo_hash, fecha_vigencia,
                    contenido_texto, contenido_embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                tabulador_data.get('aseguradora', ''),
                tabulador_data.get('plan_nombre', ''),
                tabulador_data.get('tipo_documento', 'tabulador'),
                tabulador_data.get('archivo_path', ''),
                tabulador_data.get('archivo_hash', ''),
                tabulador_data.get('fecha_vigencia'),
                tabulador_data.get('contenido_texto', ''),
                tabulador_data.get('contenido_embedding', '')
            ))
            return cursor.lastrowid
    
    def obtener_tabuladores(self, aseguradora: str = None, activo: bool = True) -> List[Dict]:
        """Obtiene tabuladores, filtrados opcionalmente por aseguradora"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = 'SELECT * FROM tabuladores WHERE activo = ?'
            params = [1 if activo else 0]
            
            if aseguradora:
                query += ' AND aseguradora = ?'
                params.append(aseguradora)
            
            query += ' ORDER BY fecha_carga DESC'
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def guardar_informe_medico(self, informe_data: Dict) -> int:
        """Guarda un informe médico generado"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO informes_medicos (
                    consulta_id, credencial_seguro_id, aseguradora,
                    paciente_nombre, numero_poliza, diagnostico,
                    procedimiento, codigo_cpt, codigo_cie10, informe_pdf_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                informe_data.get('consulta_id'),
                informe_data.get('credencial_seguro_id'),
                informe_data.get('aseguradora', ''),
                informe_data.get('paciente_nombre', ''),
                informe_data.get('numero_poliza', ''),
                informe_data.get('diagnostico', ''),
                informe_data.get('procedimiento', ''),
                informe_data.get('codigo_cpt', ''),
                informe_data.get('codigo_cie10', ''),
                informe_data.get('informe_pdf_path', '')
            ))
            return cursor.lastrowid
    
    def guardar_consulta_honorario(self, consulta_data: Dict) -> int:
        """Guarda una consulta de honorario realizada"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO consultas_honorarios (
                    medico_id, aseguradora, plan_nombre,
                    procedimiento, codigo_cpt, monto_encontrado, fuente_tabulador_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                consulta_data.get('medico_id', 'default'),
                consulta_data.get('aseguradora', ''),
                consulta_data.get('plan_nombre', ''),
                consulta_data.get('procedimiento', ''),
                consulta_data.get('codigo_cpt', ''),
                consulta_data.get('monto_encontrado'),
                consulta_data.get('fuente_tabulador_id')
            ))
            return cursor.lastrowid

class LegalDB:
    """Gestión de documentos legales, consentimientos, contratos y auditoría de cumplimiento"""
    
    def __init__(self, db_path: str = "consultas.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inicializa las tablas del módulo legal"""
        with sqlite3.connect(self.db_path) as conn:
            # Tabla de plantillas legales (consentimientos, contratos, etc.)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS plantillas_legales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tipo_documento TEXT NOT NULL CHECK(tipo_documento IN ('consentimiento_informado', 'contrato_laboral', 'nda', 'aviso_privacidad', 'otro')),
                    nombre_plantilla TEXT NOT NULL,
                    procedimiento TEXT,
                    contenido_template TEXT NOT NULL,
                    variables_template TEXT,
                    aprobado_por TEXT,
                    fecha_aprobacion DATE,
                    activo BOOLEAN DEFAULT 1,
                    version INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de documentos firmados (consentimientos, contratos)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS documentos_firmados (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    medico_id TEXT DEFAULT 'default',
                    paciente_id INTEGER,
                    paciente_nombre TEXT,
                    consulta_id INTEGER,
                    plantilla_id INTEGER,
                    tipo_documento TEXT NOT NULL,
                    procedimiento TEXT,
                    contenido_documento TEXT NOT NULL,
                    firma_digital TEXT,
                    firma_imagen_path TEXT,
                    fecha_firma DATETIME NOT NULL,
                    hora_firma TIME NOT NULL,
                    latitud REAL,
                    longitud REAL,
                    ip_address TEXT,
                    dispositivo TEXT,
                    hash_documento TEXT,
                    estado TEXT DEFAULT 'firmado' CHECK(estado IN ('firmado', 'cancelado', 'rechazado')),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de log de auditoría (quién accedió a qué)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS log_auditoria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    medico_id TEXT,
                    usuario TEXT,
                    tipo_acceso TEXT CHECK(tipo_acceso IN ('lectura', 'escritura', 'eliminacion', 'firma', 'descarga')),
                    entidad TEXT,
                    entidad_id INTEGER,
                    ip_address TEXT,
                    user_agent TEXT,
                    detalles TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de contratos de staff (empleados, asistentes, enfermeras)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS contratos_staff (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    medico_id TEXT DEFAULT 'default',
                    empleado_nombre TEXT NOT NULL,
                    puesto TEXT,
                    tipo_contrato TEXT CHECK(tipo_contrato IN ('indefinido', 'temporal', 'prueba', 'honorarios')),
                    fecha_inicio DATE NOT NULL,
                    fecha_fin DATE,
                    salario REAL,
                    plantilla_contrato_id INTEGER,
                    documento_firmado_id INTEGER,
                    estado TEXT DEFAULT 'activo' CHECK(estado IN ('activo', 'vencido', 'terminado', 'renovado')),
                    alerta_vencimiento BOOLEAN DEFAULT 0,
                    dias_vencimiento INTEGER,
                    notas TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de incidencias laborales (registro de faltas, problemas)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS incidencias_laborales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    medico_id TEXT DEFAULT 'default',
                    contrato_staff_id INTEGER,
                    empleado_nombre TEXT NOT NULL,
                    tipo_incidencia TEXT CHECK(tipo_incidencia IN ('falta', 'retardo', 'incumplimiento', 'queja', 'otro')),
                    descripcion TEXT NOT NULL,
                    fecha_incidencia DATE NOT NULL,
                    hora_incidencia TIME,
                    evidencia_path TEXT,
                    estado TEXT DEFAULT 'registrado' CHECK(estado IN ('registrado', 'resuelto', 'escalado')),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de alertas legales (riesgos detectados por auditoría)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS alertas_legales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    medico_id TEXT DEFAULT 'default',
                    tipo_alerta TEXT CHECK(tipo_alerta IN ('consentimiento_faltante', 'contrato_vencido', 'incumplimiento_nom', 'riesgo_alto', 'auditoria_cumplimiento')),
                    severidad TEXT CHECK(severidad IN ('baja', 'media', 'alta', 'critica')),
                    titulo TEXT NOT NULL,
                    descripcion TEXT NOT NULL,
                    entidad_tipo TEXT,
                    entidad_id INTEGER,
                    fecha_deteccion DATETIME DEFAULT CURRENT_TIMESTAMP,
                    fecha_resolucion DATETIME,
                    estado TEXT DEFAULT 'activa' CHECK(estado IN ('activa', 'resuelta', 'descartada')),
                    resuelto_por TEXT,
                    notas_resolucion TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de guías de reacción rápida (para botón de pánico)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS guias_reaccion_rapida (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    medico_id TEXT DEFAULT 'default',
                    tipo_crisis TEXT CHECK(tipo_crisis IN ('inspeccion_cofepris', 'amenaza_demanda', 'inspeccion_sat', 'emergencia_legal', 'otro')),
                    titulo TEXT NOT NULL,
                    contenido TEXT NOT NULL,
                    pasos_accion TEXT,
                    documentos_necesarios TEXT,
                    contacto_abogado TEXT,
                    activo BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Índices para búsquedas rápidas
            conn.execute('CREATE INDEX IF NOT EXISTS idx_doc_firmado_consulta ON documentos_firmados(consulta_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_doc_firmado_paciente ON documentos_firmados(paciente_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_doc_firmado_tipo ON documentos_firmados(tipo_documento)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_log_auditoria_medico ON log_auditoria(medico_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_log_auditoria_fecha ON log_auditoria(created_at)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_contrato_staff_vencimiento ON contratos_staff(fecha_fin)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_contrato_staff_estado ON contratos_staff(estado)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_alertas_estado ON alertas_legales(estado)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_alertas_severidad ON alertas_legales(severidad)')
            
            conn.commit()
    
    def guardar_plantilla(self, plantilla_data: Dict) -> int:
        """Guarda una nueva plantilla legal"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO plantillas_legales (
                    tipo_documento, nombre_plantilla, procedimiento,
                    contenido_template, variables_template, aprobado_por, fecha_aprobacion
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                plantilla_data.get('tipo_documento'),
                plantilla_data.get('nombre_plantilla'),
                plantilla_data.get('procedimiento', ''),
                plantilla_data.get('contenido_template'),
                plantilla_data.get('variables_template', ''),
                plantilla_data.get('aprobado_por', ''),
                plantilla_data.get('fecha_aprobacion')
            ))
            return cursor.lastrowid
    
    def obtener_plantillas(self, tipo_documento: str = None, activo: bool = True) -> List[Dict]:
        """Obtiene plantillas legales, filtradas opcionalmente"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = 'SELECT * FROM plantillas_legales WHERE activo = ?'
            params = [1 if activo else 0]
            
            if tipo_documento:
                query += ' AND tipo_documento = ?'
                params.append(tipo_documento)
            
            query += ' ORDER BY updated_at DESC'
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def obtener_plantilla_por_procedimiento(self, procedimiento: str) -> Optional[Dict]:
        """Obtiene la plantilla activa para un procedimiento específico"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM plantillas_legales 
                WHERE procedimiento = ? AND activo = 1
                ORDER BY version DESC
                LIMIT 1
            ''', (procedimiento,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def guardar_documento_firmado(self, documento_data: Dict) -> int:
        """Guarda un documento firmado"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO documentos_firmados (
                    medico_id, paciente_id, paciente_nombre, consulta_id, plantilla_id,
                    tipo_documento, procedimiento, contenido_documento,
                    firma_digital, firma_imagen_path, fecha_firma, hora_firma,
                    latitud, longitud, ip_address, dispositivo, hash_documento
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                documento_data.get('medico_id', 'default'),
                documento_data.get('paciente_id'),
                documento_data.get('paciente_nombre', ''),
                documento_data.get('consulta_id'),
                documento_data.get('plantilla_id'),
                documento_data.get('tipo_documento'),
                documento_data.get('procedimiento', ''),
                documento_data.get('contenido_documento'),
                documento_data.get('firma_digital', ''),
                documento_data.get('firma_imagen_path', ''),
                documento_data.get('fecha_firma'),
                documento_data.get('hora_firma'),
                documento_data.get('latitud'),
                documento_data.get('longitud'),
                documento_data.get('ip_address', ''),
                documento_data.get('dispositivo', ''),
                documento_data.get('hash_documento', '')
            ))
            return cursor.lastrowid
    
    def obtener_documentos_firmados(self, medico_id: str = 'default', consulta_id: int = None, limite: int = 50) -> List[Dict]:
        """Obtiene documentos firmados"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = 'SELECT * FROM documentos_firmados WHERE medico_id = ?'
            params = [medico_id]
            
            if consulta_id:
                query += ' AND consulta_id = ?'
                params.append(consulta_id)
            
            query += ' ORDER BY fecha_firma DESC LIMIT ?'
            params.append(limite)
            
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def registrar_acceso_auditoria(self, acceso_data: Dict):
        """Registra un acceso en el log de auditoría"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO log_auditoria (
                    medico_id, usuario, tipo_acceso, entidad, entidad_id,
                    ip_address, user_agent, detalles
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                acceso_data.get('medico_id', 'default'),
                acceso_data.get('usuario', ''),
                acceso_data.get('tipo_acceso', 'lectura'),
                acceso_data.get('entidad', ''),
                acceso_data.get('entidad_id'),
                acceso_data.get('ip_address', ''),
                acceso_data.get('user_agent', ''),
                acceso_data.get('detalles', '')
            ))
    
    def guardar_contrato_staff(self, contrato_data: Dict) -> int:
        """Guarda un contrato de staff"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO contratos_staff (
                    medico_id, empleado_nombre, puesto, tipo_contrato,
                    fecha_inicio, fecha_fin, salario, plantilla_contrato_id,
                    documento_firmado_id, estado, notas
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                contrato_data.get('medico_id', 'default'),
                contrato_data.get('empleado_nombre'),
                contrato_data.get('puesto', ''),
                contrato_data.get('tipo_contrato'),
                contrato_data.get('fecha_inicio'),
                contrato_data.get('fecha_fin'),
                contrato_data.get('salario'),
                contrato_data.get('plantilla_contrato_id'),
                contrato_data.get('documento_firmado_id'),
                contrato_data.get('estado', 'activo'),
                contrato_data.get('notas', '')
            ))
            return cursor.lastrowid
    
    def obtener_contratos_staff(self, medico_id: str = 'default', estado: str = None) -> List[Dict]:
        """Obtiene contratos de staff"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = 'SELECT * FROM contratos_staff WHERE medico_id = ?'
            params = [medico_id]
            
            if estado:
                query += ' AND estado = ?'
                params.append(estado)
            
            query += ' ORDER BY fecha_fin DESC, fecha_inicio DESC'
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def obtener_contratos_por_vencer(self, medico_id: str = 'default', dias: int = 30) -> List[Dict]:
        """Obtiene contratos que vencen en los próximos N días"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT *, 
                    julianday(fecha_fin) - julianday('now') as dias_restantes
                FROM contratos_staff 
                WHERE medico_id = ? 
                    AND estado = 'activo'
                    AND fecha_fin IS NOT NULL
                    AND julianday(fecha_fin) - julianday('now') <= ?
                    AND julianday(fecha_fin) - julianday('now') >= 0
                ORDER BY fecha_fin ASC
            ''', (medico_id, dias))
            return [dict(row) for row in cursor.fetchall()]
    
    def guardar_incidencia_laboral(self, incidencia_data: Dict) -> int:
        """Guarda una incidencia laboral"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO incidencias_laborales (
                    medico_id, contrato_staff_id, empleado_nombre,
                    tipo_incidencia, descripcion, fecha_incidencia, hora_incidencia, evidencia_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                incidencia_data.get('medico_id', 'default'),
                incidencia_data.get('contrato_staff_id'),
                incidencia_data.get('empleado_nombre'),
                incidencia_data.get('tipo_incidencia'),
                incidencia_data.get('descripcion'),
                incidencia_data.get('fecha_incidencia'),
                incidencia_data.get('hora_incidencia'),
                incidencia_data.get('evidencia_path', '')
            ))
            return cursor.lastrowid
    
    def obtener_incidencias_laborales(self, medico_id: str = 'default', contrato_staff_id: int = None, limite: int = 50) -> List[Dict]:
        """Obtiene incidencias laborales"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = 'SELECT * FROM incidencias_laborales WHERE medico_id = ?'
            params = [medico_id]
            
            if contrato_staff_id:
                query += ' AND contrato_staff_id = ?'
                params.append(contrato_staff_id)
            
            query += ' ORDER BY fecha_incidencia DESC, hora_incidencia DESC LIMIT ?'
            params.append(limite)
            
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def crear_alerta_legal(self, alerta_data: Dict) -> int:
        """Crea una alerta legal"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO alertas_legales (
                    medico_id, tipo_alerta, severidad, titulo, descripcion,
                    entidad_tipo, entidad_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                alerta_data.get('medico_id', 'default'),
                alerta_data.get('tipo_alerta'),
                alerta_data.get('severidad', 'media'),
                alerta_data.get('titulo'),
                alerta_data.get('descripcion'),
                alerta_data.get('entidad_tipo', ''),
                alerta_data.get('entidad_id')
            ))
            return cursor.lastrowid
    
    def obtener_alertas_legales(self, medico_id: str = 'default', estado: str = 'activa', limite: int = 50) -> List[Dict]:
        """Obtiene alertas legales"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM alertas_legales 
                WHERE medico_id = ? AND estado = ?
                ORDER BY 
                    CASE severidad 
                        WHEN 'critica' THEN 1
                        WHEN 'alta' THEN 2
                        WHEN 'media' THEN 3
                        WHEN 'baja' THEN 4
                    END,
                    fecha_deteccion DESC
                LIMIT ?
            ''', (medico_id, estado, limite))
            return [dict(row) for row in cursor.fetchall()]
    
    def resolver_alerta(self, alerta_id: int, resuelto_por: str, notas: str = ''):
        """Marca una alerta como resuelta"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE alertas_legales 
                SET estado = 'resuelta',
                    fecha_resolucion = CURRENT_TIMESTAMP,
                    resuelto_por = ?,
                    notas_resolucion = ?
                WHERE id = ?
            ''', (resuelto_por, notas, alerta_id))
    
    def obtener_estadisticas_cumplimiento(self, medico_id: str = 'default') -> Dict:
        """Obtiene estadísticas de cumplimiento para el dashboard del abogado"""
        with sqlite3.connect(self.db_path) as conn:
            # Total de consultas con consentimiento
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT consulta_id) 
                FROM documentos_firmados 
                WHERE medico_id = ? AND tipo_documento = 'consentimiento_informado'
            ''', (medico_id,))
            consultas_con_consentimiento = cursor.fetchone()[0] or 0
            
            # Total de consultas (desde tabla consultas)
            cursor = conn.execute('''
                SELECT COUNT(*) FROM consultas WHERE medico_id = ?
            ''', (medico_id,))
            total_consultas = cursor.fetchone()[0] or 0
            
            # Alertas activas por severidad
            cursor = conn.execute('''
                SELECT severidad, COUNT(*) 
                FROM alertas_legales 
                WHERE medico_id = ? AND estado = 'activa'
                GROUP BY severidad
            ''', (medico_id,))
            alertas_por_severidad = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Contratos por vencer
            cursor = conn.execute('''
                SELECT COUNT(*) 
                FROM contratos_staff 
                WHERE medico_id = ? 
                    AND estado = 'activo'
                    AND fecha_fin IS NOT NULL
                    AND julianday(fecha_fin) - julianday('now') <= 30
                    AND julianday(fecha_fin) - julianday('now') >= 0
            ''', (medico_id,))
            contratos_por_vencer = cursor.fetchone()[0] or 0
            
            # Porcentaje de cumplimiento NOM-004
            porcentaje_cumplimiento = 0
            if total_consultas > 0:
                porcentaje_cumplimiento = round((consultas_con_consentimiento / total_consultas) * 100, 1)
            
            return {
                'total_consultas': total_consultas,
                'consultas_con_consentimiento': consultas_con_consentimiento,
                'porcentaje_cumplimiento_nom': porcentaje_cumplimiento,
                'alertas_activas': sum(alertas_por_severidad.values()),
                'alertas_por_severidad': alertas_por_severidad,
                'contratos_por_vencer': contratos_por_vencer
            }
    
    def guardar_guia_reaccion(self, guia_data: Dict) -> int:
        """Guarda una guía de reacción rápida"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO guias_reaccion_rapida (
                    medico_id, tipo_crisis, titulo, contenido, pasos_accion,
                    documentos_necesarios, contacto_abogado
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                guia_data.get('medico_id', 'default'),
                guia_data.get('tipo_crisis'),
                guia_data.get('titulo'),
                guia_data.get('contenido'),
                guia_data.get('pasos_accion', ''),
                guia_data.get('documentos_necesarios', ''),
                guia_data.get('contacto_abogado', '')
            ))
            return cursor.lastrowid
    
    def obtener_guia_reaccion(self, tipo_crisis: str, medico_id: str = 'default') -> Optional[Dict]:
        """Obtiene la guía de reacción rápida para un tipo de crisis"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM guias_reaccion_rapida 
                WHERE medico_id = ? AND tipo_crisis = ? AND activo = 1
                ORDER BY updated_at DESC
                LIMIT 1
            ''', (medico_id, tipo_crisis))
            row = cursor.fetchone()
            return dict(row) if row else None