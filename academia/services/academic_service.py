# -*- coding: utf-8 -*-
"""
Servicio para la gestión de áreas académicas y ponderaciones.
Usa SQLAlchemy ORM (models/academia.py).
"""

from typing import Any, Dict, List, Tuple, Optional
from models import db
from models.academia import AcademicArea, QuestionWeight


class AcademicService:
    """
    Servicio para gestionar áreas académicas, sus asignaturas y ponderaciones.
    """

    def get_academic_area_id_from_quiz_class(self, quiz_class: Optional[str]) -> int:
        if not quiz_class:
            return 1

        quiz_class_lower = str(quiz_class).strip().lower()
        if not quiz_class_lower:
            return 1

        # 1. Coincidencia por número inicial o nombre de área común
        if quiz_class_lower.startswith(('1', 'area i', 'área i')): return 1
        if quiz_class_lower.startswith(('2', 'area ii', 'área ii')): return 2
        if quiz_class_lower.startswith(('3', 'area iii', 'área iii')): return 3
        if quiz_class_lower.startswith(('4', 'area iv', 'área iv')): return 4
        if quiz_class_lower.startswith(('5', 'area v', 'área v')): return 5

        # 2. Coincidencia por prefijo almacenado en la base de datos
        try:
            areas = AcademicArea.query.filter(AcademicArea.quiz_class_prefix.isnot(None)).all()
            for area in areas:
                prefix = area.quiz_class_prefix.lower()
                if quiz_class_lower == prefix or quiz_class_lower.startswith(prefix + ' '):
                    return area.id
        except Exception as e:
            print(f"Error al buscar prefijos de área: {e}")

        # 3. Coincidencia por palabras clave
        keywords_map = {
            1: ['med', 'salud', 'enfer', 'farmac'],
            2: ['ing', 'arqui', 'civil', 'sistem'],
            3: ['admin', 'cont', 'econom', 'empre'],
            4: ['educ', 'social', 'derech', 'psico'],
            5: ['agrar', 'agro', 'forest', 'veteri']
        }
        for area_id, keywords in keywords_map.items():
            if any(keyword in quiz_class_lower for keyword in keywords):
                return area_id

        return 1

    def get_weights_by_area(self, area_id: int) -> Dict[Tuple[int, int], Tuple[str, str, float]]:
        weights_map = {}
        try:
            weights = QuestionWeight.query.filter_by(
                academic_area_id=area_id
            ).order_by(QuestionWeight.question_start).all()

            for w in weights:
                weights_map[(w.question_start, w.question_end)] = (w.subject, w.level, w.weight)
        except Exception as e:
            print(f"Error al obtener ponderaciones para el área {area_id}: {e}")
        return weights_map

    def get_academic_area_name(self, area_id: int) -> str:
        try:
            area = db.session.get(AcademicArea, area_id)
            if area:
                return area.name
        except Exception as e:
            print(f"Error al obtener nombre del área {area_id}: {e}")
        return "Área desconocida"

    def get_all_academic_areas(self) -> List[Dict[str, Any]]:
        try:
            areas = AcademicArea.query.order_by(AcademicArea.id).all()
            return [area.to_dict() for area in areas]
        except Exception as e:
            print(f"Error al obtener todas las áreas académicas: {e}")
            return []

    def initialize_academic_areas(self) -> None:
        try:
            if AcademicArea.query.count() == 0:
                print("Inicializando áreas académicas...")
                areas_data = [
                    (1, 'CIENCIAS DE LA SALUD', 'CS'),
                    (2, 'ARQUITECTURA E INGENIERÍAS', 'AI'),
                    (3, 'CIENCIAS ADMINISTRATIVAS, ECONÓMICAS Y CONTABLES', 'CA'),
                    (4, 'EDUCACIÓN Y CIENCIAS SOCIALES', 'ES'),
                    (5, 'CIENCIAS AGRARIAS', 'AG')
                ]
                for id_, name, prefix in areas_data:
                    db.session.add(AcademicArea(id=id_, name=name, quiz_class_prefix=prefix))
                db.session.commit()
                print("Áreas académicas inicializadas correctamente.")
            else:
                print("Las áreas académicas ya existen o hubo un error al contar.")
        except Exception as e:
            db.session.rollback()
            print(f"Error al verificar/inicializar áreas académicas: {e}")

    def initialize_question_weights(self) -> None:
        try:
            if QuestionWeight.query.count() == 0:
                print("Inicializando ponderaciones de preguntas...")
                all_weights = [
                    # Área 1 - CIENCIAS DE LA SALUD
                    (1, 1, 3, 'Aritmética', 'AVANZADO', 0.795), (1, 4, 6, 'Álgebra', 'AVANZADO', 0.765),
                    (1, 7, 8, 'Estadística y Probabilidades', 'AVANZADO', 0.815), (1, 9, 12, 'Comunicación', 'INTERMEDIO', 0.653),
                    (1, 13, 13, 'Biología', 'BÁSICO', 1.056), (1, 14, 16, 'Biología', 'INTERMEDIO', 1.246),
                    (1, 17, 19, 'Biología', 'AVANZADO', 1.531), (1, 20, 23, 'Química', 'AVANZADO', 1.212),
                    (1, 24, 26, 'Física', 'AVANZADO', 1.185), (1, 27, 28, 'Ecología', 'AVANZADO', 1.248),
                    (1, 29, 32, 'Psicología', 'AVANZADO', 0.815), (1, 33, 35, 'Aptitud Lógico Matemático', 'BÁSICO', 1.006),
                    (1, 36, 38, 'Aptitud Lógico Matemático', 'INTERMEDIO', 1.104), (1, 39, 41, 'Aptitud Lógico Matemático', 'AVANZADO', 1.208),
                    (1, 42, 44, 'Aptitud Comunicativa', 'INTERMEDIO', 0.797), (1, 45, 47, 'Aptitud Comunicativa', 'AVANZADO', 0.895),
                    (1, 48, 50, 'Aptitud Comunicativa (Inglés)', 'AVANZADO', 0.834),
                    # Área 2 - ARQUITECTURA E INGENIERÍAS
                    (2, 1, 2, 'Aritmética', 'INTERMEDIO', 1.048), (2, 3, 5, 'Aritmética', 'AVANZADO', 1.181),
                    (2, 6, 7, 'Álgebra', 'INTERMEDIO', 1.034), (2, 8, 10, 'Álgebra', 'AVANZADO', 1.176),
                    (2, 11, 14, 'Geometría', 'AVANZADO', 1.115), (2, 15, 17, 'Trigonometría', 'AVANZADO', 1.113),
                    (2, 18, 20, 'Estadística y Probabilidades', 'INTERMEDIO', 0.982), (2, 21, 23, 'Comunicación', 'INTERMEDIO', 0.842),
                    (2, 24, 26, 'Química', 'AVANZADO', 0.985), (2, 27, 30, 'Física', 'AVANZADO', 1.118),
                    (2, 31, 32, 'Ecología', 'AVANZADO', 0.675), (2, 33, 36, 'Aptitud Lógico Matemático', 'AVANZADO', 0.924),
                    (2, 37, 39, 'Aptitud Lógico Matemático', 'BÁSICO', 0.993), (2, 40, 42, 'Aptitud Lógico Matemático', 'INTERMEDIO', 1.108),
                    (2, 43, 44, 'Aptitud Comunicativa', 'AVANZADO', 0.806), (2, 45, 47, 'Aptitud Comunicativa', 'INTERMEDIO', 0.868),
                    (2, 48, 50, 'Aptitud Comunicativa (Inglés)', 'AVANZADO', 0.834),
                    # Área 3 - CIENCIAS ADMINISTRATIVAS, ECONÓMICAS Y CONTABLES
                    (3, 1, 4, 'Aritmética', 'INTERMEDIO', 1.191), (3, 5, 6, 'Álgebra', 'INTERMEDIO', 0.939),
                    (3, 7, 9, 'Álgebra', 'AVANZADO', 1.199), (3, 10, 13, 'Estadística y Probabilidades', 'INTERMEDIO', 1.135),
                    (3, 14, 17, 'Comunicación', 'INTERMEDIO', 0.985), (3, 18, 19, 'Ecología', 'AVANZADO', 0.615),
                    (3, 20, 21, 'Historia', 'AVANZADO', 0.668), (3, 22, 23, 'Geografía', 'BÁSICO', 0.768),
                    (3, 24, 27, 'Economía', 'INTERMEDIO', 1.268), (3, 28, 29, 'Psicología', 'AVANZADO', 0.893),
                    (3, 30, 32, 'Cívica', 'INTERMEDIO', 0.786), (3, 33, 34, 'Aptitud Lógico Matemático', 'BÁSICO', 0.979),
                    (3, 35, 37, 'Aptitud Lógico Matemático', 'INTERMEDIO', 1.031), (3, 38, 40, 'Aptitud Lógico Matemático', 'AVANZADO', 1.111),
                    (3, 41, 41, 'Aptitud Comunicativa', 'BÁSICO', 0.879), (3, 42, 44, 'Aptitud Comunicativa', 'INTERMEDIO', 0.991),
                    (3, 45, 47, 'Aptitud Comunicativa', 'AVANZADO', 1.075), (3, 48, 50, 'Aptitud Comunicativa (Inglés)', 'AVANZADO', 0.834),
                    # Área 4 - EDUCACIÓN Y CIENCIAS SOCIALES
                    (4, 1, 3, 'Aritmética', 'INTERMEDIO', 0.815), (4, 4, 6, 'Álgebra', 'INTERMEDIO', 0.805),
                    (4, 7, 8, 'Estadística y Probabilidades', 'INTERMEDIO', 0.925), (4, 9, 11, 'Comunicación', 'INTERMEDIO', 1.026),
                    (4, 12, 14, 'Comunicación', 'INTERMEDIO', 1.164), (4, 15, 16, 'Ecología', 'BÁSICO', 0.986),
                    (4, 17, 18, 'Biología', 'BÁSICO', 0.978), (4, 19, 21, 'Historia', 'BÁSICO', 1.098),
                    (4, 22, 23, 'Geografía', 'BÁSICO', 1.065), (4, 24, 25, 'Economía', 'BÁSICO', 1.003),
                    (4, 26, 28, 'Psicología', 'INTERMEDIO', 1.095), (4, 29, 30, 'Filosofía', 'INTERMEDIO', 1.095),
                    (4, 31, 32, 'Cívica', 'INTERMEDIO', 1.095), (4, 33, 35, 'Aptitud Lógico Matemático', 'BÁSICO', 0.871),
                    (4, 36, 38, 'Aptitud Lógico Matemático', 'INTERMEDIO', 1.119), (4, 39, 41, 'Aptitud Comunicativa', 'BÁSICO', 0.896),
                    (4, 42, 44, 'Aptitud Comunicativa', 'INTERMEDIO', 0.988), (4, 45, 47, 'Aptitud Comunicativa', 'AVANZADO', 1.101),
                    (4, 48, 50, 'Aptitud Comunicativa (Inglés)', 'AVANZADO', 0.924),
                    # Área 5 - CIENCIAS AGRARIAS
                    (5, 1, 3, 'Aritmética', 'BÁSICO', 1.125), (5, 4, 6, 'Álgebra', 'BÁSICO', 1.123),
                    (5, 7, 8, 'Geometría', 'BÁSICO', 1.121), (5, 9, 10, 'Trigonometría', 'BÁSICO', 1.118),
                    (5, 11, 12, 'Estadística y Probabilidades', 'BÁSICO', 1.076), (5, 13, 16, 'Comunicación', 'BÁSICO', 0.882),
                    (5, 17, 20, 'Biología', 'INTERMEDIO', 1.114), (5, 21, 23, 'Química', 'BÁSICO', 0.984),
                    (5, 24, 25, 'Física', 'BÁSICO', 0.981), (5, 26, 28, 'Ecología', 'INTERMEDIO', 1.151),
                    (5, 29, 30, 'Geografía', 'BÁSICO', 0.842), (5, 31, 32, 'Psicología', 'BÁSICO', 0.599),
                    (5, 33, 35, 'Aptitud Lógico Matemático', 'BÁSICO', 0.988), (5, 36, 38, 'Aptitud Lógico Matemático', 'INTERMEDIO', 1.096),
                    (5, 39, 40, 'Aptitud Lógico Matemático', 'AVANZADO', 1.214), (5, 41, 43, 'Aptitud Comunicativa', 'BÁSICO', 0.839),
                    (5, 44, 46, 'Aptitud Comunicativa', 'INTERMEDIO', 0.871), (5, 47, 47, 'Aptitud Comunicativa', 'AVANZADO', 1.093),
                    (5, 48, 50, 'Aptitud Comunicativa (Inglés)', 'AVANZADO', 0.83)
                ]
                for area_id, q_start, q_end, subject, level, weight in all_weights:
                    db.session.add(QuestionWeight(
                        academic_area_id=area_id, question_start=q_start, question_end=q_end,
                        subject=subject, level=level, weight=weight
                    ))
                db.session.commit()
                print("Ponderaciones de preguntas inicializadas correctamente.")
            else:
                print("Las ponderaciones de preguntas ya existen o hubo un error al contar.")
        except Exception as e:
            db.session.rollback()
            print(f"Error al verificar/inicializar ponderaciones: {e}")

    def get_area_id_for_nivel(self, quiz_class: Optional[str], nivel: str) -> Optional[int]:
        """Retorna academic_area_id para ACADEMIA, None para niveles escolares."""
        if nivel == 'ACADEMIA':
            return self.get_academic_area_id_from_quiz_class(quiz_class)
        return None

    def get_weights_by_nivel_grado(self, nivel: str, grado: str) -> Dict[Tuple[int, int], Tuple[str, str, float]]:
        """Obtiene ponderaciones para un nivel escolar + grado específico."""
        weights_map = {}
        try:
            weights = QuestionWeight.query.filter_by(
                nivel=nivel, grado=grado
            ).order_by(QuestionWeight.question_start).all()
            for w in weights:
                weights_map[(w.question_start, w.question_end)] = (w.subject, w.level, w.weight)
        except Exception as e:
            print(f"Error al obtener ponderaciones para {nivel} grado {grado}: {e}")
        return weights_map

    def get_weights_for_student(self, student_dict: Dict[str, Any]) -> Dict[Tuple[int, int], Tuple[str, str, float]]:
        """Obtiene ponderaciones según el nivel del estudiante (ACADEMIA vs escolar)."""
        nivel = student_dict.get('nivel') or 'ACADEMIA'
        if nivel == 'ACADEMIA':
            area_id = student_dict.get('academic_area_id', 1)
            return self.get_weights_by_area(area_id)
        else:
            grado = student_dict.get('quiz_class', '')
            return self.get_weights_by_nivel_grado(nivel, grado)

    def get_academic_area_by_id(self, area_id: int) -> Optional[Dict[str, Any]]:
        try:
            area = db.session.get(AcademicArea, area_id)
            return area.to_dict() if area else None
        except Exception as e:
            print(f"Error al obtener área académica por ID {area_id}: {e}")
            return None
