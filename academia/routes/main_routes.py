"""
Rutas principales del módulo Academia (FastAPI).
"""

from __future__ import annotations

import os
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from werkzeug.utils import secure_filename

from config import Config
from dependencies import get_current_user_id
from models.aula import Aula
from template_helpers import add_flash, common_context, csrf_ok, templates


def init_routes(csv_service, academic_service):
    router = APIRouter()

    @router.get("/", name="academia_main.index")
    def index(request: Request, _user_id: int = Depends(get_current_user_id)):
        academic_areas = academic_service.get_all_academic_areas()
        programas_by_nivel = {}
        try:
            niveles_eta = ["ACADEMIA", "INICIAL", "PRIMARIA", "SECUNDARIA"]
            for niv in niveles_eta:
                aulas = Aula.query.filter_by(nivel=niv, activo=True).order_by(Aula.nombre).all()
                if aulas:
                    programas_by_nivel[niv] = [
                        {"id": a.id, "nombre": a.nombre, "grado": a.grado, "nivel": a.nivel} for a in aulas
                    ]
        except Exception:
            pass
        return templates.TemplateResponse(
            "academia/index.html",
            common_context(request, academic_areas=academic_areas, programas_by_nivel=programas_by_nivel),
        )

    @router.post("/upload", name="academia_main.upload_file")
    async def upload_file(request: Request, _user_id: int = Depends(get_current_user_id)):
        form = await request.form()
        if not csrf_ok(request, form.get("csrf_token")) and getattr(Config, "WTF_CSRF_ENABLED", True):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(url=str(request.url_for("academia_main.index")), status_code=303)

        up = form.get("file")
        if up is None or not getattr(up, "filename", None):
            add_flash(request, "No se seleccionó ningún archivo", "error")
            return RedirectResponse(url=str(request.url_for("academia_main.index")), status_code=303)

        filename = secure_filename(up.filename)
        if not filename.endswith(".csv"):
            add_flash(request, "Formato de archivo inválido. Por favor, suba un archivo CSV.", "error")
            return RedirectResponse(url=str(request.url_for("academia_main.index")), status_code=303)

        filepath = os.path.join(csv_service.upload_folder, filename)
        os.makedirs(csv_service.upload_folder, exist_ok=True)
        content = await up.read()
        with open(filepath, "wb") as f:
            f.write(content)

        try:
            programa = (form.get("programa") or "").strip()
            nivel = "ACADEMIA"
            try:
                aula = Aula.query.filter_by(nombre=programa, activo=True).first()
                if aula:
                    nivel = aula.nivel
            except Exception:
                pass
            num_records = csv_service.process_csv_file(filepath, programa=programa, nivel=nivel)
            add_flash(
                request,
                f"Archivo procesado correctamente. Se cargaron {num_records} registros en {programa or 'sin programa'} ({nivel}).",
                "success",
            )
            return RedirectResponse(url=str(request.url_for("academia_student.results")), status_code=303)
        except Exception as e:
            add_flash(request, f"Error al procesar el archivo: {str(e)}", "error")
            return RedirectResponse(url=str(request.url_for("academia_main.index")), status_code=303)

    @router.get("/update_weights", name="academia_main.update_weights")
    def update_weights(request: Request, _user_id: int = Depends(get_current_user_id)):
        academic_service.initialize_question_weights()
        add_flash(request, "Ponderaciones actualizadas correctamente", "success")
        return RedirectResponse(url=str(request.url_for("academia_main.index")), status_code=303)

    return router
