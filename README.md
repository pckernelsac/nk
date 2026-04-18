# Intranet NK — Sistema de gestión escolar

Aplicación **FastAPI** con plantillas Jinja2, SQLAlchemy y SQLite (`instance/escuela.db`). Incluye módulos de asistencia, pensiones y portal **Academia**.

## Requisitos

- Python 3.12+
- Dependencias: `pip install -r requirements.txt`

## Configuración

1. Copiar `.env.example` a `.env` y definir al menos `SECRET_KEY` y, en producción, `APP_ENV=production`.
2. **Primer usuario administrador:** `init_db.py` borra la base y solo sirve para desarrollo. En producción, si la BD está vacía, define `ADMIN_BOOTSTRAP_PASSWORD` (y opcionalmente `ADMIN_BOOTSTRAP_USERNAME`) antes del primer arranque; la app creará el admin automáticamente. Si ya levantaste sin eso, puedes ejecutar en el servidor: `python reset_admin_password.py --password "TuClave"`.
3. No subir `.env` ni la base de datos al repositorio (ya están en `.gitignore`).
4. Credenciales opcionales (Firebase): colocar el JSON en `config/` y referenciar `FIREBASE_CREDENTIALS_PATH` en `.env`.

## Desarrollo

```bash
python app.py
```

Base inicial (desarrollo; recrea tablas): `python init_db.py`. Usuario por defecto: ver `init_db.py`.

## Producción

- **Variable crítica:** `SECRET_KEY` aleatoria y distinta de la de ejemplo.
- **HTTPS:** con `APP_ENV=production`, la cookie de sesión usa `Secure` por defecto. Tras un proxy, usar Uvicorn con `--proxy-headers` (ver `Dockerfile`) o el equivalente en tu proceso manager.
- **Datos persistentes:** montar volúmenes para `instance/` (BD), `static/uploads/`, `temp_pdfs/`, `academia/uploads/` y `academia/reports/` si aplica.

### Docker (EasyPanel / VPS)

```bash
docker build -t intranet-nk .
docker run -p 8000:8000 --env-file .env -v nk_data:/app/instance -v nk_uploads:/app/static/uploads intranet-nk
```

Ajustar rutas de volumen según el panel.

### Passenger

Usar `passenger_wsgi.py` como aplicación WSGI. Opcional: `PASSENGER_PYTHON` apuntando al Python del virtualenv.

## Tests

```bash
pytest
```
