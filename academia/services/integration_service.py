"""
Servicio de integración entre el sistema de Academia y el sistema principal.
Maneja la sincronización de datos de estudiantes y asistencias con control de concurrencia.
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List, Tuple
import logging

# Configurar logging
logger = logging.getLogger(__name__)

# Importar modelos del sistema principal
# Esto se hace dinámicamente para evitar problemas de importación circular
def _get_main_models():
    """Importa los modelos del sistema principal de forma segura"""
    try:
        # Agregar el path del proyecto principal si no está
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        from models import Estudiante, Asistencia, db
        return Estudiante, Asistencia, db
    except ImportError as e:
        logger.error(f"Error importando modelos del sistema principal: {e}")
        raise


class OptimisticLockException(Exception):
    """Excepción lanzada cuando hay un conflicto de versión en actualización optimista"""
    pass


class PermissionDeniedException(Exception):
    """Excepción lanzada cuando un usuario no tiene permisos para la operación"""
    pass


class IntegrationService:
    """
    Servicio para integración entre sistema de Academia y sistema principal.
    Implementa control de concurrencia optimista y manejo robusto de errores.
    """

    def __init__(self):
        """Inicializa el servicio de integración"""
        self.Estudiante, self.Asistencia, self.db = _get_main_models()
        self._cache = {}  # Cache simple para reducir consultas
        self._cache_timeout = 300  # 5 minutos

    def _clear_cache(self, key: str = None):
        """Limpia el cache completamente o una clave específica"""
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()

    def _get_cached(self, key: str) -> Optional[Any]:
        """Obtiene un valor del cache si no ha expirado"""
        if key in self._cache:
            data, timestamp = self._cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self._cache_timeout):
                return data
            else:
                del self._cache[key]
        return None

    def _set_cached(self, key: str, value: Any):
        """Guarda un valor en el cache con timestamp"""
        self._cache[key] = (value, datetime.now())

    def get_estudiante_by_dni(self, dni: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un estudiante por DNI del sistema principal.

        Args:
            dni: DNI del estudiante

        Returns:
            Diccionario con datos del estudiante o None si no existe
        """
        cache_key = f"estudiante_{dni}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        try:
            estudiante = self.Estudiante.query.filter_by(dni_est=dni).first()
            if estudiante:
                result = self._estudiante_to_dict(estudiante)
                self._set_cached(cache_key, result)
                return result
            return None
        except Exception as e:
            logger.error(f"Error obteniendo estudiante con DNI {dni}: {e}", exc_info=True)
            return None

    def _estudiante_to_dict(self, estudiante) -> Dict[str, Any]:
        """Convierte un objeto Estudiante a diccionario"""
        return {
            'id': estudiante.id,
            'nivel': estudiante.nivel,
            'grado': estudiante.grado,
            'seccion': estudiante.seccion,
            'turno': estudiante.turno,
            'apellido_paterno_est': estudiante.apellido_paterno_est,
            'apellido_materno_est': estudiante.apellido_materno_est,
            'nombres_est': estudiante.nombres_est,
            'dni_est': estudiante.dni_est,
            'correo_est': estudiante.correo_est,
            'fecha_nacimiento_est': estudiante.fecha_nacimiento_est,
            'direccion_est': estudiante.direccion_est,
            'distrito_est': estudiante.distrito_est,
            'provincia_est': estudiante.provincia_est,
            'referencia_est': estudiante.referencia_est,
            'numero_celular_est': estudiante.numero_celular_est,
            'telefono_fijo_est': estudiante.telefono_fijo_est,
            'celular_padre': estudiante.celular_padre,
            'correo_padre': estudiante.correo_padre,
            'celular_madre': estudiante.celular_madre,
            'correo_madre': estudiante.correo_madre,
            'foto_perfil': estudiante.foto_perfil,
            'version': estudiante.version,
            'fecha_ultima_modificacion': estudiante.fecha_ultima_modificacion,
            # Sin exponer el hash: solo indica si ya definió clave propia en portal Academia
            'tiene_password_academia_personalizada': bool(
                getattr(estudiante, 'academia_portal_password_hash', None)
            ),
        }

    def validate_student_permission(self, dni_estudiante: str, dni_sesion: str) -> bool:
        """
        Valida que el estudiante en sesión tiene permiso para ver/editar los datos.

        Args:
            dni_estudiante: DNI del estudiante cuyos datos se quieren acceder
            dni_sesion: DNI del estudiante en la sesión actual

        Returns:
            True si tiene permiso, False en caso contrario
        """
        return dni_estudiante == dni_sesion

    def update_estudiante_info(
        self,
        dni: str,
        data: Dict[str, Any],
        current_version: int,
        modificado_por: str = "estudiante_portal"
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Actualiza la información de un estudiante con control optimista de concurrencia.

        Args:
            dni: DNI del estudiante
            data: Diccionario con los datos a actualizar
            current_version: Versión actual que el cliente tiene
            modificado_por: Identificador de quién hace la modificación

        Returns:
            Tupla (éxito, mensaje_error, datos_actualizados)
            - éxito: True si se actualizó correctamente
            - mensaje_error: Mensaje de error si hubo problema
            - datos_actualizados: Datos actualizados del estudiante si fue exitoso
        """
        try:
            # Buscar estudiante
            estudiante = self.Estudiante.query.filter_by(dni_est=dni).first()

            if not estudiante:
                return False, f"No se encontró estudiante con DNI {dni}", None

            # Control optimista de concurrencia
            if estudiante.version != current_version:
                logger.warning(
                    f"Conflicto de versión para estudiante {dni}. "
                    f"Versión esperada: {current_version}, versión actual: {estudiante.version}"
                )
                raise OptimisticLockException(
                    f"Los datos fueron modificados por otro usuario. "
                    f"Por favor, recarga la página y vuelve a intentar."
                )

            # Campos editables por el estudiante
            campos_editables = [
                'correo_est', 'numero_celular_est', 'direccion_est',
                'distrito_est', 'provincia_est', 'referencia_est',
                'celular_padre', 'correo_padre',
                'celular_madre', 'correo_madre'
            ]

            # Actualizar solo campos editables
            cambios_realizados = []
            for campo in campos_editables:
                if campo in data:
                    valor_anterior = getattr(estudiante, campo)
                    valor_nuevo = data[campo]

                    # Solo actualizar si cambió
                    if valor_anterior != valor_nuevo:
                        setattr(estudiante, campo, valor_nuevo)
                        cambios_realizados.append(campo)

            if not cambios_realizados:
                return True, None, self._estudiante_to_dict(estudiante)

            # Incrementar versión y actualizar metadata
            estudiante.version += 1
            estudiante.fecha_ultima_modificacion = datetime.utcnow()
            estudiante.ultimo_usuario_modificacion = modificado_por

            # Commit con manejo de errores
            try:
                self.db.session.commit()

                # Limpiar cache
                self._clear_cache(f"estudiante_{dni}")

                # Log de auditoría
                logger.info(
                    f"Estudiante {dni} actualizado exitosamente. "
                    f"Campos modificados: {', '.join(cambios_realizados)}. "
                    f"Versión: {estudiante.version}. "
                    f"Modificado por: {modificado_por}"
                )

                return True, None, self._estudiante_to_dict(estudiante)

            except Exception as e:
                self.db.session.rollback()
                logger.error(f"Error al guardar cambios para estudiante {dni}: {e}", exc_info=True)
                return False, "Error al guardar los cambios. Por favor, intenta nuevamente.", None

        except OptimisticLockException as e:
            self.db.session.rollback()
            return False, str(e), None

        except Exception as e:
            self.db.session.rollback()
            logger.error(f"Error inesperado actualizando estudiante {dni}: {e}", exc_info=True)
            return False, "Error inesperado. Por favor, contacta al administrador.", None

    def get_asistencias_estudiante(
        self,
        dni: str,
        fecha_inicio: Optional[datetime] = None,
        fecha_fin: Optional[datetime] = None,
        limit: int = 100
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Obtiene las asistencias de un estudiante.

        Args:
            dni: DNI del estudiante
            fecha_inicio: Fecha de inicio para filtrar (opcional)
            fecha_fin: Fecha de fin para filtrar (opcional)
            limit: Límite de registros a retornar

        Returns:
            Lista de diccionarios con las asistencias (puede ser vacía si no hay asistencias)
            o None si hay un error
        """
        try:
            # Buscar estudiante
            estudiante = self.Estudiante.query.filter_by(dni_est=dni).first()

            if not estudiante:
                logger.warning(f"No se encontró estudiante con DNI {dni}")
                return []  # Retornar lista vacía en vez de None

            # Query base
            query = self.Asistencia.query.filter_by(estudiante_id=estudiante.id)

            # Aplicar filtros de fecha
            if fecha_inicio:
                query = query.filter(self.Asistencia.fecha_hora >= fecha_inicio)
            if fecha_fin:
                query = query.filter(self.Asistencia.fecha_hora <= fecha_fin)

            # Ordenar y limitar
            asistencias = query.order_by(
                self.Asistencia.fecha_hora.desc()
            ).limit(limit).all()

            # Convertir a diccionarios
            resultado = []
            for asist in asistencias:
                resultado.append({
                    'id': asist.id,
                    'tipo': asist.tipo.lower() if asist.tipo else None,  # Normalizar a minúsculas
                    'fecha_hora': asist.fecha_hora,
                    'fecha_str': asist.fecha_str,
                    'hora_str': asist.hora_str,
                    'fecha_formateada': asist.fecha_str,  # Alias para template
                    'hora_formateada': asist.hora_str,    # Alias para template
                    'observaciones': getattr(asist, 'observaciones', None)
                })

            logger.info(f"Se encontraron {len(resultado)} asistencias para estudiante {dni}")
            return resultado

        except Exception as e:
            logger.error(f"Error obteniendo asistencias para estudiante {dni}: {e}", exc_info=True)
            return None

    def get_estadisticas_asistencias(
        self,
        dni: str,
        mes: Optional[int] = None,
        anio: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Obtiene estadísticas de asistencia de un estudiante.

        Args:
            dni: DNI del estudiante
            mes: Mes para filtrar (opcional)
            anio: Año para filtrar (opcional)

        Returns:
            Diccionario con estadísticas (siempre retorna un dict con valores en 0 si no hay datos)
        """
        try:
            from sqlalchemy import func, extract

            # Buscar estudiante
            estudiante = self.Estudiante.query.filter_by(dni_est=dni).first()

            if not estudiante:
                logger.warning(f"No se encontró estudiante con DNI {dni} para estadísticas")
                return {'entradas': 0, 'salidas': 0, 'total': 0}

            # Query base
            query = self.db.session.query(
                self.Asistencia.tipo,
                func.count(self.Asistencia.id).label('total')
            ).filter(
                self.Asistencia.estudiante_id == estudiante.id
            )

            # Filtrar por mes y año si se proporcionan
            if mes:
                query = query.filter(extract('month', self.Asistencia.fecha_hora) == mes)
            if anio:
                query = query.filter(extract('year', self.Asistencia.fecha_hora) == anio)

            # Agrupar por tipo
            resultados = query.group_by(self.Asistencia.tipo).all()

            # Convertir a diccionario
            stats = {
                'entradas': 0,
                'salidas': 0,
                'total': 0
            }

            for tipo, total in resultados:
                if tipo == 'ENTRADA':
                    stats['entradas'] = total
                elif tipo == 'SALIDA':
                    stats['salidas'] = total
                stats['total'] += total

            return stats

        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de asistencia para {dni}: {e}", exc_info=True)
            return {'entradas': 0, 'salidas': 0, 'total': 0}


# Instancia global del servicio
_integration_service = None

def get_integration_service() -> IntegrationService:
    """Obtiene la instancia global del servicio de integración"""
    global _integration_service
    if _integration_service is None:
        _integration_service = IntegrationService()
    return _integration_service
