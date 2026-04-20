"""
Configuración compartida para tests del sistema.

Los tests requieren una base de datos **PostgreSQL** vacía accesible.
Define ``TEST_DATABASE_URL`` en el entorno, por ejemplo::

    export TEST_DATABASE_URL=postgresql+psycopg://intranet:intranet@localhost:5432/intranet_test

Si la variable no está definida, la app lanzará ``RuntimeError`` al importar
``config`` (hard-fail intencional: la intranet es PostgreSQL-only).

Cada fixture ``db`` ejecuta ``DROP SCHEMA public CASCADE`` + ``CREATE SCHEMA
public`` para garantizar aislamiento entre tests, así que la BD indicada debe
estar dedicada a tests (no uses la misma que producción).
"""
import os
import sys

import pytest
from starlette.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _normalize_pg(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


_test_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("SQLALCHEMY_DATABASE_URI")
if _test_url:
    os.environ["SQLALCHEMY_DATABASE_URI"] = _normalize_pg(_test_url)

# Si no hay URI, ``config`` lanzará RuntimeError explicando cómo configurarla.
from app import create_app  # noqa: E402
from models import Usuario, Estudiante, Docente, db as _db  # noqa: E402


class TestConfig:
    """Configuración para tests (PostgreSQL aislado)."""

    TESTING = True
    APP_ENV = "development"
    SESSION_COOKIE_SECURE = False
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = os.environ["SQLALCHEMY_DATABASE_URI"]
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 5,
    }
    MAIL_SUPPRESS_SEND = True
    ACADEMIA_UPLOAD_FOLDER = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "academia", "uploads"
    )
    ACADEMIA_REPORTS_FOLDER = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "academia", "reports"
    )
    ACADEMIA_STATIC_FOLDER = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "academia", "static"
    )
    ACADEMIA_TEMPLATE_FOLDER = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "academia", "templates"
    )


@pytest.fixture(scope="session")
def app():
    """FastAPI app para toda la sesión de tests."""
    return create_app(TestConfig)


@pytest.fixture(scope="function")
def db(app):
    """Crea las tablas antes de cada test y las limpia después.

    En PostgreSQL usamos ``DROP SCHEMA public CASCADE`` + ``CREATE SCHEMA public``
    para garantizar un estado limpio incluso si quedan secuencias o datos
    huérfanos entre tests.
    """
    from sqlalchemy import text

    with _db.engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    _db.create_all()
    yield _db
    _db.session.rollback()
    _db.session.remove()
    with _db.engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture
def client(app, db):
    """Cliente HTTP (Starlette TestClient)."""
    # Starlette TestClient defaults follow_redirects=True; auth tests need first hop status.
    with TestClient(app, raise_server_exceptions=True, follow_redirects=False) as c:
        yield c


@pytest.fixture
def admin_user(db):
    """Crea un usuario administrador de prueba."""
    user = Usuario(
        username="admin_test",
        email="admin@test.com",
        nombre="Admin Test",
        rol="administrador",
        activo=True,
    )
    user.set_password("password123")
    _db.session.add(user)
    _db.session.commit()
    return user


@pytest.fixture
def normal_user(db):
    """Crea un usuario normal de prueba."""
    user = Usuario(
        username="user_test",
        email="user@test.com",
        nombre="User Test",
        rol="usuario",
        activo=True,
    )
    user.set_password("password123")
    _db.session.add(user)
    _db.session.commit()
    return user


@pytest.fixture
def inactive_user(db):
    """Crea un usuario inactivo de prueba."""
    user = Usuario(
        username="inactive_test",
        email="inactive@test.com",
        nombre="Inactive Test",
        rol="usuario",
        activo=False,
    )
    user.set_password("password123")
    _db.session.add(user)
    _db.session.commit()
    return user


@pytest.fixture
def sample_estudiante(db):
    """Crea un estudiante de prueba."""
    est = Estudiante(
        nivel="SECUNDARIA",
        grado="3ro",
        seccion="A",
        turno="Mañana",
        apellido_paterno_est="García",
        apellido_materno_est="López",
        nombres_est="Juan Carlos",
        dni_est="12345678",
        correo_est="juan@test.com",
        numero_celular_est="987654321",
        codigo_estudiante="EST202600001",
    )
    _db.session.add(est)
    _db.session.commit()
    return est


@pytest.fixture
def sample_docente(db):
    """Crea un docente de prueba."""
    doc = Docente(
        apellido_paterno="Pérez",
        apellido_materno="Sánchez",
        nombres="María Elena",
        dni="87654321",
        correo="maria@test.com",
        telefono="912345678",
        especialidad="Matemáticas",
        area_ensenanza="Ciencias",
    )
    _db.session.add(doc)
    _db.session.commit()
    return doc


@pytest.fixture
def logged_in_client(client, admin_user):
    """Cliente con sesión de administrador iniciada (POST /login)."""
    client.post(
        "/login",
        data={"username": admin_user.username, "password": "password123"},
        follow_redirects=False,
    )
    return client
