"""
Entrada WSGI para hosts con Passenger (ASGI vía a2wsgi).
El directorio del proyecto se deduce de este archivo; no hace falta editar rutas fijas.
Opcional: variable PASSENGER_PYTHON=/ruta/al/venv/bin/python si el host no usa el venv correcto.
"""
import io
import os
import sys
from pathlib import Path

APP_DIR = str(Path(__file__).resolve().parent)
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_interp = os.environ.get("PASSENGER_PYTHON")
if _interp and os.path.isfile(_interp) and sys.executable != _interp:
    os.execl(_interp, _interp, *sys.argv)

from a2wsgi import ASGIMiddleware

from main import app as fastapi_app

application = ASGIMiddleware(fastapi_app)
