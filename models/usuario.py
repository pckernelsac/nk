# models/usuario.py
from .database import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


class Usuario(db.Model):
    """Modelo de Usuario del sistema"""
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    rol = db.Column(db.String(20), default='usuario', nullable=False)
    activo = db.Column(db.Boolean, default=True, nullable=False)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password):
        """Hashea y guarda la contraseña"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifica si la contraseña es correcta"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Usuario {self.username}>'
