# models/auditlog.py
from .database import db
from datetime import datetime


class AuditLog(db.Model):
    """Registro de auditoría de acciones del sistema"""
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Usuario que realizó la acción
    usuario_id = db.Column(db.Integer, nullable=False, index=True)
    usuario_username = db.Column(db.String(50), nullable=False)  # Denormalized
    usuario_rol = db.Column(db.String(20))  # Denormalized

    # Acción realizada
    accion = db.Column(db.String(50), nullable=False, index=True)  # CREATE, UPDATE, DELETE, LOGIN, LOGOUT, etc.
    modulo = db.Column(db.String(50), nullable=False, index=True)  # usuarios, estudiantes, pensiones, etc.
    descripcion = db.Column(db.Text)  # Descripción detallada de la acción

    # Datos afectados
    entidad_tipo = db.Column(db.String(50))  # Tipo de entidad afectada
    entidad_id = db.Column(db.Integer)  # ID de la entidad afectada

    # Datos de la petición
    ip_address = db.Column(db.String(45))  # IPv4 o IPv6
    user_agent = db.Column(db.String(255))

    # Cambios (opcional - JSON)
    datos_anteriores = db.Column(db.Text)  # JSON con datos antes del cambio
    datos_nuevos = db.Column(db.Text)  # JSON con datos después del cambio

    # Timestamp
    fecha_hora = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f'<AuditLog {self.usuario_username} - {self.accion} - {self.modulo}>'

    @staticmethod
    def registrar(tabla, registro_id, accion, usuario, detalles=None, request=None):
        """Registra una acción en el log de auditoría. Nunca lanza excepción."""
        try:
            ip = None
            ua = None
            if request is not None:
                try:
                    ip = request.client.host if request.client else None
                    ua = (request.headers.get("User-Agent") or "")[:255]
                except Exception:
                    pass

            log = AuditLog(
                usuario_id=0,
                usuario_username=str(usuario) if usuario else 'sistema',
                accion=str(accion),
                modulo=str(tabla),
                descripcion=str(detalles) if detalles else None,
                entidad_tipo=str(tabla),
                entidad_id=registro_id,
                ip_address=ip,
                user_agent=ua,
            )
            db.session.add(log)
            db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
