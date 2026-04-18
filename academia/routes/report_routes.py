# -*- coding: utf-8 -*-
"""Reportes Academia (PDF, ranking de mérito) — FastAPI."""

from __future__ import annotations

import datetime
import logging
import os
import re
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from dependencies import get_current_user_id
from template_helpers import add_flash, common_context, templates

logger = logging.getLogger(__name__)

_student_service = None
_pdf_service = None
_academic_service = None


def init_routes(student_service, pdf_service, academic_service):
    global _student_service, _pdf_service, _academic_service
    _student_service = student_service
    _pdf_service = pdf_service
    _academic_service = academic_service
    print("Servicios de reportes inicializados correctamente.")

    router = APIRouter()

    @router.get("/generate_report/{student_id}", name="academia_report.generate_report")
    def generate_report(request: Request, student_id: int, _user_id: int = Depends(get_current_user_id)):
        if not _student_service or not _pdf_service:
            logger.error("Error en generate_report: Servicios no inicializados.")
            add_flash(
                request,
                "Error interno del servidor al intentar generar el reporte. Servicios no configurados.",
                "danger",
            )
            return RedirectResponse(url=str(request.url_for("academia_main.index")), status_code=303)

        logger.info("Solicitud para generar reporte PDF para estudiante ID: %s", student_id)
        try:
            student = _student_service.get_student_by_id(student_id)
            if student:
                logger.info("Estudiante %s encontrado. Generando PDF...", student_id)
                try:
                    pdf_path = _pdf_service.generate_pdf(student)
                    first_name = student.get("first_name", "Estudiante")
                    last_name = student.get("last_name", f"ID_{student_id}")
                    download_filename = f"Boleta_{first_name}_{last_name}.pdf"
                    logger.info("PDF generado en: %s", pdf_path)
                    if not os.path.exists(pdf_path):
                        raise FileNotFoundError(f"El archivo PDF no existe en la ruta: {pdf_path}")
                    return FileResponse(
                        pdf_path,
                        filename=download_filename,
                        media_type="application/pdf",
                    )
                except AttributeError as e:
                    logger.error("Error de método: %s", e, exc_info=True)
                    add_flash(
                        request,
                        "Error de configuración: No se encontró un método adecuado para generar PDFs.",
                        "danger",
                    )
                except FileNotFoundError as e:
                    logger.error("Error en generate_report: %s", e, exc_info=True)
                    add_flash(
                        request,
                        f"Error crítico: El archivo PDF generado para el estudiante {student_id} no se pudo encontrar.",
                        "danger",
                    )
                except Exception as e:
                    logger.error("Error generando PDF para estudiante %s: %s", student_id, e, exc_info=True)
                    add_flash(request, "Ocurrió un error inesperado al generar el PDF.", "danger")
            else:
                logger.warning("Intento de generar reporte para estudiante no existente ID: %s", student_id)
                add_flash(request, f"El estudiante con ID {student_id} no fue encontrado.", "warning")
        except Exception as e:
            logger.error("Error al buscar estudiante %s: %s", student_id, e, exc_info=True)
            add_flash(request, "Ocurrió un error al buscar la información del estudiante.", "danger")
        return RedirectResponse(url=str(request.url_for("academia_student.results")), status_code=303)

    @router.get("/get_etas_by_area/{academic_area_id}", name="academia_report.get_etas_by_area")
    def get_etas_by_area(academic_area_id: int, _user_id: int = Depends(get_current_user_id)):
        if not _student_service:
            return JSONResponse({"error": "Servicio no disponible"}, status_code=500)
        try:
            etas_disponibles = _student_service.get_available_etas_by_area(academic_area_id)
            return JSONResponse(
                {
                    "success": True,
                    "academic_area_id": academic_area_id,
                    "total_etas": len(etas_disponibles),
                    "etas": etas_disponibles,
                }
            )
        except Exception as e:
            logger.error("Error obteniendo ETAs para área %s: %s", academic_area_id, e)
            return JSONResponse({"success": False, "error": "Error interno del servidor"}, status_code=500)

    @router.get("/merit_ranking", name="academia_report.merit_ranking")
    def merit_ranking(request: Request, _user_id: int = Depends(get_current_user_id)):
        if not _student_service or not _pdf_service or not _academic_service:
            logger.error("Error en merit_ranking: Servicios no inicializados.")
            add_flash(
                request,
                "Error interno del servidor al intentar generar el ranking. Servicios no configurados.",
                "danger",
            )
            return RedirectResponse(url=str(request.url_for("academia_main.index")), status_code=303)

        qp = request.query_params
        academic_area_id = qp.get("academic_area_id")
        academic_area_id = int(academic_area_id) if academic_area_id not in (None, "") else None
        eta_number_str = qp.get("eta_number")
        nivel = qp.get("nivel")
        grado = qp.get("grado")
        programa = qp.get("programa")

        if academic_area_id is None and not nivel and not programa:
            add_flash(
                request,
                "Debe seleccionar un Área Académica, Nivel o Programa para generar el reporte de mérito.",
                "warning",
            )
            return RedirectResponse(url=str(request.url_for("academia_student.results")), status_code=303)

        eta_number = None
        if eta_number_str and str(eta_number_str).lower() != "all":
            try:
                eta_number = int(eta_number_str)
            except ValueError:
                add_flash(
                    request,
                    f"Número de ETA inválido: '{eta_number_str}'. Mostrando todas las ETAs.",
                    "warning",
                )
                eta_number = None

        try:
            if programa:
                area_name = f"Programa: {programa}"
                students_ranked = _student_service.get_students_by_programa_ranked(programa, eta_number=eta_number)
            elif nivel and nivel != "ACADEMIA" and grado:
                area_name = f"{nivel} - {grado}° grado"
                students_ranked = _student_service.get_students_by_nivel_grado_ranked(
                    nivel, grado, eta_number=eta_number
                )
            else:
                if academic_area_id is None:
                    add_flash(request, "Debe seleccionar un Área Académica.", "warning")
                    return RedirectResponse(url=str(request.url_for("academia_student.results")), status_code=303)
                academic_area = _academic_service.get_academic_area_by_id(academic_area_id)
                if not academic_area:
                    add_flash(
                        request,
                        f"El área académica con ID {academic_area_id} no fue encontrada.",
                        "warning",
                    )
                    return RedirectResponse(url=str(request.url_for("academia_student.results")), status_code=303)
                area_name = academic_area.get("name", f"Área ID {academic_area_id}")
                students_ranked = _student_service.get_students_by_area_ranked(academic_area_id, eta_number=eta_number)

            logger.info("Se obtuvieron %s estudiantes.", len(students_ranked))

            students_data_for_template = []
            for student in students_ranked:
                sid = student.get("id", "Desconocido")
                try:
                    num_questions_total = 0
                    pri_keys_str = student.get("pri_keys", "")
                    if pri_keys_str and pri_keys_str != [""]:
                        num_questions_total = len(pri_keys_str.split(","))
                    if num_questions_total == 0:
                        marks_str = student.get("marks", "")
                        responses_str = student.get("responses", "")
                        num_questions_total = max(
                            len(marks_str.split(",")) if marks_str and marks_str != [""] else 0,
                            len(responses_str.split(",")) if responses_str and responses_str != [""] else 0,
                            0,
                        )
                    if num_questions_total == 0:
                        logger.warning("Estudiante ID %s sin preguntas. Omitiendo.", sid)
                        continue

                    consolidated_data, _tc, _tw, _tb, _tp = _pdf_service.calculate_consolidated_data(student)
                    conocimientos_puntos_brutos = 0.0
                    aptitud_puntos_brutos = 0.0
                    for row in consolidated_data:
                        subject = row[0]
                        points = row[7]
                        if subject.startswith("Aptitud"):
                            aptitud_puntos_brutos += points
                        else:
                            conocimientos_puntos_brutos += points

                    total_possible_points = _pdf_service._calculate_total_possible_for_student(
                        student, num_questions_total
                    )
                    conocimientos_vigesimal_display = 0.0
                    aptitud_vigesimal_display = 0.0
                    nota_vigesimal_final = 0.0
                    observation = "EN PROCESO"
                    if total_possible_points > 0:
                        conocimientos_vigesimal_display = round(
                            max(0, min(20, (conocimientos_puntos_brutos / total_possible_points) * 20)), 3
                        )
                        aptitud_vigesimal_display = round(
                            max(0, min(20, (aptitud_puntos_brutos / total_possible_points) * 20)), 3
                        )
                        nota_vigesimal_final = conocimientos_vigesimal_display + aptitud_vigesimal_display
                        observation = "Ingresa" if nota_vigesimal_final >= 10.5 else "EN PROCESO"
                    else:
                        observation = "No Calculable"

                    students_data_for_template.append(
                        {
                            "id": sid,
                            "first_name": student.get("first_name", "N/A"),
                            "last_name": student.get("last_name", "N/A"),
                            "student_id": student.get("student_id", "N/A"),
                            "conocimientos": conocimientos_vigesimal_display,
                            "aptitud": aptitud_vigesimal_display,
                            "nota_vigesimal": nota_vigesimal_final,
                            "observation": observation,
                        }
                    )
                except Exception as e:
                    logger.error("Error calculando puntaje para estudiante ID %s: %s", sid, e, exc_info=True)
                    continue

            students_sorted = sorted(
                students_data_for_template, key=lambda x: x["nota_vigesimal"], reverse=True
            )
            for idx, srow in enumerate(students_sorted, 1):
                srow["merit_position"] = idx

            generation_date = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            passing_score = 10.5
            return templates.TemplateResponse(
                "academia/merit_report.html",
                common_context(
                    request,
                    students=students_sorted,
                    career_name=area_name,
                    eta_number=eta_number,
                    generation_date=generation_date,
                    passing_score=passing_score,
                    programa=programa,
                ),
            )
        except Exception as e:
            logger.error("Error generando ranking mérito: %s", e, exc_info=True)
            add_flash(request, "Ocurrió un error inesperado al generar el ranking de mérito.", "danger")
            return RedirectResponse(url=str(request.url_for("academia_student.results")), status_code=303)

    @router.get("/results_pdf", name="academia_report.results_pdf")
    def results_pdf(request: Request, _user_id: int = Depends(get_current_user_id)):
        if not _student_service or not _pdf_service or not _academic_service:
            add_flash(request, "Error interno: servicios no configurados.", "danger")
            return RedirectResponse(url=str(request.url_for("academia_main.index")), status_code=303)

        qp = request.query_params
        aid = qp.get("academic_area_id")
        academic_area_id = int(aid) if aid not in (None, "") else None
        eta_number_str = qp.get("eta_number")
        eta_number = None
        if eta_number_str and str(eta_number_str).lower() != "all":
            try:
                eta_number = int(eta_number_str)
            except ValueError:
                eta_number = None

        try:
            all_students = _student_service.get_all_students()
            area_name = None
            if academic_area_id:
                area = _academic_service.get_academic_area_by_id(academic_area_id)
                area_name = area.get("name", "") if area else None
                all_students = [s for s in all_students if s.get("academic_area_id") == academic_area_id]

            if eta_number:

                def matches_eta(student):
                    qname = (student.get("quiz_name") or "").upper()
                    patterns = [r"ETA(\d+)-", r"ETA\s*N?°?\s*(\d+)", r"ETA\s*(\d+)"]
                    for pat in patterns:
                        m = re.search(pat, qname)
                        if m and int(m.group(1)) == eta_number:
                            return True
                    return False

                all_students = [s for s in all_students if matches_eta(s)]

            pdf_path = _pdf_service.generate_results_pdf(
                students=all_students, area_name=area_name, eta_number=eta_number
            )
            if not os.path.exists(pdf_path):
                add_flash(request, "Error: no se pudo generar el archivo PDF.", "danger")
                return RedirectResponse(url=str(request.url_for("academia_student.results")), status_code=303)

            eta_part = f"_ETA{eta_number:02d}" if eta_number else ""
            area_part = f"_{area_name.replace(' ', '_')[:20]}" if area_name else ""
            download_name = f"ReporteResultadosETAs{area_part}{eta_part}.pdf"
            return FileResponse(pdf_path, filename=download_name, media_type="application/pdf")
        except Exception as e:
            logger.error("Error generando PDF de resultados: %s", e, exc_info=True)
            add_flash(request, "Ocurrió un error al generar el PDF de resultados.", "danger")
            return RedirectResponse(url=str(request.url_for("academia_student.results")), status_code=303)

    def _merit_redirect(request: Request, academic_area_id, eta_number_str: str | None) -> str:
        q = {}
        if academic_area_id is not None:
            q["academic_area_id"] = academic_area_id
        if eta_number_str:
            q["eta_number"] = eta_number_str
        base = str(request.url_for("academia_report.merit_ranking"))
        return base + ("?" + urlencode(q) if q else "")

    @router.get("/merit_ranking_pdf", name="academia_report.merit_ranking_pdf")
    def merit_ranking_pdf(request: Request, _user_id: int = Depends(get_current_user_id)):
        if not _student_service or not _pdf_service or not _academic_service:
            add_flash(request, "Error interno: servicios no configurados.", "danger")
            return RedirectResponse(url=str(request.url_for("academia_main.index")), status_code=303)

        qp = request.query_params
        aid = qp.get("academic_area_id")
        academic_area_id = int(aid) if aid not in (None, "") else None
        eta_number_str = qp.get("eta_number")
        programa = qp.get("programa")
        nivel = qp.get("nivel")
        grado = qp.get("grado")

        if academic_area_id is None and not programa and not nivel:
            add_flash(request, "Debe seleccionar un Área Académica, Programa o Nivel.", "warning")
            return RedirectResponse(url=str(request.url_for("academia_student.results")), status_code=303)

        eta_number = None
        if eta_number_str and str(eta_number_str).lower() != "all":
            try:
                eta_number = int(eta_number_str)
            except ValueError:
                eta_number = None

        try:
            students_sorted, area_name, passing_score, generation_date, err = _build_merit_data(
                academic_area_id, eta_number, programa=programa, nivel=nivel, grado=grado
            )
            if err:
                add_flash(request, err, "warning")
                return RedirectResponse(url=str(request.url_for("academia_student.results")), status_code=303)

            pdf_path = _pdf_service.generate_merit_ranking_pdf(
                students_sorted=students_sorted,
                career_name=area_name,
                eta_number=eta_number,
                generation_date=generation_date,
                passing_score=passing_score,
            )
            if not os.path.exists(pdf_path):
                add_flash(request, "Error: no se pudo generar el archivo PDF.", "danger")
                return RedirectResponse(
                    url=_merit_redirect(request, academic_area_id, eta_number_str or ""),
                    status_code=303,
                )

            eta_part = f"_ETA{eta_number:02d}" if eta_number else "_TodasETAs"
            safe_area = area_name.replace(" ", "_")[:20]
            download_name = f"ReporteMerito_{safe_area}{eta_part}.pdf"
            return FileResponse(pdf_path, filename=download_name, media_type="application/pdf")
        except Exception as e:
            logger.error("Error generando PDF mérito: %s", e, exc_info=True)
            add_flash(request, "Ocurrió un error al generar el PDF.", "danger")
            return RedirectResponse(
                url=_merit_redirect(request, academic_area_id, eta_number_str or ""),
                status_code=303,
            )

    return router


