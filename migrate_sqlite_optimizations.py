"""
Script de migración para optimizar SQLite en producción.
Aplica índices faltantes y verifica PRAGMAs.

Uso:
    python migrate_sqlite_optimizations.py

Seguro para ejecutar múltiples veces (usa IF NOT EXISTS).
"""

from app import app
from models import db


def migrate():
    with app.app_context():
        print("=== Migración de optimización SQLite ===\n")

        # 1. Verificar PRAGMAs
        pragmas = ['journal_mode', 'busy_timeout', 'synchronous', 'cache_size',
                    'foreign_keys', 'temp_store']
        print("PRAGMAs actuales:")
        for pragma in pragmas:
            result = db.session.execute(db.text(f'PRAGMA {pragma}')).fetchone()
            print(f"  {pragma}: {result[0]}")

        # 2. Crear índices faltantes
        indices = [
            # Asistencias: consultas frecuentes de escaneo QR y reportes
            ('ix_asistencia_estudiante_tipo_fecha',
             'asistencias', '(estudiante_id, tipo, fecha_hora)'),
            ('ix_asistencia_fecha_hora',
             'asistencias', '(fecha_hora)'),
        ]

        print("\nCreando índices faltantes:")
        for nombre, tabla, columnas in indices:
            try:
                db.session.execute(db.text(
                    f'CREATE INDEX IF NOT EXISTS {nombre} ON {tabla} {columnas}'
                ))
                print(f"  {nombre} -> OK")
            except Exception as e:
                print(f"  {nombre} -> Error: {e}")

        db.session.commit()

        # 3. Verificar todos los índices
        print("\nÍndices por tabla:")
        inspector_result = db.session.execute(db.text(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )).fetchall()

        for (table_name,) in inspector_result:
            if table_name.startswith('sqlite_'):
                continue
            idx_result = db.session.execute(
                db.text(f"PRAGMA index_list('{table_name}')")
            ).fetchall()
            if idx_result:
                print(f"\n  {table_name}:")
                for idx in idx_result:
                    print(f"    - {idx[1]} (unique={idx[2]})")

        print("\n=== Migración completada ===")


if __name__ == '__main__':
    migrate()
