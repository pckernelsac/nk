"""
Migración de datos SQLite → PostgreSQL para la Intranet NK.

Uso típico:

    # 1) Instalar dependencias (incluye psycopg v3)
    pip install -r requirements.txt

    # 2) Ejecutar la migración (el destino se crea vacío si no existen las tablas)
    python migrate_sqlite_to_postgres.py \
        --source sqlite:///instance/escuela.db \
        --target postgresql+psycopg://intranet:intranet@localhost:5432/intranet

    # Modo de prueba (no escribe nada):
    python migrate_sqlite_to_postgres.py --target <uri> --dry-run

    # Solo la tabla estudiantes (no copia asistencias, pensiones, etc.):
    python migrate_sqlite_to_postgres.py --target <uri> --only estudiantes
    # Si la tabla destino ya tiene filas y quieres reemplazarla por la de SQLite:
    python migrate_sqlite_to_postgres.py --target <uri> --only estudiantes --truncate

Si se omiten ``--source``/``--target`` se leen de las variables de entorno
``SOURCE_DATABASE_URL`` y ``TARGET_DATABASE_URL``. Si tampoco están definidas,
se usa la URI de SQLite por defecto del proyecto como fuente.

Qué hace:
  * Crea todas las tablas en destino usando los metadatos de los modelos
    SQLAlchemy del proyecto (``Base.metadata``).
  * Copia los datos tabla por tabla respetando el orden de dependencias
    (``metadata.sorted_tables``).
  * Reinicia las secuencias (``serial``/``identity``) en PostgreSQL al
    ``MAX(id) + 1`` para tablas con PK entero llamada ``id``.

Recomendaciones:
  * Haz backup de ``instance/escuela.db`` antes de ejecutar.
  * Usa una BD PostgreSQL vacía. Si ya tiene datos, pasa ``--truncate`` para
    vaciar las tablas destino antes de insertar.
  * Con ``--only estudiantes``, ``--truncate`` solo afecta a ``estudiantes``.
    Si en Postgres ya hay estudiantes y no usas ``--truncate``, los ``INSERT``
    pueden fallar por ``id`` o ``codigo_estudiante`` duplicados.
  * Si la BD SQLite tiene columnas que faltan en el ORM actual, primero
    ejecuta los scripts incrementales de ``migrations/`` o la app una vez
    (el ``lifespan`` aplica ``ALTER TABLE ADD COLUMN`` donde corresponde).
"""
from __future__ import annotations

import argparse
import os
import sys
from contextlib import contextmanager
from typing import Iterable

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlalchemy import MetaData, create_engine, inspect, select, text  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

# Importar modelos para poblar Base.metadata con todas las tablas del proyecto.
import models  # noqa: F401, E402
from models import Base  # noqa: E402

DEFAULT_SOURCE = f"sqlite:///{os.path.join(ROOT, 'instance', 'escuela.db')}"
BATCH_SIZE = 500


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migra datos de SQLite a PostgreSQL usando los modelos del proyecto.",
    )
    parser.add_argument(
        "--source",
        default=os.environ.get("SOURCE_DATABASE_URL", DEFAULT_SOURCE),
        help="URI SQLAlchemy de la BD origen (por defecto: instance/escuela.db).",
    )
    parser.add_argument(
        "--target",
        default=os.environ.get("TARGET_DATABASE_URL"),
        help="URI SQLAlchemy de la BD destino (PostgreSQL). Obligatoria.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Tamaño del lote de inserción (por defecto: {BATCH_SIZE}).",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="TRUNCATE de las tablas destino antes de insertar (usa con cuidado).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No escribe en destino: solo imprime qué haría.",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        default=None,
        metavar="TABLA",
        help='Migra solo las tablas indicadas (por nombre), ej. "estudiantes".',
    )
    parser.add_argument(
        "--skip",
        nargs="*",
        default=None,
        metavar="TABLA",
        help="Omite las tablas indicadas.",
    )
    return parser.parse_args()


def _normalize_target(uri: str) -> str:
    """Acepta ``postgres://``/``postgresql://`` y los normaliza a psycopg v3."""
    if uri.startswith("postgres://"):
        return "postgresql+psycopg://" + uri[len("postgres://"):]
    if uri.startswith("postgresql://"):
        return "postgresql+psycopg://" + uri[len("postgresql://"):]
    return uri


@contextmanager
def _engine_context(uri: str, *, sqlite_readonly: bool = False) -> Iterable[Engine]:
    kwargs: dict = {"future": True}
    if uri.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(uri, **kwargs)
    try:
        yield engine
    finally:
        engine.dispose()


