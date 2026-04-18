# routes/docentes.py
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from config import Config
from dependencies import get_current_user_id
from models import Docente, db
from template_helpers import add_flash, common_context, csrf_ok, templates

router = APIRouter()


@router.get("/docentes", name="docentes.list")
def list_docentes(request: Request, _user_id: int = Depends(get_current_user_id)):
    """Lista de docentes"""
    return templates.TemplateResponse("docentes.html", common_context(request))


@router.api_route("/form_docente", methods=["GET", "POST"], name="docentes.form")
async def form_docente(request: Request, _user_id: int = Depends(get_current_user_id)):
    """Formulario de registro de docente"""
    if request.method == "POST":
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(url=str(request.url_for("docentes.form")), status_code=303)
        try:
            docente = Docente(
                apellido_paterno=form.get("apellido_paterno"),
                apellido_materno=form.get("apellido_materno"),
                nombres=form.get("nombres"),
                dni=form.get("dni"),
                fecha_nacimiento=form.get("fecha_nacimiento"),
                genero=form.get("genero"),
                estado_civil=form.get("estado_civil"),
                correo=form.get("correo"),
                telefono=form.get("telefono"),
                nivel_educacion=form.get("nivel_educacion"),
                titulo_profesional=form.get("titulo_profesional"),
                institucion_educativa=form.get("institucion_educativa"),
                especialidad=form.get("especialidad"),
                area_ensenanza=form.get("area_ensenanza"),
                anos_experiencia=form.get("anos_experiencia"),
                direccion=form.get("direccion"),
                distrito=form.get("distrito"),
                provincia=form.get("provincia"),
                departamento=form.get("departamento"),
            )

            db.session.add(docente)
            db.session.commit()

            add_flash(request, "Docente registrado exitosamente", "success")
            return RedirectResponse(url=str(request.url_for("docentes.list")), status_code=303)

        except Exception as e:
            db.session.rollback()
            print(f"Error al registrar docente: {e}")
            add_flash(request, "Error al registrar docente", "error")

    return templates.TemplateResponse("form_docente.html", common_context(request))
