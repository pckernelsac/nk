"""
Tests para los modelos de la base de datos.
"""
import pytest
from models import Usuario, Estudiante, Docente


class TestUsuarioModel:
    """Tests para el modelo Usuario."""

    def test_crear_usuario(self, db):
        """Un usuario se crea correctamente con todos sus campos."""
        user = Usuario(
            username='testuser',
            email='test@example.com',
            nombre='Test User',
            rol='usuario',
            activo=True
        )
        user.set_password('mypassword')
        db.session.add(user)
        db.session.commit()

        saved = Usuario.query.filter_by(username='testuser').first()
        assert saved is not None
        assert saved.email == 'test@example.com'
        assert saved.nombre == 'Test User'
        assert saved.rol == 'usuario'
        assert saved.activo is True

    def test_password_hash(self, db):
        """La contraseña se hashea y no se guarda en texto plano."""
        user = Usuario(username='hashtest', email='hash@test.com', nombre='Hash')
        user.set_password('secret123')
        assert user.password_hash != 'secret123'
        assert user.check_password('secret123') is True
        assert user.check_password('wrong') is False

    def test_username_unico(self, db):
        """No se pueden crear dos usuarios con el mismo username."""
        u1 = Usuario(username='unique', email='a@test.com', nombre='A')
        u1.set_password('pass')
        db.session.add(u1)
        db.session.commit()

        u2 = Usuario(username='unique', email='b@test.com', nombre='B')
        u2.set_password('pass')
        db.session.add(u2)
        with pytest.raises(Exception):
            db.session.commit()

    def test_email_unico(self, db):
        """No se pueden crear dos usuarios con el mismo email."""
        u1 = Usuario(username='user1', email='same@test.com', nombre='A')
        u1.set_password('pass')
        db.session.add(u1)
        db.session.commit()

        u2 = Usuario(username='user2', email='same@test.com', nombre='B')
        u2.set_password('pass')
        db.session.add(u2)
        with pytest.raises(Exception):
            db.session.commit()

    def test_rol_default(self, db):
        """El rol por defecto es 'usuario'."""
        user = Usuario(username='default_rol', email='dr@test.com', nombre='DR')
        user.set_password('pass')
        db.session.add(user)
        db.session.commit()
        assert user.rol == 'usuario'

    def test_activo_default(self, db):
        """El usuario está activo por defecto."""
        user = Usuario(username='active_def', email='ad@test.com', nombre='AD')
        user.set_password('pass')
        db.session.add(user)
        db.session.commit()
        assert user.activo is True

    def test_repr(self, db):
        """El repr del usuario muestra el username."""
        user = Usuario(username='reprtest', email='repr@test.com', nombre='R')
        assert 'reprtest' in repr(user)


class TestEstudianteModel:
    """Tests para el modelo Estudiante."""

    def test_crear_estudiante(self, sample_estudiante):
        """Un estudiante se crea correctamente."""
        est = Estudiante.query.get(sample_estudiante.id)
        assert est is not None
        assert est.nombres_est == 'Juan Carlos'
        assert est.apellido_paterno_est == 'García'
        assert est.dni_est == '12345678'
        assert est.nivel == 'SECUNDARIA'
        assert est.grado == '3ro'

    def test_codigo_estudiante_unico(self, db):
        """El código de estudiante debe ser único."""
        e1 = Estudiante(
            nombres_est='A', apellido_paterno_est='A',
            apellido_materno_est='A', dni_est='11111111',
            codigo_estudiante='EST202600099'
        )
        db.session.add(e1)
        db.session.commit()

        e2 = Estudiante(
            nombres_est='B', apellido_paterno_est='B',
            apellido_materno_est='B', dni_est='22222222',
            codigo_estudiante='EST202600099'
        )
        db.session.add(e2)
        with pytest.raises(Exception):
            db.session.commit()

    def test_fecha_registro_automatica(self, sample_estudiante):
        """La fecha de registro se asigna automáticamente."""
        assert sample_estudiante.fecha_registro is not None

    def test_version_default(self, sample_estudiante):
        """La versión por defecto es 1."""
        assert sample_estudiante.version == 1

    def test_generar_codigo_estudiante(self, db):
        """El generador de código crea códigos con formato correcto."""
        codigo = Estudiante.generar_codigo_estudiante()
        assert codigo.startswith('EST')
        assert len(codigo) == 12  # ESTYYYYnnnnn


class TestDocenteModel:
    """Tests para el modelo Docente."""

    def test_crear_docente(self, sample_docente):
        """Un docente se crea correctamente."""
        doc = Docente.query.get(sample_docente.id)
        assert doc is not None
        assert doc.nombres == 'María Elena'
        assert doc.apellido_paterno == 'Pérez'
        assert doc.dni == '87654321'

    def test_dni_unico(self, db):
        """El DNI del docente debe ser único."""
        d1 = Docente(
            nombres='A', apellido_paterno='A', apellido_materno='A',
            dni='99999999'
        )
        db.session.add(d1)
        db.session.commit()

        d2 = Docente(
            nombres='B', apellido_paterno='B', apellido_materno='B',
            dni='99999999'
        )
        db.session.add(d2)
        with pytest.raises(Exception):
            db.session.commit()

    def test_fecha_registro_automatica(self, sample_docente):
        """La fecha de registro se asigna automáticamente."""
        assert sample_docente.fecha_registro is not None
