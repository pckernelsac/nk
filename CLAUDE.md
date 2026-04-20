# CLAUDE.md

Guía para asistentes de código al trabajar en este repositorio.

## Visión general

Intranet escolar en **FastAPI** con plantillas **Jinja2**, sesiones vía **Starlette SessionMiddleware**, **SQLAlchemy** y base **PostgreSQL** (driver `psycopg` v3). Despliegue típico con **Passenger** usando `passenger_wsgi.py` (ASGI vía middleware) o Docker Compose.

La app es PostgreSQL-only: `config.Config` lanza `RuntimeError` al importar si no hay URI configurada (no hay fallback a SQLite ni BD embebida).

No hay Firebase/Firestore en el flujo principal de datos: el modelo persistido es relacional.

## Comandos

```bash
# Windows
venv\Scripts\activate

pip install -r requirements.txt

# Desarrollo
python app.py
```

`app.py` arranca **uvicorn** con reload apuntando a `main:app`. Exige una BD PostgreSQL accesible (ver variables en `.env.example`).

**BD inicial (desarrollo; borra y recrea tablas en la BD PostgreSQL destino):**

```bash
python init_db.py
```

Credenciales por defecto tras `init_db`: ver comentario en `init_db.py` (usuario `admin`).

**Producción (Passenger):** tocar `tmp/restart.txt` según el hosting.

## Estructura principal

| Archivo / carpeta | Rol |
|-------------------|-----|
| `main.py` | `create_app()`, lifespan, middlewares, inclusión de routers, estáticos |
| `app.py` | Punto de entrada local: `uvicorn.run("main:app", ...)` |
| `passenger_wsgi.py` | Entrada ASGI para Passenger |
| `routes/` | Routers FastAPI (prefijos equivalentes a los antiguos blueprints) |
| `models/` | Modelos SQLAlchemy; `models/database.py` motor, sesión y compat tipo `db.Model` / `Model.query` |
| `templates/` | Jinja2; `template_helpers.py` unifica `TemplateResponse` y utilidades de sesión/CSRF |
| `static/` | Activos globales; academia tiene estáticos bajo ruta dedicada |
| `config.py` | Configuración (SECRET_KEY, URI PostgreSQL, email SMTP, etc.) |

## Autenticación

- Sesión firmada en cookie (`SessionMiddleware`).
- Rutas protegidas con dependencias en `dependencies.py` (sustituyen decoradores legacy).
- Contraseñas con hash (werkzeug / helpers del modelo usuario).

## Base de datos

- URI resuelta en `config._build_database_uri` (orden): `SQLALCHEMY_DATABASE_URI` → `DATABASE_URL` (se normaliza a `postgresql+psycopg://`) → variables `POSTGRES_HOST`/`POSTGRES_DB`/`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_PORT`. Si ninguna está definida, `RuntimeError`.
- Opciones del pool en `config._build_engine_options` (tuning por env: `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE`, `DB_POOL_TIMEOUT`).
- Patrones: `Usuario.query.filter_by(...)`, `db.session.add/commit`, etc., vía capa de compat en `models/database.py`.
- Migración de datos desde un volcado legacy SQLite: `python migrate_sqlite_to_postgres.py --source sqlite:///ruta/escuela.db --target postgresql+psycopg://...`.
- Tests: definir `TEST_DATABASE_URL` (BD dedicada); cada fixture `db` hace `DROP SCHEMA public CASCADE` + `CREATE SCHEMA public`.

## Seguridad (formularios)

- CSRF: tokens de sesión y comprobación en rutas que lo requieran (no Flask-WTF).

## Módulo Academia

Integrado en la misma BD. `routes/academia.py` construye routers bajo prefijo `/academia`. Servicios en `academia/services/`, modelos académicos en `models/academia.py`. Tablas como `academic_areas` y `question_weights` deben existir antes de usar esas rutas; `create_app()` asegura creación de tablas al arrancar.

## Módulo pensiones

Rutas bajo `/pensiones/...` (configuración, dashboard, asignación, registro, historial, recibos PDF). Modelos: configuración de pensión, pensión por estudiante, pagos.

## Notas

- Varios ítems del menú pueden seguir apuntando a rutas no implementadas; revisar `routes/` antes de asumir cobertura.
- Tras cambios de dependencias, validar con `python -c "from main import app"`.
