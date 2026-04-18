# services/aula_service.py
from models import db, Aula, Matricula, Estudiante, AuditLog
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from datetime import datetime


class AulaService:
    """Servicio para gestionar aulas y matrículas con validaciones multi-turno"""

    @staticmethod
    def crear_aula(nivel, grado, seccion, turno, anio_escolar, capacidad_maxima=30, usuario_creacion=None):
        """
        Crea un aula nueva con validaciones de unicidad

        Args:
            nivel: Nivel educativo (Primaria, Secundaria)
            grado: Grado (1ro, 2do, 3ro, etc.)
            seccion: Sección (A, B, C, etc.)
            turno: Turno (Mañana, Tarde)
            anio_escolar: Año escolar (2025, 2026, etc.)
            capacidad_maxima: Capacidad máxima de estudiantes
            usuario_creacion: Usuario que crea el aula

        Returns:
            tuple: (aula, error_message)
        """
        try:
            nivel_s = (nivel or "").strip()
            grado_s = (grado or "").strip()
            seccion_s = (seccion or "").strip()
            turno_s = (turno or "").strip()
            anio_s = str(anio_escolar).strip()

            # Misma combinación lógica (aunque el programa difiera solo en mayúsculas/espacios)
            duplicado_logico = (
                Aula.query.filter(
                    func.upper(Aula.nivel) == nivel_s.upper(),
                    func.upper(Aula.grado) == grado_s.upper(),
                    func.upper(Aula.seccion) == seccion_s.upper(),
                    Aula.turno == turno_s,
                    Aula.anio_escolar == anio_s,
                ).first()
            )
            if duplicado_logico:
                return (
                    None,
                    f"Ya existe un aula con el mismo nivel, programa/grado, sección, turno y año "
                    f"{anio_s}: «{duplicado_logico.nombre}» (código {duplicado_logico.codigo}).",
                )

            # Generar código y nombre
            codigo = Aula.generar_codigo(nivel_s, grado_s, seccion_s, turno_s, anio_s)
            nombre = Aula.generar_nombre(nivel_s, grado_s, seccion_s, turno_s)

            # Colisión residual (p. ej. datos legacy): añadir sufijo numérico al código
            codigo_base = codigo
            suf = 0
            while Aula.query.filter_by(codigo=codigo, anio_escolar=anio_s).first():
                suf += 1
                if suf > 50:
                    return None, "No se pudo generar un código de aula único. Intente de nuevo o contacte al administrador."
                extra = f"-{suf}"
                if len(codigo_base) + len(extra) <= 30:
                    codigo = codigo_base + extra
                else:
                    codigo = (codigo_base[: 30 - len(extra)] + extra)[:30]

            # Crear aula
            aula = Aula(
                codigo=codigo,
                nombre=nombre,
                nivel=nivel_s,
                grado=grado_s,
                seccion=seccion_s,
                turno=turno_s,
                anio_escolar=anio_s,
                capacidad_maxima=capacidad_maxima,
                usuario_creacion=usuario_creacion,
                activo=True
            )

            db.session.add(aula)
            db.session.commit()

            # Registrar en auditoría
            AuditLog.registrar(
                tabla='aulas',
                registro_id=aula.id,
                accion='crear',
                usuario=usuario_creacion,
                detalles=f"Aula creada: {aula.nombre} ({aula.codigo})"
            )

            return aula, None

        except IntegrityError:
            db.session.rollback()
            return (
                None,
                "No se pudo crear el aula: ya existe un registro con la misma combinación "
                "o el mismo código. Revise que no duplique nivel, programa/grado, sección, turno y año.",
            )
        except Exception as e:
            db.session.rollback()
            return None, f"Error al crear aula: {str(e)}"

    @staticmethod
    def obtener_aula(aula_id):
        """Obtiene un aula por ID"""
        return Aula.query.get(aula_id)

    @staticmethod
    def listar_aulas(anio_escolar=None, activo=None, nivel=None, turno=None):
        """
        Lista aulas con filtros opcionales

        Args:
            anio_escolar: Filtrar por año escolar
            activo: Filtrar por estado activo
            nivel: Filtrar por nivel (Primaria, Secundaria)
            turno: Filtrar por turno (Mañana, Tarde)

        Returns:
            Query de aulas
        """
        query = Aula.query

        if anio_escolar:
            query = query.filter_by(anio_escolar=anio_escolar)
        if activo is not None:
            query = query.filter_by(activo=activo)
        if nivel:
            query = query.filter_by(nivel=nivel)
        if turno:
            query = query.filter_by(turno=turno)

        return query.order_by(Aula.nivel, Aula.grado, Aula.seccion, Aula.turno)

    @staticmethod
    def actualizar_aula(aula_id, capacidad_maxima=None, activo=None, turno=None, nombre=None, usuario_modificacion=None):
        """Actualiza datos de un aula.

        - Si ``turno`` cambia: regenera código y nombre autogenerados.
        - Si ``nombre`` se envía (no vacío): sobreescribe el nombre (aplica
          después del turno, para respetar el valor ingresado por el usuario).
          Además actualiza los ``aula_nombre`` desnormalizados en matrículas.
        """
        try:
            aula = Aula.query.get(aula_id)
            if not aula:
                return None, "Aula no encontrada"

            cambios = []

            if capacidad_maxima is not None:
                aula.capacidad_maxima = capacidad_maxima
                cambios.append(f"Capacidad: {capacidad_maxima}")

            if activo is not None:
                aula.activo = activo
                cambios.append(f"Estado: {'Activo' if activo else 'Inactivo'}")

            if turno is not None and turno != aula.turno:
                nuevo_codigo = Aula.generar_codigo(aula.nivel, aula.grado, aula.seccion, turno, aula.anio_escolar)
                if Aula.query.filter(Aula.codigo == nuevo_codigo, Aula.id != aula_id).first():
                    return None, f"Ya existe un aula con el código {nuevo_codigo}"
                aula.turno = turno
                aula.codigo = nuevo_codigo
                aula.nombre = Aula.generar_nombre(aula.nivel, aula.grado, aula.seccion, turno)
                aula.matriculas.update({'aula_nombre': aula.nombre})
                cambios.append(f"Turno: {turno}")

            if nombre is not None:
                nuevo_nombre = nombre.strip()
                if not nuevo_nombre:
                    return None, "El nombre del aula no puede estar vacío"
                if len(nuevo_nombre) > 100:
                    return None, "El nombre del aula no puede superar 100 caracteres"
                if nuevo_nombre != aula.nombre:
                    aula.nombre = nuevo_nombre
                    aula.matriculas.update({'aula_nombre': nuevo_nombre})
                    cambios.append(f"Nombre: {nuevo_nombre}")

            if cambios:
                db.session.commit()
                AuditLog.registrar(
                    tabla='aulas',
                    registro_id=aula.id,
                    accion='actualizar',
                    usuario=usuario_modificacion,
                    detalles=f"Aula {aula.codigo} actualizada: {', '.join(cambios)}"
                )

            return aula, None

        except Exception as e:
            db.session.rollback()
            return None, f"Error al actualizar aula: {str(e)}"

    @staticmethod
    def eliminar_aula(aula_id, usuario=None):
        """Elimina (o archiva) un aula.

        - Si tiene matrículas activas: rechaza.
        - Si no tiene ninguna matrícula ni registros relacionados: borrado físico.
        - Si tiene matrículas retiradas u otros registros (asistencias, tests, etc.):
          borrado lógico (activo=False) para preservar la historia.

        Returns:
            tuple: (ok, error_msg, accion)
                accion es "eliminada" (borrado físico) o "archivada" (soft delete)
                cuando ok=True; None cuando ok=False.
        """
        from sqlalchemy import text

        try:
            aula = Aula.query.get(aula_id)
            if not aula:
                return False, "Aula no encontrada", None

            activas = aula.matriculas.filter_by(estado='activo').count()
            if activas > 0:
                return (
                    False,
                    f"No se puede eliminar: el aula tiene {activas} estudiante(s) matriculado(s)",
                    None,
                )

            codigo = aula.codigo
            total_matriculas = aula.matriculas.count()

            tablas_historial = [
                "asistencias",
                "registros_asistencia_aula",
                "detalles_asistencia_aula",
                "docentes_cursos_aulas",
                "fast_tests",
                "notas_fast_test",
            ]
            tiene_otros_registros = False
            for tabla in tablas_historial:
                try:
                    cnt = db.session.execute(
                        text(f"SELECT COUNT(*) FROM {tabla} WHERE aula_id = :aid"),
                        {"aid": aula_id},
                    ).scalar() or 0
                    if cnt > 0:
                        tiene_otros_registros = True
                        break
                except Exception:
                    db.session.rollback()

            tiene_historia = total_matriculas > 0 or tiene_otros_registros

            if not tiene_historia:
                db.session.delete(aula)
                db.session.commit()
                AuditLog.registrar(
                    tabla='aulas',
                    registro_id=aula_id,
                    accion='eliminar',
                    usuario=usuario,
                    detalles=f"Aula {codigo} eliminada (sin historia)",
                )
                return True, None, "eliminada"

            if not aula.activo:
                return False, "El aula ya está archivada", None

            aula.activo = False
            db.session.commit()
            AuditLog.registrar(
                tabla='aulas',
                registro_id=aula_id,
                accion='archivar',
                usuario=usuario,
                detalles=(
                    f"Aula {codigo} archivada (matrículas históricas: {total_matriculas}, "
                    f"otros registros: {tiene_otros_registros})"
                ),
            )
            return True, None, "archivada"

        except Exception as e:
            db.session.rollback()
            return False, f"Error al eliminar aula: {str(e)}", None

    @staticmethod
    def matricular_estudiante(estudiante_id, aula_id, anio_escolar, observaciones=None, usuario_registro=None):
        """
        Matricula un estudiante en un aula
        Permite multi-turno (un estudiante puede estar en varias aulas)

        Args:
            estudiante_id: ID del estudiante
            aula_id: ID del aula
            anio_escolar: Año escolar
            observaciones: Observaciones de la matrícula
            usuario_registro: Usuario que registra

        Returns:
            tuple: (matricula, error_message)
        """
        try:
            # Validar que existe el estudiante
            estudiante = Estudiante.query.get(estudiante_id)
            if not estudiante:
                return None, "Estudiante no encontrado"

            # Generar código de estudiante si no tiene (para QR)
            if not estudiante.codigo_estudiante:
                estudiante.codigo_estudiante = Estudiante.generar_codigo_estudiante()

            # Validar que existe el aula
            aula = Aula.query.get(aula_id)
            if not aula:
                return None, "Aula no encontrada"

            # Validar que el aula está activa
            if not aula.activo:
                return None, "El aula no está activa"

            # Validar que el año escolar coincide
            if aula.anio_escolar != anio_escolar:
                return None, f"El aula pertenece al año {aula.anio_escolar}, no {anio_escolar}"

            # Verificar si ya está matriculado en esta aula
            matricula_existente = Matricula.query.filter_by(
                estudiante_id=estudiante_id,
                aula_id=aula_id,
                anio_escolar=anio_escolar,
                estado='activo'
            ).first()

            if matricula_existente:
                return None, f"El estudiante ya está matriculado en {aula.nombre}"

            # Verificar capacidad del aula
            if not aula.tiene_capacidad():
                return None, f"El aula {aula.nombre} ha alcanzado su capacidad máxima"

            # Crear nombre completo del estudiante
            nombre_completo = f"{estudiante.apellido_paterno_est} {estudiante.apellido_materno_est}, {estudiante.nombres_est}"

            # Crear matrícula
            matricula = Matricula(
                estudiante_id=estudiante_id,
                aula_id=aula_id,
                estudiante_nombre_completo=nombre_completo,
                estudiante_dni=estudiante.dni_est,
                aula_nombre=aula.nombre,
                aula_codigo=aula.codigo,
                anio_escolar=anio_escolar,
                estado='activo',
                observaciones=observaciones,
                usuario_registro=usuario_registro
            )

            db.session.add(matricula)
            db.session.commit()

            # Registrar en auditoría
            AuditLog.registrar(
                tabla='matriculas',
                registro_id=matricula.id,
                accion='crear',
                usuario=usuario_registro,
                detalles=f"Estudiante {nombre_completo} matriculado en {aula.nombre}"
            )

            return matricula, None

        except IntegrityError as e:
            db.session.rollback()
            return None, "Ya existe una matrícula activa para este estudiante en esta aula"
        except Exception as e:
            db.session.rollback()
            return None, f"Error al matricular estudiante: {str(e)}"

    @staticmethod
    def retirar_estudiante(matricula_id, motivo, usuario_modificacion=None):
        """
        Retira a un estudiante de un aula

        Args:
            matricula_id: ID de la matrícula
            motivo: Motivo del retiro
            usuario_modificacion: Usuario que registra el retiro

        Returns:
            tuple: (matricula, error_message)
        """
        try:
            matricula = Matricula.query.get(matricula_id)
            if not matricula:
                return None, "Matrícula no encontrada"

            if matricula.estado != 'activo':
                return None, "La matrícula ya no está activa"

            matricula.retirar(motivo, usuario_modificacion)
            db.session.commit()

            # Registrar en auditoría
            AuditLog.registrar(
                tabla='matriculas',
                registro_id=matricula.id,
                accion='retirar',
                usuario=usuario_modificacion,
                detalles=f"Estudiante {matricula.estudiante_nombre_completo} retirado de {matricula.aula_nombre}. Motivo: {motivo}"
            )

            return matricula, None

        except Exception as e:
            db.session.rollback()
            return None, f"Error al retirar estudiante: {str(e)}"

    @staticmethod
    def obtener_matriculas_estudiante(estudiante_id, anio_escolar=None, estado='activo'):
        """
        Obtiene todas las matrículas de un estudiante
        Permite verificar si está en múltiples turnos

        Args:
            estudiante_id: ID del estudiante
            anio_escolar: Filtrar por año escolar
            estado: Filtrar por estado

        Returns:
            Lista de matrículas
        """
        query = Matricula.query.filter_by(estudiante_id=estudiante_id)

        if anio_escolar:
            query = query.filter_by(anio_escolar=anio_escolar)
        if estado:
            query = query.filter_by(estado=estado)

        return query.all()

    @staticmethod
    def obtener_estudiantes_aula(aula_id, estado='activo'):
        """
        Obtiene todos los estudiantes matriculados en un aula

        Args:
            aula_id: ID del aula
            estado: Filtrar por estado de matrícula

        Returns:
            Lista de matrículas
        """
        query = Matricula.query.filter_by(aula_id=aula_id)

        if estado:
            query = query.filter_by(estado=estado)

        return query.order_by(Matricula.estudiante_nombre_completo).all()

    # Mapeo de promoción de grado por nivel
    PROMOCION_GRADO = {
        'PRIMARIA': {'1ro': '2do', '2do': '3ro', '3ro': '4to', '4to': '5to', '5to': '6to', '6to': None},
        'SECUNDARIA': {'1ro': '2do', '2do': '3ro', '3ro': '4to', '4to': '5to', '5to': None},
        'INICIAL': {},
    }

    @staticmethod
    def obtener_grado_sugerido(nivel, grado_actual):
        """Retorna el grado sugerido para promoción o None si egresa"""
        return AulaService.PROMOCION_GRADO.get(nivel, {}).get(grado_actual, '')

    @staticmethod
    def promocion_anual(anio_origen, anio_destino, aulas_config, usuario=None):
        """
        Promueve estudiantes de un año escolar al siguiente.

        Args:
            anio_origen: Año escolar de origen
            anio_destino: Año escolar de destino
            aulas_config: lista de dicts {aula_id, grado_destino}
            usuario: Usuario que ejecuta la acción

        Returns:
            dict con estadísticas
        """
        stats = {
            'aulas_creadas': 0,
            'matriculas_creadas': 0,
            'aulas_cerradas': 0,
            'egresados': 0,
            'errores': []
        }

        try:
            for config in aulas_config:
                aula_origen = Aula.query.get(config['aula_id'])
                if not aula_origen:
                    stats['errores'].append(f"Aula ID {config['aula_id']} no encontrada")
                    continue

                grado_destino = config.get('grado_destino', '').strip()
                matriculas_activas = Matricula.query.filter_by(
                    aula_id=aula_origen.id, estado='activo'
                ).all()

                if not grado_destino:
                    # Egresa: solo cerrar matrículas y aula
                    for m in matriculas_activas:
                        m.estado = 'promovido'
                        m.fecha_retiro = datetime.utcnow()
                        m.motivo_retiro = 'Promoción anual - Egresado'
                        m.usuario_modificacion = usuario
                    aula_origen.activo = False
                    stats['aulas_cerradas'] += 1
                    stats['egresados'] += len(matriculas_activas)
                    continue

                # Crear aula destino
                aula_destino, error = AulaService.crear_aula(
                    nivel=aula_origen.nivel,
                    grado=grado_destino,
                    seccion=aula_origen.seccion,
                    turno=aula_origen.turno,
                    anio_escolar=anio_destino,
                    capacidad_maxima=aula_origen.capacidad_maxima,
                    usuario_creacion=usuario
                )

                if error:
                    # Buscar si ya existe
                    codigo = Aula.generar_codigo(aula_origen.nivel, grado_destino, aula_origen.seccion, aula_origen.turno, anio_destino)
                    aula_destino = Aula.query.filter_by(codigo=codigo, anio_escolar=anio_destino).first()
                    if not aula_destino:
                        stats['errores'].append(f"{aula_origen.nombre}: {error}")
                        continue
                else:
                    stats['aulas_creadas'] += 1

                # Mover estudiantes activos
                for m in matriculas_activas:
                    nueva_mat, err = AulaService.matricular_estudiante(
                        estudiante_id=m.estudiante_id,
                        aula_id=aula_destino.id,
                        anio_escolar=anio_destino,
                        observaciones=f'Promoción de {aula_origen.nombre}',
                        usuario_registro=usuario
                    )
                    if err:
                        stats['errores'].append(f"{m.estudiante_nombre_completo}: {err}")
                    else:
                        stats['matriculas_creadas'] += 1

                    # Cerrar matrícula origen
                    m.estado = 'promovido'
                    m.fecha_retiro = datetime.utcnow()
                    m.motivo_retiro = f'Promoción a {grado_destino}'
                    m.usuario_modificacion = usuario

                aula_origen.activo = False
                stats['aulas_cerradas'] += 1

            db.session.commit()
            return stats

        except Exception as e:
            db.session.rollback()
            stats['errores'].append(f"Error crítico: {str(e)}")
            return stats

    @staticmethod
    def renovar_ciclo(aula_id, nuevo_grado, estudiantes_ids, anio_escolar_destino=None, usuario=None):
        """
        Cierra un aula (típicamente Academia) y crea una nueva con estudiantes seleccionados.

        Args:
            aula_id: ID del aula a cerrar
            nuevo_grado: Nombre del nuevo grado
            estudiantes_ids: Lista de IDs de estudiantes a mover
            anio_escolar_destino: Año escolar del nuevo aula (por defecto mismo que origen)
            usuario: Usuario que ejecuta la acción

        Returns:
            dict con estadísticas
        """
        stats = {
            'aula_creada': False,
            'aula_nombre': '',
            'matriculas_creadas': 0,
            'errores': []
        }

        try:
            aula_origen = Aula.query.get(aula_id)
            if not aula_origen:
                stats['errores'].append('Aula no encontrada')
                return stats

            anio = anio_escolar_destino or aula_origen.anio_escolar

            # Crear nueva aula
            aula_nueva, error = AulaService.crear_aula(
                nivel=aula_origen.nivel,
                grado=nuevo_grado,
                seccion=aula_origen.seccion,
                turno=aula_origen.turno,
                anio_escolar=anio,
                capacidad_maxima=aula_origen.capacidad_maxima,
                usuario_creacion=usuario
            )

            if error:
                stats['errores'].append(f"Error creando aula: {error}")
                return stats

            stats['aula_creada'] = True
            stats['aula_nombre'] = aula_nueva.nombre

            # Matricular estudiantes seleccionados
            for est_id in estudiantes_ids:
                matricula, err = AulaService.matricular_estudiante(
                    estudiante_id=int(est_id),
                    aula_id=aula_nueva.id,
                    anio_escolar=anio,
                    observaciones=f'Renovación de ciclo desde {aula_origen.nombre}',
                    usuario_registro=usuario
                )
                if err:
                    stats['errores'].append(f"Estudiante {est_id}: {err}")
                else:
                    stats['matriculas_creadas'] += 1

            # Cerrar matrículas activas del aula origen
            matriculas_origen = Matricula.query.filter_by(
                aula_id=aula_origen.id, estado='activo'
            ).all()
            for m in matriculas_origen:
                m.estado = 'promovido'
                m.fecha_retiro = datetime.utcnow()
                m.motivo_retiro = f'Ciclo cerrado - Renovación a {nuevo_grado}'
                m.usuario_modificacion = usuario

            # Cerrar aula origen
            aula_origen.activo = False

            db.session.commit()
            return stats

        except Exception as e:
            db.session.rollback()
            stats['errores'].append(f"Error crítico: {str(e)}")
            return stats

    @staticmethod
    def migrar_datos_existentes(anio_escolar='2025'):
        """
        Migra datos existentes de estudiantes a sistema de aulas
        Crea aulas basadas en nivel+grado+seccion+turno y matricula estudiantes.
        Asigna valores por defecto si seccion o turno están vacíos.

        Args:
            anio_escolar: Año escolar a migrar

        Returns:
            dict con estadísticas de migración
        """
        try:
            stats = {
                'aulas_creadas': 0,
                'matriculas_creadas': 0,
                'errores': []
            }

            # Obtener estudiantes que tengan al menos nivel y grado
            estudiantes = Estudiante.query.filter(
                Estudiante.nivel.isnot(None),
                Estudiante.nivel != '',
                Estudiante.grado.isnot(None),
                Estudiante.grado != ''
            ).all()

            # Agrupar por aula (normalizar seccion y turno vacíos)
            aulas_dict = {}
            for est in estudiantes:
                seccion = (est.seccion or '').strip() or 'A'
                turno = (est.turno or '').strip() or 'Mañana'
                # Normalizar turno (primera letra mayúscula)
                turno = turno.capitalize()
                if turno not in ('Mañana', 'Tarde'):
                    turno = 'Mañana'

                clave = (est.nivel.strip(), est.grado.strip(), seccion.upper(), turno)
                if clave not in aulas_dict:
                    aulas_dict[clave] = []
                aulas_dict[clave].append(est)

            # Crear aulas y matricular estudiantes
            for (nivel, grado, seccion, turno), estudiantes_list in aulas_dict.items():
                # Crear aula
                aula, error = AulaService.crear_aula(
                    nivel=nivel,
                    grado=grado,
                    seccion=seccion,
                    turno=turno,
                    anio_escolar=anio_escolar,
                    capacidad_maxima=max(30, len(estudiantes_list) + 5),
                    usuario_creacion='SISTEMA_MIGRACION'
                )

                if error:
                    # Si ya existe, buscarla para matricular igualmente
                    codigo = Aula.generar_codigo(nivel, grado, seccion, turno, anio_escolar)
                    aula = Aula.query.filter_by(codigo=codigo, anio_escolar=anio_escolar).first()
                    if not aula:
                        stats['errores'].append(f"Error al crear aula {nivel} {grado} {seccion} {turno}: {error}")
                        continue
                else:
                    stats['aulas_creadas'] += 1

                # Matricular estudiantes
                for est in estudiantes_list:
                    matricula, error = AulaService.matricular_estudiante(
                        estudiante_id=est.id,
                        aula_id=aula.id,
                        anio_escolar=anio_escolar,
                        observaciones='Migración automática',
                        usuario_registro='SISTEMA_MIGRACION'
                    )

                    if error:
                        stats['errores'].append(f"Error al matricular {est.id}: {error}")
                    else:
                        stats['matriculas_creadas'] += 1

            return stats

        except Exception as e:
            db.session.rollback()
            return {
                'aulas_creadas': 0,
                'matriculas_creadas': 0,
                'errores': [f"Error crítico en migración: {str(e)}"]
            }
