# services/asistencia_service.py
from models import db, Asistencia, Estudiante, RegistroAsistenciaAula, DetalleAsistenciaAula, JustificacionInasistencia, Aula, Matricula, AuditLog
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, and_
from datetime import datetime, date, time


class AsistenciaService:
    """Servicio para gestionar asistencia por aula con justificaciones"""

    @staticmethod
    def crear_registro_aula(aula_id, fecha, usuario_registro=None):
        """
        Crea un registro de asistencia para un aula en una fecha específica
        Auto-crea detalles para todos los estudiantes matriculados

        Args:
            aula_id: ID del aula
            fecha: Fecha del registro (date object)
            usuario_registro: Usuario que crea el registro

        Returns:
            tuple: (registro, error_message)
        """
        try:
            # Validar que existe el aula
            aula = Aula.query.get(aula_id)
            if not aula:
                return None, "Aula no encontrada"

            # Verificar si ya existe registro para esta aula+fecha
            registro_existente = RegistroAsistenciaAula.query.filter_by(
                aula_id=aula_id,
                fecha=fecha
            ).first()

            if registro_existente:
                return registro_existente, None  # Retornar el existente

            # Crear registro de asistencia
            registro = RegistroAsistenciaAula(
                aula_id=aula_id,
                fecha=fecha,
                aula_nombre=aula.nombre,
                aula_codigo=aula.codigo,
                anio_escolar=aula.anio_escolar,
                estado='abierto',
                usuario_registro=usuario_registro
            )

            db.session.add(registro)
            db.session.flush()  # Para obtener el ID del registro

            # Obtener estudiantes matriculados activos
            matriculas = Matricula.query.filter_by(
                aula_id=aula_id,
                anio_escolar=aula.anio_escolar,
                estado='activo'
            ).all()

            # Crear detalle por cada estudiante (todos ausentes por defecto)
            for matricula in matriculas:
                detalle = DetalleAsistenciaAula(
                    registro_aula_id=registro.id,
                    estudiante_id=matricula.estudiante_id,
                    estudiante_nombre_completo=matricula.estudiante_nombre_completo,
                    estudiante_dni=matricula.estudiante_dni,
                    estado='ausente',
                    usuario_registro=usuario_registro
                )
                db.session.add(detalle)

            db.session.commit()

            # Registrar en auditoría
            AuditLog.registrar(
                tabla='registros_asistencia_aula',
                registro_id=registro.id,
                accion='crear',
                usuario=usuario_registro,
                detalles=f"Registro de asistencia creado para {aula.nombre} en {fecha}"
            )

            return registro, None

        except IntegrityError:
            db.session.rollback()
            # Intentar recuperar el registro existente
            registro_existente = RegistroAsistenciaAula.query.filter_by(
                aula_id=aula_id,
                fecha=fecha
            ).first()
            return registro_existente, None
        except Exception as e:
            db.session.rollback()
            return None, f"Error al crear registro de asistencia: {str(e)}"

    @staticmethod
    def registrar_asistencia_masiva(registro_id, asistencias_dict, usuario=None):
        """
        Registra asistencia de múltiples estudiantes en una transacción

        Args:
            registro_id: ID del registro de asistencia
            asistencias_dict: Dict con {estudiante_id: {'estado': 'presente/ausente/tardanza', 'hora': time, 'observaciones': str}}
            usuario: Usuario que registra

        Returns:
            tuple: (success, error_message)
        """
        try:
            registro = RegistroAsistenciaAula.query.get(registro_id)
            if not registro:
                return False, "Registro de asistencia no encontrado"

            if registro.estado == 'cerrado':
                return False, "No se puede modificar un registro cerrado"

            # Actualizar cada detalle
            for estudiante_id, datos in asistencias_dict.items():
                detalle = DetalleAsistenciaAula.query.filter_by(
                    registro_aula_id=registro_id,
                    estudiante_id=estudiante_id
                ).first()

                if not detalle:
                    continue

                estado = datos.get('estado', 'ausente')
                hora = datos.get('hora')
                observaciones = datos.get('observaciones')

                if estado == 'presente':
                    detalle.marcar_presente(hora=hora, observaciones=observaciones, usuario=usuario)
                elif estado == 'ausente':
                    detalle.marcar_ausente(observaciones=observaciones, usuario=usuario)
                elif estado == 'tardanza':
                    detalle.marcar_tardanza(hora=hora, observaciones=observaciones, usuario=usuario)

            # Actualizar estadísticas
            registro.calcular_estadisticas()
            registro.usuario_modificacion = usuario

            db.session.commit()

            # Registrar en auditoría
            AuditLog.registrar(
                tabla='registros_asistencia_aula',
                registro_id=registro.id,
                accion='actualizar',
                usuario=usuario,
                detalles=f"Asistencia registrada para {len(asistencias_dict)} estudiantes"
            )

            return True, None

        except Exception as e:
            db.session.rollback()
            return False, f"Error al registrar asistencia: {str(e)}"

    @staticmethod
    def crear_justificacion(estudiante_id, fecha, apoderado_nombre, apoderado_dni, motivo,
                           tipo_motivo='otros', apoderado_telefono=None, apoderado_relacion=None,
                           tiene_documento=False, tipo_documento=None, usuario_registro=None):
        """
        Crea una justificación de inasistencia (sistema escáner QR)
        """
        try:
            # Validar que existe el estudiante
            estudiante = Estudiante.query.get(estudiante_id)
            if not estudiante:
                return None, "Estudiante no encontrado"

            # Verificar que el estudiante no tiene ENTRADA ese día
            tiene_entrada = Asistencia.query.filter(
                and_(
                    Asistencia.estudiante_id == estudiante_id,
                    Asistencia.tipo == 'ENTRADA',
                    func.date(Asistencia.fecha_hora) == fecha
                )
            ).first()

            if tiene_entrada:
                return None, "El estudiante sí asistió ese día (tiene registro de entrada)"

            # Verificar si ya tiene justificación para esa fecha
            existente = JustificacionInasistencia.query.filter_by(
                estudiante_id=estudiante_id,
                fecha=fecha
            ).first()

            if existente:
                return None, "Ya existe una justificación para este estudiante en esa fecha"

            # Crear justificación
            nombre_completo = f"{estudiante.apellido_paterno_est} {estudiante.apellido_materno_est}, {estudiante.nombres_est}"
            justificacion = JustificacionInasistencia(
                estudiante_id=estudiante_id,
                fecha=fecha,
                estudiante_nombre_completo=nombre_completo,
                estudiante_dni=estudiante.dni_est,
                apoderado_nombre=apoderado_nombre,
                apoderado_dni=apoderado_dni,
                apoderado_telefono=apoderado_telefono,
                apoderado_relacion=apoderado_relacion,
                motivo=motivo,
                tipo_motivo=tipo_motivo,
                tiene_documento=tiene_documento,
                tipo_documento=tipo_documento,
                estado='pendiente',
                usuario_registro=usuario_registro
            )

            db.session.add(justificacion)
            db.session.commit()

            AuditLog.registrar(
                tabla='justificaciones_inasistencia',
                registro_id=justificacion.id,
                accion='crear',
                usuario=usuario_registro,
                detalles=f"Justificación creada para {nombre_completo} - fecha: {fecha}"
            )

            return justificacion, None

        except IntegrityError:
            db.session.rollback()
            return None, "Ya existe una justificación para este estudiante en esa fecha"
        except Exception as e:
            db.session.rollback()
            return None, f"Error al crear justificación: {str(e)}"

    @staticmethod
    def aprobar_justificacion(justificacion_id, usuario, observaciones=None):
        """
        Aprueba una justificación de inasistencia
        """
        try:
            justificacion = JustificacionInasistencia.query.get(justificacion_id)
            if not justificacion:
                return None, "Justificación no encontrada"

            if justificacion.estado != 'pendiente':
                return None, "Solo se pueden aprobar justificaciones pendientes"

            justificacion.aprobar(usuario, observaciones)
            db.session.commit()

            AuditLog.registrar(
                tabla='justificaciones_inasistencia',
                registro_id=justificacion.id,
                accion='aprobar',
                usuario=usuario,
                detalles=f"Justificación aprobada para {justificacion.estudiante_nombre_completo}"
            )

            return justificacion, None

        except Exception as e:
            db.session.rollback()
            return None, f"Error al aprobar justificación: {str(e)}"

    @staticmethod
    def rechazar_justificacion(justificacion_id, usuario, observaciones):
        """Rechaza una justificación"""
        try:
            if not observaciones:
                return None, "Debe proporcionar un motivo para rechazar la justificación"

            justificacion = JustificacionInasistencia.query.get(justificacion_id)
            if not justificacion:
                return None, "Justificación no encontrada"

            if justificacion.estado != 'pendiente':
                return None, "Solo se pueden rechazar justificaciones pendientes"

            justificacion.rechazar(usuario, observaciones)
            db.session.commit()

            AuditLog.registrar(
                tabla='justificaciones_inasistencia',
                registro_id=justificacion.id,
                accion='rechazar',
                usuario=usuario,
                detalles=f"Justificación rechazada para {justificacion.estudiante_nombre_completo}: {observaciones}"
            )

            return justificacion, None

        except Exception as e:
            db.session.rollback()
            return None, f"Error al rechazar justificación: {str(e)}"

    @staticmethod
    def obtener_registro_aula(aula_id, fecha):
        """
        Obtiene el registro de asistencia de un aula en una fecha específica

        Args:
            aula_id: ID del aula
            fecha: Fecha del registro

        Returns:
            RegistroAsistenciaAula o None
        """
        return RegistroAsistenciaAula.query.filter_by(
            aula_id=aula_id,
            fecha=fecha
        ).first()

    @staticmethod
    def listar_registros_aula(aula_id=None, fecha_inicio=None, fecha_fin=None,
                              estado=None, nivel=None, aula_ids=None):
        """
        Lista registros de asistencia con filtros.

        aula_ids: lista de IDs (usado cuando nivel=Academia + grado específico)
        nivel: filtra por nivel del aula
        aula_id: filtra por un aula específica
        """
        from models.aula import Aula
        query = RegistroAsistenciaAula.query

        if aula_ids is not None:
            query = query.filter(RegistroAsistenciaAula.aula_id.in_(aula_ids))
        elif nivel:
            ids_nivel = [a.id for a in Aula.query.filter(
                Aula.nivel.ilike(nivel), Aula.activo == True
            ).all()]
            query = query.filter(RegistroAsistenciaAula.aula_id.in_(ids_nivel))
        elif aula_id:
            query = query.filter_by(aula_id=aula_id)

        if fecha_inicio:
            query = query.filter(RegistroAsistenciaAula.fecha >= fecha_inicio)
        if fecha_fin:
            query = query.filter(RegistroAsistenciaAula.fecha <= fecha_fin)
        if estado:
            query = query.filter_by(estado=estado)

        return query.order_by(RegistroAsistenciaAula.fecha.desc())

    @staticmethod
    def listar_justificaciones(estado=None, fecha_inicio=None, fecha_fin=None):
        """Lista justificaciones con filtros"""
        query = JustificacionInasistencia.query

        if estado:
            query = query.filter_by(estado=estado)
        if fecha_inicio:
            query = query.filter(JustificacionInasistencia.fecha >= fecha_inicio)
        if fecha_fin:
            query = query.filter(JustificacionInasistencia.fecha <= fecha_fin)

        return query.order_by(JustificacionInasistencia.fecha.desc())

    @staticmethod
    def obtener_fechas_ausencia(estudiante_id, dias=30):
        """
        Obtiene las fechas en que el estudiante no tiene registro de ENTRADA
        en los últimos N días (solo días de lunes a viernes)
        """
        from datetime import timedelta
        hoy = date.today()
        fechas_ausencia = []

        for i in range(dias):
            fecha_check = hoy - timedelta(days=i)
            # Solo días de lunes (0) a viernes (4)
            if fecha_check.weekday() >= 5:
                continue

            tiene_entrada = Asistencia.query.filter(
                and_(
                    Asistencia.estudiante_id == estudiante_id,
                    Asistencia.tipo == 'ENTRADA',
                    func.date(Asistencia.fecha_hora) == fecha_check
                )
            ).first()

            if not tiene_entrada:
                # Verificar si ya tiene justificación
                tiene_justificacion = JustificacionInasistencia.query.filter_by(
                    estudiante_id=estudiante_id,
                    fecha=fecha_check
                ).first()

                fechas_ausencia.append({
                    'fecha': fecha_check.isoformat(),
                    'fecha_formato': fecha_check.strftime('%d/%m/%Y'),
                    'dia_semana': ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes'][fecha_check.weekday()],
                    'justificada': tiene_justificacion is not None
                })

        return fechas_ausencia

    @staticmethod
    def obtener_reporte_asistencia_estudiante(estudiante_id, fecha_inicio, fecha_fin):
        """
        Genera reporte de asistencia de un estudiante en un rango de fechas

        Args:
            estudiante_id: ID del estudiante
            fecha_inicio: Fecha de inicio
            fecha_fin: Fecha de fin

        Returns:
            dict con estadísticas
        """
        detalles = DetalleAsistenciaAula.query.join(RegistroAsistenciaAula).filter(
            DetalleAsistenciaAula.estudiante_id == estudiante_id,
            RegistroAsistenciaAula.fecha >= fecha_inicio,
            RegistroAsistenciaAula.fecha <= fecha_fin
        ).all()

        total_dias = len(detalles)
        presentes = sum(1 for d in detalles if d.estado == 'presente')
        ausentes = sum(1 for d in detalles if d.estado == 'ausente')
        tardanzas = sum(1 for d in detalles if d.estado == 'tardanza')
        justificados = sum(1 for d in detalles if d.estado == 'justificado')

        porcentaje_asistencia = (presentes / total_dias * 100) if total_dias > 0 else 0

        return {
            'total_dias': total_dias,
            'presentes': presentes,
            'ausentes': ausentes,
            'tardanzas': tardanzas,
            'justificados': justificados,
            'porcentaje_asistencia': round(porcentaje_asistencia, 2)
        }

    @staticmethod
    def cerrar_registro(registro_id, usuario):
        """
        Cierra un registro de asistencia

        Args:
            registro_id: ID del registro
            usuario: Usuario que cierra

        Returns:
            tuple: (registro, error_message)
        """
        try:
            registro = RegistroAsistenciaAula.query.get(registro_id)
            if not registro:
                return None, "Registro no encontrado"

            if registro.estado == 'cerrado':
                return None, "El registro ya está cerrado"

            registro.cerrar_registro(usuario)
            db.session.commit()

            # Registrar en auditoría
            AuditLog.registrar(
                tabla='registros_asistencia_aula',
                registro_id=registro.id,
                accion='cerrar',
                usuario=usuario,
                detalles=f"Registro cerrado: {registro.total_presentes}/{registro.total_estudiantes} presentes"
            )

            return registro, None

        except Exception as e:
            db.session.rollback()
            return None, f"Error al cerrar registro: {str(e)}"
