"""Aplica UNCP 2026 a la BD: cupo 80 + ponderaciones por área (rangos 1..80).

Uso:
    venv\\Scripts\\activate
    python bump_cupo_academia_a_80.py

Hace dos cosas (idempotentes):

1. Sube a 80 el ``max_questions`` de las filas
   ``examen_preguntas_config`` con ACADEMIA o SECUNDARIA 5° cuyo valor actual
   sea menor que 80 (no baja valores ya configurados por encima).

2. Si encuentra ``excel/NUEVA PONDERACION CICLO UNCP 2026.xlsx``, reemplaza
   ``question_weights`` ACADEMIA con los rangos 1..80 del Excel (vía
   ``apply_full``). Sin esto, los puntajes de Conocimientos / Aptitud en la
   boleta PDF solo cubrirían las primeras 50 preguntas (rangos legacy) y las
   51..80 se contarían como en blanco.

Importante: los registros académicos ya cargados con 50 entradas en pri_keys
siguen guardados con 50 — la boleta de esos quizzes solo mostrará 80
preguntas si vuelves a subir el archivo del quiz original después de correr
este script.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from config import Config  # noqa: E402
from models.database import configure_engine  # noqa: E402
import models  # noqa: F401, E402  (registra modelos)
from models import db  # noqa: E402
from models.academia import ExamenPreguntasConfig  # noqa: E402

TARGET = 80
UNCP_EXCEL = os.path.join(ROOT, "excel", "NUEVA PONDERACION CICLO UNCP 2026.xlsx")


def _bump_cupo() -> int:
    rows = ExamenPreguntasConfig.query.all()
    bumped = 0
    for row in rows:
        niv = (row.nivel or "").upper()
        grado = (row.grado or "*")
        es_academia = niv == "ACADEMIA"
        es_sec5 = niv == "SECUNDARIA" and grado == "5"
        if not (es_academia or es_sec5):
            continue
        if (row.max_questions or 0) < TARGET:
            old = row.max_questions
            row.max_questions = TARGET
            bumped += 1
            print(
                f"  bump  nivel={niv:<10} grado={grado:<3} "
                f"area_id={row.academic_area_id}  {old} -> {TARGET}"
            )
    db.session.commit()
    print(f"  Filas examen_preguntas_config revisadas: {len(rows)}. "
          f"Actualizadas: {bumped}.")
    return bumped


def _load_uncp_weights() -> None:
    if not os.path.isfile(UNCP_EXCEL):
        print(
            f"  AVISO: no se encontró {UNCP_EXCEL!r}; "
            f"ponderaciones NO actualizadas."
        )
        print(
            "         Sin esto, conocimientos/aptitud en la boleta solo cubren "
            "las primeras 50 preguntas."
        )
        return

    from academia.services.uncp_loader import (
        apply_full,
        parse_workbook,
        validate_parsed,
    )

    print(f"  Excel: {UNCP_EXCEL}")
    parsed = parse_workbook(UNCP_EXCEL)
    validate_parsed(parsed)
    stats = apply_full(parsed, commit=True)
    print(
        f"  question_weights borrados:    {stats['deleted_weights']}"
    )
    print(
        f"  question_weights insertados:  {stats['inserted_weights']}"
    )
    print(
        f"  examen_preguntas_config:      {stats['cupo_areas']} áreas a "
        f"{stats['cupo_max_questions']} preguntas"
    )


def main() -> None:
    configure_engine(
        getattr(Config, "SQLALCHEMY_DATABASE_URI", None),
        engine_options=getattr(Config, "SQLALCHEMY_ENGINE_OPTIONS", None) or {},
    )
    print(f"BD: {Config.SQLALCHEMY_DATABASE_URI}\n")

    print("[1/2] Bump cupo de preguntas (ACADEMIA + SECUNDARIA 5°) -> 80")
    _bump_cupo()

    print("\n[2/2] Carga ponderaciones UNCP 2026 (rangos 1..80)")
    _load_uncp_weights()

    print("\nListo.")


if __name__ == "__main__":
    main()
