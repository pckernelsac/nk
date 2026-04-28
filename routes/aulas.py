# routes/aulas.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy import func, or_

from config import Config
from dependencies import get_current_user_id, require_roles
from models import Aula, Estudiante, Matricula, db
from services.aula_service import AulaService
from template_helpers import add_flash, common_context, csrf_ok, templates

router = APIRouter()
ROOT_DIR = Path(__file__).resolve().parents[1]


def get_aula_service():
    return AulaService


def _username(request: Request) -> str | None:
    return request.session.get("username")


@router.get("/lista", name="aulas.lista")
def lista(request: Request, _user_id: int = Depends(get_current_user_id)):
    """Lista todas las aulas con filtros"""
    anio_escolar = request.query_params.get("anio_escolar", str(datetime.now().year))
    nivel = request.query_params.get("nivel", "")
    grado = request.query_params.get("grado", "")
    turno = request.query_params.get("turno", "")
    # Por defecto mostramos solo aulas activas (las archivadas se ocultan salvo filtro explícito)
    activo = request.query_params.get("activo", "1")

    query_args: dict = {"anio_escolar": anio_escolar}
    if nivel:
        query_args["nivel"] = nivel
    if turno:
        query_args["turno"] = turno
    if activo in ("0", "1"):
        query_args["activo"] = activo == "1"

    query = get_aula_service().listar_aulas(**query_args)
    if grado:
        query = query.filter(Aula.grado == grado)
    aulas = query.all()

    for aula in aulas:
        aula.num_estudiantes = aula.estudiantes_matriculados_count()
        aula.disponible = aula.capacidad_maxima - aula.num_estudiantes

    grados_disponibles = db.session.query(Aula.grado).distinct().order_by(Aula.grado).all()
    grados_disponibles = [g[0] for g in grados_disponibles]

    return templates.TemplateResponse(
        "aulas/lista.html",
        common_context(
            request,
            aulas=aulas,
            anio_escolar=anio_escolar,
            nivel_filtro=nivel,
            grado_filtro=grado,
            grados_disponibles=grados_disponibles,
            turno_filtro=turno,
            activo_filtro=activo,
        ),
    )


@router.api_route("/crear", methods=["GET", "POST"], name="aulas.crear")
async def crear(
    request: Request,
    _user_id: int = Depends(require_roles("administrador")),
):
    """Crear un aula nueva"""
    if request.method == "POST":
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(url=str(request.url_for("aulas.crear")), status_code=303)
        nivel = form.get("nivel")
        grado = form.get("grado")
        seccion = form.get("seccion")
        turno = form.get("turno")
        anio_escolar = form.get("anio_escolar") or str(datetime.now().year)
        capacidad_maxima = int(form.get("capacidad_maxima") or 30)

        if not all([nivel, grado, seccion, turno]):
            add_flash(request, "Todos los campos son obligatorios", "error")
            return RedirectResponse(url=str(request.url_for("aulas.crear")), status_code=303)

        aula, error = get_aula_service().crear_aula(
            nivel=nivel,
            grado=grado,
            seccion=seccion,
            turno=turno,
            anio_escolar=anio_escolar,
            capacidad_maxima=capacidad_maxima,
            usuario_creacion=_username(request),
        )
        if error:
            add_flash(request, error, "error")
            return RedirectResponse(url=str(request.url_for("aulas.crear")), status_code=303)

        add_flash(request, f"Aula {aula.nombre} creada exitosamente", "success")
        return RedirectResponse(
            url=str(request.url_for("aulas.detalle", aula_id=aula.id)), status_code=303
        )

    return templates.TemplateResponse("aulas/crear.html", common_context(request))