def _iter_batches(rows: list[dict], size: int):
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def _reset_postgres_sequences(target: Engine, tables) -> None:
    """Pone las secuencias al MAX(id)+1 tras la copia (si existen)."""
    if target.dialect.name != "postgresql":
        return
    with target.begin() as conn:
        for table in tables:
            pk_cols = list(table.primary_key.columns)
            if len(pk_cols) != 1:
                continue
            pk = pk_cols[0]
            if pk.name != "id":
                continue
            # pg_get_serial_sequence detecta tanto SERIAL como IDENTITY
            sql = text(
                """
                SELECT setval(
                    pg_get_serial_sequence(:tbl, :col),
                    COALESCE((SELECT MAX(id) FROM "%s"), 0) + 1,
                    false
                )
                """
                % table.name
            )
            try:
                conn.execute(sql, {"tbl": table.name, "col": "id"})
            except Exception as exc:  # noqa: BLE001
                print(f"  [seq] {table.name}: no se pudo ajustar secuencia ({exc})")


def _truncate_target_tables(target: Engine, tables) -> None:
    if target.dialect.name != "postgresql":
        # Para SQLite/MySQL usar DELETE simple
        with target.begin() as conn:
            for table in reversed(list(tables)):
                conn.execute(table.delete())
        return
    # En Postgres TRUNCATE ... CASCADE es mucho más rápido
    names = ", ".join(f'"{t.name}"' for t in tables)
    with target.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


def migrate(
    source_uri: str,
    target_uri: str,
    *,
    batch_size: int = BATCH_SIZE,
    truncate: bool = False,
    dry_run: bool = False,
    only: list[str] | None = None,
    skip: list[str] | None = None,
) -> None:
    target_uri = _normalize_target(target_uri)
    print(f"Origen : {source_uri}")
    print(f"Destino: {target_uri}")
    if dry_run:
        print("*** DRY RUN: no se escribirá en destino ***")

    only_set = set(only) if only else None
    skip_set = set(skip) if skip else set()

    with _engine_context(source_uri) as src, _engine_context(target_uri) as dst:
        if dst.dialect.name not in ("postgresql",):
            print(
                f"ADVERTENCIA: el destino no es PostgreSQL ({dst.dialect.name!r}). "
                "El script está pensado para Postgres; puede funcionar en otros "
                "motores pero el reseteo de secuencias se omitirá."
            )

        # 1) Crear el esquema en destino a partir de los modelos del proyecto.
        print("\n[1/3] Creando tablas en destino si no existen...")
        if not dry_run:
            Base.metadata.create_all(bind=dst)
        print("     OK")

        src_inspector = inspect(src)
        src_tables = set(src_inspector.get_table_names())

        # 2) Copiar datos respetando FKs: orden topológico de metadatos del proyecto.
        print("\n[2/3] Copiando filas por tabla...")
        migratable = [
            t for t in Base.metadata.sorted_tables
            if t.name in src_tables
            and (only_set is None or t.name in only_set)
            and t.name not in skip_set
        ]

        if truncate and migratable and not dry_run:
            print("     TRUNCATE tablas destino...")
            _truncate_target_tables(dst, migratable)

        # Para leer por tabla, armamos un SELECT reflejando las columnas reales
        # del origen (útil si SQLite tiene columnas extra que el ORM sí conoce).
        src_meta = MetaData()
        src_meta.reflect(bind=src, only=[t.name for t in migratable])

        total_rows = 0
        for table in migratable:
            src_table = src_meta.tables.get(table.name)
            if src_table is None:
                print(f"  - {table.name}: (no existe en origen, se omite)")
                continue

            common_cols = [c.name for c in table.columns if c.name in src_table.c]
            if not common_cols:
                print(f"  - {table.name}: sin columnas comunes, se omite")
                continue

            with src.connect() as sconn:
                result = sconn.execute(
                    select(*[src_table.c[name] for name in common_cols])
                )
                rows = [dict(r._mapping) for r in result]

            n = len(rows)
            total_rows += n
            if n == 0:
                print(f"  - {table.name}: 0 filas")
                continue

            if dry_run:
                print(f"  - {table.name}: {n} filas (dry-run, no insertadas)")
                continue

            # Insertar por lotes usando la definición de tabla del ORM destino
            # para que SQLAlchemy aplique el casting adecuado de tipos.
            dst_table = table
            with dst.begin() as dconn:
                for batch in _iter_batches(rows, batch_size):
                    # Si la fila tiene claves ausentes en el ORM destino, se filtran
                    clean_batch = [
                        {k: v for k, v in row.items() if k in dst_table.c}
                        for row in batch
                    ]
                    dconn.execute(dst_table.insert(), clean_batch)
            print(f"  + {table.name}: {n} filas")

        print(f"\n     Total filas copiadas: {total_rows}")

        # 3) Reajustar secuencias en Postgres.
        print("\n[3/3] Reajustando secuencias en destino...")
        if not dry_run:
            _reset_postgres_sequences(dst, migratable)
        print("     OK")

    print("\nMigración completada.")


def main() -> int:
    args = _parse_args()
    if not args.target:
        print(
            "ERROR: falta URI destino. Pasa --target o define TARGET_DATABASE_URL.",
            file=sys.stderr,
        )
        return 2
    try:
        migrate(
            source_uri=args.source,
            target_uri=args.target,
            batch_size=args.batch_size,
            truncate=args.truncate,
            dry_run=args.dry_run,
            only=args.only,
            skip=args.skip,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"\nFALLO: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
