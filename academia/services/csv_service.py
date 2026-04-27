import pandas as pd
import os
import datetime
import re
from typing import Any, Dict, List, Optional, Tuple


# Códigos del segundo segmento de QuizName (ETAxx-<CODE>-yyyy-cc) → nivel del sistema.
QUIZ_NAME_NIVEL_MAP: Dict[str, str] = {
    'INI': 'INICIAL',
    'PRIM': 'PRIMARIA',
    'SEC': 'SECUNDARIA',
    'PS': 'ACADEMIA',
    'INT': 'ACADEMIA',
    'SEM': 'ACADEMIA',
    'CV': 'ACADEMIA',
    'CI': 'ACADEMIA',
    'ANUAL': 'ACADEMIA',
}


def detect_nivel_from_quiz_name(quiz_name: str) -> Optional[str]:
    """Devuelve el nivel del sistema inferido del código en el QuizName.

    QuizName típico: ``ETA01-PRIM-2026-1`` → ``PRIMARIA``;
    ``ETA02-PS-2026-1`` → ``ACADEMIA``. Retorna None si no se reconoce el patrón.
    """
    if not quiz_name:
        return None
    m = re.match(r'^ETA\d+\s*-\s*([A-Z]+)\s*-', str(quiz_name).strip().upper())
    if not m:
        return None
    return QUIZ_NAME_NIVEL_MAP.get(m.group(1))


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

    @staticmethod
    def _read_dataframe(filepath: str) -> pd.DataFrame:
        """Carga el archivo CSV/XLSX preservando StudentID y CustomID como string."""
        dtype_options = {'StudentID': str, 'CustomID': str}
        ext = os.path.splitext(filepath)[1].lower()
        try:
            if ext == '.xlsx':
                df = pd.read_excel(filepath, dtype=dtype_options, engine='openpyxl')
                df = df.where(df.notna(), '')
            else:
                df = pd.read_csv(filepath, dtype=dtype_options, na_filter=False)
        except Exception as e:
            print(f"Error leyendo el archivo en {filepath}: {e}")
            raise ValueError(f"No se pudo leer o procesar el archivo: {e}") from e
        return df

    def peek_quiz_metadata(self, filepath: str) -> Dict[str, Any]:
        """Lee la primera fila de datos y devuelve QuizName/QuizClass + nivel inferido."""
        df = self._read_dataframe(filepath)
        if len(df) == 0:
            return {'quiz_name': '', 'quiz_class': '', 'nivel': None}
        row0 = df.iloc[0]
        qn = str(row0.get('QuizName', '') or '').strip()
        qc_raw = row0.get('QuizClass', '')
        qc = '' if qc_raw is None else str(qc_raw).strip()
        return {
            'quiz_name': qn,
            'quiz_class': qc,
            'nivel': detect_nivel_from_quiz_name(qn),
        }

    @staticmethod
    def _normalize_dni(raw: Any) -> str:
        """Limpia un valor StudentID para compararlo contra estudiantes.dni_est."""
        if raw is None:
            return ""
        sid = str(raw).strip()
        if sid.endswith('.0'):
            sid = sid[:-2]
        return sid

    def validate_file(self, filepath: str) -> Dict[str, Any]:
        """
        Valida un archivo de quiz antes de procesarlo:
          * DNI vacío / 0 → 'missing_dni' (bloquea).
          * DNI no encontrado en estudiantes.dni_est → 'unknown_dni' (bloquea).

        No escribe en la base de datos. Hace una sola consulta IN(...) a estudiantes.

        Returns:
            dict con keys:
                total_rows (int),
                missing_dni: list[(excel_row:int, info:str)],
                unknown_dni: list[(excel_row:int, dni:str, info:str)].
        """
        df = self._read_dataframe(filepath)

        missing: List[Tuple[int, str]] = []
        seen_dnis: List[Tuple[int, str, str]] = []  # (excel_row, dni, info)
        invalid_sentinels = {"", "0", "00", "000", "0000"}

        for idx, row in df.iterrows():
            excel_row = int(idx) + 2  # 1-based + cabecera
            sid = self._normalize_dni(row.get('StudentID', ''))
            first = str(row.get('FirstName', '') or '').strip()
            last = str(row.get('LastName', '') or '').strip()
            info = (f"{first} {last}".strip()) or "(sin nombre)"
            if sid in invalid_sentinels:
                missing.append((excel_row, info))
            else:
                seen_dnis.append((excel_row, sid, info))

        unknown: List[Tuple[int, str, str]] = []
        unique_dnis = {sid for _, sid, _ in seen_dnis}
        if unique_dnis:
            try:
                from models import Estudiante
                rows = (
                    Estudiante.query
                    .with_entities(Estudiante.dni_est)
                    .filter(Estudiante.dni_est.in_(list(unique_dnis)))
                    .all()
                )
                existing = {r[0] for r in rows}
                for excel_row, sid, info in seen_dnis:
                    if sid not in existing:
                        unknown.append((excel_row, sid, info))
            except Exception as e:
                print(f"Error consultando estudiantes para validación: {e}")
                # No bloquear por error de BD; el llamador decide.

        return {
            'total_rows': int(len(df)),
            'missing_dni': missing,
            'unknown_dni': unknown,
        }

    def process_csv_file(self, filepath: str, programa: str = '', nivel: str = 'ACADEMIA') -> int:
        """
        Procesa un archivo CSV o XLSX (mismo esquema de columnas) y guarda sus datos.

        Args:
            filepath (str): Ruta al archivo CSV o XLSX

        Returns:
            int: Número de registros procesados
        """
        df = self._read_dataframe(filepath)

        count = 0

        # Guardar cada fila en la base de datos
        for _, row in df.iterrows():
            student_id = self._normalize_dni(row.get('StudentID', ''))
            custom_id = self._normalize_dni(row.get('CustomID', ''))

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

            academic_area_id = self.academic_service.get_area_id_for_nivel(quiz_class, nivel)
            grado_csv = (quiz_class or "").strip() if nivel != "ACADEMIA" else None
            max_questions = self.academic_service.get_max_questions(
                nivel, grado_csv, academic_area_id if nivel == "ACADEMIA" else None
            )
            for i in range(1, max_questions + 1):
                responses.append(str(row.get(f'Stu{i}', '')))
                pri_keys.append(str(row.get(f'PriKey{i}', '')))
                points.append(str(row.get(f'Points{i}', '0'))) # Guardar como string
                marks.append(str(row.get(f'Mark{i}', '')))

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