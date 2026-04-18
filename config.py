# config.py
import os
from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


# Ruta absoluta a instance/escuela.db — única BD del sistema (ORM principal + Academia).
# Usar ruta absoluta para que no dependa del cwd desde donde se arranque la app.
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_INSTANCE_DIR = os.path.join(_BASE_DIR, 'instance')
os.makedirs(_INSTANCE_DIR, exist_ok=True)
_DB_PATH = os.path.join(_INSTANCE_DIR, 'escuela.db')


class Config:
    """Configuración base de la aplicación"""
    # development | production — en production conviene SESSION_COOKIE_SECURE=true detrás de HTTPS
    APP_ENV = os.environ.get("APP_ENV", "development")
    SECRET_KEY = os.environ.get('SECRET_KEY', 'tu_clave_secreta')
    SESSION_COOKIE_SECURE = _env_bool(
        "SESSION_COOKIE_SECURE",
        default=(os.environ.get("APP_ENV", "development") == "production"),
    )
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'SQLALCHEMY_DATABASE_URI',
        f'sqlite:///{_DB_PATH}',
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True

    # SQLite optimizado para concurrencia (20-100 usuarios)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'max_overflow': 10,
        'pool_pre_ping': True,
        'pool_recycle': 3600,
        'connect_args': {
            'timeout': 30,
            'check_same_thread': False,
        },
    }

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

    # Configuración de Academia (sistema integrado - misma base de datos)
    ACADEMIA_DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'escuela.db')
    ACADEMIA_UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'academia', 'uploads')
    ACADEMIA_REPORTS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'academia', 'reports')
    ACADEMIA_STATIC_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'academia', 'static')
    ACADEMIA_TEMPLATE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'academia', 'templates')
