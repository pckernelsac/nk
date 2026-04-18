# utils/decorators.py
"""
Legacy Flask decorators were replaced by FastAPI dependencies.

Use in route handlers:
- ``Depends(get_current_user_id)`` with ``_user_id: int = Depends(get_current_user_id)``
  instead of ``@login_required``.
- ``Depends(require_roles("administrador"))`` instead of ``@admin_required``.
- ``Depends(require_roles("administrador", "contador"))`` instead of
  ``@admin_or_contador_required``.
- Portal estudiante: ``Depends(get_portal_estudiante_id)`` instead of
  ``@estudiante_login_required``.

See ``dependencies.py`` for implementations.
"""
from dependencies import get_current_user_id, get_portal_estudiante_id, require_roles

__all__ = [
    "get_current_user_id",
    "get_portal_estudiante_id",
    "require_roles",
]