@router.post("/auto-matricular", name="aulas.auto_matricular")
async def auto_matricular(
    request: Request,
    _user_id: int = Depends(require_roles("administrador")),
):
    """Reconcilia estudiantes existentes contra aulas: matricula a quienes
    no tienen matrícula activa y cuyo (nivel, grado) coincide con
    exactamente un aula activa.
    """
    form = await request.form()
    if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
        add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
        return RedirectResponse(url=str(request.url_for("aulas.lista")), status_code=303)

    usuario = _username(request) or "SISTEMA_AUTO_MATRICULAR"

    # IDs de estudiantes que YA tienen matrícula activa (en cualquier aula).
    matriculados_ids = {
        row[0]
        for row in db.session.query(Matricula.estudiante_id)
        .filter(Matricula.estado == "activo")
        .distinct()
        .all()
    }

    # Estudiantes con nivel+grado y sin matrícula activa.
    candidatos = (
        Estudiante.query.filter(
            Estudiante.nivel.isnot(None),
            Estudiante.nivel != "",
            Estudiante.grado.isnot(None),
            Estudiante.grado != "",
        )
        .all()
    )

    matriculados = 0
    sin_aula = 0
    ambiguos = 0
    errores: list[str] = []
    aulas_cache: dict[tuple[str, str], list] = {}

    for est in candidatos:
        if est.id in matriculados_ids:
            continue
        clave = (est.nivel.strip().upper(), est.grado.strip().upper())
        if clave not in aulas_cache:
            aulas_cache[clave] = (
                Aula.query.filter(
                    Aula.activo.is_(True),
                    func.upper(func.trim(Aula.nivel)) == clave[0],
                    func.upper(func.trim(Aula.grado)) == clave[1],
                ).all()
            )
        aulas_match = aulas_cache[clave]
        if not aulas_match:
            sin_aula += 1
            continue
        if len(aulas_match) > 1:
            ambiguos += 1
            continue
        aula = aulas_match[0]
        _, err = get_aula_service().matricular_estudiante(
            estudiante_id=est.id,
            aula_id=aula.id,
            anio_escolar=aula.anio_escolar,
            observaciones="Auto-matrícula (reconciliación de estudiantes existentes)",
            usuario_registro=usuario,
        )
        if err:
            errores.append(f"{est.dni_est or est.id}: {err}")
        else:
            matriculados += 1

    msg = f"Auto-matrícula completada: {matriculados} matriculado(s)"
    if sin_aula:
        msg += f", {sin_aula} sin aula coincidente"
    if ambiguos:
        msg += f", {ambiguos} con varias aulas posibles (asignar manualmente)"
    add_flash(request, msg, "success" if matriculados else "warning")
    for e in errores[:10]:
        add_flash(request, e, "warning")
    return RedirectResponse(url=str(request.url_for("aulas.lista")), status_code=303)


@router.api_route("/migrar", methods=["GET", "POST"], name="aulas.migrar_datos")
async def migrar_datos(
    request: Request,
    _user_id: int = Depends(require_roles("administrador")),
):
    if request.method == "POST":
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(url=str(request.url_for("aulas.migrar_datos")), status_code=303)

        accion = form.get("accion") or "migrar_datos"

        if accion == "migrar_datos":
            anio_escolar = form.get("anio_escolar") or str(datetime.now().year)
            stats = get_aula_service().migrar_datos_existentes(anio_escolar)
            add_flash(
                request,
                f"Migración completada: {stats['aulas_creadas']} aulas creadas, "
                f"{stats['matriculas_creadas']} matrículas creadas",
                "success",
            )
            for error in stats.get("errores", [])[:10]:
                add_flash(request, error, "warning")

        elif accion == "promocion_anual":
            anio_origen = form.get("anio_origen")
            anio_destino = form.get("anio_destino")
            aulas_ids = list(form.getlist("aulas_ids"))
            grados_destino = list(form.getlist("grados_destino"))

            if not anio_origen or not anio_destino:
                add_flash(request, "Debe especificar año origen y destino", "error")
                return RedirectResponse(url=str(request.url_for("aulas.migrar_datos")), status_code=303)
            if not aulas_ids:
                add_flash(request, "Debe seleccionar al menos un aula", "error")
                return RedirectResponse(url=str(request.url_for("aulas.migrar_datos")), status_code=303)

            aulas_config = []
            for i, aula_id in enumerate(aulas_ids):
                grado = grados_destino[i] if i < len(grados_destino) else ""
                aulas_config.append({"aula_id": int(aula_id), "grado_destino": grado})

            stats = get_aula_service().promocion_anual(
                anio_origen=anio_origen,
                anio_destino=anio_destino,
                aulas_config=aulas_config,
                usuario=_username(request),
            )
            msg = (
                f"Promoción completada: {stats['aulas_creadas']} aulas creadas, "
                f"{stats['matriculas_creadas']} matrículas, {stats['aulas_cerradas']} aulas cerradas"
            )
            if stats.get("egresados", 0) > 0:
                msg += f", {stats['egresados']} egresados"
            add_flash(request, msg, "success")
            for error in stats.get("errores", [])[:10]:
                add_flash(request, error, "warning")

        elif accion == "renovar_ciclo":
            aula_id = form.get("aula_id")
            nuevo_grado = (form.get("nuevo_grado") or "").strip()
            anio_destino = (form.get("anio_destino_ciclo") or "").strip()
            estudiantes_ids = list(form.getlist("estudiantes_ciclo"))

            if not aula_id or not nuevo_grado:
                add_flash(request, "Debe seleccionar un aula y especificar el nuevo grado", "error")
                return RedirectResponse(url=str(request.url_for("aulas.migrar_datos")), status_code=303)

            stats = get_aula_service().renovar_ciclo(
                aula_id=int(aula_id),
                nuevo_grado=nuevo_grado,
                estudiantes_ids=estudiantes_ids,
                anio_escolar_destino=anio_destino or None,
                usuario=_username(request),
            )
            if stats.get("aula_creada"):
                add_flash(
                    request,
                    f"Ciclo renovado: aula '{stats['aula_nombre']}' creada con "
                    f"{stats['matriculas_creadas']} estudiantes",
                    "success",
                )
            for error in stats.get("errores", [])[:10]:
                add_flash(
                    request,
                    error,
                    "warning" if stats.get("aula_creada") else "error",
                )

        return RedirectResponse(url=str(request.url_for("aulas.lista")), status_code=303)

    return await _migrar_datos_page(request)


