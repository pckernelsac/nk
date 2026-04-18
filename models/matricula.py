# models/matricula.py
from .database import db
from datetime import datetime


class Matricula(db.Model):
    """
    Modelo de Matricula - Relación estudiante-aula
    Permite que un estudiante esté matriculado en múltiples aulas (multi-turno)
    """
    __tablename__ = 'matriculas'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Relaciones
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False, index=True)
    aula_id = db.Column(db.Integer, db.ForeignKey('aulas.id'), nullable=False, index=True)

    # Datos desnormalizados para performance (evitar joins en reportes)
    estudiante_nombre_completo = db.Column(db.String(200), nullable=False)
    estudiante_dni = db.Column(db.String(8), index=True)
    aula_nombre = db.Column(db.String(100), nullable=False)
    aula_codigo = db.Column(db.String(20), nullable=False)

    # Año escolar
    anio_escolar = db.Column(db.String(4), nullable=False, index=True)

    # Estado de la matrícula
    estado = db.Column(db.String(20), default='activo', nullable=False)  # activo, retirado, trasladado
    fecha_matricula = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_retiro = db.Column(db.DateTime)
    motivo_retiro = db.Column(db.String(200))

    # Observaciones
    observaciones = db.Column(db.Text)

    # Auditoría
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_modificacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    usuario_registro = db.Column(db.String(100))
    usuario_modificacion = db.Column(db.String(100))

    # Relaciones inversas
    estudiante = db.relationship('Estudiante', backref=db.backref('matriculas', lazy='dynamic'))
    aula = db.relationship('Aula', back_populates='matriculas')

    # Índices compuestos
    __table_args__ = (
        # No permitir matrículas duplicadas en misma aula-estudiante-año
        db.UniqueConstraint('estudiante_id', 'aula_id', 'anio_escolar',
                           name='uix_matricula_unica'),
        db.Index('ix_matricula_estado_anio', 'estado', 'anio_escolar'),
    )

    def __repr__(self):
        return f'<Matricula {self.estudiante_nombre_completo} en {self.aula_nombre}>'

    def retirar(self, motivo, usuario):
        """Retira al estudiante del aula"""
        self.estado = 'retirado'
        self.fecha_retiro = datetime.utcnow()
        self.motivo_retiro = motivo
        self.usuario_modificacion = usuario

    def activar(self, usuario):
        """Reactiva una matrícula retirada"""
        self.estado = 'activo'
        self.fecha_retiro = None
        self.motivo_retiro = None
        self.usuario_modificacion = usuario
