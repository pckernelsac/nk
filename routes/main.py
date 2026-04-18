# routes/main.py
import locale
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import extract, func

from dependencies import get_current_user_id
from models import (
    Aula,
    DetalleAsistenciaAula,
    Docente,
    Estudiante,
    FastTest,
    JustificacionInasistencia,
    Matricula,
    NotaFastTest,
    ObligacionPagoEstudiante,
    PagoGeneral,
    PagoPension,
    PensionEstudiante,
    RegistroAsistenciaAula,
    db,
)
from template_helpers import common_context, templates

router = APIRouter()

try:
    locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
except Exception:
    try:
        locale.setlocale(locale.LC_TIME, "Spanish_Spain.1252")
    except Exception:
        pass


@router.get("/", name="main.index")
def index(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url=str(request.url_for("main.dashboard")), status_code=303)
    return RedirectResponse(url=str(request.url_for("auth.login")), status_code=303)


@router.get("/dashboard", name="main.dashboard")
def dashboard(request: Request, _user_id: int = Depends(get_current_user_id)):
    hoy = datetime.now()
    mes_actual = hoy.month
    anio_actual = str(hoy.year)

    meses_es = [
        "",
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    ]
    mes_nombre = meses_es[mes_actual]

    total_estudiantes = Estudiante.query.count()
    total_docentes = Docente.query.count()

    total_grados = (
        db.session.query(func.count(func.distinct(Estudiante.grado)))
        .filter(Estudiante.grado.isnot(None))
        .scalar()
        or 0
    )

    estudiantes_con_pension = PensionEstudiante.query.filter_by(
        activo=True, anio_escolar=anio_actual
    ).count()

    pagos_mes = (
        PagoPension.query.filter(
            extract("month", PagoPension.fecha_registro) == mes_actual,
            extract("year", PagoPension.fecha_registro) == hoy.year,
            PagoPension.estado == "pagado",
        ).all()
    )

    total_pagos_mes = len(pagos_mes)
    monto_recaudado_mes = sum(float(pago.monto_pagado) for pago in pagos_mes)

    if estudiantes_con_pension > 0:
        porcentaje_pagos = round((total_pagos_mes / estudiantes_con_pension) * 100)
    else:
        porcentaje_pagos = 0

    distribucion_nivel = (
        db.session.query(Estudiante.nivel, func.count(Estudiante.id))
        .filter(Estudiante.nivel.isnot(None))
        .group_by(Estudiante.nivel)
        .all()
    )

    niveles = []
    cantidades_nivel = []
    for nivel, cantidad in distribucion_nivel:
        niveles.append(nivel or "Sin nivel")
        cantidades_nivel.append(cantidad)

    distribucion_grado = (
        db.session.query(Estudiante.grado, func.count(Estudiante.id))
        .filter(Estudiante.grado.isnot(None))
        .group_by(Estudiante.grado)
        .order_by(Estudiante.grado)
        .all()
    )

    grados = []
    cantidades_grado = []
    for grado, cantidad in distribucion_grado:
        grados.append(grado or "Sin grado")
        cantidades_grado.append(cantidad)

    estudiantes_este_mes = Estudiante.query.filter(
        extract("month", Estudiante.fecha_registro) == mes_actual,
        extract("year", Estudiante.fecha_registro) == hoy.year,
    ).count()

    mes_pasado = mes_actual - 1 if mes_actual > 1 else 12
    anio_mes_pasado = hoy.year if mes_actual > 1 else hoy.year - 1
    estudiantes_mes_pasado = Estudiante.query.filter(
        extract("month", Estudiante.fecha_registro) == mes_pasado,
        extract("year", Estudiante.fecha_registro) == anio_mes_pasado,
    ).count()

    if estudiantes_mes_pasado > 0:
        crecimiento_estudiantes = round(
            ((estudiantes_este_mes - estudiantes_mes_pasado) / estudiantes_mes_pasado) * 100
        )
    else:
        crecimiento_estudiantes = 100 if estudiantes_este_mes > 0 else 0

    total_aulas = Aula.query.filter_by(activo=True, anio_escolar=anio_actual).count()
    total_matriculas = Matricula.query.filter_by(
        estado="activo", anio_escolar=anio_actual
    ).count()

    total_fast_tests = FastTest.query.filter_by(anio_escolar=anio_actual).count()
    fast_tests_abiertos = FastTest.query.filter_by(
        anio_escolar=anio_actual, estado="abierto"
    ).count()

    promedio_notas = db.session.query(func.avg(NotaFastTest.nota)).filter(
        NotaFastTest.nota.isnot(None)
    ).scalar()
    promedio_notas = round(promedio_notas, 2) if promedio_notas else 0

    total_obligaciones = ObligacionPagoEstudiante.query.filter_by(
        anio_escolar=anio_actual
    ).count()
    obligaciones_pendientes = ObligacionPagoEstudiante.query.filter_by(
        anio_escolar=anio_actual, estado="pendiente"
    ).count()

    pagos_generales_mes = PagoGeneral.query.filter(
        extract("month", PagoGeneral.fecha_registro) == mes_actual,
        extract("year", PagoGeneral.fecha_registro) == hoy.year,
        PagoGeneral.estado == "pagado",
    ).all()
    monto_pagos_generales = sum(float(pago.monto_pagado) for pago in pagos_generales_mes)

    registros_mes_ids = db.session.query(RegistroAsistenciaAula.id).filter(
        extract("month", RegistroAsistenciaAula.fecha) == mes_actual,
        extract("year", RegistroAsistenciaAula.fecha) == hoy.year,
    ).subquery()

    total_detalles_mes = DetalleAsistenciaAula.query.filter(
        DetalleAsistenciaAula.registro_aula_id.in_(registros_mes_ids)
    ).count()

    asistieron_mes = DetalleAsistenciaAula.query.filter(
        DetalleAsistenciaAula.registro_aula_id.in_(registros_mes_ids),
        DetalleAsistenciaAula.estado.in_(["presente", "tardanza", "justificado"]),
    ).count()

    if total_detalles_mes > 0:
        porcentaje_asistencia = round((asistieron_mes / total_detalles_mes) * 100, 1)
    else:
        porcentaje_asistencia = 0

    justificaciones_pendientes = JustificacionInasistencia.query.filter_by(
        estado="pendiente"
    ).count()
    total_alertas = justificaciones_pendientes + obligaciones_pendientes

    return templates.TemplateResponse(
        "dashboard.html",
        common_context(
            request,
            total_estudiantes=total_estudiantes,
            total_docentes=total_docentes,
            total_grados=total_grados,
            porcentaje_pagos=porcentaje_pagos,
            monto_recaudado_mes=monto_recaudado_mes,
            crecimiento_estudiantes=crecimiento_estudiantes,
            hoy=hoy,
            mes_nombre=mes_nombre,
            niveles=niveles,
            cantidades_nivel=cantidades_nivel,
            grados=grados,
            cantidades_grado=cantidades_grado,
            total_aulas=total_aulas,
            total_matriculas=total_matriculas,
            total_fast_tests=total_fast_tests,
            fast_tests_abiertos=fast_tests_abiertos,
            promedio_notas=promedio_notas,
            total_obligaciones=total_obligaciones,
            obligaciones_pendientes=obligaciones_pendientes,
            monto_pagos_generales=monto_pagos_generales,
            porcentaje_asistencia=porcentaje_asistencia,
            total_alertas=total_alertas,
        ),
    )


@router.get("/formulario", name="main.formulario")
def formulario(request: Request, _user_id: int = Depends(get_current_user_id)):
    return templates.TemplateResponse("formulario.html", common_context(request))
