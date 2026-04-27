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


def init_weights_routes(academic_service):
    @router.get("/ponderaciones", name="academia_weights.index")
    def ponderaciones_get(
        request: Request, _user_id: int = Depends(require_roles("administrador"))
    ):
        mode = (request.query_params.get("mode") or "area").strip()
        if mode not in ("area", "nivel"):
            mode = "area"
        area_id = int(request.query_params.get("area_id") or 1)
        nivel = (request.query_params.get("nivel") or "PRIMARIA").strip()
        if nivel not in ("INICIAL", "PRIMARIA", "SECUNDARIA"):
            nivel = "PRIMARIA"
        grado = (request.query_params.get("grado") or "1").strip()

        areas = academic_service.get_all_academic_areas()
        if mode == "area":
            filas = academic_service.list_question_weights_for_area(area_id)
        else:
            filas = academic_service.list_question_weights_for_nivel_grado(nivel, grado)

        max_rows = 32
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
        tab_area_href = f"{base}?mode=area&area_id={area_id}"
        tab_nivel_href = f"{base}?mode=nivel&nivel={quote(nivel)}&grado={quote(grado)}"

        if mode == "area":
            max_preguntas = academic_service.get_max_questions("ACADEMIA", None, area_id)
        else:
            max_preguntas = academic_service.get_max_questions(nivel, grado, None)

        return templates.TemplateResponse(
            "academia/ponderaciones.html",
            common_context(
                request,
                mode=mode,
                area_id=area_id,
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
            err = academic_service.replace_weights_for_academic_area(area_id, rows)
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
            loc = f"{request.url_for('academia_weights.index')}?mode=area&area_id={aid}"
        else:
            niv = (form.get("nivel") or "PRIMARIA").strip()
            g = (form.get("grado") or "").strip()
            loc = (
                f"{request.url_for('academia_weights.index')}"
                f"?mode=nivel&nivel={quote(niv)}&grado={quote(g)}"
            )
        return RedirectResponse(url=loc, status_code=303)

    @router.post(
        "/ponderaciones/cargar-uncp", name="academia_weights.cargar_uncp"
    )
    async def ponderaciones_cargar_uncp(
        request: Request, _user_id: int = Depends(require_roles("administrador"))
    ):
        form = await request.form()
        if not csrf_ok(request, form.get("csrf_token")) and getattr(
            Config, "WTF_CSRF_ENABLED", True
        ):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(
                url=str(request.url_for("academia_weights.index")), status_code=303
            )

        up = form.get("file_uncp")
        if up is None or not getattr(up, "filename", None):
            add_flash(request, "Seleccione el archivo .xlsx de ponderaciones UNCP.", "error")
            return RedirectResponse(
                url=str(request.url_for("academia_weights.index")), status_code=303
            )
        if not up.filename.lower().endswith(".xlsx"):
            add_flash(request, "El archivo debe ser .xlsx.", "error")
            return RedirectResponse(
                url=str(request.url_for("academia_weights.index")), status_code=303
            )

        try:
            content = await up.read()
            parsed = uncp_parse_workbook(BytesIO(content))
            uncp_validate_parsed(parsed)
            stats = uncp_apply_weights(parsed)
            add_flash(
                request,
                f"Ponderaciones UNCP cargadas: {stats['inserted']} filas insertadas en "
                f"{stats['areas']} áreas (se reemplazaron {stats['deleted']} filas previas).",
                "success",
            )
        except (ValueError, RuntimeError) as exc:
            add_flash(request, f"Error al cargar el Excel: {exc}", "error")
        except Exception as exc:  # noqa: BLE001 — rollback ya hecho por apply_full/weights
            add_flash(request, f"Error inesperado: {exc}", "error")

        return RedirectResponse(
            url=str(request.url_for("academia_weights.index")), status_code=303
        )

    return router
