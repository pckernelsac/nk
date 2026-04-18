# -*- coding: utf-8 -*-
"""
Servicio para la gestión de estudiantes.
Usa SQLAlchemy ORM (models/academia.py).
"""

from typing import Dict, List, Any, Optional
import datetime
import re

from models import db
from models.academia import AcademiaStudent, AcademicArea


class StudentService:
    """
    Servicio para gestionar estudiantes, incluyendo guardar, recuperar,
    actualizar y eliminar sus datos.
    """

    def __init__(self, academic_service):
        self.academic_service = academic_service

    def save_student(self, quiz_name: str, quiz_class: str, first_name: str, last_name: str,
                     student_id_field: str, custom_id: str,
                     earned_points: Optional[float], possible_points: Optional[float],
                     percent_correct: Optional[float], quiz_created: str, data_exported: str,
                     responses: str, pri_keys: str, points: str, marks: str,
                     academic_area_id: Optional[int], key_version: str = '', programa: str = '',
                     nivel: str = 'ACADEMIA', estudiante_id: Optional[int] = None) -> Optional[int]:
        """Guarda un nuevo registro de examen en la base de datos."""
        calculated_percent = percent_correct
        if calculated_percent is None:
            try:
                earned = float(earned_points) if earned_points is not None else 0.0
                possible = float(possible_points) if possible_points is not None else 0.0
                calculated_percent = (earned / possible) * 100.0 if possible > 0 else 0.0
            except (ValueError, TypeError):
                calculated_percent = 0.0

        # Formatear quiz_created a YYYY-MM-DD
        quiz_created_formatted = quiz_created
        if isinstance(quiz_created, str):
            date_formats_to_try = ["%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"]
            date_str = quiz_created.split(' ')[0]
            for fmt in date_formats_to_try:
                try:
                    parsed_date = datetime.datetime.strptime(date_str, fmt).date()
                    quiz_created_formatted = parsed_date.strftime('%Y-%m-%d')
                    break
                except ValueError:
                    continue

        try:
            student = AcademiaStudent(
                quiz_name=quiz_name, quiz_class=quiz_class,
                first_name=first_name, last_name=last_name,
                student_id=student_id_field, custom_id=custom_id,
                estudiante_id=estudiante_id,
                earned_points=earned_points, possible_points=possible_points,
                percent_correct=calculated_percent,
                quiz_created=quiz_created_formatted, data_exported=data_exported,
                key_version=key_version, responses=responses,
                pri_keys=pri_keys, points=points, marks=marks,
                academic_area_id=academic_area_id, programa=programa,
                nivel=nivel
            )
            db.session.add(student)
            db.session.commit()
            return student.id
        except Exception as e:
            db.session.rollback()
            print(f"Error al guardar estudiante: {e}")
            return None

    def get_all_students(self) -> List[Dict[str, Any]]:
        try:
            students = AcademiaStudent.query.order_by(
                AcademiaStudent.last_name, AcademiaStudent.first_name
            ).all()
            return [s.to_dict() for s in students]
        except Exception as e:
            print(f"Error al obtener todos los estudiantes: {e}")
            return []

    def get_total_students(self) -> int:
        try:
            return AcademiaStudent.query.count()
        except Exception as e:
            print(f"Error al contar estudiantes: {e}")
            return 0

    def get_all_students_paginated(self, page: int = 1, per_page: int = 20) -> List[Dict[str, Any]]:
        try:
            from utils.pagination import paginate_query

            q = AcademiaStudent.query.order_by(
                AcademiaStudent.last_name, AcademiaStudent.first_name
            )
            pagination = paginate_query(q, page=page, per_page=per_page, error_out=False)
            return [s.to_dict() for s in pagination.items]
        except Exception as e:
            print(f"Error al obtener estudiantes paginados: {e}")
            return []

    def get_student_by_id(self, student_db_id: int) -> Optional[Dict[str, Any]]:
        try:
            student = db.session.get(AcademiaStudent, student_db_id)
            return student.to_dict() if student else None
        except Exception as e:
            print(f"Error al obtener estudiante por ID {student_db_id}: {e}")
            return None

    def update_student_academic_area(self, student_db_id: int, academic_area_id: int) -> bool:
        try:
            student = db.session.get(AcademiaStudent, student_db_id)
            if student:
                student.academic_area_id = academic_area_id
                db.session.commit()
                return True
            return False
        except Exception as e:
            db.session.rollback()
            print(f"Error al actualizar área académica para estudiante {student_db_id}: {e}")
            return False

    def delete_student(self, student_db_id: int) -> bool:
        try:
            student = db.session.get(AcademiaStudent, student_db_id)
            if student:
                db.session.delete(student)
                db.session.commit()
                return True
            return False
        except Exception as e:
            db.session.rollback()
            print(f"Error al eliminar estudiante {student_db_id}: {e}")
            return False

    def delete_all_students(self) -> bool:
        try:
            AcademiaStudent.query.delete()
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error al eliminar todos los estudiantes: {e}")
            return False

    @staticmethod
    def _extract_eta_number_from_name(quiz_name: str) -> Optional[int]:
        """Extrae el número de ETA del nombre del quiz (ej: 'ETA 06' -> 6)."""
        if not quiz_name:
            return None
        patterns = [r'ETA(\d+)-\w+-\d{4}-\d+', r'ETA\s*N?°?\s*(\d+)', r'ETA\s*(\d+)']
        for pattern in patterns:
            match = re.search(pattern, quiz_name.upper())
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        return None

    def get_students_by_area_ranked(self, academic_area_id: int, eta_number: Optional[int] = None) -> List[Dict[str, Any]]:
        print(f"[ETA SYSTEM] Área: {academic_area_id}, ETA: {eta_number}")

        try:
            if eta_number is not None and isinstance(eta_number, int) and eta_number >= 1:
                # Obtener quiz_names distintos para esta área
                name_rows = db.session.query(AcademiaStudent.quiz_name).filter(
                    AcademiaStudent.academic_area_id == academic_area_id,
                    AcademiaStudent.quiz_name.isnot(None)
                ).distinct().all()

                if not name_rows:
                    return []

                # Encontrar quiz_names cuyo número coincide con eta_number
                matching_names = []
                for (qname,) in name_rows:
                    if self._extract_eta_number_from_name(qname) == eta_number:
                        matching_names.append(qname)

                print(f"quiz_names que coinciden con ETA {eta_number}: {matching_names}")
                if not matching_names:
                    return []

                students = AcademiaStudent.query.filter(
                    AcademiaStudent.academic_area_id == academic_area_id,
                    AcademiaStudent.quiz_name.in_(matching_names)
                ).order_by(
                    AcademiaStudent.percent_correct.desc(),
                    AcademiaStudent.last_name.asc(),
                    AcademiaStudent.first_name.asc()
                ).all()
            else:
                students = AcademiaStudent.query.filter_by(
                    academic_area_id=academic_area_id
                ).order_by(
                    AcademiaStudent.percent_correct.desc(),
                    AcademiaStudent.last_name.asc(),
                    AcademiaStudent.first_name.asc()
                ).all()

            result = [s.to_dict() for s in students]
            print(f"Encontrados {len(result)} estudiantes")
            return result

        except Exception as e:
            print(f"Error: {e}")
            return []

    def get_available_etas_by_area(self, academic_area_id: int) -> List[Dict[str, Any]]:
        etas_list = []
        try:
            rows = db.session.query(
                AcademiaStudent.quiz_created,
                AcademiaStudent.quiz_name,
                db.func.count(AcademiaStudent.id)
            ).filter(
                AcademiaStudent.academic_area_id == academic_area_id,
                AcademiaStudent.quiz_created.isnot(None)
            ).group_by(
                AcademiaStudent.quiz_created, AcademiaStudent.quiz_name
            ).order_by(AcademiaStudent.quiz_created.asc()).all()

            for fecha_eta, quiz_name, estudiantes_count in rows:
                extracted_number = self._extract_eta_number_from_name(quiz_name)
                eta_number = extracted_number if extracted_number is not None else 0
                etas_list.append({
                    'eta_number': eta_number,
                    'fecha': fecha_eta,
                    'quiz_name': quiz_name,
                    'estudiantes_count': estudiantes_count,
                    'display_name': f"ETA {eta_number:02d} - {quiz_name[:30]}{'...' if len(str(quiz_name)) > 30 else ''}"
                })
            etas_list.sort(key=lambda x: x['eta_number'])
        except Exception as e:
            print(f"Error obteniendo ETAs disponibles para área {academic_area_id}: {e}")
        return etas_list

    def get_students_by_nivel_grado_ranked(self, nivel: str, grado: str, eta_number: Optional[int] = None) -> List[Dict[str, Any]]:
        """Ranking de estudiantes por nivel escolar + grado (para INICIAL/PRIMARIA/SECUNDARIA)."""
        try:
            query = AcademiaStudent.query.filter(
                AcademiaStudent.nivel == nivel,
                AcademiaStudent.quiz_class == grado
            )

            if eta_number is not None and isinstance(eta_number, int) and eta_number >= 1:
                name_rows = query.with_entities(AcademiaStudent.quiz_name).distinct().all()
                matching_names = [
                    qname for (qname,) in name_rows
                    if self._extract_eta_number_from_name(qname) == eta_number
                ]
                if not matching_names:
                    return []
                query = AcademiaStudent.query.filter(
                    AcademiaStudent.nivel == nivel,
                    AcademiaStudent.quiz_class == grado,
                    AcademiaStudent.quiz_name.in_(matching_names)
                )

            students = query.order_by(
                AcademiaStudent.percent_correct.desc(),
                AcademiaStudent.last_name.asc(),
                AcademiaStudent.first_name.asc()
            ).all()
            return [s.to_dict() for s in students]
        except Exception as e:
            print(f"Error ranking nivel {nivel} grado {grado}: {e}")
            return []

    def get_available_etas_by_nivel_grado(self, nivel: str, grado: str) -> List[Dict[str, Any]]:
        """Obtiene ETAs disponibles para un nivel escolar + grado."""
        etas_list = []
        try:
            rows = db.session.query(
                AcademiaStudent.quiz_created,
                AcademiaStudent.quiz_name,
                db.func.count(AcademiaStudent.id)
            ).filter(
                AcademiaStudent.nivel == nivel,
                AcademiaStudent.quiz_class == grado,
                AcademiaStudent.quiz_created.isnot(None)
            ).group_by(
                AcademiaStudent.quiz_created, AcademiaStudent.quiz_name
            ).order_by(AcademiaStudent.quiz_created.asc()).all()

            for fecha_eta, quiz_name, estudiantes_count in rows:
                extracted_number = self._extract_eta_number_from_name(quiz_name)
                eta_number = extracted_number if extracted_number is not None else 0
                etas_list.append({
                    'eta_number': eta_number,
                    'fecha': fecha_eta,
                    'quiz_name': quiz_name,
                    'estudiantes_count': estudiantes_count,
                    'display_name': f"ETA {eta_number:02d} - {quiz_name[:30]}{'...' if len(str(quiz_name)) > 30 else ''}"
                })
            etas_list.sort(key=lambda x: x['eta_number'])
        except Exception as e:
            print(f"Error obteniendo ETAs para {nivel} grado {grado}: {e}")
        return etas_list

    def get_students_by_programa_ranked(self, programa: str, eta_number: Optional[int] = None) -> List[Dict[str, Any]]:
        """Ranking de estudiantes por programa/aula (para ACADEMIA)."""
        try:
            query = AcademiaStudent.query.filter(
                AcademiaStudent.programa == programa
            )

            if eta_number is not None and isinstance(eta_number, int) and eta_number >= 1:
                name_rows = query.with_entities(AcademiaStudent.quiz_name).distinct().all()
                matching_names = [
                    qname for (qname,) in name_rows
                    if self._extract_eta_number_from_name(qname) == eta_number
                ]
                if not matching_names:
                    return []
                query = AcademiaStudent.query.filter(
                    AcademiaStudent.programa == programa,
                    AcademiaStudent.quiz_name.in_(matching_names)
                )

            students = query.order_by(
                AcademiaStudent.percent_correct.desc(),
                AcademiaStudent.last_name.asc(),
                AcademiaStudent.first_name.asc()
            ).all()
            return [s.to_dict() for s in students]
        except Exception as e:
            print(f"Error ranking programa {programa}: {e}")
            return []

    def get_available_etas_by_programa(self, programa: str) -> List[Dict[str, Any]]:
        """Obtiene ETAs disponibles para un programa específico."""
        etas_list = []
        try:
            rows = db.session.query(
                AcademiaStudent.quiz_created,
                AcademiaStudent.quiz_name,
                db.func.count(AcademiaStudent.id)
            ).filter(
                AcademiaStudent.programa == programa,
                AcademiaStudent.quiz_created.isnot(None)
            ).group_by(
                AcademiaStudent.quiz_created, AcademiaStudent.quiz_name
            ).order_by(AcademiaStudent.quiz_created.asc()).all()

            for fecha_eta, quiz_name, estudiantes_count in rows:
                extracted_number = self._extract_eta_number_from_name(quiz_name)
                eta_number = extracted_number if extracted_number is not None else 0
                etas_list.append({
                    'eta_number': eta_number,
                    'fecha': fecha_eta,
                    'quiz_name': quiz_name,
                    'estudiantes_count': estudiantes_count,
                    'display_name': f"ETA {eta_number:02d} - {quiz_name[:30]}{'...' if len(str(quiz_name)) > 30 else ''}"
                })
            etas_list.sort(key=lambda x: x['eta_number'])
        except Exception as e:
            print(f"Error obteniendo ETAs para programa {programa}: {e}")
        return etas_list

    def debug_quiz_names(self):
        try:
            rows = db.session.query(
                AcademiaStudent.quiz_name,
                db.func.count(AcademiaStudent.id)
            ).group_by(AcademiaStudent.quiz_name).order_by(AcademiaStudent.quiz_name).all()
            print("\n" + "=" * 50)
            print("QuizNames únicos en la base de datos:")
            for quiz_name, count in rows:
                print(f"QuizName: '{quiz_name}' - Cantidad: {count}")
            print("=" * 50 + "\n")
        except Exception as e:
            print(f"Error en debug_quiz_names: {e}")
