"""
Migración: Agrega columna estudiante_id a la tabla students (AcademiaStudent)
y vincula registros existentes con la tabla estudiantes por DNI.

Ejecutar una sola vez:
    python migrate_estudiante_id.py
"""
from app import create_app
from models import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # 1. Agregar columna si no existe
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    columnas = [col['name'] for col in inspector.get_columns('students')]

    if 'estudiante_id' not in columnas:
        db.session.execute(text('ALTER TABLE students ADD COLUMN estudiante_id INTEGER REFERENCES estudiantes(id)'))
        db.session.execute(text('CREATE INDEX IF NOT EXISTS ix_students_estudiante_id ON students(estudiante_id)'))
        db.session.commit()
        print("Columna estudiante_id agregada a tabla students.")
    else:
        print("Columna estudiante_id ya existe.")

    # 2. Vincular registros existentes por DNI
    result = db.session.execute(text("""
        UPDATE students
        SET estudiante_id = (
            SELECT e.id FROM estudiantes e
            WHERE e.dni_est = students.student_id
            LIMIT 1
        )
        WHERE estudiante_id IS NULL
          AND student_id IS NOT NULL
          AND student_id != ''
    """))
    db.session.commit()

    vinculados = result.rowcount
    print(f"Registros vinculados: {vinculados}")

    # 3. Mostrar estadísticas
    total = db.session.execute(text("SELECT COUNT(*) FROM students")).scalar()
    con_vinculo = db.session.execute(text("SELECT COUNT(*) FROM students WHERE estudiante_id IS NOT NULL")).scalar()
    sin_vinculo = db.session.execute(text("SELECT COUNT(*) FROM students WHERE estudiante_id IS NULL")).scalar()

    print(f"\nEstadísticas:")
    print(f"  Total registros ETA: {total}")
    print(f"  Vinculados con estudiante: {con_vinculo}")
    print(f"  Sin vínculo (DNI no encontrado): {sin_vinculo}")

    if sin_vinculo > 0:
        huerfanos = db.session.execute(text("""
            SELECT student_id, first_name, last_name, COUNT(*) as etas
            FROM students
            WHERE estudiante_id IS NULL AND student_id IS NOT NULL AND student_id != ''
            GROUP BY student_id
            ORDER BY etas DESC
            LIMIT 20
        """)).fetchall()
        if huerfanos:
            print(f"\n  DNIs sin estudiante registrado (top 20):")
            for row in huerfanos:
                print(f"    DNI: {row[0]} | {row[1]} {row[2]} | ETAs: {row[3]}")