async def _migrar_datos_page(request: Request):
    anio_actual = str(datetime.now().year)
    aulas_promocion = (
        Aula.query.filter_by(activo=True)
        .filter(Aula.nivel.in_(["PRIMARIA", "SECUNDARIA", "INICIAL"]))
        .order_by(Aula.anio_escolar.desc(), Aula.nivel, Aula.grado, Aula.seccion)
        .all()
    )
    for aula in aulas_promocion:
        aula.grado_sugerido = get_aula_service().obtener_grado_sugerido(aula.nivel, aula.grado)
        aula.num_estudiantes = aula.estudiantes_matriculados_count()

    aulas_academia = (
        Aula.query.filter_by(activo=True)
        .filter(Aula.nivel == "ACADEMIA")
        .order_by(Aula.anio_escolar.desc(), Aula.grado, Aula.seccion)
        .all()
    )
    for aula in aulas_academia:
        aula.num_estudiantes = aula.estudiantes_matriculados_count()

    return templates.TemplateResponse(
        "aulas/migrar.html",
        common_context(
            request,
            aulas_promocion=aulas_promocion,
            aulas_academia=aulas_academia,
            anio_actual=anio_actual,
        ),
    )


@router.get("/api/buscar_estudiante", name="aulas.api_buscar_estudiante")
def api_buscar_estudiante(request: Request, _user_id: int = Depends(get_current_user_id)):
    termino = request.query_params.get("q", "")
    if len(termino) < 2:
        return JSONResponse([])

    estudiantes = (
        Estudiante.query.filter(
            or_(
                Estudiante.dni_est.like(f"%{termino}%"),
                Estudiante.nombres_est.like(f"%{termino}%"),
                Estudiante.apellido_paterno_est.like(f"%{termino}%"),
                Estudiante.apellido_materno_est.like(f"%{termino}%"),
            )
        )
        .limit(10)
        .all()
    )

    resultados = []
    for est in estudiantes:
        nombre_completo = (
            f"{est.apellido_paterno_est} {est.apellido_materno_est}, {est.nombres_est}"
        )
        resultados.append(
            {
                "id": est.id,
                "nombre": nombre_completo,
                "dni": est.dni_est,
                "nivel": est.nivel,
                "grado": est.grado,
            }
        )
    return JSONResponse(resultados)


@router.get("/api/estudiantes_aula/{aula_id}", name="aulas.api_estudiantes_aula")
def api_estudiantes_aula(
    request: Request,
    aula_id: int,
    _user_id: int = Depends(get_current_user_id),
):
    matriculas = (
        Matricula.query.filter_by(aula_id=aula_id, estado="activo")
        .order_by(Matricula.estudiante_nombre_completo)
        .all()
    )
    return JSONResponse(
        [
            {"id": m.estudiante_id, "nombre": m.estudiante_nombre_completo, "dni": m.estudiante_dni}
            for m in matriculas
        ]
    )


