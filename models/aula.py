# models/aula.py
import hashlib
import unicodedata
from .database import db
from datetime import datetime


def _normalizar_grado_academia(grado: str) -> str:
    """Texto estable para hash: mayúsculas, sin marcas diacríticas, espacios colapsados."""
    if not grado:
        return ""
    t = unicodedata.normalize("NFKC", grado.strip())
    t = " ".join(t.split())
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t.upper()


def _fragmento_grado_academia(grado: str) -> str:
    """Código corto y casi siempre único por programa (evita colisiones entre nombres parecidos)."""
    norm = _normalizar_grado_academia(grado)
    digest = hashlib.sha1(norm.encode("utf-8")).hexdigest()[:6].upper()
    words = norm.split()
    rel = ""
    if words:
        rel = "".join(c for c in words[0] if c.isalnum())[:4]
        if len(words) > 1 and words[1]:
            rel += words[1][0] if words[1][0].isalnum() else ""
    rel = (rel or "AC")[:5]
    # Máx. ~12 chars para no exceder codigo VARCHAR(30) con sufijos de año/sección
    return f"{rel}{digest}"[:12]


class Aula(db.Model):
    """
    Modelo de Aula - Define aulas únicas por nivel+grado+seccion+turno+año
    Resuelve conflictos de estudiantes matriculados en múltiples turnos
    """
    __tablename__ = 'aulas'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Identificación del aula
    codigo = db.Column(db.String(30), nullable=False, index=True)  # Ej: "5S-A-M-26"
    nombre = db.Column(db.String(100), nullable=False)  # Ej: "5to Sec A - Mañana"

    # Características del aula
    nivel = db.Column(db.String(50), nullable=False)  # Primaria, Secundaria
    grado = db.Column(db.String(20), nullable=False)  # 1ro, 2do, 3ro, 4to, 5to, 6to
    seccion = db.Column(db.String(10), nullable=False)  # A, B, C, etc.
    turno = db.Column(db.String(20), nullable=False)  # Mañana, Tarde

    # Año escolar
    anio_escolar = db.Column(db.String(4), nullable=False, index=True)  # 2025, 2026, etc.

    # Capacidad y estado
    capacidad_maxima = db.Column(db.Integer, default=30)
    activo = db.Column(db.Boolean, default=True, nullable=False)

    # Auditoría
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    fecha_modificacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    usuario_creacion = db.Column(db.String(100))

    # Relaciones
    matriculas = db.relationship('Matricula', back_populates='aula', lazy='dynamic')

    # Índice compuesto para unicidad (nivel+grado+seccion+turno+año)
    __table_args__ = (
        db.UniqueConstraint('nivel', 'grado', 'seccion', 'turno', 'anio_escolar',
                           name='uix_aula_completa'),
        db.UniqueConstraint('codigo', 'anio_escolar', name='uix_codigo_anio'),
        db.Index('ix_aula_activo_anio', 'activo', 'anio_escolar'),
    )

    def __repr__(self):
        return f'<Aula {self.codigo} - {self.nombre}>'

    def estudiantes_matriculados_count(self):
        """Retorna el número de estudiantes matriculados activos"""
        return self.matriculas.filter_by(estado='activo').count()

    def tiene_capacidad(self):
        """Verifica si el aula tiene capacidad disponible"""
        return self.estudiantes_matriculados_count() < self.capacidad_maxima

    @staticmethod
    def generar_codigo(nivel, grado, seccion, turno, anio_escolar=''):
        """
        Genera código único del aula incluyendo año escolar.
        Ejemplos: 5S-A-M-26, 3P-B-T-26, INTAC-A-M-26
        """
        nivel_lower = nivel.lower()
        if 'primaria' in nivel_lower:
            nivel_abrev = 'P'
        elif 'inicial' in nivel_lower:
            nivel_abrev = 'I'
        elif 'academia' in nivel_lower:
            nivel_abrev = 'AC'
        else:
            nivel_abrev = 'S'  # Secundaria

        # Para ACADEMIA y grados con texto largo: usar abreviatura del texto
        # Para niveles escolares: extraer número del grado (1ro->1, 2do->2)
        if 'academia' in nivel_lower:
            # Antes: solo abreviaturas de palabras → programas distintos podían
            # colapsar al mismo código ("PROGRAMA UNO" vs "PROGRAMA DOS", etc.).
            # Ahora: prefijo legible + huella SHA-1 (6 hex) del texto completo normalizado.
            grado_num = _fragmento_grado_academia(grado)
        else:
            grado_num = ''.join(filter(str.isdigit, grado))
            if not grado_num:
                grado_clean = grado.upper().replace(' ', '')
                grado_num = grado_clean[:6] if len(grado_clean) > 6 else grado_clean

        # Abreviar turno: M=Mañana, T=Tarde
        turno_abrev = turno[0].upper()

        # Incluir últimos 2 dígitos del año
        anio_sufijo = str(anio_escolar)[-2:] if anio_escolar else ''

        if anio_sufijo:
            return f"{grado_num}{nivel_abrev}-{seccion.upper()}-{turno_abrev}-{anio_sufijo}"
        return f"{grado_num}{nivel_abrev}-{seccion.upper()}-{turno_abrev}"

    @staticmethod
    def generar_nombre(nivel, grado, seccion, turno):
        """
        Genera nombre descriptivo del aula
        Ejemplo: "5to Sec A - Mañana" / "Básico Acad A - Tarde"
        """
        nivel_lower = nivel.lower()
        if 'primaria' in nivel_lower:
            nivel_abrev = 'Prim'
        elif 'academia' in nivel_lower:
            nivel_abrev = 'Acad'
        else:
            nivel_abrev = 'Sec'

        return f"{grado} {nivel_abrev} {seccion.upper()} - {turno}"
