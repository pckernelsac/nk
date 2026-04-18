# models/docente.py
from .database import db
from datetime import datetime


class Docente(db.Model):
    """Modelo de Docente"""
    __tablename__ = 'docentes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    apellido_paterno = db.Column(db.String(50), nullable=False)
    apellido_materno = db.Column(db.String(50), nullable=False)
    nombres = db.Column(db.String(100), nullable=False)
    dni = db.Column(db.String(8), unique=True, nullable=False, index=True)
    fecha_nacimiento = db.Column(db.String(20))
    genero = db.Column(db.String(20))
    estado_civil = db.Column(db.String(20))
    correo = db.Column(db.String(100))
    telefono = db.Column(db.String(15))
    nivel_educacion = db.Column(db.String(100))
    titulo_profesional = db.Column(db.String(200))
    institucion_educativa = db.Column(db.String(200))
    especialidad = db.Column(db.String(100))
    area_ensenanza = db.Column(db.String(100))
    anos_experiencia = db.Column(db.String(10))
    direccion = db.Column(db.String(200))
    distrito = db.Column(db.String(50))
    provincia = db.Column(db.String(50))
    departamento = db.Column(db.String(50))
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Docente {self.nombres} {self.apellido_paterno}>'
