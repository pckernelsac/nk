# models/pagos.py
"""
Modelos unificados para el sistema de pagos:
- Pensiones (pagos mensuales de matrícula)
- Pagos generales (otros conceptos: carnet, uniformes, etc.)
"""
from .database import db
from datetime import datetime


# ============================================================
# PENSIONES - Configuración, asignación y pagos mensuales
# ============================================================

class ConfiguracionPension(db.Model):
    """Configuración del sistema de pensiones"""
    __tablename__ = 'configuracion_pension'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Datos de la institución (para recibos)
    nombre_institucion = db.Column(db.String(200), nullable=False)
    ruc_institucion = db.Column(db.String(11))
    direccion_institucion = db.Column(db.String(200))
    telefono_institucion = db.Column(db.String(15))

    # Año escolar
    anio_escolar = db.Column(db.String(10), nullable=False)
    meses_activos = db.Column(db.String(200), nullable=False)  # CSV: "marzo,abril,mayo,..."

    # Numeración de recibos (pensiones)
    serie_recibo = db.Column(db.String(10), default='001')
    numero_correlativo = db.Column(db.Integer, default=1)

    # Numeración de recibos (pagos generales)
    serie_recibo_general = db.Column(db.String(10), default='002')
    numero_correlativo_general = db.Column(db.Integer, default=1)

    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    activo = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<ConfiguracionPension {self.anio_escolar}>'


class PensionEstudiante(db.Model):
    """Pensión asignada a un estudiante"""
    __tablename__ = 'pension_estudiante'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Referencia al estudiante (sin FK, patrón plano)
    estudiante_id = db.Column(db.Integer, nullable=False, index=True)
    estudiante_nombre_completo = db.Column(db.String(200))
    estudiante_dni = db.Column(db.String(8))
    estudiante_nivel = db.Column(db.String(50))
    estudiante_grado = db.Column(db.String(20))

    # Tipo de pensión
    tipo = db.Column(db.String(20), default='regular', nullable=False)  # 'regular' o 'academia'

    # Meses personalizados (solo para academia), CSV: "julio,agosto,septiembre,octubre"
    meses_activos = db.Column(db.String(200))

    # Monto de pensión personalizado
    monto_mensual = db.Column(db.Numeric(10, 2), nullable=False)
    anio_escolar = db.Column(db.String(10), nullable=False)

    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    activo = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<PensionEstudiante {self.estudiante_nombre_completo} - S/{self.monto_mensual}>'


class PagoPension(db.Model):
    """Registro de pago de pensión"""
    __tablename__ = 'pago_pension'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Número de recibo único
    numero_recibo = db.Column(db.String(20), unique=True, nullable=False, index=True)

    # Info del estudiante (desnormalizada)
    estudiante_id = db.Column(db.Integer, nullable=False, index=True)
    estudiante_nombre_completo = db.Column(db.String(200))
    estudiante_dni = db.Column(db.String(8))
    estudiante_nivel = db.Column(db.String(50))
    estudiante_grado = db.Column(db.String(20))

    # Info del pagador
    pagador_nombre = db.Column(db.String(200))
    pagador_dni = db.Column(db.String(8))
    pagador_relacion = db.Column(db.String(50))
    pagador_telefono = db.Column(db.String(15))

    # Detalles del pago
    mes_pago = db.Column(db.String(20), nullable=False)
    anio_pago = db.Column(db.String(10), nullable=False)
    monto_pagado = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_pago = db.Column(db.String(20), nullable=False)

    metodo_pago = db.Column(db.String(50), default='efectivo')
    numero_operacion = db.Column(db.String(50))

    # Estado
    estado = db.Column(db.String(20), default='pagado')
    observaciones = db.Column(db.String(500))

    # Metadata
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_registro = db.Column(db.String(50))

    # Anulación
    fecha_anulacion = db.Column(db.DateTime)
    usuario_anulacion = db.Column(db.String(50))
    motivo_anulacion = db.Column(db.String(500))

    def __repr__(self):
        return f'<PagoPension {self.numero_recibo} - S/{self.monto_pagado}>'


# ============================================================
# PLAN DE PAGOS DE PENSIONES (cronograma + cuotas)
# ============================================================

class CronogramaPagoPension(db.Model):
    """Plan de pagos: monto total acordado para varios meses, dividido en cuotas."""
    __tablename__ = 'cronograma_pago_pension'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    estudiante_id = db.Column(db.Integer, nullable=False, index=True)
    estudiante_nombre_completo = db.Column(db.String(200))
    anio_escolar = db.Column(db.String(10), nullable=False, index=True)

    meses_cubiertos = db.Column(db.String(200), nullable=False)  # CSV: "marzo,abril,mayo"
    monto_total = db.Column(db.Numeric(10, 2), nullable=False)
    numero_cuotas = db.Column(db.Integer, nullable=False)

    estado = db.Column(db.String(20), default='activo', nullable=False)  # activo, completado, anulado
    observaciones = db.Column(db.String(500))

    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    usuario_registro = db.Column(db.String(50))

    fecha_anulacion = db.Column(db.DateTime)
    usuario_anulacion = db.Column(db.String(50))
    motivo_anulacion = db.Column(db.String(500))

    cuotas = db.relationship(
        'CuotaPagoPension',
        back_populates='cronograma',
        order_by='CuotaPagoPension.numero_cuota',
        cascade='all, delete-orphan',
        lazy='joined',
    )

    def __repr__(self):
        return f'<CronogramaPagoPension est={self.estudiante_id} total=S/{self.monto_total}>'


