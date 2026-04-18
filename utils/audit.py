# utils/audit.py
"""
Helper functions para registro de auditoría
"""
import json

from fastapi import Request

from models import db, AuditLog


def registrar_auditoria(
    accion,
    modulo,
    descripcion,
    entidad_tipo=None,
    entidad_id=None,
    datos_anteriores=None,
    datos_nuevos=None,
    *,
    request: Request | None = None,
):
    """
    Registra una acción en el log de auditoría

    Args:
        accion: CREATE, UPDATE, DELETE, LOGIN, LOGOUT, VIEW, etc.
        modulo: usuarios, estudiantes, pensiones, configuracion, etc.
        descripcion: Descripción legible de la acción
        entidad_tipo: Tipo de entidad afectada (opcional)
        entidad_id: ID de la entidad afectada (opcional)
        datos_anteriores: Diccionario con datos antes del cambio (opcional)
        datos_nuevos: Diccionario con datos después del cambio (opcional)
    """
    try:
        sess = request.session if request else {}
        client = request.client if request else None
        log = AuditLog(
            usuario_id=sess.get('user_id'),
            usuario_username=sess.get('username'),
            usuario_rol=sess.get('rol'),
            accion=accion,
            modulo=modulo,
            descripcion=descripcion,
            entidad_tipo=entidad_tipo,
            entidad_id=entidad_id,
            ip_address=client.host if client else None,
            user_agent=(request.headers.get('User-Agent', '')[:255] if request else ''),
            datos_anteriores=json.dumps(datos_anteriores, ensure_ascii=False) if datos_anteriores else None,
            datos_nuevos=json.dumps(datos_nuevos, ensure_ascii=False) if datos_nuevos else None
        )

        db.session.add(log)
        db.session.commit()

    except Exception as e:
        # No debe fallar la operación principal si falla el logging
        print(f"Error al registrar auditoría: {e}")
        db.session.rollback()
