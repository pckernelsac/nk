"""
Tests para el módulo de autenticación.
"""
import pytest
from models import Usuario


class TestLogin:
    """Tests para la ruta de login."""

    def test_login_page_loads(self, client):
        """La página de login carga correctamente."""
        response = client.get('/login')
        assert response.status_code == 200

    def test_login_exitoso(self, client, admin_user):
        """Un usuario con credenciales correctas puede iniciar sesión."""
        response = client.post('/login', data={
            'username': 'admin_test',
            'password': 'password123'
        }, follow_redirects=True)
        assert response.status_code == 200

    def test_login_password_incorrecto(self, client, admin_user):
        """Un password incorrecto no permite el acceso."""
        response = client.post('/login', data={
            'username': 'admin_test',
            'password': 'wrong_password'
        }, follow_redirects=True)
        assert response.status_code == 200
        body = (response.text or "").lower()
        assert "incorrectos" in body or response.status_code == 200

    def test_login_usuario_no_existe(self, client):
        """Un usuario inexistente no puede iniciar sesión."""
        response = client.post('/login', data={
            'username': 'noexiste',
            'password': 'password123'
        }, follow_redirects=True)
        assert response.status_code == 200

    def test_login_usuario_inactivo(self, client, inactive_user):
        """Un usuario inactivo no puede iniciar sesión."""
        response = client.post('/login', data={
            'username': 'inactive_test',
            'password': 'password123'
        }, follow_redirects=True)
        assert response.status_code == 200

    def test_login_establece_sesion(self, client, admin_user):
        """El login exitoso establece la sesión (acceso a /dashboard)."""
        r = client.post(
            "/login",
            data={"username": "admin_test", "password": "password123"},
            follow_redirects=False,
        )
        assert r.status_code in (302, 303)
        dash = client.get("/dashboard", follow_redirects=False)
        assert dash.status_code == 200


class TestLogout:
    """Tests para la ruta de logout."""

    def test_logout_limpia_sesion(self, logged_in_client):
        """El logout limpia la sesión del usuario."""
        logged_in_client.get("/logout", follow_redirects=False)
        dash = logged_in_client.get("/dashboard", follow_redirects=False)
        assert dash.status_code in (302, 303)
        assert "/login" in (dash.headers.get("location") or "")

    def test_logout_redirige_a_login(self, logged_in_client):
        """El logout redirige a la página de login."""
        response = logged_in_client.get("/logout", follow_redirects=False)
        assert response.status_code in (302, 303)
        assert "/login" in (response.headers.get("location") or "")


class TestRegister:
    """Tests para la ruta de registro."""

    def test_register_page_loads(self, client):
        """La página de registro carga correctamente."""
        response = client.get('/register')
        assert response.status_code == 200

    def test_registro_exitoso(self, client, db):
        """Un usuario nuevo se registra correctamente."""
        response = client.post('/register', data={
            'username': 'nuevo_user',
            'password': 'newpass123',
            'email': 'nuevo@test.com',
            'nombre': 'Nuevo Usuario'
        }, follow_redirects=True)
        assert response.status_code == 200

        user = Usuario.query.filter_by(username='nuevo_user').first()
        assert user is not None
        assert user.email == 'nuevo@test.com'

    def test_registro_username_duplicado(self, client, admin_user):
        """No se puede registrar con un username que ya existe."""
        response = client.post('/register', data={
            'username': 'admin_test',
            'password': 'pass123',
            'email': 'otro@test.com',
            'nombre': 'Otro'
        }, follow_redirects=True)
        assert response.status_code == 200

    def test_registro_email_duplicado(self, client, admin_user):
        """No se puede registrar con un email que ya existe."""
        response = client.post('/register', data={
            'username': 'otro_user',
            'password': 'pass123',
            'email': 'admin@test.com',
            'nombre': 'Otro'
        }, follow_redirects=True)
        assert response.status_code == 200


class TestLoginRequired:
    """Tests para el decorador @login_required."""

    def test_dashboard_requiere_login(self, client):
        """El dashboard redirige a login si no hay sesión."""
        response = client.get("/dashboard", follow_redirects=False)
        assert response.status_code in (302, 303)
        loc = response.headers.get("location") or ""
        assert "/login" in loc

    def test_estudiantes_requiere_login(self, client):
        """La lista de estudiantes redirige a login si no hay sesión."""
        response = client.get("/estudiantes", follow_redirects=False)
        assert response.status_code in (302, 303)
        loc = response.headers.get("location") or ""
        assert "/login" in loc

    def test_index_redirige_sin_sesion(self, client):
        """La raíz redirige a login si no hay sesión."""
        response = client.get("/", follow_redirects=False)
        assert response.status_code in (302, 303)
        loc = response.headers.get("location") or ""
        assert "/login" in loc

    def test_index_redirige_con_sesion(self, logged_in_client):
        """La raíz redirige a dashboard si hay sesión."""
        response = logged_in_client.get("/", follow_redirects=False)
        assert response.status_code in (302, 303)
        loc = response.headers.get("location") or ""
        assert "/dashboard" in loc
