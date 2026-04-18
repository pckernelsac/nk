import pandas as pd
import os
import datetime
# Asegúrate de tener cualquier otro import necesario aquí
# from typing import List, Dict, Any # Si usas type hints

class CSVService:
    """
    Servicio para procesar archivos CSV con resultados de exámenes.
    """

    def __init__(self, upload_folder: str, student_service, academic_service):
        """
        Inicializa el servicio CSV.

        Args:
            upload_folder (str): Carpeta para guardar los archivos subidos
            student_service: Servicio de estudiantes para guardar datos
            academic_service: Servicio académico para determinar áreas
        """
        self.upload_folder = upload_folder
        self.student_service = student_service
        self.academic_service = academic_service

        # Crear carpeta de uploads si no existe
        if not os.path.exists(self.upload_folder):
            os.makedirs(self.upload_folder)

    def process_csv_file(self, filepath: str, programa: str = '', nivel: str = 'ACADEMIA') -> int:
        """
        Procesa un archivo CSV y guarda sus datos.

        Args:
            filepath (str): Ruta al archivo CSV

        Returns:
            int: Número de registros procesados
        """
        try:
            # --- MODIFICACIÓN CLAVE ---
            # Especificar explícitamente el tipo de dato como string para columnas ID
            dtype_options = {'StudentID': str, 'CustomID': str} 
            # Lee el CSV forzando los tipos y tratando celdas vacías como strings vacíos
            df = pd.read_csv(filepath, dtype=dtype_options, na_filter=False)
            # --- FIN MODIFICACIÓN ---

            # Opcional: Si aún quieres manejar posibles NaN que no sean string vacío:
            # df['StudentID'] = df['StudentID'].fillna('').astype(str)
            # df['CustomID'] = df['CustomID'].fillna('').astype(str)

        except Exception as e:
            # Manejar error de lectura de CSV de forma más robusta
            print(f"Error leyendo el archivo CSV en {filepath}: {e}")
            # Puedes relanzar un error más específico o devolver 0/None
            raise ValueError(f"No se pudo leer o procesar el archivo CSV: {e}") from e

        count = 0

        # Guardar cada fila en la base de datos
        for _, row in df.iterrows():
            # Ahora .get() debería devolver strings directamente por el dtype especificado
            student_id = row.get('StudentID', '')
            custom_id = row.get('CustomID', '')

            # Como precaución extra (aunque menos probable ahora), podrías limpiar el '.0' si aún apareciera
            if isinstance(student_id, str) and student_id.endswith('.0'):
                 student_id = student_id[:-2]
            if isinstance(custom_id, str) and custom_id.endswith('.0'):
                 custom_id = custom_id[:-2]

            # Extraer el resto de los datos (sin cambios aquí)
            quiz_name = row.get('QuizName', '')
            quiz_class = row.get('QuizClass', '')
            first_name = row.get('FirstName', '')
            last_name = row.get('LastName', '')
            # Para campos numéricos, es bueno manejar posibles errores de conversión
            try:
                earned_points = float(row.get('Earned Points', 0.0))
            except (ValueError, TypeError):
                earned_points = 0.0
            try:
                possible_points = float(row.get('Possible Points', 0.0))
            except (ValueError, TypeError):
                possible_points = 0.0
            try:
                percent_correct = float(row.get('PercentCorrect', 0.0))
            except (ValueError, TypeError):
                percent_correct = 0.0

            quiz_created = row.get('QuizCreated', '')
            data_exported = row.get('DataExported', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')) # Formato con hora
            key_version = row.get('Key Version', '')  # Nueva columna

            responses = []
            pri_keys = []
            points = []
            marks = []

            # 50 preguntas para ACADEMIA, 20 para niveles escolares
            max_questions = 50 if nivel == 'ACADEMIA' else 20
            for i in range(1, max_questions + 1):
                responses.append(str(row.get(f'Stu{i}', '')))
                pri_keys.append(str(row.get(f'PriKey{i}', '')))
                points.append(str(row.get(f'Points{i}', '0'))) # Guardar como string
                marks.append(str(row.get(f'Mark{i}', '')))

            academic_area_id = self.academic_service.get_area_id_for_nivel(quiz_class, nivel)

            # Buscar estudiante del sistema principal por DNI para vincular y resolver nombres
            estudiante_id = None
            if student_id:
                try:
                    from models import Estudiante
                    est = Estudiante.query.filter_by(dni_est=student_id).first()
                    if est:
                        estudiante_id = est.id
                        # Si no tiene nombre/apellido o viene como "Estudiante", usar el nombre real
                        nombre_faltante = (
                            not first_name or not first_name.strip() or
                            first_name.strip().lower() == 'estudiante' or
                            not last_name or not last_name.strip() or
                            last_name.strip().lower() == 'estudiante'
                        )
                        if nombre_faltante:
                            first_name = est.nombres_est or 'Estudiante'
                            last_name = f"{est.apellido_paterno_est or ''} {est.apellido_materno_est or ''}".strip() or 'Estudiante'
                except Exception:
                    pass

            # Fallback si no se encontró estudiante y el nombre está vacío
            if not first_name or not first_name.strip() or first_name.strip().lower() == 'estudiante':
                first_name = "Estudiante"
            if not last_name or not last_name.strip() or last_name.strip().lower() == 'estudiante':
                last_name = "Estudiante"

            # Guardar el estudiante
            try:
                self.student_service.save_student(
                    quiz_name, quiz_class, first_name, last_name, student_id, custom_id,
                    earned_points, possible_points, percent_correct, quiz_created,
                    data_exported, ','.join(responses), ','.join(pri_keys),
                    ','.join(points), ','.join(marks), academic_area_id, key_version,
                    programa=programa, nivel=nivel, estudiante_id=estudiante_id
                )
                count += 1
            except Exception as db_err:
                 # Loggear error al guardar estudiante específico
                 print(f"Error al guardar datos del estudiante con ID {student_id} desde CSV: {db_err}")
                 # Decidir si continuar con el siguiente registro o detener todo el proceso
                 # raise db_err # Para detener el proceso
                 continue # Para continuar con el siguiente estudiante

        return count