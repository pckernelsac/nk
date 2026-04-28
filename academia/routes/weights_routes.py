# -*- coding: utf-8 -*-
"""
Administración manual de ponderaciones (question_weights) para PDFs y cálculos de academia.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from urllib.parse import quote

from academia.services.uncp_loader import (
    apply_weights as uncp_apply_weights,
    parse_workbook as uncp_parse_workbook,
    validate_parsed as uncp_validate_parsed,
)
from config import Config
from dependencies import require_roles
from template_helpers import add_flash, common_context, csrf_ok, templates

router = APIRouter()


def _rows_from_form(form) -> List[Dict[str, Any]]:
    starts = form.getlist("q_start")
    ends = form.getlist("q_end")
    subjects = form.getlist("q_subject")
    levels = form.getlist("q_level")
    weights = form.getlist("q_weight")
    n = max(len(starts), len(ends), len(subjects), len(levels), len(weights))
    rows: List[Dict[str, Any]] = []
    for i in range(n):
        s = (starts[i] if i < len(starts) else "") or ""
        s = s.strip()
        if not s:
            continue
        rows.append(
            {
                "question_start": s,
                "question_end": (ends[i] if i < len(ends) else "") or "",
                "subject": (subjects[i] if i < len(subjects) else "") or "",
                "level": (levels[i] if i < len(levels) else "") or "",
                "weight": (weights[i] if i < len(weights) else "") or "",
            }
        )
    return rows


ACADEMIA_CUPOS = (20, 50, 80)
AREA_AGNOSTIC_CUPOS = (20,)


def _normalize_cupo(raw: Any, default: int = 80) -> int:
    try:
        c = int(raw)
    except (TypeError, ValueError):
        return default
    return c if c in ACADEMIA_CUPOS else default


def init_weights_routes(academic_service):
    @router.get("/ponderaciones", name="academia_weights.index")
    def ponderaciones_get(
        request: Request, _user_id: int = Depends(require_roles("administrador"))
    ):
        mode = (request.query_params.get("mode") or "area").strip()
        if mode not in ("area", "nivel"):
            mode = "area"
        area_id = int(request.query_params.get("area_id") or 1)
        cupo = _normalize_cupo(request.query_params.get("cupo"))
        nivel = (request.query_params.get("nivel") or "PRIMARIA").strip()
        if nivel not in ("INICIAL", "PRIMARIA", "SECUNDARIA"):
            nivel = "PRIMARIA"
        grado = (request.query_params.get("grado") or "1").strip()

        areas = academic_service.get_all_academic_areas()
        if mode == "area":
            filas = academic_service.list_question_weights_for_area(area_id, cupo=cupo)
        else:
            filas = academic_service.list_question_weights_for_nivel_grado(nivel, grado)

        max_rows = max(32, cupo) if mode == "area" else 32
        while len(filas) < max_rows:
            filas.append(
                {
                    "question_start": "",
                    "question_end": "",
                    "subject": "",
                    "level": "",
                    "weight": "",
                }
            )
        filas = filas[:max_rows]

        base = str(request.url_for("academia_weights.index"))
        tab_area_href = f"{base}?mode=area&area_id={area_id}&cupo={cupo}"
        tab_nivel_href = f"{base}?mode=nivel&nivel={quote(nivel)}&grado={quote(grado)}"
        cupo_tabs = [
            (c, f"{base}?mode=area&area_id={area_id}&cupo={c}") for c in ACADEMIA_CUPOS
        ]

        if mode == "area":
            max_preguntas = cupo
        else:
            max_preguntas = academic_service.get_max_questions(nivel, grado, None)

        return templates.TemplateResponse(
            "academia/ponderaciones.html",
            common_context(
                request,
                mode=mode,
                area_id=area_id,
                cupo_sel=cupo,
                cupo_tabs=cupo_tabs,
                cupo_usa_area=(cupo not in AREA_AGNOSTIC_CUPOS),
                nivel_sel=nivel,
                grado_sel=grado,
                areas_academia=areas,
                filas=filas,
                max_rows=max_rows,
                tab_area_href=tab_area_href,
                tab_nivel_href=tab_nivel_href,
                max_preguntas=max_preguntas,
            ),
        )

    @router.post("/ponderaciones", name="academia_weights.save")
    async def ponderaciones_post(
        request: Request, _user_id: int = Depends(require_roles("administrador"))
    ):
        form = await request.form()
        if not csrf_ok(request, form.get("csrf_token")) and getattr(Config, "WTF_CSRF_ENABLED", True):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(
                url=str(request.url_for("academia_weights.index")), status_code=303
            )

        mode = (form.get("mode") or "area").strip()
        rows = _rows_from_form(form)

        if mode == "area":
            try:
                area_id = int(form.get("area_id") or 1)
            except (TypeError, ValueError):
                area_id = 1
            cupo = _normalize_cupo(form.get("cupo"))
            err = academic_service.replace_weights_for_academic_area(
                area_id, rows, cupo=cupo
            )
        else:
            nivel = (form.get("nivel") or "PRIMARIA").strip()
            if nivel not in ("INICIAL", "PRIMARIA", "SECUNDARIA"):
                nivel = "PRIMARIA"
            grado = (form.get("grado") or "").strip()
            err = academic_service.replace_weights_for_nivel_grado(nivel, grado, rows)

        if err:
            add_flash(request, err, "error")
        else:
            add_flash(request, "Ponderaciones guardadas correctamente.", "success")

        if mode == "area":
            try:
                aid = int(form.get("area_id") or 1)
            except (TypeError, ValueError):
                aid = 1
            c = _normalize_cupo(form.get("cupo"))
            loc = (
                f"{request.url_for('academia_weights.index')}"
                f"?mode=area&area_id={aid}&cupo={c}"
            )
        else:
            niv = (form.get("nivel") or "PRIMARIA").strip()
            g = (form.get("grado") or "").strip()
            loc = (
                f"{request.url_for('academia_weights.index')}"
                f"?mode=nivel&nivel={quote(niv)}&grado={quote(g)}"
            )
        return RedirectResponse(url=loc, status_code=303)

    async def _cargar_excel(request: Request, expected_questions: int) -> RedirectResponse:
        form = await request.form()
        redirect = (
            f"{request.url_for('academia_weights.index')}"
            f"?mode=area&area_id=1&cupo={expected_questions}"
        )
        if not csrf_ok(request, form.get("csrf_token")) and getattr(
            Config, "WTF_CSRF_ENABLED", True
        ):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(url=redirect, status_code=303)

        up = form.get("file_uncp")
        if up is None or not getattr(up, "filename", None):
            add_flash(
                request,
                f"Seleccione el archivo .xlsx de ponderaciones de {expected_questions} preguntas.",
                "error",
            )
            return RedirectResponse(url=redirect, status_code=303)
        if not up.filename.lower().endswith(".xlsx"):
            add_flash(request, "El archivo debe ser .xlsx.", "error")
            return RedirectResponse(url=redirect, status_code=303)

        try:
            content = await up.read()
            parsed = uncp_parse_workbook(BytesIO(content))
            uncp_validate_parsed(parsed, expected_questions=expected_questions)
            stats = uncp_apply_weights(parsed, cupo=expected_questions)
            add_flash(
                request,
                f"Ponderaciones de {expected_questions} preguntas cargadas: "
                f"{stats['inserted']} filas insertadas en {stats['areas']} áreas "
                f"(se reemplazaron {stats['deleted']} filas previas).",
                "success",
            )
        except (ValueError, RuntimeError) as exc:
            add_flash(request, f"Error al cargar el Excel: {exc}", "error")
        except Exception as exc:  # noqa: BLE001 — rollback ya hecho por apply_full/weights
            add_flash(request, f"Error inesperado: {exc}", "error")

        return RedirectResponse(url=redirect, status_code=303)

    @router.post(
        "/ponderaciones/cargar-uncp", name="academia_weights.cargar_uncp"
    )
    async def ponderaciones_cargar_uncp(
        request: Request, _user_id: int = Depends(require_roles("administrador"))
    ):
        return await _cargar_excel(request, expected_questions=80)

    @router.post(
        "/ponderaciones/cargar-50", name="academia_weights.cargar_50"
    )
    async def ponderaciones_cargar_50(
        request: Request, _user_id: int = Depends(require_roles("administrador"))
    ):
        return await _cargar_excel(request, expected_questions=50)

    return router
