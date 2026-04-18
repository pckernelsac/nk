"""
Rutas de resultados de estudiantes (Academia) — FastAPI.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_

from config import Config
from dependencies import get_current_user_id
from models.aula import Aula
from template_helpers import add_flash, common_context, csrf_ok, templates
from utils.pagination import paginate_query


def init_routes(student_service, academic_service):
    router = APIRouter()

    @router.get("/results", name="academia_student.results")
    def results(request: Request, _user_id: int = Depends(get_current_user_id)):
        page = int(request.query_params.get("page") or 1)
        search = (request.query_params.get("search") or "").strip()
        per_page = 20

        if search:
            from models.academia import AcademiaStudent

            tokens = [t for t in search.split() if t]
            query = AcademiaStudent.query
            for token in tokens:
                pattern = f"%{token}%"
                query = query.filter(
                    or_(
                        AcademiaStudent.student_id.ilike(pattern),
                        AcademiaStudent.first_name.ilike(pattern),
                        AcademiaStudent.last_name.ilike(pattern),
                        AcademiaStudent.custom_id.ilike(pattern),
                        AcademiaStudent.quiz_name.ilike(pattern),
                        AcademiaStudent.quiz_class.ilike(pattern),
                        AcademiaStudent.programa.ilike(pattern),
                    )
                )
            query = query.order_by(AcademiaStudent.last_name, AcademiaStudent.first_name)
            total_students = query.count()
            pagination = paginate_query(query, page=page, per_page=per_page, error_out=False)
            students = [s.to_dict() for s in pagination.items]
        else:
            students = student_service.get_all_students_paginated(page=page, per_page=per_page)
            total_students = student_service.get_total_students()

        academic_areas = academic_service.get_all_academic_areas()
        total_pages = (total_students + per_page - 1) // per_page if per_page else 0

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
            "academia/results.html",
            common_context(
                request,
                students=students,
                academic_areas=academic_areas,
                programas_by_nivel=programas_by_nivel,
                page=page,
                total_pages=total_pages,
                total_students=total_students,
                per_page=per_page,
                search=search,
            ),
        )

    @router.post("/update_academic_area/{student_id}", name="academia_student.update_academic_area")
    async def update_academic_area(
        request: Request, student_id: int, _user_id: int = Depends(get_current_user_id)
    ):
        form = await request.form()
        if not csrf_ok(request, form.get("csrf_token")) and getattr(Config, "WTF_CSRF_ENABLED", True):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(url=str(request.url_for("academia_student.results")), status_code=303)
        academic_area_id = form.get("academic_area")
        student_service.update_student_academic_area(student_id, academic_area_id)
        add_flash(request, "Área académica actualizada correctamente", "success")
        return RedirectResponse(url=str(request.url_for("academia_student.results")), status_code=303)

    @router.post("/delete_student/{student_id}", name="academia_student.delete_student")
    async def delete_student(request: Request, student_id: int, _user_id: int = Depends(get_current_user_id)):
        form = await request.form()
        if not csrf_ok(request, form.get("csrf_token")) and getattr(Config, "WTF_CSRF_ENABLED", True):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(url=str(request.url_for("academia_student.results")), status_code=303)
        student_service.delete_student(student_id)
        add_flash(request, "Estudiante eliminado correctamente", "success")
        return RedirectResponse(url=str(request.url_for("academia_student.results")), status_code=303)

    @router.post("/clear_all", name="academia_student.clear_all")
    async def clear_all(request: Request, _user_id: int = Depends(get_current_user_id)):
        form = await request.form()
        if not csrf_ok(request, form.get("csrf_token")) and getattr(Config, "WTF_CSRF_ENABLED", True):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(url=str(request.url_for("academia_student.results")), status_code=303)
        student_service.delete_all_students()
        add_flash(request, "Todos los registros han sido eliminados", "success")
        return RedirectResponse(url=str(request.url_for("academia_student.results")), status_code=303)

    return router
