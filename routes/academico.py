# routes/academico.py
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse

from config import Config
from dependencies import get_current_user_id, require_roles
from models import Aula, Curso, Estudiante, FastTest, NotaFastTest, PeriodoAcademico, db
from services.academico_service import AcademicoService
from template_helpers import add_flash, common_context, csrf_ok, templates

router = APIRouter()


def get_academico_service():
    return AcademicoService


@router.get("/periodos", name="academico.periodos_lista")
def periodos_lista(request: Request, _user_id: int = Depends(get_current_user_id)):
    anio_actual = str(datetime.now().year)
    anio = request.query_params.get("anio", anio_actual)
    periodos = (
        PeriodoAcademico.query.filter_by(anio_escolar=anio)
        .order_by(PeriodoAcademico.numero)
        .all()
    )
    return templates.TemplateResponse(
        "academico/periodos_lista.html",
        common_context(request, periodos=periodos, anio_escolar=anio),
    )


@router.get("/cursos", name="academico.cursos_lista")
def cursos_lista(request: Request, _user_id: int = Depends(get_current_user_id)):
    cursos = Curso.query.filter_by(activo=True).order_by(Curso.nombre).all()
    return templates.TemplateResponse(
        "academico/cursos_lista.html", common_context(request, cursos=cursos)
    )


@router.get("/fast_tests", name="academico.fast_tests_lista")
def fast_tests_lista(request: Request, _user_id: int = Depends(get_current_user_id)):
    anio_actual = str(datetime.now().year)
    aula_id = request.query_params.get("aula_id", "")
    curso_id = request.query_params.get("curso_id", "")
    periodo_id = request.query_params.get("periodo_id", "")
    anio_escolar = request.query_params.get("anio_escolar", anio_actual)
    estado = request.query_params.get("estado", "")

    query_args: dict = {}
    if aula_id:
        query_args["aula_id"] = int(aula_id)
    if curso_id:
        query_args["curso_id"] = int(curso_id)
    if periodo_id:
        query_args["periodo_id"] = int(periodo_id)
    if anio_escolar:
        query_args["anio_escolar"] = anio_escolar
    if estado:
        query_args["estado"] = estado

    fast_tests = get_academico_service().listar_fast_tests(**query_args).all()

    aulas = (
        Aula.query.filter_by(activo=True, anio_escolar=anio_escolar)
        .order_by(Aula.nombre)
        .all()
    )
    cursos = Curso.query.filter_by(activo=True).order_by(Curso.nombre).all()
    periodos = (
        PeriodoAcademico.query.filter_by(anio_escolar=anio_escolar)
        .order_by(PeriodoAcademico.numero)
        .all()
    )

    return templates.TemplateResponse(
        "academico/fast_tests_lista.html",
        common_context(
            request,
            fast_tests=fast_tests,
            aulas=aulas,
            cursos=cursos,
            periodos=periodos,
            aula_id_filtro=aula_id,
            curso_id_filtro=curso_id,
            periodo_id_filtro=periodo_id,
            estado_filtro=estado,
            anio_escolar=anio_escolar,
        ),
    )


