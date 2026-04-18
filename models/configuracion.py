# models/configuracion.py
from .database import db
from datetime import datetime


class ConfiguracionSistema(db.Model):
    """Configuración general del sistema escolar"""
    __tablename__ = 'configuracion_sistema'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Datos institucionales
    nombre_institucion = db.Column(db.String(200), nullable=False)
    logo_url = db.Column(db.String(255))  # Path to uploaded logo
    ruc = db.Column(db.String(11))
    direccion = db.Column(db.String(255))
    telefono = db.Column(db.String(20))
    email = db.Column(db.String(100))
    sitio_web = db.Column(db.String(100))

    # Año académico
    anio_academico_actual = db.Column(db.String(10), nullable=False)
    fecha_inicio_anio = db.Column(db.Date)
    fecha_fin_anio = db.Column(db.Date)

    # Configuración regional
    zona_horaria = db.Column(db.String(50), default='America/Lima')
    idioma = db.Column(db.String(10), default='es')
    moneda = db.Column(db.String(10), default='PEN')

    # Metadata
    activo = db.Column(db.Boolean, default=True, nullable=False)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_modificacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    usuario_modificacion = db.Column(db.String(50))

    def __repr__(self):
        return f'<ConfiguracionSistema {self.nombre_institucion}>'
