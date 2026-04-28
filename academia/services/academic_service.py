# -*- coding: utf-8 -*-
"""
Servicio para la gestión de áreas académicas y ponderaciones.
Usa SQLAlchemy ORM (models/academia.py).
"""

from typing import Any, Dict, List, Tuple, Optional
from sqlalchemy import or_
from models import db
from models.academia import AcademicArea, ExamenPreguntasConfig, QuestionWeight


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

    ACADEMIA_CUPOS = (20, 50, 80)
    # Cupos que NO usan area: una sola tabla compartida para todas las áreas
    # (academic_area_id IS NULL en question_weights).
    AREA_AGNOSTIC_CUPOS = (20,)

    @classmethod
    def normalize_cupo(cls, cupo: Optional[int], default: int = 80) -> int:
        """Normaliza un cupo a uno de los tamaños soportados de ACADEMIA (20/50/80).

        Si el valor recibido no coincide exactamente con un cupo soportado, redondea
        hacia el inmediatamente superior (≤20→20, 21..50→50, 51..→80). ``None`` o
        ``0`` retorna ``default``.
        """
        try:
            n = int(cupo) if cupo is not None else 0
        except (TypeError, ValueError):
            n = 0
        if n <= 0:
            return default
        if n in cls.ACADEMIA_CUPOS:
            return n
        for c in cls.ACADEMIA_CUPOS:
            if n <= c:
                return c
        return cls.ACADEMIA_CUPOS[-1]

    @classmethod
    def cupo_uses_area(cls, cupo: int) -> bool:
        """¿El cupo usa el desglose por área? (20 → no, 50/80 → sí)."""
        return cupo not in cls.AREA_AGNOSTIC_CUPOS

    def get_weights_by_area(
        self, area_id: int, cupo: Optional[int] = None
    ) -> Dict[Tuple[int, int], Tuple[str, str, float]]:
        """Ponderaciones ACADEMIA para un cupo dado (default 80).

        Si el cupo está en ``AREA_AGNOSTIC_CUPOS`` (p. ej. 20) ignora ``area_id``
        y devuelve el set único almacenado con ``academic_area_id IS NULL``.
        """
        target_cupo = self.normalize_cupo(cupo, default=80)
        weights_map = {}
        try:
            base = QuestionWeight.query.filter(
                or_(QuestionWeight.nivel == "ACADEMIA", QuestionWeight.nivel.is_(None)),
                or_(QuestionWeight.grado.is_(None), QuestionWeight.grado == ""),
                QuestionWeight.cupo == target_cupo,
            )
            if self.cupo_uses_area(target_cupo):
                base = base.filter(QuestionWeight.academic_area_id == area_id)
            else:
                base = base.filter(QuestionWeight.academic_area_id.is_(None))
            weights = base.order_by(QuestionWeight.question_start).all()

            for w in weights:
                weights_map[(w.question_start, w.question_end)] = (w.subject, w.level, w.weight)
        except Exception as e:
            print(f"Error al obtener ponderaciones para el área {area_id} (cupo {target_cupo}): {e}")
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
                        subject=subject, level=level, weight=weight,
                        nivel="ACADEMIA", cupo=50,
                    ))
                db.session.commit()
                print("Ponderaciones de preguntas inicializadas correctamente.")
            else:
                print("Las ponderaciones de preguntas ya existen o hubo un error al contar.")
        except Exception as e:
            db.session.rollback()
            print(f"Error al verificar/inicializar ponderaciones: {e}")

    def initialize_examen_preguntas_config(self) -> None:
        """Crea filas por defecto para el máximo de preguntas por contexto (si la tabla está vacía)."""
        try:
            if ExamenPreguntasConfig.query.count() > 0:
                return
            # Grados escolares: 20; 5.° sec. y academia: 80 por defecto (UNCP 2026, configurable en /academia/cupo-preguntas)
            defaults: List[Tuple[str, str, Optional[int], int]] = [
                ("INICIAL", "*", None, 20),
                ("PRIMARIA", "*", None, 20),
                ("SECUNDARIA", "*", None, 20),
                ("SECUNDARIA", "5", None, 80),
            ]
            for aid in range(1, 6):
                defaults.append(("ACADEMIA", "*", aid, 80))
            defaults.append(("ACADEMIA", "*", None, 80))
            for niv, gr, area, mx in defaults:
                db.session.add(
                    ExamenPreguntasConfig(
                        nivel=niv, grado=gr, academic_area_id=area, max_questions=mx
                    )
                )
            db.session.commit()
            print("Configuración de cupo de preguntas (examen_preguntas_config) inicializada.")
        except Exception as e:
            db.session.rollback()
            print(f"Error al inicializar examen_preguntas_config: {e}")

    def get_max_questions(
        self,
        nivel: str,
        grado: Optional[str] = None,
        academic_area_id: Optional[int] = None,
    ) -> int:
        """
        Resuelve el número máximo de preguntas (Stu1..N en CSV) según BD.
        - ACADEMIA: primero por academic_area_id, luego regla global (área NULL).
        - INICIAL/PRIMARIA/SECUNDARIA: primero (nivel, grado exacto), luego (nivel, '*').
        """
        n = (nivel or "ACADEMIA").strip().upper()
        if n not in ("INICIAL", "PRIMARIA", "SECUNDARIA", "ACADEMIA"):
            n = "ACADEMIA"
        g = (grado or "").strip()
        try:
            if n == "ACADEMIA":
                if academic_area_id is not None:
                    row = (
                        ExamenPreguntasConfig.query.filter_by(
                            nivel="ACADEMIA", grado="*", academic_area_id=int(academic_area_id)
                        ).first()
                    )
                    if row and row.max_questions > 0:
                        return int(row.max_questions)
                row = (
                    ExamenPreguntasConfig.query.filter_by(
                        nivel="ACADEMIA", grado="*", academic_area_id=None
                    ).first()
                )
                if row and row.max_questions > 0:
                    return int(row.max_questions)
                return 80
            if g:
                row = ExamenPreguntasConfig.query.filter_by(
                    nivel=n, grado=g, academic_area_id=None
                ).first()
                if row and row.max_questions > 0:
                    return int(row.max_questions)
            row = ExamenPreguntasConfig.query.filter_by(
                nivel=n, grado="*", academic_area_id=None
            ).first()
            if row and row.max_questions > 0:
                return int(row.max_questions)
            return 20
        except Exception as e:
            print(f"get_max_questions: {e}")
            return 80 if n == "ACADEMIA" else 20

    def list_examen_preguntas_configs(self) -> List[Dict[str, Any]]:
        try:
            rows = (
                ExamenPreguntasConfig.query.order_by(
                    ExamenPreguntasConfig.nivel,
                    ExamenPreguntasConfig.grado,
                    ExamenPreguntasConfig.academic_area_id,
                )
                .all()
            )
            return [r.to_dict() for r in rows]
        except Exception as e:
            print(f"list_examen_preguntas_configs: {e}")
            return []

    def replace_examen_preguntas_configs(self, rows: List[Dict[str, Any]]) -> Optional[str]:
        """Sustituye toda la tabla de cupos. Validado en aplicación (sin traslapes de clave lógica)."""
        if not rows:
            return "Debe quedar al menos una regla o use los valores por defecto."
        parsed: List[Tuple[str, str, Optional[int], int]] = []
        seen: set = set()
        for r in rows:
            n = (r.get("nivel") or "").strip().upper()
            if n not in ("INICIAL", "PRIMARIA", "SECUNDARIA", "ACADEMIA"):
                return f"Nivel no válido: {n}."
            g = (r.get("grado") or "*").strip() or "*"
            try:
                mx = int(r["max_questions"])
            except (KeyError, TypeError, ValueError):
                return "Cada fila requiere un máximo de preguntas (entero)."
            if mx < 1 or mx > 200:
                return "El máximo de preguntas debe estar entre 1 y 200."
            area_raw = r.get("academic_area_id")
            area: Optional[int] = None
            if area_raw not in (None, "", "None", "0", 0):
                try:
                    area = int(area_raw)
                except (TypeError, ValueError):
                    return "Área académica no válida."
            if n != "ACADEMIA" and area is not None:
                return "Solo el nivel ACADEMIA utiliza 'Área' en esta tabla."
            if n == "ACADEMIA" and g != "*":
                return "En ACADEMIA el grado debe ser '*' (el cupo aplica al área)."
            k = (n, g, area)
            if k in seen:
                return f"Fila duplicada: {n} / grado {g} / área {area}."
            seen.add(k)
            parsed.append((n, g, area, mx))
        try:
            ExamenPreguntasConfig.query.delete(synchronize_session=False)
            for n, g, area, mx in parsed:
                db.session.add(
                    ExamenPreguntasConfig(
                        nivel=n, grado=g, academic_area_id=area, max_questions=mx
                    )
                )
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return f"Error al guardar: {e}"
        return None

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

    @staticmethod
    def _student_cupo(student_dict: Dict[str, Any]) -> int:
        """Cupo del estudiante = nº real de entradas en pri_keys (auto-detectado)."""
        pk = student_dict.get('pri_keys') or ''
        if not pk:
            return 0
        return len([p for p in pk.split(',') if p is not None])

    def get_weights_for_student(self, student_dict: Dict[str, Any]) -> Dict[Tuple[int, int], Tuple[str, str, float]]:
        """Obtiene ponderaciones según el nivel del estudiante (ACADEMIA vs escolar).

        Para ACADEMIA, el cupo se infiere del largo real de ``pri_keys`` (20/50/80)
        para que un quiz viejo de 50 use sus pesos sin necesidad de reconfigurar.
        """
        nivel = student_dict.get('nivel') or 'ACADEMIA'
        if nivel == 'ACADEMIA':
            area_id = student_dict.get('academic_area_id', 1)
            cupo = self._student_cupo(student_dict)
            return self.get_weights_by_area(area_id, cupo=cupo or None)
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

    def list_question_weights_for_area(
        self, area_id: int, cupo: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Filas de ponderación ACADEMIA para un área y cupo (para edición manual)."""
        wmap = self.get_weights_by_area(area_id, cupo=cupo)
        out: List[Dict[str, Any]] = []
        for (q_start, q_end), (subject, level, weight) in sorted(
            wmap.items(), key=lambda x: (x[0][0], x[0][1])
        ):
            out.append(
                {
                    "question_start": q_start,
                    "question_end": q_end,
                    "subject": subject,
                    "level": level,
                    "weight": weight,
                }
            )
        return out

    def list_question_weights_for_nivel_grado(self, nivel: str, grado: str) -> List[Dict[str, Any]]:
        wmap = self.get_weights_by_nivel_grado(nivel, grado)
        out: List[Dict[str, Any]] = []
        for (q_start, q_end), (subject, level, weight) in sorted(
            wmap.items(), key=lambda x: (x[0][0], x[0][1])
        ):
            out.append(
                {
                    "question_start": q_start,
                    "question_end": q_end,
                    "subject": subject,
                    "level": level,
                    "weight": weight,
                }
            )
        return out

    @staticmethod
    def _validate_weight_rows(
        rows: List[Dict[str, Any]], max_q: int
    ) -> Optional[str]:
        """Valida rangos 1..max_q, sin traslapes, peso > 0. None si ok."""
        cap = min(max(int(max_q or 50), 1), 200)
        parsed: List[Tuple[int, int, str, str, float]] = []
        for r in rows:
            try:
                a = int(r["question_start"])
                b = int(r["question_end"])
            except (KeyError, TypeError, ValueError):
                return "Cada rango requiere números enteros de pregunta inicio y fin."
            if a < 1 or b < 1 or a > cap or b > cap or a > b:
                return f"Rango de preguntas inválido: {a}–{b} (límite 1–{cap} según cupo, inicio ≤ fin)."
            subj = (r.get("subject") or "").strip()
            lev = (r.get("level") or "").strip()
            if not subj or not lev:
                return "Asignatura y nivel (curso) no pueden estar vacíos en cada fila con datos."
            try:
                wv = float(r["weight"])
            except (KeyError, TypeError, ValueError):
                return "Cada fila requiere un peso numérico válido."
            if wv <= 0:
                return "El peso debe ser mayor que cero."
            parsed.append((a, b, subj, lev, wv))
        parsed.sort(key=lambda x: x[0])
        for i in range(1, len(parsed)):
            if parsed[i][0] <= parsed[i - 1][1]:
                return (
                    f"Los rangos de preguntas no deben superponerse: "
                    f"{parsed[i-1][0]}-{parsed[i-1][1]} y {parsed[i][0]}-{parsed[i][1]}"
                )
        return None

    def replace_weights_for_academic_area(
        self,
        area_id: int,
        rows: List[Dict[str, Any]],
        cupo: Optional[int] = None,
    ) -> Optional[str]:
        """
        Sustituye las ponderaciones de ACADEMIA del área para el cupo dado.
        Lista vacía elimina todas las ponderaciones del área (ACADEMIA) en ese cupo.
        Solo afecta el conjunto del cupo indicado: los demás cupos del área quedan intactos.

        Para cupos en ``AREA_AGNOSTIC_CUPOS`` (p. ej. 20) ``area_id`` se ignora
        y se opera sobre el set único con ``academic_area_id IS NULL``.

        Retorna mensaje de error o None si ok.
        """
        target_cupo = self.normalize_cupo(cupo, default=80)
        uses_area = self.cupo_uses_area(target_cupo)
        if uses_area and not db.session.get(AcademicArea, area_id):
            return "El área académica no existe."
        if rows:
            err = self._validate_weight_rows(rows, target_cupo)
            if err:
                return err
        try:
            q = QuestionWeight.query.filter(
                or_(QuestionWeight.nivel == "ACADEMIA", QuestionWeight.nivel.is_(None)),
                or_(QuestionWeight.grado.is_(None), QuestionWeight.grado == ""),
                QuestionWeight.cupo == target_cupo,
            )
            if uses_area:
                q = q.filter(QuestionWeight.academic_area_id == area_id)
            else:
                q = q.filter(QuestionWeight.academic_area_id.is_(None))
            q.delete(synchronize_session=False)

            for r in rows:
                db.session.add(
                    QuestionWeight(
                        academic_area_id=area_id if uses_area else None,
                        question_start=int(r["question_start"]),
                        question_end=int(r["question_end"]),
                        subject=(r.get("subject") or "").strip(),
                        level=(r.get("level") or "").strip(),
                        weight=float(r["weight"]),
                        nivel="ACADEMIA",
                        grado=None,
                        cupo=target_cupo,
                    )
                )
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return f"Error al guardar: {e}"
        return None

    def replace_weights_for_nivel_grado(
        self, nivel: str, grado: str, rows: List[Dict[str, Any]]
    ) -> Optional[str]:
        if nivel not in ("INICIAL", "PRIMARIA", "SECUNDARIA"):
            return "Nivel escolar no válido."
        gr = (grado or "").strip()
        if not gr:
            return "Debe indicar el grado."
        if rows:
            max_q = self.get_max_questions(nivel, gr, None)
            err = self._validate_weight_rows(rows, max_q)
            if err:
                return err
        try:
            (
                QuestionWeight.query.filter(
                    QuestionWeight.nivel == nivel, QuestionWeight.grado == gr
                ).delete(synchronize_session=False)
            )
            for r in rows:
                db.session.add(
                    QuestionWeight(
                        academic_area_id=None,
                        question_start=int(r["question_start"]),
                        question_end=int(r["question_end"]),
                        subject=(r.get("subject") or "").strip(),
                        level=(r.get("level") or "").strip(),
                        weight=float(r["weight"]),
                        nivel=nivel,
                        grado=gr,
                    )
                )
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return f"Error al guardar: {e}"
        return None
