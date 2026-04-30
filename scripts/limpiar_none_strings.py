"""
Limpia strings basura ('None', 'NULL', 'nan', 'N/A'...) en columnas de
estudiantes que se contaminaron por imports/exports de Excel.

Por defecto corre en --dry-run y solo reporta cuántas filas se afectarían
por columna. Para aplicar los UPDATEs:

    python scripts/limpiar_none_strings.py --apply

Tokens normalizados a NULL (case-insensitive, tras trim):
    'none', 'null', 'nan', 'n/a', 'na', '#n/a'
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from sqlalchemy import String, func, update  # noqa: E402

from config import Config  # noqa: E402
from models.database import configure_engine  # noqa: E402
import models  # noqa: F401, E402
from models import db  # noqa: E402
from models.estudiante import Estudiante  # noqa: E402

JUNK_TOKENS = ("none", "null", "nan", "n/a", "na", "#n/a")


def _string_columns():
    """Devuelve las columnas de Estudiante que son tipo String."""
    cols = []
    for col in Estudiante.__table__.columns:
        if isinstance(col.type, String):
            cols.append(col)
    return cols


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica los UPDATEs (por defecto solo reporta).",
    )
    args = parser.parse_args()

    configure_engine()
    session = db.session

    cols = _string_columns()
    print(f"Inspeccionando {len(cols)} columnas string en estudiantes...")
    print(f"Tokens basura: {JUNK_TOKENS}")
    print()

    total_filas = 0
    afectados_por_col: list[tuple[str, int]] = []

    for col in cols:
        # filas donde lower(trim(col)) está en la lista de tokens
        cond = func.lower(func.trim(col)).in_(JUNK_TOKENS)
        n = session.query(Estudiante).filter(cond).count()
        if n:
            afectados_por_col.append((col.name, n))
            total_filas += n

    if not afectados_por_col:
        print("Nada para limpiar — no hay strings basura en estudiantes.")
        return 0

    print("Columnas afectadas:")
    for name, n in afectados_por_col:
        print(f"  - {name}: {n} fila(s)")
    print(f"\nTotal de actualizaciones de celdas: {total_filas}")

    if not args.apply:
        print("\n[DRY-RUN] No se modificó nada. Re-ejecutar con --apply para aplicar.")
        return 0

    print("\nAplicando UPDATEs...")
    actualizados = 0
    for col in cols:
        cond = func.lower(func.trim(col)).in_(JUNK_TOKENS)
        stmt = update(Estudiante).where(cond).values({col.name: None})
        result = session.execute(stmt)
        rc = result.rowcount or 0
        if rc:
            print(f"  - {col.name}: {rc} fila(s) actualizadas")
            actualizados += rc

    session.commit()
    print(f"\nOK — {actualizados} celda(s) limpiadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
