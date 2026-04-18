"""
Portal estudiante Academia — FastAPI.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

from config import Config
from template_helpers import add_flash, common_context, csrf_ok, templates


def require_academia_student(request: Request) -> None:
    if not request.session.get("student_authenticated"):
        request.session["student_next_url"] = str(request.url)
        add_flash(request, "Debes iniciar sesión para acceder a esta página", "warning")
        raise HTTPException(
            status_code=302,
            headers={"Location": str(request.url_for("academia_student_auth.login"))},
        )


def init_routes(student_auth_service, student_service, pdf_service):
    router = APIRouter()

    @router.api_route("/login", methods=["GET", "POST"], name="academia_student_auth.login")
    async def login(request: Request):
        sess = request.session
        if student_auth_service.is_authenticated(sess):
            return RedirectResponse(url=str(request.url_for("academia_student_auth.dashboard")), status_code=303)

        if request.method == "POST":
            form = await request.form()
            if not csrf_ok(request, form.get("csrf_token")) and getattr(Config, "WTF_CSRF_ENABLED", True):
                add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
                return RedirectResponse(url=str(request.url_for("academia_student_auth.login")), status_code=303)
            student_id = form.get("student_id")
            password = form.get("password")
            if student_auth_service.login(sess, student_id, password):
                add_flash(request, "Sesión iniciada correctamente", "success")
                next_url = sess.pop("student_next_url", None)
                if next_url:
                    return RedirectResponse(url=next_url, status_code=303)
                return RedirectResponse(url=str(request.url_for("academia_student_auth.dashboard")), status_code=303)
            add_flash(request, "StudentID o contraseña incorrectos", "error")

        return templates.TemplateResponse("academia/student/login.html", common_context(request))

    @router.get("/logout", name="academia_student_auth.logout")
    def logout(request: Request):
        student_auth_service.logout(request.session)
        add_flash(request, "Sesión cerrada correctamente", "success")
        return RedirectResponse(url=str(request.url_for("academia_student_auth.login")), status_code=303)

    @router.get("/dashboard", name="academia_student_auth.dashboard")
    def dashboard(request: Request, _auth: None = Depends(require_academia_student)):
        from collections import OrderedDict

        student = student_auth_service.get_current_student(request.session)
        if not student:
            add_flash(request, "Debes iniciar sesión para acceder a esta página", "warning")
            return RedirectResponse(url=str(request.url_for("academia_student_auth.login")), status_code=303)

        student_reports = student_auth_service.get_all_student_reports(student["student_id"])
        reportes_por_programa = OrderedDict()

        try:
            from models import db
            from models.academico import FastTest, NotaFastTest
            from models.aula import Aula
            from models.estudiante import Estudiante
            from models.matricula import Matricula

            estudiante_main = Estudiante.query.filter_by(dni_est=student["student_id"]).first()
            if estudiante_main:
                matriculas = (
                    Matricula.query.join(Aula)
                    .filter(Matricula.estudiante_id == estudiante_main.id, Matricula.estado == "activo")
                    .all()
                )
                for mat in matriculas:
                    aula_nombre = mat.aula_nombre
                    if aula_nombre not in reportes_por_programa:
                        reportes_por_programa[aula_nombre] = {"area": "", "reportes": [], "fast_tests": []}

                for report in student_reports:
                    programa = report.get("programa") or "Sin programa"
                    if programa not in reportes_por_programa:
                        reportes_por_programa[programa] = {
                            "area": report.get("academic_area_name", "Sin área"),
                            "reportes": [],
                            "fast_tests": [],
                        }
                    if not reportes_por_programa[programa]["area"]:
                        reportes_por_programa[programa]["area"] = report.get("academic_area_name", "Sin área")
                    reportes_por_programa[programa]["reportes"].append(report)

                notas_ft = (
                    NotaFastTest.query.join(FastTest)
                    .filter(NotaFastTest.estudiante_id == estudiante_main.id)
                    .order_by(FastTest.aula_nombre, FastTest.fecha_evaluacion.asc())
                    .all()
                )
                for nota in notas_ft:
                    ft = nota.fast_test
                    programa = ft.aula_nombre or "Sin aula"
                    if programa not in reportes_por_programa:
                        reportes_por_programa[programa] = {"area": "", "reportes": [], "fast_tests": []}
                    reportes_por_programa[programa]["fast_tests"].append(
                        {
                            "titulo": ft.titulo,
                            "curso": ft.curso_nombre,
                            "fecha": ft.fecha_evaluacion,
                            "nota": nota.nota,
                            "nota_maxima": ft.nota_maxima,
                            "estado": ft.estado,
                        }
                    )
        except Exception as e:
            print(f"Error obteniendo programas/fast tests: {e}")
            for report in student_reports:
                programa = report.get("programa") or "Sin programa"
                if programa not in reportes_por_programa:
                    reportes_por_programa[programa] = {
                        "area": report.get("academic_area_name", "Sin área"),
                        "reportes": [],
                        "fast_tests": [],
                    }
                reportes_por_programa[programa]["reportes"].append(report)

        return templates.TemplateResponse(
            "academia/student/dashboard.html",
            common_context(
                request, student=student, student_reports=student_reports, reportes_por_programa=reportes_por_programa
            ),
        )

    @router.get("/report/{report_id}", name="academia_student_auth.report")
    def report(request: Request, report_id: int, _auth: None = Depends(require_academia_student)):
        from models.academia import AcademiaStudent

        current_student = student_auth_service.get_current_student(request.session)
        if not current_student:
            add_flash(request, "Debes iniciar sesión para acceder a esta página", "warning")
            return RedirectResponse(url=str(request.url_for("academia_student_auth.login")), status_code=303)

        student_record = AcademiaStudent.query.filter_by(
            id=report_id, student_id=current_student["student_id"]
        ).first()
        if not student_record:
            add_flash(request, "No tienes acceso a este reporte", "error")
            return RedirectResponse(url=str(request.url_for("academia_student_auth.dashboard")), status_code=303)

        stu = student_record.to_dict()
        pdf_path = pdf_service.generate_pdf(stu)
        return FileResponse(
            pdf_path,
            filename=f"Boleta_{stu['first_name']}_{stu['last_name']}.pdf",
            media_type="application/pdf",
        )

    @router.get("/mi-informacion", name="academia_student_auth.mi_informacion")
    def mi_informacion(request: Request, _auth: None = Depends(require_academia_student)):
        from academia.services.integration_service import get_integration_service

        dni_sesion = request.session.get("student_id_number")
        if not dni_sesion:
            add_flash(request, "Error de sesión. Por favor, inicia sesión nuevamente.", "error")
            return RedirectResponse(url=str(request.url_for("academia_student_auth.login")), status_code=303)

        integration_service = get_integration_service()
        estudiante = integration_service.get_estudiante_by_dni(dni_sesion)
        return templates.TemplateResponse(
            "academia/student/mi_informacion.html",
            common_context(request, estudiante=estudiante, dni=dni_sesion),
        )

    @router.api_route("/editar-perfil", methods=["GET", "POST"], name="academia_student_auth.editar_perfil")
    async def editar_perfil(request: Request, _auth: None = Depends(require_academia_student)):
        from academia.services.integration_service import get_integration_service

        dni_sesion = request.session.get("student_id_number")
        student_name = request.session.get("student_name", "Estudiante")
        if not dni_sesion:
            add_flash(request, "Error de sesión. Por favor, inicia sesión nuevamente.", "error")
            return RedirectResponse(url=str(request.url_for("academia_student_auth.login")), status_code=303)

        integration_service = get_integration_service()

        def _perfil_template_ctx(est):
            return {
                "estudiante": est,
                "dni": dni_sesion,
                "tiene_password_personalizada": (
                    bool(est.get("tiene_password_academia_personalizada")) if isinstance(est, dict) else False
                )
                if est
                else False,
            }

        if request.method == "POST":
            form = await request.form()
            if not csrf_ok(request, form.get("csrf_token")) and getattr(Config, "WTF_CSRF_ENABLED", True):
                add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
                estudiante = integration_service.get_estudiante_by_dni(dni_sesion)
                return templates.TemplateResponse(
                    "academia/student/editar_perfil.html",
                    common_context(request, **_perfil_template_ctx(estudiante)),
                )

            if (form.get("accion") or "").strip() == "cambiar_password":
                ok, err = student_auth_service.cambiar_password_portal(
                    dni=dni_sesion,
                    password_actual=form.get("password_actual") or "",
                    password_nuevo=form.get("password_nuevo") or "",
                    password_confirm=form.get("password_confirm") or "",
                )
                estudiante = integration_service.get_estudiante_by_dni(dni_sesion)
                if ok:
                    add_flash(request, "Contraseña actualizada correctamente. Usa tu nueva clave en el próximo inicio de sesión.", "success")
                    return RedirectResponse(url=str(request.url_for("academia_student_auth.editar_perfil")), status_code=303)
                add_flash(request, err, "error")
                return templates.TemplateResponse(
                    "academia/student/editar_perfil.html",
                    common_context(request, **_perfil_template_ctx(estudiante)),
                )

            try:
                current_version = int(form.get("version") or 0)
                data = {
                    "correo_est": (form.get("correo_est") or "").strip(),
                    "numero_celular_est": (form.get("numero_celular_est") or "").strip(),
                    "direccion_est": (form.get("direccion_est") or "").strip(),
                    "distrito_est": (form.get("distrito_est") or "").strip(),
                    "provincia_est": (form.get("provincia_est") or "").strip(),
                    "referencia_est": (form.get("referencia_est") or "").strip(),
                    "celular_padre": (form.get("celular_padre") or "").strip(),
                    "correo_padre": (form.get("correo_padre") or "").strip(),
                    "celular_madre": (form.get("celular_madre") or "").strip(),
                    "correo_madre": (form.get("correo_madre") or "").strip(),
                }
                if data["correo_est"] and "@" not in data["correo_est"]:
                    add_flash(request, "El correo electrónico no es válido", "error")
                    estudiante = integration_service.get_estudiante_by_dni(dni_sesion)
                    return templates.TemplateResponse(
                        "academia/student/editar_perfil.html",
                        common_context(request, **_perfil_template_ctx(estudiante)),
                    )

                exito, mensaje_error, _datos = integration_service.update_estudiante_info(
                    dni=dni_sesion,
                    data=data,
                    current_version=current_version,
                    modificado_por=f"estudiante_portal:{student_name}",
                )
                if exito:
                    add_flash(request, "Tu información ha sido actualizada exitosamente", "success")
                    return RedirectResponse(url=str(request.url_for("academia_student_auth.mi_informacion")), status_code=303)
                add_flash(request, mensaje_error, "error")
                estudiante = integration_service.get_estudiante_by_dni(dni_sesion)
                return templates.TemplateResponse(
                    "academia/student/editar_perfil.html",
                    common_context(request, **_perfil_template_ctx(estudiante)),
                )
            except ValueError:
                add_flash(request, "Error en los datos del formulario", "error")
            except Exception:
                add_flash(request, "Error inesperado. Por favor, intenta nuevamente.", "error")
            estudiante = integration_service.get_estudiante_by_dni(dni_sesion)
            return templates.TemplateResponse(
                "academia/student/editar_perfil.html",
                common_context(request, **_perfil_template_ctx(estudiante)),
            )

        estudiante = integration_service.get_estudiante_by_dni(dni_sesion)
        return templates.TemplateResponse(
            "academia/student/editar_perfil.html",
            common_context(request, **_perfil_template_ctx(estudiante)),
        )

    @router.get("/mis-notas-fast-test", name="academia_student_auth.mis_notas_fast_test")
    def mis_notas_fast_test(request: Request, _auth: None = Depends(require_academia_student)):
        from models import Estudiante, FastTest, NotaFastTest, db as main_db

        dni_sesion = request.session.get("student_id_number")
        if not dni_sesion:
            add_flash(request, "Error de sesión. Por favor, inicia sesión nuevamente.", "error")
            return RedirectResponse(url=str(request.url_for("academia_student_auth.login")), status_code=303)

        estudiante_principal = Estudiante.query.filter_by(dni_est=dni_sesion).first()
        anio_actual = str(datetime.now().year)
        anio_escolar = request.query_params.get("anio_escolar") or anio_actual
        grilla, sesiones, cursos, aula_nombre = {}, [], [], ""
        anios = [anio_actual]
        if estudiante_principal:
            notas = (
                NotaFastTest.query.join(FastTest)
                .filter(NotaFastTest.estudiante_id == estudiante_principal.id, FastTest.anio_escolar == anio_escolar)
                .order_by(FastTest.fecha_evaluacion)
                .all()
            )
            sesiones = sorted(
                set(n.fast_test.titulo for n in notas),
                key=lambda s: (int(s[1:]) if len(s) > 1 and s[1:].isdigit() else 99, s),
            )
            cursos = sorted(set(n.fast_test.curso_nombre for n in notas))
            for nota in notas:
                curso = nota.fast_test.curso_nombre
                ses = nota.fast_test.titulo
                grilla.setdefault(curso, {})[ses] = nota
            aula_nombre = notas[0].fast_test.aula_nombre if notas else ""
            anios_q = (
                main_db.session.query(FastTest.anio_escolar)
                .join(NotaFastTest)
                .filter(NotaFastTest.estudiante_id == estudiante_principal.id)
                .distinct()
                .order_by(FastTest.anio_escolar.desc())
                .all()
            )
            anios = [a[0] for a in anios_q] or [anio_actual]

        return templates.TemplateResponse(
            "academia/student/mis_notas_fast_test.html",
            common_context(
                request,
                estudiante=estudiante_principal,
                grilla=grilla,
                cursos=cursos,
                sesiones=sesiones,
                aula_nombre=aula_nombre,
                anio_escolar=anio_escolar,
                anios=anios,
                dni=dni_sesion,
            ),
        )

    @router.get("/mis-notas-fast-test/pdf", name="academia_student_auth.mis_notas_fast_test_pdf")
    def mis_notas_fast_test_pdf(request: Request, _auth: None = Depends(require_academia_student)):
        from models import Estudiante, FastTest, NotaFastTest

        dni_sesion = request.session.get("student_id_number")
        if not dni_sesion:
            add_flash(request, "Error de sesión. Por favor, inicia sesión nuevamente.", "error")
            return RedirectResponse(url=str(request.url_for("academia_student_auth.login")), status_code=303)

        estudiante_principal = Estudiante.query.filter_by(dni_est=dni_sesion).first()
        anio_actual = str(datetime.now().year)
        anio_escolar = request.query_params.get("anio_escolar") or anio_actual
        grilla, sesiones, cursos, aula_nombre = {}, [], [], ""
        if estudiante_principal:
            notas = (
                NotaFastTest.query.join(FastTest)
                .filter(NotaFastTest.estudiante_id == estudiante_principal.id, FastTest.anio_escolar == anio_escolar)
                .order_by(FastTest.fecha_evaluacion)
                .all()
            )
            sesiones = sorted(
                set(n.fast_test.titulo for n in notas),
                key=lambda s: (int(s[1:]) if len(s) > 1 and s[1:].isdigit() else 99, s),
            )
            cursos = sorted(set(n.fast_test.curso_nombre for n in notas))
            for nota in notas:
                curso = nota.fast_test.curso_nombre
                ses = nota.fast_test.titulo
                grilla.setdefault(curso, {})[ses] = nota
            aula_nombre = notas[0].fast_test.aula_nombre if notas else ""

        try:
            pdf_path = pdf_service.generate_fast_test_pdf(
                estudiante=estudiante_principal,
                grilla=grilla,
                cursos=cursos,
                sesiones=sesiones,
                aula_nombre=aula_nombre,
                anio_escolar=anio_escolar,
                dni=dni_sesion,
            )
            nombre = dni_sesion
            if estudiante_principal:
                nombre = f"{estudiante_principal.apellido_paterno_est}_{estudiante_principal.nombres_est}"
            download_name = f"FastTest_{nombre}_{anio_escolar}.pdf"
            return FileResponse(pdf_path, filename=download_name, media_type="application/pdf")
        except Exception as e:
            add_flash(request, f"Error al generar el PDF: {str(e)}", "error")
            base = str(request.url_for("academia_student_auth.mis_notas_fast_test"))
            return RedirectResponse(
                url=f"{base}?{urlencode({'anio_escolar': anio_escolar})}", status_code=303
            )

    @router.get("/mis-asistencias", name="academia_student_auth.mis_asistencias")
    def mis_asistencias(request: Request, _auth: None = Depends(require_academia_student)):
        from academia.services.integration_service import get_integration_service

        dni_sesion = request.session.get("student_id_number")
        if not dni_sesion:
            add_flash(request, "Error de sesión. Por favor, inicia sesión nuevamente.", "error")
            return RedirectResponse(url=str(request.url_for("academia_student_auth.login")), status_code=303)

        integration_service = get_integration_service()
        mes_s = request.query_params.get("mes")
        anio_s = request.query_params.get("anio")
        mes = int(mes_s) if mes_s else None
        anio = int(anio_s) if anio_s else datetime.now().year

        fecha_inicio = None
        fecha_fin = None
        if mes:
            fecha_inicio = datetime(anio, mes, 1)
            if mes == 12:
                fecha_fin = datetime(anio + 1, 1, 1) - timedelta(days=1)
            else:
                fecha_fin = datetime(anio, mes + 1, 1) - timedelta(days=1)
            fecha_fin = fecha_fin.replace(hour=23, minute=59, second=59)
        else:
            fecha_inicio = datetime(anio, 1, 1)
            fecha_fin = datetime(anio, 12, 31, 23, 59, 59)

        try:
            asistencias = integration_service.get_asistencias_estudiante(
                dni=dni_sesion, fecha_inicio=fecha_inicio, fecha_fin=fecha_fin, limit=200
            )
        except Exception as e:
            add_flash(request, f"Error al obtener el historial de asistencias: {str(e)}", "error")
            asistencias = []

        try:
            estadisticas = integration_service.get_estadisticas_asistencias(dni=dni_sesion, mes=mes, anio=anio)
        except Exception as e:
            add_flash(request, f"Error al obtener estadísticas: {str(e)}", "error")
            estadisticas = {"entradas": 0, "salidas": 0, "total": 0}

        if asistencias is None:
            add_flash(
                request,
                "Error al conectar con el sistema de asistencias. Por favor, contacta al administrador.",
                "error",
            )
            asistencias = []
        if not asistencias and estadisticas["total"] == 0:
            add_flash(request, "No tienes asistencias registradas para el período seleccionado.", "info")

        return templates.TemplateResponse(
            "academia/student/mis_asistencias.html",
            common_context(
                request,
                asistencias=asistencias,
                estadisticas=estadisticas,
                mes_filtro=mes,
                anio_filtro=anio,
            ),
        )

    return router
