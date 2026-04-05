# -*- coding: utf-8 -*-
"""
Generador automático de informes médicos para aseguradoras
Llena formularios PDF oficiales de las aseguradoras con datos de la consulta
"""

import os
from io import BytesIO
from typing import Dict, Optional
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime

def generar_informe_medico(
    datos_consulta: Dict,
    datos_paciente: Dict,
    datos_seguro: Dict,
    tipo_aseguradora: str = 'GNP'
) -> BytesIO:
    """
    Genera un informe médico en PDF para una aseguradora específica
    
    Args:
        datos_consulta: Dict con datos de la consulta (diagnóstico, procedimiento, etc.)
        datos_paciente: Dict con datos del paciente (nombre, edad, etc.)
        datos_seguro: Dict con datos del seguro (póliza, plan, etc.)
        tipo_aseguradora: Tipo de aseguradora ('GNP', 'AXA', 'Monterrey', etc.)
    
    Returns:
        BytesIO con el PDF generado
    """
    
    buffer = BytesIO()
    
    # Crear documento
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    # Contenedor para elementos del PDF
    story = []
    
    # Estilos
    styles = getSampleStyleSheet()
    
    # Título
    titulo_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    story.append(Paragraph(f"INFORME MÉDICO - {tipo_aseguradora}", titulo_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Fecha
    fecha_actual = datetime.now().strftime("%d de %B de %Y")
    fecha_style = ParagraphStyle(
        'Fecha',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_RIGHT
    )
    story.append(Paragraph(f"Fecha: {fecha_actual}", fecha_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Datos del Paciente
    paciente_title = ParagraphStyle(
        'PacienteTitle',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#333333'),
        spaceAfter=10,
        fontName='Helvetica-Bold'
    )
    
    story.append(Paragraph("DATOS DEL PACIENTE", paciente_title))
    
    datos_paciente_table = [
        ['Nombre del Paciente:', datos_paciente.get('nombre', 'N/A')],
        ['Edad:', datos_paciente.get('edad', 'N/A')],
        ['Fecha de Nacimiento:', datos_paciente.get('fecha_nacimiento', 'N/A')],
        ['Sexo:', datos_paciente.get('sexo', 'N/A')],
    ]
    
    paciente_table = Table(datos_paciente_table, colWidths=[2.5*inch, 4*inch])
    paciente_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    
    story.append(paciente_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Datos del Seguro
    story.append(Paragraph("DATOS DEL SEGURO", paciente_title))
    
    datos_seguro_table = [
        ['Aseguradora:', datos_seguro.get('aseguradora', 'N/A')],
        ['Número de Póliza:', datos_seguro.get('numero_poliza', 'N/A')],
        ['Plan:', datos_seguro.get('plan_nombre', 'N/A')],
    ]
    
    seguro_table = Table(datos_seguro_table, colWidths=[2.5*inch, 4*inch])
    seguro_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    
    story.append(seguro_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Información Clínica
    story.append(Paragraph("INFORMACIÓN CLÍNICA", paciente_title))
    
    datos_clinicos_table = [
        ['Fecha de Consulta:', datos_consulta.get('fecha_consulta', fecha_actual)],
        ['Diagnóstico:', datos_consulta.get('diagnostico', 'N/A')],
        ['Código CIE-10:', datos_consulta.get('codigo_cie10', 'N/A')],
    ]
    
    if datos_consulta.get('procedimiento'):
        datos_clinicos_table.append(['Procedimiento:', datos_consulta.get('procedimiento', 'N/A')])
        if datos_consulta.get('codigo_cpt'):
            datos_clinicos_table.append(['Código CPT:', datos_consulta.get('codigo_cpt', 'N/A')])
    
    clinicos_table = Table(datos_clinicos_table, colWidths=[2.5*inch, 4*inch])
    clinicos_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey)
    ]))
    
    story.append(clinicos_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Resumen Clínico
    if datos_consulta.get('resumen_clinico') or datos_consulta.get('soap_subjetivo'):
        story.append(Paragraph("RESUMEN CLÍNICO", paciente_title))
        
        resumen_texto = datos_consulta.get('resumen_clinico', '')
        if not resumen_texto:
            # Construir resumen desde SOAP
            resumen_parts = []
            if datos_consulta.get('soap_subjetivo'):
                resumen_parts.append(f"<b>Subjetivo:</b> {datos_consulta['soap_subjetivo']}")
            if datos_consulta.get('soap_objetivo'):
                resumen_parts.append(f"<b>Objetivo:</b> {datos_consulta['soap_objetivo']}")
            if datos_consulta.get('soap_analisis'):
                resumen_parts.append(f"<b>Análisis:</b> {datos_consulta['soap_analisis']}")
            if datos_consulta.get('soap_plan'):
                resumen_parts.append(f"<b>Plan:</b> {datos_consulta['soap_plan']}")
            resumen_texto = '<br/><br/>'.join(resumen_parts)
        
        resumen_style = ParagraphStyle(
            'Resumen',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_LEFT,
            leftIndent=0.2*inch,
            spaceAfter=15
        )
        
        story.append(Paragraph(resumen_texto, resumen_style))
        story.append(Spacer(1, 0.3*inch))
    
    # Tratamiento
    if datos_consulta.get('tratamiento'):
        story.append(Paragraph("TRATAMIENTO", paciente_title))
        
        tratamiento_style = ParagraphStyle(
            'Tratamiento',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_LEFT,
            leftIndent=0.2*inch
        )
        
        story.append(Paragraph(datos_consulta.get('tratamiento', ''), tratamiento_style))
        story.append(Spacer(1, 0.3*inch))
    
    # Firma
    story.append(Spacer(1, 0.5*inch))
    
    firma_table = [
        ['', ''],
        ['_________________________', ''],
        ['Nombre y Firma del Médico', 'Fecha: ___________________']
    ]
    
    firma_table_style = Table(firma_table, colWidths=[3*inch, 3*inch])
    firma_table_style.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    story.append(firma_table_style)
    
    # Construir PDF
    doc.build(story)
    
    buffer.seek(0)
    return buffer

def generar_informe_generico(
    datos_consulta: Dict,
    datos_paciente: Dict,
    datos_seguro: Dict
) -> BytesIO:
    """
    Genera un informe médico genérico (sin formato específico de aseguradora)
    """
    return generar_informe_medico(datos_consulta, datos_paciente, datos_seguro, tipo_aseguradora='GENÉRICO')

