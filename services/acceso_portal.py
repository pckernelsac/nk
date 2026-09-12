# services/acceso_portal.py
"""Reglas de acceso de los estudiantes al portal según su matrícula.

Un alumno deja de entrar al portal cuando su matrícula ya no corresponde al
ciclo en curso (retirado, trasladado, o matriculado sólo en años anteriores).
Quien nunca tuvo matrícula registrada NO se bloquea: puede ser un alumno
vigente al que todavía no le registraron la matrícula, y cerrarle el portal por
un dato faltante es peor que dejarlo pasar.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable

from models import db
from models.configuracion import ConfiguracionSistema
from models.matricula import Matricula

MSG_SIN_MATRICULA = (
    "No figuras matriculado en el ciclo {anio}. "
    "Acércate a la administración para regularizar tu matrícula."
)


def anio_academico_actual() -> str:
    """Año del ciclo en curso: el configurado en el sistema, si no el del reloj."""
    try:
        config = ConfiguracionSistema.query.first()
    except Exception:
        config = None
    crudo = str(getattr(config, "anio_academico_actual", "") or "")
    # El campo es texto libre ("2026", "2026-2027", "Ciclo 2026"): basta el año.
    match = re.search(r"\d{4}", crudo)
    return match.group(0) if match else str(datetime.now().year)


def ids_sin_matricula_vigente(
    estudiante_ids: Iterable[int] | None = None, anio: str | None = None
) -> set[int]:
    """IDs con matrícula registrada pero ninguna activa en el ciclo indicado.

    Con ``estudiante_ids`` la consulta se limita a esos alumnos (para marcar una
    página del listado); sin él abarca toda la base.
    """
    anio = str(anio or anio_academico_actual())
    ids = list(estudiante_ids) if estudiante_ids is not None else None
    if ids is not None and not ids:
        return set()

    con_alguna = db.session.query(Matricula.estudiante_id).distinct()
    vigentes = (
        db.session.query(Matricula.estudiante_id)
        .filter(Matricula.estado == "activo", Matricula.anio_escolar == anio)
        .distinct()
    )
    if ids is not None:
        con_alguna = con_alguna.filter(Matricula.estudiante_id.in_(ids))
        vigentes = vigentes.filter(Matricula.estudiante_id.in_(ids))

    return {fila[0] for fila in con_alguna if fila[0]} - {
        fila[0] for fila in vigentes if fila[0]
    }


def sin_matricula_vigente(estudiante, anio: str | None = None) -> bool:
    """True si hay que cerrarle el portal al estudiante por matrícula no vigente.

    Best-effort: ante un fallo de BD devuelve False, para no dejar a nadie fuera
    por un error transitorio.
    """
    est_id = getattr(estudiante, "id", None)
    if not est_id:
        return False
    try:
        return est_id in ids_sin_matricula_vigente([est_id], anio)
    except Exception:
        return False


def mensaje_sin_matricula(anio: str | None = None) -> str:
    """Mensaje que ve el alumno al que se le niega el ingreso."""
    return MSG_SIN_MATRICULA.format(anio=anio or anio_academico_actual())