class CuotaPagoPension(db.Model):
    """Cuota individual de un cronograma de pago."""
    __tablename__ = 'cuota_pago_pension'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    cronograma_id = db.Column(
        db.Integer, db.ForeignKey('cronograma_pago_pension.id'), nullable=False, index=True
    )
    numero_cuota = db.Column(db.Integer, nullable=False)
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_programada = db.Column(db.String(20), nullable=False)  # YYYY-MM-DD

    estado = db.Column(db.String(20), default='programada', nullable=False)  # programada, pagada, anulada

    fecha_pago_real = db.Column(db.String(20))
    metodo_pago = db.Column(db.String(50))
    numero_operacion = db.Column(db.String(50))
    usuario_cobro = db.Column(db.String(50))
    fecha_cobro = db.Column(db.DateTime)
    recibos_generados = db.Column(db.String(200))  # CSV de N° de recibo emitidos al cobrar

    cronograma = db.relationship('CronogramaPagoPension', back_populates='cuotas')

    def __repr__(self):
        return f'<CuotaPagoPension #{self.numero_cuota} S/{self.monto} {self.estado}>'


# ============================================================
# PAGOS GENERALES - Tipos, conceptos, obligaciones y pagos
# ============================================================

class TipoPago(db.Model):
    """Modelo para tipos de pago (conceptos de pago)"""
    __tablename__ = 'tipos_pago'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Identificación
    nombre = db.Column(db.String(100), nullable=False, unique=True, index=True)  # Carnet, Compendio, Uniformes, etc.
    codigo = db.Column(db.String(20), unique=True, nullable=False, index=True)  # CARNET, COMPENDIO, etc.

    # Descripción
    descripcion = db.Column(db.Text)

    # Categoría
    categoria = db.Column(db.String(50))  # Escolar, Administrativo, Eventos, etc.

    # Estado
    activo = db.Column(db.Boolean, default=True, nullable=False)

    # Auditoría
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    usuario_registro = db.Column(db.String(100))

    # Relaciones
    conceptos_ciclo = db.relationship('ConceptoPagoCiclo', back_populates='tipo_pago', lazy='dynamic')

    def __repr__(self):
        return f'<TipoPago {self.nombre}>'


class ConceptoPagoCiclo(db.Model):
    """Modelo para configuración de conceptos de pago por ciclo escolar"""
    __tablename__ = 'conceptos_pago_ciclo'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Relación con tipo de pago
    tipo_pago_id = db.Column(db.Integer, db.ForeignKey('tipos_pago.id'), nullable=False, index=True)

    # Datos desnormalizados
    tipo_pago_nombre = db.Column(db.String(100), nullable=False)

    # Año escolar
    anio_escolar = db.Column(db.String(4), nullable=False, index=True)

    # Configuración de monto
    monto = db.Column(db.Numeric(10, 2), nullable=False)  # Monto base del concepto

    # Aplicabilidad
    nivel = db.Column(db.String(50))  # Primaria, Secundaria, Ambos, null = todos
    grado = db.Column(db.String(50))  # 1ro, 2do, 3ro, etc., null = todos

    # Configuración de cuotas
    permite_cuotas = db.Column(db.Boolean, default=False, nullable=False)
    numero_cuotas_max = db.Column(db.Integer, default=1)  # Máximo número de cuotas permitidas

    # Estado
    activo = db.Column(db.Boolean, default=True, nullable=False)

    # Auditoría
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    usuario_registro = db.Column(db.String(100))

    # Relaciones
    tipo_pago = db.relationship('TipoPago', back_populates='conceptos_ciclo')
    obligaciones = db.relationship('ObligacionPagoEstudiante', back_populates='concepto', lazy='dynamic')

    # Índice único: un concepto por tipo por año
    __table_args__ = (
        db.UniqueConstraint('tipo_pago_id', 'anio_escolar', 'nivel', 'grado',
                           name='uix_concepto_tipo_anio_nivel_grado'),
    )

    def __repr__(self):
        return f'<ConceptoPagoCiclo {self.tipo_pago_nombre} - {self.anio_escolar}>'


