# models/academico.py
from .database import db
from datetime import datetime


class PeriodoAcademico(db.Model):
    """Modelo para períodos académicos (bimestres, trimestres)"""
    __tablename__ = 'periodos_academicos'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Identificación del período
    nombre = db.Column(db.String(50), nullable=False)  # I Bimestre, II Bimestre, etc.
    numero = db.Column(db.Integer, nullable=False)  # 1, 2, 3, 4
    anio_escolar = db.Column(db.String(4), nullable=False, index=True)

    # Fechas del período
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)

    # Estado
    activo = db.Column(db.Boolean, default=True, nullable=False)

    # Auditoría
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    usuario_registro = db.Column(db.String(100))

    # Relaciones
    fast_tests = db.relationship('FastTest', back_populates='periodo', lazy='dynamic')

    # Índice único
    __table_args__ = (
        db.UniqueConstraint('numero', 'anio_escolar', name='uix_periodo_numero_anio'),
    )

    def __repr__(self):
        return f'<PeriodoAcademico {self.nombre} - {self.anio_escolar}>'


class Curso(db.Model):
    """Modelo para cursos/materias"""
    __tablename__ = 'cursos'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Identificación
    nombre = db.Column(db.String(100), nullable=False)  # Matemática, Comunicación, etc.
    codigo = db.Column(db.String(20), unique=True, nullable=False, index=True)

    # Descripción
    descripcion = db.Column(db.Text)

    # Nivel al que aplica
    nivel = db.Column(db.String(50))  # Primaria, Secundaria, Ambos

    # Estado
    activo = db.Column(db.Boolean, default=True, nullable=False)

    # Auditoría
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    usuario_registro = db.Column(db.String(100))

    # Relaciones
    asignaciones = db.relationship('DocenteCursoAula', back_populates='curso', lazy='dynamic')
    fast_tests = db.relationship('FastTest', back_populates='curso', lazy='dynamic')

    def __repr__(self):
        return f'<Curso {self.nombre}>'


class DocenteCursoAula(db.Model):
    """Modelo para asignación de docente a curso en un aula específica"""
    __tablename__ = 'docentes_cursos_aulas'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Relaciones
    docente_id = db.Column(db.Integer, db.ForeignKey('docentes.id'), nullable=False, index=True)
    curso_id = db.Column(db.Integer, db.ForeignKey('cursos.id'), nullable=False, index=True)
    aula_id = db.Column(db.Integer, db.ForeignKey('aulas.id'), nullable=False, index=True)

    # Datos desnormalizados
    docente_nombre = db.Column(db.String(200), nullable=False)
    curso_nombre = db.Column(db.String(100), nullable=False)
    aula_nombre = db.Column(db.String(100), nullable=False)

    # Año escolar
    anio_escolar = db.Column(db.String(4), nullable=False, index=True)

    # Estado
    activo = db.Column(db.Boolean, default=True, nullable=False)

    # Auditoría
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    usuario_registro = db.Column(db.String(100))

    # Relaciones
    docente = db.relationship('Docente', backref=db.backref('asignaciones', lazy='dynamic'))
    curso = db.relationship('Curso', back_populates='asignaciones')
    aula = db.relationship('Aula', backref=db.backref('asignaciones_curso', lazy='dynamic'))

    # Índice único: un docente por curso por aula por año
    __table_args__ = (
        db.UniqueConstraint('docente_id', 'curso_id', 'aula_id', 'anio_escolar',
                           name='uix_docente_curso_aula_anio'),
    )

    def __repr__(self):
        return f'<DocenteCursoAula {self.docente_nombre} - {self.curso_nombre} - {self.aula_nombre}>'


