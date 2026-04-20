"""
Restablece la contraseña del usuario 'admin' en la BD PostgreSQL configurada
(usa la misma URI que la app, resuelta desde ``config.Config``).

Uso (desde la raíz del proyecto, mismo cwd que al ejecutar python app.py):
    python reset_admin_password.py
    python reset_admin_password.py --password "MiNuevaClave123"
"""
from __future__ import annotations

import argparse
import os
import sys

# Raíz del proyecto en el path
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.chdir(ROOT)

from config import Config  # noqa: E402
from models.database import configure_engine  # noqa: E402
import models  # noqa: F401, E402 — registra modelos
from models import Usuario, db  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Restablecer contraseña de admin")
    parser.add_argument(
        "--password",
        default="Kevin@2025",
        help="Nueva contraseña (por defecto: Kevin@2025)",
    )
    parser.add_argument(
        "--username",
        default="admin",
        help="Usuario a actualizar (por defecto: admin)",
    )
    args = parser.parse_args()

    configure_engine(
        getattr(Config, "SQLALCHEMY_DATABASE_URI", None),
        engine_options=getattr(Config, "SQLALCHEMY_ENGINE_OPTIONS", None) or {},
    )

    uri = Config.SQLALCHEMY_DATABASE_URI
    print(f"Base de datos: {uri}")
    print(f"CWD: {os.getcwd()}")

    user = Usuario.query.filter_by(username=args.username).first()
    if not user:
        print(f"No existe el usuario '{args.username}'. Creando usuario administrador...")
        user = Usuario(
            username=args.username,
            email="admin@escuela.com",
            nombre="Administrador",
            rol="administrador",
            activo=True,
        )
        db.session.add(user)

    user.set_password(args.password)
    user.activo = True
    db.session.commit()
    print(f"Listo. Usuario '{args.username}' actualizado. Prueba iniciar sesión con esa contraseña.")


if __name__ == "__main__":
    main()
