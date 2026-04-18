"""
Agrega columna academia_portal_password_hash a estudiantes (portal Academia).

La migración también se aplica automáticamente al arrancar la app (main.py lifespan).

Ejecutar manualmente si hace falta sin reiniciar:
    python migrations_manual/add_academia_portal_password_hash.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text

from config import Config
from models import db
from models.database import configure_engine

configure_engine(Config.SQLALCHEMY_DATABASE_URI)
import models  # noqa: F401 — registra modelos

db.create_all()

inspector = inspect(db.engine)
cols = [c["name"] for c in inspector.get_columns("estudiantes")]
if "academia_portal_password_hash" in cols:
    print("Columna academia_portal_password_hash ya existe.")
else:
    with db.engine.connect() as conn:
        conn.execute(
            text(
                "ALTER TABLE estudiantes ADD COLUMN academia_portal_password_hash VARCHAR(255)"
            )
        )
        conn.commit()
    print("Columna academia_portal_password_hash agregada.")