class FastTest(db.Model):
    """Modelo para evaluaciones rápidas (Fast Tests)"""
    __tablename__ = 'fast_tests'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Relaciones
    curso_id = db.Column(db.Integer, db.ForeignKey('cursos.id'), nullable=False, index=True)
    aula_id = db.Column(db.Integer, db.ForeignKey('aulas.id'), nullable=False, index=True)
    periodo_id = db.Column(db.Integer, db.ForeignKey('periodos_academicos.id'), nullable=True, index=True)
    docente_id = db.Column(db.Integer, db.ForeignKey('docentes.id'), index=True)

    # Datos desnormalizados
    curso_nombre = db.Column(db.String(100), nullable=False)
    aula_nombre = db.Column(db.String(100), nullable=False)
    periodo_nombre = db.Column(db.String(50), nullable=True)
    docente_nombre = db.Column(db.String(200))

    # Información del Fast Test
    titulo = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text)
    fecha_evaluacion = db.Column(db.Date, nullable=False)

    # Peso para el promedio (0.0 a 1.0)
    peso = db.Column(db.Float, default=1.0, nullable=False)

    # Nota máxima (escala vigesimal = 20)
    nota_maxima = db.Column(db.Float, default=20.0, nullable=False)

    # Año escolar
    anio_escolar = db.Column(db.String(4), nullable=False, index=True)

    # Estado
    estado = db.Column(db.String(20), default='abierto', nullable=False)  # abierto, cerrado
    fecha_cierre = db.Column(db.DateTime)

    # Estadísticas (calculadas al cerrar)
    total_estudiantes = db.Column(db.Integer, default=0)
    promedio_general = db.Column(db.Float)
    nota_maxima_obtenida = db.Column(db.Float)
    nota_minima_obtenida = db.Column(db.Float)

    # Auditoría
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    usuario_registro = db.Column(db.String(100))

    # Relaciones
    curso = db.relationship('Curso', back_populates='fast_tests')
    aula = db.relationship('Aula', backref=db.backref('fast_tests', lazy='dynamic'))
    periodo = db.relationship('PeriodoAcademico', back_populates='fast_tests')
    docente = db.relationship('Docente', backref=db.backref('fast_tests', lazy='dynamic'))
    notas = db.relationship('NotaFastTest', back_populates='fast_test', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<FastTest {self.titulo} - {self.aula_nombre}>'

    def calcular_estadisticas(self):
        """Calcula estadísticas del fast test"""
        notas_list = [n.nota for n in self.notas.all() if n.nota is not None]

        if notas_list:
            self.total_estudiantes = len(notas_list)
            self.promedio_general = sum(notas_list) / len(notas_list)
            self.nota_maxima_obtenida = max(notas_list)
            self.nota_minima_obtenida = min(notas_list)
        else:
            self.total_estudiantes = 0
            self.promedio_general = None
            self.nota_maxima_obtenida = None
            self.nota_minima_obtenida = None


class NotaFastTest(db.Model):
    """Modelo para notas de Fast Tests"""
    __tablename__ = 'notas_fast_test'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Relaciones
    fast_test_id = db.Column(db.Integer, db.ForeignKey('fast_tests.id'), nullable=False, index=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False, index=True)

    # Datos desnormalizados
    estudiante_nombre_completo = db.Column(db.String(200), nullable=False)
    estudiante_dni = db.Column(db.String(8))

    # Nota (escala vigesimal 0-20)
    nota = db.Column(db.Float)

    # Observaciones
    observaciones = db.Column(db.String(500))

    # Control de concurrencia
    version = db.Column(db.Integer, default=1, nullable=False)

    # Auditoría
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_modificacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    usuario_registro = db.Column(db.String(100))

    # Relaciones
    fast_test = db.relationship('FastTest', back_populates='notas')
    estudiante = db.relationship('Estudiante', backref=db.backref('notas_fast_test', lazy='dynamic'))

    # Índice único: una nota por estudiante por fast test
    __table_args__ = (
        db.UniqueConstraint('fast_test_id', 'estudiante_id', name='uix_nota_ft_estudiante'),
        db.Index('ix_nota_estudiante_ft', 'estudiante_id', 'fast_test_id'),
    )

    def __repr__(self):
        return f'<NotaFastTest {self.estudiante_nombre_completo} - {self.nota}>'

    def validar_nota(self):
        """Valida que la nota esté en el rango correcto"""
        if self.nota is not None:
            if self.nota < 0 or self.nota > 20:
                raise ValueError("La nota debe estar entre 0 y 20")
