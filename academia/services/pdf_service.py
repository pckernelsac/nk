# -*- coding: utf-8 -*-
"""
Servicio para la generación de PDFs con boletas de notas personalizadas.

Este módulo encapsula toda la lógica relacionada con la creación de informes
en PDF utilizando la librería FPDF.
"""

import sqlite3 # Importar sqlite3 para manejo de errores específico si es necesario
import fpdf
import os
import datetime
import locale
import math # Para ceil
from typing import Dict, List, Tuple, Any, Optional

# --- Configuración de locale para español ---
# Intenta configurar el locale para fechas en español (Perú/España)
locales_to_try = ['es_PE.UTF-8', 'es-PE', 'es_ES.UTF-8', 'Spanish_Spain', 'es_PE', 'es_ES', 'es']
locale_set = False
for loc in locales_to_try:
    try:
        locale.setlocale(locale.LC_TIME, loc)
        locale_set = True
        # print(f"Locale configurado a: {loc}") # Descomentar para depuración
        break
    except locale.Error:
        continue
if not locale_set:
    print("Advertencia: No se pudo configurar locale a ninguna variante de español. Las fechas podrían aparecer en inglés.")
# ------------------------------------------

# --- Definición de Colores (RGB 0-255) ---
PURPLE_RGB = (69, 3, 140)
WHITE_RGB = (255, 255, 255)
LIGHT_GREY_RGB = (240, 240, 240) # Fondo claro general
MEDIUM_GREY_RGB = (211, 211, 211) # Borde o fondo alternativo
DARK_GREY_RGB = (50, 50, 50)     # Texto oscuro principal
BLACK_RGB = (0, 0, 0)
# Colores de Rendimiento
GREEN_BG = (220, 240, 220); GREEN_BAR = (0, 180, 0); GREEN_TEXT = (0, 100, 0)   # Bueno
YELLOW_BG = (255, 243, 224); YELLOW_BAR = (255, 180, 0); YELLOW_TEXT = (200, 120, 0) # Regular
RED_BG = (250, 220, 220); RED_BAR = (220, 0, 0); RED_TEXT = (180, 0, 0)     # En Proceso
GREY_BG = (230, 230, 230); GREY_TEXT = (100, 100, 100) # No Calculable / Blanco
# -----------------------------

# --- Constantes de Diseño (mm) ---
HEADER_HEIGHT_MM = 30
FOOTER_HEIGHT_MM = 25
BASE_MARGIN_LR = 10
# Margen superior efectivo = altura header + espacio para títulos + espacio antes de contenido
BASE_MARGIN_TOP_CONTENT = HEADER_HEIGHT_MM + 15 # Ajustado
# Margen inferior efectivo = altura footer + espacio texto footer + espacio antes de footer
BASE_MARGIN_BOTTOM_CONTENT = FOOTER_HEIGHT_MM + 5
# ---------------------------

