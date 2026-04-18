# utils/datetime_helper.py
"""
Helper para manejo de fechas y horas con zona horaria de Lima, Perú
"""
from datetime import datetime
import pytz

# Zona horaria de Lima, Perú
LIMA_TZ = pytz.timezone('America/Lima')


def now_lima():
    """
    Retorna la fecha y hora actual en zona horaria de Lima, Perú
    Retorna un datetime "naive" (sin timezone) para compatibilidad con SQLite

    Returns:
        datetime: Fecha y hora actual en Lima (GMT-5) sin timezone info
    """
    return datetime.now(LIMA_TZ).replace(tzinfo=None)


def utc_to_lima(utc_datetime):
    """
    Convierte una fecha/hora UTC a zona horaria de Lima

    Args:
        utc_datetime: datetime object en UTC

    Returns:
        datetime: datetime convertido a Lima timezone
    """
    if utc_datetime.tzinfo is None:
        # Si no tiene timezone, asumimos que es UTC
        utc_datetime = pytz.utc.localize(utc_datetime)
    return utc_datetime.astimezone(LIMA_TZ)


def lima_to_utc(lima_datetime):
    """
    Convierte una fecha/hora de Lima a UTC

    Args:
        lima_datetime: datetime object en Lima timezone

    Returns:
        datetime: datetime convertido a UTC
    """
    if lima_datetime.tzinfo is None:
        # Si no tiene timezone, asumimos que es Lima
        lima_datetime = LIMA_TZ.localize(lima_datetime)
    return lima_datetime.astimezone(pytz.utc)
