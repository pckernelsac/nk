"""Sube a 80 el cupo de preguntas para ACADEMIA y SECUNDARIA 5° (UNCP 2026).

Uso:
    venv\\Scripts\\activate
    python bump_cupo_academia_a_80.py

Solo TOCA filas cuyo max_questions actual sea menor a 80; nunca baja valores
ya configurados manualmente por encima de 80. Después de correrlo, los
quizzes que se suban serán guardados con 80 PriKeys/Stu (y la boleta PDF
mostrará las 80 preguntas).

Importante: los registros académicos ya cargados con 50 preguntas siguen
guardados con 50 — la boleta de esos quizzes solo mostrará 80 si vuelves a
subir el archivo del quiz después de correr este script.
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


def main() -> None:
    configure_engine(
        getattr(Config, "SQLALCHEMY_DATABASE_URI", None),
        engine_options=getattr(Config, "SQLALCHEMY_ENGINE_OPTIONS", None) or {},
    )
    print(f"Usando BD: {Config.SQLALCHEMY_DATABASE_URI}")

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
    print(f"\nFilas revisadas: {len(rows)}. Filas actualizadas: {bumped}.")


if __name__ == "__main__":
    main()
