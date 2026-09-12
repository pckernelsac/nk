# services/portal_estudiante_service.py
from models import db, Estudiante, AuditLog
from sqlalchemy.exc import IntegrityError
from datetime import datetime


class PortalEstudianteService:
    """Servicio para gestionar el portal de actualización de estudiantes"""

    # Campos permitidos para actualización por estudiantes/apoderados
    CAMPOS_PERMITIDOS = {
        # Datos del estudiante
        'correo_est',
        'numero_celular_est',
        'telefono_fijo_est',
        'direccion_est',
        'distrito_est',
        'provincia_est',
        'referencia_est',

        # Datos del padre
        'celular_padre',
        'telefono_fijo_padre',
        'correo_padre',
        'direccion_padre',
        'distrito_padre',
        'provincia_padre',

        # Datos de la madre
        'celular_madre',
        'telefono_fijo_madre',
        'correo_madre',
        'direccion_madre',
        'distrito_madre',
        'provincia_madre',

        # Datos del apoderado
        'celular_apoderado',
        'telefono_fijo_apoderado',
        'correo_apoderado',
        'direccion_apoderado',
        'distrito_apoderado',
        'provincia_apoderado',
    }

    @staticmethod
    def autenticar_estudiante(dni, codigo):
        """
        Autentica un estudiante usando DNI y código (fecha de nacimiento)

        Args:
            dni: DNI del estudiante
            codigo: Código de acceso (fecha de nacimiento en formato DDMMYYYY)

        Returns:
            tuple: (estudiante, error_message)
        """
        try:
            # Buscar estudiante por DNI
            estudiante = Estudiante.query.filter_by(dni_est=dni).first()

            if not estudiante:
                return None, "No se encontró ningún estudiante con ese DNI"

            # Verificar que puede actualizar datos
            if not estudiante.puede_actualizar_datos:
                return None, "No tiene permisos para acceder al portal"

            # Verificar código (fecha de nacimiento)
            codigo_valido = estudiante.generar_codigo_portal()

            if not codigo_valido:
                return None, "No se ha configurado el código de acceso. Contacte con la institución."

            if codigo != codigo_valido:
                return None, "Código de acceso incorrecto"

            # Mismas puertas que el portal de Academia: acceso suspendido por la
            # administración y matrícula que ya no corresponde al ciclo en curso.
            from services.acceso_portal import mensaje_sin_matricula, sin_matricula_vigente

            if getattr(estudiante, "acceso_suspendido", False):
                return None, (
                    "Tu acceso al portal está suspendido por pensión pendiente. "
                    "Acércate a la administración para regularizar tu situación."
                )

            if sin_matricula_vigente(estudiante):
                return None, mensaje_sin_matricula()

            # Registrar acceso en auditoría
            AuditLog.registrar(
                tabla='estudiantes',
                registro_id=estudiante.id,
                accion='login_portal',
                usuario=f"Estudiante DNI: {dni}",
                detalles="Acceso exitoso al portal de estudiantes"
            )

            return estudiante, None

        except Exception as e:
            return None, f"Error al autenticar: {str(e)}"

    @staticmethod
    def validar_campos_permitidos(campos_dict):
        """
        Valida que solo se estén actualizando campos permitidos

        Args:
            campos_dict: Diccionario con campos a actualizar

        Returns:
            tuple: (campos_validos, campos_rechazados)
        """
        campos_validos = {}
        campos_rechazados = []

        for campo, valor in campos_dict.items():
            if campo in PortalEstudianteService.CAMPOS_PERMITIDOS:
                campos_validos[campo] = valor
            else:
                campos_rechazados.append(campo)

        return campos_validos, campos_rechazados

    @staticmethod
    def actualizar_datos_estudiante(estudiante_id, campos_dict, version_actual):
        """
        Actualiza datos del estudiante con control de concurrencia optimista

        Args:
            estudiante_id: ID del estudiante
            campos_dict: Diccionario con campos a actualizar
            version_actual: Versión actual del registro (para control de concurrencia)

        Returns:
            tuple: (estudiante, error_message)
        """
        try:
            # Obtener estudiante
            estudiante = Estudiante.query.get(estudiante_id)

            if not estudiante:
                return None, "Estudiante no encontrado"

            # Verificar permisos
            if not estudiante.puede_actualizar_datos:
                return None, "No tiene permisos para actualizar datos"

            # Control de concurrencia optimista
            if estudiante.version != version_actual:
                return None, "Los datos fueron modificados por otro usuario. Por favor, recargue la página y vuelva a intentar."

            # Validar campos permitidos
            campos_validos, campos_rechazados = PortalEstudianteService.validar_campos_permitidos(campos_dict)

            if campos_rechazados:
                return None, f"No se permite actualizar los siguientes campos: {', '.join(campos_rechazados)}"

            # Registrar cambios para auditoría
            cambios = []

            # Actualizar campos
            for campo, valor in campos_validos.items():
                valor_anterior = getattr(estudiante, campo, None)
                if valor_anterior != valor:
                    setattr(estudiante, campo, valor)
                    cambios.append(f"{campo}: '{valor_anterior}' → '{valor}'")

            if not cambios:
                return estudiante, "No se detectaron cambios en los datos"

            # Actualizar metadatos
            estudiante.version += 1  # Incrementar versión
            estudiante.ultima_actualizacion_portal = datetime.utcnow()
            estudiante.ultimo_usuario_modificacion = f"Portal - DNI: {estudiante.dni_est}"

            db.session.commit()

            # Registrar en auditoría
            AuditLog.registrar(
                tabla='estudiantes',
                registro_id=estudiante.id,
                accion='actualizar_portal',
                usuario=f"Estudiante DNI: {estudiante.dni_est}",
                detalles=f"Campos actualizados desde portal: {', '.join(cambios)}"
            )

            return estudiante, None

        except IntegrityError as e:
            db.session.rollback()
            return None, "Error de integridad en los datos"
        except Exception as e:
            db.session.rollback()
            return None, f"Error al actualizar datos: {str(e)}"

    @staticmethod
    def obtener_datos_actualizables(estudiante):
        """
        Obtiene solo los datos que el estudiante puede actualizar

        Args:
            estudiante: Instancia de Estudiante

        Returns:
            dict con datos actualizables organizados por categoría
        """
        return {
            'estudiante': {
                'correo': estudiante.correo_est,
                'celular': estudiante.numero_celular_est,
                'telefono_fijo': estudiante.telefono_fijo_est,
                'direccion': estudiante.direccion_est,
                'distrito': estudiante.distrito_est,
                'provincia': estudiante.provincia_est,
                'referencia': estudiante.referencia_est,
            },
            'padre': {
                'celular': estudiante.celular_padre,
                'telefono_fijo': estudiante.telefono_fijo_padre,
                'correo': estudiante.correo_padre,
                'direccion': estudiante.direccion_padre,
                'distrito': estudiante.distrito_padre,
                'provincia': estudiante.provincia_padre,
            },
            'madre': {
                'celular': estudiante.celular_madre,
                'telefono_fijo': estudiante.telefono_fijo_madre,
                'correo': estudiante.correo_madre,
                'direccion': estudiante.direccion_madre,
                'distrito': estudiante.distrito_madre,
                'provincia': estudiante.provincia_madre,
            },
            'apoderado': {
                'celular': estudiante.celular_apoderado,
                'telefono_fijo': estudiante.telefono_fijo_apoderado,
                'correo': estudiante.correo_apoderado,
                'direccion': estudiante.direccion_apoderado,
                'distrito': estudiante.distrito_apoderado,
                'provincia': estudiante.provincia_apoderado,
            },
            'metadatos': {
                'version': estudiante.version,
                'ultima_actualizacion': estudiante.ultima_actualizacion_portal,
                'puede_actualizar': estudiante.puede_actualizar_datos,
            }
        }

    @staticmethod
    def habilitar_acceso_portal(estudiante_id, habilitar=True, usuario=None):
        """
        Habilita o deshabilita el acceso al portal para un estudiante

        Args:
            estudiante_id: ID del estudiante
            habilitar: True para habilitar, False para deshabilitar
            usuario: Usuario que realiza la acción

        Returns:
            tuple: (estudiante, error_message)
        """
        try:
            estudiante = Estudiante.query.get(estudiante_id)

            if not estudiante:
                return None, "Estudiante no encontrado"

            estudiante.puede_actualizar_datos = habilitar

            db.session.commit()

            # Registrar en auditoría
            accion = 'habilitar' if habilitar else 'deshabilitar'
            AuditLog.registrar(
                tabla='estudiantes',
                registro_id=estudiante.id,
                accion=f'{accion}_portal',
                usuario=usuario,
                detalles=f"Acceso al portal {accion}ado para {estudiante.nombre_completo()}"
            )

            return estudiante, None

        except Exception as e:
            db.session.rollback()
            return None, f"Error al modificar acceso: {str(e)}"
