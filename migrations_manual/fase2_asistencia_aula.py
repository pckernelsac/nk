"""
Migración Fase 2: Crear tablas de Asistencia por Aula
Sistema de asistencia por aula completa con justificaciones

Ejecutar: python migrations_manual/fase2_asistencia_aula.py
"""

import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db

def ejecutar_migracion():
    """Ejecuta la migración para crear las tablas de asistencia por aula"""

    print("=" * 60)
    print("MIGRACION FASE 2: Sistema de Asistencia por Aula")
    print("=" * 60)
    print()

    with app.app_context():
        try:
            print("Creando tablas de asistencia por aula...")

            # Crear todas las tablas
            db.create_all()

            print("Tablas creadas exitosamente")
            print()

            # Verificar que las tablas se crearon
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tablas = inspector.get_table_names()

            if 'registros_asistencia_aula' in tablas:
                print("Tabla 'registros_asistencia_aula' creada")
            if 'detalles_asistencia_aula' in tablas:
                print("Tabla 'detalles_asistencia_aula' creada")
            if 'justificaciones_inasistencia' in tablas:
                print("Tabla 'justificaciones_inasistencia' creada")

            print()
            print("=" * 60)
            print("MIGRACION COMPLETADA")
            print("=" * 60)
            print()
            print("Proximos pasos:")
            print("1. Accede a /asistencias/por_aula para ver asistencia por aula")
            print("2. Selecciona un aula y fecha para tomar asistencia")
            print("3. Gestiona justificaciones desde /asistencias/justificaciones")
            print()

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    ejecutar_migracion()
