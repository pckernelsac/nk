# routes/__init__.py — FastAPI routers (prefixes match former Flask blueprints)
from .academia import build_academia_routers
from .administracion import router as administracion_router
from .asistencias import router as asistencias_router
from .academico import router as academico_router
from .aulas import router as aulas_router
from .auth import router as auth_router
from .cursos import router as cursos_router
from .docentes import router as docentes_router
from .estudiantes import router as estudiantes_router
from .main import router as main_router
from .pagos import router as pagos_router
from .pensiones import router as pensiones_router
from .portal_estudiante import router as portal_estudiante_router

routers: list = [
    (auth_router, ""),
    (main_router, ""),
    (estudiantes_router, ""),
    (docentes_router, ""),
    (cursos_router, ""),
    (pensiones_router, "/pagos/pensiones"),
    (asistencias_router, "/asistencias"),
    (administracion_router, "/administracion"),
    (aulas_router, "/aulas"),
    (portal_estudiante_router, "/portal"),
    (academico_router, "/academico"),
    (pagos_router, "/pagos/generales"),
]

for _rt, _pfx in build_academia_routers():
    routers.append((_rt, _pfx))
