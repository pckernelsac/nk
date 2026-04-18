# routes/pagos.py
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import or_

from config import Config
from dependencies import get_current_user_id, require_roles
from models import ConceptoPagoCiclo, Estudiante, ObligacionPagoEstudiante, PagoGeneral, TipoPago, db
from services.pago_service import PagoService
from template_helpers import add_flash, common_context, csrf_ok, templates

router = APIRouter()


def get_pago_service():
    return PagoService


@router.get("/tipos", name="pagos.tipos_lista")
def tipos_lista(
    request: Request,
    _user_id: int = Depends(get_current_user_id),
    _admin: int = Depends(require_roles("administrador")),
):
    tipos = TipoPago.query.filter_by(activo=True).order_by(TipoPago.nombre).all()
    return templates.TemplateResponse(
        "pagos/tipos_lista.html", common_context(request, tipos=tipos)
    )


@router.post("/api/tipos", name="pagos.api_crear_tipo")
async def api_crear_tipo(
    request: Request,
    _user_id: int = Depends(get_current_user_id),
    _admin: int = Depends(require_roles("administrador")),
):
    try:
        data = await request.json()
        tipo, error = get_pago_service().crear_tipo_pago(
            nombre=data["nombre"],
            codigo=data["codigo"],
            categoria=data.get("categoria"),
            descripcion=data.get("descripcion"),
            usuario=request.session.get("username"),
        )
        if error:
            return JSONResponse({"ok": False, "message": error}, status_code=400)
        return JSONResponse({"ok": True, "tipo_id": tipo.id})
    except Exception as e:
        return JSONResponse({"ok": False, "message": str(e)}, status_code=500)


@router.get("/conceptos", name="pagos.conceptos_lista")
def conceptos_lista(request: Request, _user_id: int = Depends(get_current_user_id)):
    anio_escolar = request.query_params.get("anio_escolar", str(datetime.now().year))
    conceptos = get_pago_service().listar_conceptos(anio_escolar=anio_escolar, activo=True)
    tipos = TipoPago.query.filter_by(activo=True).all()
    return templates.TemplateResponse(
        "pagos/conceptos_lista.html",
        common_context(
            request,
            conceptos=conceptos,
            tipos=tipos,
            anio_escolar=anio_escolar,
        ),
    )


@router.api_route("/conceptos/crear", methods=["GET", "POST"], name="pagos.crear_concepto")
async def crear_concepto(
    request: Request,
    _user_id: int = Depends(get_current_user_id),
    _admin: int = Depends(require_roles("administrador")),
):
    anio_default = str(datetime.now().year)
    if request.method == "POST":
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(
                url=str(request.url_for("pagos.crear_concepto")), status_code=303
            )
        tipo_pago_id = int(form.get("tipo_pago_id") or 0)
        anio_escolar = form.get("anio_escolar") or anio_default
        monto = float(form.get("monto") or 0)
        nivel = form.get("nivel") or None
        grado = form.get("grado") or None
        permite_cuotas = form.get("permite_cuotas") == "on"
        numero_cuotas_max = int(form.get("numero_cuotas_max") or 1)

        concepto, error = get_pago_service().crear_concepto_ciclo(
            tipo_pago_id=tipo_pago_id,
            anio_escolar=anio_escolar,
            monto=monto,
            nivel=nivel,
            grado=grado,
            permite_cuotas=permite_cuotas,
            numero_cuotas_max=numero_cuotas_max,
            usuario=request.session.get("username"),
        )

        if error:
            add_flash(request, error, "error")
            return RedirectResponse(
                url=str(request.url_for("pagos.crear_concepto")), status_code=303
            )

        add_flash(
            request,
            f'Concepto "{concepto.tipo_pago_nombre}" creado exitosamente',
            "success",
        )
        base = str(request.url_for("pagos.conceptos_lista"))
        return RedirectResponse(url=f"{base}?anio_escolar={anio_escolar}", status_code=303)

    tipos = TipoPago.query.filter_by(activo=True).all()
    anio_escolar = request.query_params.get("anio_escolar", anio_default)

    niveles = [
        n[0]
        for n in db.session.query(Estudiante.nivel)
        .filter(Estudiante.nivel.isnot(None), Estudiante.nivel != "")
        .distinct()
        .order_by(Estudiante.nivel)
        .all()
    ]
    grados = [
        g[0]
        for g in db.session.query(Estudiante.grado)
        .filter(Estudiante.grado.isnot(None), Estudiante.grado != "")
        .distinct()
        .order_by(Estudiante.grado)
        .all()
    ]

    return templates.TemplateResponse(
        "pagos/crear_concepto.html",
        common_context(
            request,
            tipos=tipos,
            anio_escolar=anio_escolar,
            niveles=niveles,
            grados=grados,
        ),
    )


