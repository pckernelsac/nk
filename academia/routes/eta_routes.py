# -*- coding: utf-8 -*-
"""Rutas de análisis consolidado de ETAs — FastAPI."""

from __future__ import annotations

import datetime
import logging
import os
import tempfile
import zipfile
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from config import Config
from dependencies import get_current_user_id
from template_helpers import add_flash, common_context, csrf_ok, templates

logger = logging.getLogger(__name__)

router = APIRouter()

_eta_analysis_service = None
_eta_pdf_generator = None
_student_service = None


def init_eta_routes(eta_analysis_service, eta_pdf_generator, student_service):
    global _eta_analysis_service, _eta_pdf_generator, _student_service
    _eta_analysis_service = eta_analysis_service
    _eta_pdf_generator = eta_pdf_generator
    _student_service = student_service
    print("Rutas de análisis de ETAs inicializadas correctamente.")


def _bulk_redirect(request: Request, path: str, **query):
    base = str(request.url_for(path))
    return base + ("?" + urlencode(query) if query else "")


@router.get("/eta_search", name="academia_eta_analysis.eta_search")
def eta_search(request: Request, _user_id: int = Depends(get_current_user_id)):
    if not _eta_analysis_service:
        logger.error("Servicio de análisis de ETAs no inicializado")
        add_flash(request, "Error interno: Servicio no disponible", "error")
        return RedirectResponse(url=str(request.url_for("academia_student.results")), status_code=303)

    search_term = (request.query_params.get("search") or "").strip()
    students = []
    if search_term:
        try:
            students = _eta_analysis_service.search_students_for_eta_analysis(search_term)
            logger.info("Búsqueda de ETAs para '%s': %s resultados", search_term, len(students))
        except Exception as e:
            logger.error("Error en búsqueda de ETAs: %s", e)
            add_flash(request, "Error al buscar estudiantes", "error")

    return templates.TemplateResponse(
        "academia/eta_search.html", common_context(request, students=students, search_term=search_term)
    )


@router.get("/eta_preview/{student_id}", name="academia_eta_analysis.eta_preview")
def eta_preview(request: Request, student_id: str, _user_id: int = Depends(get_current_user_id)):
    if not _eta_analysis_service:
        logger.error("Servicio de análisis de ETAs no inicializado")
        add_flash(request, "Error interno: Servicio no disponible", "error")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.eta_search")), status_code=303)

    try:
        eta_history = _eta_analysis_service.get_student_eta_history(student_id)
        if not eta_history.get("student_found", False):
            add_flash(request, f"Estudiante con ID {student_id} no encontrado", "warning")
            return RedirectResponse(url=str(request.url_for("academia_eta_analysis.eta_search")), status_code=303)

        logger.info("Vista previa de ETAs para estudiante %s", student_id)
        return templates.TemplateResponse(
            "academia/eta_preview.html",
            common_context(
                request,
                student_info=eta_history["student_info"],
                etas=eta_history["etas"],
                summary=eta_history["summary"],
            ),
        )
    except Exception as e:
        logger.error("Error en vista previa de ETAs para %s: %s", student_id, e)
        add_flash(request, "Error al cargar datos del estudiante", "error")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.eta_search")), status_code=303)


@router.get("/generate_eta_pdf/{student_id}", name="academia_eta_analysis.generate_eta_pdf")
def generate_eta_pdf(request: Request, student_id: str, _user_id: int = Depends(get_current_user_id)):
    if not _eta_pdf_generator or not _eta_analysis_service:
        logger.error("Servicios de PDF de ETAs no inicializados")
        add_flash(request, "Error interno: Servicios no disponibles", "error")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.eta_search")), status_code=303)

    logger.info("Generando PDF de ETAs para estudiante %s", student_id)
    try:
        eta_history = _eta_analysis_service.get_student_eta_history(student_id)
        if not eta_history.get("student_found", False):
            add_flash(request, f"Estudiante con ID {student_id} no encontrado", "warning")
            return RedirectResponse(url=str(request.url_for("academia_eta_analysis.eta_search")), status_code=303)
        if not eta_history.get("etas"):
            add_flash(request, f"No se encontraron ETAs para el estudiante {student_id}", "warning")
            return RedirectResponse(url=str(request.url_for("academia_eta_analysis.eta_search")), status_code=303)

        pdf_path = _eta_pdf_generator.generate_eta_summary_pdf(student_id)
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"El archivo PDF no se generó correctamente: {pdf_path}")

        student_info = eta_history["student_info"]
        first_name = student_info.get("first_name", "Estudiante")
        last_name = student_info.get("last_name", f"ID_{student_id}")
        download_filename = f"Resumen_ETAs_{first_name}_{last_name}.pdf"
        logger.info("PDF de ETAs generado exitosamente: %s", pdf_path)
        return FileResponse(pdf_path, filename=download_filename, media_type="application/pdf")
    except ValueError as e:
        logger.warning("Error de validación en PDF de ETAs: %s", e)
        add_flash(request, str(e), "warning")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.eta_search")), status_code=303)
    except FileNotFoundError as e:
        logger.error("Error de archivo en PDF de ETAs: %s", e)
        add_flash(request, "Error al generar el archivo PDF", "error")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.eta_search")), status_code=303)
    except Exception as e:
        logger.error("Error inesperado generando PDF de ETAs para %s: %s", student_id, e, exc_info=True)
        add_flash(request, "Error inesperado al generar el reporte PDF", "error")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.eta_search")), status_code=303)


