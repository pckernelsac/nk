"""
Migración Fase 3: Portal de Actualización de Estudiantes
Agrega campos para que estudiantes puedan actualizar sus datos

Ejecutar: python migrations_manual/fase3_portal_estudiante.py
"""

import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, Estudiante

def ejecutar_migracion():
    """Ejecuta la migración para agregar campos al modelo Estudiante"""

    print("=" * 60)
    print("MIGRACION FASE 3: Portal de Estudiantes")
    print("=" * 60)
    print()

    with app.app_context():
        try:
            print("Creando nuevos campos en tabla estudiantes...")

            # Crear todas las tablas (SQLite creará automáticamente las nuevas columnas)
            db.create_all()

            print("Campos agregados exitosamente")
            print()

            # Inicializar campos para estudiantes existentes
            print("Inicializando campos para estudiantes existentes...")

            estudiantes = Estudiante.query.all()
            count = 0

            for estudiante in estudiantes:
                # Habilitar actualización de datos por defecto
                if estudiante.puede_actualizar_datos is None:
                    estudiante.puede_actualizar_datos = True

                # Generar código de portal si tiene fecha de nacimiento
                if not estudiante.codigo_portal and estudiante.fecha_nacimiento_est:
                    estudiante.codigo_portal = estudiante.generar_codigo_portal()
                    count += 1

            db.session.commit()

            print(f"Inicializados {count} códigos de portal")
            print()
            print("=" * 60)
            print("MIGRACION COMPLETADA")
            print("=" * 60)
            print()
            print("Proximos pasos:")
            print("1. Los estudiantes pueden acceder a /portal/login")
            print("2. Login con DNI y fecha de nacimiento (DDMMYYYY)")
            print("3. Actualizar datos de contacto desde el portal")
            print()

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == '__main__':
    ejecutar_migracion()
