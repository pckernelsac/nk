# routes/auth.py
from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from models import Usuario, db
from template_helpers import add_flash, common_context, csrf_ok, templates
from utils.audit import registrar_auditoria

router = APIRouter()


@router.api_route("/login", methods=["GET", "POST"], name="auth.login")
async def login(request: Request):
    """Página de inicio de sesión"""
    if request.method == "POST":
        form = await request.form()

        def _field(name: str) -> str:
            v = form.get(name)
            if v is None:
                return ""
            if hasattr(v, "read"):
                return ""
            return str(v).strip()

        username = _field("username")
        password = _field("password")
        csrf_tok = _field("csrf_token")
        if not csrf_ok(request, csrf_tok):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(url=str(request.url_for("auth.login")), status_code=303)

        try:
            user = Usuario.query.filter_by(username=username).first()
            if user and user.check_password(password):
                if not user.activo:
                    add_flash(request, "Tu cuenta está desactivada. Contacta al administrador.", "error")
                    return RedirectResponse(url=str(request.url_for("auth.login")), status_code=303)
                request.session["user_id"] = user.id
                request.session["username"] = user.username
                request.session["rol"] = user.rol
                registrar_auditoria(
                    "LOGIN",
                    "auth",
                    "Inicio de sesión exitoso",
                    request=request,
                )
                add_flash(request, "Inicio de sesión exitoso", "success")
                return RedirectResponse(url=str(request.url_for("main.dashboard")), status_code=303)
            add_flash(request, "Usuario o contraseña incorrectos", "error")
        except Exception as e:
            print(f"Error en login: {e}")
            add_flash(request, "Error al iniciar sesión. Intente nuevamente.", "error")

    return templates.TemplateResponse("login.html", common_context(request))


@router.api_route("/register", methods=["GET", "POST"], name="auth.register")
async def register(request: Request):
    """Página de registro de usuarios"""
    if request.method == "POST":
        form = await request.form()
        if not csrf_ok(request, form.get("csrf_token")):
            add_flash(request, "Sesión de seguridad expirada. Intente de nuevo.", "error")
            return RedirectResponse(url=str(request.url_for("auth.register")), status_code=303)
        username = form.get("username")
        password = form.get("password")
        email = form.get("email")
        nombre = form.get("nombre")
        try:
            if Usuario.query.filter_by(username=username).first():
                add_flash(request, "El nombre de usuario ya está en uso", "error")
                return RedirectResponse(url=str(request.url_for("auth.register")), status_code=303)
            if Usuario.query.filter_by(email=email).first():
                add_flash(request, "El correo electrónico ya está en uso", "error")
                return RedirectResponse(url=str(request.url_for("auth.register")), status_code=303)
            new_user = Usuario(
                username=username,
                email=email,
                nombre=nombre,
                rol="usuario",
                activo=True,
            )
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            add_flash(request, "Registro exitoso! Ya puedes iniciar sesión", "success")
            return RedirectResponse(url=str(request.url_for("auth.login")), status_code=303)
        except Exception as e:
            db.session.rollback()
            print(f"Error en registro: {e}")
            add_flash(request, "Error al registrar usuario. Intente nuevamente.", "error")

    return templates.TemplateResponse("register.html", common_context(request))


@router.get("/logout", name="auth.logout")
def logout(request: Request):
    """Cerrar sesión"""
    if request.session.get("user_id"):
        registrar_auditoria("LOGOUT", "auth", "Cierre de sesión", request=request)
    request.session.clear()
    add_flash(request, "Has cerrado sesión exitosamente", "info")
    return RedirectResponse(url=str(request.url_for("auth.login")), status_code=303)