@router.get("/api/eta_summary/{student_id}", name="academia_eta_analysis.api_eta_summary")
def api_eta_summary(student_id: str, _user_id: int = Depends(get_current_user_id)):
    if not _eta_analysis_service:
        return JSONResponse({"error": "Servicio no disponible"}, status_code=500)
    try:
        eta_history = _eta_analysis_service.get_student_eta_history(student_id)
        if not eta_history.get("student_found", False):
            return JSONResponse({"error": "Estudiante no encontrado"}, status_code=404)
        return JSONResponse(
            {
                "student_info": eta_history["student_info"],
                "summary": eta_history["summary"],
                "etas_count": len(eta_history["etas"]),
                "valid_etas_count": eta_history["summary"].get("valid_etas", 0),
            }
        )
    except Exception as e:
        logger.error("Error en API de resumen ETAs para %s: %s", student_id, e)
        return JSONResponse({"error": "Error interno del servidor"}, status_code=500)


@router.api_route("/bulk_eta_analysis", methods=["GET", "POST"], name="academia_eta_analysis.bulk_eta_analysis")
async def bulk_eta_analysis(request: Request, _user_id: int = Depends(get_current_user_id)):
    if request.method == "GET":
        try:
            students = _eta_analysis_service.search_students_for_eta_analysis()
            students_multi_eta = [s for s in students if s.get("total_etas", 0) > 1]
            return templates.TemplateResponse(
                "academia/bulk_eta_analysis.html",
                common_context(request, students=students_multi_eta),
            )
        except Exception as e:
            logger.error("Error cargando análisis masivo: %s", e)
            add_flash(request, "Error al cargar la página de análisis masivo", "error")
            return RedirectResponse(url=str(request.url_for("academia_eta_analysis.eta_search")), status_code=303)

    form = await request.form()
    if not csrf_ok(request, form.get("csrf_token")) and getattr(Config, "WTF_CSRF_ENABLED", True):
        add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)

    selected = form.getlist("selected_students")
    action = form.get("action") or "individual_pdfs"
    if not selected:
        add_flash(request, "Debe seleccionar al menos un estudiante", "warning")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)

    logger.info("Análisis masivo solicitado para %s estudiantes", len(selected))
    joined = ",".join(selected)

    if action == "individual_pdfs":
        try:
            url = str(request.url_for("academia_eta_analysis.generate_bulk_pdfs"))
            return RedirectResponse(url=f"{url}?{urlencode({'student_ids': joined})}", status_code=303)
        except Exception as e:
            logger.error("Error en generación masiva: %s", e)
            add_flash(request, "Error al generar PDFs masivos", "error")
            return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)

    if action == "consolidated_report":
        try:
            url = str(request.url_for("academia_eta_analysis.consolidated_report_preview"))
            return RedirectResponse(url=f"{url}?{urlencode({'student_ids': joined})}", status_code=303)
        except Exception as e:
            logger.error("Error redirigiendo a vista previa consolidada: %s", e)
            add_flash(request, "Error al preparar el reporte consolidado", "error")
            return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)

    add_flash(request, "Acción no válida seleccionada", "error")
    return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)


@router.get("/consolidated_report_preview", name="academia_eta_analysis.consolidated_report_preview")
def consolidated_report_preview(request: Request, _user_id: int = Depends(get_current_user_id)):
    if not _eta_analysis_service:
        logger.error("Servicio de análisis de ETAs no inicializado")
        add_flash(request, "Error interno: Servicio no disponible", "error")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)

    student_ids_param = request.query_params.get("student_ids") or ""
    if not student_ids_param:
        add_flash(request, "No se especificaron estudiantes para el reporte consolidado", "warning")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)

    student_ids = [sid.strip() for sid in student_ids_param.split(",") if sid.strip()]
    if not student_ids:
        add_flash(request, "No se encontraron IDs de estudiantes válidos", "warning")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)

    logger.info("Vista previa de reporte consolidado para %s estudiantes", len(student_ids))
    try:
        analysis_result = _eta_analysis_service.get_consolidated_eta_analysis(student_ids)
        if not analysis_result.get("valid", False):
            error_msg = analysis_result.get("error", "Error desconocido en el análisis")
            add_flash(request, f"Error en el análisis consolidado: {error_msg}", "error")
            return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)

        consolidated_data = analysis_result["data"]
        return templates.TemplateResponse(
            "academia/consolidated_eta_preview.html",
            common_context(
                request, consolidated_data=consolidated_data, student_ids_param=student_ids_param
            ),
        )
    except Exception as e:
        logger.error("Error en vista previa de reporte consolidado: %s", e, exc_info=True)
        add_flash(request, "Error inesperado al preparar la vista previa del reporte", "error")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)


