"""FastAPI application factory (replaces Flask create_app)."""
from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from config import Config
from models import Estudiante
from models.database import db as db_facade
from template_helpers import common_context, templates

ROOT = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging

    from sqlalchemy import inspect, or_, text

    logger = logging.getLogger("uvicorn.error")
    if (
        getattr(Config, "APP_ENV", "") == "production"
        and getattr(Config, "SECRET_KEY", "") in ("", "tu_clave_secreta")
    ):
        logger.warning(
            "APP_ENV=production pero SECRET_KEY no está definida de forma segura. "
            "Define SECRET_KEY en el entorno."
        )

    db_facade.create_all()

    inspector = inspect(db_facade.engine)
    columnas = [col["name"] for col in inspector.get_columns("estudiantes")]
    if "codigo_estudiante" not in columnas:
        db_facade.session.execute(
            text("ALTER TABLE estudiantes ADD COLUMN codigo_estudiante VARCHAR(20)")
        )
        db_facade.session.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_estudiantes_codigo_estudiante "
                "ON estudiantes(codigo_estudiante)"
            )
        )
        db_facade.session.commit()
    if "area_postula" not in columnas:
        db_facade.session.execute(
            text("ALTER TABLE estudiantes ADD COLUMN area_postula VARCHAR(100)")
        )
        db_facade.session.commit()
    if "academia_portal_password_hash" not in columnas:
        db_facade.session.execute(
            text(
                "ALTER TABLE estudiantes ADD COLUMN academia_portal_password_hash VARCHAR(255)"
            )
        )
        db_facade.session.commit()
    if "acceso_suspendido" not in columnas:
        # IF NOT EXISTS + try/except: con varios workers de uvicorn, dos pueden
        # ejecutar el ALTER a la vez en el primer arranque; así ninguno crashea.
        try:
            db_facade.session.execute(
                text(
                    "ALTER TABLE estudiantes ADD COLUMN IF NOT EXISTS "
                    "acceso_suspendido BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            db_facade.session.commit()
        except Exception as exc:  # noqa: BLE001
            db_facade.session.rollback()
            logger.warning("No se pudo agregar columna acceso_suspendido: %s", exc)

    if inspector.has_table("question_weights"):
        columnas_qw = [col["name"] for col in inspector.get_columns("question_weights")]
        if "cupo" not in columnas_qw:
            db_facade.session.execute(
                text("ALTER TABLE question_weights ADD COLUMN cupo INTEGER")
            )
            db_facade.session.execute(
                text(
                    "UPDATE question_weights SET cupo = 80 "
                    "WHERE cupo IS NULL AND (nivel = 'ACADEMIA' OR nivel IS NULL)"
                )
            )
            db_facade.session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_question_weights_cupo "
                    "ON question_weights(cupo)"
                )
            )
            db_facade.session.commit()

    def _maybe_widen_varchar(table: str, column: str, target_len: int = 100) -> None:
        """ALTER COLUMN ... TYPE VARCHAR(target_len) si la columna actual es más corta.

        Idempotente: no hace nada si la tabla/columna no existe o ya cumple.
        """
        if not inspector.has_table(table):
            return
        cols = {c["name"]: c for c in inspector.get_columns(table)}
        col = cols.get(column)
        if not col:
            return
        col_type = col.get("type")
        actual_len = getattr(col_type, "length", None) if col_type is not None else None
        if actual_len is not None and actual_len < target_len:
            db_facade.session.execute(
                text(
                    f"ALTER TABLE {table} ALTER COLUMN {column} TYPE VARCHAR({target_len})"
                )
            )
            db_facade.session.commit()

    # 'grado' guarda el nombre del programa de Academia (texto largo) además del
    # grado escolar tradicional. Ampliamos a 100 chars para aceptar nombres como
    # 'ACADEMIA 1RA SELESCCION A5 2026-1' o 'MATE DESDE CERO NK01 2026-1'.
    _maybe_widen_varchar("aulas", "grado", 100)
    _maybe_widen_varchar("estudiantes", "grado", 100)
    _maybe_widen_varchar("pension_estudiante", "estudiante_grado", 100)
    _maybe_widen_varchar("pago_pension", "estudiante_grado", 100)

    # Auto-carga ponderaciones por cupo si están ausentes y existe el Excel
    # correspondiente en ``excel/``. Esto cubre los reportes consolidados de
    # ETAs de 50 preguntas: si la tabla cupo=50 está vacía, la boleta y la
    # tabla "Calificaciones por asignatura y ETA" muestran N/A.
    try:
        from models.academia import QuestionWeight  # noqa: WPS433

        if inspector.has_table("question_weights"):
            ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
            mapping = (
                (50, os.path.join(ROOT_DIR, "excel", "50PREGUNTAS.xlsx")),
            )
            for cupo_target, xlsx_path in mapping:
                if not os.path.isfile(xlsx_path):
                    continue
                existe = (
                    db_facade.session.query(QuestionWeight.id)
                    .filter(QuestionWeight.cupo == cupo_target)
                    .first()
                )
                if existe is not None:
                    continue
                try:
                    from academia.services.uncp_loader import (
                        apply_weights as _uncp_apply_weights,
                        parse_workbook as _uncp_parse_workbook,
                        validate_parsed as _uncp_validate_parsed,
                    )

                    parsed = _uncp_parse_workbook(xlsx_path)
                    _uncp_validate_parsed(parsed, expected_questions=cupo_target)
                    _uncp_apply_weights(parsed, cupo=cupo_target)
                    logger.info(
                        "Ponderaciones cupo=%s cargadas automáticamente desde %s",
                        cupo_target,
                        os.path.basename(xlsx_path),
                    )
                except Exception as exc:  # noqa: BLE001
                    db_facade.session.rollback()
                    logger.warning(
                        "No se pudieron cargar las ponderaciones cupo=%s desde %s: %s",
                        cupo_target,
                        xlsx_path,
                        exc,
                    )
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se ejecutó la auto-carga de ponderaciones por cupo: %s", exc)

    estudiantes_actualizar = (
        Estudiante.query.filter(
            or_(
                Estudiante.codigo_estudiante.is_(None),
                Estudiante.codigo_estudiante == "",
                Estudiante.codigo_estudiante.like("EST-%"),
            )
        )
        .order_by(Estudiante.id)
        .all()
    )
    for est in estudiantes_actualizar:
        est.codigo_estudiante = Estudiante.generar_codigo_estudiante()
    if estudiantes_actualizar:
        db_facade.session.commit()

    from utils.bootstrap_admin import ensure_bootstrap_admin
    from utils.bootstrap_tipos_pago import ensure_tipos_pago_base

    ensure_bootstrap_admin(logger)
    ensure_tipos_pago_base(logger)

    yield


