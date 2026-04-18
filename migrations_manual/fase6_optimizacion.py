"""
Migracion Fase 6: Optimizacion y Indices
Agrega indices de base de datos para mejorar el rendimiento

Ejecutar: python migrations_manual/fase6_optimizacion.py
"""

import sys
import os

# Agregar el directorio raiz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db

def ejecutar_migracion():
    """Ejecuta la migracion para agregar indices de rendimiento"""

    print("=" * 60)
    print("MIGRACION FASE 6: Optimizacion y Indices")
    print("=" * 60)
    print()

    with app.app_context():
        try:
            print("Agregando indices de rendimiento...")
            print()

            # Indices para matriculas
            print("Indices para matriculas:")
            try:
                db.session.execute(db.text(
                    "CREATE INDEX IF NOT EXISTS ix_matricula_estudiante_anio ON matriculas (estudiante_id, anio_escolar)"
                ))
                print("  [OK] Indice ix_matricula_estudiante_anio creado")
            except Exception as e:
                print(f"  [INFO] Indice ix_matricula_estudiante_anio: {str(e)}")

            try:
                db.session.execute(db.text(
                    "CREATE INDEX IF NOT EXISTS ix_matricula_aula_estado ON matriculas (aula_id, estado)"
                ))
                print("  [OK] Indice ix_matricula_aula_estado creado")
            except Exception as e:
                print(f"  [INFO] Indice ix_matricula_aula_estado: {str(e)}")

            print()

            # Indices para detalle_asistencia_aula
            print("Indices para detalle_asistencia_aula:")
            try:
                db.session.execute(db.text(
                    "CREATE INDEX IF NOT EXISTS ix_detalle_asist_estudiante_registro ON detalle_asistencia_aula (estudiante_id, registro_aula_id)"
                ))
                print("  [OK] Indice ix_detalle_asist_estudiante_registro creado")
            except Exception as e:
                print(f"  [INFO] Indice ix_detalle_asist_estudiante_registro: {str(e)}")

            print()

            # Indices para notas_fast_test
            print("Indices para notas_fast_test:")
            try:
                db.session.execute(db.text(
                    "CREATE INDEX IF NOT EXISTS ix_nota_fasttest_estudiante ON notas_fast_test (fast_test_id, estudiante_id)"
                ))
                print("  [OK] Indice ix_nota_fasttest_estudiante creado")
            except Exception as e:
                print(f"  [INFO] Indice ix_nota_fasttest_estudiante: {str(e)}")

            print()

            # Indices para obligaciones_pago_estudiante
            print("Indices para obligaciones_pago_estudiante:")
            try:
                db.session.execute(db.text(
                    "CREATE INDEX IF NOT EXISTS ix_obligacion_estudiante_estado ON obligaciones_pago_estudiante (estudiante_id, estado)"
                ))
                print("  [OK] Indice ix_obligacion_estudiante_estado creado")
            except Exception as e:
                print(f"  [INFO] Indice ix_obligacion_estudiante_estado: {str(e)}")

            try:
                db.session.execute(db.text(
                    "CREATE INDEX IF NOT EXISTS ix_obligacion_anio_estado ON obligaciones_pago_estudiante (anio_escolar, estado)"
                ))
                print("  [OK] Indice ix_obligacion_anio_estado creado")
            except Exception as e:
                print(f"  [INFO] Indice ix_obligacion_anio_estado: {str(e)}")

            print()

            # Indices para fast_tests
            print("Indices para fast_tests:")
            try:
                db.session.execute(db.text(
                    "CREATE INDEX IF NOT EXISTS ix_fasttest_aula_estado ON fast_tests (aula_id, estado)"
                ))
                print("  [OK] Indice ix_fasttest_aula_estado creado")
            except Exception as e:
                print(f"  [INFO] Indice ix_fasttest_aula_estado: {str(e)}")

            try:
                db.session.execute(db.text(
                    "CREATE INDEX IF NOT EXISTS ix_fasttest_anio_estado ON fast_tests (anio_escolar, estado)"
                ))
                print("  [OK] Indice ix_fasttest_anio_estado creado")
            except Exception as e:
                print(f"  [INFO] Indice ix_fasttest_anio_estado: {str(e)}")

            print()

            # Indices para pagos_generales
            print("Indices para pagos_generales:")
            try:
                db.session.execute(db.text(
                    "CREATE INDEX IF NOT EXISTS ix_pago_general_estudiante_anio ON pagos_generales (estudiante_id, anio_escolar)"
                ))
                print("  [OK] Indice ix_pago_general_estudiante_anio creado")
            except Exception as e:
                print(f"  [INFO] Indice ix_pago_general_estudiante_anio: {str(e)}")

            try:
                db.session.execute(db.text(
                    "CREATE INDEX IF NOT EXISTS ix_pago_general_estado_anio ON pagos_generales (estado, anio_escolar)"
                ))
                print("  [OK] Indice ix_pago_general_estado_anio creado")
            except Exception as e:
                print(f"  [INFO] Indice ix_pago_general_estado_anio: {str(e)}")

            print()

            # Indices para registro_asistencia_aula
            print("Indices para registro_asistencia_aula:")
            try:
                db.session.execute(db.text(
                    "CREATE INDEX IF NOT EXISTS ix_reg_asist_aula_fecha ON registro_asistencia_aula (aula_id, fecha)"
                ))
                print("  [OK] Indice ix_reg_asist_aula_fecha creado")
            except Exception as e:
                print(f"  [INFO] Indice ix_reg_asist_aula_fecha: {str(e)}")

            print()

            # Commit de todos los cambios
            db.session.commit()

            print("=" * 60)
            print("MIGRACION COMPLETADA")
            print("=" * 60)
            print()
            print("Indices creados:")
            print("  - ix_matricula_estudiante_anio")
            print("  - ix_matricula_aula_estado")
            print("  - ix_detalle_asist_estudiante_registro")
            print("  - ix_nota_fasttest_estudiante")
            print("  - ix_obligacion_estudiante_estado")
            print("  - ix_obligacion_anio_estado")
            print("  - ix_fasttest_aula_estado")
            print("  - ix_fasttest_anio_estado")
            print("  - ix_pago_general_estudiante_anio")
            print("  - ix_pago_general_estado_anio")
            print("  - ix_reg_asist_aula_fecha")
            print()
            print("Beneficios:")
            print("  - Consultas mas rapidas en listados")
            print("  - Mejor rendimiento en reportes")
            print("  - Optimizacion de filtros por estado y anio")
            print("  - Mejora en joins entre tablas")
            print()

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == '__main__':
    ejecutar_migracion()
