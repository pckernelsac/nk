"""
Migración Fase 1: Crear tablas de Aulas y Matrículas
Resuelve el problema de estudiantes matriculados en múltiples turnos

Ejecutar: python migrations_manual/fase1_crear_aulas.py
"""

import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db

def ejecutar_migracion():
    """Ejecuta la migración para crear las tablas de aulas y matrículas"""

    print("=" * 60)
    print("MIGRACIÓN FASE 1: Sistema de Aulas")
    print("=" * 60)
    print()

    with app.app_context():
        try:
            print("📋 Verificando tablas existentes...")

            # Verificar si las tablas ya existen
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tablas_existentes = inspector.get_table_names()

            if 'aulas' in tablas_existentes:
                print("⚠️  La tabla 'aulas' ya existe")
                respuesta = input("¿Desea eliminarla y recrearla? (s/n): ")
                if respuesta.lower() != 's':
                    print("❌ Migración cancelada")
                    return

                # Eliminar tablas en orden (primero matriculas por FK)
                print("🗑️  Eliminando tablas existentes...")
                db.session.execute(db.text('DROP TABLE IF EXISTS matriculas'))
                db.session.execute(db.text('DROP TABLE IF EXISTS aulas'))
                db.session.commit()
                print("✅ Tablas eliminadas")

            print()
            print("🔨 Creando tablas nuevas...")

            # Crear todas las tablas (solo creará las que no existan)
            db.create_all()

            print("✅ Tablas creadas exitosamente:")
            print("   - aulas")
            print("   - matriculas")
            print()

            # Verificar estructura de la tabla aulas
            print("📊 Estructura de tabla 'aulas':")
            columns = inspector.get_columns('aulas')
            for col in columns:
                print(f"   - {col['name']}: {col['type']}")
            print()

            # Verificar estructura de la tabla matriculas
            print("📊 Estructura de tabla 'matriculas':")
            columns = inspector.get_columns('matriculas')
            for col in columns:
                print(f"   - {col['name']}: {col['type']}")
            print()

            print("=" * 60)
            print("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
            print("=" * 60)
            print()
            print("Próximos pasos:")
            print("1. Accede a /aulas/lista para ver el módulo de aulas")
            print("2. Usa /aulas/migrar para migrar datos existentes")
            print("3. Crea aulas manualmente desde /aulas/crear")
            print()

        except Exception as e:
            print()
            print("=" * 60)
            print("❌ ERROR EN LA MIGRACIÓN")
            print("=" * 60)
            print(f"Error: {str(e)}")
            print()
            import traceback
            traceback.print_exc()

            # Rollback en caso de error
            db.session.rollback()


if __name__ == '__main__':
    ejecutar_migracion()