@router.get("/obligaciones", name="pagos.obligaciones_lista")
def obligaciones_lista(request: Request, _user_id: int = Depends(get_current_user_id)):
    anio_escolar = request.query_params.get("anio_escolar", str(datetime.now().year))
    estado = request.query_params.get("estado", "")
    concepto_id = request.query_params.get("concepto_id", "")
    nivel = request.query_params.get("nivel", "")

    query = ObligacionPagoEstudiante.query.filter_by(anio_escolar=anio_escolar)

    if estado:
        query = query.filter_by(estado=estado)
    if concepto_id:
        query = query.filter_by(concepto_id=int(concepto_id))
    if nivel:
        query = query.join(
            Estudiante, ObligacionPagoEstudiante.estudiante_id == Estudiante.id
        ).filter(Estudiante.nivel == nivel)

    obligaciones = query.order_by(ObligacionPagoEstudiante.fecha_registro.desc()).all()
    conceptos = get_pago_service().listar_conceptos(anio_escolar=anio_escolar)

    niveles = [
        n[0]
        for n in db.session.query(Estudiante.nivel)
        .filter(Estudiante.nivel.isnot(None), Estudiante.nivel != "")
        .distinct()
        .order_by(Estudiante.nivel)
        .all()
    ]

    return templates.TemplateResponse(
        "pagos/obligaciones_lista.html",
        common_context(
            request,
            obligaciones=obligaciones,
            conceptos=conceptos,
            anio_escolar=anio_escolar,
            estado_filtro=estado,
            concepto_id_filtro=concepto_id,
            nivel_filtro=nivel,
            niveles=niveles,
        ),
    )


@router.api_route("/obligaciones/asignar", methods=["GET", "POST"], name="pagos.asignar_obligaciones")
async def asignar_obligaciones(
    request: Request,
    _user_id: int = Depends(get_current_user_id),
    _admin: int = Depends(require_roles("administrador")),
):
    if request.method == "POST":
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(
                url=str(request.url_for("pagos.asignar_obligaciones")), status_code=303
            )
        concepto_id = int(form.get("concepto_id") or 0)
        numero_cuotas = int(form.get("numero_cuotas") or 1)
        anio_escolar = form.get("anio_escolar") or str(datetime.now().year)

        filtros: dict = {"anio_escolar": anio_escolar}
        nivel = form.get("nivel")
        if nivel:
            filtros["nivel"] = nivel
        grado = form.get("grado")
        if grado:
            filtros["grado"] = grado
        seccion = form.get("seccion")
        if seccion:
            filtros["seccion"] = seccion

        resultado, error = get_pago_service().asignar_obligaciones_masivo(
            concepto_id=concepto_id,
            filtros=filtros,
            numero_cuotas=numero_cuotas,
            usuario=request.session.get("username"),
        )

        if error:
            add_flash(request, error, "error")
            return RedirectResponse(
                url=str(request.url_for("pagos.asignar_obligaciones")), status_code=303
            )

        add_flash(
            request,
            f"Asignación masiva completada: {resultado['creados']} obligaciones creadas",
            "success",
        )
        if resultado["ya_tenian"] > 0:
            add_flash(
                request,
                f"{resultado['ya_tenian']} estudiantes ya tenían esta obligación",
                "info",
            )

        base = str(request.url_for("pagos.obligaciones_lista"))
        return RedirectResponse(url=f"{base}?anio_escolar={anio_escolar}", status_code=303)

    anio_escolar = request.query_params.get("anio_escolar", str(datetime.now().year))
    conceptos = get_pago_service().listar_conceptos(activo=True)

    niveles = [
        n[0]
        for n in db.session.query(Estudiante.nivel)
        .filter(Estudiante.nivel.isnot(None), Estudiante.nivel != "")
        .distinct()
        .order_by(Estudiante.nivel)
        .all()
    ]
    grados = [
        g[0]
        for g in db.session.query(Estudiante.grado)
        .filter(Estudiante.grado.isnot(None), Estudiante.grado != "")
        .distinct()
        .order_by(Estudiante.grado)
        .all()
    ]

    return templates.TemplateResponse(
        "pagos/asignar_obligaciones.html",
        common_context(
            request,
            conceptos=conceptos,
            anio_escolar=anio_escolar,
            niveles=niveles,
            grados=grados,
        ),
    )


