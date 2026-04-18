# utils/helpers.py
from models import db, ConfiguracionPension, PagoPension, PensionEstudiante, Estudiante
from datetime import datetime as dt


def generar_numero_recibo():
    """Genera un número de recibo correlativo único (thread-safe)"""
    # Usar SELECT FOR UPDATE para prevenir race conditions
    # Esto bloquea la fila hasta que se complete la transacción
    config = db.session.query(ConfiguracionPension)\
        .filter_by(activo=True)\
        .with_for_update()\
        .first()

    if not config:
        raise Exception("No hay configuración activa de pensiones")

    numero = f"{config.serie_recibo}-{str(config.numero_correlativo).zfill(7)}"
    config.numero_correlativo += 1
    db.session.commit()

    return numero


def obtener_meses_pendientes(estudiante_id, anio):
    """Obtiene los meses pendientes de pago para un estudiante.
    Un mes se considera pagado cuando la suma de abonos >= monto_mensual."""
    pension = PensionEstudiante.query.filter_by(
        estudiante_id=estudiante_id,
        anio_escolar=anio,
        activo=True
    ).first()
    monto_mensual = float(pension.monto_mensual) if pension else 0

    # Para academia se usan los meses propios; para regular los de la configuración global
    if pension and pension.tipo == 'academia' and pension.meses_activos:
        meses_activos = [m.strip() for m in pension.meses_activos.split(',') if m.strip()]
    else:
        config = ConfiguracionPension.query.filter_by(activo=True, anio_escolar=anio).first()
        if not config or not config.meses_activos:
            return []
        meses_activos = [m.strip() for m in config.meses_activos.split(',') if m.strip()]

    if not meses_activos:
        return []

    # Sumar todos los abonos activos por mes
    pagos = PagoPension.query.filter_by(
        estudiante_id=estudiante_id,
        anio_pago=anio,
        estado='pagado'
    ).all()

    acumulado = {}
    for p in pagos:
        acumulado[p.mes_pago] = acumulado.get(p.mes_pago, 0.0) + float(p.monto_pagado)

    # Mes pendiente = acumulado < monto_mensual (o sin ningún pago)
    meses_pendientes = [
        m for m in meses_activos
        if acumulado.get(m, 0.0) < monto_mensual
    ]
    return meses_pendientes


def obtener_saldo_por_mes(estudiante_id, anio):
    """Devuelve el detalle de saldo por cada mes activo.
    Returns:
        dict: {mes: {'monto_mensual': X, 'pagado': Y, 'restante': Z, 'completado': bool}}
    """
    pension = PensionEstudiante.query.filter_by(
        estudiante_id=estudiante_id,
        anio_escolar=anio,
        activo=True
    ).first()
    monto_mensual = float(pension.monto_mensual) if pension else 0

    if pension and pension.tipo == 'academia' and pension.meses_activos:
        meses_activos = [m.strip() for m in pension.meses_activos.split(',') if m.strip()]
    else:
        config = ConfiguracionPension.query.filter_by(activo=True, anio_escolar=anio).first()
        if not config or not config.meses_activos:
            return {}
        meses_activos = [m.strip() for m in config.meses_activos.split(',') if m.strip()]

    if not meses_activos:
        return {}

    pagos = PagoPension.query.filter_by(
        estudiante_id=estudiante_id,
        anio_pago=anio,
        estado='pagado'
    ).all()

    acumulado = {}
    for p in pagos:
        acumulado[p.mes_pago] = acumulado.get(p.mes_pago, 0.0) + float(p.monto_pagado)

    saldos = {}
    for mes in meses_activos:
        pagado = round(acumulado.get(mes, 0.0), 2)
        restante = round(max(0.0, monto_mensual - pagado), 2)
        saldos[mes] = {
            'monto_mensual': monto_mensual,
            'pagado': pagado,
            'restante': restante,
            'completado': pagado >= monto_mensual
        }
    return saldos


def calcular_estadisticas_pensiones():
    """Calcula las estadísticas del dashboard de pensiones"""
    # Obtener configuración activa
    config = ConfiguracionPension.query.filter_by(activo=True).first()
    anio_actual = config.anio_escolar if config else str(dt.now().year)

    # Mes actual
    mes_actual = dt.now().strftime('%B').lower()
    meses_es = {
        'january': 'enero', 'february': 'febrero', 'march': 'marzo',
        'april': 'abril', 'may': 'mayo', 'june': 'junio',
        'july': 'julio', 'august': 'agosto', 'september': 'septiembre',
        'october': 'octubre', 'november': 'noviembre', 'december': 'diciembre'
    }
    mes_actual_es = meses_es.get(mes_actual, 'marzo')

    # Estadísticas
    total_estudiantes = Estudiante.query.count()

    # Pagos del mes actual
    pagos_mes = PagoPension.query.filter_by(
        mes_pago=mes_actual_es,
        anio_pago=anio_actual,
        estado='pagado'
    ).count()

    # Monto recaudado este mes
    monto_recaudado = db.session.query(
        db.func.sum(PagoPension.monto_pagado)
    ).filter_by(
        mes_pago=mes_actual_es,
        anio_pago=anio_actual,
        estado='pagado'
    ).scalar() or 0

    # Estudiantes con pensión asignada
    estudiantes_con_pension = PensionEstudiante.query.filter_by(
        anio_escolar=anio_actual,
        activo=True
    ).count()

    # Pagos pendientes (estudiantes con pensión - pagos realizados del mes)
    pagos_pendientes = max(0, estudiantes_con_pension - pagos_mes)

    return {
        'total_estudiantes': total_estudiantes,
        'pagos_mes': pagos_mes,
        'pagos_pendientes': pagos_pendientes,
        'monto_recaudado': float(monto_recaudado)
    }


def obtener_pagos_pendientes_lista(anio_actual):
    """Obtiene la lista de estudiantes con pagos pendientes"""
    estudiantes_con_pension_obj = PensionEstudiante.query.filter_by(
        anio_escolar=anio_actual,
        activo=True
    ).all()

    pagos_pendientes_list = []
    for pension in estudiantes_con_pension_obj:
        meses_pendientes = obtener_meses_pendientes(pension.estudiante_id, anio_actual)
        if meses_pendientes:
            pagos_pendientes_list.append({
                'estudiante_nombre': pension.estudiante_nombre_completo,
                'nivel': pension.estudiante_nivel,
                'grado': pension.estudiante_grado,
                'meses_pendientes': len(meses_pendientes),
                'monto': float(pension.monto_mensual)
            })

    # Ordenar por más meses pendientes
    pagos_pendientes_list.sort(key=lambda x: x['meses_pendientes'], reverse=True)

    return pagos_pendientes_list
