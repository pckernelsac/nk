"""FastAPI dependencies (auth / roles) — replaces Flask decorators."""
from __future__ import annotations

from fastapi import HTTPException, Request

from template_helpers import add_flash


def get_current_user_id(request: Request) -> int:
    uid = request.session.get("user_id")
    if uid is None:
        add_flash(request, "Por favor inicia sesión para acceder", "warning")
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return int(uid)


def require_roles(*roles: str):
    """Depends(require_roles('administrador', 'contador'))"""

    def checker(request: Request) -> int:
        uid = get_current_user_id(request)
        role = request.session.get("rol", "usuario")
        if role not in roles:
            add_flash(request, "No tienes permisos para acceder a esta página", "error")
            raise HTTPException(status_code=403)
        return uid

    return checker


def get_portal_estudiante_id(request: Request) -> int:
    eid = request.session.get("estudiante_id")
    if eid is None:
        add_flash(request, "Por favor inicia sesión para acceder al portal", "warning")
        raise HTTPException(status_code=302, headers={"Location": "/portal/login"})
    return int(eid)
