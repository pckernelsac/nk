# routes/pensiones.py
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from reportlab.lib.units import mm as mm_unit
from reportlab.pdfgen import canvas
from sqlalchemy import or_

from config import Config
from dependencies import get_current_user_id, require_roles
from models import (
    ConfiguracionPension,
    CronogramaPagoPension,
    CuotaPagoPension,
    Estudiante,
    ObligacionPagoEstudiante,
    PagoPension,
    PensionEstudiante,
    db,
)
from services.pago_service import PagoService
from template_helpers import add_flash, common_context, csrf_ok, templates
from utils.helpers import (
    calcular_estadisticas_pensiones,
    generar_numero_recibo,
    obtener_meses_pendientes,
    obtener_pagos_pendientes_lista,
    obtener_saldo_por_mes,
)
from utils.pagination import paginate_query

router = APIRouter()


def _pago_or_404(pago_id: int) -> PagoPension:
    row = db.session.get(PagoPension, pago_id)
    if row is None:
        raise HTTPException(status_code=404)
    return row


def _est_or_404(estudiante_id: int) -> Estudiante:
    row = db.session.get(Estudiante, estudiante_id)
    if row is None:
        raise HTTPException(status_code=404)
    return row


@router.get("/dashboard", name="pensiones.dashboard")
def dashboard(
    request: Request,
    _user_id: int = Depends(get_current_user_id),
    _role_ok: int = Depends(require_roles("administrador", "contador")),
):
    """Dashboard principal de pensiones"""
    try:
        # Obtener configuración activa
        config = ConfiguracionPension.query.filter_by(activo=True).first()
        anio_actual = config.anio_escolar if config else str(datetime.now().year)

        # Calcular estadísticas
        stats = calcular_estadisticas_pensiones()

        # Últimos 10 pagos
        ultimos_pagos = PagoPension.query.order_by(
            PagoPension.fecha_registro.desc()
        ).limit(10).all()

        # Estudiantes con pagos pendientes
        pagos_pendientes_list = obtener_pagos_pendientes_lista(anio_actual)

        return templates.TemplateResponse(
            "pensiones/dashboard.html",
            common_context(
                request,
                stats=stats,
                ultimos_pagos=ultimos_pagos,
                pagos_pendientes=pagos_pendientes_list,
                config=config,
            ),
        )

    except Exception as e:
        print(f"Error al cargar dashboard: {e}")
        add_flash(request, "Error al cargar el dashboard", "error")
        return templates.TemplateResponse(
            "pensiones/dashboard.html",
            common_context(
                request,
                stats={"total_estudiantes": 0, "pagos_mes": 0, "pagos_pendientes": 0, "monto_recaudado": 0},
                ultimos_pagos=[],
                pagos_pendientes=[],
                config=None,
            ),
        )


@router.api_route("/configuracion", methods=["GET", "POST"], name="pensiones.configuracion")
async def configuracion(request: Request, _user_id: int = Depends(get_current_user_id)):
    """Configuración del sistema de pensiones"""
    if request.method == "POST":
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(url=str(request.url_for("pensiones.configuracion")), status_code=303)
        try:
            meses_activos = form.getlist("meses_activos")
            meses_str = ",".join(meses_activos)

            config = ConfiguracionPension.query.filter_by(activo=True).first()

            if config:
                config.nombre_institucion = form.get("nombre_institucion")
                config.ruc_institucion = form.get("ruc_institucion")
                config.direccion_institucion = form.get("direccion_institucion")
                config.telefono_institucion = form.get("telefono_institucion")
                config.anio_escolar = form.get("anio_escolar")
                config.meses_activos = meses_str
                config.serie_recibo = form.get("serie_recibo")
                config.numero_correlativo = int(form.get("numero_correlativo"))
            else:
                config = ConfiguracionPension(
                    nombre_institucion=form.get("nombre_institucion"),
                    ruc_institucion=form.get("ruc_institucion"),
                    direccion_institucion=form.get("direccion_institucion"),
                    telefono_institucion=form.get("telefono_institucion"),
                    anio_escolar=form.get("anio_escolar"),
                    meses_activos=meses_str,
                    serie_recibo=form.get("serie_recibo"),
                    numero_correlativo=int(form.get("numero_correlativo")),
                    activo=True,
                )
                db.session.add(config)

            db.session.commit()
            add_flash(request, "Configuración guardada exitosamente", "success")
            return RedirectResponse(url=str(request.url_for("pensiones.configuracion")), status_code=303)

        except Exception as e:
            db.session.rollback()
            print(f"Error al guardar configuración: {e}")
            add_flash(request, "Error al guardar la configuración. Intente nuevamente.", "error")

    config = ConfiguracionPension.query.filter_by(activo=True).first()
    return templates.TemplateResponse("pensiones/configuracion.html", common_context(request, config=config))


@router.get("/asignar", name="pensiones.asignar_lista")
def asignar_lista(request: Request, _user_id: int = Depends(get_current_user_id)):
    """Lista de estudiantes para asignar pensiones"""
    try:
        config = ConfiguracionPension.query.filter_by(activo=True).first()
        anio_actual = config.anio_escolar if config else str(datetime.now().year)

        buscar = (request.query_params.get("buscar") or "").strip()
        nivel = (request.query_params.get("nivel") or "").strip()
        grado = (request.query_params.get("grado") or "").strip()
        estado = (request.query_params.get("estado") or "").strip()
        page = int(request.query_params.get("page") or 1)
        per_page = 20

        query = Estudiante.query

        if buscar:
            query = query.filter(
                or_(
                    Estudiante.nombres_est.ilike(f"%{buscar}%"),
                    Estudiante.apellido_paterno_est.ilike(f"%{buscar}%"),
                    Estudiante.apellido_materno_est.ilike(f"%{buscar}%"),
                    Estudiante.dni_est.ilike(f"%{buscar}%"),
                )
            )
        if nivel:
            query = query.filter(Estudiante.nivel == nivel)
        if grado:
            query = query.filter(Estudiante.grado.ilike(f'%{grado}%'))

        # Filtrar por estado de pensión requiere subquery
        if estado == 'asignado':
            ids_con_pension = db.session.query(PensionEstudiante.estudiante_id).filter_by(
                anio_escolar=anio_actual, activo=True
            ).subquery()
            query = query.filter(Estudiante.id.in_(ids_con_pension))
        elif estado == 'sin-asignar':
            ids_con_pension = db.session.query(PensionEstudiante.estudiante_id).filter_by(
                anio_escolar=anio_actual, activo=True
            ).subquery()
            query = query.filter(Estudiante.id.notin_(ids_con_pension))

        query = query.order_by(
            Estudiante.apellido_paterno_est,
            Estudiante.apellido_materno_est,
            Estudiante.nombres_est
        )

        paginacion = paginate_query(query, page=page, per_page=per_page, error_out=False)
        estudiantes = paginacion.items

        # Asignar pensión a cada estudiante de la página actual
        ids_pagina = [e.id for e in estudiantes]
        pensiones_map = {
            p.estudiante_id: p
            for p in PensionEstudiante.query.filter(
                PensionEstudiante.estudiante_id.in_(ids_pagina),
                PensionEstudiante.anio_escolar == anio_actual,
                PensionEstudiante.activo == True
            ).all()
        }
        for est in estudiantes:
            est.pension = pensiones_map.get(est.id)

        return templates.TemplateResponse(
            "pensiones/asignar_lista.html",
            common_context(
                request,
                estudiantes=estudiantes,
                paginacion=paginacion,
                buscar=buscar,
                nivel=nivel,
                grado=grado,
                estado=estado,
            ),
        )

    except Exception as e:
        print(f"Error al cargar lista de estudiantes: {e}")
        add_flash(request, "Error al cargar la lista de estudiantes", "error")
        return templates.TemplateResponse(
            "pensiones/asignar_lista.html",
            common_context(
                request,
                estudiantes=[],
                paginacion=None,
                buscar="",
                nivel="",
                grado="",
                estado="",
            ),
        )


