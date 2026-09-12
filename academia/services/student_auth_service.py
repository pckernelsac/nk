# -*- coding: utf-8 -*-
"""
Servicio de autenticación para estudiantes.
Permite a los estudiantes iniciar sesión con su StudentID para ver sus boletas.
Usa SQLAlchemy ORM (models/academia.py).
"""

from typing import Any, Dict, List, MutableMapping, Optional, Tuple

from werkzeug.security import check_password_hash, generate_password_hash

from models import db
from models.academia import AcademiaStudent, AcademicArea
from models.estudiante import Estudiante


class StudentAuthService:
    """
    Servicio para la gestión de autenticación de estudiantes.
    Session keys se escriben en ``sess`` (p.ej. ``request.session`` de Starlette).
    """

    def _password_academia_ok(self, estudiante: Optional[Estudiante], student_id: str, password: str) -> bool:
        """Valida contraseña del portal Academia: hash personalizado o legado (DNI)."""
        if not password:
            return False
        pwd = password.strip()
        sid = (student_id or "").strip()
        if estudiante is not None:
            h = getattr(estudiante, "academia_portal_password_hash", None)
            if h:
                return check_password_hash(h, pwd)
            return pwd == sid
        return pwd == sid

    def login(self, sess: MutableMapping, student_id: str, password: str) -> bool:
        """
        Inicia sesión para un estudiante.
        Busca primero en la BD de academia, si no existe, busca en el sistema principal.

        Contraseña: si el estudiante tiene ``academia_portal_password_hash``, se verifica ese hash;
        si no, el comportamiento legado es contraseña = DNI (Student ID).
        """
        if not student_id or not password:
            return False

        sid = student_id.strip()
        estudiante = Estudiante.query.filter_by(dni_est=sid).first()
        if not self._password_academia_ok(estudiante, sid, password):
            return False

        # Acceso suspendido por la administración (p. ej. pensión pendiente):
        # credenciales válidas pero el ingreso queda bloqueado.
        if estudiante is not None and getattr(estudiante, "acceso_suspendido", False):
            sess["login_error"] = (
                "Tu acceso al portal está suspendido por pensión pendiente. "
                "Acércate a la administración para regularizar tu situación."
            )
            return False

        # Matrícula que ya no corresponde al ciclo en curso (retirado, trasladado
        # o matriculado sólo en años anteriores): credenciales válidas, sin ingreso.
        from services.acceso_portal import mensaje_sin_matricula, sin_matricula_vigente

        if sin_matricula_vigente(estudiante):
            sess["login_error"] = mensaje_sin_matricula()
            return False

        student = AcademiaStudent.query.filter_by(student_id=sid).order_by(
            AcademiaStudent.quiz_created.asc(),
            AcademiaStudent.id.asc(),
        ).first()

        if student:
            sess["student_id"] = student.id
            sess["student_id_number"] = student.student_id
            sess["estudiante_id"] = student.estudiante_id
            sess["student_name"] = f"{student.first_name} {student.last_name}"
            sess["student_authenticated"] = True
            sess["academic_area_id"] = student.academic_area_id
            sess["has_academic_data"] = True
            return True

        try:
            if estudiante:
                sess["student_id"] = None
                sess["student_id_number"] = estudiante.dni_est
                sess["estudiante_id"] = estudiante.id
                sess["student_name"] = f"{estudiante.nombres_est} {estudiante.apellido_paterno_est}"
                sess["student_authenticated"] = True
                sess["academic_area_id"] = None
                sess["has_academic_data"] = False
                return True
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.debug("No se pudo consultar sistema principal: %s", e)

        return False

    def cambiar_password_portal(
        self,
        dni: str,
        password_actual: str,
        password_nuevo: str,
        password_confirm: str,
    ) -> Tuple[bool, str]:
        """
        Cambia la contraseña del portal Academia para un estudiante del sistema principal.
        Requiere la contraseña actual (o el DNI si aún no definió una personalizada).
        """
        dni = (dni or "").strip()
        if not dni:
            return False, "Sesión inválida."

        est = Estudiante.query.filter_by(dni_est=dni).first()
        if not est:
            return False, "No se encontró tu registro en el sistema."

        pa = (password_actual or "").strip()
        pn = (password_nuevo or "").strip()
        pc = (password_confirm or "").strip()

        if not pa or not pn or not pc:
            return False, "Completa todos los campos de contraseña."

        if not self._password_academia_ok(est, dni, pa):
            return False, "La contraseña actual no es correcta."

        if len(pn) < 8:
            return False, "La nueva contraseña debe tener al menos 8 caracteres."

        if pn != pc:
            return False, "La confirmación no coincide con la nueva contraseña."

        if pn == dni:
            return False, "Por seguridad, usa una contraseña distinta a tu DNI."

        est.academia_portal_password_hash = generate_password_hash(pn)
        db.session.commit()
        try:
            from academia.services.integration_service import get_integration_service

            get_integration_service()._clear_cache(f"estudiante_{dni}")
        except Exception:
            pass
        return True, ""

    def logout(self, sess: MutableMapping) -> None:
        """Cierra la sesión del estudiante actual."""
        for key in (
            "student_id",
            "student_id_number",
            "estudiante_id",
            "student_name",
            "student_authenticated",
            "academic_area_id",
            "has_academic_data",
        ):
            sess.pop(key, None)

    def is_authenticated(self, sess: MutableMapping) -> bool:
        """Verifica si hay un estudiante autenticado."""
        return bool(sess.get("student_authenticated", False))

    def get_current_student(self, sess: MutableMapping) -> Optional[Dict[str, Any]]:
        """Obtiene los datos del estudiante actual."""
        if not self.is_authenticated(sess):
            return None

        student_table_id = sess.get("student_id")

        if not student_table_id:
            name = sess.get("student_name", "") or ""
            parts = name.split()
            return {
                "id": None,
                "student_id": sess.get("student_id_number"),
                "first_name": parts[0] if parts else "",
                "last_name": " ".join(parts[1:]) if len(parts) > 1 else "",
                "academic_area_id": None,
                "academic_area_name": None,
                "formatted_quiz_date": None,
                "has_academic_data": False,
            }

        student = db.session.get(AcademiaStudent, student_table_id)
        if student:
            student_dict = student.to_dict()
            student_dict["has_academic_data"] = True
            return student_dict

        return None

    def get_all_student_reports(self, student_id_number: str) -> List[Dict[str, Any]]:
        """
        Obtiene todos los reportes disponibles para un estudiante por su StudentID (DNI/código).
        Ordenados por fecha de examen ascendente.
        """
        students = AcademiaStudent.query.filter_by(
            student_id=student_id_number
        ).order_by(
            AcademiaStudent.quiz_created.asc(),
            AcademiaStudent.id.asc()
        ).all()

        return [s.to_dict() for s in students]
