# models/asistencia.py
from .database import db
from datetime import datetime

class Asistencia(db.Model):
    """Modelo para registro de asistencias de estudiantes"""
    __tablename__ = 'asistencias'

    id = db.Column(db.Integer, primary_key=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False)
    tipo = db.Column(db.String(10), nullable=False, default='ENTRADA')  # 'ENTRADA' o 'SALIDA'
    fecha_hora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relación con estudiante
    estudiante = db.relationship('Estudiante', backref=db.backref('asistencias', lazy='dynamic'))

    # Índices para consultas frecuentes de escaneo y reportes
    __table_args__ = (
        db.Index('ix_asistencia_estudiante_tipo_fecha', 'estudiante_id', 'tipo', 'fecha_hora'),
        db.Index('ix_asistencia_fecha_hora', 'fecha_hora'),
    )

    def __repr__(self):
        return f'<Asistencia {self.id} - {self.tipo}>'

    @property
    def fecha_str(self):
        """Retorna la fecha formateada en formato DD/MM/YYYY"""
        return self.fecha_hora.strftime('%d/%m/%Y')

    @property
    def hora_str(self):
        """Retorna la hora formateada en formato HH:MM"""
        return self.fecha_hora.strftime('%H:%M')

    @property
    def fecha_hora_str(self):
        """Retorna fecha y hora formateadas"""
        return self.fecha_hora.strftime('%Y-%m-%d %H:%M:%S')


class RegistroAsistenciaAula(db.Model):
    """
    Modelo para registro diario de asistencia por aula
    Un registro por aula por día
    """
    __tablename__ = 'registros_asistencia_aula'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Relación con aula
    aula_id = db.Column(db.Integer, db.ForeignKey('aulas.id'), nullable=False, index=True)

    # Fecha del registro
    fecha = db.Column(db.Date, nullable=False, index=True)

    # Datos desnormalizados para performance
    aula_nombre = db.Column(db.String(100), nullable=False)
    aula_codigo = db.Column(db.String(20), nullable=False)
    anio_escolar = db.Column(db.String(4), nullable=False)

    # Estado del registro
    estado = db.Column(db.String(20), default='abierto', nullable=False)  # abierto, cerrado
    fecha_cierre = db.Column(db.DateTime)

    # Estadísticas (calculadas al cerrar)
    total_estudiantes = db.Column(db.Integer, default=0)
    total_presentes = db.Column(db.Integer, default=0)
    total_ausentes = db.Column(db.Integer, default=0)
    total_tardanzas = db.Column(db.Integer, default=0)
    total_justificados = db.Column(db.Integer, default=0)

    # Observaciones generales
    observaciones = db.Column(db.Text)

    # Auditoría
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    usuario_registro = db.Column(db.String(100))
    fecha_modificacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    usuario_modificacion = db.Column(db.String(100))

    # Relaciones
    aula = db.relationship('Aula', backref=db.backref('registros_asistencia', lazy='dynamic'))
    detalles = db.relationship('DetalleAsistenciaAula', back_populates='registro', lazy='dynamic', cascade='all, delete-orphan')

    # Índice único: no duplicar registro aula+fecha
    __table_args__ = (
        db.UniqueConstraint('aula_id', 'fecha', name='uix_registro_aula_fecha'),
        db.Index('ix_registro_fecha_estado', 'fecha', 'estado'),
    )

    def __repr__(self):
        return f'<RegistroAsistenciaAula {self.aula_codigo} - {self.fecha}>'

    def calcular_estadisticas(self):
        """Calcula las estadísticas de asistencia"""
        detalles = self.detalles.all()
        self.total_estudiantes = len(detalles)
        self.total_presentes = sum(1 for d in detalles if d.estado == 'presente')
        self.total_ausentes = sum(1 for d in detalles if d.estado == 'ausente')
        self.total_tardanzas = sum(1 for d in detalles if d.estado == 'tardanza')
        self.total_justificados = sum(1 for d in detalles if d.estado == 'justificado')

    def cerrar_registro(self, usuario):
        """Cierra el registro y calcula estadísticas"""
        self.calcular_estadisticas()
        self.estado = 'cerrado'
        self.fecha_cierre = datetime.utcnow()
        self.usuario_modificacion = usuario