def _build_merit_data(academic_area_id, eta_number, programa=None, nivel=None, grado=None):
    if programa:
        area_name = f"Programa: {programa}"
        students_ranked = _student_service.get_students_by_programa_ranked(programa, eta_number=eta_number)
    elif nivel and nivel != "ACADEMIA" and grado:
        area_name = f"{nivel} - {grado}° grado"
        students_ranked = _student_service.get_students_by_nivel_grado_ranked(nivel, grado, eta_number=eta_number)
    else:
        academic_area = _academic_service.get_academic_area_by_id(academic_area_id)
        if not academic_area:
            return None, None, None, None, f"El área académica con ID {academic_area_id} no fue encontrada."
        area_name = academic_area.get("name", f"Área ID {academic_area_id}")
        students_ranked = _student_service.get_students_by_area_ranked(academic_area_id, eta_number=eta_number)

    students_data = []
    for student in students_ranked:
        student_id = student.get("id", "Desconocido")
        try:
            num_questions_total = 0
            pri_keys_str = student.get("pri_keys", "")
            if pri_keys_str and pri_keys_str != [""]:
                num_questions_total = len(pri_keys_str.split(","))
            if num_questions_total == 0:
                marks_str = student.get("marks", "")
                responses_str = student.get("responses", "")
                num_questions_total = max(
                    len(marks_str.split(",")) if marks_str and marks_str != [""] else 0,
                    len(responses_str.split(",")) if responses_str and responses_str != [""] else 0,
                    0,
                )
            if num_questions_total == 0:
                continue

            consolidated_data, _a, _b, _c, _d = _pdf_service.calculate_consolidated_data(student)
            conocimientos_puntos_brutos = 0.0
            aptitud_puntos_brutos = 0.0
            for row in consolidated_data:
                subject, _level, _peso, _c2, _w, _bl, _tq, points, _perf = row
                if subject.startswith("Aptitud"):
                    aptitud_puntos_brutos += points
                else:
                    conocimientos_puntos_brutos += points

            total_possible_points = _pdf_service._calculate_total_possible_for_student(student, num_questions_total)
            conocimientos_vigesimal = 0.0
            aptitud_vigesimal = 0.0
            nota_vigesimal_final = 0.0
            observation = "EN PROCESO"
            if total_possible_points > 0:
                conocimientos_vigesimal = round(
                    max(0, min(20, (conocimientos_puntos_brutos / total_possible_points) * 20)), 3
                )
                aptitud_vigesimal = round(
                    max(0, min(20, (aptitud_puntos_brutos / total_possible_points) * 20)), 3
                )
                nota_vigesimal_final = conocimientos_vigesimal + aptitud_vigesimal
                observation = "Ingresa" if nota_vigesimal_final >= 10.5 else "EN PROCESO"
            else:
                observation = "No Calculable"

            students_data.append(
                {
                    "id": student_id,
                    "first_name": student.get("first_name", "N/A"),
                    "last_name": student.get("last_name", "N/A"),
                    "student_id": student.get("student_id", "N/A"),
                    "conocimientos": conocimientos_vigesimal,
                    "aptitud": aptitud_vigesimal,
                    "nota_vigesimal": nota_vigesimal_final,
                    "observation": observation,
                }
            )
        except Exception as e:
            logger.error("Error calculando puntaje para estudiante ID %s: %s", student_id, e, exc_info=True)
            continue

    students_sorted = sorted(students_data, key=lambda x: x["nota_vigesimal"], reverse=True)
    generation_date = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    return students_sorted, area_name, 10.5, generation_date, None
