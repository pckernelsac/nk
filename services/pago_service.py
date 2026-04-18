# services/pago_service.py
from models import db, TipoPago, ConceptoPagoCiclo, ObligacionPagoEstudiante, PagoGeneral, Estudiante, ConfiguracionPension, AuditLog, Matricula
from sqlalchemy.exc import IntegrityError
from datetime import datetime, date


class PagoService:
    """Servicio para gestionar el sistema de pagos generales (no pensiones)"""

    @staticmethod
    def crear_tipo_pago(nombre, codigo, categoria=None, descripcion=None, usuario=None):
        """Crea un tipo de pago"""
        try:
            tipo = TipoPago(
                nombre=nombre,
                codigo=codigo.upper(),
                categoria=categoria,
                descripcion=descripcion,
                activo=True,
                usuario_registro=usuario
            )

            db.session.add(tipo)
            db.session.commit()

            AuditLog.registrar(
                tabla='tipos_pago',
                registro_id=tipo.id,
                accion='crear',
                usuario=usuario,
                detalles=f"Tipo de pago creado: {tipo.nombre}"
            )

            return tipo, None

        except IntegrityError:
            db.session.rollback()
            return None, f"Ya existe un tipo de pago con el código {codigo}"
        except Exception as e:
            db.session.rollback()
            return None, f"Error al crear tipo de pago: {str(e)}"

    @staticmethod
    def crear_concepto_ciclo(tipo_pago_id, anio_escolar, monto, nivel=None, grado=None,
                            permite_cuotas=False, numero_cuotas_max=1, usuario=None):
        """Crea un concepto de pago para un ciclo escolar"""
        try:
            tipo = TipoPago.query.get(tipo_pago_id)
            if not tipo:
                return None, "Tipo de pago no encontrado"

            concepto = ConceptoPagoCiclo(
                tipo_pago_id=tipo_pago_id,
                tipo_pago_nombre=tipo.nombre,
                anio_escolar=anio_escolar,
                monto=monto,
                nivel=nivel,
                grado=grado,
                permite_cuotas=permite_cuotas,
                numero_cuotas_max=numero_cuotas_max,
                activo=True,
                usuario_registro=usuario
            )

            db.session.add(concepto)
            db.session.commit()

            AuditLog.registrar(
                tabla='conceptos_pago_ciclo',
                registro_id=concepto.id,
                accion='crear',
                usuario=usuario,
                detalles=f"Concepto creado: {concepto.tipo_pago_nombre} - {anio_escolar} - S/{monto}"
            )

            return concepto, None

        except IntegrityError:
            db.session.rollback()
            return None, "Ya existe un concepto con esa configuración"
        except Exception as e:
            db.session.rollback()
            return None, f"Error al crear concepto: {str(e)}"

    @staticmethod
    def asignar_obligacion(concepto_id, estudiante_id, numero_cuotas=1,
                          fecha_vencimiento=None, usuario=None):
        """Asigna una obligación de pago a un estudiante"""
        try:
            concepto = ConceptoPagoCiclo.query.get(concepto_id)
            if not concepto:
                return None, "Concepto no encontrado"

            estudiante = Estudiante.query.get(estudiante_id)
            if not estudiante:
                return None, "Estudiante no encontrado"

            # Validar número de cuotas
            if numero_cuotas > concepto.numero_cuotas_max:
                return None, f"El número de cuotas excede el máximo permitido ({concepto.numero_cuotas_max})"

            # Verificar si ya tiene esta obligación
            existe = ObligacionPagoEstudiante.query.filter_by(
                concepto_id=concepto_id,
                estudiante_id=estudiante_id,
                anio_escolar=concepto.anio_escolar
            ).first()

            if existe:
                return None, f"El estudiante ya tiene asignada esta obligación para el año {concepto.anio_escolar}"

            obligacion = ObligacionPagoEstudiante(
                concepto_id=concepto_id,
                estudiante_id=estudiante_id,
                concepto_nombre=concepto.tipo_pago_nombre,
                estudiante_nombre_completo=estudiante.nombre_completo(),
                estudiante_dni=estudiante.dni_est,
                anio_escolar=concepto.anio_escolar,
                monto_total=concepto.monto,
                monto_pagado=0,
                monto_pendiente=concepto.monto,
                numero_cuotas=numero_cuotas,
                cuotas_pagadas=0,
                estado='pendiente',
                fecha_vencimiento=fecha_vencimiento,
                usuario_registro=usuario
            )

            db.session.add(obligacion)
            db.session.commit()

            AuditLog.registrar(
                tabla='obligaciones_pago_estudiante',
                registro_id=obligacion.id,
                accion='crear',
                usuario=usuario,
                detalles=f"Obligación asignada: {estudiante.nombre_completo()} - {concepto.tipo_pago_nombre}"
            )

            return obligacion, None

        except IntegrityError:
            db.session.rollback()
            return None, "Ya existe esta obligación para el estudiante"
        except Exception as e:
            db.session.rollback()
            return None, f"Error al asignar obligación: {str(e)}"

    @staticmethod
    def asignar_obligaciones_masivo(concepto_id, filtros, numero_cuotas=1, usuario=None):
        """
        Asigna obligaciones de forma masiva según filtros
        filtros: {'nivel': 'Secundaria', 'grado': '5to', 'seccion': 'A', 'anio_escolar': '2025'}
        """
        try:
            concepto = ConceptoPagoCiclo.query.get(concepto_id)
            if not concepto:
                return None, "Concepto no encontrado"

            # Obtener estudiantes según filtros usando matrículas
            anio_escolar = filtros.get('anio_escolar', '2025')

            query = Estudiante.query.join(Matricula).filter(
                Matricula.anio_escolar == anio_escolar,
                Matricula.estado == 'activo'
            )

            if filtros.get('nivel'):
                query = query.filter(Estudiante.nivel == filtros['nivel'])
            if filtros.get('grado'):
                query = query.filter(Estudiante.grado == filtros['grado'])
            if filtros.get('seccion'):
                query = query.filter(Estudiante.seccion == filtros['seccion'])

            estudiantes = query.distinct().all()

            if not estudiantes:
                return None, "No se encontraron estudiantes con los filtros aplicados"

            creados = 0
            errores = []

            for estudiante in estudiantes:
                # Verificar si ya tiene la obligación
                existe = ObligacionPagoEstudiante.query.filter_by(
                    concepto_id=concepto_id,
                    estudiante_id=estudiante.id,
                    anio_escolar=concepto.anio_escolar
                ).first()

                if existe:
                    continue  # Saltar si ya existe

                obligacion = ObligacionPagoEstudiante(
                    concepto_id=concepto_id,
                    estudiante_id=estudiante.id,
                    concepto_nombre=concepto.tipo_pago_nombre,
                    estudiante_nombre_completo=estudiante.nombre_completo(),
                    estudiante_dni=estudiante.dni_est,
                    anio_escolar=concepto.anio_escolar,
                    monto_total=concepto.monto,
                    monto_pagado=0,
                    monto_pendiente=concepto.monto,
                    numero_cuotas=numero_cuotas,
                    cuotas_pagadas=0,
                    estado='pendiente',
                    usuario_registro=usuario
                )

                db.session.add(obligacion)
                creados += 1

            db.session.commit()

            AuditLog.registrar(
                tabla='obligaciones_pago_estudiante',
                registro_id=None,
                accion='crear_masivo',
                usuario=usuario,
                detalles=f"Asignación masiva: {creados} obligaciones creadas - {concepto.tipo_pago_nombre}"
            )

            return {
                'creados': creados,
                'total_estudiantes': len(estudiantes),
                'ya_tenian': len(estudiantes) - creados
            }, None

        except Exception as e:
            db.session.rollback()
            return None, f"Error en asignación masiva: {str(e)}"

    @staticmethod
    def generar_numero_recibo_general():
        """Genera el siguiente número de recibo para pagos generales (Serie 002)
        Usa with_for_update() para prevenir race conditions con recibos duplicados"""
        try:
            config = ConfiguracionPension.query.filter_by(
                activo=True
            ).with_for_update().first()

            if not config:
                config = ConfiguracionPension(
                    nombre_institucion='Institución Educativa',
                    anio_escolar='2025',
                    meses_activos='',
                    serie_recibo='001',
                    numero_correlativo=1,
                    serie_recibo_general='002',
                    numero_correlativo_general=1,
                    activo=True
                )
                db.session.add(config)
                db.session.flush()

            numero_recibo = f"{config.serie_recibo_general}-{config.numero_correlativo_general:07d}"
            config.numero_correlativo_general += 1

            return numero_recibo, None

        except Exception as e:
            return None, f"Error al generar número de recibo: {str(e)}"

    @staticmethod
    def registrar_pago(obligacion_id, monto_pagado, fecha_pago, forma_pago='efectivo',
                      apoderado_nombre=None, apoderado_dni=None, observaciones=None,
                      version_actual=1, usuario=None):
        """Registra un pago para una obligación"""
        try:
            obligacion = ObligacionPagoEstudiante.query.get(obligacion_id)
            if not obligacion:
                return None, "Obligación no encontrada"

            # Control de concurrencia
            if obligacion.version != version_actual:
                return None, "Los datos fueron modificados por otro usuario. Recargue la página."

            # Validar estado
            if obligacion.estado == 'anulado':
                return None, "No se puede pagar una obligación anulada"

            if obligacion.estado == 'pagado_total':
                return None, "Esta obligación ya está totalmente pagada"

            # Validar monto
            monto_pagado = float(monto_pagado)
            if monto_pagado <= 0:
                return None, "El monto debe ser mayor a cero"

            if monto_pagado > obligacion.monto_pendiente:
                return None, f"El monto excede el monto pendiente (S/{obligacion.monto_pendiente})"

            # Obtener estudiante
            estudiante = Estudiante.query.get(obligacion.estudiante_id)
            if not estudiante:
                return None, "Estudiante no encontrado"

            # Generar número de recibo
            numero_recibo, error = PagoService.generar_numero_recibo_general()
            if error:
                return None, error

            # Parsear fecha si viene como string
            if isinstance(fecha_pago, str):
                fecha_pago = datetime.strptime(fecha_pago, '%Y-%m-%d').date()

            # Calcular número de cuota
            numero_cuota = obligacion.cuotas_pagadas + 1

            # Crear pago
            pago = PagoGeneral(
                numero_recibo=numero_recibo,
                obligacion_id=obligacion_id,
                estudiante_id=estudiante.id,
                estudiante_nombre_completo=estudiante.nombre_completo(),
                estudiante_dni=estudiante.dni_est,
                estudiante_nivel=estudiante.nivel,
                estudiante_grado=estudiante.grado,
                apoderado_nombre=apoderado_nombre,
                apoderado_dni=apoderado_dni,
                concepto_nombre=obligacion.concepto_nombre,
                anio_escolar=obligacion.anio_escolar,
                monto_pagado=monto_pagado,
                numero_cuota=numero_cuota,
                total_cuotas=obligacion.numero_cuotas,
                fecha_pago=fecha_pago,
                forma_pago=forma_pago,
                observaciones=observaciones,
                estado='pagado',
                usuario_registro=usuario
            )

            db.session.add(pago)

            # Actualizar obligación
            obligacion.monto_pagado += monto_pagado
            obligacion.cuotas_pagadas += 1
            obligacion.version += 1
            obligacion.actualizar_estado()

            db.session.commit()

            AuditLog.registrar(
                tabla='pagos_generales',
                registro_id=pago.id,
                accion='crear',
                usuario=usuario,
                detalles=f"Pago registrado: {numero_recibo} - {obligacion.concepto_nombre} - S/{monto_pagado}"
            )

            return pago, None

        except Exception as e:
            db.session.rollback()
            return None, f"Error al registrar pago: {str(e)}"

    @staticmethod
    def anular_pago(pago_id, motivo, usuario=None):
        """Anula un pago y revierte la obligación"""
        try:
            pago = PagoGeneral.query.get(pago_id)
            if not pago:
                return None, "Pago no encontrado"

            if pago.estado == 'anulado':
                return None, "Este pago ya está anulado"

            # Obtener obligación
            obligacion = pago.obligacion
            if not obligacion:
                return None, "Obligación no encontrada"

            # Anular pago
            pago.anular(usuario, motivo)

            # Revertir en obligación
            obligacion.monto_pagado -= pago.monto_pagado
            obligacion.cuotas_pagadas -= 1
            obligacion.version += 1
            obligacion.actualizar_estado()

            db.session.commit()

            AuditLog.registrar(
                tabla='pagos_generales',
                registro_id=pago.id,
                accion='anular',
                usuario=usuario,
                detalles=f"Pago anulado: {pago.numero_recibo} - Motivo: {motivo}"
            )

            return pago, None

        except Exception as e:
            db.session.rollback()
            return None, f"Error al anular pago: {str(e)}"

    @staticmethod
    def calcular_estado_cuenta(estudiante_id, anio_escolar):
        """Calcula el estado de cuenta completo de un estudiante (pensiones + otros pagos)"""
        try:
            estudiante = Estudiante.query.get(estudiante_id)
            if not estudiante:
                return None, "Estudiante no encontrado"

            # Obtener obligaciones
            obligaciones = ObligacionPagoEstudiante.query.filter_by(
                estudiante_id=estudiante_id,
                anio_escolar=anio_escolar
            ).all()

            # Calcular totales
            total_obligaciones = sum(o.monto_total for o in obligaciones)
            total_pagado = sum(o.monto_pagado for o in obligaciones)
            total_pendiente = sum(o.monto_pendiente for o in obligaciones)

            # Agrupar por concepto
            por_concepto = {}
            for obligacion in obligaciones:
                concepto = obligacion.concepto_nombre
                if concepto not in por_concepto:
                    por_concepto[concepto] = {
                        'obligacion_id': obligacion.id,
                        'monto_total': 0,
                        'monto_pagado': 0,
                        'monto_pendiente': 0,
                        'estado': obligacion.estado,
                        'cuotas_pagadas': obligacion.cuotas_pagadas,
                        'total_cuotas': obligacion.numero_cuotas,
                        'pagos': []
                    }

                por_concepto[concepto]['monto_total'] += float(obligacion.monto_total)
                por_concepto[concepto]['monto_pagado'] += float(obligacion.monto_pagado)
                por_concepto[concepto]['monto_pendiente'] += float(obligacion.monto_pendiente)

                # Agregar pagos
                for pago in obligacion.pagos.filter_by(estado='pagado').all():
                    por_concepto[concepto]['pagos'].append({
                        'id': pago.id,
                        'numero_recibo': pago.numero_recibo,
                        'fecha': pago.fecha_pago,
                        'monto': float(pago.monto_pagado),
                        'forma_pago': pago.forma_pago
                    })

            return {
                'estudiante': {
                    'id': estudiante.id,
                    'nombre_completo': estudiante.nombre_completo(),
                    'dni': estudiante.dni_est,
                    'nivel': estudiante.nivel,
                    'grado': estudiante.grado,
                    'seccion': estudiante.seccion
                },
                'anio_escolar': anio_escolar,
                'total_obligaciones': float(total_obligaciones),
                'total_pagado': float(total_pagado),
                'total_pendiente': float(total_pendiente),
                'por_concepto': por_concepto
            }, None

        except Exception as e:
            return None, f"Error al calcular estado de cuenta: {str(e)}"

    @staticmethod
    def listar_conceptos(anio_escolar=None, activo=True):
        """Lista conceptos de pago con filtros"""
        query = ConceptoPagoCiclo.query

        if anio_escolar:
            query = query.filter_by(anio_escolar=anio_escolar)
        if activo is not None:
            query = query.filter_by(activo=activo)

        return query.order_by(ConceptoPagoCiclo.tipo_pago_nombre).all()

    @staticmethod
    def listar_obligaciones(estudiante_id=None, anio_escolar=None, estado=None):
        """Lista obligaciones con filtros"""
        query = ObligacionPagoEstudiante.query

        if estudiante_id:
            query = query.filter_by(estudiante_id=estudiante_id)
        if anio_escolar:
            query = query.filter_by(anio_escolar=anio_escolar)
        if estado:
            query = query.filter_by(estado=estado)

        return query.order_by(ObligacionPagoEstudiante.fecha_registro.desc()).all()
