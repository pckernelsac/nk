"""
Tests para endpoints API (JSON).
"""
import pytest


class TestBuscarEstudianteAPI:
    """Tests para el API de búsqueda de estudiantes en pensiones."""

    def test_buscar_por_dni(self, logged_in_client, sample_estudiante):
        """Buscar estudiante por DNI vía API."""
        response = logged_in_client.post(
            "/pagos/pensiones/api/buscar_estudiante",
            json={"termino": "12345678"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_buscar_termino_corto(self, logged_in_client):
        """Buscar con menos de 3 caracteres retorna error."""
        response = logged_in_client.post(
            "/pagos/pensiones/api/buscar_estudiante",
            json={"termino": "ab"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is False

    def test_buscar_sin_resultados(self, logged_in_client):
        """Buscar un DNI que no existe retorna mensaje de no encontrado."""
        response = logged_in_client.post(
            "/pagos/pensiones/api/buscar_estudiante",
            json={"termino": "00000000"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is False

    def test_buscar_por_nombre(self, logged_in_client, sample_estudiante):
        """Buscar estudiante por nombre vía API."""
        response = logged_in_client.post(
            "/pagos/pensiones/api/buscar_estudiante",
            json={"termino": "García"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
