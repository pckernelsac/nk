# Intranet NK — FastAPI + Uvicorn (producción)
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN mkdir -p static/uploads/estudiantes temp_pdfs academia/uploads academia/reports

# Datos persistentes — declarar volúmenes para que NO se borren al rebuild.
# El comando de arranque debe montar volúmenes nombrados o bind-mounts.
# La BD vive en PostgreSQL (servicio aparte), no en el contenedor.
VOLUME ["/app/static/uploads", "/app/academia/uploads", "/app/academia/reports"]

EXPOSE 8000

# Detrás de Nginx/Caddy/Traefik: --proxy-headers y forwarded-allow-ips para cookies HTTPS y URLs correctas
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