@router.api_route("/registrar", methods=["GET", "POST"], name="pagos.registrar_pago")
async def registrar_pago(request: Request, _user_id: int = Depends(get_current_user_id)):
    if request.method == "POST":
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(
                url=str(request.url_for("pagos.registrar_pago")), status_code=303
            )
        obligacion_id = int(form.get("obligacion_id") or 0)
        monto_pagado = float(form.get("monto_pagado") or 0)
        fecha_pago = form.get("fecha_pago")
        forma_pago = form.get("forma_pago") or "efectivo"
        apoderado_nombre = (form.get("apoderado_nombre") or "").strip() or None
        apoderado_dni = (form.get("apoderado_dni") or "").strip() or None
        observaciones = (form.get("observaciones") or "").strip() or None
        version_actual = int(form.get("version") or 1)

        pago, error = get_pago_service().registrar_pago(
            obligacion_id=obligacion_id,
            monto_pagado=monto_pagado,
            fecha_pago=fecha_pago,
            forma_pago=forma_pago,
            apoderado_nombre=apoderado_nombre,
            apoderado_dni=apoderado_dni,
            observaciones=observaciones,
            version_actual=version_actual,
            usuario=request.session.get("username"),
        )

        if error:
            add_flash(request, error, "error")
            return RedirectResponse(
                url=str(request.url_for("pagos.registrar_pago")), status_code=303
            )

        add_flash(
            request,
            f"Pago registrado exitosamente. Recibo: {pago.numero_recibo}",
            "success",
        )
        return RedirectResponse(
            url=str(request.url_for("pagos.ver_recibo", pago_id=pago.id)),
            status_code=303,
        )

    anio_escolar = request.query_params.get("anio_escolar", str(datetime.now().year))
    return templates.TemplateResponse(
        "pagos/registrar_pago.html",
        common_context(request, anio_escolar=anio_escolar, datetime=datetime),
    )


@router.get("/api/buscar_estudiante", name="pagos.api_buscar_estudiante")
def api_buscar_estudiante(request: Request, _user_id: int = Depends(get_current_user_id)):
    try:
        termino = (request.query_params.get("q") or "").strip()
        anio_escolar = request.query_params.get("anio_escolar", str(datetime.now().year))

        if not termino or len(termino) < 2:
            return JSONResponse({"ok": False, "message": "Ingrese al menos 2 caracteres"})

        nombre_concat = (
            Estudiante.apellido_paterno_est
            + " "
            + Estudiante.apellido_materno_est
            + " "
            + Estudiante.nombres_est
        )

        estudiantes = (
            Estudiante.query.filter(
                or_(
                    Estudiante.dni_est.like(f"%{termino}%"),
                    nombre_concat.like(f"%{termino}%"),
                )
            )
            .limit(10)
            .all()
        )

        resultados = []
        for est in estudiantes:
            obligaciones = est.obligaciones_pago.filter(
                ObligacionPagoEstudiante.anio_escolar == anio_escolar,
                ObligacionPagoEstudiante.estado.in_(["pendiente", "pagado_parcial"]),
            ).all()

            resultados.append(
                {
                    "id": est.id,
                    "nombre_completo": est.nombre_completo(),
                    "dni": est.dni_est,
                    "nivel": est.nivel,
                    "grado": est.grado,
                    "obligaciones": [
                        {
                            "id": ob.id,
                            "concepto": ob.concepto_nombre,
                            "monto_total": float(ob.monto_total),
                            "monto_pagado": float(ob.monto_pagado),
                            "monto_pendiente": float(ob.monto_pendiente),
                            "cuotas_pagadas": ob.cuotas_pagadas,
                            "total_cuotas": ob.numero_cuotas,
                            "version": ob.version,
                        }
                        for ob in obligaciones
                    ],
                }
            )

        return JSONResponse({"ok": True, "estudiantes": resultados})
    except Exception as e:
        return JSONResponse({"ok": False, "message": str(e)}, status_code=500)