class PDFService:
    """
    Servicio para la generación de PDFs (boletas de notas) utilizando FPDF.

    Requiere un 'academic_service' para obtener ponderaciones y nombres de áreas.
    Permite personalizar las imágenes de encabezado y pie.
    """

    def __init__(self, academic_service: object,
                 header_img_path: str = 'static/img/encabezado.png',
                 footer_img_path: str = 'static/img/pie.png'):
        """
        Inicializa el servicio de PDF.

        Args:
            academic_service: Instancia del servicio académico. Debe tener los métodos
                              'get_weights_by_area' y 'get_academic_area_name'.
            header_img_path (str): Ruta a la imagen de encabezado.
            footer_img_path (str): Ruta a la imagen de pie de página.

        Raises:
            TypeError: Si 'academic_service' no tiene los métodos requeridos.
            FileNotFoundError: Si las rutas de las imágenes no existen.
        """
        # Validar academic_service
        if not hasattr(academic_service, 'get_weights_by_area') or not callable(getattr(academic_service, 'get_weights_by_area')):
            raise TypeError("El objeto 'academic_service' debe tener un método callable 'get_weights_by_area'.")
        if not hasattr(academic_service, 'get_academic_area_name') or not callable(getattr(academic_service, 'get_academic_area_name')):
             # Considerar si esto debe ser un error o una advertencia
             print("Advertencia: 'academic_service' no tiene 'get_academic_area_name'. El nombre del área podría no mostrarse.")
             # raise TypeError("El objeto 'academic_service' debe tener un método callable 'get_academic_area_name'.")
        self.academic_service = academic_service

        # Validar rutas de imágenes
        if not os.path.exists(header_img_path):
            raise FileNotFoundError(f"No se encontró la imagen de encabezado en: {os.path.abspath(header_img_path)}")
        if not os.path.exists(footer_img_path):
            raise FileNotFoundError(f"No se encontró la imagen de pie de página en: {os.path.abspath(footer_img_path)}")

        self.header_img_path = header_img_path
        self.footer_img_path = footer_img_path
        # print(f"PDFService inicializado. Usando encabezado: {os.path.abspath(self.header_img_path)}")
        # print(f"PDFService inicializado. Usando pie: {os.path.abspath(self.footer_img_path)}")

    def _display_value(self, value: Any, default: str = "-") -> str:
        """
        Formatea un valor para mostrarlo en el PDF. Devuelve 'default' si es None,
        vacío o un valor predeterminado conocido.
        """
        if value is None: return default
        # Convertir a string y limpiar espacios
        str_value = str(value).strip()
        # Lista de valores considerados "vacíos" o "no disponibles"
        empty_values = ["", "N/A", "No disponible", "Fecha no disponible", "Área desconocida"]
        if not str_value or str_value in empty_values: return default
        # Devuelve el valor original convertido a string (puede ser número)
        return str(value)

    def _encode_text(self, text: str) -> str:
        """
        Intenta codificar texto para fuentes estándar de FPDF (Latin-1).
        Reemplaza caracteres no codificables.
        ¡PRECAUCIÓN!: Puede perder información. Usar fuentes TTF UTF-8 es preferible.
        """
        try:
            # FPDF usa 'latin-1' (ISO-8859-1) por defecto para fuentes base
            return text.encode('latin-1', 'replace').decode('latin-1')
        except Exception as e:
            print(f"Error de codificación para texto '{text[:20]}...': {e}")
            return "?" # O algún carácter de reemplazo

    def _get_performance_style(self, performance_text: str) -> tuple:
        """ Devuelve colores (fondo, barra, texto) según el texto de rendimiento. """
        if performance_text == "Bueno": return GREEN_BG, GREEN_BAR, GREEN_TEXT
        if performance_text == "Regular": return YELLOW_BG, YELLOW_BAR, YELLOW_TEXT
        if performance_text == "En Proceso": return RED_BG, RED_BAR, RED_TEXT
        return GREY_BG, DARK_GREY_RGB, GREY_TEXT # Estilo por defecto/No calculable

    def calculate_performance_text(self, correct: int, total_questions: int) -> str:
        """ Calcula el rendimiento textual basado en porcentaje de correctas. """
        if total_questions <= 0: return "N/A" # No aplica si no hay preguntas
        percentage = (correct / total_questions) * 100
        if percentage >= 70: return "Bueno"
        elif percentage >= 50: return "Regular"
        else: return "En Proceso"

    def _get_points_lookup_for_student(self, student: Dict[str, Any], num_total_questions: int) -> Dict[int, float]:
        """Wrapper nivel-aware de _get_points_lookup."""
        nivel = student.get('nivel') or 'ACADEMIA'
        if nivel == 'ACADEMIA':
            area_id = int(student.get('academic_area_id', 1) or 1)
            return self._get_points_lookup(area_id, num_total_questions)
        else:
            return self._get_points_lookup_by_nivel(nivel, student.get('quiz_class', ''), num_total_questions)

    def _get_points_lookup_by_nivel(self, nivel: str, grado: str, num_total_questions: int) -> Dict[int, float]:
        """Obtiene ponderaciones para niveles escolares (INICIAL/PRIMARIA/SECUNDARIA)."""
        points_lookup = {}
        try:
            subjects_map = self.academic_service.get_weights_by_nivel_grado(nivel, grado) or {}
            if not subjects_map:
                return {}
            for key, value in subjects_map.items():
                if not (isinstance(key, tuple) and len(key) == 2 and isinstance(value, tuple) and len(value) == 3):
                    continue
                q_start, q_end = key
                _subject, _level, points_val = value
                try:
                    q_start_int, q_end_int = int(q_start), int(q_end)
                    points_float = float(points_val)
                    if not (q_start_int > 0 and q_end_int >= q_start_int):
                        continue
                    for i in range(q_start_int - 1, min(q_end_int, num_total_questions)):
                        points_lookup[i] = points_float
                except (ValueError, TypeError):
                    continue
        except Exception as e:
            print(f"Error obteniendo ponderaciones para {nivel} grado {grado}: {e}")
        return points_lookup

    def _get_points_lookup(self, academic_area_id: int, num_total_questions: int) -> Dict[int, float]:
        """
        Obtiene las ponderaciones del servicio académico y crea un diccionario
        mapeando el índice de pregunta (0-based) a su puntaje.
        """
        points_lookup = {}
        try:
            # Obtener pesos: Dict[Tuple[int, int], Tuple[str, str, float]]
            subjects_map = self.academic_service.get_weights_by_area(academic_area_id) or {}
            if not subjects_map:
                 print(f"Advertencia: No se encontraron ponderaciones para el área {academic_area_id}.")
                 return {}

            for key, value in subjects_map.items():
                # Validar estructura de clave y valor
                if not (isinstance(key, tuple) and len(key) == 2 and
                        isinstance(value, tuple) and len(value) == 3): # Ahora espera (subj, level, weight)
                    print(f"Advertencia: Formato de ponderación inválido omitido: key={key}, value={value}")
                    continue

                q_start, q_end = key
                _subject, _level, points_val = value # Desempaquetar los 3 elementos

                try:
                    q_start_int, q_end_int = int(q_start), int(q_end)
                    points_float = float(points_val)
                    # Validar rango
                    if not (q_start_int > 0 and q_end_int >= q_start_int):
                        print(f"Advertencia: Rango de pregunta inválido omitido: {q_start_int}-{q_end_int}")
                        continue

                    # Llenar el lookup (índices 0-based)
                    # Asegurarse de no exceder el número total de preguntas reales
                    for i in range(q_start_int - 1, min(q_end_int, num_total_questions)):
                        points_lookup[i] = points_float

                except (ValueError, TypeError) as e:
                    print(f"Advertencia: Error procesando ponderación ({q_start}-{q_end}, {points_val}): {e}")
                    continue # Saltar esta entrada si hay error de conversión

        except Exception as e:
            # Capturar errores al llamar a get_weights_by_area
            print(f"Error crítico obteniendo ponderaciones para área {academic_area_id}: {e}")
            # Devolver lookup vacío para indicar fallo
            return {}

        return points_lookup

    def calculate_total_possible_points(self, academic_area_id: int, num_total_questions: int) -> float:
        """
        Calcula el puntaje máximo posible sumando las ponderaciones de todas las preguntas definidas.
        """
        points_lookup = self._get_points_lookup(academic_area_id, num_total_questions)
        if not points_lookup:
            print(f"Advertencia: No se pudo calcular el puntaje total posible para el área {academic_area_id} debido a falta de ponderaciones.")
            return 0.0 # O manejar como error

        # Sumar los puntos de todas las preguntas definidas en el lookup
        # Asegurarse de que solo contamos hasta num_total_questions
        total_possible = sum(points_lookup.get(i, 0.0) for i in range(num_total_questions))

        # Redondear a 3 decimales por consistencia
        return round(total_possible, 3)

    def _calculate_total_possible_for_student(self, student: Dict[str, Any], num_total_questions: int) -> float:
        """Calcula puntaje máximo posible de forma nivel-aware."""
        points_lookup = self._get_points_lookup_for_student(student, num_total_questions)
        if not points_lookup:
            return 0.0
        total_possible = sum(points_lookup.get(i, 0.0) for i in range(num_total_questions))
        return round(total_possible, 3)

    def calculate_partial_score(self, student: dict, start_question: int, end_question: int) -> float:
        """
        Calcula el puntaje parcial obtenido por el estudiante para un rango
        específico de preguntas (1-based, ambos inclusive).

        Utiliza las marcas ('marks') y las ponderaciones del área académica.
    
        Args:
        student: Diccionario con datos del estudiante
        start_question: Número de pregunta inicial (1-based, inclusive)
        end_question: Número de pregunta final (1-based, inclusive)
        
        Returns:
        float: Puntaje parcial obtenido
        """
        marks_str = student.get('marks')
        if not marks_str:
             print("Advertencia: No hay 'marks' para calcular puntaje parcial.")
             return 0.0

        marks = marks_str.split(',')
        num_questions = len(marks)

        if num_questions == 0 or start_question > num_questions or start_question > end_question:
            return 0.0

    # Obtener el lookup de puntos por pregunta (nivel-aware)
        points_lookup = self._get_points_lookup_for_student(student, num_questions)
        if not points_lookup:
            return 0.0

    # Ajustar índices a 0-based
    # IMPORTANTE: end_question es INCLUSIVE, por lo que sumamos 1 al end_idx
        start_idx = max(0, start_question - 1)
        end_idx = min(num_questions, end_question)  # end_question es el último índice inclusive

        partial_score = 0.0
        for i in range(start_idx, end_idx):  # range es exclusivo en el límite superior
                if i < len(marks):
                    is_correct = (marks[i].strip().upper() == "C")
                    if is_correct:
                # Sumar el puntaje de la pregunta si existe en el lookup
                        partial_score += points_lookup.get(i, 0.0)

                return round(partial_score, 6)
    
    def calculate_knowledge_aptitude_scores(self, student: Dict[str, Any], num_questions_total: int) -> Tuple[float, float]:
        """
        Calcula los puntajes de conocimientos y aptitud basándose en las asignaturas reales.
        Las asignaturas que empiezan con "Aptitud" son de aptitud, las demás son de conocimientos.
        """
        # Obtener las asignaturas y sus rangos (nivel-aware)
        subjects_map = {}
        try:
            subjects_map = self.academic_service.get_weights_for_student(student) or {}
        except Exception as e:
            print(f"Error obteniendo ponderaciones para calcular conocimientos/aptitud: {e}")
            return 0.0, 0.0
            
        conocimientos_score = 0.0
        aptitud_score = 0.0
        
        # Calcular puntajes por área
        
        # Iterar sobre las asignaturas y sus rangos
        for key, value in subjects_map.items():
            if isinstance(key, tuple) and len(key) == 2 and isinstance(value, tuple) and len(value) == 3:
                try:
                    start, end = int(key[0]), int(key[1])
                    subject, level, weight = value
                    
                    if start > 0 and end >= start:
                        # Calcular el puntaje para este rango
                        partial_score = self.calculate_partial_score(student, start, end)
                        
                        # Determinar si es conocimiento o aptitud basándose en el nombre de la asignatura
                        if subject.startswith('Aptitud'):
                            aptitud_score += partial_score
                        else:
                            conocimientos_score += partial_score
                            
                except (ValueError, TypeError) as e:
                    print(f"Error procesando rango {key} para conocimientos/aptitud: {e}")
                    continue
        
        return round(conocimientos_score, 6), round(aptitud_score, 6)

    def calculate_consolidated_data(self, student: Dict[str, Any]) -> Tuple[List[List[Any]], int, int, int, float]:
        """
        Calcula los datos consolidados por asignatura (correctas, incorrectas, etc.)
        y los totales generales.
        """
        responses_str = student.get('responses', '')
        pri_keys_str = student.get('pri_keys', '')
        marks_str = student.get('marks', '')

        # Determinar el número total de preguntas de forma más robusta
        responses = responses_str.split(',') if responses_str else []
        pri_keys = pri_keys_str.split(',') if pri_keys_str else []
        marks = marks_str.split(',') if marks_str else []
        num_questions_total = 0
        if pri_keys and pri_keys != ['']: num_questions_total = len(pri_keys)
        else: num_questions_total = max(len(marks), len(responses), 0)

        if num_questions_total == 0:
             print("Advertencia: No hay datos de preguntas (claves, marcas, respuestas) para consolidar.")
             return [], 0, 0, 0, 0.0

        try:
            academic_area_id = int(student.get('academic_area_id', 1))
        except (ValueError, TypeError):
            academic_area_id = 1

        consolidated_data = []
        total_correct = 0
        total_wrong = 0
        total_blank = 0
        total_points_obtained = 0.0
        processed_questions_indices = set() # Para rastrear preguntas ya asignadas a una asignatura

        # Obtener pesos y lookup de puntos (nivel-aware)
        nivel = student.get('nivel') or 'ACADEMIA'
        points_lookup = self._get_points_lookup_for_student(student, num_questions_total)
        subjects_map = {}
        try:
             subjects_map = self.academic_service.get_weights_for_student(student) or {}
        except Exception as e:
             print(f"Error obteniendo ponderaciones para consolidado: {e}")
             # Continuar sin ponderaciones puede ser posible si solo se cuentan C/W/B
        
        # CORRECCIÓN: Filtrar asignaturas por área académica
        valid_subjects = set()
        for (start, end), (subject, level, weight) in subjects_map.items():
            valid_subjects.add(subject)
        
        print(f"Debug: Área {academic_area_id}, Asignaturas válidas: {sorted(valid_subjects)}")

        # Validar y ordenar los rangos de preguntas
        valid_question_ranges = []
        for key, value in subjects_map.items():
            if isinstance(key, tuple) and len(key) == 2 and isinstance(value, tuple) and len(value) == 3:
                try:
                    start, end = int(key[0]), int(key[1])
                    if start > 0 and end >= start:
                        valid_question_ranges.append(((start, end), value))
                except (ValueError, TypeError):
                    print(f"Advertencia: Rango inválido {key} en ponderaciones.")
                    pass # Ignorar rango inválido
            else:
                 print(f"Advertencia: Formato de ponderación inválido omitido: key={key}, value={value}")

        # Ordenar por pregunta inicial para procesar en orden
        valid_question_ranges.sort(key=lambda item: item[0][0])

        # Procesar cada asignatura/rango
        for (start, end), subject_data in valid_question_ranges:
            subject, level, points_per_question_str = subject_data
            try:
                points_per_question_float = float(points_per_question_str)
            except (ValueError, TypeError):
                points_per_question_float = 0.0 # Peso 0 si no es numérico

            correct_subj = 0
            wrong_subj = 0
            blank_subj = 0
            subject_total_points = 0.0
            questions_in_this_range_count = 0

            # Iterar sobre las preguntas DENTRO del rango definido (índices 0-based)
            start_idx = start - 1
            end_idx = min(end, num_questions_total) # Asegurar no exceder el total real

            for i in range(start_idx, end_idx):
                if i in processed_questions_indices:
                     # Evitar doble conteo si los rangos se solapan (aunque no deberían)
                     continue

                questions_in_this_range_count += 1
                processed_questions_indices.add(i)

                # Obtener marca, asegurando que el índice es válido
                mark = marks[i].strip().upper() if i < len(marks) else ''

                if mark == "C":
                    correct_subj += 1
                    # Usar el puntaje del lookup general (más preciso si pesos varían dentro de un rango amplio)
                    subject_total_points += points_lookup.get(i, 0.0)
                elif mark == "" or mark == "-": # Considerar respuesta vacía como en blanco
                    blank_subj += 1
                else: # Cualquier otra marca (E, X, etc.) se considera incorrecta
                    wrong_subj += 1

            # Recalcular blancos por si faltaron marcas al final
            if questions_in_this_range_count > (correct_subj + wrong_subj + blank_subj):
                 blank_subj = questions_in_this_range_count - (correct_subj + wrong_subj)

            # Calcular rendimiento textual para la asignatura
            performance_text = self.calculate_performance_text(correct_subj, questions_in_this_range_count)

            consolidated_data.append([
                subject, # Nombre Asignatura
                level, # Nivel (Nuevo)
                points_per_question_float, # Peso "nominal" del rango (puede diferir del real si varía)
                correct_subj, # Correctas
                wrong_subj, # Incorrectas
                blank_subj, # En Blanco
                questions_in_this_range_count, # Total Preguntas en Rango
                round(subject_total_points, 3), # Puntaje Obtenido en Asignatura
                performance_text # Rendimiento Textual
            ])

            # Acumular totales generales
            total_correct += correct_subj
            total_wrong += wrong_subj
            # total_blank se calculará al final para mayor precisión
            total_points_obtained += subject_total_points

        # Calcular total en blanco final basado en las preguntas no procesadas o el total general
        total_processed = total_correct + total_wrong
        total_blank = max(0, num_questions_total - total_processed)

        # Verificación final (opcional)
        if total_correct + total_wrong + total_blank != num_questions_total:
            print(f"ADVERTENCIA: Conteo C({total_correct})+W({total_wrong})+B({total_blank}) = {total_correct+total_wrong+total_blank} != Total Q({num_questions_total})")

        # FILTRAR: Solo asignaturas válidas para el área académica
        filtered_consolidated_data = []
        for row in consolidated_data:
            if len(row) > 0:
                subject = row[0]  # Primera columna es la asignatura
                if subject in valid_subjects:
                    filtered_consolidated_data.append(row)
                else:
                    print(f"Asignatura '{subject}' excluida (no pertenece al área {academic_area_id})")
        
        print(f"Debug: Asignaturas filtradas: {len(filtered_consolidated_data)}/{len(consolidated_data)}")
        
        return filtered_consolidated_data, total_correct, total_wrong, total_blank, round(total_points_obtained, 3)

    # ==========================================================================
    # Métodos de Dibujo en PDF (Privados)
    # ==========================================================================

    def _draw_titles(self, pdf: fpdf.FPDF):
        """ Dibuja los títulos principales centrados en la parte superior. """
        initial_y = pdf.get_y() # Guardar Y actual
        title_y = HEADER_HEIGHT_MM + 5 # Posición Y después de la imagen del header
        pdf.set_y(title_y)
        pdf.set_font("Arial", "B", 14)
        pdf.set_text_color(*PURPLE_RGB)
        pdf.cell(0, 6, self._encode_text("BOLETA DE NOTAS"), 0, 1, 'C')
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, self._encode_text("EXAMEN TIPO ADMISIÓN"), 0, 1, 'C')
        pdf.set_y(initial_y) # Restaurar Y para el contenido
        pdf.set_text_color(*BLACK_RGB) # Resetear color

    def _draw_exam_info_header(self, pdf: fpdf.FPDF, student: Dict[str, Any]):
        """ Dibuja la cabecera con información del área/nivel, ciclo y fecha. """
        nivel = student.get('nivel') or 'ACADEMIA'
        area_name_raw = "Área desconocida"
        if nivel != 'ACADEMIA':
            grado = student.get('quiz_class', '')
            area_name_raw = f"{nivel} - {grado}° grado"
        else:
            try:
                area_id = int(student.get('academic_area_id', 1))
                if hasattr(self.academic_service, 'get_academic_area_name'):
                     area_name_raw = self.academic_service.get_academic_area_name(area_id) or area_name_raw
                else:
                     area_name_raw = student.get('academic_area_name', area_name_raw)
            except Exception as e:
                print(f"Error obteniendo nombre de área: {e}")

        academic_area_name = self._display_value(area_name_raw)

        # Formatear fecha
        quiz_date_str = student.get('quiz_created')
        formatted_date_raw = "Fecha no disponible"
        if quiz_date_str:
            try:
                # Intentar parsear formatos comunes (ajustar según el formato real de 'quiz_created')
                dt_obj = None
                for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d", "%d/%m/%Y"):
                     try:
                         dt_obj = datetime.datetime.strptime(quiz_date_str, fmt)
                         break
                     except ValueError:
                         continue
                if dt_obj and locale_set:
                     # Formato largo con nombre de mes en español
                     formatted_date_raw = dt_obj.strftime("%d de %B de %Y").capitalize()
                elif dt_obj:
                     formatted_date_raw = dt_obj.strftime("%d/%m/%Y") # Fallback si locale falló
            except Exception as e:
                 print(f"Error formateando fecha '{quiz_date_str}': {e}")

        formatted_date = self._display_value(formatted_date_raw)
        ciclo_val = student.get('ciclo', str(datetime.datetime.now().year)) # Ciclo por defecto = año actual
        ciclo = self._display_value(ciclo_val)

        # Dibujar rectángulo y texto
        pdf.set_fill_color(*LIGHT_GREY_RGB)
        pdf.rect(BASE_MARGIN_LR, pdf.get_y(), pdf.w - 2 * BASE_MARGIN_LR, 16, 'F') # Ancho completo menos márgenes
        pdf.set_text_color(*BLACK_RGB)
        pdf.set_font("Arial", "B", 9)
        y_start_box = pdf.get_y() + 2 # Pequeño padding superior
        x_start_text = BASE_MARGIN_LR + 2 # Pequeño padding izquierdo

        pdf.set_xy(x_start_text, y_start_box)
        pdf.cell(30, 6, self._encode_text("Área Académica:"), 0, 0, 'L')
        pdf.set_font("Arial", "", 9)
        pdf.cell(100, 6, self._encode_text(academic_area_name), 0, 0, 'L')
        pdf.set_font("Arial", "", 9) # Asegurar fuente para fecha
        pdf.cell(pdf.w - 2 * BASE_MARGIN_LR - 130 - 10, 6, self._encode_text(formatted_date), 0, 1, 'R') # Ajustar ancho restante

        pdf.set_xy(x_start_text, pdf.get_y())
        pdf.set_font("Arial", "B", 9)
        pdf.cell(30, 6, self._encode_text("Ciclo Semestral:"), 0, 0, 'L')
        pdf.set_font("Arial", "", 9)
        pdf.cell(60, 6, self._encode_text(ciclo), 0, 1, 'L')
        pdf.ln(6) # Espacio después de la cabecera

    def _draw_student_info_table(self, pdf: fpdf.FPDF, student: Dict[str, Any]):
        """ Dibuja la tabla con la información básica del estudiante. """
        pdf.set_fill_color(*PURPLE_RGB)
        pdf.set_text_color(*WHITE_RGB)
        pdf.set_font("Arial", "B", 8)
        col_widths = [30, 90, 35, 35] # Código, Estudiante, Carrera, DNI
        headers = ["Código", "Estudiante", "Carrera", "DNI"]
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 6, self._encode_text(header), 1, 0, 'C', 1)
        pdf.ln()

        # Obtener y formatear datos del estudiante
        st_code_raw = student.get('student_id') # Este es el ID/Código del estudiante, no el PK de la DB
        st_code = self._display_value(st_code_raw)

        fname = student.get('first_name', '')
        lname = student.get('last_name', '')
        full_n_raw = f"{fname} {lname}".strip()
        full_n = self._display_value(full_n_raw, "No disponible")

        career_raw = student.get('custom_id') # Asumiendo que custom_id es la carrera
        career = self._display_value(career_raw)

        # Intentar extraer DNI del código si es posible, o usar un campo específico si existe
        dni_val = str(st_code_raw) if st_code_raw else ''
        # Asumiendo DNI de 8 dígitos, intentar extraer o formatear
        dni_raw = dni_val[:8] if len(dni_val) >= 8 else dni_val.zfill(8) if dni_val.isdigit() else "N/A"
        dni = self._display_value(dni_raw)

        # Dibujar fila de datos
        pdf.set_fill_color(*LIGHT_GREY_RGB)
        pdf.set_text_color(*BLACK_RGB)
        pdf.set_font("Arial", "", 8)
        data = [st_code, full_n, career, dni]
        aligns = ['C', 'L', 'C', 'C']
        for i, item in enumerate(data):
            pdf.cell(col_widths[i], 6, self._encode_text(item), 1, 0, aligns[i], 1)
        pdf.ln()
        pdf.ln(2) # Espacio después de la tabla

    def _draw_response_table(self, pdf: fpdf.FPDF, student: Dict[str, Any]):
        """ Dibuja la(s) tabla(s) de claves correctas y respuestas del estudiante. """
        responses_str = student.get('responses', '')
        pri_keys_str = student.get('pri_keys', '')
        responses = responses_str.split(',') if responses_str else []
        pri_keys = pri_keys_str.split(',') if pri_keys_str else []

        num_questions_total = 0
        if pri_keys and pri_keys != ['']: num_questions_total = len(pri_keys)
        else: num_questions_total = max(len(responses), 0)

        if num_questions_total == 0:
            pdf.set_font("Arial", "I", 8)
            pdf.cell(0, 6, self._encode_text("No hay datos de respuestas disponibles."), 0, 1, 'C')
            pdf.ln(5)
            return

        pdf.set_font("Arial", "B", 9)
        pdf.set_fill_color(*LIGHT_GREY_RGB)
        pdf.set_text_color(*BLACK_RGB)
        pdf.cell(0, 6, self._encode_text("CLAVES CORRECTAS Y RESPUESTAS DEL ESTUDIANTE"), 1, 1, 'C', 1)

        # Calcular ancho de celda dinámicamente
        available_width = pdf.w - 2 * BASE_MARGIN_LR - 7 # Ancho total menos márgenes menos ancho de columna 'N°'
        # Determinar cuántas preguntas caben por fila (mínimo ancho 3.5mm)
        max_q_per_row = math.floor(available_width / 3.5) if available_width > 0 else 50 # 50 como fallback
        cell_w = available_width / max_q_per_row if max_q_per_row > 0 else 3.5
        cell_w = max(3.5, cell_w) # Asegurar mínimo

        def draw_single_row(start_q, end_q):
            if start_q > num_questions_total: return
            actual_end_q = min(end_q, num_questions_total)

            pdf.set_font("Arial", "B", 6)
            pdf.set_fill_color(*PURPLE_RGB)
            pdf.set_text_color(*WHITE_RGB)
            pdf.cell(7, 4, self._encode_text("N°"), 1, 0, 'C', 1)
            current_x = pdf.get_x()
            for i in range(start_q, actual_end_q + 1):
                pdf.cell(cell_w, 4, str(i), 1, 0, 'C', 1)
            pdf.ln()

            pdf.set_xy(pdf.l_margin, pdf.get_y()) # Asegurar alineación
            pdf.set_fill_color(*LIGHT_GREY_RGB)
            pdf.set_text_color(*BLACK_RGB)
            pdf.cell(7, 4, self._encode_text("Clave"), 1, 0, 'C', 1)
            pdf.set_x(current_x) # Alinear con celdas de números
            for i in range(start_q - 1, actual_end_q):
                key = pri_keys[i].strip().upper() if i < len(pri_keys) else ""
                pdf.cell(cell_w, 4, self._encode_text(key), 1, 0, 'C', 1)
            pdf.ln()

            pdf.set_xy(pdf.l_margin, pdf.get_y()) # Asegurar alineación
            pdf.set_fill_color(*WHITE_RGB)
            pdf.set_text_color(*BLACK_RGB)
            pdf.cell(7, 4, self._encode_text("Resp."), 1, 0, 'C', 1)
            pdf.set_x(current_x) # Alinear con celdas de números
            for i in range(start_q - 1, actual_end_q):
                resp = responses[i].strip().upper() if i < len(responses) else ""
                key = pri_keys[i].strip().upper() if i < len(pri_keys) else ""
                fill_c = WHITE_RGB
                text_c = BLACK_RGB
                # Colorear fondo si hay clave y respuesta
                if key and resp:
                    if resp == key: fill_c = GREEN_BG; text_c = GREEN_TEXT
                    else: fill_c = RED_BG; text_c = RED_TEXT
                elif not resp and key: # Respuesta en blanco
                     fill_c = GREY_BG; text_c = GREY_TEXT
                     resp = "-" # Mostrar guion para blanco

                pdf.set_fill_color(*fill_c)
                pdf.set_text_color(*text_c)
                pdf.cell(cell_w, 4, self._encode_text(resp), 1, 0, 'C', 1)
            pdf.ln(5) # Espacio después de cada bloque de respuestas
            pdf.set_text_color(*BLACK_RGB) # Restaurar color de texto

        # Dibujar en bloques según cuántas caben por fila
        for block_start in range(1, num_questions_total + 1, max_q_per_row):
            draw_single_row(block_start, block_start + max_q_per_row - 1)

    def _draw_consolidated_table(self, pdf: fpdf.FPDF, student: Dict[str, Any]):
        """ Dibuja la tabla consolidada de rendimiento por asignatura. """
        pdf.set_font("Arial", "B", 9)
        pdf.set_fill_color(*LIGHT_GREY_RGB)
        pdf.set_text_color(*BLACK_RGB)
        pdf.cell(0, 6, self._encode_text("CONSOLIDADO DE RENDIMIENTO POR ASIGNATURA"), 1, 1, 'C', 1)

        # Cabeceras de la tabla
        pdf.set_font("Arial", "B", 6)
        pdf.set_fill_color(*PURPLE_RGB)
        pdf.set_text_color(*WHITE_RGB)
        col_widths = [45, 15, 12, 10, 10, 10, 10, 17, 51] # Ajustado ancho rendimiento
        headers = ["ASIGNATURA", "NIVEL", "PESO", "BIEN", "MAL", "BLANCO", "TOTAL Q.", "PUNTAJE", "RENDIMIENTO"]
        # Dibujar cabeceras
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 4, self._encode_text(header), 1, 0, 'C', 1)
        pdf.ln()

        # Obtener datos consolidados
        consolidated_data, total_correct, total_wrong, total_blank, total_points = self.calculate_consolidated_data(student)
        num_questions_total = total_correct + total_wrong + total_blank

        if not consolidated_data:
             pdf.set_font("Arial", "I", 8)
             pdf.cell(sum(col_widths), 6, self._encode_text("No hay datos consolidados disponibles."), 1, 1, 'C')
             return # Salir si no hay datos

        # Dibujar filas de datos
        pdf.set_text_color(*BLACK_RGB)
        pdf.set_font("Arial", "", 6)
        for row in consolidated_data:
            # Desempaquetar datos (ahora incluye nivel)
            subj_raw, level_raw, peso_val, bien, mal, blanco, total_q, puntaje_val, perf_raw = row

            subj = self._display_value(subj_raw, "Asignatura?")
            level = self._display_value(level_raw, "-")
            perf = self._display_value(perf_raw, "N/A")
            peso = f"{peso_val:.3f}" if isinstance(peso_val, (int, float)) else "-"
            puntaje = f"{puntaje_val:.3f}" if isinstance(puntaje_val, (int, float)) else "-"

            # Determinar colores según rendimiento
            bg_color, bar_color, _text_color = self._get_performance_style(perf)
            pdf.set_fill_color(*bg_color)
            fill = True

            # Dibujar celdas de datos
            data_cells = [subj, level, peso, str(bien), str(mal), str(blanco), str(total_q), puntaje]
            aligns = ['L', 'C', 'C', 'C', 'C', 'C', 'C', 'C']
            for i, item in enumerate(data_cells):
                 pdf.cell(col_widths[i], 4, self._encode_text(str(item)), 1, 0, aligns[i], fill)

            # Dibujar celda de rendimiento con barra de progreso
            prog_w = col_widths[-1] # Ancho de la última columna
            bar_x = pdf.get_x()
            bar_y = pdf.get_y()

            # Celda contenedora de la barra (con fondo blanco para contraste)
            pdf.set_fill_color(*WHITE_RGB)
            pdf.cell(prog_w, 4, "", 1, 0, 'L', 1) # Borde 1, Fondo blanco (fill=1)

            # Calcular y dibujar barra de progreso
            q_correct = int(bien)
            q_total_range = int(total_q)
            percentage = (q_correct / q_total_range) * 100 if q_total_range > 0 else 0
            bar_margin = 0.5
            bar_height = 3
            max_bar_width = prog_w - (2 * bar_margin)
            bar_width = max(0, (max_bar_width * percentage / 100))
            actual_bar_x = bar_x + bar_margin
            actual_bar_y = bar_y + (4 - bar_height) / 2 # Centrar verticalmente

            pdf.set_fill_color(*bar_color)
            pdf.rect(actual_bar_x, actual_bar_y, bar_width, bar_height, 'F')

            # Escribir texto de rendimiento sobre la barra (alineado a la derecha)
            text_x = bar_x + prog_w - 18 # Ajustar posición X para texto
            text_y = bar_y
            pdf.set_xy(text_x, text_y)
            pdf.set_font("Arial", "B", 6)
            pdf.set_text_color(*DARK_GREY_RGB) # Usar gris oscuro para el texto
            pdf.cell(17, 4, self._encode_text(perf.upper()), 0, 0, 'R') # Sin borde, alineado derecha

            pdf.ln() # Nueva línea para la siguiente asignatura
            pdf.set_font("Arial", "", 6) # Restaurar fuente normal
            pdf.set_text_color(*BLACK_RGB) # Restaurar color texto

        # --- Fila de Totales ---
        pdf.set_font("Arial", "B", 6)
        pdf.set_fill_color(*LIGHT_GREY_RGB)
        pdf.set_text_color(*BLACK_RGB)
        fill = True
        total_correct_perc = round((total_correct / num_questions_total) * 100, 1) if num_questions_total > 0 else 0

        # Celdas vacías hasta 'BIEN'
        pdf.cell(col_widths[0] + col_widths[1] + col_widths[2], 4, "TOTALES", 1, 0, 'C', fill)
        # Datos totales
        pdf.cell(col_widths[3], 4, str(total_correct), 1, 0, 'C', fill)
        pdf.cell(col_widths[4], 4, str(total_wrong), 1, 0, 'C', fill)
        pdf.cell(col_widths[5], 4, str(total_blank), 1, 0, 'C', fill)
        pdf.cell(col_widths[6], 4, str(num_questions_total), 1, 0, 'C', fill)
        pdf.cell(col_widths[7], 4, f"{total_points:.3f}", 1, 0, 'C', fill)
        # Celda final con resumen de correctas
        summary_text = f"{total_correct}/{num_questions_total} correctas ({total_correct_perc}%)"
        pdf.cell(col_widths[8], 4, self._encode_text(summary_text), 1, 1, 'C', fill)

    def _draw_partial_scores(self, pdf: fpdf.FPDF, student: Dict[str, Any]):
         """ Dibuja los cuadros con los puntajes parciales de Conocimientos y Aptitud. """
         pdf.ln(5) # Espacio antes

         # --- Usar los mismos datos que calculate_consolidated_data para total consistencia ---
         consolidated_data, total_correct, total_wrong, total_blank, total_points = self.calculate_consolidated_data(student)
         num_questions_total = total_correct + total_wrong + total_blank
         
         # Calcular conocimientos y aptitud sumando por tipo de asignatura (mismo método que _draw_final_summary)
         conocimientos_obtained = 0.0
         aptitud_obtained = 0.0
         
         for row in consolidated_data:
             subject, level, peso, correct, wrong, blank, total_q, points, performance = row
             if subject.startswith('Aptitud'):
                 aptitud_obtained += points
             else:
                 conocimientos_obtained += points

         # --- Calcular puntajes vigesimals (escalados usando el total posible) ---
         total_possible = self._calculate_total_possible_for_student(student, num_questions_total)
         calculation_possible = total_possible > 0
         
         conocimientos_vigesimal = 0.0
         aptitud_vigesimal = 0.0
         
         if calculation_possible:
             # Escalar usando el total posible de TODAS las preguntas (no solo del rango)
             conocimientos_vigesimal = round(max(0, min(20, (conocimientos_obtained / total_possible) * 20)), 3)
             aptitud_vigesimal = round(max(0, min(20, (aptitud_obtained / total_possible) * 20)), 3)


         # --- Dibujar cuadros ---
         current_y = pdf.get_y()
         box_h = 16 # Alto total del cuadro (cabecera + contenido)
         box_w = 80 # Ancho de cada cuadro
         space_bw = 10 # Espacio entre cuadros
         total_w = (box_w * 2) + space_bw
         start_x = (pdf.w - total_w) / 2 # Centrar horizontalmente

         # Cuadro Conocimientos
         pdf.set_xy(start_x, current_y)
         pdf.set_fill_color(*PURPLE_RGB); pdf.set_text_color(*WHITE_RGB) # Cabecera
         pdf.set_font("Arial", "B", 9); pdf.cell(box_w, 6, self._encode_text("PUNTAJE CONOCIMIENTOS"), 1, 2, 'C', 1) # ln=2 para mover cursor abajo
         pdf.set_xy(start_x, pdf.get_y()) # Alinear contenido con cabecera
         pdf.set_fill_color(*WHITE_RGB); pdf.set_text_color(*DARK_GREY_RGB) # Contenido
         pdf.set_font("Arial", "B", 12); pdf.cell(box_w, 10, f"{conocimientos_vigesimal:.3f}" if calculation_possible else '---', 1, 0, 'C', 0) # Mostrar vigesimal

         # Cuadro Aptitud
         apt_start_x = start_x + box_w + space_bw
         pdf.set_xy(apt_start_x, current_y)
         pdf.set_fill_color(*PURPLE_RGB); pdf.set_text_color(*WHITE_RGB) # Cabecera
         pdf.set_font("Arial", "B", 9); pdf.cell(box_w, 6, self._encode_text("PUNTAJE APTITUD"), 1, 2, 'C', 1)
         pdf.set_xy(apt_start_x, pdf.get_y()) # Alinear contenido
         pdf.set_fill_color(*WHITE_RGB); pdf.set_text_color(*DARK_GREY_RGB) # Contenido
         pdf.set_font("Arial", "B", 12); pdf.cell(box_w, 10, f"{aptitud_vigesimal:.3f}" if calculation_possible else '---', 1, 0, 'C', 0) # Mostrar vigesimal

         pdf.set_y(current_y + box_h) # Mover cursor debajo de los cuadros
         pdf.ln(5) # Espacio después
         pdf.set_text_color(*BLACK_RGB) # Restaurar color

    def _draw_final_summary(self, pdf: fpdf.FPDF, student: Dict[str, Any], totals: tuple):
         """ Dibuja el resumen final: Puntos obtenidos, Correctas y Nota Vigesimal. """
         consolidated_data, total_correct, _total_wrong, _total_blank, total_points_from_consolidated = totals
         num_questions_total = len(student.get('pri_keys', '').split(',')) if student.get('pri_keys') else 0
         total_possible = self._calculate_total_possible_for_student(student, num_questions_total)
         
         # USAR LOS MISMOS DATOS que calculate_consolidated_data para consistencia total
         # Calcular conocimientos y aptitud sumando por tipo de asignatura
         conocimientos_obtained = 0.0
         aptitud_obtained = 0.0
         
         for row in consolidated_data:
             subject, level, peso, correct, wrong, blank, total_q, points, performance = row
             if subject.startswith('Aptitud'):
                 aptitud_obtained += points
             else:
                 conocimientos_obtained += points
         
         # Usar el total de puntos de calculate_consolidated_data
         total_points_obtained = total_points_from_consolidated
         
         # Calcular vigesimals usando la misma base que el resto del sistema
         conocimientos_vigesimal = 0.0
         aptitud_vigesimal = 0.0
         if total_possible > 0:
             conocimientos_vigesimal = round(max(0, min(20, (conocimientos_obtained / total_possible) * 20)), 3)
             aptitud_vigesimal = round(max(0, min(20, (aptitud_obtained / total_possible) * 20)), 3)
         
         # La nota final es la suma de ambos vigesimals
         note_vigesimal = conocimientos_vigesimal + aptitud_vigesimal

         # --- Filas de Puntos y Correctas ---
         pdf.set_font("Arial", "B", 8)
         pdf.set_fill_color(*LIGHT_GREY_RGB)
         pdf.set_text_color(*BLACK_RGB)
         fill = True
         column_width = (pdf.w - 2 * BASE_MARGIN_LR) / 2 # Dividir ancho disponible en 2

         # Mostrar puntos brutos obtenidos vs total posible (NO vigesimal)
         pdf.cell(column_width, 6, self._encode_text("PUNTOS OBTENIDOS:"), 1, 0, 'R', fill)
         pdf.cell(column_width, 6, f"{total_points_obtained:.3f} / {total_possible:.3f}", 1, 1, 'C', fill)

         pdf.set_x(pdf.l_margin) # Volver al margen izquierdo
         total_correct_perc = round((total_correct / num_questions_total) * 100, 1) if num_questions_total > 0 else 0
         pdf.cell(column_width, 6, self._encode_text("CORRECTAS:"), 1, 0, 'R', fill)
         pdf.cell(column_width, 6, f"{total_correct}/{num_questions_total} ({total_correct_perc}%)", 1, 1, 'C', fill)

         pdf.ln(5) # Espacio antes de la nota vigesimal

         # --- Cuadro Nota Vigesimal ---
         evaluation = "No Calculable"
         calculation_possible = total_possible > 0

         if calculation_possible:
             # Definir umbrales para evaluación
             if note_vigesimal >= 14: evaluation = "Bueno"
             elif note_vigesimal >= 10.5: evaluation = "Regular"
             else: evaluation = "En Proceso" # Incluye 0 hasta 10.499

         # Determinar colores
         bg_color, _bar_color, text_color = self._get_performance_style(evaluation)

         # Dibujar cuadro centrado
         box_w = 90; box_h = 24
         box_x = (pdf.w - box_w) / 2
         box_y = pdf.get_y()

         pdf.set_fill_color(*bg_color)
         pdf.rect(box_x, box_y, box_w, box_h, 'F') # Fondo
         pdf.set_draw_color(*text_color) # Borde del color del texto
         pdf.set_line_width(0.5)
         pdf.rect(box_x, box_y, box_w, box_h) # Borde

         # Texto dentro del cuadro
         pdf.set_text_color(*text_color)
         pdf.set_xy(box_x, box_y + 2) # Posicionar texto con padding
         pdf.set_font("Arial", "B", 12)
         pdf.cell(box_w, 6, self._encode_text("NOTA VIGESIMAL"), 0, 1, 'C')

         pdf.set_xy(box_x, pdf.get_y())
         pdf.set_font("Arial", "B", 14)
         pdf.cell(box_w, 8, f"{note_vigesimal:.3f}" if calculation_possible else '---', 0, 1, 'C')

         pdf.set_xy(box_x, pdf.get_y())
         pdf.set_font("Arial", "B", 10)
         pdf.cell(box_w, 6, self._encode_text(evaluation.upper()), 0, 1, 'C')

         # Restaurar colores y línea
         pdf.set_text_color(*BLACK_RGB)
         pdf.set_draw_color(*BLACK_RGB)
         pdf.set_line_width(0.2)
         pdf.set_y(box_y + box_h) # Mover cursor debajo del cuadro

    def _draw_final_message(self, pdf: fpdf.FPDF):
        """ Dibuja el mensaje motivacional final. """
        pdf.ln(5) # Espacio antes
        pdf.set_font("Arial", "B", 8)
        pdf.set_text_color(*PURPLE_RGB)
        pdf.cell(0, 4, self._encode_text("¡NO SERÁ FÁCIL, PERO VALDRÁ LA PENA!"), 0, 1, 'C')
        pdf.set_text_color(*BLACK_RGB) # Restaurar color

    def _save_pdf(self, pdf: fpdf.FPDF, student: Dict[str, Any]) -> str:
        """ Guarda el objeto PDF en un archivo. """
        # Crear nombre de archivo seguro
        student_id_field = student.get('student_id', 'unknown_id') # Usar el ID del estudiante, no el PK de DB
        safe_student_id = "".join(c if c.isalnum() else "_" for c in str(student_id_field))
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S_UTC')
        pdf_output_filename = f"Boleta_{safe_student_id}_{timestamp}.pdf" # Nombre más descriptivo

        # Determinar directorio de salida
        intended_output_dir = student.get('output_dir', "reports") # Permitir especificar directorio
        final_output_dir = None
        try:
            # Crear directorio si no existe
            if not os.path.exists(intended_output_dir):
                os.makedirs(intended_output_dir)
                print(f"Directorio creado: {os.path.abspath(intended_output_dir)}")

            # Verificar permisos de escritura
            if os.access(intended_output_dir, os.W_OK | os.X_OK):
                final_output_dir = intended_output_dir
            else:
                raise OSError(f"Sin permisos de escritura en el directorio destino: '{intended_output_dir}'")

        except OSError as e:
            print(f"Advertencia: Problema con directorio destino '{intended_output_dir}': {e}.")
            # Intentar guardar en el directorio actual como fallback
            current_dir = "."
            print(f"Intentando usar directorio actual: {os.path.abspath(current_dir)}")
            if os.access(current_dir, os.W_OK):
                final_output_dir = current_dir
            else:
                error_msg = f"Error Crítico: Sin permisos de escritura ni en '{intended_output_dir}' ni en el directorio actual."
                print(error_msg)
                raise IOError(error_msg) from e # Relanzar como IOError

        if final_output_dir is None:
             # Esto no debería ocurrir si la lógica anterior funciona, pero por seguridad
             raise RuntimeError("No se pudo determinar un directorio de salida válido para el PDF.")

        # Guardar el archivo
        pdf_output_path = os.path.join(final_output_dir, pdf_output_filename)
        try:
            pdf.output(pdf_output_path)
            abs_path = os.path.abspath(pdf_output_path)
            print(f"PDF generado exitosamente: {abs_path}")
            return abs_path
        except Exception as e:
            # Capturar errores específicos de FPDF si es posible
            print(f"Error Crítico al guardar PDF en {pdf_output_path}: {e}")
            raise IOError(f"No se pudo guardar el PDF: {e}") from e # Relanzar como IOError

    # ==========================================================================
    # Método Público Principal
    # ==========================================================================

    def generate_pdf(self, student: Dict[str, Any]) -> str:
        """
        Genera el informe PDF completo para un estudiante dado.

        Args:
            student (Dict[str, Any]): Diccionario con todos los datos del estudiante
                                      y los resultados del examen.

        Returns:
            str: La ruta absoluta al archivo PDF generado.

        Raises:
            ValueError: Si faltan datos esenciales del estudiante.
            IOError: Si hay problemas al guardar el archivo PDF.
            Exception: Otros errores inesperados durante la generación.
        """
        # --- Validación de Datos Esenciales ---
        # Ajustar según los campos realmente indispensables para la generación
        required_keys = ['student_id', 'academic_area_id', 'marks', 'pri_keys'] # 'responses' es opcional?
        for key in required_keys:
            if student.get(key) is None: # Verificar None explícitamente
                raise ValueError(f"Falta dato requerido o es None en los datos del estudiante: '{key}'.")
        # Validar que pri_keys no esté vacío si existe
        if not student.get('pri_keys', '').strip():
             raise ValueError("El campo 'pri_keys' está vacío o ausente, no se puede generar el reporte.")

        # --- Clase PDF Interna (con acceso a paths de imágenes) ---
        class PDFReport(fpdf.FPDF):
            # Pasar las rutas como atributos de clase para que header/footer las usen
            img_header_path = self.header_img_path
            img_footer_path = self.footer_img_path

            def header(self):
                if self.img_header_path: # Ya validamos que existe en __init__
                    try:
                        # Dibujar imagen de encabezado ocupando el ancho y alto definidos
                        self.image(self.img_header_path, x=0, y=0, w=self.w, h=HEADER_HEIGHT_MM)
                    except Exception as e:
                        # Loggear o imprimir error si falla la inserción de la imagen
                        print(f"Error al insertar imagen de encabezado '{self.img_header_path}': {e}")
                # Posicionar el cursor para el contenido principal (después del header y títulos)
                # El margen superior ya se aplica, set_y asegura empezar ahí
                self.set_y(BASE_MARGIN_TOP_CONTENT)

            def footer(self):
                if self.img_footer_path: # Ya validamos que existe en __init__
                    try:
                        # Dibujar imagen de pie de página en la parte inferior
                        self.image(self.img_footer_path, x=0, y=self.h - FOOTER_HEIGHT_MM, w=self.w, h=FOOTER_HEIGHT_MM)
                    except Exception as e:
                        print(f"Error al insertar imagen de pie '{self.img_footer_path}': {e}")

                # --- Texto del pie de página ---
                # Posición relativa desde el fondo (-15mm)
                self.set_y(-15)
                self.set_font('Arial', 'I', 7) # Fuente pequeña e itálica
                self.set_text_color(128) # Color gris

                # Texto de Copyright centrado
                copyright_text = self._outer_instance._encode_text(f"© {datetime.datetime.now().year} NK Chambergo")
                self.cell(0, 5, copyright_text, 0, 0, 'C')

                # Número de página a la derecha
                page_num_text = self._outer_instance._encode_text(f'Página {self.page_no()}/{{nb}}')
                self.cell(0, 5, page_num_text, 0, 0, 'R')

        # --- Creación e Inicialización del PDF ---
        pdf = PDFReport(orientation='P', unit='mm', format='A4')
        pdf._outer_instance = self # Dar acceso a la instancia de PDFService para _encode_text
        pdf.alias_nb_pages() # Habilitar numeración total de páginas {nb}
        pdf.set_margins(BASE_MARGIN_LR, BASE_MARGIN_TOP_CONTENT, BASE_MARGIN_LR)
        pdf.set_auto_page_break(auto=True, margin=BASE_MARGIN_BOTTOM_CONTENT)
        pdf.add_page()

        # --- Dibujar Contenido ---
        try:
            self._draw_titles(pdf)
            self._draw_exam_info_header(pdf, student)
            self._draw_student_info_table(pdf, student)
            self._draw_response_table(pdf, student)
            self._draw_consolidated_table(pdf, student)
            self._draw_partial_scores(pdf, student)
             # Calcular totales una vez para pasar a _draw_final_summary
            totals = self.calculate_consolidated_data(student)
            self._draw_final_summary(pdf, student, totals)
            self._draw_final_message(pdf)

        except Exception as draw_error:
             # Capturar errores durante el dibujo para evitar PDF corrupto
             print(f"Error durante la generación del contenido del PDF: {draw_error}")
             # Considerar si se debe intentar guardar un PDF parcial o lanzar error
             raise RuntimeError(f"Fallo al dibujar contenido del PDF: {draw_error}") from draw_error

        # --- Guardar el PDF ---
        # El método _save_pdf maneja la creación de directorio y el guardado final
        pdf_output_path = self._save_pdf(pdf, student)

        return pdf_output_path

    def generate_merit_ranking_pdf(self, students_sorted, career_name, eta_number,
                                   generation_date, passing_score=10.5, output_dir="reports"):
        """
        Genera un PDF del ranking de mérito de ETAs.
        Retorna la ruta absoluta al archivo generado.
        """
        # --- Clase PDF interna — mismo patrón que PDFReport (boleta) ---
        class MeritPDF(fpdf.FPDF):
            # Rutas como atributos de clase (igual que PDFReport)
            img_header_path = self.header_img_path
            img_footer_path = self.footer_img_path

            def header(self):
                if self.img_header_path:
                    try:
                        self.image(self.img_header_path, x=0, y=0,
                                   w=self.w, h=HEADER_HEIGHT_MM)
                    except Exception as e:
                        print(f"Error al insertar imagen de encabezado: {e}")
                self.set_y(BASE_MARGIN_TOP_CONTENT)

            def footer(self):
                if self.img_footer_path:
                    try:
                        self.image(self.img_footer_path,
                                   x=0, y=self.h - FOOTER_HEIGHT_MM,
                                   w=self.w, h=FOOTER_HEIGHT_MM)
                    except Exception as e:
                        print(f"Error al insertar imagen de pie: {e}")
                self.set_y(-15)
                self.set_font('Arial', 'I', 7)
                self.set_text_color(128)
                # Igual que boleta: copyright centrado + página a la derecha
                copyright_text = self._outer_instance._encode_text(
                    "\xa9 2025 NK Chambergo")
                self.cell(0, 5, copyright_text, 0, 0, 'C')
                page_num_text = self._outer_instance._encode_text(
                    f'P\xe1gina {self.page_no()}/{{nb}}')
                self.cell(0, 5, page_num_text, 0, 0, 'R')

        pdf = MeritPDF(orientation='L', unit='mm', format='A4')
        pdf._outer_instance = self          # igual que boleta
        pdf.alias_nb_pages()
        pdf.set_margins(BASE_MARGIN_LR, BASE_MARGIN_TOP_CONTENT, BASE_MARGIN_LR)
        pdf.set_auto_page_break(auto=True, margin=BASE_MARGIN_BOTTOM_CONTENT)
        pdf.add_page()

        enc = self._encode_text  # alias; self aquí es la instancia de PDFService

        # --- Títulos ---
        eta_str = f"ETA N\xb0 {eta_number:02d}" if eta_number else "TODAS LAS ETAs"
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(*PURPLE_RGB)
        pdf.cell(0, 8, enc(f"RESULTADO EN ORDEN DE MERITO - {eta_str}"), 0, 1, 'C')

        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(*DARK_GREY_RGB)
        pdf.cell(0, 6, enc(career_name), 0, 1, 'C')
        pdf.ln(3)

        # --- Cabecera de tabla ---
        # A4 landscape usable width ≈ 277 mm (297 - 2×10 margins)
        col_w = [10, 22, 95, 28, 28, 32, 40]
        headers = ['N\xb0', 'COD.', 'APELLIDOS Y NOMBRES',
                   'P.Conoc', 'P.Aptit', 'NOTA VIGES.', 'OBSERVACION']

        pdf.set_font('Arial', 'B', 9)
        pdf.set_fill_color(*MEDIUM_GREY_RGB)
        pdf.set_text_color(*DARK_GREY_RGB)
        for h, w in zip(headers, col_w):
            pdf.cell(w, 8, enc(h), 1, 0, 'C', fill=True)
        pdf.ln()

        # --- Filas ---
        pdf.set_font('Arial', '', 9)
        for idx, student in enumerate(students_sorted, 1):
            nota = float(student.get('nota_vigesimal', 0))
            obs  = student.get('observation', 'EN PROCESO')
            aprueba = nota >= passing_score

            if aprueba:
                pdf.set_fill_color(*GREEN_BG)
                pdf.set_text_color(*GREEN_TEXT)
            else:
                pdf.set_fill_color(255, 255, 255)
                pdf.set_text_color(*DARK_GREY_RGB)

            pdf.cell(col_w[0], 7, str(idx), 1, 0, 'C', fill=aprueba)
            pdf.cell(col_w[1], 7,
                     enc(str(student.get('student_id', ''))), 1, 0, 'C', fill=aprueba)
            nombre = enc(f"{student.get('last_name','')}, {student.get('first_name','')}")
            pdf.cell(col_w[2], 7, nombre, 1, 0, 'L', fill=aprueba)
            pdf.cell(col_w[3], 7,
                     f"{float(student.get('conocimientos', 0)):.3f}", 1, 0, 'C', fill=aprueba)
            pdf.cell(col_w[4], 7,
                     f"{float(student.get('aptitud', 0)):.3f}", 1, 0, 'C', fill=aprueba)

            pdf.set_font('Arial', 'B', 9)
            pdf.cell(col_w[5], 7, f"{nota:.3f}", 1, 0, 'C', fill=aprueba)
            pdf.set_font('Arial', '', 9)
            pdf.cell(col_w[6], 7, enc(obs), 1, 0, 'C', fill=aprueba)
            pdf.ln()

        # --- Pie informativo (dentro del área de contenido, antes del footer imagen) ---
        pdf.set_text_color(*DARK_GREY_RGB)
        pdf.ln(3)
        pdf.set_font('Arial', 'I', 8)
        pdf.set_text_color(100, 100, 100)
        total_txt = enc(f"Total: {len(students_sorted)} estudiante(s)  |  "
                        f"Puntaje de corte: {passing_score}  |  "
                        f"Generado: {generation_date}")
        pdf.cell(0, 5, total_txt, 0, 0, 'R')

        # --- Guardar ---
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = career_name.replace(' ', '_').replace('/', '-')[:30]
        filename = f"ReporteMerito_{safe_name}_{timestamp}.pdf"
        path = os.path.join(output_dir, filename)
        pdf.output(path)
        return os.path.abspath(path)

    def generate_results_pdf(self, students, area_name=None, eta_number=None,
                              output_dir="reports"):
        """
        Genera un PDF con la tabla de resultados de ETAs (mismo formato que las otras boletas).
        """
        class ResultsPDF(fpdf.FPDF):
            img_header_path = self.header_img_path
            img_footer_path = self.footer_img_path

            def header(self):
                if self.img_header_path:
                    try:
                        self.image(self.img_header_path, x=0, y=0,
                                   w=self.w, h=HEADER_HEIGHT_MM)
                    except Exception as e:
                        print(f"Error al insertar imagen de encabezado: {e}")
                self.set_y(BASE_MARGIN_TOP_CONTENT)

            def footer(self):
                if self.img_footer_path:
                    try:
                        self.image(self.img_footer_path,
                                   x=0, y=self.h - FOOTER_HEIGHT_MM,
                                   w=self.w, h=FOOTER_HEIGHT_MM)
                    except Exception as e:
                        print(f"Error al insertar imagen de pie: {e}")
                self.set_y(-15)
                self.set_font('Arial', 'I', 7)
                self.set_text_color(128)
                copyright_text = self._outer_instance._encode_text(
                    "\xa9 2025 NK Chambergo")
                self.cell(0, 5, copyright_text, 0, 0, 'C')
                page_num_text = self._outer_instance._encode_text(
                    f'P\xe1gina {self.page_no()}/{{nb}}')
                self.cell(0, 5, page_num_text, 0, 0, 'R')

        pdf = ResultsPDF(orientation='L', unit='mm', format='A4')
        pdf._outer_instance = self
        pdf.alias_nb_pages()
        pdf.set_margins(BASE_MARGIN_LR, BASE_MARGIN_TOP_CONTENT, BASE_MARGIN_LR)
        pdf.set_auto_page_break(auto=True, margin=BASE_MARGIN_BOTTOM_CONTENT)
        pdf.add_page()

        enc = self._encode_text

        # --- Titulo ---
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(*PURPLE_RGB)
        titulo = "RESULTADOS DE EVALUACIONES TIPO ADMISION"
        pdf.cell(0, 8, enc(titulo), 0, 1, 'C')

        # Subtitulo con filtros
        subtitulo_parts = []
        if area_name:
            subtitulo_parts.append(area_name)
        if eta_number:
            subtitulo_parts.append(f"ETA N\xb0 {eta_number:02d}")
        else:
            subtitulo_parts.append("TODAS LAS ETAs")

        if subtitulo_parts:
            pdf.set_font('Arial', 'B', 11)
            pdf.set_text_color(*DARK_GREY_RGB)
            pdf.cell(0, 6, enc(" - ".join(subtitulo_parts)), 0, 1, 'C')

        generation_date = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        pdf.set_font('Arial', 'I', 8)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, enc(f"Fecha de generaci\xf3n: {generation_date}"), 0, 1, 'R')
        pdf.ln(2)

        # --- Estadisticas resumen ---
        total = len(students)
        buenos = sum(1 for s in students
                     if s.get('percent_correct') is not None
                     and float(s.get('percent_correct', 0)) >= 70)
        en_proceso = total - buenos

        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(*DARK_GREY_RGB)
        pdf.cell(0, 5, enc(f"Total registros: {total}  |  Buenos: {buenos}  |  En proceso: {en_proceso}"), 0, 1, 'L')
        pdf.ln(2)

        # --- Cabecera de tabla ---
        # A4 landscape usable width = 277mm
        col_w = [12, 22, 80, 40, 40, 30, 25, 28]
        headers = ['N\xb0', 'COD.', 'ESTUDIANTE', 'QUIZ CLASS', '\xc1REA ACAD\xc9MICA',
                   'PUNTAJE', '%', 'ESTADO']

        pdf.set_font('Arial', 'B', 8)
        pdf.set_fill_color(*PURPLE_RGB)
        pdf.set_text_color(*WHITE_RGB)
        for h, w in zip(headers, col_w):
            pdf.cell(w, 7, enc(h), 1, 0, 'C', fill=True)
        pdf.ln()

        # --- Filas de datos ---
        pdf.set_font('Arial', '', 7)
        for idx, student in enumerate(students, 1):
            percent = float(student.get('percent_correct', 0) or 0)
            earned = float(student.get('earned_points', 0) or 0)
            possible = float(student.get('possible_points', 0) or 0)

            # Color de fila segun rendimiento
            if percent >= 70:
                pdf.set_fill_color(*GREEN_BG)
                pdf.set_text_color(*GREEN_TEXT)
                estado = "Bueno"
            elif percent >= 50:
                pdf.set_fill_color(*YELLOW_BG)
                pdf.set_text_color(*YELLOW_TEXT)
                estado = "Regular"
            else:
                pdf.set_fill_color(*RED_BG)
                pdf.set_text_color(*RED_TEXT)
                estado = "En Proceso"

            fill = True
            nombre = enc(f"{student.get('first_name', '')} {student.get('last_name', '')}")
            quiz_class = enc(str(student.get('quiz_class', '') or ''))
            area = enc(str(student.get('academic_area_name', 'Sin \xe1rea') or 'Sin \xe1rea'))
            puntaje = f"{earned:.3f}/{possible:.3f}"

            pdf.cell(col_w[0], 6, str(idx), 1, 0, 'C', fill)
            pdf.cell(col_w[1], 6, enc(str(student.get('student_id', ''))), 1, 0, 'C', fill)
            pdf.cell(col_w[2], 6, nombre, 1, 0, 'L', fill)
            pdf.cell(col_w[3], 6, quiz_class, 1, 0, 'C', fill)
            pdf.cell(col_w[4], 6, area, 1, 0, 'C', fill)
            pdf.cell(col_w[5], 6, puntaje, 1, 0, 'C', fill)
            pdf.cell(col_w[6], 6, f"{percent:.1f}%", 1, 0, 'C', fill)
            pdf.cell(col_w[7], 6, enc(estado), 1, 0, 'C', fill)
            pdf.ln()

        # --- Pie informativo ---
        pdf.set_text_color(*DARK_GREY_RGB)
        pdf.ln(3)
        pdf.set_font('Arial', 'I', 8)
        pdf.set_text_color(100, 100, 100)
        total_txt = enc(f"Total: {len(students)} registro(s)  |  Generado: {generation_date}")
        pdf.cell(0, 5, total_txt, 0, 0, 'R')

        # --- Guardar ---
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"ReporteResultadosETAs_{timestamp}.pdf"
        path = os.path.join(output_dir, filename)
        pdf.output(path)
        return os.path.abspath(path)

    def generate_fast_test_pdf(self, estudiante, grilla, cursos, sesiones,
                               aula_nombre='', anio_escolar='', dni='',
                               output_dir="reports"):
        """
        Genera un PDF de notas Fast Test con encabezado y pie institucional.
        """
        class FastTestPDF(fpdf.FPDF):
            img_header_path = self.header_img_path
            img_footer_path = self.footer_img_path

            def header(self):
                if self.img_header_path:
                    try:
                        self.image(self.img_header_path, x=0, y=0,
                                   w=self.w, h=HEADER_HEIGHT_MM)
                    except Exception as e:
                        print(f"Error al insertar imagen de encabezado: {e}")
                self.set_y(BASE_MARGIN_TOP_CONTENT)

            def footer(self):
                if self.img_footer_path:
                    try:
                        self.image(self.img_footer_path,
                                   x=0, y=self.h - FOOTER_HEIGHT_MM,
                                   w=self.w, h=FOOTER_HEIGHT_MM)
                    except Exception as e:
                        print(f"Error al insertar imagen de pie: {e}")
                self.set_y(-15)
                self.set_font('Arial', 'I', 7)
                self.set_text_color(128)
                copyright_text = self._outer_instance._encode_text(
                    "\xa9 2025 NK Chambergo")
                self.cell(0, 5, copyright_text, 0, 0, 'C')
                page_num_text = self._outer_instance._encode_text(
                    f'P\xe1gina {self.page_no()}/{{nb}}')
                self.cell(0, 5, page_num_text, 0, 0, 'R')

        # Landscape para tablas anchas
        pdf = FastTestPDF(orientation='L', unit='mm', format='A4')
        pdf._outer_instance = self
        pdf.alias_nb_pages()
        pdf.set_margins(BASE_MARGIN_LR, BASE_MARGIN_TOP_CONTENT, BASE_MARGIN_LR)
        pdf.set_auto_page_break(auto=True, margin=BASE_MARGIN_BOTTOM_CONTENT)
        pdf.add_page()

        enc = self._encode_text

        # --- Titulo ---
        pdf.set_font('Arial', 'B', 14)
        pdf.set_text_color(*PURPLE_RGB)
        pdf.cell(0, 8, enc("CONTROL DE CALIFICACIONES FAST TEST"), 0, 1, 'C')

        pdf.set_font('Arial', 'B', 11)
        pdf.set_text_color(*DARK_GREY_RGB)
        subtitulo = f"A\xf1o Escolar {anio_escolar}"
        if aula_nombre:
            subtitulo += f"  |  {aula_nombre}"
        pdf.cell(0, 6, enc(subtitulo), 0, 1, 'C')
        pdf.ln(2)

        # --- Info estudiante ---
        nombre_completo = ''
        if estudiante:
            nombre_completo = f"{getattr(estudiante, 'apellido_paterno_est', '')} {getattr(estudiante, 'apellido_materno_est', '')}, {getattr(estudiante, 'nombres_est', '')}"

        pdf.set_font('Arial', 'B', 9)
        pdf.set_fill_color(*LIGHT_GREY_RGB)
        pdf.cell(25, 7, enc("Alumno:"), 1, 0, 'L', fill=True)
        pdf.set_font('Arial', '', 9)
        pdf.cell(120, 7, enc(nombre_completo), 1, 0, 'L')
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(15, 7, enc("DNI:"), 1, 0, 'L', fill=True)
        pdf.set_font('Arial', '', 9)
        pdf.cell(30, 7, enc(str(dni)), 1, 1, 'L')
        pdf.ln(3)

        if not cursos or not sesiones:
            pdf.set_font('Arial', 'I', 10)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 10, enc(f"Sin notas registradas para el a\xf1o {anio_escolar}"), 0, 1, 'C')
        else:
            # --- Calcular anchos ---
            num_sesiones = len(sesiones)
            asig_width = 60
            prom_width = 20
            available = pdf.w - 2 * BASE_MARGIN_LR - asig_width - prom_width
            ses_width = min(18, available / max(1, num_sesiones))

            # --- Cabecera tabla ---
            pdf.set_font('Arial', 'B', 7)
            pdf.set_fill_color(*PURPLE_RGB)
            pdf.set_text_color(*WHITE_RGB)
            pdf.cell(asig_width, 7, enc("ASIGNATURA"), 1, 0, 'C', fill=True)
            for s in sesiones:
                pdf.cell(ses_width, 7, enc(str(s)), 1, 0, 'C', fill=True)
            pdf.set_fill_color(95, 42, 93)
            pdf.cell(prom_width, 7, enc("PROM."), 1, 1, 'C', fill=True)

            # --- Filas de datos ---
            pdf.set_font('Arial', '', 8)
            for curso in cursos:
                fila = grilla.get(curso, {})
                pdf.set_text_color(*DARK_GREY_RGB)
                pdf.set_fill_color(*WHITE_RGB)
                pdf.cell(asig_width, 6, enc(str(curso)), 1, 0, 'L')

                suma = 0.0
                count = 0
                for s in sesiones:
                    nota_obj = fila.get(s)
                    if nota_obj:
                        es_nsp = getattr(nota_obj, 'observaciones', '') == 'N.S.P.'
                        nota_val = getattr(nota_obj, 'nota', None)
                        if es_nsp:
                            pdf.set_text_color(*RED_TEXT)
                            pdf.cell(ses_width, 6, "N.S.P.", 1, 0, 'C')
                            count += 1
                        elif nota_val is not None:
                            if nota_val >= 14:
                                pdf.set_text_color(*GREEN_TEXT)
                            elif nota_val >= 11:
                                pdf.set_text_color(*YELLOW_TEXT)
                            else:
                                pdf.set_text_color(*RED_TEXT)
                            nota_str = str(int(nota_val)) if nota_val == int(nota_val) else f"{nota_val:.1f}"
                            pdf.cell(ses_width, 6, nota_str, 1, 0, 'C')
                            suma += nota_val
                            count += 1
                        else:
                            pdf.set_text_color(180, 180, 180)
                            pdf.cell(ses_width, 6, enc("\u2014"), 1, 0, 'C')
                    else:
                        pdf.set_text_color(180, 180, 180)
                        pdf.cell(ses_width, 6, enc("\u2014"), 1, 0, 'C')

                # Promedio
                if count > 0:
                    prom = suma / count
                    if prom >= 14:
                        pdf.set_text_color(*GREEN_TEXT)
                    elif prom >= 11:
                        pdf.set_text_color(*YELLOW_TEXT)
                    else:
                        pdf.set_text_color(*RED_TEXT)
                    pdf.set_font('Arial', 'B', 8)
                    pdf.set_fill_color(*LIGHT_GREY_RGB)
                    pdf.cell(prom_width, 6, f"{prom:.1f}", 1, 0, 'C', fill=True)
                    pdf.set_font('Arial', '', 8)
                else:
                    pdf.set_text_color(180, 180, 180)
                    pdf.set_fill_color(*LIGHT_GREY_RGB)
                    pdf.cell(prom_width, 6, enc("\u2014"), 1, 0, 'C', fill=True)
                pdf.ln()

            # --- Leyenda ---
            pdf.ln(3)
            pdf.set_font('Arial', 'I', 7)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 4, enc("Logro (\u2265 14)  |  En Proceso (11-13)  |  Inicio (< 11)  |  N.S.P. (No se present\xf3)"), 0, 1, 'L')

        # --- Fecha ---
        generation_date = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        pdf.ln(2)
        pdf.set_font('Arial', 'I', 8)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, enc(f"Generado: {generation_date}"), 0, 0, 'R')

        # --- Guardar ---
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = dni.replace(' ', '_')[:20] if dni else 'estudiante'
        filename = f"FastTest_{safe_name}_{timestamp}.pdf"
        path = os.path.join(output_dir, filename)
        pdf.output(path)
        return os.path.abspath(path)

# --- Fin de la clase PDFService ---
