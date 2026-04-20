# config.py
import os
from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    try:
        v = os.environ.get(name)
        return int(v) if v not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _normalize_pg_uri(dsn: str) -> str:
    """Normaliza la URI de PostgreSQL al driver psycopg v3."""
    if dsn.startswith("postgres://"):
        return "postgresql+psycopg://" + dsn[len("postgres://"):]
    if dsn.startswith("postgresql://"):
        return "postgresql+psycopg://" + dsn[len("postgresql://"):]
    return dsn


def _build_database_uri() -> str:
    """Resuelve la URI PostgreSQL desde variables de entorno.

    Prioridad:
      1) ``SQLALCHEMY_DATABASE_URI``.
      2) ``DATABASE_URL`` (convención Heroku/Render/Railway; se normaliza a psycopg3).
      3) Variables separadas ``POSTGRES_HOST``/``POSTGRES_DB``/``POSTGRES_USER``.

    Si no hay ninguna configurada se lanza ``RuntimeError``: la app es
    PostgreSQL-only, no hay fallback a SQLite ni valores por defecto ocultos.
    """
    uri = os.environ.get("SQLALCHEMY_DATABASE_URI")
    if uri:
        return _normalize_pg_uri(uri)

    dsn = os.environ.get("DATABASE_URL")
    if dsn:
        return _normalize_pg_uri(dsn)

    pg_host = os.environ.get("POSTGRES_HOST")
    pg_db = os.environ.get("POSTGRES_DB")
    pg_user = os.environ.get("POSTGRES_USER")
    if pg_host and pg_db and pg_user:
        pg_pass = os.environ.get("POSTGRES_PASSWORD", "")
        pg_port = os.environ.get("POSTGRES_PORT", "5432")
        auth = f"{pg_user}:{pg_pass}" if pg_pass else pg_user
        return f"postgresql+psycopg://{auth}@{pg_host}:{pg_port}/{pg_db}"

    raise RuntimeError(
        "No se encontró configuración de base de datos PostgreSQL. "
        "Define SQLALCHEMY_DATABASE_URI o DATABASE_URL (postgresql+psycopg://user:pass@host:5432/db) "
        "o bien las variables POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER (y opcionalmente "
        "POSTGRES_PASSWORD, POSTGRES_PORT) en el entorno o en el archivo .env."
    )


def _build_engine_options() -> dict:
    """Opciones de pool/conexión para PostgreSQL (psycopg v3)."""
    return {
        'pool_size': _env_int('DB_POOL_SIZE', 10),
        'max_overflow': _env_int('DB_MAX_OVERFLOW', 20),
        'pool_pre_ping': True,
        'pool_recycle': _env_int('DB_POOL_RECYCLE', 1800),
        'pool_timeout': _env_int('DB_POOL_TIMEOUT', 30),
    }


class Config:
    """Configuración base de la aplicación"""
    # development | production — en production conviene SESSION_COOKIE_SECURE=true detrás de HTTPS
    APP_ENV = os.environ.get("APP_ENV", "development")
    SECRET_KEY = os.environ.get('SECRET_KEY', 'tu_clave_secreta')
    SESSION_COOKIE_SECURE = _env_bool(
        "SESSION_COOKIE_SECURE",
        default=(os.environ.get("APP_ENV", "development") == "production"),
    )
    SQLALCHEMY_DATABASE_URI = _build_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True

    # Opciones de motor para PostgreSQL (psycopg v3).
    SQLALCHEMY_ENGINE_OPTIONS = _build_engine_options()

    # Configuración de la aplicación
    APP_NAME = 'Sistema de Gestión Escolar'
    APP_VERSION = '2.0.0'

    # Paginación
    ITEMS_PER_PAGE = 10

    # Uploads
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    # Fotos de estudiantes
    STUDENT_PHOTOS_FOLDER = 'static/uploads/estudiantes'
    DEFAULT_STUDENT_PHOTO = 'static/img/default-student.png'

    # PDF
    PDF_TEMP_FOLDER = 'temp_pdfs'

    # Configuración de Carnets
    CARNET_CONFIG = {
        'ANCHO_MM': 62,
        'ALTO_MM': 90,
        'MARGEN_PAGINA_MM': 10,
        'ESPACIADO_MM': 1,
        'COLOR_PRIMARIO': '#5F2A5D',
        'LOGO_INSTITUCION': 'static/img/nk.png',
        'FOTO_DIAMETRO_MM': 25,
        'QR_TAMANIO_MM': 20,
    }

    # Primer administrador (solo si la tabla usuarios está vacía al arrancar)
    ADMIN_BOOTSTRAP_USERNAME = os.environ.get("ADMIN_BOOTSTRAP_USERNAME", "admin")
    ADMIN_BOOTSTRAP_PASSWORD = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "").strip()
    ADMIN_BOOTSTRAP_EMAIL = os.environ.get("ADMIN_BOOTSTRAP_EMAIL", "").strip()

    # Configuración de Email (SMTP; envío vía utils/email_helper)
    # Las credenciales se cargan desde el archivo .env
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = ('Sistema de Asistencias - Colegio NK Chambergo', os.environ.get('MAIL_USERNAME', 'asistencia@nkchambergo.edu.pe'))
    MAIL_MAX_EMAILS = None
    MAIL_ASCII_ATTACHMENTS = False

    # Opciones adicionales para SSL (útil si hay problemas de certificados)
    MAIL_SUPPRESS_SEND = os.environ.get('MAIL_SUPPRESS_SEND', 'False') == 'True'
    MAIL_DEBUG = os.environ.get('MAIL_DEBUG', 'False') == 'True'

    # Configuración de Academia (sistema integrado - misma base de datos PostgreSQL)
    ACADEMIA_UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'academia', 'uploads')
    ACADEMIA_REPORTS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'academia', 'reports')
    ACADEMIA_STATIC_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'academia', 'static')
    ACADEMIA_TEMPLATE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'academia', 'templates')
