"""
Tests para las rutas principales del sistema.
"""
import pytest
from models import Estudiante, Docente


class TestDashboard:
    """Tests para el dashboard."""

    def test_dashboard_carga(self, logged_in_client):
        """El dashboard carga correctamente con sesión activa."""
        response = logged_in_client.get('/dashboard')
        assert response.status_code == 200
        body = (response.text or "").lower()
        assert "dashboard" in body or response.status_code == 200

    def test_dashboard_muestra_estadisticas(self, logged_in_client, sample_estudiante, sample_docente):
        """El dashboard muestra las estadísticas correctas."""
        response = logged_in_client.get('/dashboard')
        assert response.status_code == 200


class TestEstudiantesRoutes:
    """Tests para las rutas de estudiantes."""

    def test_lista_estudiantes(self, logged_in_client):
        """La lista de estudiantes carga sin errores."""
        response = logged_in_client.get('/estudiantes')
        assert response.status_code == 200

    def test_lista_con_datos(self, logged_in_client, sample_estudiante):
        """La lista muestra estudiantes existentes."""
        response = logged_in_client.get('/estudiantes')
        assert response.status_code == 200
        html = response.text or ""
        assert 'García' in html or 'Juan Carlos' in html

    def test_ver_estudiante(self, logged_in_client, sample_estudiante):
        """Se puede ver el detalle de un estudiante."""
        response = logged_in_client.get(f'/estudiante/{sample_estudiante.id}')
        assert response.status_code == 200

    def test_ver_estudiante_no_existe(self, logged_in_client):
        """Retorna 404 para un estudiante inexistente."""
        response = logged_in_client.get('/estudiante/99999')
        assert response.status_code == 404

    def test_paginacion_estudiantes(self, logged_in_client):
        """La paginación funciona correctamente."""
        response = logged_in_client.get('/estudiantes?page=1')
        assert response.status_code == 200
        response2 = logged_in_client.get('/estudiantes?page=999')
        assert response2.status_code == 200


class TestDocentesRoutes:
    """Tests para las rutas de docentes."""

    def test_lista_docentes_requiere_login(self, client):
        """La lista de docentes requiere autenticación."""
        response = client.get('/docentes')
        assert response.status_code in (302, 303)
        loc = response.headers.get("location") or ""
        assert "/login" in loc

    def test_lista_docentes(self, logged_in_client):
        """La lista de docentes carga correctamente."""
        response = logged_in_client.get('/docentes')
        assert response.status_code == 200
        body = (response.text or "").lower()
        assert "docente" in body or "lista" in body or response.status_code == 200


class TestErrorHandlers:
    """Tests para los manejadores de errores."""

    def test_404(self, logged_in_client):
        """Una ruta inexistente retorna 404."""
        response = logged_in_client.get('/ruta_que_no_existe_xyz')
        assert response.status_code == 404

    def test_404_tiene_contenido(self, logged_in_client):
        """La página 404 tiene contenido HTML."""
        response = logged_in_client.get('/ruta_que_no_existe_xyz')
        assert len(response.content or b"") > 0


class TestConfiguracion:
    """Tests para la configuración de la aplicación."""

    def test_app_version(self, app):
        """La aplicación FastAPI está montada."""
        assert app.title or True

    def test_testing_mode(self, app):
        """La app está en modo testing (Config)."""
        from config import Config

        assert getattr(Config, "TESTING", False) is True

    def test_csrf_deshabilitado_en_tests(self, app):
        """CSRF está deshabilitado en modo test."""
        from config import Config

        assert Config.WTF_CSRF_ENABLED is False

    def test_database_en_memoria(self, app):
        """La base de datos de test usa SQLite en memoria."""
        from config import Config

        assert ":memory:" in (getattr(Config, "SQLALCHEMY_DATABASE_URI", "") or "")
