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


def parse_quiz_name(quiz_name: str) -> Dict[str, Any]:
    """Descompone QuizName en (eta_number, remainder).

    Patrón nuevo (a partir de 2026): ``ETA<NN>-<AULA_CODIGO>``,
    donde ``AULA_CODIGO`` puede contener guiones internos (p. ej.
    ``ETA02-SEMECF17DF5AC-A-M-26``). El remainder es todo lo que va después del
    primer guion y se compara contra ``aulas.codigo``.

    Patrón legacy (anterior a 2026): ``ETA<NN>-<NIVEL_CODE>-<YEAR>-<CICLO>``,
    donde ``NIVEL_CODE`` ∈ {INI, PRIM, SEC, PS, INT, …}. Se preserva como
    fallback cuando el código del aula no coincide.
    """
    out: Dict[str, Any] = {
        'eta_number': None,
        'remainder': '',
        'legacy_nivel_code': None,
    }
    if not quiz_name:
        return out
    m = re.match(r'^\s*ETA\s*(\d+)\s*-\s*(.+?)\s*$', str(quiz_name).strip().upper())
    if not m:
        return out
    out['eta_number'] = int(m.group(1))
    out['remainder'] = m.group(2).strip()
    first = out['remainder'].split('-', 1)[0]
    if first in QUIZ_NAME_NIVEL_MAP:
        out['legacy_nivel_code'] = first
    return out


