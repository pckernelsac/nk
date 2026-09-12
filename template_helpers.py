"""Jinja2 / session flash / CSRF helpers for FastAPI (replaces Flask-WTF patterns)."""
from __future__ import annotations

import secrets
from datetime import datetime
from itertools import combinations
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Request
from starlette.routing import NoMatchFound
from starlette.templating import Jinja2Templates

from config import Config

ROOT = Path(__file__).resolve().parent

# Starlette 1.x: TemplateResponse(request, name, context). El proyecto usa el orden
# antiguo (name, common_context(request)). Compat: si el 1er arg es str y el 2º un dict
# con request envuelto (_TemplateRequest), reinyectar el Request real.
_orig_template_response = Jinja2Templates.TemplateResponse


def _template_response_compat(self, *args, **kwargs):
    if (
        len(args) >= 2
        and isinstance(args[0], str)
        and isinstance(args[1], dict)
    ):
        name, context = args[0], args[1]
        req_proxy = context.get("request")
        real_request = getattr(req_proxy, "_request", None)
        if real_request is not None:
            return _orig_template_response(
                self, real_request, name, context, *args[2:], **kwargs
            )
    return _orig_template_response(self, *args, **kwargs)


Jinja2Templates.TemplateResponse = _template_response_compat  # type: ignore[assignment]

templates = Jinja2Templates(directory=str(ROOT / "templates"))
ACADEMIA_STATIC = "/academia/static"


def add_flash(request: Request, message: str, category: str = "message") -> None:
    bucket = request.session.setdefault("_flashes", [])
    bucket.append((category, message))


def get_flashed_messages(request: Request, with_categories: bool = False):
    raw = request.session.pop("_flashes", [])
    if with_categories:
        return raw
    return [m for _, m in raw]


def get_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def csrf_ok(request: Request, token: str | None) -> bool:
    if not getattr(Config, "WTF_CSRF_ENABLED", True):
        return True
    return bool(token and token == request.session.get("csrf_token"))


def _iter_named_routes(app):
    """Recorre ``app.routes`` (y sub-routers montados) produciendo rutas con nombre."""
    seen: set[int] = set()
    stack = list(getattr(app, "routes", []) or [])
    while stack:
        r = stack.pop()
        rid = id(r)
        if rid in seen:
            continue
        seen.add(rid)
        if getattr(r, "name", None):
            yield r
        # Versiones nuevas de FastAPI no aplanan los routers incluidos: los dejan
        # anidados detrás de ``router``/``original_router``, así que hay que bajar
        # por cualquiera de esos atributos y no sólo por ``app``/``routes``.
        for attr in ("routes", "app", "router", "original_router"):
            sub = getattr(r, attr, None)
            if sub is None or sub is r:
                continue
            if attr == "routes":
                stack.extend(sub or [])
            elif hasattr(sub, "routes"):
                stack.extend(getattr(sub, "routes", []) or [])


def _route_path_param_keys(app, name: str) -> set[str] | None:
    """Retorna los parámetros de path declarados por la ruta ``name`` (o None si no existe)."""
    for r in _iter_named_routes(app):
        if getattr(r, "name", None) != name:
            continue
        pc = getattr(r, "param_convertors", None)
        if isinstance(pc, dict):
            return set(pc.keys())
        return set()
    return None


def _url_for_con_query(request: Request, name: str, path_params: dict) -> str | None:
    """Construye la URL repartiendo ``path_params`` entre path y query string.

    Se prueba primero el reparto que declara la propia ruta y, si el escaneo de
    rutas no la encuentra (la estructura interna de ``app.routes`` cambia entre
    versiones de FastAPI), se prueban subconjuntos de mayor a menor tamaño. Así
    sólo se depende de ``request.url_for``, que funciona en cualquier versión.
    Devuelve ``None`` si ninguna combinación resuelve.
    """
    nombres = list(path_params)
    candidatos: list[tuple[str, ...]] = []
    keys = _route_path_param_keys(request.app, name)
    if keys is not None:
        candidatos.append(tuple(k for k in nombres if k in keys))
    for tam in range(len(nombres) - 1, -1, -1):
        for combo in combinations(nombres, tam):
            if combo not in candidatos:
                candidatos.append(combo)

    for combo in candidatos:
        en_path = set(combo)
        try:
            base = str(
                request.url_for(
                    name, **{k: v for k, v in path_params.items() if k in en_path}
                )
            )
        except NoMatchFound:
            continue
        extra = {
            k: v
            for k, v in path_params.items()
            if k not in en_path and v is not None and str(v) != ""
        }
        if extra:
            base += ("&" if "?" in base else "?") + urlencode(extra, doseq=True)
        return base
    return None


def url_for(request: Request, name: str, **path_params: str | int) -> str:
    if name == "static":
        return f"/static/{path_params['filename']}"
    if name in (
        "academia_report.static",
        "academia_student_auth.static",
        "academia_main.static",
        "academia_student.static",
    ):
        return f"{ACADEMIA_STATIC}/{path_params['filename']}"
    # Flask had two URL rules sharing endpoint ``administracion.usuarios_form``.
    if name == "administracion.usuarios_form":
        uid = path_params.get("usuario_id")
        if uid is not None:
            return str(request.url_for("administracion.usuarios_form_editar", usuario_id=uid))
        return str(request.url_for("administracion.usuarios_form_crear"))
    try:
        return str(request.url_for(name, **path_params))
    except NoMatchFound:
        # La ruta existe pero sobran kwargs: los que no sean parámetros de path
        # deben ir como query string (p. ej. ``aula_id`` en boleta_fast_test).
        resuelto = _url_for_con_query(request, name, path_params)
        if resuelto is None:
            raise
        return resuelto


class _TemplateG:
    """Minimal stand-in for Flask ``g`` used by academia and results templates."""

    current_user = None
    current_student = None


class _TemplateRequest:
    """Jinja ``request`` with Flask-compatible ``.args`` (query string)."""

    __slots__ = ("_request",)

    def __init__(self, request: Request):
        self._request = request

    @property
    def args(self):
        return self._request.query_params

    def __getattr__(self, name: str):
        return getattr(self._request, name)


class _SessionTemplateProxy:
    """Expose ``request.session`` to Jinja as ``session`` (``.get()`` and ``.attr``)."""

    def __init__(self, request: Request):
        self._request = request

    def get(self, key: str, default=None):
        return self._request.session.get(key, default)

    def __getitem__(self, key: str):
        return self._request.session[key]

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        return self._request.session.get(name)

    def __contains__(self, key: str) -> bool:
        return key in self._request.session


def template_g(request: Request) -> _TemplateG:
    g = _TemplateG()
    uid = request.session.get("user_id")
    if uid is not None:
        g.current_user = {
            "id": uid,
            "username": request.session.get("username"),
            "full_name": request.session.get("username"),
            "rol": request.session.get("rol"),
        }
    if request.session.get("student_authenticated"):
        g.current_student = {
            "id": request.session.get("student_id"),
            "student_id": request.session.get("student_id_number"),
            "name": request.session.get("student_name"),
        }
    return g


def common_context(request: Request, **extra):
    """Merge into every TemplateResponse context."""
    ctx = {
        "request": _TemplateRequest(request),
        "session": _SessionTemplateProxy(request),
        "g": template_g(request),
        "csrf_token": lambda: get_csrf_token(request),
        "get_flashed_messages": lambda with_categories=False: get_flashed_messages(
            request, with_categories=with_categories
        ),
        "url_for": lambda n, **kw: url_for(request, n, **kw),
        "current_year": datetime.now().year,
        **extra,
    }
    return ctx
