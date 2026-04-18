# models/academia.py
"""
Modelos SQLAlchemy para el módulo de Academia.
Estas tablas reemplazan la base de datos separada academia/database.db
y ahora viven en la base de datos principal (instance/escuela.db).
"""

from .database import db
from datetime import datetime
from sqlalchemy import event


class AcademicArea(db.Model):
    """Áreas académicas (Ciencias de la Salud, Ingenierías, etc.)"""
    __tablename__ = 'academic_areas'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    quiz_class_prefix = db.Column(db.Text, nullable=False)

    # Relationships
    students = db.relationship('AcademiaStudent', backref='academic_area', lazy='dynamic')
    question_weights = db.relationship('QuestionWeight', backref='academic_area', lazy='dynamic')

    def __repr__(self):
        return f'<AcademicArea {self.id}: {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'quiz_class_prefix': self.quiz_class_prefix
        }


class AcademiaStudent(db.Model):
    """
    Resultados de evaluaciones/quizzes del módulo academia.
    Cada fila representa un intento de examen, NO un estudiante único.
    Un mismo student_id (DNI) puede tener múltiples registros (una por cada ETA).
    """
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    quiz_name = db.Column(db.Text)
    quiz_class = db.Column(db.Text)
    first_name = db.Column(db.Text)
    last_name = db.Column(db.Text)
    student_id = db.Column(db.Text)      # DNI del estudiante
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=True, index=True)
    custom_id = db.Column(db.Text)        # ID personalizado / carrera
    earned_points = db.Column(db.Float)
    possible_points = db.Column(db.Float)
    percent_correct = db.Column(db.Float)
    quiz_created = db.Column(db.Text)
    data_exported = db.Column(db.Text)
    key_version = db.Column(db.Text)
    responses = db.Column(db.Text)
    pri_keys = db.Column(db.Text)
    points = db.Column(db.Text)
    marks = db.Column(db.Text)
    academic_area_id = db.Column(db.Integer, db.ForeignKey('academic_areas.id'), default=1)
    programa = db.Column(db.Text, nullable=True)  # Programa/aula: INTENSIVO, SEMESTRAL, etc.
    nivel = db.Column(db.String(20), nullable=True, default='ACADEMIA')  # ACADEMIA, INICIAL, PRIMARIA, SECUNDARIA

    # Relación con Estudiante del sistema principal
    estudiante = db.relationship('Estudiante', backref=db.backref('etas', lazy='dynamic'))

    def __repr__(self):
        return f'<AcademiaStudent {self.id}: {self.first_name} {self.last_name}>'

    @property
    def formatted_quiz_date(self):
        """Formatea quiz_created a dd/mm/yyyy"""
        if not self.quiz_created:
            return None
        try:
            date_str = self.quiz_created.split(' ')[0]
            parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
            return parsed.strftime('%d/%m/%Y')
        except (ValueError, AttributeError):
            return self.quiz_created

    def to_dict(self, include_area_name=True):
        d = {
            'id': self.id,
            'quiz_name': self.quiz_name,
            'quiz_class': self.quiz_class,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'student_id': self.student_id,
            'estudiante_id': self.estudiante_id,
            'custom_id': self.custom_id,
            'earned_points': self.earned_points,
            'possible_points': self.possible_points,
            'percent_correct': self.percent_correct,
            'quiz_created': self.quiz_created,
            'data_exported': self.data_exported,
            'key_version': self.key_version,
            'responses': self.responses,
            'pri_keys': self.pri_keys,
            'points': self.points,
            'marks': self.marks,
            'academic_area_id': self.academic_area_id,
            'programa': self.programa,
            'nivel': self.nivel or 'ACADEMIA',
            'formatted_quiz_date': self.formatted_quiz_date,
        }
        if include_area_name:
            d['academic_area_name'] = self.academic_area.name if self.academic_area else 'Sin área'
        return d


class QuestionWeight(db.Model):
    """Ponderaciones de preguntas por área académica, materia y nivel."""
    __tablename__ = 'question_weights'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    academic_area_id = db.Column(db.Integer, db.ForeignKey('academic_areas.id'))
    question_start = db.Column(db.Integer)
    question_end = db.Column(db.Integer)
    subject = db.Column(db.Text, nullable=False)
    level = db.Column(db.Text, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    nivel = db.Column(db.String(20), nullable=True, default='ACADEMIA')  # ACADEMIA, INICIAL, PRIMARIA, SECUNDARIA
    grado = db.Column(db.String(20), nullable=True)  # Grado escolar: 3,4,5 (INI), 1-6 (PRIM), 1-5 (SEC)

    def __repr__(self):
        return f'<QuestionWeight {self.id}: {self.subject} ({self.level})>'
