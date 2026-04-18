"""
Configuración compartida para tests del sistema.
Usa una base de datos SQLite en memoria para aislar los tests.
"""
import os
import sys

import pytest
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import Usuario, Estudiante, Docente, db as _db


class TestConfig:
    """Configuración para tests"""

    TESTING = True
    APP_ENV = "development"
    SESSION_COOKIE_SECURE = False
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    # Single shared connection so create_all, ORM, and TestClient see the same :memory: DB
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }
    MAIL_SUPPRESS_SEND = True
    ACADEMIA_DATABASE_PATH = ":memory:"
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
    """Crea las tablas antes de cada test y las limpia después."""
    _db.create_all()
    yield _db
    _db.session.rollback()
    _db.session.remove()
    _db.drop_all()


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
