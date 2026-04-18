"""
Migration script to add carrera_postula column to estudiantes table
Run this script to update existing database without losing data
"""

import sys
import os

# Add parent directory to path to import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import db

def add_carrera_postula_column():
    """Add carrera_postula column to estudiantes table"""
    with app.app_context():
        try:
            # Add new column using raw SQL
            sql = """
            ALTER TABLE estudiantes
            ADD COLUMN carrera_postula VARCHAR(100);
            """

            db.session.execute(db.text(sql))
            db.session.commit()

            print("✓ Successfully added carrera_postula column to estudiantes table")
            print("  Column type: VARCHAR(100)")
            print("  Nullable: Yes (existing records will have NULL value)")

        except Exception as e:
            db.session.rollback()
            error_msg = str(e).lower()

            # Check if column already exists
            if 'duplicate column name' in error_msg or 'already exists' in error_msg:
                print("ℹ Column carrera_postula already exists in estudiantes table")
                print("  No migration needed")
            else:
                print(f"✗ Error adding column: {e}")
                raise

if __name__ == '__main__':
    add_carrera_postula_column()