def detect_nivel_from_quiz_name(quiz_name: str) -> Optional[str]:
    """Compatibilidad: nivel inferido del segmento legacy del QuizName.

    Sólo funciona con el formato antiguo (``ETA01-PRIM-2026-1`` →
    ``PRIMARIA``). Para el formato nuevo (código de aula), usa
    ``CSVService.peek_quiz_metadata``.
    """
    parsed = parse_quiz_name(quiz_name)
    code = parsed.get('legacy_nivel_code')
    return QUIZ_NAME_NIVEL_MAP.get(code) if code else None


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
        """Lee la primera fila y resuelve aula/nivel a partir del QuizName.

        Estrategia:
          1. Intentar match exacto contra ``aulas.codigo`` con el remainder
             del QuizName (lo que va después de ``ETA<NN>-``).
          2. Si no hay aula con ese código, caer al mapeo legacy
             (``PRIM`` → ``PRIMARIA`` y demás).

        Devuelve:
            quiz_name (str), quiz_class (str), eta_number (int|None),
            aula_codigo (str): remainder del QuizName,
            aula_match: dict con la fila de Aula que coincide exactamente,
                o None si no hubo match,
            nivel: nivel resuelto (de aula_match o legacy), o None.
        """
        df = self._read_dataframe(filepath)
        if len(df) == 0:
            return {
                'quiz_name': '', 'quiz_class': '', 'eta_number': None,
                'aula_codigo': '', 'aula_match': None, 'nivel': None,
            }
        row0 = df.iloc[0]
        qn = str(row0.get('QuizName', '') or '').strip()
        qc_raw = row0.get('QuizClass', '')
        qc = '' if qc_raw is None else str(qc_raw).strip()
        parsed = parse_quiz_name(qn)
        aula_codigo = parsed.get('remainder') or ''

        aula_match = None
        nivel = None
        if aula_codigo:
            try:
                from models.aula import Aula
                aula = (
                    Aula.query
                    .filter(Aula.codigo.ilike(aula_codigo), Aula.activo.is_(True))
                    .first()
                )
                if aula is not None:
                    aula_match = {
                        'id': aula.id,
                        'nombre': aula.nombre,
                        'codigo': aula.codigo,
                        'nivel': aula.nivel,
                        'grado': aula.grado,
                    }
                    nivel = aula.nivel
            except Exception as e:
                print(f"peek_quiz_metadata: error buscando aula por codigo {aula_codigo!r}: {e}")

        if nivel is None:
            legacy_code = parsed.get('legacy_nivel_code')
            if legacy_code:
                nivel = QUIZ_NAME_NIVEL_MAP.get(legacy_code)

        return {
            'quiz_name': qn,
            'quiz_class': qc,
            'eta_number': parsed.get('eta_number'),
            'aula_codigo': aula_codigo,
            'aula_match': aula_match,
            'nivel': nivel,
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

    def process_csv_file(
        self, filepath: str, programa: str = '', nivel: str = 'ACADEMIA'
    ) -> Dict[str, Any]:
        """
        Procesa un archivo CSV o XLSX y guarda los registros cuyo DNI esté
        registrado en la tabla ``estudiantes``.

        Reglas:
          * Filas sin DNI: omitidas (en la práctica el endpoint ya las bloqueó
            con ``validate_file``; aquí actúa como guardia defensiva).
          * Filas con DNI no registrado en ``estudiantes.dni_est``: omitidas y
            reportadas en el dict de retorno.
          * Filas con DNI registrado: se vincula ``estudiante_id`` y, si el
            archivo no trae nombres, se rellenan desde el registro de BD.

        Returns:
            dict con keys:
                count (int): registros guardados,
                skipped_no_dni (int),
                skipped_unknown_dni (list[(excel_row:int, dni:str)]).
        """
        df = self._read_dataframe(filepath)

        # 0) Detectar cupo real del CSV: contar columnas PriKey{i}/Stu{i}.
        #    Con esto un archivo de 50 preguntas guarda 50 entradas en pri_keys
        #    aunque el cupo global esté configurado en 80. La boleta luego elige
        #    el set de ponderaciones que coincide con ese tamaño.
        prikey_re = re.compile(r'^PriKey(\d+)$')
        prikey_indices: List[int] = []
        for col in df.columns:
            m = prikey_re.match(str(col))
            if m:
                try:
                    prikey_indices.append(int(m.group(1)))
                except ValueError:
                    pass
        csv_n_questions = max(prikey_indices) if prikey_indices else 0

        # 1) Lookup batch de estudiantes (1 sola query) por DNIs únicos del archivo.
        from models import Estudiante
        unique_dnis = {
            self._normalize_dni(row.get('StudentID', ''))
            for _, row in df.iterrows()
        }
        unique_dnis.discard("")
        estudiantes_by_dni: Dict[str, Any] = {}
        if unique_dnis:
            try:
                rows = Estudiante.query.filter(
                    Estudiante.dni_est.in_(list(unique_dnis))
                ).all()
                estudiantes_by_dni = {e.dni_est: e for e in rows}
            except Exception as e:
                print(f"process_csv_file: error consultando estudiantes: {e}")

        count = 0
        skipped_no_dni = 0
        skipped_unknown_dni: List[Tuple[int, str]] = []
        invalid_sentinels = {"", "0", "00", "000", "0000"}

        for idx, row in df.iterrows():
            excel_row = int(idx) + 2
            student_id = self._normalize_dni(row.get('StudentID', ''))
            custom_id = self._normalize_dni(row.get('CustomID', ''))

            # 2a) Sin DNI → saltar (se asume bloqueo previo en upload_file).
            if student_id in invalid_sentinels:
                skipped_no_dni += 1
                continue

            # 2b) DNI no registrado → saltar y reportar.
            est = estudiantes_by_dni.get(student_id)
            if est is None:
                skipped_unknown_dni.append((excel_row, student_id))
                continue

            quiz_name = row.get('QuizName', '')
            quiz_class = row.get('QuizClass', '')
            first_name = row.get('FirstName', '') or ''
            last_name = row.get('LastName', '') or ''
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
            data_exported = row.get(
                'DataExported',
                datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            )
            key_version = row.get('Key Version', '')

            responses: List[str] = []
            pri_keys: List[str] = []
            points: List[str] = []
            marks: List[str] = []

            academic_area_id = self.academic_service.get_area_id_for_nivel(
                quiz_class, nivel
            )
            grado_csv = (quiz_class or "").strip() if nivel != "ACADEMIA" else None
            # Tamaño efectivo: lo que el CSV trae; si el archivo no tiene columnas
            # PriKey{i}, caer al cupo configurado para no romper niveles escolares.
            if csv_n_questions > 0:
                n_questions = csv_n_questions
            else:
                n_questions = self.academic_service.get_max_questions(
                    nivel, grado_csv, academic_area_id if nivel == "ACADEMIA" else None
                )
            for i in range(1, n_questions + 1):
                responses.append(str(row.get(f'Stu{i}', '')))
                pri_keys.append(str(row.get(f'PriKey{i}', '')))
                points.append(str(row.get(f'Points{i}', '0')))
                marks.append(str(row.get(f'Mark{i}', '')))

            # Resolver nombres: si el archivo no los trae, usar los de BD.
            first_name = first_name.strip() if isinstance(first_name, str) else ''
            last_name = last_name.strip() if isinstance(last_name, str) else ''
            nombre_faltante = (
                not first_name
                or first_name.lower() == 'estudiante'
                or not last_name
                or last_name.lower() == 'estudiante'
            )
            if nombre_faltante:
                first_name = est.nombres_est or 'Estudiante'
                last_name = (
                    f"{est.apellido_paterno_est or ''} {est.apellido_materno_est or ''}"
                ).strip() or 'Estudiante'

            try:
                self.student_service.save_student(
                    quiz_name, quiz_class, first_name, last_name,
                    student_id, custom_id,
                    earned_points, possible_points, percent_correct,
                    quiz_created, data_exported,
                    ','.join(responses), ','.join(pri_keys),
                    ','.join(points), ','.join(marks),
                    academic_area_id, key_version,
                    programa=programa, nivel=nivel, estudiante_id=est.id,
                )
                count += 1
            except Exception as db_err:
                print(
                    f"Error al guardar datos del estudiante con DNI {student_id} "
                    f"(fila {excel_row}): {db_err}"
                )
                continue

        return {
            'count': count,
            'skipped_no_dni': skipped_no_dni,
            'skipped_unknown_dni': skipped_unknown_dni,
        }