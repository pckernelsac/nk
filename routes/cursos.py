# routes/cursos.py
from fastapi import APIRouter, Depends, Request

from dependencies import get_current_user_id
from template_helpers import common_context, templates

router = APIRouter()


@router.get("/cursos", name="cursos.list")
def list_cursos(request: Request, _user_id: int = Depends(get_current_user_id)):
    """Lista de cursos"""
    return templates.TemplateResponse("cursos.html", common_context(request))
