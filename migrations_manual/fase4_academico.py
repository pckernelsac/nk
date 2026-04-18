"""
Migracion Fase 4: Sistema Academico (Fast Tests)
Crea tablas para periodos academicos, cursos, fast tests y notas

Ejecutar: python migrations_manual/fase4_academico.py
"""

import sys
import os

# Agregar el directorio raiz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db, PeriodoAcademico, Curso, DocenteCursoAula, FastTest, NotaFastTest

def ejecutar_migracion():
    """Ejecuta la migracion para crear tablas academicas"""

    print("=" * 60)
    print("MIGRACION FASE 4: Sistema Academico (Fast Tests)")
    print("=" * 60)
    print()

    with app.app_context():
        try:
            print("Creando tablas academicas...")

            # Crear todas las tablas
            db.create_all()

            print("[OK] Tabla periodos_academicos creada")
            print("[OK] Tabla cursos creada")
            print("[OK] Tabla docentes_cursos_aulas creada")
            print("[OK] Tabla fast_tests creada")
            print("[OK] Tabla notas_fast_test creada")
            print()

            # Crear periodos academicos de ejemplo para 2025
            print("Creando periodos academicos de ejemplo para 2025...")

            periodos_2025 = [
                {
                    'nombre': 'I Bimestre',
                    'numero': 1,
                    'anio_escolar': '2025',
                    'fecha_inicio': '2025-03-01',
                    'fecha_fin': '2025-05-10'
                },
                {
                    'nombre': 'II Bimestre',
                    'numero': 2,
                    'anio_escolar': '2025',
                    'fecha_inicio': '2025-05-11',
                    'fecha_fin': '2025-07-20'
                },
                {
                    'nombre': 'III Bimestre',
                    'numero': 3,
                    'anio_escolar': '2025',
                    'fecha_inicio': '2025-08-01',
                    'fecha_fin': '2025-10-10'
                },
                {
                    'nombre': 'IV Bimestre',
                    'numero': 4,
                    'anio_escolar': '2025',
                    'fecha_inicio': '2025-10-11',
                    'fecha_fin': '2025-12-20'
                }
            ]

            from datetime import datetime

            for p_data in periodos_2025:
                # Verificar si ya existe
                existe = PeriodoAcademico.query.filter_by(
                    numero=p_data['numero'],
                    anio_escolar=p_data['anio_escolar']
                ).first()

                if not existe:
                    periodo = PeriodoAcademico(
                        nombre=p_data['nombre'],
                        numero=p_data['numero'],
                        anio_escolar=p_data['anio_escolar'],
                        fecha_inicio=datetime.strptime(p_data['fecha_inicio'], '%Y-%m-%d').date(),
                        fecha_fin=datetime.strptime(p_data['fecha_fin'], '%Y-%m-%d').date(),
                        activo=True,
                        usuario_registro='admin'
                    )
                    db.session.add(periodo)
                    print(f"  [OK] Creado: {periodo.nombre}")

            # Crear cursos de ejemplo
            print()
            print("Creando cursos de ejemplo...")

            cursos_ejemplo = [
                {'nombre': 'Matematica', 'codigo': 'MAT', 'nivel': 'Ambos'},
                {'nombre': 'Comunicacion', 'codigo': 'COM', 'nivel': 'Ambos'},
                {'nombre': 'Ciencia y Tecnologia', 'codigo': 'CYT', 'nivel': 'Ambos'},
                {'nombre': 'Personal Social', 'codigo': 'PS', 'nivel': 'Primaria'},
                {'nombre': 'Historia, Geografia y Economia', 'codigo': 'HGE', 'nivel': 'Secundaria'},
                {'nombre': 'Ingles', 'codigo': 'ING', 'nivel': 'Ambos'},
                {'nombre': 'Educacion Fisica', 'codigo': 'EF', 'nivel': 'Ambos'},
                {'nombre': 'Arte y Cultura', 'codigo': 'ART', 'nivel': 'Ambos'},
                {'nombre': 'Educacion Religiosa', 'codigo': 'REL', 'nivel': 'Ambos'},
            ]

            for c_data in cursos_ejemplo:
                # Verificar si ya existe
                existe = Curso.query.filter_by(codigo=c_data['codigo']).first()

                if not existe:
                    curso = Curso(
                        nombre=c_data['nombre'],
                        codigo=c_data['codigo'],
                        nivel=c_data.get('nivel'),
                        activo=True,
                        usuario_registro='admin'
                    )
                    db.session.add(curso)
                    print(f"  [OK] Creado: {curso.nombre} ({curso.codigo})")

            db.session.commit()

            print()
            print("=" * 60)
            print("MIGRACION COMPLETADA")
            print("=" * 60)
            print()
            print("Tablas creadas:")
            print("  - periodos_academicos (con 4 bimestres para 2025)")
            print("  - cursos (con 9 cursos de ejemplo)")
            print("  - docentes_cursos_aulas")
            print("  - fast_tests")
            print("  - notas_fast_test")
            print()
            print("Proximos pasos:")
            print("1. Acceder a /academico/periodos para ver periodos")
            print("2. Acceder a /academico/cursos para ver cursos")
            print("3. Crear Fast Tests en /academico/fast_tests/crear")
            print("4. Calificar Fast Tests")
            print("5. Ver reportes academicos integrados en /academico/estudiantes/<id>/reporte")
            print()

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()

if __name__ == '__main__':
    ejecutar_migracion()