@router.get("/{aula_id}/carnets", name="aulas.generar_carnets_aula")
def generar_carnets_aula(
    request: Request,
    aula_id: int,
    _user_id: int = Depends(get_current_user_id),
):
    from utils.carnet_generator import generar_carnets_a4

    aula = get_aula_service().obtener_aula(aula_id)
    if not aula:
        add_flash(request, "Aula no encontrada", "error")
        return RedirectResponse(url=str(request.url_for("aulas.lista")), status_code=303)

    matriculas = get_aula_service().obtener_estudiantes_aula(aula_id, estado="activo")
    if not matriculas:
        add_flash(request, "No hay estudiantes matriculados en esta aula", "warning")
        return RedirectResponse(
            url=str(request.url_for("aulas.detalle", aula_id=aula_id)), status_code=303
        )

    try:
        estudiantes_ids = [m.estudiante_id for m in matriculas]
        estudiantes = Estudiante.query.filter(Estudiante.id.in_(estudiantes_ids)).all()
        for est in estudiantes:
            if not est.codigo_estudiante:
                est.codigo_estudiante = Estudiante.generar_codigo_estudiante()
        db.session.commit()

        logo_path = str(ROOT_DIR / "static" / "img" / "nk.png")
        buffer = generar_carnets_a4(
            estudiantes,
            logo_path=logo_path,
            incluir_reverso=False,
            root_path=str(ROOT_DIR),
        )
        download_name = f"carnets_{aula.codigo}_{aula.anio_escolar}.pdf"
        return Response(
            buffer.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={download_name}"},
        )
    except Exception as e:
        print(f"Error generando carnets del aula: {e}")
        add_flash(request, "Error al generar los carnets", "error")
        return RedirectResponse(
            url=str(request.url_for("aulas.detalle", aula_id=aula_id)), status_code=303
        )


@router.get("/{aula_id}", name="aulas.detalle")
def detalle(
    request: Request,
    aula_id: int,
    _user_id: int = Depends(get_current_user_id),
):
    aula = get_aula_service().obtener_aula(aula_id)
    if not aula:
        add_flash(request, "Aula no encontrada", "error")
        return RedirectResponse(url=str(request.url_for("aulas.lista")), status_code=303)

    matriculas = get_aula_service().obtener_estudiantes_aula(aula_id, estado="activo")
    total_matriculados = len(matriculas)
    disponible = aula.capacidad_maxima - total_matriculados

    return templates.TemplateResponse(
        "aulas/detalle.html",
        common_context(
            request,
            aula=aula,
            matriculas=matriculas,
            total_matriculados=total_matriculados,
            disponible=disponible,
        ),
    )


@router.api_route("/{aula_id}/matricular", methods=["GET", "POST"], name="aulas.matricular")
async def matricular(
    request: Request,
    aula_id: int,
    _user_id: int = Depends(require_roles("administrador")),
):
    aula = get_aula_service().obtener_aula(aula_id)
    if not aula:
        add_flash(request, "Aula no encontrada", "error")
        return RedirectResponse(url=str(request.url_for("aulas.lista")), status_code=303)

    if request.method == "POST":
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(
                url=str(request.url_for("aulas.matricular", aula_id=aula_id)), status_code=303
            )
        estudiantes_ids = list(form.getlist("estudiantes"))
        observaciones = form.get("observaciones") or ""

        if not estudiantes_ids:
            add_flash(request, "Debe seleccionar al menos un estudiante", "error")
            return RedirectResponse(
                url=str(request.url_for("aulas.matricular", aula_id=aula_id)), status_code=303
            )

        exitosos = 0
        errores = []
        for estudiante_id in estudiantes_ids:
            matricula, error = get_aula_service().matricular_estudiante(
                estudiante_id=int(estudiante_id),
                aula_id=aula_id,
                anio_escolar=aula.anio_escolar,
                observaciones=observaciones,
                usuario_registro=_username(request),
            )
            if error:
                errores.append(error)
            else:
                exitosos += 1

        if exitosos > 0:
            add_flash(request, f"{exitosos} estudiante(s) matriculado(s) exitosamente", "success")
        for error in errores[:5]:
            add_flash(request, error, "warning")

        return RedirectResponse(
            url=str(request.url_for("aulas.detalle", aula_id=aula_id)), status_code=303
        )

    estudiantes_matriculados_ids = [
        m.estudiante_id for m in get_aula_service().obtener_estudiantes_aula(aula_id)
    ]
    estudiantes_disponibles = (
        Estudiante.query.filter(~Estudiante.id.in_(estudiantes_matriculados_ids))
        .order_by(
            Estudiante.apellido_paterno_est,
            Estudiante.apellido_materno_est,
            Estudiante.nombres_est,
        )
        .all()
    )

    return templates.TemplateResponse(
        "aulas/matricular.html",
        common_context(request, aula=aula, estudiantes=estudiantes_disponibles),
    )


