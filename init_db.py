"""
Inicializa la base de datos PostgreSQL de la app FastAPI.

Ejecutar una vez desde la raíz del proyecto con ``SQLALCHEMY_DATABASE_URI``
(o ``DATABASE_URL`` / variables ``POSTGRES_*``) apuntando a una BD vacía::

    python init_db.py

ADVERTENCIA: el script ejecuta ``drop_all()`` antes de crear las tablas.
Solo úsalo en entornos de desarrollo o en una BD recién creada.

Credenciales por defecto: admin / Kevin@2025
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from config import Config  # noqa: E402
from models.database import configure_engine  # noqa: E402
import models  # noqa: F401, E402
from models import (  # noqa: E402
    db,
    Usuario,
    ConfiguracionPension,
    ConfiguracionSistema,
)


def init_database() -> None:
    configure_engine(
        getattr(Config, "SQLALCHEMY_DATABASE_URI", None),
        engine_options=getattr(Config, "SQLALCHEMY_ENGINE_OPTIONS", None) or {},
    )

    print(f"Usando BD: {Config.SQLALCHEMY_DATABASE_URI} (cwd={os.getcwd()})")

    db.drop_all()
    print("Tablas eliminadas (si existían)")

    db.create_all()
    print("Tablas creadas")

    admin = Usuario(
        username="admin",
        email="admin@escuela.com",
        nombre="Administrador",
        rol="administrador",
        activo=True,
    )
    admin.set_password("Kevin@2025")

    db.session.add(admin)
    db.session.commit()
    print("\nUsuario creado: admin / Kevin@2025 (rol: administrador)")

    config = ConfiguracionPension(
        nombre_institucion="Institución Educativa",
        ruc_institucion="12345678901",
        direccion_institucion="Av. Principal 123",
        telefono_institucion="987654321",
        anio_escolar=str(datetime.now().year),
        meses_activos="marzo,abril,mayo,junio,julio,agosto,septiembre,octubre,noviembre,diciembre",
        serie_recibo="001",
        numero_correlativo=1,
        activo=True,
    )
    db.session.add(config)
    db.session.commit()
    print(f"Configuración de pensiones por defecto ({datetime.now().year})")

    config_sistema = ConfiguracionSistema(
        nombre_institucion="Colegio y NK Chambergo",
        ruc="12345678901",
        direccion="Dirección del colegio",
        telefono="987654321",
        email="contacto@numeralk.edu.pe",
        sitio_web="www.numeralk.edu.pe",
        anio_academico_actual=str(datetime.now().year),
        zona_horaria="America/Lima",
        idioma="es",
        moneda="PEN",
        activo=True,
        usuario_modificacion="admin",
    )
    db.session.add(config_sistema)
    db.session.commit()
    print("Configuración del sistema creada")

    print("\nBase inicializada correctamente.")


if __name__ == "__main__":
    init_database()
