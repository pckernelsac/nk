"""Crea el primer usuario administrador cuando la BD está vacía (producción / primer despliegue)."""
from __future__ import annotations

import logging

from config import Config
from models import Usuario
from models.database import db


def ensure_bootstrap_admin(logger: logging.Logger | None = None) -> None:
    log = logger or logging.getLogger("uvicorn.error")
    if getattr(Config, "TESTING", False):
        return
    if Usuario.query.count() > 0:
        return
    pwd = getattr(Config, "ADMIN_BOOTSTRAP_PASSWORD", "") or ""
    if not pwd:
        log.warning(
            "La base de datos no tiene usuarios. Para crear el administrador inicial, define "
            "ADMIN_BOOTSTRAP_PASSWORD (y opcionalmente ADMIN_BOOTSTRAP_USERNAME) en el entorno "
            "y reinicia; o ejecuta en el servidor: python reset_admin_password.py"
        )
        return
    username = (getattr(Config, "ADMIN_BOOTSTRAP_USERNAME", None) or "admin").strip() or "admin"
    email = getattr(Config, "ADMIN_BOOTSTRAP_EMAIL", "") or ""
    if not email:
        email = f"{username}@escuela.local"
    user = Usuario(
        username=username,
        email=email,
        nombre="Administrador",
        rol="administrador",
        activo=True,
    )
    user.set_password(pwd)
    db.session.add(user)
    db.session.commit()
    log.info("Usuario administrador inicial creado (usuario=%s). Cambia la contraseña tras el primer acceso.", username)