@router.post("/{aula_id}/actualizar", name="aulas.actualizar")
async def actualizar(
    request: Request,
    aula_id: int,
    _user_id: int = Depends(require_roles("administrador")),
):
    form = await request.form()
    if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
        add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
        return RedirectResponse(
            url=str(request.url_for("aulas.detalle", aula_id=aula_id)), status_code=303
        )
    capacidad_maxima = form.get("capacidad_maxima")
    activo = form.get("activo")
    if capacidad_maxima:
        capacidad_maxima = int(capacidad_maxima)
    if activo is not None:
        activo = activo == "1"

    _aula, error = get_aula_service().actualizar_aula(
        aula_id=aula_id,
        capacidad_maxima=capacidad_maxima,
        activo=activo,
        usuario_modificacion=_username(request),
    )
    if error:
        add_flash(request, error, "error")
    else:
        add_flash(request, "Aula actualizada exitosamente", "success")

    return RedirectResponse(
        url=str(request.url_for("aulas.detalle", aula_id=aula_id)), status_code=303
    )


@router.post("/{aula_id}/editar", name="aulas.editar")
async def editar(
    request: Request,
    aula_id: int,
    _user_id: int = Depends(require_roles("administrador")),
):
    form = await request.form()
    if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
        add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
        return RedirectResponse(url=str(request.url_for("aulas.lista")), status_code=303)
    capacidad_maxima = form.get("capacidad_maxima")
    turno = form.get("turno") or None
    activo_val = form.get("activo")
    activo = activo_val == "1" if activo_val is not None else None
    nombre_raw = form.get("nombre")
    nombre = nombre_raw.strip() if isinstance(nombre_raw, str) and nombre_raw.strip() else None

    _aula, error = get_aula_service().actualizar_aula(
        aula_id=aula_id,
        capacidad_maxima=int(capacidad_maxima) if capacidad_maxima else None,
        turno=turno,
        activo=activo,
        nombre=nombre,
        usuario_modificacion=_username(request),
    )
    if error:
        add_flash(request, error, "error")
    else:
        add_flash(request, "Aula actualizada exitosamente", "success")

    return RedirectResponse(url=str(request.url_for("aulas.lista")), status_code=303)


@router.post("/{aula_id}/eliminar", name="aulas.eliminar")
async def eliminar(
    request: Request,
    aula_id: int,
    _user_id: int = Depends(require_roles("administrador")),
):
    form = await request.form()
    if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
        add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
        return RedirectResponse(url=str(request.url_for("aulas.lista")), status_code=303)
    ok, error, accion = get_aula_service().eliminar_aula(
        aula_id=aula_id, usuario=_username(request)
    )
    if error:
        add_flash(request, error, "error")
    elif accion == "archivada":
        add_flash(
            request,
            "El aula tenía historial (estudiantes retirados o registros previos), "
            "por lo que se archivó en lugar de eliminarse. Ya no aparecerá en los listados activos.",
            "success",
        )
    else:
        add_flash(request, "Aula eliminada exitosamente", "success")

    return RedirectResponse(url=str(request.url_for("aulas.lista")), status_code=303)


@router.post("/matricula/{matricula_id}/retirar", name="aulas.retirar_estudiante")
async def retirar_estudiante(
    request: Request,
    matricula_id: int,
    _user_id: int = Depends(require_roles("administrador")),
):
    form = await request.form()
    if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
        add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
        return RedirectResponse(url=str(request.url_for("aulas.lista")), status_code=303)
    motivo = form.get("motivo") or "No especificado"

    matricula, error = get_aula_service().retirar_estudiante(
        matricula_id=matricula_id,
        motivo=motivo,
        usuario_modificacion=_username(request),
    )
    if error:
        add_flash(request, error, "error")
        return RedirectResponse(url=str(request.url_for("aulas.lista")), status_code=303)

    add_flash(
        request,
        f"Estudiante {matricula.estudiante_nombre_completo} retirado exitosamente",
        "success",
    )
    return RedirectResponse(
        url=str(request.url_for("aulas.detalle", aula_id=matricula.aula_id)), status_code=303
    )
