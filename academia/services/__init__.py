"""
Servicios del módulo de Academia.
Los servicios se inicializan desde routes/academia.py (bridge).
Todos usan SQLAlchemy ORM (models/academia.py).
"""

from academia.services.pdf_service import PDFService
from academia.services.student_service import StudentService
from academia.services.csv_service import CSVService
from academia.services.academic_service import AcademicService
from academia.services.student_auth_service import StudentAuthService
from academia.services.eta_analysis_service import ETAAnalysisService
from academia.services.eta_pdf_generator import ETAPDFGenerator
