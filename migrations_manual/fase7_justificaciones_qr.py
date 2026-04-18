"""
Migracion Fase 7: Rediseño de Justificaciones para sistema QR
Cambia el modelo JustificacionInasistencia para vincularse directamente
a estudiante_id + fecha en lugar de detalle_asistencia_id

Ejecutar: python migrations_manual/fase7_justificaciones_qr.py
"""

import sys
import os

# Agregar el directorio raiz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db

def ejecutar_migracion():
    """Ejecuta la migracion para rediseñar justificaciones"""

    print("=" * 60)
    print("MIGRACION FASE 7: Justificaciones para sistema QR")
    print("=" * 60)
    print()

    with app.app_context():
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(db.engine)
            tablas = inspector.get_table_names()

            if 'justificaciones_inasistencia' in tablas:
                # Verificar si ya tiene la columna nueva
                columnas = [c['name'] for c in inspector.get_columns('justificaciones_inasistencia')]

                if 'estudiante_id' in columnas and 'detalle_asistencia_id' not in columnas:
                    print("La tabla ya fue migrada. No se requieren cambios.")
                    return

                print("Eliminando tabla antigua justificaciones_inasistencia...")
                db.session.execute(text("DROP TABLE IF EXISTS justificaciones_inasistencia"))
                db.session.commit()
                print("  OK - Tabla eliminada")

            print("Creando nueva tabla justificaciones_inasistencia...")
            db.create_all()
            print("  OK - Tabla creada con nuevo esquema")
            print()

            # Verificar
            inspector = inspect(db.engine)
            columnas = [c['name'] for c in inspector.get_columns('justificaciones_inasistencia')]
            print(f"Columnas de la nueva tabla: {columnas}")
            print()
            print("Migracion completada exitosamente!")

        except Exception as e:
            db.session.rollback()
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    ejecutar_migracion()
