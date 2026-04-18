"""
Script de migración manual para agregar campos de control de concurrencia al modelo Estudiante.
Este script debe ejecutarse UNA SOLA VEZ después de desplegar el código.

Fecha: 2026-01-10
Descripción: Agrega campos version, fecha_ultima_modificacion y ultimo_usuario_modificacion
"""

import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def upgrade():
    """
    Aplica la migración agregando los campos necesarios.
    """
    try:
        print("Iniciando migración: agregar campos de control de concurrencia a Estudiante...")

        # Importar después de ajustar el path
        from models import db, Estudiante
        from app import app
        from datetime import datetime

        # Conectar a la base de datos
        with app.app_context():
            # Verificar si los campos ya existen
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('estudiantes')]

            if 'version' in columns:
                print("⚠️  Los campos ya existen. Migración ya aplicada.")
                return

            print("📋 Agregando columnas a la tabla 'estudiantes'...")

            # Agregar columnas mediante SQL directo (SQLite)
            try:
                # Nota: SQLite tiene limitaciones con ALTER TABLE
                # Primero verificamos que la tabla existe
                with db.engine.connect() as conn:
                    # Agregar fecha_ultima_modificacion
                    try:
                        conn.execute(db.text(
                            "ALTER TABLE estudiantes ADD COLUMN fecha_ultima_modificacion DATETIME"
                        ))
                        conn.commit()
                        print("   ✓ Campo 'fecha_ultima_modificacion' agregado")
                    except Exception as e:
                        if 'duplicate column name' not in str(e).lower():
                            raise

                    # Agregar version
                    try:
                        conn.execute(db.text(
                            "ALTER TABLE estudiantes ADD COLUMN version INTEGER DEFAULT 1 NOT NULL"
                        ))
                        conn.commit()
                        print("   ✓ Campo 'version' agregado (DEFAULT 1)")
                    except Exception as e:
                        if 'duplicate column name' not in str(e).lower():
                            raise

                    # Agregar ultimo_usuario_modificacion
                    try:
                        conn.execute(db.text(
                            "ALTER TABLE estudiantes ADD COLUMN ultimo_usuario_modificacion VARCHAR(100)"
                        ))
                        conn.commit()
                        print("   ✓ Campo 'ultimo_usuario_modificacion' agregado")
                    except Exception as e:
                        if 'duplicate column name' not in str(e).lower():
                            raise

                    # Inicializar fecha_ultima_modificacion para registros existentes
                    result = conn.execute(db.text(
                        "UPDATE estudiantes SET fecha_ultima_modificacion = fecha_registro WHERE fecha_ultima_modificacion IS NULL"
                    ))
                    conn.commit()
                    print(f"   ✓ {result.rowcount} registros existentes actualizados con fecha_ultima_modificacion")

            except Exception as e:
                print(f"❌ Error ejecutando ALTER TABLE: {e}")
                raise

            print("\n✅ Migración completada exitosamente.")
            print("\n📊 Resumen:")
            print("   - Campo 'version' agregado (control de concurrencia)")
            print("   - Campo 'fecha_ultima_modificacion' agregado (auditoría)")
            print("   - Campo 'ultimo_usuario_modificacion' agregado (trazabilidad)")
            print("\n🎯 Los estudiantes ahora pueden editar su información de forma segura")
            print("   desde el portal de academia sin riesgo de pérdida de datos.")

    except Exception as e:
        print(f"\n❌ Error durante la migración: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def downgrade():
    """
    Revierte la migración eliminando los campos agregados.
    """
    try:
        print("Revirtiendo migración...")

        from app import app

        with app.app_context():
            # SQLite no soporta DROP COLUMN directamente
            print("⚠️  SQLite no soporta DROP COLUMN directamente.")
            print("   Para revertir, necesitas recrear la tabla sin estos campos.")
            print("   Esto requiere un proceso manual más complejo.")

    except Exception as e:
        print(f"❌ Error durante el downgrade: {e}")
        raise

if __name__ == '__main__':
    print("=" * 70)
    print(" " * 10 + "MIGRACIÓN DE BASE DE DATOS")
    print(" " * 5 + "Agregar control de concurrencia a Estudiante")
    print("=" * 70)
    print()
    print("Esta migración agregará los siguientes campos:")
    print("  • version (INTEGER) - Para control optimista de concurrencia")
    print("  • fecha_ultima_modificacion (DATETIME) - Para auditoría")
    print("  • ultimo_usuario_modificacion (VARCHAR) - Para trazabilidad")
    print()
    print("⚠️  IMPORTANTE: Esta operación modificará la estructura de la BD.")
    print("   Se recomienda hacer un backup antes de continuar.")
    print()

    respuesta = input("¿Deseas ejecutar la migración? (si/no): ")

    if respuesta.lower() in ['si', 's', 'yes', 'y', 'sí']:
        print()
        upgrade()
        print()
        print("=" * 70)
        print("🎉 Proceso completado. La aplicación está lista para usar.")
        print("=" * 70)
    else:
        print("\n❌ Migración cancelada por el usuario.")
        sys.exit(0)