@router.api_route("/asignar/{estudiante_id:int}", methods=["GET", "POST"], name="pensiones.asignar_form")
async def asignar_form(request: Request, estudiante_id: int, _user_id: int = Depends(get_current_user_id)):
    """Formulario para asignar/actualizar pensión a un estudiante"""
    try:
        estudiante = _est_or_404(estudiante_id)

        config = ConfiguracionPension.query.filter_by(activo=True).first()

        if request.method == "POST":
            form = await request.form()
            if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
                add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
                return RedirectResponse(
                    url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                    status_code=303,
                )
            anio_escolar = form.get("anio_escolar")
            tipo = form.get("tipo") or "regular"

            meses_activos_csv = None
            if tipo == "academia":
                meses_sel = form.getlist("meses_academia")
                if not meses_sel:
                    add_flash(request, "Seleccione al menos un mes para la pensión de Academia.", "error")
                    return RedirectResponse(
                        url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                        status_code=303,
                    )
                meses_activos_csv = ",".join(meses_sel)
                try:
                    monto_total = float(form.get("monto_total_academia") or 0)
                except ValueError:
                    monto_total = 0.0
                if monto_total <= 0:
                    add_flash(request, "Ingrese el monto total del paquete de Academia.", "error")
                    return RedirectResponse(
                        url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                        status_code=303,
                    )
                monto_mensual = round(monto_total / len(meses_sel), 2)
            else:
                try:
                    monto_mensual = float(form.get("monto_mensual") or 0)
                except ValueError:
                    monto_mensual = 0.0
                if monto_mensual <= 0:
                    add_flash(request, "Ingrese el monto mensual.", "error")
                    return RedirectResponse(
                        url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                        status_code=303,
                    )

            # Verificar si ya existe una pensión del mismo tipo para este estudiante y año
            pension = PensionEstudiante.query.filter_by(
                estudiante_id=estudiante_id,
                anio_escolar=anio_escolar,
                tipo=tipo,
                activo=True
            ).first()

            if pension:
                # Actualizar pensión existente
                pension.monto_mensual = monto_mensual
                pension.meses_activos = meses_activos_csv
                mensaje = 'Pensión actualizada exitosamente'
            else:
                # Crear nueva pensión
                nombre_completo = f"{estudiante.apellido_paterno_est} {estudiante.apellido_materno_est}, {estudiante.nombres_est}"

                pension = PensionEstudiante(
                    estudiante_id=estudiante_id,
                    estudiante_nombre_completo=nombre_completo,
                    estudiante_dni=estudiante.dni_est,
                    estudiante_nivel=estudiante.nivel,
                    estudiante_grado=estudiante.grado,
                    monto_mensual=monto_mensual,
                    anio_escolar=anio_escolar,
                    tipo=tipo,
                    meses_activos=meses_activos_csv,
                    activo=True
                )
                db.session.add(pension)
                mensaje = 'Pensión asignada exitosamente'

            db.session.commit()
            add_flash(request, mensaje, "success")
            return RedirectResponse(url=str(request.url_for("pensiones.asignar_lista")), status_code=303)

        # GET request - mostrar formulario
        # Obtener pensión actual si existe
        anio_actual = config.anio_escolar if config else str(datetime.now().year)
        pension = PensionEstudiante.query.filter_by(
            estudiante_id=estudiante_id,
            anio_escolar=anio_actual,
            activo=True
        ).first()

        meses_pendientes = []
        saldos_por_mes = {}
        if pension:
            meses_pendientes = obtener_meses_pendientes(estudiante_id, anio_actual)
            saldos_por_mes = obtener_saldo_por_mes(estudiante_id, anio_actual)

        todos_los_meses = [
            'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
        ]
        meses_academia_actuales = []
        if pension and pension.tipo == 'academia' and pension.meses_activos:
            meses_academia_actuales = [m.strip() for m in pension.meses_activos.split(',') if m.strip()]

        cronogramas_activos = (
            CronogramaPagoPension.query.filter_by(
                estudiante_id=estudiante_id,
                anio_escolar=anio_actual,
            )
            .filter(CronogramaPagoPension.estado != 'anulado')
            .order_by(CronogramaPagoPension.fecha_registro.desc())
            .all()
        )

        return templates.TemplateResponse(
            "pensiones/asignar_form.html",
            common_context(
                request,
                estudiante=estudiante,
                pension=pension,
                config=config,
                meses_pendientes=meses_pendientes,
                saldos_por_mes=saldos_por_mes,
                todos_los_meses=todos_los_meses,
                meses_academia_actuales=meses_academia_actuales,
                cronogramas_activos=cronogramas_activos,
                now=datetime.utcnow(),
            ),
        )

    except Exception as e:
        db.session.rollback()
        print(f"Error al asignar pensión: {e}")
        add_flash(request, "Error al procesar la asignación. Intente nuevamente.", "error")
        return RedirectResponse(url=str(request.url_for("pensiones.asignar_lista")), status_code=303)


