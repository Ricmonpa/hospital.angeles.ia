#!/bin/bash

echo "Iniciando Hospital Ángeles IA (módulo transacciones)"
echo "============================================"
echo ""

# Verificar si existe la base de datos
if [ ! -f "consultas.db" ]; then
    echo "📊 Base de datos no encontrada. Creando datos de ejemplo..."
    python3 seed_transacciones.py
    echo ""
fi

echo "✅ Base de datos lista"
echo ""
echo "🌐 Iniciando servidor Flask..."
echo "📍 Accede al módulo del contador en: http://localhost:5555/contador"
echo ""
echo "Presiona Ctrl+C para detener el servidor"
echo ""

python3 main.py
