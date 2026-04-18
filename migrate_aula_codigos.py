"""
Migración: Actualizar códigos de aulas para incluir año escolar.

Resuelve el bug donde aulas de diferentes años colisionan porque el código
no incluía el año. Ahora el formato es: "5S-A-M-26" (con sufijo de año).

Uso:
    python migrate_aula_codigos.py

IMPORTANTE: Hacer backup de la base de datos antes de ejecutar.
"""

import sqlite3
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_DB = os.path.join(BASE_DIR, 'instance', 'escuela.db')


def migrate():
    if not os.path.exists(MAIN_DB):
        print(f"Base de datos no encontrada: {MAIN_DB}")
        sys.exit(1)

    conn = sqlite3.connect(MAIN_DB)
    cursor = conn.cursor()

    try:
        # 1. Eliminar el índice único global de codigo si existe
        try:
            cursor.execute("DROP INDEX IF EXISTS ix_aulas_codigo")
        except Exception:
            pass

        # 2. Obtener todas las aulas y actualizar sus códigos
        cursor.execute("SELECT id, nivel, grado, seccion, turno, anio_escolar, codigo FROM aulas")
        aulas = cursor.fetchall()

        print(f"Encontradas {len(aulas)} aulas para actualizar...")

        for aula_id, nivel, grado, seccion, turno, anio_escolar, codigo_actual in aulas:
            # Generar nuevo código con año
            nivel_lower = nivel.lower()
            if 'primaria' in nivel_lower:
                nivel_abrev = 'P'
            elif 'inicial' in nivel_lower:
                nivel_abrev = 'I'
            elif 'academia' in nivel_lower:
                nivel_abrev = 'AC'
            else:
                nivel_abrev = 'S'

            grado_num = ''.join(filter(str.isdigit, grado))
            if not grado_num:
                grado_clean = grado.upper().replace(' ', '')
                grado_num = grado_clean[:6] if len(grado_clean) > 6 else grado_clean

            turno_abrev = turno[0].upper() if turno else 'M'
            anio_sufijo = str(anio_escolar)[-2:] if anio_escolar else ''

            nuevo_codigo = f"{grado_num}{nivel_abrev}-{seccion.upper()}-{turno_abrev}-{anio_sufijo}"

            if nuevo_codigo != codigo_actual:
                print(f"  Aula {aula_id}: '{codigo_actual}' -> '{nuevo_codigo}'")
                cursor.execute(
                    "UPDATE aulas SET codigo = ? WHERE id = ?",
                    (nuevo_codigo, aula_id)
                )

                # Actualizar matrículas que tienen el código desnormalizado
                cursor.execute(
                    "UPDATE matriculas SET aula_codigo = ? WHERE aula_id = ?",
                    (nuevo_codigo, aula_id)
                )

        conn.commit()
        print(f"\nMigración completada exitosamente.")
        print("Los códigos de aulas ahora incluyen el año escolar.")

    except Exception as e:
        conn.rollback()
        print(f"Error durante la migración: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    print("=== Migración de códigos de aulas ===")
    print(f"Base de datos: {MAIN_DB}")
    migrate()