@router.get("/recibo/{pago_id}", name="pagos.ver_recibo")
def ver_recibo(request: Request, pago_id: int, _user_id: int = Depends(get_current_user_id)):
    pago = db.session.get(PagoGeneral, pago_id)
    if not pago:
        add_flash(request, "Recibo no encontrado", "error")
        return RedirectResponse(url=str(request.url_for("pagos.historial")), status_code=303)

    return templates.TemplateResponse(
        "pagos/recibo.html", common_context(request, pago=pago)
    )


@router.get("/historial", name="pagos.historial")
def historial(request: Request, _user_id: int = Depends(get_current_user_id)):
    anio_escolar = request.query_params.get("anio_escolar", str(datetime.now().year))
    estado = request.query_params.get("estado", "")
    estudiante_dni = (request.query_params.get("estudiante_dni") or "").strip()

    query = PagoGeneral.query.filter_by(anio_escolar=anio_escolar)

    if estado:
        query = query.filter_by(estado=estado)
    if estudiante_dni:
        query = query.filter(PagoGeneral.estudiante_dni.like(f"%{estudiante_dni}%"))

    pagos = query.order_by(PagoGeneral.fecha_registro.desc()).limit(100).all()

    return templates.TemplateResponse(
        "pagos/historial.html",
        common_context(
            request,
            pagos=pagos,
            anio_escolar=anio_escolar,
            estado_filtro=estado,
            estudiante_dni_filtro=estudiante_dni,
        ),
    )


@router.post("/anular/{pago_id}", name="pagos.anular_pago")
async def anular_pago(
    request: Request,
    pago_id: int,
    _user_id: int = Depends(get_current_user_id),
    _admin: int = Depends(require_roles("administrador")),
):
    form = await request.form()
    if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
        add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
        return RedirectResponse(url=str(request.url_for("pagos.historial")), status_code=303)
    motivo = (form.get("motivo") or "").strip()

    if not motivo:
        add_flash(request, "Debe proporcionar un motivo para la anulación", "error")
        return RedirectResponse(url=str(request.url_for("pagos.historial")), status_code=303)

    _pago, error = get_pago_service().anular_pago(
        pago_id=pago_id,
        motivo=motivo,
        usuario=request.session.get("username"),
    )

    if error:
        add_flash(request, error, "error")
    else:
        add_flash(request, "Pago anulado exitosamente", "success")

    return RedirectResponse(url=str(request.url_for("pagos.historial")), status_code=303)


@router.get("/estado_cuenta/{estudiante_id}", name="pagos.estado_cuenta")
def estado_cuenta(
    request: Request, estudiante_id: int, _user_id: int = Depends(get_current_user_id)
):
    anio_escolar = request.query_params.get("anio_escolar", str(datetime.now().year))

    estado, error = get_pago_service().calcular_estado_cuenta(
        estudiante_id=estudiante_id, anio_escolar=anio_escolar
    )

    if error:
        add_flash(request, error, "error")
        return RedirectResponse(url=str(request.url_for("estudiantes.list")), status_code=303)

    return templates.TemplateResponse(
        "pagos/estado_cuenta.html",
        common_context(request, estado=estado, anio_escolar=anio_escolar),
    )