class DetalleAsistenciaAula(db.Model):
    """
    Modelo para detalle de asistencia individual dentro de un registro de aula
    """
    __tablename__ = 'detalles_asistencia_aula'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Relación con registro de asistencia
    registro_aula_id = db.Column(db.Integer, db.ForeignKey('registros_asistencia_aula.id'), nullable=False, index=True)

    # Relación con estudiante
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False, index=True)

    # Datos desnormalizados
    estudiante_nombre_completo = db.Column(db.String(200), nullable=False)
    estudiante_dni = db.Column(db.String(8))

    # Estado de asistencia
    estado = db.Column(db.String(20), default='ausente', nullable=False)  # presente, ausente, tardanza, justificado

    # Hora de registro (para tardanzas)
    hora_llegada = db.Column(db.Time)

    # Observaciones individuales
    observaciones = db.Column(db.String(500))

    # Auditoría
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_registro = db.Column(db.String(100))

    # Relaciones
    registro = db.relationship('RegistroAsistenciaAula', back_populates='detalles')
    estudiante = db.relationship('Estudiante', backref=db.backref('detalles_asistencia', lazy='dynamic'))
    # Índice único: no duplicar estudiante en mismo registro
    __table_args__ = (
        db.UniqueConstraint('registro_aula_id', 'estudiante_id', name='uix_detalle_registro_estudiante'),
        db.Index('ix_detalle_estudiante_fecha', 'estudiante_id', 'registro_aula_id'),
    )

    def __repr__(self):
        return f'<DetalleAsistenciaAula {self.estudiante_nombre_completo} - {self.estado}>'

    def marcar_presente(self, hora=None, observaciones=None, usuario=None):
        """Marca al estudiante como presente"""
        self.estado = 'presente'
        self.hora_llegada = hora
        if observaciones:
            self.observaciones = observaciones
        if usuario:
            self.usuario_registro = usuario

    def marcar_ausente(self, observaciones=None, usuario=None):
        """Marca al estudiante como ausente"""
        self.estado = 'ausente'
        self.hora_llegada = None
        if observaciones:
            self.observaciones = observaciones
        if usuario:
            self.usuario_registro = usuario

    def marcar_tardanza(self, hora, observaciones=None, usuario=None):
        """Marca al estudiante con tardanza"""
        self.estado = 'tardanza'
        self.hora_llegada = hora
        if observaciones:
            self.observaciones = observaciones
        if usuario:
            self.usuario_registro = usuario

    def marcar_justificado(self, observaciones=None, usuario=None):
        """Marca la inasistencia como justificada"""
        self.estado = 'justificado'
        if observaciones:
            self.observaciones = observaciones
        if usuario:
            self.usuario_registro = usuario


class JustificacionInasistencia(db.Model):
    """
    Modelo para justificaciones de inasistencias (sistema de escáner QR)
    Vinculado directamente a estudiante + fecha de ausencia
    """
    __tablename__ = 'justificaciones_inasistencia'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Relación directa con estudiante y fecha de ausencia
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False, index=True)
    fecha = db.Column(db.Date, nullable=False, index=True)

    # Datos desnormalizados del estudiante
    estudiante_nombre_completo = db.Column(db.String(200), nullable=False)
    estudiante_dni = db.Column(db.String(8))

    # Datos del apoderado que justifica
    apoderado_nombre = db.Column(db.String(200), nullable=False)
    apoderado_dni = db.Column(db.String(8))
    apoderado_telefono = db.Column(db.String(15))
    apoderado_relacion = db.Column(db.String(50))  # padre, madre, tutor, etc.

    # Motivo de la inasistencia
    motivo = db.Column(db.Text, nullable=False)
    tipo_motivo = db.Column(db.String(50))  # enfermedad, familiar, emergencia, otros

    # Documentos de respaldo
    tiene_documento = db.Column(db.Boolean, default=False)
    tipo_documento = db.Column(db.String(100))
    archivo_documento = db.Column(db.String(255))

    # Estado de la justificación
    estado = db.Column(db.String(20), default='pendiente', nullable=False)  # pendiente, aprobada, rechazada
    fecha_aprobacion = db.Column(db.DateTime)
    usuario_aprobacion = db.Column(db.String(100))
    observaciones_aprobacion = db.Column(db.Text)

    # Auditoría
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    usuario_registro = db.Column(db.String(100))

    # Relaciones
    estudiante = db.relationship('Estudiante', backref=db.backref('justificaciones', lazy='dynamic'))

    # Índice único: no duplicar justificación para mismo estudiante+fecha
    __table_args__ = (
        db.UniqueConstraint('estudiante_id', 'fecha', name='uix_justificacion_estudiante_fecha'),
    )

    def __repr__(self):
        return f'<JustificacionInasistencia {self.id} - {self.estado}>'

    def aprobar(self, usuario, observaciones=None):
        """Aprueba la justificación"""
        self.estado = 'aprobada'
        self.fecha_aprobacion = datetime.utcnow()
        self.usuario_aprobacion = usuario
        if observaciones:
            self.observaciones_aprobacion = observaciones

    def rechazar(self, usuario, observaciones):
        """Rechaza la justificación"""
        self.estado = 'rechazada'
        self.fecha_aprobacion = datetime.utcnow()
        self.usuario_aprobacion = usuario
        self.observaciones_aprobacion = observaciones
