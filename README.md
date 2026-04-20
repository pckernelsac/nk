# Intranet NK — Sistema de gestión escolar

Aplicación **FastAPI** con plantillas Jinja2, SQLAlchemy y **PostgreSQL** (driver `psycopg` v3). Incluye módulos de asistencia, pensiones y portal **Academia**.

## Requisitos

- Python 3.12+
- PostgreSQL 14+ accesible
- Dependencias: `pip install -r requirements.txt`

## Configuración

1. Copiar `.env.example` a `.env` y rellenar:
   - `SECRET_KEY` aleatoria.
   - `APP_ENV=production` en producción.
   - `SQLALCHEMY_DATABASE_URI=postgresql+psycopg://usuario:clave@host:5432/intranet`
     (o `DATABASE_URL`, o variables `POSTGRES_*`). **La app no arranca sin una URI PostgreSQL válida**.
2. **Primer usuario administrador:** `init_db.py` borra la base y solo sirve para desarrollo. En producción, si la BD está vacía, define `ADMIN_BOOTSTRAP_PASSWORD` (y opcionalmente `ADMIN_BOOTSTRAP_USERNAME`) antes del primer arranque; la app creará el admin automáticamente. Si ya levantaste sin eso, puedes ejecutar en el servidor: `python reset_admin_password.py --password "TuClave"`.
3. No subir `.env` al repositorio (ya está en `.gitignore`).
4. Credenciales opcionales (Firebase): colocar el JSON en `config/` y referenciar `FIREBASE_CREDENTIALS_PATH` en `.env`.

## Desarrollo

```bash
# 1) Levantar PostgreSQL (por ejemplo con Docker Compose)
docker compose up -d postgres

# 2) Arrancar la app
python app.py
```

Base inicial (desarrollo; recrea tablas): `python init_db.py`. Usuario por defecto: ver `init_db.py`.

## Producción

- **Variable crítica:** `SECRET_KEY` aleatoria y distinta de la de ejemplo.
- **HTTPS:** con `APP_ENV=production`, la cookie de sesión usa `Secure` por defecto. Tras un proxy, usar Uvicorn con `--proxy-headers` (ver `Dockerfile`) o el equivalente en tu proceso manager.
- **Datos persistentes:** PostgreSQL gestiona la BD; monta volúmenes para `static/uploads/`, `temp_pdfs/`, `academia/uploads/` y `academia/reports/` si aplica.

### Docker Compose

```bash
docker compose up -d
```

Arranca los servicios `intranet` y `postgres` con un volumen `postgres_data` para persistencia. Ajusta los valores `POSTGRES_*` en `.env`.

### Passenger

Usar `passenger_wsgi.py` como aplicación WSGI. Opcional: `PASSENGER_PYTHON` apuntando al Python del virtualenv.

## Base de datos

La URI PostgreSQL se resuelve en este orden (`config.py`):

1. `SQLALCHEMY_DATABASE_URI` (recomendada).
2. `DATABASE_URL` (convención Heroku/Render/Railway; acepta `postgres://` o `postgresql://`, se normaliza a `postgresql+psycopg://`).
3. Variables separadas `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`.

Opciones del pool (opcionales): `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE`, `DB_POOL_TIMEOUT`.

## Tests

Los tests también corren contra PostgreSQL. Define `TEST_DATABASE_URL` apuntando a una BD **dedicada** (cada test ejecuta `DROP SCHEMA public CASCADE`):

```bash
export TEST_DATABASE_URL=postgresql+psycopg://intranet:intranet@localhost:5432/intranet_test
pytest
```