@router.post("/asignar/{estudiante_id:int}/adelantar", name="pensiones.adelantar_cuotas")
async def adelantar_cuotas(request: Request, estudiante_id: int, _user_id: int = Depends(get_current_user_id)):
    """Registra pagos adelantados de cuotas seleccionadas por el apoderado"""
    try:
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        estudiante = _est_or_404(estudiante_id)
        config = ConfiguracionPension.query.filter_by(activo=True).first()
        anio_actual = config.anio_escolar if config else str(datetime.now().year)

        pension = PensionEstudiante.query.filter_by(
            estudiante_id=estudiante_id,
            anio_escolar=anio_actual,
            activo=True,
        ).first()

        if not pension:
            add_flash(request, "El estudiante no tiene pensión asignada. Asigne un monto primero.", "error")
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        meses_seleccionados = form.getlist("meses_adelantar")
        fecha_pago = form.get("fecha_pago_adelanto")
        metodo_pago = form.get("metodo_pago_adelanto") or "efectivo"
        numero_operacion = (form.get("numero_operacion_adelanto") or "").strip()
        observaciones = (form.get("observaciones_adelanto") or "").strip()

        if not meses_seleccionados:
            add_flash(request, "Seleccione al menos un mes para adelantar.", "warning")
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        if not fecha_pago:
            add_flash(request, "Indique la fecha de pago.", "warning")
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        monto_mensual = float(pension.monto_mensual)

        # Construir datos desnormalizados
        estudiante_nombre = f"{estudiante.apellido_paterno_est} {estudiante.apellido_materno_est}, {estudiante.nombres_est}"
        pagador_nombre = f"{estudiante.apellido_paterno_apoderado or ''} {estudiante.apellido_materno_apoderado or ''}, {estudiante.nombres_apoderado or ''}".strip(', ')

        # Obtener saldos actuales para validar no exceder lo adeudado
        saldos = obtener_saldo_por_mes(estudiante_id, anio_actual)

        recibos_generados = []
        errores = []
        for mes in meses_seleccionados:
            monto_raw = (form.get(f"monto_mes_{mes}") or "").strip()
            try:
                monto_abono = round(float(monto_raw), 2) if monto_raw else monto_mensual
            except ValueError:
                errores.append(f'Monto inválido para {mes}')
                continue

            if monto_abono <= 0:
                errores.append(f'El monto para {mes} debe ser mayor a 0')
                continue

            # Restante real para este mes
            saldo_mes = saldos.get(mes, {})
            restante = saldo_mes.get('restante', monto_mensual)

            if restante <= 0:
                errores.append(f'{mes.capitalize()} ya está completamente pagado')
                continue

            # Limitar al máximo adeudado para ese mes
            monto_abono = min(monto_abono, restante)
            es_abono_parcial = monto_abono < restante

            obs_auto = 'Pago adelantado por apoderado'
            if es_abono_parcial:
                obs_auto = f'Abono parcial. Restante: S/ {round(restante - monto_abono, 2):.2f}'
            if observaciones:
                obs_auto = f'{obs_auto}. {observaciones}'

            numero_recibo = generar_numero_recibo()
            nuevo_pago = PagoPension(
                numero_recibo=numero_recibo,
                estudiante_id=estudiante_id,
                estudiante_nombre_completo=estudiante_nombre,
                estudiante_dni=estudiante.dni_est,
                estudiante_nivel=estudiante.nivel,
                estudiante_grado=estudiante.grado,
                pagador_nombre=pagador_nombre,
                pagador_dni=estudiante.dni_apoderado,
                pagador_relacion=estudiante.relacion_apoderado or 'Apoderado',
                pagador_telefono=estudiante.celular_apoderado,
                mes_pago=mes,
                anio_pago=anio_actual,
                monto_pagado=monto_abono,
                fecha_pago=fecha_pago,
                metodo_pago=metodo_pago,
                numero_operacion=numero_operacion or None,
                observaciones=obs_auto,
                estado='pagado',
                usuario_registro=request.session.get("username"),
            )
            db.session.add(nuevo_pago)
            recibos_generados.append((mes, numero_recibo, monto_abono))

        if errores:
            for err in errores:
                add_flash(request, err, "warning")

        if recibos_generados:
            db.session.commit()
            meses_str = ", ".join(f"{m.capitalize()} (S/ {amt:.2f})" for m, _, amt in recibos_generados)
            recibo_nums = ", ".join(r for _, r, _ in recibos_generados)
            add_flash(
                request,
                f"{len(recibos_generados)} pago(s) registrado(s): {meses_str}. Recibos: {recibo_nums}",
                "success",
            )
        return RedirectResponse(
            url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
            status_code=303,
        )

    except Exception as e:
        db.session.rollback()
        print(f"Error al adelantar cuotas: {e}")
        add_flash(request, "Error al registrar los pagos adelantados. Intente nuevamente.", "error")
        return RedirectResponse(
            url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
            status_code=303,
        )


# ============================================================
# PLAN DE PAGOS (cronograma + cuotas)
# ============================================================

