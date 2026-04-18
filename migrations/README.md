# Database Migrations

This folder contains database migration scripts for incremental schema changes without data loss.

## Running Migrations

To apply migrations to your database:

1. Navigate to the project root directory:
   ```bash
   cd D:\Proyectos_python\intranetnumeralk
   ```

2. Activate your virtual environment:
   ```bash
   # Windows
   venv\Scripts\activate

   # Linux/Mac
   source venv/bin/activate
   ```

3. Run the migration script:
   ```bash
   python migrations/add_carrera_postula.py
   ```

## Available Migrations

### add_carrera_postula.py

**Purpose:** Adds `carrera_postula` column to `estudiantes` table

**Changes:**
- Adds column: `carrera_postula VARCHAR(100)` (nullable)

**When to run:** After pulling updates that include the "Carrera al que postula" feature

**Safe to re-run:** Yes (script detects if column already exists)

## Important Notes

- Always backup your database before running migrations
- Migration scripts are idempotent (safe to run multiple times)
- For fresh installations, use `init_db.py` instead - it creates all tables from scratch

## Database Location

Default: `instance/escuela.db`
