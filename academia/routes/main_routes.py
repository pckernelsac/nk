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
        aula_match = meta.get("aula_match")
        # Si no hay match exacto por código de aula, devolvemos las aulas del
        # nivel detectado para fallback (modo legacy).
        if not aula_match and nivel:
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
                        "codigo": a.codigo,
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
                "eta_number": meta.get("eta_number"),
                "aula_codigo": meta.get("aula_codigo") or "",
                "aula_match": aula_match,
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
            except ValueError:
                meta = {}
            nivel_detectado = (meta or {}).get("nivel")
            aula_match = (meta or {}).get("aula_match")

            mismatch_msg = None
            if aula_match and programa:
                # Si el archivo identifica un aula concreta por código, exigimos
                # que el programa elegido sea exactamente esa aula.
                if programa != aula_match.get("nombre"):
                    mismatch_msg = (
                        f"El QuizName del archivo identifica el aula "
                        f"'{aula_match.get('nombre')}' (código "
                        f"{aula_match.get('codigo')}), pero seleccionaste "
                        f"'{programa}'. Use el aula que coincide con el código del "
                        f"archivo."
                    )
            elif nivel_detectado and programa and nivel_detectado != nivel:
                mismatch_msg = (
                    f"El QuizName del archivo indica nivel {nivel_detectado}, pero el "
                    f"programa seleccionado ('{programa}') es de nivel {nivel}. "
                    f"Seleccione un programa de {nivel_detectado} o suba un archivo "
                    f"que coincida."
                )

            if mismatch_msg:
                try:
                    os.remove(filepath)
                except OSError:
                    pass
                add_flash(request, mismatch_msg, "error")
                return RedirectResponse(
                    url=str(request.url_for("academia_main.index")), status_code=303
                )

            # Solo bloqueamos cuando hay DNI faltante en el archivo (irrecuperable);
            # los DNIs no registrados en /estudiantes se omiten en el procesamiento
            # pero el archivo se sube y los reconocidos sí se guardan.
            validation = csv_service.validate_file(filepath)
            missing = validation.get("missing_dni") or []
            if missing:
                preview = ", ".join(f"fila {r} ({info})" for r, info in missing[:8])
                more = "" if len(missing) <= 8 else f" y {len(missing) - 8} más"
                try:
                    os.remove(filepath)
                except OSError:
                    pass
                add_flash(
                    request,
                    f"Falta DNI en {len(missing)} registro(s): {preview}{more}. "
                    f"Complete el StudentID en el archivo y vuelva a subirlo.",
                    "error",
                )
                return RedirectResponse(
                    url=str(request.url_for("academia_main.index")), status_code=303
                )

            result = csv_service.process_csv_file(
                filepath, programa=programa, nivel=nivel
            )
            saved = result.get("count", 0)
            skipped_unknown = result.get("skipped_unknown_dni") or []
            target = programa or "sin programa"
            if skipped_unknown:
                preview = ", ".join(
                    f"fila {r} (DNI {dni})" for r, dni in skipped_unknown[:8]
                )
                more = "" if len(skipped_unknown) <= 8 else f" y {len(skipped_unknown) - 8} más"
                add_flash(
                    request,
                    f"Se cargaron {saved} registros en {target} ({nivel}). "
                    f"Se omitieron {len(skipped_unknown)} fila(s) con DNI no "
                    f"registrado en /estudiantes: {preview}{more}.",
                    "warning",
                )
            else:
                add_flash(
                    request,
                    f"Archivo procesado correctamente. Se cargaron {saved} "
                    f"registros en {target} ({nivel}).",
                    "success",
                )
            return RedirectResponse(
                url=str(request.url_for("academia_student.results")), status_code=303
            )
        except Exception as e:
            add_flash(request, f"Error al procesar el archivo: {str(e)}", "error")
            return RedirectResponse(url=str(request.url_for("academia_main.index")), status_code=303)

    @router.get("/update_weights", name="academia_main.update_weights")
    def update_weights(request: Request, _user_id: int = Depends(get_current_user_id)):
        academic_service.initialize_question_weights()
        add_flash(request, "Ponderaciones actualizadas correctamente", "success")
        return RedirectResponse(url=str(request.url_for("academia_main.index")), status_code=303)

    return router