def create_app(config_class: type | None = None) -> FastAPI:
    """Build FastAPI app. Pass a ``config_class`` (e.g. tests' ``TestConfig``) to override ``Config`` and DB engine."""
    if config_class is not None:
        for key in dir(config_class):
            if key.isupper() and not key.startswith("_"):
                setattr(Config, key, getattr(config_class, key))
        from models.database import configure_engine

        configure_engine(
            getattr(Config, "SQLALCHEMY_DATABASE_URI", None),
            engine_options=getattr(Config, "SQLALCHEMY_ENGINE_OPTIONS", None) or {},
        )

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # Crear tablas antes de importar ``routes``: al cargarse se llama
    # ``build_academia_routers()`` → ``init_academia_module()`` y los servicios
    # consultan ``academic_areas`` / ``question_weights``. Si ``create_all`` solo
    # corre en ``lifespan``, aún no existen esas tablas en el primer arranque.
    import models  # noqa: F401 — registra todos los modelos en Base.metadata
    db_facade.create_all()

    app = FastAPI(title=getattr(Config, "APP_NAME", "Intranet"), lifespan=lifespan)

    app.add_middleware(
        SessionMiddleware,
        secret_key=Config.SECRET_KEY,
        session_cookie="session",
        same_site="lax",
        https_only=Config.SESSION_COOKIE_SECURE,
    )

    @app.middleware("http")
    async def db_session_scope(request: Request, call_next):
        try:
            return await call_next(request)
        finally:
            db_facade.session.remove()

    from routes import routers as app_routers

    for rt, prefix in app_routers:
        app.include_router(rt, prefix=prefix or "")

    app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
    app.mount(
        "/academia/static",
        StaticFiles(directory=str(ROOT / "academia" / "static")),
        name="academia_static_mount",
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        loc = None
        if exc.headers:
            loc = exc.headers.get("location") or exc.headers.get("Location")
        if exc.status_code in (302, 303, 307) and loc:
            return RedirectResponse(url=loc, status_code=303)
        if exc.status_code == 403:
            return templates.TemplateResponse(
                "errors/404.html", common_context(request), status_code=403
            )
        if exc.status_code == 404:
            return templates.TemplateResponse(
                "errors/404.html", common_context(request), status_code=404
            )
        return JSONResponse(
            {"detail": str(exc.detail)}, status_code=exc.status_code, headers=dict(exc.headers or {})
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            return await http_exception_handler(request, exc)
        try:
            db_facade.session.rollback()
        except Exception:
            pass
        return templates.TemplateResponse(
            "errors/500.html", common_context(request), status_code=500
        )

    return app


app = create_app()
