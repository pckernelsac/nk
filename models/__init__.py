# models/__init__.py
from .database import Base, configure_engine, db

# Importar todos los modelos aquí para que estén disponibles
from .usuario import Usuario
from .estudiante import Estudiante
from .docente import Docente
from .pagos import (ConfiguracionPension, PensionEstudiante, PagoPension,
                    CronogramaPagoPension, CuotaPagoPension,
                    TipoPago, ConceptoPagoCiclo, ObligacionPagoEstudiante, PagoGeneral)
from .asistencia import Asistencia, RegistroAsistenciaAula, DetalleAsistenciaAula, JustificacionInasistencia
from .configuracion import ConfiguracionSistema
from .auditlog import AuditLog
from .aula import Aula
from .matricula import Matricula
from .academico import PeriodoAcademico, Curso, DocenteCursoAula, FastTest, NotaFastTest
from .academia import AcademicArea, AcademiaStudent, ExamenPreguntasConfig, QuestionWeight

__all__ = [
    'Base',
    'configure_engine',
    'db',
    'Usuario',
    'Estudiante',
    'Docente',
    'ConfiguracionPension',
    'PensionEstudiante',
    'PagoPension',
    'CronogramaPagoPension',
    'CuotaPagoPension',
    'Asistencia',
    'RegistroAsistenciaAula',
    'DetalleAsistenciaAula',
    'JustificacionInasistencia',
    'ConfiguracionSistema',
    'AuditLog',
    'Aula',
    'Matricula',
    'PeriodoAcademico',
    'Curso',
    'DocenteCursoAula',
    'FastTest',
    'NotaFastTest',
    'TipoPago',
    'ConceptoPagoCiclo',
    'ObligacionPagoEstudiante',
    'PagoGeneral',
    'AcademicArea',
    'AcademiaStudent',
    'QuestionWeight',
    'ExamenPreguntasConfig',
]