@router.api_route("/fast_tests/crear", methods=["GET", "POST"], name="academico.crear_fast_test")
async def crear_fast_test(
    request: Request,
    _user_id: int = Depends(get_current_user_id),
    _admin: int = Depends(require_roles("administrador")),
):
    anio_escolar = str(datetime.now().year)

    if request.method == "POST":
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(
                url=str(request.url_for("academico.crear_fast_test")), status_code=303
            )
        curso_ids = form.getlist("curso_ids")
        aula_id = form.get("aula_id")
        titulo = (form.get("titulo") or "").strip()
        descripcion = form.get("descripcion") or ""
        fecha_evaluacion = form.get("fecha_evaluacion")
        anio_escolar = form.get("anio_escolar") or anio_escolar

        if not curso_ids or not aula_id or not titulo or not fecha_evaluacion:
            add_flash(
                request,
                "Complete todos los campos obligatorios y seleccione al menos un curso",
                "error",
            )
            aulas = (
                Aula.query.filter_by(activo=True, anio_escolar=anio_escolar)
                .order_by(Aula.nombre)
                .all()
            )
            cursos = Curso.query.filter_by(activo=True).order_by(Curso.nombre).all()
            return templates.TemplateResponse(
                "academico/crear_fast_test.html",
                common_context(
                    request, aulas=aulas, cursos=cursos, anio_escolar=anio_escolar
                ),
            )

        creados = []
        errores = []
        primer_fast_test_id = None

        for curso_id in curso_ids:
            fast_test, error = get_academico_service().crear_fast_test(
                curso_id=int(curso_id),
                aula_id=int(aula_id),
                titulo=titulo,
                descripcion=descripcion,
                fecha_evaluacion=fecha_evaluacion,
                anio_escolar=anio_escolar,
                usuario=request.session.get("username"),
            )
            if error:
                errores.append(error)
            else:
                creados.append(fast_test.curso_nombre)
                if primer_fast_test_id is None:
                    primer_fast_test_id = fast_test.id

        if creados:
            add_flash(
                request,
                f'Fast Test creado para: {", ".join(creados)}',
                "success",
            )
        for err in errores:
            add_flash(request, err, "error")

        if primer_fast_test_id:
            return RedirectResponse(
                url=str(
                    request.url_for(
                        "academico.calificar_fast_test", fast_test_id=primer_fast_test_id
                    )
                ),
                status_code=303,
            )
        return RedirectResponse(
            url=str(request.url_for("academico.crear_fast_test")), status_code=303
        )

    aulas = (
        Aula.query.filter_by(activo=True, anio_escolar=anio_escolar)
        .order_by(Aula.nombre)
        .all()
    )
    cursos = Curso.query.filter_by(activo=True).order_by(Curso.nombre).all()

    return templates.TemplateResponse(
        "academico/crear_fast_test.html",
        common_context(request, aulas=aulas, cursos=cursos, anio_escolar=anio_escolar),
    )


@router.api_route(
    "/fast_tests/{fast_test_id}/calificar",
    methods=["GET", "POST"],
    name="academico.calificar_fast_test",
)
async def calificar_fast_test(
    request: Request, fast_test_id: int, _user_id: int = Depends(get_current_user_id)
):
    fast_test = db.session.get(FastTest, fast_test_id)
    if not fast_test:
        add_flash(request, "Fast Test no encontrado", "error")
        return RedirectResponse(
            url=str(request.url_for("academico.fast_tests_lista")), status_code=303
        )

    fast_tests_sesion = (
        FastTest.query.filter_by(
            aula_id=fast_test.aula_id,
            titulo=fast_test.titulo,
            fecha_evaluacion=fast_test.fecha_evaluacion,
        )
        .order_by(FastTest.curso_nombre)
        .all()
    )

    if request.method == "POST":
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(
                url=str(
                    request.url_for("academico.calificar_fast_test", fast_test_id=fast_test_id)
                ),
                status_code=303,
            )
        total_exitosos = 0
        todos_errores = []

        for ft in fast_tests_sesion:
            notas_dict: dict = {}
            for nota in ft.notas.all():
                key_nota = f"nota_{ft.id}_{nota.estudiante_id}"
                key_nsp = f"nsp_{ft.id}_{nota.estudiante_id}"
                key_ver = f"version_{ft.id}_{nota.estudiante_id}"

                es_nsp = form.get(key_nsp) == "1"
                nota_raw = (form.get(key_nota) or "").strip()
                version = int(form.get(key_ver) or nota.version)

                if es_nsp:
                    nota_val = 0.0
                    obs = "N.S.P."
                elif nota_raw:
                    nota_val = float(nota_raw)
                    obs = None
                else:
                    nota_val = None
                    obs = None

                notas_dict[nota.estudiante_id] = {
                    "nota": nota_val,
                    "version": version,
                    "observaciones": obs,
                }

            resultado, error = get_academico_service().ingresar_notas_fast_test(
                fast_test_id=ft.id,
                notas_dict=notas_dict,
                usuario=request.session.get("username"),
            )
            if error:
                todos_errores.append(error)
            elif resultado:
                total_exitosos += resultado["exitosos"]
                todos_errores.extend(resultado.get("errores", []))

        if total_exitosos:
            add_flash(request, f"Notas guardadas: {total_exitosos} registros", "success")
        for err in todos_errores[:5]:
            add_flash(request, err, "warning")

        return RedirectResponse(
            url=str(
                request.url_for("academico.calificar_fast_test", fast_test_id=fast_test_id)
            ),
            status_code=303,
        )

    primer_ft = fast_tests_sesion[0] if fast_tests_sesion else fast_test
    estudiantes = primer_ft.notas.order_by(
        NotaFastTest.estudiante_nombre_completo
    ).all()

    notas_map: dict = {}
    for ft in fast_tests_sesion:
        notas_map[ft.id] = {}
        for nota in ft.notas.all():
            notas_map[ft.id][nota.estudiante_id] = nota

    return templates.TemplateResponse(
        "academico/calificar_fast_test.html",
        common_context(
            request,
            fast_test=fast_test,
            fast_tests_sesion=fast_tests_sesion,
            estudiantes=estudiantes,
            notas_map=notas_map,
        ),
    )


