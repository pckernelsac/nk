# -*- coding: utf-8 -*-
"""Administración del máximo de preguntas (Stu1..N) según nivel / grado / área académica."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from config import Config
from dependencies import require_roles
from template_helpers import add_flash, common_context, csrf_ok, templates

router = APIRouter()
MAX_CUPO_UI_ROWS = 30


def _cupo_rows_from_form(form) -> List[Dict[str, Any]]:
    nivs = form.getlist("c_nivel")
    grads = form.getlist("c_grado")
    areas = form.getlist("c_area_id")
    maxs = form.getlist("c_max")
    n = max(len(nivs), len(grads), len(areas), len(maxs))
    rows: List[Dict[str, Any]] = []
    for i in range(n):
        try:
            mx = int((maxs[i] if i < len(maxs) else "") or 0)
        except (TypeError, ValueError):
            continue
        if mx < 1:
            continue
        niv = (nivs[i] if i < len(nivs) else "") or ""
        niv = niv.strip()
        if not niv:
            continue
        gr = (grads[i] if i < len(grads) else "*") or "*"
        ares = (areas[i] if i < len(areas) else "") or ""
        rows.append(
            {
                "nivel": niv,
                "grado": (gr or "*").strip() or "*",
                "academic_area_id": ares,
                "max_questions": mx,
            }
        )
    return rows


def init_cupo_preguntas_routes(academic_service):
    @router.get("/cupo-preguntas", name="academia_cupo.index")
    def cupo_get(
        request: Request, _user_id: int = Depends(require_roles("administrador"))
    ):
        configs = academic_service.list_examen_preguntas_configs()
        filas: List[Dict[str, Any]] = list(configs)
        # Filas de relleno: nivel vacío (el usuario o el formulario deben rellenar; no se envían a guardar)
        while len(filas) < MAX_CUPO_UI_ROWS:
            filas.append(
                {
                    "nivel": "",
                    "grado": "*",
                    "academic_area_id": None,
                    "max_questions": "",
                }
            )
        return templates.TemplateResponse(
            "academia/cupo_preguntas.html",
            common_context(
                request,
                filas=filas[:MAX_CUPO_UI_ROWS],
                areas=academic_service.get_all_academic_areas(),
            ),
        )

    @router.post("/cupo-preguntas", name="academia_cupo.save")
    async def cupo_post(
        request: Request, _user_id: int = Depends(require_roles("administrador"))
    ):
        form = await request.form()
        if not csrf_ok(request, form.get("csrf_token")) and getattr(Config, "WTF_CSRF_ENABLED", True):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(
                url=str(request.url_for("academia_cupo.index")), status_code=303
            )
        rows = _cupo_rows_from_form(form)
        err = academic_service.replace_examen_preguntas_configs(rows)
        if err:
            add_flash(request, err, "error")
        else:
            add_flash(request, "Configuración de cupo de preguntas guardada.", "success")
        return RedirectResponse(
            url=str(request.url_for("academia_cupo.index")), status_code=303
        )

    return router