class ObligacionPagoEstudiante(db.Model):
    """Modelo para obligaciones de pago asignadas a estudiantes"""
    __tablename__ = 'obligaciones_pago_estudiante'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Relaciones
    concepto_id = db.Column(db.Integer, db.ForeignKey('conceptos_pago_ciclo.id'), nullable=False, index=True)
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False, index=True)

    # Datos desnormalizados
    concepto_nombre = db.Column(db.String(100), nullable=False)
    estudiante_nombre_completo = db.Column(db.String(200), nullable=False)
    estudiante_dni = db.Column(db.String(8))

    # Año escolar
    anio_escolar = db.Column(db.String(4), nullable=False, index=True)

    # Montos
    monto_total = db.Column(db.Numeric(10, 2), nullable=False)  # Monto total a pagar
    monto_pagado = db.Column(db.Numeric(10, 2), default=0, nullable=False)  # Monto ya pagado
    monto_pendiente = db.Column(db.Numeric(10, 2), nullable=False)  # Monto pendiente

    # Cuotas
    numero_cuotas = db.Column(db.Integer, default=1, nullable=False)  # Número de cuotas acordadas
    cuotas_pagadas = db.Column(db.Integer, default=0, nullable=False)  # Cuotas ya pagadas

    # Estado
    estado = db.Column(db.String(20), default='pendiente', nullable=False)  # pendiente, pagado_parcial, pagado_total, anulado

    # Fecha límite de pago (opcional)
    fecha_vencimiento = db.Column(db.Date)

    # Control de concurrencia
    version = db.Column(db.Integer, default=1, nullable=False)

    # Auditoría
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_modificacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    usuario_registro = db.Column(db.String(100))

    # Relaciones
    concepto = db.relationship('ConceptoPagoCiclo', back_populates='obligaciones')
    estudiante = db.relationship('Estudiante', backref=db.backref('obligaciones_pago', lazy='dynamic'))
    pagos = db.relationship('PagoGeneral', back_populates='obligacion', lazy='dynamic')

    # Índice único: una obligación por concepto por estudiante por año
    __table_args__ = (
        db.UniqueConstraint('concepto_id', 'estudiante_id', 'anio_escolar',
                           name='uix_obligacion_concepto_estudiante_anio'),
        db.Index('ix_obligacion_estado_anio', 'estado', 'anio_escolar'),
    )

    def __repr__(self):
        return f'<ObligacionPagoEstudiante {self.estudiante_nombre_completo} - {self.concepto_nombre}>'

    def actualizar_estado(self):
        """Actualiza el estado basado en montos pagados"""
        if self.monto_pagado >= self.monto_total:
            self.estado = 'pagado_total'
            self.monto_pendiente = 0
        elif self.monto_pagado > 0:
            self.estado = 'pagado_parcial'
            self.monto_pendiente = self.monto_total - self.monto_pagado
        else:
            self.estado = 'pendiente'
            self.monto_pendiente = self.monto_total


class PagoGeneral(db.Model):
    """Modelo para registro de pagos generales (no pensiones)"""
    __tablename__ = 'pagos_generales'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Número de recibo único (Serie 002)
    numero_recibo = db.Column(db.String(20), unique=True, nullable=False, index=True)  # 002-0000001

    # Relación con obligación
    obligacion_id = db.Column(db.Integer, db.ForeignKey('obligaciones_pago_estudiante.id'), nullable=False, index=True)

    # Datos desnormalizados del estudiante
    estudiante_id = db.Column(db.Integer, db.ForeignKey('estudiantes.id'), nullable=False, index=True)
    estudiante_nombre_completo = db.Column(db.String(200), nullable=False)
    estudiante_dni = db.Column(db.String(8))
    estudiante_nivel = db.Column(db.String(50))
    estudiante_grado = db.Column(db.String(50))

    # Datos desnormalizados del apoderado
    apoderado_nombre = db.Column(db.String(200))
    apoderado_dni = db.Column(db.String(8))

    # Concepto
    concepto_nombre = db.Column(db.String(100), nullable=False)
    anio_escolar = db.Column(db.String(4), nullable=False, index=True)

    # Información del pago
    monto_pagado = db.Column(db.Numeric(10, 2), nullable=False)
    numero_cuota = db.Column(db.Integer)  # Si es pago en cuotas: 1, 2, 3...
    total_cuotas = db.Column(db.Integer)  # Total de cuotas acordadas

    # Fecha y forma de pago
    fecha_pago = db.Column(db.Date, nullable=False)
    forma_pago = db.Column(db.String(50), default='efectivo')  # efectivo, transferencia, tarjeta, etc.

    # Observaciones
    observaciones = db.Column(db.String(500))

    # Estado del pago
    estado = db.Column(db.String(20), default='pagado', nullable=False)  # pagado, anulado

    # Anulación
    fecha_anulacion = db.Column(db.DateTime)
    usuario_anulacion = db.Column(db.String(100))
    motivo_anulacion = db.Column(db.String(500))

    # Auditoría
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    usuario_registro = db.Column(db.String(100))

    # Relaciones
    obligacion = db.relationship('ObligacionPagoEstudiante', back_populates='pagos')
    estudiante = db.relationship('Estudiante', backref=db.backref('pagos_generales', lazy='dynamic'))

    def __repr__(self):
        return f'<PagoGeneral {self.numero_recibo} - {self.concepto_nombre}>'

    def anular(self, usuario, motivo):
        """Anula el pago"""
        self.estado = 'anulado'
        self.fecha_anulacion = datetime.utcnow()
        self.usuario_anulacion = usuario
        self.motivo_anulacion = motivo