@router.post("/fast_tests/{fast_test_id}/cerrar", name="academico.cerrar_fast_test")
async def cerrar_fast_test(
    request: Request,
    fast_test_id: int,
    _user_id: int = Depends(get_current_user_id),
    _admin: int = Depends(require_roles("administrador")),
):
    form = await request.form()
    if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
        add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
        return RedirectResponse(
            url=str(request.url_for("academico.fast_tests_lista")), status_code=303
        )
    _ft, error = get_academico_service().cerrar_fast_test(
        fast_test_id=fast_test_id, usuario=request.session.get("username")
    )

    if error:
        add_flash(request, error, "error")
    else:
        add_flash(request, "Fast Test cerrado exitosamente", "success")

    return RedirectResponse(
        url=str(request.url_for("academico.fast_tests_lista")), status_code=303
    )


@router.get("/estudiantes/{estudiante_id}/reporte", name="academico.reporte_estudiante")
def reporte_estudiante(
    request: Request, estudiante_id: int, _user_id: int = Depends(get_current_user_id)
):
    anio_escolar = request.query_params.get("anio_escolar", str(datetime.now().year))

    reporte, error = get_academico_service().obtener_reporte_academico_estudiante(
        estudiante_id=estudiante_id,
        anio_escolar=anio_escolar,
        incluir_asistencias=True,
    )

    if error:
        add_flash(request, error, "error")
        return RedirectResponse(url=str(request.url_for("estudiantes.list")), status_code=303)

    return templates.TemplateResponse(
        "academico/reporte_estudiante.html",
        common_context(request, reporte=reporte, anio_escolar=anio_escolar),
    )


