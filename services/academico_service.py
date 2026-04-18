# services/academico_service.py
from models import db, PeriodoAcademico, Curso, DocenteCursoAula, FastTest, NotaFastTest, Estudiante, Matricula, AuditLog
from sqlalchemy.exc import IntegrityError
from datetime import datetime, date


class AcademicoService:
    """Servicio para gestionar el sistema académico con Fast Tests"""

    @staticmethod
    def crear_periodo(nombre, numero, anio_escolar, fecha_inicio, fecha_fin, usuario=None):
        """Crea un período académico"""
        try:
            periodo = PeriodoAcademico(
                nombre=nombre,
                numero=numero,
                anio_escolar=anio_escolar,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                activo=True,
                usuario_registro=usuario
            )

            db.session.add(periodo)
            db.session.commit()

            AuditLog.registrar(
                tabla='periodos_academicos',
                registro_id=periodo.id,
                accion='crear',
                usuario=usuario,
                detalles=f"Período académico creado: {periodo.nombre}"
            )

            return periodo, None

        except IntegrityError:
            db.session.rollback()
            return None, f"Ya existe el período {numero} para el año {anio_escolar}"
        except Exception as e:
            db.session.rollback()
            return None, f"Error al crear período: {str(e)}"

    @staticmethod
    def crear_curso(nombre, codigo, nivel=None, descripcion=None, usuario=None):
        """Crea un curso"""
        try:
            curso = Curso(
                nombre=nombre,
                codigo=codigo,
                nivel=nivel,
                descripcion=descripcion,
                activo=True,
                usuario_registro=usuario
            )

            db.session.add(curso)
            db.session.commit()

            AuditLog.registrar(
                tabla='cursos',
                registro_id=curso.id,
                accion='crear',
                usuario=usuario,
                detalles=f"Curso creado: {curso.nombre}"
            )

            return curso, None

        except IntegrityError:
            db.session.rollback()
            return None, f"Ya existe un curso con el código {codigo}"
        except Exception as e:
            db.session.rollback()
            return None, f"Error al crear curso: {str(e)}"

    @staticmethod
    def crear_fast_test(curso_id, aula_id, titulo, fecha_evaluacion,
                       anio_escolar, periodo_id=None, docente_id=None, descripcion=None, peso=1.0, usuario=None):
        """
        Crea un Fast Test vinculado a curso-aula.
        periodo_id es opcional.
        """
        try:
            from models import Curso, Aula, PeriodoAcademico, Docente

            # Validar curso
            curso = Curso.query.get(curso_id)
            if not curso:
                return None, "Curso no encontrado"

            # Validar aula
            aula = Aula.query.get(aula_id)
            if not aula:
                return None, "Aula no encontrada"

            # Validar que el año escolar del aula coincida
            if aula.anio_escolar != anio_escolar:
                return None, "El año escolar no coincide con el aula"

            # Validar fecha
            if not isinstance(fecha_evaluacion, date):
                fecha_evaluacion = datetime.strptime(fecha_evaluacion, '%Y-%m-%d').date()

            # Período (opcional)
            periodo_nombre = None
            if periodo_id:
                periodo = PeriodoAcademico.query.get(periodo_id)
                if periodo:
                    periodo_nombre = periodo.nombre

            # Obtener nombre del docente si existe
            docente_nombre = None
            if docente_id:
                docente = Docente.query.get(docente_id)
                if docente:
                    docente_nombre = f"{docente.apellido_paterno} {docente.apellido_materno}, {docente.nombres}"

            # Crear Fast Test
            fast_test = FastTest(
                curso_id=curso_id,
                aula_id=aula_id,
                periodo_id=periodo_id,
                docente_id=docente_id,
                curso_nombre=curso.nombre,
                aula_nombre=aula.nombre,
                periodo_nombre=periodo_nombre,
                docente_nombre=docente_nombre,
                titulo=titulo,
                descripcion=descripcion,
                fecha_evaluacion=fecha_evaluacion,
                peso=peso,
                anio_escolar=anio_escolar,
                estado='abierto',
                usuario_registro=usuario
            )

            db.session.add(fast_test)
            db.session.flush()

            # Auto-crear notas para estudiantes matriculados en el aula
            matriculas = Matricula.query.filter_by(
                aula_id=aula_id,
                anio_escolar=anio_escolar,
                estado='activo'
            ).all()

            for matricula in matriculas:
                nota = NotaFastTest(
                    fast_test_id=fast_test.id,
                    estudiante_id=matricula.estudiante_id,
                    estudiante_nombre_completo=matricula.estudiante_nombre_completo,
                    estudiante_dni=matricula.estudiante_dni,
                    nota=None,  # Sin calificar inicialmente
                    usuario_registro=usuario
                )
                db.session.add(nota)

            db.session.commit()

            AuditLog.registrar(
                tabla='fast_tests',
                registro_id=fast_test.id,
                accion='crear',
                usuario=usuario,
                detalles=f"Fast Test creado: {fast_test.titulo} para {aula.nombre}"
            )

            return fast_test, None

        except Exception as e:
            db.session.rollback()
            return None, f"Error al crear Fast Test: {str(e)}"

    @staticmethod
    def ingresar_notas_fast_test(fast_test_id, notas_dict, usuario=None):
        """
        Ingresa notas de un Fast Test con control de concurrencia
        notas_dict: {estudiante_id: {'nota': float, 'observaciones': str, 'version': int}}
        """
        try:
            fast_test = FastTest.query.get(fast_test_id)
            if not fast_test:
                return None, "Fast Test no encontrado"

            if fast_test.estado == 'cerrado':
                return None, "No se pueden modificar notas de un Fast Test cerrado"

            errores = []
            exitosos = 0

            for estudiante_id, datos in notas_dict.items():
                nota_valor = datos.get('nota')
                observaciones = datos.get('observaciones')
                version_actual = datos.get('version', 1)

                # Buscar nota existente
                nota_ft = NotaFastTest.query.filter_by(
                    fast_test_id=fast_test_id,
                    estudiante_id=estudiante_id
                ).first()

                if not nota_ft:
                    errores.append(f"Estudiante {estudiante_id} no encontrado en este Fast Test")
                    continue

                # Control de concurrencia
                if nota_ft.version != version_actual:
                    errores.append(f"{nota_ft.estudiante_nombre_completo}: Nota modificada por otro usuario")
                    continue

                # Validar nota
                if nota_valor is not None:
                    try:
                        nota_valor = float(nota_valor)
                        if nota_valor < 0 or nota_valor > 20:
                            errores.append(f"{nota_ft.estudiante_nombre_completo}: Nota debe estar entre 0 y 20")
                            continue
                    except ValueError:
                        errores.append(f"{nota_ft.estudiante_nombre_completo}: Nota inválida")
                        continue

                # Actualizar nota
                nota_ft.nota = nota_valor
                nota_ft.observaciones = observaciones if observaciones else None
                nota_ft.version += 1
                nota_ft.usuario_registro = usuario

                exitosos += 1

            db.session.commit()

            # Registrar en auditoría
            AuditLog.registrar(
                tabla='fast_tests',
                registro_id=fast_test_id,
                accion='calificar',
                usuario=usuario,
                detalles=f"Notas ingresadas: {exitosos} exitosas, {len(errores)} errores"
            )

            return {'exitosos': exitosos, 'errores': errores}, None

        except Exception as e:
            db.session.rollback()
            return None, f"Error al ingresar notas: {str(e)}"

    @staticmethod
    def cerrar_fast_test(fast_test_id, usuario=None):
        """Cierra un Fast Test y calcula estadísticas"""
        try:
            fast_test = FastTest.query.get(fast_test_id)
            if not fast_test:
                return None, "Fast Test no encontrado"

            if fast_test.estado == 'cerrado':
                return None, "El Fast Test ya está cerrado"

            # Calcular estadísticas
            fast_test.calcular_estadisticas()
            fast_test.estado = 'cerrado'
            fast_test.fecha_cierre = datetime.utcnow()

            db.session.commit()

            AuditLog.registrar(
                tabla='fast_tests',
                registro_id=fast_test.id,
                accion='cerrar',
                usuario=usuario,
                detalles=f"Fast Test cerrado. Promedio: {fast_test.promedio_general:.2f}" if fast_test.promedio_general else "Fast Test cerrado"
            )

            return fast_test, None

        except Exception as e:
            db.session.rollback()
            return None, f"Error al cerrar Fast Test: {str(e)}"

    @staticmethod
    def obtener_reporte_academico_estudiante(estudiante_id, anio_escolar, incluir_asistencias=True):
        """
        Genera reporte académico completo de un estudiante
        INTEGRACIÓN CRÍTICA: Incluye asistencias del AsistenciaService
        """
        try:
            estudiante = Estudiante.query.get(estudiante_id)
            if not estudiante:
                return None, "Estudiante no encontrado"

            # Obtener todas las matrículas del estudiante para el año
            matriculas = Matricula.query.filter_by(
                estudiante_id=estudiante_id,
                anio_escolar=anio_escolar,
                estado='activo'
            ).all()

            if not matriculas:
                return None, f"Estudiante no matriculado en el año {anio_escolar}"

            # Obtener notas de todos los Fast Tests del año
            notas = NotaFastTest.query.join(FastTest).filter(
                NotaFastTest.estudiante_id == estudiante_id,
                FastTest.anio_escolar == anio_escolar
            ).all()

            # Organizar notas por curso y período
            notas_por_curso = {}
            for nota in notas:
                curso_nombre = nota.fast_test.curso_nombre
                periodo_nombre = nota.fast_test.periodo_nombre

                if curso_nombre not in notas_por_curso:
                    notas_por_curso[curso_nombre] = {}

                if periodo_nombre not in notas_por_curso[curso_nombre]:
                    notas_por_curso[curso_nombre][periodo_nombre] = []

                notas_por_curso[curso_nombre][periodo_nombre].append({
                    'fast_test': nota.fast_test.titulo,
                    'nota': nota.nota,
                    'peso': nota.fast_test.peso,
                    'fecha': nota.fast_test.fecha_evaluacion,
                    'aula': nota.fast_test.aula_nombre
                })

            # Calcular promedios por curso
            promedios_por_curso = {}
            for curso, periodos in notas_por_curso.items():
                promedios_por_curso[curso] = {}

                for periodo, tests in periodos.items():
                    # Calcular promedio ponderado del período
                    notas_validas = [t for t in tests if t['nota'] is not None]
                    if notas_validas:
                        suma_ponderada = sum(t['nota'] * t['peso'] for t in notas_validas)
                        suma_pesos = sum(t['peso'] for t in notas_validas)
                        promedio = suma_ponderada / suma_pesos if suma_pesos > 0 else 0
                        promedios_por_curso[curso][periodo] = round(promedio, 2)
                    else:
                        promedios_por_curso[curso][periodo] = None

                # Calcular promedio final del curso
                promedios_periodos = [p for p in promedios_por_curso[curso].values() if p is not None]
                if promedios_periodos:
                    promedios_por_curso[curso]['PROMEDIO_FINAL'] = round(sum(promedios_periodos) / len(promedios_periodos), 2)
                else:
                    promedios_por_curso[curso]['PROMEDIO_FINAL'] = None

            # INTEGRACIÓN: Obtener reporte de asistencias
            reporte_asistencias = None
            if incluir_asistencias:
                try:
                    from services.asistencia_service import AsistenciaService
                    from datetime import date

                    # Obtener primer y último día del año escolar
                    fecha_inicio = date(int(anio_escolar), 1, 1)
                    fecha_fin = date(int(anio_escolar), 12, 31)

                    reporte_asistencias = AsistenciaService.obtener_reporte_asistencia_estudiante(
                        estudiante_id=estudiante_id,
                        fecha_inicio=fecha_inicio,
                        fecha_fin=fecha_fin
                    )
                except Exception as e:
                    print(f"Error al obtener asistencias: {e}")
                    reporte_asistencias = None

            return {
                'estudiante': {
                    'id': estudiante.id,
                    'nombre_completo': estudiante.nombre_completo(),
                    'dni': estudiante.dni_est,
                    'nivel': estudiante.nivel,
                    'grado': estudiante.grado,
                    'seccion': estudiante.seccion
                },
                'matriculas': [{'aula': m.aula_nombre, 'codigo': m.aula_codigo} for m in matriculas],
                'notas_por_curso': notas_por_curso,
                'promedios_por_curso': promedios_por_curso,
                'asistencias': reporte_asistencias,
                'anio_escolar': anio_escolar
            }, None

        except Exception as e:
            return None, f"Error al generar reporte: {str(e)}"

    @staticmethod
    def listar_fast_tests(aula_id=None, curso_id=None, periodo_id=None, anio_escolar=None, estado=None):
        """Lista Fast Tests con filtros"""
        query = FastTest.query

        if aula_id:
            query = query.filter_by(aula_id=aula_id)
        if curso_id:
            query = query.filter_by(curso_id=curso_id)
        if periodo_id:
            query = query.filter_by(periodo_id=periodo_id)
        if anio_escolar:
            query = query.filter_by(anio_escolar=anio_escolar)
        if estado:
            query = query.filter_by(estado=estado)

        return query.order_by(FastTest.fecha_evaluacion.desc())