@router.get("/generate_consolidated_pdf", name="academia_eta_analysis.generate_consolidated_pdf")
def generate_consolidated_pdf(request: Request, _user_id: int = Depends(get_current_user_id)):
    if not _eta_pdf_generator or not _eta_analysis_service:
        logger.error("Servicios de PDF consolidado no inicializados")
        add_flash(request, "Error interno: Servicios no disponibles", "error")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)

    student_ids_param = request.query_params.get("student_ids") or ""
    if not student_ids_param:
        add_flash(request, "No se especificaron estudiantes para el reporte consolidado", "warning")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)

    student_ids = [sid.strip() for sid in student_ids_param.split(",") if sid.strip()]
    if not student_ids:
        add_flash(request, "No se encontraron IDs de estudiantes válidos", "warning")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)

    logger.info("Generando PDF consolidado para %s estudiantes", len(student_ids))
    try:
        pdf_path = _eta_pdf_generator.generate_consolidated_eta_report(student_ids)
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"El archivo PDF consolidado no se generó correctamente: {pdf_path}")
        download_filename = f"Reporte_Consolidado_ETAs_{len(student_ids)}_estudiantes.pdf"
        return FileResponse(pdf_path, filename=download_filename, media_type="application/pdf")
    except ValueError as e:
        logger.warning("Error de validación en PDF consolidado: %s", e)
        add_flash(request, str(e), "warning")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)
    except FileNotFoundError as e:
        logger.error("Error de archivo en PDF consolidado: %s", e)
        add_flash(request, "Error al generar el archivo PDF consolidado", "error")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)
    except Exception as e:
        logger.error("Error inesperado generando PDF consolidado: %s", e, exc_info=True)
        add_flash(request, "Error inesperado al generar el reporte PDF consolidado", "error")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)


@router.get("/generate_bulk_pdfs", name="academia_eta_analysis.generate_bulk_pdfs")
def generate_bulk_pdfs(request: Request, _user_id: int = Depends(get_current_user_id)):
    if not _eta_pdf_generator or not _eta_analysis_service:
        logger.error("Servicios de PDF masivo no inicializados")
        add_flash(request, "Error interno: Servicios no disponibles", "error")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)

    student_ids_param = request.query_params.get("student_ids") or ""
    if not student_ids_param:
        add_flash(request, "No se especificaron estudiantes para generar PDFs masivos", "warning")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)

    student_ids = [sid.strip() for sid in student_ids_param.split(",") if sid.strip()]
    if not student_ids:
        add_flash(request, "No se encontraron IDs de estudiantes válidos", "warning")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)

    logger.info("Generando PDFs masivos para %s estudiantes", len(student_ids))
    try:
        temp_dir = tempfile.mkdtemp()
        pdf_paths = []
        successful_generations = 0
        for student_id in student_ids:
            try:
                eta_history = _eta_analysis_service.get_student_eta_history(student_id)
                if eta_history.get("student_found", False) and eta_history.get("etas"):
                    pdf_path = _eta_pdf_generator.generate_eta_summary_pdf(student_id, temp_dir)
                    if os.path.exists(pdf_path):
                        pdf_paths.append(pdf_path)
                        successful_generations += 1
                        logger.info("PDF generado exitosamente para estudiante %s", student_id)
            except Exception as e:
                logger.error("Error generando PDF para estudiante %s: %s", student_id, e)
                continue

        if not pdf_paths:
            add_flash(request, "No se pudo generar ningún PDF válido", "error")
            return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"PDFs_ETAs_Masivo_{successful_generations}estudiantes_{timestamp}.zip"
        zip_path = os.path.join(temp_dir, zip_filename)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for pdf_path in pdf_paths:
                zipf.write(pdf_path, os.path.basename(pdf_path))

        if not os.path.exists(zip_path):
            raise FileNotFoundError("No se pudo crear el archivo ZIP")

        logger.info("Archivo ZIP creado exitosamente: %s", zip_path)
        if successful_generations < len(student_ids):
            failed_count = len(student_ids) - successful_generations
            add_flash(
                request,
                f"Se generaron {successful_generations} PDFs exitosamente. {failed_count} estudiantes no pudieron procesarse.",
                "warning",
            )
        else:
            add_flash(request, f"Se generaron {successful_generations} PDFs exitosamente.", "success")

        return FileResponse(zip_path, filename=zip_filename, media_type="application/zip")
    except Exception as e:
        logger.error("Error inesperado en generación masiva de PDFs: %s", e, exc_info=True)
        add_flash(request, "Error inesperado al generar los PDFs masivos", "error")
        return RedirectResponse(url=str(request.url_for("academia_eta_analysis.bulk_eta_analysis")), status_code=303)
