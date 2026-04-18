# routes/portal_estudiante.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from config import Config
from dependencies import get_portal_estudiante_id
from models import Estudiante, db
from services.portal_estudiante_service import PortalEstudianteService
from template_helpers import add_flash, common_context, csrf_ok, templates

router = APIRouter()


def get_portal_service():
    return PortalEstudianteService


@router.api_route("/login", methods=["GET", "POST"], name="portal_estudiante.login")
async def login(request: Request):
    """Login para estudiantes en el portal"""
    if request.session.get("estudiante_id"):
        return RedirectResponse(
            url=str(request.url_for("portal_estudiante.dashboard")), status_code=303
        )

    if request.method == "POST":
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(
                url=str(request.url_for("portal_estudiante.login")), status_code=303
            )
        dni = (form.get("dni") or "").strip()
        codigo = (form.get("codigo") or "").strip()

        if not dni or not codigo:
            add_flash(request, "Complete todos los campos", "error")
            return templates.TemplateResponse(
                "portal_estudiante/login.html", common_context(request)
            )

        estudiante, error = get_portal_service().autenticar_estudiante(dni, codigo)

        if error:
            add_flash(request, error, "error")
            return templates.TemplateResponse(
                "portal_estudiante/login.html", common_context(request)
            )

        request.session["estudiante_id"] = estudiante.id
        request.session["estudiante_dni"] = estudiante.dni_est
        request.session["estudiante_nombre"] = estudiante.nombre_completo()

        add_flash(request, f"Bienvenido/a {estudiante.nombres_est}", "success")
        return RedirectResponse(
            url=str(request.url_for("portal_estudiante.dashboard")), status_code=303
        )

    return templates.TemplateResponse("portal_estudiante/login.html", common_context(request))


@router.get("/logout", name="portal_estudiante.logout")
def logout(request: Request):
    """Cerrar sesión del estudiante"""
    request.session.pop("estudiante_id", None)
    request.session.pop("estudiante_dni", None)
    request.session.pop("estudiante_nombre", None)
    add_flash(request, "Sesión cerrada exitosamente", "success")
    return RedirectResponse(url=str(request.url_for("portal_estudiante.login")), status_code=303)


@router.get("/dashboard", name="portal_estudiante.dashboard")
def dashboard(
    request: Request, _eid: int = Depends(get_portal_estudiante_id)
):
    """Dashboard del portal de estudiantes"""
    estudiante_id = request.session.get("estudiante_id")
    estudiante = db.session.get(Estudiante, estudiante_id) if estudiante_id else None

    if not estudiante:
        request.session.clear()
        add_flash(request, "Estudiante no encontrado", "error")
        return RedirectResponse(url=str(request.url_for("portal_estudiante.login")), status_code=303)

    datos = get_portal_service().obtener_datos_actualizables(estudiante)

    return templates.TemplateResponse(
        "portal_estudiante/dashboard.html",
        common_context(request, estudiante=estudiante, datos=datos),
    )


@router.api_route("/actualizar_datos", methods=["GET", "POST"], name="portal_estudiante.actualizar_datos")
async def actualizar_datos(
    request: Request, _eid: int = Depends(get_portal_estudiante_id)
):
    """Formulario para actualizar datos del estudiante"""
    estudiante_id = request.session.get("estudiante_id")
    estudiante = db.session.get(Estudiante, estudiante_id) if estudiante_id else None

    if not estudiante:
        request.session.clear()
        add_flash(request, "Estudiante no encontrado", "error")
        return RedirectResponse(url=str(request.url_for("portal_estudiante.login")), status_code=303)

    if request.method == "POST":
        form = await request.form()
        if getattr(Config, "WTF_CSRF_ENABLED", True) and not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(
                url=str(request.url_for("portal_estudiante.actualizar_datos")), status_code=303
            )
        version_actual = int(form.get("version") or 0)

        campos_actualizar = {
            "correo_est": (form.get("correo_est") or "").strip(),
            "numero_celular_est": (form.get("numero_celular_est") or "").strip(),
            "telefono_fijo_est": (form.get("telefono_fijo_est") or "").strip(),
            "direccion_est": (form.get("direccion_est") or "").strip(),
            "distrito_est": (form.get("distrito_est") or "").strip(),
            "provincia_est": (form.get("provincia_est") or "").strip(),
            "referencia_est": (form.get("referencia_est") or "").strip(),
            "celular_padre": (form.get("celular_padre") or "").strip(),
            "telefono_fijo_padre": (form.get("telefono_fijo_padre") or "").strip(),
            "correo_padre": (form.get("correo_padre") or "").strip(),
            "direccion_padre": (form.get("direccion_padre") or "").strip(),
            "distrito_padre": (form.get("distrito_padre") or "").strip(),
            "provincia_padre": (form.get("provincia_padre") or "").strip(),
            "celular_madre": (form.get("celular_madre") or "").strip(),
            "telefono_fijo_madre": (form.get("telefono_fijo_madre") or "").strip(),
            "correo_madre": (form.get("correo_madre") or "").strip(),
            "direccion_madre": (form.get("direccion_madre") or "").strip(),
            "distrito_madre": (form.get("distrito_madre") or "").strip(),
            "provincia_madre": (form.get("provincia_madre") or "").strip(),
            "celular_apoderado": (form.get("celular_apoderado") or "").strip(),
            "telefono_fijo_apoderado": (form.get("telefono_fijo_apoderado") or "").strip(),
            "correo_apoderado": (form.get("correo_apoderado") or "").strip(),
            "direccion_apoderado": (form.get("direccion_apoderado") or "").strip(),
            "distrito_apoderado": (form.get("distrito_apoderado") or "").strip(),
            "provincia_apoderado": (form.get("provincia_apoderado") or "").strip(),
        }

        _est, error = get_portal_service().actualizar_datos_estudiante(
            estudiante_id=estudiante_id,
            campos_dict=campos_actualizar,
            version_actual=version_actual,
        )

        if error:
            add_flash(request, error, "error")
            return RedirectResponse(
                url=str(request.url_for("portal_estudiante.actualizar_datos")), status_code=303
            )

        add_flash(request, "Datos actualizados exitosamente", "success")
        return RedirectResponse(
            url=str(request.url_for("portal_estudiante.dashboard")), status_code=303
        )

    datos = get_portal_service().obtener_datos_actualizables(estudiante)
    return templates.TemplateResponse(
        "portal_estudiante/actualizar_datos.html",
        common_context(request, estudiante=estudiante, datos=datos),
    )
