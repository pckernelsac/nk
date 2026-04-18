"""
Script de migración: academia/database.db → instance/escuela.db

Migra los datos de las tablas del módulo de academia (students, academic_areas,
question_weights) desde la base de datos separada a la base de datos principal.

Uso:
    python migrate_academia.py

IMPORTANTE:
    - Ejecutar DESPUÉS de haber iniciado la app al menos una vez (para que
      SQLAlchemy cree las tablas en escuela.db via db.create_all()).
    - Hacer backup de ambas bases de datos antes de ejecutar.
    - Este script es idempotente: verifica si ya hay datos antes de migrar.
"""

import sqlite3
import os
import sys
import shutil
from datetime import datetime

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACADEMIA_DB = os.path.join(BASE_DIR, 'academia', 'database.db')
MAIN_DB = os.path.join(BASE_DIR, 'instance', 'escuela.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'backups')


def create_backup():
    """Crea backups de ambas bases de datos."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if os.path.exists(MAIN_DB):
        backup_main = os.path.join(BACKUP_DIR, f'escuela_backup_{timestamp}.db')
        shutil.copy2(MAIN_DB, backup_main)
        print(f"  Backup de escuela.db: {backup_main}")

    if os.path.exists(ACADEMIA_DB):
        backup_academia = os.path.join(BACKUP_DIR, f'academia_backup_{timestamp}.db')
        shutil.copy2(ACADEMIA_DB, backup_academia)
        print(f"  Backup de database.db: {backup_academia}")


def ensure_tables_exist(conn_main):
    """Crea las tablas en la BD principal si no existen (por si no se ejecutó la app)."""
    conn_main.execute('''
        CREATE TABLE IF NOT EXISTS academic_areas (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            quiz_class_prefix TEXT NOT NULL
        )
    ''')
    conn_main.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_name TEXT,
            quiz_class TEXT,
            first_name TEXT,
            last_name TEXT,
            student_id TEXT,
            custom_id TEXT,
            earned_points REAL,
            possible_points REAL,
            percent_correct REAL,
            quiz_created TEXT,
            data_exported TEXT,
            key_version TEXT,
            responses TEXT,
            pri_keys TEXT,
            points TEXT,
            marks TEXT,
            academic_area_id INTEGER DEFAULT 1,
            FOREIGN KEY (academic_area_id) REFERENCES academic_areas(id)
        )
    ''')
    conn_main.execute('''
        CREATE TABLE IF NOT EXISTS question_weights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            academic_area_id INTEGER,
            question_start INTEGER,
            question_end INTEGER,
            subject TEXT NOT NULL,
            level TEXT NOT NULL,
            weight REAL NOT NULL,
            FOREIGN KEY (academic_area_id) REFERENCES academic_areas(id)
        )
    ''')
    conn_main.commit()


def get_table_columns(conn, table_name):
    """Obtiene las columnas de una tabla."""
    cursor = conn.execute(f'PRAGMA table_info({table_name})')
    return [row[1] for row in cursor.fetchall()]


def migrate_table(conn_academia, conn_main, table_name):
    """
    Migra datos de una tabla de academia a la BD principal.
    Verifica columnas para manejar diferencias de esquema.
    """
    # Verificar si la tabla existe en academia
    check = conn_academia.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    ).fetchone()
    if not check:
        print(f"  Tabla '{table_name}' no existe en academia DB. Saltando.")
        return 0

    # Obtener columnas de ambas tablas
    cols_academia = get_table_columns(conn_academia, table_name)
    cols_main = get_table_columns(conn_main, table_name)

    # Usar solo columnas que existen en ambas tablas
    common_cols = [c for c in cols_academia if c in cols_main]

    if not common_cols:
        print(f"  No hay columnas comunes para '{table_name}'. Saltando.")
        return 0

    # Contar registros existentes en destino
    existing_count = conn_main.execute(f'SELECT COUNT(*) FROM {table_name}').fetchone()[0]
    if existing_count > 0:
        print(f"  Tabla '{table_name}' ya tiene {existing_count} registros en destino.")
        response = input(f"  ¿Desea AGREGAR los datos de academia? (s/n): ").strip().lower()
        if response != 's':
            print(f"  Saltando '{table_name}'.")
            return 0

    # Leer datos de academia
    cols_str = ', '.join(common_cols)
    rows = conn_academia.execute(f'SELECT {cols_str} FROM {table_name}').fetchall()

    if not rows:
        print(f"  Tabla '{table_name}' está vacía en academia. Nada que migrar.")
        return 0

    # Insertar en destino
    placeholders = ', '.join(['?' for _ in common_cols])

    # Para academic_areas y question_weights, usar INSERT OR REPLACE para evitar duplicados por ID
    if table_name in ('academic_areas', 'question_weights'):
        insert_sql = f'INSERT OR REPLACE INTO {table_name} ({cols_str}) VALUES ({placeholders})'
    else:
        insert_sql = f'INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})'

    count = 0
    for row in rows:
        try:
            conn_main.execute(insert_sql, tuple(row))
            count += 1
        except sqlite3.IntegrityError as e:
            print(f"    Registro duplicado saltado: {e}")
            continue

    conn_main.commit()
    return count


def main():
    print("=" * 60)
    print("MIGRACIÓN: academia/database.db → instance/escuela.db")
    print("=" * 60)

    # Verificar que existe la BD de academia
    if not os.path.exists(ACADEMIA_DB):
        print(f"\nERROR: No se encontró la base de datos de academia en:")
        print(f"  {ACADEMIA_DB}")
        print("Nada que migrar.")
        sys.exit(1)

    # Verificar que existe la BD principal
    if not os.path.exists(MAIN_DB):
        print(f"\nERROR: No se encontró la base de datos principal en:")
        print(f"  {MAIN_DB}")
        print("Ejecute 'python init_db.py' primero o inicie la app.")
        sys.exit(1)

    # Crear backups
    print("\n1. Creando backups...")
    create_backup()

    # Conectar a ambas bases de datos
    print("\n2. Conectando a las bases de datos...")
    conn_academia = sqlite3.connect(ACADEMIA_DB)
    conn_academia.row_factory = sqlite3.Row
    conn_main = sqlite3.connect(MAIN_DB)
    conn_main.row_factory = sqlite3.Row

    # Asegurar que las tablas existen en destino
    print("\n3. Verificando tablas en destino...")
    ensure_tables_exist(conn_main)

    # Migrar tablas en orden (academic_areas primero por FK)
    tables = ['academic_areas', 'question_weights', 'students']

    print("\n4. Migrando datos...")
    total_migrated = 0

    for table in tables:
        print(f"\n  --- {table} ---")
        count = migrate_table(conn_academia, conn_main, table)
        print(f"  Migrados: {count} registros")
        total_migrated += count

    # Cerrar conexiones
    conn_academia.close()
    conn_main.close()

    # Resumen
    print("\n" + "=" * 60)
    print(f"MIGRACIÓN COMPLETADA")
    print(f"  Total de registros migrados: {total_migrated}")
    print(f"  Base de datos destino: {MAIN_DB}")
    print(f"\nNOTA: La base de datos de academia original ({ACADEMIA_DB})")
    print(f"se mantiene intacta. Puede eliminarla manualmente cuando")
    print(f"verifique que todo funciona correctamente.")
    print("=" * 60)


if __name__ == '__main__':
    main()
