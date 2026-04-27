"""
Carga las ponderaciones del ciclo UNCP 2026 (80 preguntas) desde un .xlsx.

Reemplaza las filas ACADEMIA de question_weights para las 5 áreas detectadas y
sube examen_preguntas_config (ACADEMIA, '*', area_id) a 80 para cada una.

Uso:
    python scripts/load_ponderaciones_uncp.py [--dry-run]
                                              [--excel "excel/NUEVA PONDERACION CICLO UNCP 2026.xlsx"]

--dry-run revierte la transacción al final, imprimiendo el plan sin tocar la BD.
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from config import Config  # noqa: E402
from models.database import configure_engine  # noqa: E402
import models  # noqa: F401, E402
from models import db  # noqa: E402

from academia.services.uncp_loader import (  # noqa: E402
    EXPECTED_AREAS,
    EXPECTED_QUESTIONS_PER_AREA,
    apply_full,
    match_db_areas,
    normalize_level,
    normalize_subject,
    parse_workbook,
    validate_parsed,
)


DEFAULT_EXCEL = os.path.join(
    ROOT, "excel", "NUEVA PONDERACION CICLO UNCP 2026.xlsx"
)


def _print_plan(parsed, matched) -> None:
    print("Plan de carga:")
    for area_id in sorted(parsed.keys()):
        info = parsed[area_id]
        db_area = matched[area_id]
        print(
            f"  AREA {area_id:>2}  Excel={info['name']!r}  ->  "
            f"BD id={db_area.id} {db_area.name!r}  ({len(info['rows'])} filas)"
        )
        for row in sorted(info["rows"], key=lambda x: x["q_start"]):
            subj = normalize_subject(row["subject_raw"])
            lvl = normalize_level(row["level_raw"])
            print(
                f"      Q{row['q_start']:>2}-{row['q_end']:>2}  "
                f"{subj:<32} {lvl:<10}  peso={row['weight']:.3f}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--excel",
        default=DEFAULT_EXCEL,
        help=f"Ruta al Excel de ponderaciones (default: {DEFAULT_EXCEL!r}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula la carga (rollback al final, sin escribir en BD).",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.excel):
        print(f"ERROR: no existe el archivo {args.excel}", file=sys.stderr)
        return 2

    print(f"Excel:    {args.excel}")
    print(f"Modo:     {'DRY-RUN (rollback al final)' if args.dry_run else 'COMMIT'}")

    parsed = parse_workbook(args.excel)
    validate_parsed(parsed)

    configure_engine(
        getattr(Config, "SQLALCHEMY_DATABASE_URI", None),
        engine_options=getattr(Config, "SQLALCHEMY_ENGINE_OPTIONS", None) or {},
    )
    print(f"BD:       {Config.SQLALCHEMY_DATABASE_URI}")

    matched = match_db_areas(parsed)
    _print_plan(parsed, matched)

    if args.dry_run:
        try:
            stats = apply_full(parsed, commit=False)
        finally:
            db.session.rollback()
        print()
        print("Resultado (DRY-RUN, revertido):")
    else:
        stats = apply_full(parsed, commit=True)
        print()
        print("Resultado:")

    print(f"  question_weights borrados:    {stats['deleted_weights']}")
    print(f"  question_weights insertados:  {stats['inserted_weights']}")
    print(
        f"  examen_preguntas_config:      {stats['cupo_areas']} áreas a "
        f"{stats['cupo_max_questions']} preguntas"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
