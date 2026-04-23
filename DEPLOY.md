# Despliegue a producción (PostgreSQL)

Esta app **solo** usa **PostgreSQL** (driver `psycopg` v3). No incluyas en el repositorio archivos `.db` locales ni el directorio `instance/`.

## Antes de cada despliegue

1. **Respaldo de la base de datos** en el servidor (dump de PostgreSQL) antes de actualizar código.
2. **Variables de entorno** en el host (nunca en Git): `SECRET_KEY`, `SQLALCHEMY_DATABASE_URI` o `DATABASE_URL` o `POSTGRES_*`, `APP_ENV=production`.
3. Revisar `.env.example` como plantilla; copiar a `.env` (o al panel del proveedor) con valores reales.

## Nuevo despliegue (pull / CI / Docker)

1. Obtener el código (`git pull` o build de la imagen).
2. Asegurar que las variables de conexión a PostgreSQL apuntan a la **misma** instancia de producción.
3. **Arrancar la aplicación** una vez: al iniciar, SQLAlchemy ejecuta `create_all()`. Las **tablas nuevas** (por ejemplo `examen_preguntas_config` u otras añadidas al código) se crean automáticamente si no existen. Las tablas y datos existentes no se borran.
4. Los servicios de Academia que inicializan datos por defecto (`academic_areas`, `question_weights`, `examen_preguntas_config` vacío) solo insertan filas **si** las tablas/criterios de vacío lo permiten: no pisan datos de producción que ya tengas.

## Docker Compose

- `docker compose up -d` levanta `intranet` + `postgres` en el mismo host. Ajusta `POSTGRES_*` en `.env` y **cambia las contraseñas por defecto** en un entorno real.
- En producción con PostgreSQL **gestionado** (RDS, Supabase, Railway, etc.), suele usarse **solo** el servicio `intranet` (o equivalente) y `DATABASE_URL` al motor remoto, sin el contenedor `postgres` de ejemplo.

## HTTPS y sesiones

- Con `APP_ENV=production` la cookie de sesión exige `Secure` por defecto. El `Dockerfile` ya usa Uvicorn con `--proxy-headers` para proxies (Nginx, Caddy, Cloudflare, etc.).

## Checklist post-deploy

- [ ] La app arranca sin errores de conexión a la BD.
- [ ] Inicio de sesión y una acción crítica (p. ej. listado de estudiantes) funcionan.
- [ ] (Opcional) Revisar que las rutas nuevas de Academia respondan: `/academia/cupo-preguntas`, `/academia/ponderaciones` (requieren rol administrador).

## Problemas frecuentes

- **“No se encontró configuración de base de datos”**: faltan `SQLALCHEMY_DATABASE_URI` / `DATABASE_URL` / `POSTGRES_*` en el entorno del proceso que ejecuta Uvicorn.
- **Migrations manuales**: hoy el proyecto se apoya en `create_all()` y en algunos `ALTER` puntuales en el arranque. Si el DBA aplica SQL manual, alinealo con `models/*.py`.
