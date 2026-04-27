"""
Rutas principales del módulo Academia (FastAPI).
"""

from __future__ import annotations

import os
import tempfile
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from werkzeug.utils import secure_filename

from academia.services.csv_service import detect_nivel_from_quiz_name
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

    @router.post("/upload/preview", name="academia_main.upload_preview")
    async def upload_preview(
        request: Request, _user_id: int = Depends(get_current_user_id)
    ):
        """Lee la primera fila del archivo subido y devuelve metadata + aulas candidatas.

        No escribe en BD ni guarda nada permanente: el archivo va a un tmpfile que
        se borra al final.
        """
        form = await request.form()
        if not csrf_ok(request, form.get("csrf_token")) and getattr(
            Config, "WTF_CSRF_ENABLED", True
        ):
            return JSONResponse({"error": "csrf"}, status_code=400)

        up = form.get("file")
        if up is None or not getattr(up, "filename", None):
            return JSONResponse({"error": "no_file"}, status_code=400)
        fname_lower = up.filename.lower()
        if not fname_lower.endswith((".csv", ".xlsx")):
            return JSONResponse({"error": "formato_invalido"}, status_code=400)

        suffix = ".xlsx" if fname_lower.endswith(".xlsx") else ".csv"
        content = await up.read()
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            try:
                meta = csv_service.peek_quiz_metadata(tmp_path)
            except ValueError as exc:
                return JSONResponse(
                    {"error": "archivo_ilegible", "detail": str(exc)}, status_code=400
                )
        finally:
            if tmp_path:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        aulas_candidatas: list = []
        nivel = meta.get("nivel")
        if nivel:
            try:
                rows = (
                    Aula.query.filter_by(nivel=nivel, activo=True)
                    .order_by(Aula.nombre)
                    .all()
                )
                aulas_candidatas = [
                    {
                        "id": a.id,
                        "nombre": a.nombre,
                        "grado": a.grado,
                        "nivel": a.nivel,
                    }
                    for a in rows
                ]
            except Exception as exc:
                print(f"upload_preview: error consultando aulas: {exc}")

        return JSONResponse(
            {
                "quiz_name": meta.get("quiz_name") or "",
                "quiz_class": meta.get("quiz_class") or "",
                "nivel_detectado": nivel,
                "aulas_candidatas": aulas_candidatas,
            }
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
        if not filename.lower().endswith((".csv", ".xlsx")):
            add_flash(request, "Formato de archivo inválido. Por favor, suba un archivo CSV o XLSX.", "error")
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

            try:
                meta = csv_service.peek_quiz_metadata(filepath)
                nivel_detectado = meta.get("nivel")
            except ValueError:
                nivel_detectado = None
            if nivel_detectado and programa and nivel_detectado != nivel:
                try:
                    os.remove(filepath)
                except OSError:
                    pass
                add_flash(
                    request,
                    f"El QuizName del archivo indica nivel {nivel_detectado}, pero el "
                    f"programa seleccionado ('{programa}') es de nivel {nivel}. "
                    f"Seleccione un programa de {nivel_detectado} o suba un archivo "
                    f"que coincida.",
                    "error",
                )
                return RedirectResponse(
                    url=str(request.url_for("academia_main.index")), status_code=303
                )

            validation = csv_service.validate_file(filepath)
            problems = []
            missing = validation.get("missing_dni") or []
            unknown = validation.get("unknown_dni") or []
            if missing:
                preview = ", ".join(f"fila {r} ({info})" for r, info in missing[:8])
                more = "" if len(missing) <= 8 else f" y {len(missing) - 8} más"
                problems.append(
                    f"Falta DNI en {len(missing)} registro(s): {preview}{more}."
                )
            if unknown:
                preview = ", ".join(
                    f"fila {r}: DNI {dni} ({info})" for r, dni, info in unknown[:8]
                )
                more = "" if len(unknown) <= 8 else f" y {len(unknown) - 8} más"
                problems.append(
                    f"DNI no registrado en /estudiantes para {len(unknown)} registro(s): "
                    f"{preview}{more}. Regístrelos antes de cargar el archivo."
                )
            if problems:
                try:
                    os.remove(filepath)
                except OSError:
                    pass
                add_flash(request, " | ".join(problems), "error")
                return RedirectResponse(
                    url=str(request.url_for("academia_main.index")), status_code=303
                )

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
