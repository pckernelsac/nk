"""
Módulo bridge para integración del sistema de Academia (FastAPI APIRouter).
Inicializa servicios y expone ``build_academia_routers()`` para ``routes/__init__.py``.
"""

from __future__ import annotations

import os

from academia.services.academic_service import AcademicService
from academia.services.csv_service import CSVService
from academia.services.eta_analysis_service import ETAAnalysisService
from academia.services.eta_pdf_generator import ETAPDFGenerator
from academia.services.pdf_service import PDFService
from academia.services.student_auth_service import StudentAuthService
from academia.services.student_service import StudentService

from academia.routes import eta_routes as eta_routes_module
from academia.routes.main_routes import init_routes as init_main_routes
from academia.routes.report_routes import init_routes as init_report_routes
from academia.routes.student_auth_routes import init_routes as init_student_auth_routes
from academia.routes.student_routes import init_routes as init_student_routes
from academia.routes.weights_routes import init_weights_routes

from config import Config

ACADEMIA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "academia")

_academia_services: dict | None = None


def init_academia_module() -> dict:
    """Crea servicios de academia una sola vez."""
    global _academia_services
    if _academia_services is not None:
        return _academia_services

    header_img_path = os.path.join(ACADEMIA_PATH, "static", "img", "encabezado.png")
    footer_img_path = os.path.join(ACADEMIA_PATH, "static", "img", "pie.png")

    academic_service = AcademicService()
    academic_service.initialize_academic_areas()
    academic_service.initialize_question_weights()
    academic_service.initialize_examen_preguntas_config()

    student_service = StudentService(academic_service)

    pdf_service = PDFService(
        academic_service,
        header_img_path=header_img_path,
        footer_img_path=footer_img_path,
    )

    csv_service = CSVService(
        Config.ACADEMIA_UPLOAD_FOLDER,
        student_service,
        academic_service,
    )

    student_auth_service = StudentAuthService()

    eta_analysis_service = ETAAnalysisService(academic_service, pdf_service)
    eta_pdf_generator = ETAPDFGenerator(pdf_service, eta_analysis_service)

    _academia_services = {
        "academic_service": academic_service,
        "student_service": student_service,
        "pdf_service": pdf_service,
        "csv_service": csv_service,
        "student_auth_service": student_auth_service,
        "eta_analysis_service": eta_analysis_service,
        "eta_pdf_generator": eta_pdf_generator,
    }
    print("Servicios de Academia inicializados correctamente")
    return _academia_services


def get_academia_services() -> dict | None:
    return _academia_services


def build_academia_routers():
    """Lista de ``(router, url_prefix)`` para ``include_router`` (equivalente a blueprints Flask)."""
    services = init_academia_module()

    main_router = init_main_routes(services["csv_service"], services["academic_service"])
    student_router = init_student_routes(services["student_service"], services["academic_service"])
    report_router = init_report_routes(
        services["student_service"], services["pdf_service"], services["academic_service"]
    )
    student_auth_router = init_student_auth_routes(
        services["student_auth_service"],
        services["student_service"],
        services["pdf_service"],
    )

    eta_routes_module.init_eta_routes(
        services["eta_analysis_service"],
        services["eta_pdf_generator"],
        services["student_service"],
    )
    eta_router = eta_routes_module.router

    weights_router = init_weights_routes(services["academic_service"])

    return [
        (main_router, "/academia"),
        (student_router, "/academia"),
        (report_router, "/academia"),
        (weights_router, "/academia"),
        (student_auth_router, "/academia/estudiante"),
        (eta_router, "/academia/eta"),
    ]