@router.get("/estudiantes/{estudiante_id}/boleta", name="academico.boleta_fast_test")
def boleta_fast_test(
    request: Request,
    estudiante_id: int,
    _user_id: int = Depends(get_current_user_id),
):
    anio_escolar = request.query_params.get("anio_escolar", str(datetime.now().year))
    aula_id_q = request.query_params.get("aula_id")
    aula_id = int(aula_id_q) if aula_id_q else None

    estudiante = db.session.get(Estudiante, estudiante_id)
    if not estudiante:
        add_flash(request, "Estudiante no encontrado", "error")
        return RedirectResponse(url=str(request.url_for("estudiantes.list")), status_code=303)

    query = NotaFastTest.query.join(FastTest).filter(
        NotaFastTest.estudiante_id == estudiante_id,
        FastTest.anio_escolar == anio_escolar,
    )
    if aula_id is not None:
        query = query.filter(FastTest.aula_id == aula_id)

    notas = query.all()

    sesiones = sorted(
        {n.fast_test.titulo for n in notas},
        key=lambda s: (int(s[1:]) if len(s) > 1 and s[1:].isdigit() else 99),
    )
    cursos = sorted({n.fast_test.curso_nombre for n in notas})

    grilla: dict = {}
    for nota in notas:
        curso = nota.fast_test.curso_nombre
        sesion = nota.fast_test.titulo
        if curso not in grilla:
            grilla[curso] = {}
        grilla[curso][sesion] = nota

    aula_nombre = notas[0].fast_test.aula_nombre if notas else ""

    return templates.TemplateResponse(
        "academico/boleta_fast_test.html",
        common_context(
            request,
            estudiante=estudiante,
            grilla=grilla,
            cursos=cursos,
            sesiones=sesiones,
            aula_nombre=aula_nombre,
            anio_escolar=anio_escolar,
        ),
    )


@router.post("/api/periodos", name="academico.api_crear_periodo")
async def api_crear_periodo(
    request: Request,
    _user_id: int = Depends(get_current_user_id),
    _admin: int = Depends(require_roles("administrador")),
):
    try:
        data = await request.json()
        periodo, error = get_academico_service().crear_periodo(
            nombre=data["nombre"],
            numero=int(data["numero"]),
            anio_escolar=data["anio_escolar"],
            fecha_inicio=datetime.strptime(data["fecha_inicio"], "%Y-%m-%d").date(),
            fecha_fin=datetime.strptime(data["fecha_fin"], "%Y-%m-%d").date(),
            usuario=request.session.get("username"),
        )
        if error:
            return JSONResponse({"ok": False, "message": error}, status_code=400)
        return JSONResponse({"ok": True, "periodo_id": periodo.id})
    except Exception as e:
        return JSONResponse({"ok": False, "message": str(e)}, status_code=500)


@router.delete("/api/cursos/{curso_id}", name="academico.api_eliminar_curso")
def api_eliminar_curso(
    request: Request,
    curso_id: int,
    _user_id: int = Depends(get_current_user_id),
    _admin: int = Depends(require_roles("administrador")),
):
    try:
        curso = db.session.get(Curso, curso_id)
        if not curso:
            return JSONResponse({"ok": False, "message": "Curso no encontrado"}, status_code=404)

        if curso.fast_tests.count() > 0:
            return JSONResponse(
                {
                    "ok": False,
                    "message": f"No se puede eliminar: el curso tiene {curso.fast_tests.count()} Fast Test(s) asociado(s)",
                },
                status_code=400,
            )

        if curso.asignaciones.count() > 0:
            return JSONResponse(
                {
                    "ok": False,
                    "message": f"No se puede eliminar: el curso tiene {curso.asignaciones.count()} asignación(es) de docente",
                },
                status_code=400,
            )

        nombre = curso.nombre
        db.session.delete(curso)
        db.session.commit()
        return JSONResponse(
            {"ok": True, "message": f'Curso "{nombre}" eliminado correctamente'}
        )
    except Exception as e:
        db.session.rollback()
        return JSONResponse({"ok": False, "message": str(e)}, status_code=500)


@router.post("/api/cursos", name="academico.api_crear_curso")
async def api_crear_curso(
    request: Request,
    _user_id: int = Depends(get_current_user_id),
    _admin: int = Depends(require_roles("administrador")),
):
    try:
        data = await request.json()
        curso, error = get_academico_service().crear_curso(
            nombre=data["nombre"],
            codigo=data["codigo"],
            nivel=data.get("nivel"),
            descripcion=data.get("descripcion"),
            usuario=request.session.get("username"),
        )
        if error:
            return JSONResponse({"ok": False, "message": error}, status_code=400)
        return JSONResponse({"ok": True, "curso_id": curso.id})
    except Exception as e:
        return JSONResponse({"ok": False, "message": str(e)}, status_code=500)
