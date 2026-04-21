# models/estudiante.py
from .database import db
from datetime import datetime


class Estudiante(db.Model):
    """Modelo de Estudiante"""
    __tablename__ = 'estudiantes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    codigo_estudiante = db.Column(db.String(20), unique=True, index=True)

    # Información del Estudiante
    nivel = db.Column(db.String(50))
    grado = db.Column(db.String(20))
    seccion = db.Column(db.String(10))
    turno = db.Column(db.String(20))
    carrera_postula = db.Column(db.String(100))
    area_postula = db.Column(db.String(100))  # Área académica a la que postula
    apellido_paterno_est = db.Column(db.String(50))
    apellido_materno_est = db.Column(db.String(50))
    nombres_est = db.Column(db.String(100))
    dni_est = db.Column(db.String(8), index=True)
    correo_est = db.Column(db.String(100))
    fecha_nacimiento_est = db.Column(db.String(20))
    direccion_est = db.Column(db.String(200))
    distrito_est = db.Column(db.String(50))
    provincia_est = db.Column(db.String(50))
    referencia_est = db.Column(db.String(200))
    numero_celular_est = db.Column(db.String(15))
    telefono_fijo_est = db.Column(db.String(15))
    religion_est = db.Column(db.String(50))
    tiene_hermanos = db.Column(db.String(5))
    numero_hermanos = db.Column(db.String(5))
    tiene_computadora = db.Column(db.String(5))
    grupo_sanguineo = db.Column(db.String(10))
    es_alergica = db.Column(db.String(5))
    padece_enfermedad = db.Column(db.String(5))
    tiene_discapacidad = db.Column(db.String(5))

    # Información del Padre
    apellido_paterno_padre = db.Column(db.String(50))
    apellido_materno_padre = db.Column(db.String(50))
    nombres_padre = db.Column(db.String(100))
    dni_padre = db.Column(db.String(8))
    grado_instruccion_padre = db.Column(db.String(50))
    fecha_nacimiento_padre = db.Column(db.String(20))
    direccion_padre = db.Column(db.String(200))
    distrito_padre = db.Column(db.String(50))
    provincia_padre = db.Column(db.String(50))
    celular_padre = db.Column(db.String(15))
    telefono_fijo_padre = db.Column(db.String(15))
    ocupacion_padre = db.Column(db.String(100))
    centro_trabajo_padre = db.Column(db.String(200))
    telefono_trabajo_padre = db.Column(db.String(15))
    estado_civil_padre = db.Column(db.String(20))
    religion_padre = db.Column(db.String(50))
    vive_con_hijo_padre = db.Column(db.String(5))
    correo_padre = db.Column(db.String(100))

    # Información de la Madre
    apellido_paterno_madre = db.Column(db.String(50))
    apellido_materno_madre = db.Column(db.String(50))
    nombres_madre = db.Column(db.String(100))
    dni_madre = db.Column(db.String(8))
    grado_instruccion_madre = db.Column(db.String(50))
    fecha_nacimiento_madre = db.Column(db.String(20))
    direccion_madre = db.Column(db.String(200))
    distrito_madre = db.Column(db.String(50))
    provincia_madre = db.Column(db.String(50))
    celular_madre = db.Column(db.String(15))
    telefono_fijo_madre = db.Column(db.String(15))
    ocupacion_madre = db.Column(db.String(100))
    centro_trabajo_madre = db.Column(db.String(200))
    telefono_trabajo_madre = db.Column(db.String(15))
    estado_civil_madre = db.Column(db.String(20))
    religion_madre = db.Column(db.String(50))
    vive_con_hijo_madre = db.Column(db.String(5))
    correo_madre = db.Column(db.String(100))

    # Estado de Supervivencia
    padre_supervivencia = db.Column(db.String(20))
    madre_supervivencia = db.Column(db.String(20))

    # Información del Apoderado
    apellido_paterno_apoderado = db.Column(db.String(50))
    apellido_materno_apoderado = db.Column(db.String(50))
    nombres_apoderado = db.Column(db.String(100))
    dni_apoderado = db.Column(db.String(8))
    relacion_apoderado = db.Column(db.String(50))
    grado_instruccion_apoderado = db.Column(db.String(50))
    fecha_nacimiento_apoderado = db.Column(db.String(20))
    direccion_apoderado = db.Column(db.String(200))
    distrito_apoderado = db.Column(db.String(50))
    provincia_apoderado = db.Column(db.String(50))
    celular_apoderado = db.Column(db.String(15))
    telefono_fijo_apoderado = db.Column(db.String(15))
    ocupacion_apoderado = db.Column(db.String(100))
    centro_trabajo_apoderado = db.Column(db.String(200))
    telefono_trabajo_apoderado = db.Column(db.String(15))
    estado_civil_apoderado = db.Column(db.String(20))
    religion_apoderado = db.Column(db.String(50))
    vive_con_hijo_apoderado = db.Column(db.String(5))
    correo_apoderado = db.Column(db.String(100))

    # Foto del estudiante
    foto_perfil = db.Column(db.String(255))  # Ruta del archivo de foto

    # Control de concurrencia y auditoría
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_ultima_modificacion = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = db.Column(db.Integer, default=1, nullable=False)  # Control optimista de concurrencia
    ultimo_usuario_modificacion = db.Column(db.String(100))  # Usuario que hizo última modificación

    # Portal de Estudiantes
    puede_actualizar_datos = db.Column(db.Boolean, default=True, nullable=False)  # Permiso para actualizar datos
    ultima_actualizacion_portal = db.Column(db.DateTime)  # Última vez que actualizó desde el portal
    codigo_portal = db.Column(db.String(100))  # Código de acceso al portal (fecha_nacimiento hash)
    # Portal Academia (/academia/estudiante): si es NULL, la contraseña es el DNI (legado)
    academia_portal_password_hash = db.Column(db.String(255), nullable=True)

    @staticmethod
    def siguiente_codigo_estudiante_inicial() -> tuple[str, int]:
        """Retorna (prefijo, siguiente_número) según la BD.

        Útil para asignar códigos únicos en un mismo lote (p. ej. import Excel)
        sin commit entre filas: incrementar el número en memoria tras cada fila.

        Para un solo alta, usar ``generar_codigo_estudiante()``.
        """
        anio = datetime.utcnow().year
        prefijo = f"EST{anio}"
        ultimo = db.session.query(Estudiante).filter(
            Estudiante.codigo_estudiante.like(f"{prefijo}%")
        ).order_by(Estudiante.codigo_estudiante.desc()).first()
        if ultimo and ultimo.codigo_estudiante:
            try:
                ultimo_num = int(ultimo.codigo_estudiante[len(prefijo):])
            except ValueError:
                ultimo_num = 0
        else:
            ultimo_num = 0
        return prefijo, ultimo_num + 1

    @staticmethod
    def generar_codigo_estudiante():
        """Genera un código único de estudiante con formato EST202600001"""
        prefijo, nuevo_num = Estudiante.siguiente_codigo_estudiante_inicial()
        return f"{prefijo}{nuevo_num:05d}"

    def __repr__(self):
        return f'<Estudiante {self.nombres_est} {self.apellido_paterno_est}>'

    def generar_codigo_portal(self):
        """Genera código de acceso al portal basado en fecha de nacimiento"""
        if self.fecha_nacimiento_est:
            # Usar fecha de nacimiento como código (formato: DDMMYYYY)
            # En producción, considerar usar hash más seguro
            return self.fecha_nacimiento_est.replace('/', '').replace('-', '')
        return None

    def nombre_completo(self):
        """Retorna el nombre completo del estudiante"""
        return f"{self.apellido_paterno_est} {self.apellido_materno_est}, {self.nombres_est}"