@router.post("/asignar/{estudiante_id:int}/crear_plan", name="pensiones.crear_plan")
async def crear_plan(request: Request, estudiante_id: int, _user_id: int = Depends(get_current_user_id)):
    """Crea un plan de pagos: monto total dividido en N cuotas con fecha programada."""
    try:
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        estudiante = _est_or_404(estudiante_id)
        config = ConfiguracionPension.query.filter_by(activo=True).first()
        anio_actual = config.anio_escolar if config else str(datetime.now().year)

        pension = PensionEstudiante.query.filter_by(
            estudiante_id=estudiante_id,
            anio_escolar=anio_actual,
            activo=True,
        ).first()

        if not pension:
            add_flash(request, "El estudiante no tiene pensión asignada.", "error")
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        meses_seleccionados = form.getlist("meses_plan")
        if not meses_seleccionados:
            add_flash(request, "Seleccione al menos un mes para el plan.", "warning")
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        try:
            monto_total = round(float(form.get("monto_total_plan") or 0), 2)
        except ValueError:
            add_flash(request, "Monto total inválido.", "error")
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        if monto_total <= 0:
            add_flash(request, "El monto total debe ser mayor a 0.", "warning")
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        cuotas_montos = form.getlist("cuota_monto")
        cuotas_fechas = form.getlist("cuota_fecha")

        if not cuotas_montos or len(cuotas_montos) != len(cuotas_fechas):
            add_flash(request, "Defina al menos una cuota con monto y fecha.", "warning")
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        cuotas_data = []
        suma = 0.0
        for idx, (monto_raw, fecha_raw) in enumerate(zip(cuotas_montos, cuotas_fechas), start=1):
            try:
                monto = round(float(monto_raw), 2)
            except ValueError:
                add_flash(request, f"Monto inválido en cuota #{idx}.", "error")
                return RedirectResponse(
                    url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                    status_code=303,
                )
            if monto <= 0:
                add_flash(request, f"La cuota #{idx} debe ser mayor a 0.", "warning")
                return RedirectResponse(
                    url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                    status_code=303,
                )
            if not fecha_raw:
                add_flash(request, f"Indique fecha para la cuota #{idx}.", "warning")
                return RedirectResponse(
                    url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                    status_code=303,
                )
            cuotas_data.append((idx, monto, fecha_raw))
            suma += monto

        # Validar que la suma de cuotas coincida con el monto total (tolerancia 0.01)
        if abs(suma - monto_total) > 0.01:
            add_flash(
                request,
                f"La suma de cuotas (S/ {suma:.2f}) no coincide con el monto total (S/ {monto_total:.2f}).",
                "error",
            )
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        observaciones = (form.get("observaciones_plan") or "").strip() or None
        estudiante_nombre = (
            f"{estudiante.apellido_paterno_est} {estudiante.apellido_materno_est}, {estudiante.nombres_est}"
        )

        cronograma = CronogramaPagoPension(
            estudiante_id=estudiante_id,
            estudiante_nombre_completo=estudiante_nombre,
            anio_escolar=anio_actual,
            meses_cubiertos=",".join(meses_seleccionados),
            monto_total=monto_total,
            numero_cuotas=len(cuotas_data),
            estado='activo',
            observaciones=observaciones,
            usuario_registro=request.session.get("username"),
        )
        db.session.add(cronograma)
        db.session.flush()  # obtener id

        for numero, monto, fecha in cuotas_data:
            db.session.add(
                CuotaPagoPension(
                    cronograma_id=cronograma.id,
                    numero_cuota=numero,
                    monto=monto,
                    fecha_programada=fecha,
                    estado='programada',
                )
            )

        db.session.commit()
        add_flash(
            request,
            f"Plan de pagos creado: S/ {monto_total:.2f} en {len(cuotas_data)} cuota(s).",
            "success",
        )
        return RedirectResponse(
            url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
            status_code=303,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.session.rollback()
        print(f"Error al crear plan de pagos: {e}")
        add_flash(request, "Error al crear el plan de pagos. Intente nuevamente.", "error")
        return RedirectResponse(
            url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
            status_code=303,
        )


@router.post("/cuota/{cuota_id:int}/cobrar", name="pensiones.cobrar_cuota")
async def cobrar_cuota(request: Request, cuota_id: int, _user_id: int = Depends(get_current_user_id)):
    """Confirma el cobro de una cuota: genera PagoPension(s) aplicando FIFO sobre los meses cubiertos."""
    try:
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(
                url=request.headers.get("referer") or str(request.url_for("pensiones.dashboard")),
                status_code=303,
            )

        cuota = db.session.get(CuotaPagoPension, cuota_id)
        if not cuota:
            raise HTTPException(status_code=404)

        cronograma = cuota.cronograma
        estudiante_id = cronograma.estudiante_id

        if cuota.estado != 'programada':
            add_flash(request, f"La cuota #{cuota.numero_cuota} ya está {cuota.estado}.", "warning")
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        if cronograma.estado == 'anulado':
            add_flash(request, "El plan de pagos está anulado.", "error")
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        fecha_pago = form.get("fecha_pago_real") or cuota.fecha_programada
        metodo_pago = form.get("metodo_pago") or "efectivo"
        numero_operacion = (form.get("numero_operacion") or "").strip() or None

        estudiante = _est_or_404(estudiante_id)
        pension = PensionEstudiante.query.filter_by(
            estudiante_id=estudiante_id,
            anio_escolar=cronograma.anio_escolar,
            activo=True,
        ).first()

        if not pension:
            add_flash(request, "El estudiante ya no tiene pensión asignada.", "error")
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        monto_mensual = float(pension.monto_mensual)
        meses_cubiertos = [m.strip() for m in (cronograma.meses_cubiertos or "").split(",") if m.strip()]
        saldos = obtener_saldo_por_mes(estudiante_id, cronograma.anio_escolar)

        estudiante_nombre = (
            f"{estudiante.apellido_paterno_est} {estudiante.apellido_materno_est}, {estudiante.nombres_est}"
        )
        pagador_nombre = (
            f"{estudiante.apellido_paterno_apoderado or ''} {estudiante.apellido_materno_apoderado or ''}, "
            f"{estudiante.nombres_apoderado or ''}"
        ).strip(', ')

        restante_cuota = float(cuota.monto)
        recibos_generados = []

        # Repartir FIFO sobre los meses cubiertos por el cronograma.
        for mes in meses_cubiertos:
            if restante_cuota <= 0:
                break
            saldo_mes = saldos.get(mes, {})
            restante_mes = round(saldo_mes.get('restante', monto_mensual), 2)
            if restante_mes <= 0:
                continue
            abono = round(min(restante_cuota, restante_mes), 2)
            if abono <= 0:
                continue

            es_parcial = abono < restante_mes
            obs = f"Cobro cuota #{cuota.numero_cuota} de plan #{cronograma.id}"
            if es_parcial:
                obs += f". Restará en {mes}: S/ {round(restante_mes - abono, 2):.2f}"

            numero_recibo = generar_numero_recibo()
            nuevo_pago = PagoPension(
                numero_recibo=numero_recibo,
                estudiante_id=estudiante_id,
                estudiante_nombre_completo=estudiante_nombre,
                estudiante_dni=estudiante.dni_est,
                estudiante_nivel=estudiante.nivel,
                estudiante_grado=estudiante.grado,
                pagador_nombre=pagador_nombre,
                pagador_dni=estudiante.dni_apoderado,
                pagador_relacion=estudiante.relacion_apoderado or 'Apoderado',
                pagador_telefono=estudiante.celular_apoderado,
                mes_pago=mes,
                anio_pago=cronograma.anio_escolar,
                monto_pagado=abono,
                fecha_pago=fecha_pago,
                metodo_pago=metodo_pago,
                numero_operacion=numero_operacion,
                observaciones=obs,
                estado='pagado',
                usuario_registro=request.session.get("username"),
            )
            db.session.add(nuevo_pago)
            recibos_generados.append(numero_recibo)

            # Actualizar saldo en memoria para próxima iteración
            saldo_mes['restante'] = round(restante_mes - abono, 2)
            saldo_mes['pagado'] = round(saldo_mes.get('pagado', 0) + abono, 2)
            saldos[mes] = saldo_mes
            restante_cuota = round(restante_cuota - abono, 2)

        if not recibos_generados:
            add_flash(
                request,
                "No se pudo aplicar la cuota: los meses cubiertos ya están pagados. Anule el plan o ajuste meses.",
                "warning",
            )
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        # Si quedó remanente sin aplicar (todos los meses ya estaban cubiertos), avisamos.
        sobrante = round(restante_cuota, 2)
        if sobrante > 0:
            add_flash(
                request,
                f"Cuota cobrada con remanente sin aplicar: S/ {sobrante:.2f} (meses ya estaban cubiertos).",
                "warning",
            )

        cuota.estado = 'pagada'
        cuota.fecha_pago_real = fecha_pago
        cuota.metodo_pago = metodo_pago
        cuota.numero_operacion = numero_operacion
        cuota.usuario_cobro = request.session.get("username")
        cuota.fecha_cobro = datetime.utcnow()
        cuota.recibos_generados = ",".join(recibos_generados)

        # Si ya no queda ninguna programada, marcamos cronograma como completado
        pendientes = [c for c in cronograma.cuotas if c.id != cuota.id and c.estado == 'programada']
        if not pendientes:
            cronograma.estado = 'completado'

        db.session.commit()
        add_flash(
            request,
            f"Cuota #{cuota.numero_cuota} cobrada. Recibo(s): {', '.join(recibos_generados)}.",
            "success",
        )
        return RedirectResponse(
            url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
            status_code=303,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.session.rollback()
        print(f"Error al cobrar cuota: {e}")
        add_flash(request, "Error al registrar el cobro de la cuota. Intente nuevamente.", "error")
        return RedirectResponse(
            url=request.headers.get("referer") or str(request.url_for("pensiones.dashboard")),
            status_code=303,
        )


@router.post("/cronograma/{cronograma_id:int}/anular", name="pensiones.anular_plan")
async def anular_plan(request: Request, cronograma_id: int, _user_id: int = Depends(get_current_user_id)):
    """Anula un plan de pagos. Solo permitido si ninguna cuota ha sido cobrada."""
    try:
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(
                url=request.headers.get("referer") or str(request.url_for("pensiones.dashboard")),
                status_code=303,
            )

        cronograma = db.session.get(CronogramaPagoPension, cronograma_id)
        if not cronograma:
            raise HTTPException(status_code=404)

        estudiante_id = cronograma.estudiante_id
        motivo = (form.get("motivo_anulacion") or "").strip()

        if cronograma.estado == 'anulado':
            add_flash(request, "Este plan ya está anulado.", "warning")
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        if any(c.estado == 'pagada' for c in cronograma.cuotas):
            add_flash(
                request,
                "No se puede anular: el plan ya tiene cuotas cobradas. Anule los recibos individuales primero.",
                "error",
            )
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        if not motivo:
            add_flash(request, "Indique el motivo de anulación del plan.", "error")
            return RedirectResponse(
                url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
                status_code=303,
            )

        cronograma.estado = 'anulado'
        cronograma.fecha_anulacion = datetime.utcnow()
        cronograma.usuario_anulacion = request.session.get("username")
        cronograma.motivo_anulacion = motivo
        for c in cronograma.cuotas:
            if c.estado == 'programada':
                c.estado = 'anulada'

        db.session.commit()
        add_flash(request, "Plan de pagos anulado.", "success")
        return RedirectResponse(
            url=str(request.url_for("pensiones.asignar_form", estudiante_id=estudiante_id)),
            status_code=303,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.session.rollback()
        print(f"Error al anular plan: {e}")
        add_flash(request, "Error al anular el plan. Intente nuevamente.", "error")
        return RedirectResponse(
            url=request.headers.get("referer") or str(request.url_for("pensiones.dashboard")),
            status_code=303,
        )


@router.post("/adelantar_desde_registro", name="pensiones.adelantar_desde_registro")
async def adelantar_desde_registro(request: Request, _user_id: int = Depends(get_current_user_id)):
    """Registra pagos adelantados de varios meses desde la pantalla de registro"""
    try:
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(url=str(request.url_for("pensiones.registrar")), status_code=303)

        estudiante_id = int(form.get("estudiante_id"))
        estudiante = _est_or_404(estudiante_id)
        config = ConfiguracionPension.query.filter_by(activo=True).first()
        anio_actual = config.anio_escolar if config else str(datetime.now().year)

        pension = PensionEstudiante.query.filter_by(
            estudiante_id=estudiante_id,
            anio_escolar=anio_actual,
            activo=True,
        ).first()

        if not pension:
            add_flash(request, "El estudiante no tiene pensión asignada.", "error")
            return RedirectResponse(url=str(request.url_for("pensiones.registrar")), status_code=303)

        meses_seleccionados = form.getlist("meses_adelantar")
        fecha_pago = form.get("fecha_pago_adelanto")
        metodo_pago = form.get("metodo_pago_adelanto") or "efectivo"
        numero_operacion = (form.get("numero_operacion_adelanto") or "").strip()

        if not meses_seleccionados:
            add_flash(request, "Seleccione al menos un mes para adelantar.", "warning")
            return RedirectResponse(url=str(request.url_for("pensiones.registrar")), status_code=303)

        if not fecha_pago:
            add_flash(request, "Indique la fecha de pago.", "warning")
            return RedirectResponse(url=str(request.url_for("pensiones.registrar")), status_code=303)

        monto_mensual = float(pension.monto_mensual)
        estudiante_nombre = f"{estudiante.apellido_paterno_est} {estudiante.apellido_materno_est}, {estudiante.nombres_est}"
        pagador_nombre = f"{estudiante.apellido_paterno_apoderado or ''} {estudiante.apellido_materno_apoderado or ''}, {estudiante.nombres_apoderado or ''}".strip(', ')

        # Saldos actuales para validar montos personalizados
        saldos = obtener_saldo_por_mes(estudiante_id, anio_actual)

        recibos_generados = []
        errores = []

        for mes in meses_seleccionados:
            saldo_mes = saldos.get(mes, {})
            restante = round(saldo_mes.get('restante', monto_mensual), 2)

            if restante <= 0:
                errores.append(f'{mes.capitalize()} ya está completamente pagado')
                continue

            # Leer monto personalizado enviado desde el formulario
            monto_raw = (form.get(f"monto_mes_{mes}") or "").strip()
            try:
                monto_abono = round(float(monto_raw), 2) if monto_raw else restante
            except ValueError:
                errores.append(f'Monto inválido para {mes.capitalize()}')
                continue

            if monto_abono <= 0:
                errores.append(f'El monto para {mes.capitalize()} debe ser mayor a 0')
                continue

            # No puede superar el restante
            monto_abono = min(monto_abono, restante)

            # Observación automática
            es_parcial = monto_abono < restante
            if es_parcial:
                quedara = round(restante - monto_abono, 2)
                obs = f'Abono parcial adelantado. Restará: S/ {quedara:.2f}'
            else:
                obs = 'Pago adelantado completo por apoderado'

            numero_recibo = generar_numero_recibo()
            nuevo_pago = PagoPension(
                numero_recibo=numero_recibo,
                estudiante_id=estudiante_id,
                estudiante_nombre_completo=estudiante_nombre,
                estudiante_dni=estudiante.dni_est,
                estudiante_nivel=estudiante.nivel,
                estudiante_grado=estudiante.grado,
                pagador_nombre=pagador_nombre,
                pagador_dni=estudiante.dni_apoderado,
                pagador_relacion=estudiante.relacion_apoderado or 'Apoderado',
                pagador_telefono=estudiante.celular_apoderado,
                mes_pago=mes,
                anio_pago=anio_actual,
                monto_pagado=monto_abono,
                fecha_pago=fecha_pago,
                metodo_pago=metodo_pago,
                numero_operacion=numero_operacion or None,
                observaciones=obs,
                estado='pagado',
                usuario_registro=request.session.get("username"),
            )
            db.session.add(nuevo_pago)
            recibos_generados.append((mes, numero_recibo, monto_abono))

        if errores:
            for err in errores:
                add_flash(request, err, "warning")

        if recibos_generados:
            db.session.commit()
            meses_str = ", ".join(f"{m.capitalize()} (S/ {amt:.2f})" for m, _, amt in recibos_generados)
            recibo_nums = ", ".join(r for _, r, _ in recibos_generados)
            add_flash(
                request,
                f"{len(recibos_generados)} pago(s) adelantado(s) registrado(s): {meses_str}. Recibos: {recibo_nums}",
                "success",
            )

        return RedirectResponse(url=str(request.url_for("pensiones.historial")), status_code=303)

    except Exception as e:
        db.session.rollback()
        print(f"Error al adelantar cuotas desde registro: {e}")
        add_flash(request, "Error al registrar los pagos adelantados. Intente nuevamente.", "error")
        return RedirectResponse(url=str(request.url_for("pensiones.registrar")), status_code=303)


@router.post("/registrar_otros_pagos", name="pensiones.registrar_otros_pagos")
async def registrar_otros_pagos(request: Request, _user_id: int = Depends(get_current_user_id)):
    """Registra pagos generales (no pensiones) desde la pantalla de registro de pensiones"""
    try:
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(url=str(request.url_for("pensiones.registrar")), status_code=303)

        obligacion_ids = form.getlist("obligacion_ids[]")
        fecha_pago = form.get("fecha_pago_otros")
        forma_pago = form.get("forma_pago_otros") or "efectivo"
        numero_operacion = (form.get("numero_operacion_otros") or "").strip()

        if not obligacion_ids:
            add_flash(request, "Seleccione al menos una obligación para pagar.", "warning")
            return RedirectResponse(url=str(request.url_for("pensiones.registrar")), status_code=303)

        if not fecha_pago:
            add_flash(request, "Indique la fecha de pago.", "warning")
            return RedirectResponse(url=str(request.url_for("pensiones.registrar")), status_code=303)

        recibos_generados = []
        errores = []

        for ob_id in obligacion_ids:
            monto_raw = (form.get(f"monto_ob_{ob_id}") or "").strip()
            version = int(form.get(f"version_ob_{ob_id}") or 1)

            try:
                monto = float(monto_raw)
            except (ValueError, TypeError):
                errores.append(f'Monto inválido para obligación #{ob_id}')
                continue

            obs = f'N° Op: {numero_operacion}' if numero_operacion else None

            pago, error = PagoService.registrar_pago(
                obligacion_id=int(ob_id),
                monto_pagado=monto,
                fecha_pago=fecha_pago,
                forma_pago=forma_pago,
                observaciones=obs,
                version_actual=version,
                usuario=request.session.get("username"),
            )

            if error:
                errores.append(error)
            else:
                recibos_generados.append(pago.numero_recibo)

        if errores:
            for err in errores:
                add_flash(request, err, "warning")

        if recibos_generados:
            add_flash(
                request,
                f"{len(recibos_generados)} pago(s) registrado(s). Recibo(s): {', '.join(recibos_generados)}",
                "success",
            )

        return RedirectResponse(url=str(request.url_for("pensiones.registrar")), status_code=303)

    except Exception as e:
        db.session.rollback()
        print(f"Error al registrar otros pagos: {e}")
        add_flash(request, "Error al registrar los pagos. Intente nuevamente.", "error")
        return RedirectResponse(url=str(request.url_for("pensiones.registrar")), status_code=303)


@router.post("/api/buscar_estudiante", name="pensiones.buscar_estudiante")
async def buscar_estudiante(request: Request, _user_id: int = Depends(get_current_user_id)):
    """API para buscar estudiante por DNI o nombre"""
    try:
        data = await request.json()
        termino = (data.get("termino") or "").strip()

        if len(termino) < 3:
            return JSONResponse({"success": False, "message": "Ingrese al menos 3 caracteres"})

        # Buscar por DNI exacto
        estudiante = Estudiante.query.filter_by(dni_est=termino).first()

        # Si no se encuentra por DNI, buscar por nombre
        if not estudiante:
            # Búsqueda por nombre (case insensitive)
            estudiante = Estudiante.query.filter(
                or_(
                    Estudiante.nombres_est.ilike(f"%{termino}%"),
                    Estudiante.apellido_paterno_est.ilike(f"%{termino}%"),
                    Estudiante.apellido_materno_est.ilike(f"%{termino}%"),
                )
            ).first()

        if not estudiante:
            return JSONResponse(
                {"success": False, "message": "No se encontró ningún estudiante con ese DNI o nombre"}
            )

        config = ConfiguracionPension.query.filter_by(activo=True).first()
        if not config:
            return JSONResponse({"success": False, "message": "No hay configuración activa de pensiones"})

        anio_actual = config.anio_escolar

        # Verificar que el estudiante tenga pensión asignada
        pension = PensionEstudiante.query.filter_by(
            estudiante_id=estudiante.id,
            anio_escolar=anio_actual,
            activo=True
        ).first()

        if not pension:
            # Preparar datos del estudiante y apoderado
            nombre_completo = f"{estudiante.apellido_paterno_est} {estudiante.apellido_materno_est}, {estudiante.nombres_est}"
            nivel_grado = f"{estudiante.nivel.capitalize() if estudiante.nivel else '-'} - {estudiante.grado or '-'}"

            apoderado_nombre = f"{estudiante.apellido_paterno_apoderado or ''} {estudiante.apellido_materno_apoderado or ''}, {estudiante.nombres_apoderado or ''}".strip(', ')
            if not apoderado_nombre or apoderado_nombre == ',':
                apoderado_nombre = 'No registrado'

            # Obtener obligaciones generales pendientes (Otros Pagos funciona sin pensión)
            obligaciones = ObligacionPagoEstudiante.query.filter_by(
                estudiante_id=estudiante.id,
                anio_escolar=anio_actual
            ).filter(
                ObligacionPagoEstudiante.estado.in_(['pendiente', 'pagado_parcial'])
            ).all()

            obligaciones_data = [
                {
                    'id': ob.id,
                    'concepto': ob.concepto_nombre,
                    'monto_total': float(ob.monto_total),
                    'monto_pagado': float(ob.monto_pagado),
                    'monto_pendiente': float(ob.monto_pendiente),
                    'cuotas_pagadas': ob.cuotas_pagadas,
                    'total_cuotas': ob.numero_cuotas,
                    'version': ob.version
                }
                for ob in obligaciones
            ]

            return JSONResponse(
                {
                'success': True,
                'sin_pension': True,
                'estudiante': {
                    'id': estudiante.id,
                    'nombre_completo': nombre_completo,
                    'dni': estudiante.dni_est,
                    'nivel': estudiante.nivel,
                    'grado': estudiante.grado,
                    'nivel_grado': nivel_grado
                },
                'apoderado': {
                    'nombre': apoderado_nombre,
                    'dni': estudiante.dni_apoderado,
                    'relacion': estudiante.relacion_apoderado or 'Apoderado',
                    'telefono': estudiante.celular_apoderado
                },
                'pension': None,
                'meses_pendientes': [],
                'saldos_por_mes': {},
                'obligaciones': obligaciones_data,
                'message': f'El estudiante no tiene pensión asignada para el año {anio_actual}'
                }
            )

        meses_pendientes = obtener_meses_pendientes(estudiante.id, anio_actual)

        if not meses_pendientes:
            return JSONResponse({"success": False, "message": "El estudiante no tiene meses pendientes de pago"})

        # Preparar información del estudiante
        nombre_completo = f"{estudiante.apellido_paterno_est} {estudiante.apellido_materno_est}, {estudiante.nombres_est}"
        nivel_grado = f"{estudiante.nivel.capitalize() if estudiante.nivel else '-'} - {estudiante.grado or '-'}"

        # Preparar información del apoderado
        apoderado_nombre = f"{estudiante.apellido_paterno_apoderado or ''} {estudiante.apellido_materno_apoderado or ''}, {estudiante.nombres_apoderado or ''}".strip(', ')
        if not apoderado_nombre or apoderado_nombre == ',':
            apoderado_nombre = 'No registrado'

        # Saldos pendientes por mes (para mostrar restante en la UI)
        saldos_todos = obtener_saldo_por_mes(estudiante.id, anio_actual)
        saldos_por_mes = {
            mes: {
                'monto_mensual': saldos_todos[mes]['monto_mensual'],
                'pagado': saldos_todos[mes]['pagado'],
                'restante': saldos_todos[mes]['restante']
            }
            for mes in meses_pendientes
            if mes in saldos_todos
        }

        # Obtener obligaciones generales pendientes del estudiante
        obligaciones = ObligacionPagoEstudiante.query.filter_by(
            estudiante_id=estudiante.id,
            anio_escolar=anio_actual
        ).filter(
            ObligacionPagoEstudiante.estado.in_(['pendiente', 'pagado_parcial'])
        ).all()

        obligaciones_data = [
            {
                'id': ob.id,
                'concepto': ob.concepto_nombre,
                'monto_total': float(ob.monto_total),
                'monto_pagado': float(ob.monto_pagado),
                'monto_pendiente': float(ob.monto_pendiente),
                'cuotas_pagadas': ob.cuotas_pagadas,
                'total_cuotas': ob.numero_cuotas,
                'version': ob.version
            }
            for ob in obligaciones
        ]

        return JSONResponse({
            'success': True,
            'estudiante': {
                'id': estudiante.id,
                'nombre_completo': nombre_completo,
                'dni': estudiante.dni_est,
                'nivel': estudiante.nivel,
                'grado': estudiante.grado,
                'nivel_grado': nivel_grado
            },
            'apoderado': {
                'nombre': apoderado_nombre,
                'dni': estudiante.dni_apoderado,
                'relacion': estudiante.relacion_apoderado or 'Apoderado',
                'telefono': estudiante.celular_apoderado
            },
            'pension': {
                'id': pension.id,
                'monto': float(pension.monto_mensual)
            },
            'meses_pendientes': meses_pendientes,
            'saldos_por_mes': saldos_por_mes,
            'obligaciones': obligaciones_data
        })

    except Exception as e:
        print(f"Error al buscar estudiante: {e}")
        return JSONResponse({"success": False, "message": "Error al buscar el estudiante"})


@router.api_route("/registrar", methods=["GET", "POST"], name="pensiones.registrar")
async def registrar(request: Request, _user_id: int = Depends(get_current_user_id)):
    """Registrar pago de pensión"""
    if request.method == "POST":
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(url=str(request.url_for("pensiones.registrar")), status_code=303)
        try:
            estudiante_id = int(form.get("estudiante_id"))
            mes_pago = form.get("mes_pago")
            monto_pagado = float(form.get("monto_pagado"))
            fecha_pago = form.get("fecha_pago")
            metodo_pago = form.get("metodo_pago")
            numero_operacion = form.get("numero_operacion")
            observaciones = form.get("observaciones")

            estudiante = db.session.get(Estudiante, estudiante_id)
            if not estudiante:
                add_flash(request, "Estudiante no encontrado", "error")
                return RedirectResponse(url=str(request.url_for("pensiones.registrar")), status_code=303)

            # Obtener configuración activa
            config = ConfiguracionPension.query.filter_by(activo=True).first()
            anio_actual = config.anio_escolar

            # Verificar que el mes no esté ya pagado
            pago_existente = PagoPension.query.filter_by(
                estudiante_id=estudiante_id,
                mes_pago=mes_pago,
                anio_pago=anio_actual,
                estado='pagado'
            ).first()

            if pago_existente:
                add_flash(request, f"El mes de {mes_pago} ya ha sido pagado", "error")
                return RedirectResponse(url=str(request.url_for("pensiones.registrar")), status_code=303)

            # Generar número de recibo
            numero_recibo = generar_numero_recibo()

            # Construir nombres completos
            estudiante_nombre = f"{estudiante.apellido_paterno_est} {estudiante.apellido_materno_est}, {estudiante.nombres_est}"
            pagador_nombre = f"{estudiante.apellido_paterno_apoderado or ''} {estudiante.apellido_materno_apoderado or ''}, {estudiante.nombres_apoderado or ''}".strip(', ')

            # Crear registro de pago
            nuevo_pago = PagoPension(
                numero_recibo=numero_recibo,
                estudiante_id=estudiante_id,
                estudiante_nombre_completo=estudiante_nombre,
                estudiante_dni=estudiante.dni_est,
                estudiante_nivel=estudiante.nivel,
                estudiante_grado=estudiante.grado,
                pagador_nombre=pagador_nombre,
                pagador_dni=estudiante.dni_apoderado,
                pagador_relacion=estudiante.relacion_apoderado or 'Apoderado',
                pagador_telefono=estudiante.celular_apoderado,
                mes_pago=mes_pago,
                anio_pago=anio_actual,
                monto_pagado=monto_pagado,
                fecha_pago=fecha_pago,
                metodo_pago=metodo_pago,
                numero_operacion=numero_operacion,
                observaciones=observaciones,
                estado="pagado",
                usuario_registro=request.session.get("username"),
            )

            db.session.add(nuevo_pago)
            db.session.commit()

            add_flash(request, f"Pago registrado exitosamente. Recibo N° {numero_recibo}", "success")
            return RedirectResponse(
                url=str(request.url_for("pensiones.recibo_preview", pago_id=nuevo_pago.id)),
                status_code=303,
            )

        except Exception as e:
            db.session.rollback()
            print(f"Error al registrar pago: {e}")
            add_flash(request, "Error al registrar el pago. Intente nuevamente.", "error")

    from datetime import datetime as dt

    return templates.TemplateResponse(
        "pensiones/registrar_pago.html", common_context(request, now=dt.now())
    )


@router.get("/recibo/{pago_id:int}/preview", name="pensiones.recibo_preview")
def recibo_preview(request: Request, pago_id: int, _user_id: int = Depends(get_current_user_id)):
    """Vista previa del recibo de pago"""
    try:
        pago = _pago_or_404(pago_id)
        config = ConfiguracionPension.query.filter_by(activo=True).first()

        pension = PensionEstudiante.query.filter_by(
            estudiante_id=pago.estudiante_id,
            anio_escolar=pago.anio_pago,
            activo=True
        ).first()
        monto_mensual = float(pension.monto_mensual) if pension else None

        return templates.TemplateResponse(
            "pensiones/recibo_preview.html",
            common_context(request, pago=pago, config=config, monto_mensual=monto_mensual),
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al mostrar recibo: {e}")
        add_flash(request, "Error al cargar el recibo", "error")
        return RedirectResponse(url=str(request.url_for("pensiones.historial")), status_code=303)


@router.get("/recibo/{pago_id:int}/pdf", name="pensiones.recibo_pdf")
def recibo_pdf(request: Request, pago_id: int, _user_id: int = Depends(get_current_user_id)):
    """Generar y descargar recibo en formato PDF 80mm"""
    try:
        pago = _pago_or_404(pago_id)
        config = ConfiguracionPension.query.filter_by(activo=True).first()

        # Monto mensual para badge completo/parcial
        pension_obj = PensionEstudiante.query.filter_by(
            estudiante_id=pago.estudiante_id,
            anio_escolar=pago.anio_pago,
            activo=True
        ).first()
        monto_mensual_pdf = float(pension_obj.monto_mensual) if pension_obj else None

        # Crear buffer de memoria
        buffer = BytesIO()

        # Tamaño de ticket térmico 80mm
        width = 80 * mm_unit
        height = 280 * mm_unit  # Altura ajustable

        # Crear canvas
        c = canvas.Canvas(buffer, pagesize=(width, height))

        # Posición Y inicial
        y = height - 20

        # Header - Institución
        c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(width / 2, y, config.nombre_institucion)
        y -= 15

        c.setFont("Helvetica", 8)
        if config.ruc_institucion:
            c.drawCentredString(width / 2, y, f"RUC: {config.ruc_institucion}")
            y -= 12
        if config.direccion_institucion:
            c.drawCentredString(width / 2, y, config.direccion_institucion)
            y -= 12
        if config.telefono_institucion:
            c.drawCentredString(width / 2, y, f"Tel: {config.telefono_institucion}")
            y -= 15

        # Línea separadora
        c.line(10, y, width - 10, y)
        y -= 15

        # Título
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(width / 2, y, "RECIBO DE PAGO")
        y -= 15

        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(width / 2, y, f"N° {pago.numero_recibo}")
        y -= 15

        # Línea separadora
        c.line(10, y, width - 10, y)
        y -= 15

        # Fecha
        c.setFont("Helvetica", 8)
        c.drawString(10, y, f"Fecha: {pago.fecha_pago}")
        y -= 15

        # Datos del Estudiante
        c.setFont("Helvetica-Bold", 8)
        c.drawString(10, y, "Estudiante:")
        y -= 12

        c.setFont("Helvetica", 8)
        c.drawString(10, y, pago.estudiante_nombre_completo[:35])
        y -= 10
        c.drawString(10, y, f"DNI: {pago.estudiante_dni or '-'}")
        y -= 10
        c.drawString(10, y, f"Grado: {pago.estudiante_grado or '-'} - {pago.estudiante_nivel or '-'}")
        y -= 15

        # Datos del Apoderado
        c.setFont("Helvetica-Bold", 8)
        c.drawString(10, y, "Apoderado:")
        y -= 12

        c.setFont("Helvetica", 8)
        c.drawString(10, y, pago.pagador_nombre[:35])
        y -= 10
        c.drawString(10, y, f"DNI: {pago.pagador_dni or '-'}")
        y -= 15

        # Línea separadora
        c.line(10, y, width - 10, y)
        y -= 15

        # Concepto
        c.setFont("Helvetica-Bold", 8)
        c.drawString(10, y, "Concepto:")
        y -= 12

        c.setFont("Helvetica", 8)
        c.drawString(10, y, f"Pensión {pago.mes_pago.capitalize()} {pago.anio_pago}")
        y -= 10
        c.drawString(10, y, f"Método: {pago.metodo_pago.capitalize()}")
        y -= 15

        if pago.numero_operacion:
            c.drawString(10, y, f"N° Op: {pago.numero_operacion}")
            y -= 12

        if pago.observaciones:
            # Truncar líneas largas para que quepan en 80mm (~45 chars)
            obs = pago.observaciones
            linea1 = obs[:45]
            linea2 = obs[45:90] if len(obs) > 45 else None
            c.drawString(10, y, f"Obs: {linea1}")
            y -= 10
            if linea2:
                c.drawString(10, y, f"     {linea2}")
                y -= 10
            y -= 5

        # Línea separadora
        c.line(10, y, width - 10, y)
        y -= 15

        # Monto (en grande)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width / 2, y, f"MONTO: S/ {pago.monto_pagado:.2f}")
        y -= 14

        # Badge: Pago completo / Abono parcial
        if monto_mensual_pdf:
            c.setFont("Helvetica-Bold", 9)
            if float(pago.monto_pagado) >= monto_mensual_pdf:
                c.drawCentredString(width / 2, y, "[ PAGO COMPLETO ]")
                y -= 14
            else:
                restante_pdf = round(monto_mensual_pdf - float(pago.monto_pagado), 2)
                c.drawCentredString(width / 2, y, "[ ABONO PARCIAL ]")
                y -= 11
                c.setFont("Helvetica", 8)
                c.drawCentredString(width / 2, y, f"Restante: S/ {restante_pdf:.2f}")
                y -= 14
        else:
            y -= 6

        # Línea separadora
        c.line(10, y, width - 10, y)
        y -= 15

        # Footer
        c.setFont("Helvetica", 8)
        c.drawCentredString(width / 2, y, "Gracias por su pago")
        y -= 12
        c.drawCentredString(width / 2, y, "Sistema de Gestión Escolar")
        y -= 10
        c.setFont("Helvetica", 6)
        c.drawCentredString(width / 2, y, f"Registrado por: {pago.usuario_registro}")

        # Finalizar PDF
        c.save()

        # Preparar respuesta - Usar Response en lugar de send_file para evitar error de fileno en producción
        buffer.seek(0)
        return Response(
            content=buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=recibo_{pago.numero_recibo}.pdf",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error al generar PDF: {e}")
        add_flash(request, "Error al generar el PDF del recibo", "error")
        return RedirectResponse(
            url=str(request.url_for("pensiones.recibo_preview", pago_id=pago_id)),
            status_code=303,
        )


@router.get("/historial", name="pensiones.historial")
def historial(request: Request, _user_id: int = Depends(get_current_user_id)):
    """Historial de pagos con filtros"""
    try:
        estudiante = (request.query_params.get("estudiante") or "").strip()
        mes = (request.query_params.get("mes") or "").strip()
        anio = (request.query_params.get("anio") or "").strip()
        estado = (request.query_params.get("estado") or "").strip()

        query = PagoPension.query

        if estudiante:
            query = query.filter(
                or_(
                    PagoPension.estudiante_nombre_completo.ilike(f"%{estudiante}%"),
                    PagoPension.estudiante_dni.ilike(f"%{estudiante}%"),
                )
            )

        if mes:
            query = query.filter(PagoPension.mes_pago == mes)

        if anio:
            query = query.filter(PagoPension.anio_pago == anio)

        if estado:
            query = query.filter(PagoPension.estado == estado)

        # Ordenar por fecha de registro más reciente
        pagos = query.order_by(PagoPension.fecha_registro.desc()).all()

        # Lookup: "{estudiante_id}_{anio}" -> monto_mensual  (para badge completo/parcial)
        pensiones_list = PensionEstudiante.query.filter_by(activo=True).all()
        pension_lookup = {
            f"{p.estudiante_id}_{p.anio_escolar}": float(p.monto_mensual)
            for p in pensiones_list
        }

        return templates.TemplateResponse(
            "pensiones/historial.html",
            common_context(request, pagos=pagos, pension_lookup=pension_lookup),
        )

    except Exception as e:
        print(f"Error al cargar historial: {e}")
        add_flash(request, "Error al cargar el historial de pagos", "error")
        return templates.TemplateResponse(
            "pensiones/historial.html",
            common_context(request, pagos=[], pension_lookup={}),
        )


@router.post("/anular/{pago_id:int}", name="pensiones.anular")
async def anular(request: Request, pago_id: int, _user_id: int = Depends(get_current_user_id)):
    """Anular un pago de pensión"""
    try:
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(url=str(request.url_for("pensiones.historial")), status_code=303)

        pago = _pago_or_404(pago_id)

        if pago.estado == "anulado":
            add_flash(request, "Este pago ya está anulado", "warning")
            return RedirectResponse(url=str(request.url_for("pensiones.historial")), status_code=303)

        motivo = (form.get("motivo_anulacion") or "").strip()

        if not motivo:
            add_flash(request, "Debe proporcionar un motivo para anular el pago", "error")
            return RedirectResponse(url=str(request.url_for("pensiones.historial")), status_code=303)

        pago.estado = "anulado"
        pago.fecha_anulacion = datetime.utcnow()
        pago.usuario_anulacion = request.session.get("username")
        pago.motivo_anulacion = motivo

        # Sincronizar cuotas del plan: si este recibo provino de cobrar una cuota,
        # quitarlo de cuota.recibos_generados y revertir estado si quedó sin recibos vivos.
        cuota_revertida = None
        cuotas_relacionadas = CuotaPagoPension.query.filter(
            CuotaPagoPension.recibos_generados.like(f"%{pago.numero_recibo}%")
        ).all()
        for cuota in cuotas_relacionadas:
            recibos = [r.strip() for r in (cuota.recibos_generados or "").split(",") if r.strip()]
            if pago.numero_recibo not in recibos:
                continue  # falso positivo del LIKE (substring)
            recibos.remove(pago.numero_recibo)
            cuota.recibos_generados = ",".join(recibos) or None
            if not recibos:
                cuota.estado = "programada"
                cuota.fecha_pago_real = None
                cuota.metodo_pago = None
                cuota.numero_operacion = None
                cuota.usuario_cobro = None
                cuota.fecha_cobro = None
                cronograma = cuota.cronograma
                if cronograma and cronograma.estado == "completado":
                    cronograma.estado = "activo"
                cuota_revertida = cuota

        db.session.commit()

        if cuota_revertida is not None:
            add_flash(
                request,
                f"Pago {pago.numero_recibo} anulado. Cuota #{cuota_revertida.numero_cuota} del plan revertida a 'programada'.",
                "success",
            )
        else:
            add_flash(request, f"Pago {pago.numero_recibo} anulado exitosamente", "success")
        return RedirectResponse(url=str(request.url_for("pensiones.historial")), status_code=303)

    except HTTPException:
        raise
    except Exception as e:
        db.session.rollback()
        print(f"Error al anular pago: {e}")
        add_flash(request, "Error al anular el pago. Intente nuevamente.", "error")
        return RedirectResponse(url=str(request.url_for("pensiones.historial")), status_code=303)
