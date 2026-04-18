"""
Tests para el módulo de pensiones.
"""
import pytest
from models import (db as _db, ConfiguracionPension, PensionEstudiante,
                    PagoPension, Estudiante)


class TestPensionesRoutes:
    """Tests para las rutas del módulo de pensiones."""

    def test_dashboard_pensiones(self, logged_in_client):
        """El dashboard de pensiones carga correctamente."""
        response = logged_in_client.get('/pagos/pensiones/dashboard')
        assert response.status_code == 200

    def test_configuracion_pensiones_get(self, logged_in_client):
        """La página de configuración de pensiones carga."""
        response = logged_in_client.get('/pagos/pensiones/configuracion')
        assert response.status_code == 200

    def test_asignar_pensiones_lista(self, logged_in_client):
        """La lista para asignar pensiones carga."""
        response = logged_in_client.get('/pagos/pensiones/asignar')
        assert response.status_code == 200

    def test_registrar_pago_get(self, logged_in_client):
        """La página de registrar pago carga."""
        response = logged_in_client.get('/pagos/pensiones/registrar')
        assert response.status_code == 200

    def test_historial_pagos(self, logged_in_client):
        """El historial de pagos carga."""
        response = logged_in_client.get('/pagos/pensiones/historial')
        assert response.status_code == 200


class TestPensionModels:
    """Tests para los modelos de pensiones."""

    def test_crear_pension_estudiante(self, db, sample_estudiante):
        """Se puede crear una pensión para un estudiante."""
        pension = PensionEstudiante(
            estudiante_id=sample_estudiante.id,
            estudiante_nombre_completo='García López, Juan Carlos',
            estudiante_dni='12345678',
            estudiante_nivel='SECUNDARIA',
            estudiante_grado='3ro',
            monto_mensual=250.00,
            anio_escolar='2026',
            activo=True
        )
        db.session.add(pension)
        db.session.commit()

        saved = PensionEstudiante.query.first()
        assert saved is not None
        assert saved.monto_mensual == 250.00
        assert saved.anio_escolar == '2026'

    def test_crear_configuracion_pension(self, db):
        """Se puede crear la configuración de pensiones."""
        config = ConfiguracionPension(
            nombre_institucion='Colegio Test',
            ruc_institucion='12345678901',
            direccion_institucion='Av. Test 123',
            telefono_institucion='074123456',
            anio_escolar='2026',
            meses_activos='marzo,abril,mayo,junio,julio,agosto,septiembre,octubre,noviembre,diciembre',
            serie_recibo='001',
            numero_correlativo=1
        )
        db.session.add(config)
        db.session.commit()

        saved = ConfiguracionPension.query.first()
        assert saved is not None
        assert saved.nombre_institucion == 'Colegio Test'
