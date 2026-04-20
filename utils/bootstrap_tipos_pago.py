"""Seed inicial de Tipos de Pago.

Se ejecuta en el arranque de la aplicación (lifespan). Si la tabla
``tipos_pago`` está vacía, inserta un catálogo base común para colegios y
academias, de forma que el flujo Tipos → Conceptos → Obligaciones funcione
de inmediato en una instalación nueva.

Es idempotente: no hace nada si ya existen registros. Los usuarios
administradores pueden editar / desactivar estos tipos desde la UI.
"""
from __future__ import annotations

import logging

from config import Config
from models.database import db
from models.pagos import TipoPago


TIPOS_BASE: list[dict[str, str]] = [
    {
        "codigo": "MATRICULA",
        "nombre": "Matrícula",
        "categoria": "Escolar",
        "descripcion": "Pago único de matrícula al inicio del año escolar.",
    },
    {
        "codigo": "PENSION",
        "nombre": "Pensión",
        "categoria": "Escolar",
        "descripcion": "Pensión mensual por enseñanza regular.",
    },
    {
        "codigo": "CARNET",
        "nombre": "Carnet",
        "categoria": "Administrativo",
        "descripcion": "Carnet estudiantil de identificación.",
    },
    {
        "codigo": "COMPENDIO",
        "nombre": "Compendio",
        "categoria": "Escolar",
        "descripcion": "Material de estudio / compendio académico anual.",
    },
    {
        "codigo": "UNIFORME",
        "nombre": "Uniforme",
        "categoria": "Administrativo",
        "descripcion": "Uniforme escolar o de educación física.",
    },
    {
        "codigo": "RIFA",
        "nombre": "Rifa",
        "categoria": "Eventos",
        "descripcion": "Aporte por rifa institucional.",
    },
    {
        "codigo": "EVENTO",
        "nombre": "Evento",
        "categoria": "Eventos",
        "descripcion": "Aporte por actividad, ceremonia o evento especial.",
    },
    {
        "codigo": "CERTIFICADO",
        "nombre": "Certificado",
        "categoria": "Administrativo",
        "descripcion": "Constancias, certificados y documentos oficiales.",
    },
    {
        "codigo": "APAFA",
        "nombre": "APAFA",
        "categoria": "Administrativo",
        "descripcion": "Cuota de la Asociación de Padres de Familia.",
    },
    {
        "codigo": "EXAMEN",
        "nombre": "Examen / Simulacro",
        "categoria": "Escolar",
        "descripcion": "Pago por examen, simulacro u otra evaluación.",
    },
]


def ensure_tipos_pago_base(logger: logging.Logger | None = None) -> None:
    """Inserta los tipos de pago base si la tabla está vacía."""
    log = logger or logging.getLogger("uvicorn.error")
    if getattr(Config, "TESTING", False):
        return
    try:
        if TipoPago.query.count() > 0:
            return
        creados = 0
        for data in TIPOS_BASE:
            tipo = TipoPago(
                nombre=data["nombre"],
                codigo=data["codigo"],
                categoria=data.get("categoria"),
                descripcion=data.get("descripcion"),
                activo=True,
                usuario_registro="system",
            )
            db.session.add(tipo)
            creados += 1
        db.session.commit()
        if creados:
            log.info(
                "Catálogo inicial de Tipos de Pago creado (%d registros). Puedes editarlos desde /pagos/generales/tipos.",
                creados,
            )
    except Exception as exc:  # pragma: no cover - defensive
        db.session.rollback()
        log.warning("No se pudo inicializar el catálogo base de Tipos de Pago: %s", exc)
