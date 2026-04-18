# -*- coding: utf-8 -*-
"""
Extensión del PDFService para generar reportes consolidados de ETAs.

Este módulo extiende la funcionalidad del PDFService existente para crear
reportes que muestran el historial completo de ETAs de un estudiante.
"""

import os
import datetime
from typing import Dict, List, Any, Optional
import fpdf

# Importar las constantes del PDFService original
PURPLE_RGB = (69, 3, 140)
WHITE_RGB = (255, 255, 255)
LIGHT_GREY_RGB = (240, 240, 240)
MEDIUM_GREY_RGB = (211, 211, 211)
DARK_GREY_RGB = (50, 50, 50)
BLACK_RGB = (0, 0, 0)
GREEN_BG = (220, 240, 220); GREEN_BAR = (0, 180, 0); GREEN_TEXT = (0, 100, 0)
YELLOW_BG = (255, 243, 224); YELLOW_BAR = (255, 180, 0); YELLOW_TEXT = (200, 120, 0)
RED_BG = (250, 220, 220); RED_BAR = (220, 0, 0); RED_TEXT = (180, 0, 0); RED_RGB = (220, 0, 0)
GREY_BG = (230, 230, 230); GREY_TEXT = (100, 100, 100)

HEADER_HEIGHT_MM = 30
FOOTER_HEIGHT_MM = 25
BASE_MARGIN_LR = 10
BASE_MARGIN_TOP_CONTENT = HEADER_HEIGHT_MM + 15
BASE_MARGIN_BOTTOM_CONTENT = FOOTER_HEIGHT_MM + 5

class ETAPDFGenerator:
    """
    Generador de PDFs consolidados para análisis de ETAs.
    
    Esta clase extiende la funcionalidad del PDFService existente
    para crear reportes que muestran múltiples ETAs de un estudiante.
    """

    def __init__(self, pdf_service, eta_analysis_service):
        """
        Inicializa el generador de PDFs de ETA.

        Args:
            pdf_service: Instancia del PDFService original
            eta_analysis_service: Servicio de análisis de ETAs
        """
        self.pdf_service = pdf_service
        self.eta_analysis_service = eta_analysis_service

    def generate_eta_summary_pdf(self, student_id: str, output_dir: str = "reports") -> str:
        """
        Genera un PDF consolidado con el resumen de todas las ETAs de un estudiante.

        Args:
            student_id: ID del estudiante
            output_dir: Directorio donde guardar el PDF

        Returns:
            str: Ruta al archivo PDF generado

        Raises:
            ValueError: Si el estudiante no se encuentra
            IOError: Si hay problemas al generar o guardar el PDF
        """
        # Obtener datos del estudiante
        eta_history = self.eta_analysis_service.get_student_eta_history(student_id)
        
        if not eta_history.get('student_found', False):
            raise ValueError(f"Estudiante con ID {student_id} no encontrado.")

        student_info = eta_history['student_info']
        etas = eta_history['etas']
        summary = eta_history['summary']

        if not etas:
            raise ValueError(f"No se encontraron ETAs para el estudiante {student_id}.")

        # Crear PDF personalizado
        class ETAReportPDF(fpdf.FPDF):
            img_header_path = self.pdf_service.header_img_path
            img_footer_path = self.pdf_service.footer_img_path

            def header(self):
                if self.img_header_path:
                    try:
                        self.image(self.img_header_path, x=0, y=0, w=self.w, h=HEADER_HEIGHT_MM)
                    except Exception as e:
                        print(f"Error al insertar imagen de encabezado: {e}")
                self.set_y(BASE_MARGIN_TOP_CONTENT)

            def footer(self):
                if self.img_footer_path:
                    try:
                        self.image(self.img_footer_path, x=0, y=self.h - FOOTER_HEIGHT_MM, w=self.w, h=FOOTER_HEIGHT_MM)
                    except Exception as e:
                        print(f"Error al insertar imagen de pie: {e}")

                self.set_y(-15)
                self.set_font('Arial', 'I', 7)
                self.set_text_color(128)
                copyright_text = self.pdf_service._encode_text("© 2025 NK Chambergo")
                self.cell(0, 5, copyright_text, 0, 0, 'C')
                page_num_text = self.pdf_service._encode_text(f'Página {self.page_no()}/{{nb}}')
                self.cell(0, 5, page_num_text, 0, 0, 'R')

        # Crear instancia del PDF
        pdf = ETAReportPDF(orientation='P', unit='mm', format='A4')
        pdf.pdf_service = self.pdf_service  # Dar acceso al PDFService
        pdf.alias_nb_pages()
        pdf.set_margins(BASE_MARGIN_LR, BASE_MARGIN_TOP_CONTENT, BASE_MARGIN_LR)
        pdf.set_auto_page_break(auto=True, margin=BASE_MARGIN_BOTTOM_CONTENT)
        pdf.add_page()

        # Generar contenido del PDF
        self._draw_eta_report_content(pdf, student_info, etas, summary)

        # Guardar PDF
        pdf_path = self._save_eta_pdf(pdf, student_info, output_dir)
        return pdf_path

    def _draw_eta_report_content(self, pdf: fpdf.FPDF, student_info: Dict[str, Any], 
                                etas: List[Dict[str, Any]], summary: Dict[str, Any]):
        """Dibuja todo el contenido del reporte de ETAs."""
        
        # Guardar datos para uso en métodos secundarios
        self._current_eta_history = {'etas': etas, 'summary': summary, 'student_info': student_info}
        
        # Títulos principales
        self._draw_eta_titles(pdf)
        
        # Información del estudiante
        self._draw_eta_student_info(pdf, student_info, summary)
        
        # Resumen ejecutivo
        self._draw_eta_executive_summary(pdf, summary)
        
        # Tabla de ETAs
        self._draw_eta_table(pdf, etas)
        
        # Gráfico de tendencias (simplificado)
        self._draw_eta_trends(pdf, etas)
        
        # NUEVA TABLA CONSOLIDADA (Formato Materias x ETAs)
        eta_data_by_subject = summary.get('eta_data_by_subject', {})
        if eta_data_by_subject:
            self._draw_consolidated_subjects_table(pdf, eta_data_by_subject)
        
        # Análisis por asignatura (tradicional)
        self._draw_subject_analysis(pdf, summary.get('subject_averages', {}))
        
        # Recomendaciones
        self._draw_recommendations(pdf, summary)
        
        # Limpiar datos temporales
        self._current_eta_history = None

    def _draw_eta_titles(self, pdf: fpdf.FPDF):
        """Dibuja los títulos del reporte de ETAs."""
        pdf.set_font("Arial", "B", 16)
        pdf.set_text_color(*PURPLE_RGB)
        pdf.cell(0, 8, self.pdf_service._encode_text("REPORTE CONSOLIDADO DE ETAs"), 0, 1, 'C')
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 6, self.pdf_service._encode_text("HISTORIAL ACADÉMICO COMPLETO"), 0, 1, 'C')
        pdf.ln(5)
        pdf.set_text_color(*BLACK_RGB)

    def _draw_eta_student_info(self, pdf: fpdf.FPDF, student_info: Dict[str, Any], summary: Dict[str, Any]):
        """Dibuja la información básica del estudiante."""
        pdf.set_fill_color(*LIGHT_GREY_RGB)
        pdf.rect(BASE_MARGIN_LR, pdf.get_y(), pdf.w - 2 * BASE_MARGIN_LR, 20, 'F')
        
        pdf.set_font("Arial", "B", 10)
        y_start = pdf.get_y() + 3
        
        # Línea 1: Datos personales
        pdf.set_xy(BASE_MARGIN_LR + 3, y_start)
        pdf.cell(30, 5, self.pdf_service._encode_text("Estudiante:"), 0, 0, 'L')
        pdf.set_font("Arial", "", 10)
        name = f"{student_info.get('first_name', '')} {student_info.get('last_name', '')}"
        pdf.cell(80, 5, self.pdf_service._encode_text(name), 0, 0, 'L')
        
        pdf.set_font("Arial", "B", 10)
        pdf.cell(25, 5, self.pdf_service._encode_text("Código:"), 0, 0, 'L')
        pdf.set_font("Arial", "", 10)
        pdf.cell(50, 5, self.pdf_service._encode_text(str(student_info.get('student_id', ''))), 0, 1, 'L')
        
        # Línea 2: Área académica
        pdf.set_xy(BASE_MARGIN_LR + 3, pdf.get_y())
        pdf.set_font("Arial", "B", 10)
        pdf.cell(30, 5, self.pdf_service._encode_text("Área:"), 0, 0, 'L')
        pdf.set_font("Arial", "", 10)
        area_name = student_info.get('academic_area_name', 'No especificada')
        pdf.cell(80, 5, self.pdf_service._encode_text(area_name), 0, 0, 'L')
        
        pdf.set_font("Arial", "B", 10)
        pdf.cell(25, 5, self.pdf_service._encode_text("ETAs:"), 0, 0, 'L')
        pdf.set_font("Arial", "", 10)
        eta_count = f"{summary.get('valid_etas', 0)} válidas de {summary.get('total_etas', 0)} total"
        pdf.cell(50, 5, self.pdf_service._encode_text(eta_count), 0, 1, 'L')
        
        # Línea 3: Promedio general
        pdf.set_xy(BASE_MARGIN_LR + 3, pdf.get_y())
        pdf.set_font("Arial", "B", 10)
        pdf.cell(30, 5, self.pdf_service._encode_text("Promedio:"), 0, 0, 'L')
        pdf.set_font("Arial", "B", 12)
        avg_score = summary.get('average_score', 0)
        color = GREEN_TEXT if avg_score >= 10.5 else RED_TEXT
        pdf.set_text_color(*color)
        pdf.cell(30, 5, f"{avg_score:.3f}", 0, 0, 'L')
        pdf.set_text_color(*BLACK_RGB)
        
        pdf.set_font("Arial", "B", 10)
        pdf.cell(25, 5, self.pdf_service._encode_text("Tendencia:"), 0, 0, 'L')
        pdf.set_font("Arial", "", 10)
        trend = summary.get('trend', 'estable').upper()
        trend_color = GREEN_TEXT if trend == 'MEJORANDO' else RED_TEXT if trend == 'DECLINANDO' else DARK_GREY_RGB
        pdf.set_text_color(*trend_color)
        pdf.cell(50, 5, self.pdf_service._encode_text(trend), 0, 1, 'L')
        pdf.set_text_color(*BLACK_RGB)
        
        pdf.ln(8)

    def _draw_eta_executive_summary(self, pdf: fpdf.FPDF, summary: Dict[str, Any]):
        """Dibuja el resumen ejecutivo."""
        pdf.set_font("Arial", "B", 11)
        pdf.set_fill_color(*PURPLE_RGB)
        pdf.set_text_color(*WHITE_RGB)
        pdf.cell(0, 6, self.pdf_service._encode_text("RESUMEN EJECUTIVO"), 1, 1, 'C', 1)
        
        # Crear tabla de resumen
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(*BLACK_RGB)
        
        col_widths = [47.5, 47.5, 47.5, 47.5]  # 4 columnas iguales
        
        # Fila 1
        pdf.set_fill_color(*LIGHT_GREY_RGB)
        pdf.cell(col_widths[0], 5, self.pdf_service._encode_text("Mejor ETA"), 1, 0, 'C', 1)
        pdf.cell(col_widths[1], 5, self.pdf_service._encode_text("Peor ETA"), 1, 0, 'C', 1)
        pdf.cell(col_widths[2], 5, self.pdf_service._encode_text("ETAs Aprobatorias"), 1, 0, 'C', 1)
        pdf.cell(col_widths[3], 5, self.pdf_service._encode_text("Tasa de Éxito"), 1, 1, 'C', 1)
        
        # Fila 2 - Datos
        pdf.set_fill_color(*WHITE_RGB)
        best_eta = summary.get('best_eta', {})
        worst_eta = summary.get('worst_eta', {})
        
        best_text = f"ETA {best_eta.get('eta_number', '?')} ({best_eta.get('score', 0):.2f})"
        worst_text = f"ETA {worst_eta.get('eta_number', '?')} ({worst_eta.get('score', 0):.2f})"
        passing_text = f"{summary.get('passing_etas_count', 0)} ETAs"
        rate_text = f"{summary.get('passing_rate', 0):.1f}%"
        
        pdf.cell(col_widths[0], 5, self.pdf_service._encode_text(best_text), 1, 0, 'C', 1)
        pdf.cell(col_widths[1], 5, self.pdf_service._encode_text(worst_text), 1, 0, 'C', 1)
        pdf.cell(col_widths[2], 5, self.pdf_service._encode_text(passing_text), 1, 0, 'C', 1)
        pdf.cell(col_widths[3], 5, self.pdf_service._encode_text(rate_text), 1, 1, 'C', 1)
        
        pdf.ln(5)

    def _draw_eta_table(self, pdf: fpdf.FPDF, etas: List[Dict[str, Any]]):
        """Dibuja la tabla de ETAs."""
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(*PURPLE_RGB)
        pdf.set_text_color(*WHITE_RGB)
        pdf.cell(0, 6, self.pdf_service._encode_text("DETALLE DE ETAs"), 1, 1, 'C', 1)
        
        # Cabeceras
        pdf.set_font("Arial", "B", 8)
        col_widths = [15, 60, 20, 20, 20, 20, 25]
        headers = ["ETA", "EXAMEN", "CORRECT.", "PUNTAJE", "CONOC.", "APTITUD", "NOTA"]
        
        pdf.set_fill_color(*MEDIUM_GREY_RGB)
        pdf.set_text_color(*BLACK_RGB)
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 5, self.pdf_service._encode_text(header), 1, 0, 'C', 1)
        pdf.ln()
        
        # Datos de ETAs
        pdf.set_font("Arial", "", 7)
        for eta in etas:
            if eta.get('total_questions', 0) == 0:
                continue  # Saltar ETAs sin datos
            
            eta_num = eta.get('eta_number', '?')
            quiz_name = eta.get('quiz_name', '')[:25] + '...' if len(eta.get('quiz_name', '')) > 25 else eta.get('quiz_name', '')
            correctas = f"{eta.get('total_correct', 0)}/{eta.get('total_questions', 0)}"
            puntaje = f"{eta.get('total_points', 0):.2f}"
            conocimientos = f"{eta.get('conocimientos_score', 0):.2f}"
            aptitud = f"{eta.get('aptitud_score', 0):.2f}"
            nota = f"{eta.get('nota_vigesimal', 0):.3f}"
            
            # Color de fondo según rendimiento
            nota_val = eta.get('nota_vigesimal', 0)
            if nota_val >= 10.5:
                pdf.set_fill_color(*GREEN_BG)
            elif nota_val >= 7:
                pdf.set_fill_color(*YELLOW_BG)
            else:
                pdf.set_fill_color(*RED_BG)
            
            data = [str(eta_num), quiz_name, correctas, puntaje, conocimientos, aptitud, nota]
            aligns = ['C', 'L', 'C', 'C', 'C', 'C', 'C']
            
            for i, item in enumerate(data):
                pdf.cell(col_widths[i], 4, self.pdf_service._encode_text(item), 1, 0, aligns[i], 1)
            pdf.ln()
        
        pdf.ln(5)

    def _draw_eta_trends(self, pdf: fpdf.FPDF, etas: List[Dict[str, Any]]):
        """Dibuja un gráfico simplificado de tendencias."""
        valid_etas = [eta for eta in etas if eta.get('total_questions', 0) > 0]
        if len(valid_etas) < 2:
            return
        
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(*LIGHT_GREY_RGB)
        pdf.cell(0, 6, self.pdf_service._encode_text("EVOLUCIÓN DE RENDIMIENTO"), 1, 1, 'C', 1)
        
        # Área del gráfico
        graph_x = BASE_MARGIN_LR + 5
        graph_y = pdf.get_y() + 5
        graph_w = pdf.w - 2 * BASE_MARGIN_LR - 10
        graph_h = 30
        
        # Fondo del gráfico
        pdf.set_fill_color(*WHITE_RGB)
        pdf.rect(graph_x, graph_y, graph_w, graph_h, 'F')
        pdf.rect(graph_x, graph_y, graph_w, graph_h)
        
        # Línea de referencia (nota 10.5)
        pdf.set_draw_color(*RED_RGB)
        ref_y = graph_y + graph_h - (10.5 / 20 * graph_h)
        pdf.line(graph_x, ref_y, graph_x + graph_w, ref_y)
        
        # Puntos y líneas
        pdf.set_draw_color(*PURPLE_RGB)
        if len(valid_etas) > 1:
            prev_x = None
            prev_y = None
            
            for i, eta in enumerate(valid_etas):
                x = graph_x + (i / (len(valid_etas) - 1)) * graph_w
                nota = min(20, max(0, eta.get('nota_vigesimal', 0)))
                y = graph_y + graph_h - (nota / 20 * graph_h)
                
                # Dibujar línea desde el punto anterior
                if prev_x is not None:
                    pdf.line(prev_x, prev_y, x, y)
                
                # Dibujar punto
                pdf.set_fill_color(*PURPLE_RGB)
                pdf.ellipse(x - 1, y - 1, 2, 2, 'F')
                
                prev_x, prev_y = x, y
        
        pdf.set_y(graph_y + graph_h + 5)

    def _draw_consolidated_subjects_table(self, pdf: fpdf.FPDF, eta_data_by_subject: Dict[str, Dict[str, float]]):
        """
        Dibuja tabla consolidada con formato: Materias (filas) x ETAs (columnas) = Puntajes
        Similar al formato de la primera imagen de referencia.
        """
        if not eta_data_by_subject:
            return
        
        pdf.ln(3)
        pdf.set_font("Arial", "B", 12)
        pdf.set_fill_color(*PURPLE_RGB)
        pdf.set_text_color(*WHITE_RGB)
        pdf.cell(0, 8, self.pdf_service._encode_text("CONSOLIDADO DE CALIFICACIONES POR ASIGNATURA Y ETA"), 1, 1, 'C', 1)
        pdf.set_text_color(*BLACK_RGB)
        
        # Obtener todas las ETAs disponibles y ordenarlas
        all_etas = set()
        for subject_data in eta_data_by_subject.values():
            all_etas.update(subject_data.keys())
        
        # Filtrar ETAs válidas y ordenar (numeros primero, luego textos)
        valid_etas = [eta for eta in all_etas if eta != 'N/A']
        sorted_etas = sorted(valid_etas, key=lambda x: (len(str(x)), str(x)))
        
        if not sorted_etas:
            pdf.set_font("Arial", "I", 9)
            pdf.cell(0, 6, self.pdf_service._encode_text("No hay datos de ETAs disponibles para mostrar"), 0, 1, 'C')
            return
        
        # Calcular anchos de columna (ahora incluye columna NIVEL)
        asignatura_width = 50  # Ancho para columna de asignaturas (reducido)
        nivel_width = 20       # Ancho para columna de nivel
        available_width = pdf.w - 2 * BASE_MARGIN_LR - asignatura_width - nivel_width
        eta_width = min(12, available_width / max(1, len(sorted_etas)))  # Reducido para dar espacio al nivel
        
        # Dibujar cabeceras
        pdf.set_font("Arial", "B", 8)
        pdf.set_fill_color(*MEDIUM_GREY_RGB)
        
        # Cabecera de asignaturas
        pdf.cell(asignatura_width, 6, self.pdf_service._encode_text("ASIGNATURAS"), 1, 0, 'C', 1)
        
        # Cabecera de nivel
        pdf.cell(nivel_width, 6, self.pdf_service._encode_text("NIVEL"), 1, 0, 'C', 1)
        
        # Cabeceras de ETAs
        for eta in sorted_etas:
            eta_text = f"ETA {eta}" if str(eta).isdigit() else str(eta)
            pdf.cell(eta_width, 6, self.pdf_service._encode_text(eta_text), 1, 0, 'C', 1)
        pdf.ln()
        
        # Dibujar filas de datos
        pdf.set_font("Arial", "", 7)
        
        # Usar las asignaturas que realmente existen en los datos (dinámicamente)
        # y obtener sus niveles reales desde academic_service
        sorted_subjects = []
        
        # Obtener todas las asignaturas únicas de los datos
        all_subjects = list(eta_data_by_subject.keys())
        
        # Obtener el área académica del estudiante actual para determinar niveles
        academic_area_id = None
        student_info = getattr(self, '_current_eta_history', {}).get('student_info', {})
        if student_info:
            academic_area_id = student_info.get('academic_area_id')
        
        # Mapeo de asignaturas a niveles desde academic_service
        subject_to_level = {}
        if academic_area_id and hasattr(self, 'pdf_service') and hasattr(self.pdf_service, 'academic_service'):
            try:
                weights_map = self.pdf_service.academic_service.get_weights_by_area(academic_area_id)
                if weights_map:
                    for (q_start, q_end), (subject, level, weight) in weights_map.items():
                        # Si la asignatura ya existe, mantener el primer nivel encontrado
                        # (podría haber múltiples niveles para la misma asignatura)
                        if subject not in subject_to_level:
                            subject_to_level[subject] = level
            except Exception as e:
                print(f"Error obteniendo niveles de asignaturas: {e}")
        
        # Obtener asignaturas válidas del área académica para filtrar correctamente
        valid_area_subjects = set()
        if academic_area_id and hasattr(self, 'pdf_service') and hasattr(self.pdf_service, 'academic_service'):
            try:
                weights_map_for_filter = self.pdf_service.academic_service.get_weights_by_area(academic_area_id)
                for (start, end), (subject, level, weight) in weights_map_for_filter.items():
                    valid_area_subjects.add(subject)
            except Exception as e:
                print(f"Error obteniendo asignaturas válidas del área: {e}")
        
        # Filtrar las asignaturas en los datos solo a las del área
        filtered_eta_data_by_subject = {}
        for subject, data in eta_data_by_subject.items():
            if not valid_area_subjects or subject in valid_area_subjects:
                filtered_eta_data_by_subject[subject] = data
        
        # Usar los datos filtrados
        eta_data_by_subject = filtered_eta_data_by_subject
        all_subjects = list(eta_data_by_subject.keys())
        
        # Orden preferido para presentación (si existen en los datos)
        preferred_order = [
            'Aritmética', 'Aritmética',
            'Álgebra', 'Algebra', 
            'Estadística y Probabilidades',
            'Comunicación', 'Comunicacion',
            'Química', 'Quimica',
            'Física', 'Fisica',
            'Biología', 'Biologia',
            'Ecología', 'Ecologia',
            'Historia',
            'Geografía', 'Geografia',
            'Economía', 'Economia',
            'Psicología', 'Psicologia',
            'Cívica', 'Civica',
            'Filosofía', 'Filosofia',
            'Aptitud Lógico Matemático',
            'Aptitud Comunicativa',
            'Aptitud Comunicativa (Inglés)'
        ]
        
        # Primero agregar asignaturas en el orden preferido (si existen)
        for preferred_subject in preferred_order:
            for actual_subject in all_subjects:
                if (preferred_subject.lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u') == 
                    actual_subject.lower().replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')):
                    if actual_subject not in [s[0] for s in sorted_subjects]:
                        # Obtener el nivel real desde academic_service
                        level = subject_to_level.get(actual_subject, 'INTERMEDIO')
                        sorted_subjects.append((actual_subject, level))
                        break
        
        # Agregar cualquier asignatura restante que no esté en el orden preferido
        for subject in all_subjects:
            if subject not in [s[0] for s in sorted_subjects]:
                level = subject_to_level.get(subject, 'INTERMEDIO')
                sorted_subjects.append((subject, level))
        
        for subject_info in sorted_subjects:
            subject, level = subject_info
            subject_data = eta_data_by_subject[subject]
            
            # Nombre de la asignatura
            pdf.set_fill_color(*LIGHT_GREY_RGB)
            subject_display = subject[:30] + '...' if len(subject) > 30 else subject  # Reducido por la nueva columna
            pdf.cell(asignatura_width, 5, self.pdf_service._encode_text(subject_display), 1, 0, 'L', 1)
            
            # Nivel de la asignatura
            pdf.cell(nivel_width, 5, self.pdf_service._encode_text(level), 1, 0, 'C', 1)
            
            # Puntajes por ETA
            for eta in sorted_etas:
                puntaje = subject_data.get(eta, None)
                
                # Si no hay datos para esta ETA, verificar si la asignatura existe en esta ETA
                if puntaje is None:
                    # La asignatura no tuvo preguntas en esta ETA
                    pdf.set_fill_color(*GREY_BG)
                    puntaje_text = "N/A"
                elif puntaje == 0.0:
                    # La asignatura tuvo preguntas pero se obtuvieron 0 puntos
                    pdf.set_fill_color(*RED_BG)
                    puntaje_text = "0.00"
                else:
                    # Colorear según el puntaje (escala basada en el peso promedio)
                    if puntaje >= 3.0:  # Buen puntaje (60%+)
                        pdf.set_fill_color(*GREEN_BG)
                    elif puntaje >= 1.5:  # Puntaje regular (30-59%)
                        pdf.set_fill_color(*YELLOW_BG)
                    else:  # Puntaje bajo
                        pdf.set_fill_color(*RED_BG)
                    
                    puntaje_text = f"{puntaje:.2f}"
                
                pdf.cell(eta_width, 5, puntaje_text, 1, 0, 'C', 1)
            
            pdf.ln()
        
        # Agregar sección de detalles al final (similar a la primera imagen)
        pdf.ln(3)
        self._draw_eta_details_section(pdf, sorted_etas, eta_data_by_subject)
    
    def _draw_eta_details_section(self, pdf: fpdf.FPDF, etas_list: list, eta_data: Dict[str, Dict[str, float]]):
        """Dibuja la sección de detalles corregida con fechas reales, ranking y puntajes consistentes."""
        # Obtener las ETAs reales con sus datos completos
        eta_history = getattr(self, '_current_eta_history', {})
        etas_with_data = eta_history.get('etas', [])
        
        if not etas_with_data:
            return
        
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(*LIGHT_GREY_RGB)
        pdf.cell(0, 6, self.pdf_service._encode_text("DETALLE DE CALIFICACIONES"), 1, 1, 'C', 1)
        
        # Tabla de detalles
        pdf.set_font("Arial", "B", 8)
        pdf.set_fill_color(*MEDIUM_GREY_RGB)
        
        col_widths = [20, 25, 25, 25, 25, 25, 25, 20]
        headers = ["ETA", "FECHA", "ORDEN", "NOTA", "PUNTAJE", "CONOC.", "APTITUD", "POSICIÓN"]
        
        for i, header in enumerate(headers):
            if i < len(col_widths):
                pdf.cell(col_widths[i], 5, self.pdf_service._encode_text(header), 1, 0, 'C', 1)
        pdf.ln()
        
        # Ordenar ETAs por nota vigesimal para obtener ranking real
        valid_etas = [eta for eta in etas_with_data if eta.get('total_questions', 0) > 0]
        sorted_etas_by_score = sorted(valid_etas, key=lambda x: x.get('nota_vigesimal', 0), reverse=True)
        
        # Crear mapeo de ETA number a posición de ranking
        ranking_map = {}
        for pos, eta in enumerate(sorted_etas_by_score, 1):
            eta_num = eta.get('eta_number')
            if eta_num is not None:
                ranking_map[eta_num] = pos
        
        # Datos de ETAs (ordenados por número de ETA, no por ranking)
        pdf.set_font("Arial", "", 7)
        pdf.set_fill_color(*WHITE_RGB)
        
        etas_ordenadas = sorted(valid_etas, key=lambda x: x.get('eta_number', 999))
        
        for eta in etas_ordenadas[:18]:  # Mostrar hasta 18 ETAs
            eta_num = eta.get('eta_number', '?')
            
            # FECHA REAL del quiz_created
            fecha_str = "N/D"
            quiz_created = eta.get('quiz_created')
            if quiz_created:
                try:
                    if isinstance(quiz_created, str):
                        # Intentar parsear diferentes formatos de fecha
                        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"]:
                            try:
                                dt = datetime.datetime.strptime(quiz_created, fmt)
                                fecha_str = dt.strftime("%d/%m/%Y")
                                break
                            except ValueError:
                                continue
                    else:
                        # Si ya es un objeto datetime
                        fecha_str = quiz_created.strftime("%d/%m/%Y")
                except Exception as e:
                    print(f"Error formateando fecha para ETA {eta_num}: {e}")
                    fecha_str = "N/D"
            
            # RANKING REAL por ETA
            posicion_ranking = ranking_map.get(eta_num, len(valid_etas))
            orden_str = f"{posicion_ranking:04d}"
            
            # USAR DATOS REALES Y CONSISTENTES
            nota_vigesimal = eta.get('nota_vigesimal', 0.0)
            total_points = eta.get('total_points', 0.0)
            conocimientos_score = eta.get('conocimientos_score', 0.0)  # Ya es vigesimal
            aptitud_score = eta.get('aptitud_score', 0.0)  # Ya es vigesimal
            
            # Color según rendimiento
            if nota_vigesimal >= 10.5:
                pdf.set_fill_color(*GREEN_BG)
            elif nota_vigesimal >= 7:
                pdf.set_fill_color(*YELLOW_BG)
            else:
                pdf.set_fill_color(*RED_BG)
            
            row_data = [
                str(eta_num),
                fecha_str,
                orden_str,
                f"{nota_vigesimal:.3f}",
                f"{total_points:.3f}",
                f"{conocimientos_score:.3f}",
                f"{aptitud_score:.3f}",
                str(posicion_ranking)
            ]
            
            for j, data in enumerate(row_data):
                if j < len(col_widths):
                    pdf.cell(col_widths[j], 4, self.pdf_service._encode_text(data), 1, 0, 'C', 1)
            pdf.ln()

    def _draw_subject_analysis(self, pdf: fpdf.FPDF, subject_averages: Dict[str, float]):
        """Dibuja el análisis por asignatura."""
        if not subject_averages:
            return
        
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(*LIGHT_GREY_RGB)
        pdf.cell(0, 6, self.pdf_service._encode_text("PROMEDIO POR ASIGNATURA"), 1, 1, 'C', 1)
        
        # Filtrar asignaturas por área académica y excluir las sin datos reales
        filtered_subjects = {}
        student_info = getattr(self, '_current_eta_history', {}).get('student_info', {})
        academic_area_id = student_info.get('academic_area_id')
        
        if academic_area_id and hasattr(self.pdf_service, 'academic_service'):
            try:
                # Obtener asignaturas válidas para el área
                weights_map = self.pdf_service.academic_service.get_weights_by_area(academic_area_id)
                valid_subjects = set()
                for (start, end), (subject, level, weight) in weights_map.items():
                    valid_subjects.add(subject)
                
                # Filtrar solo asignaturas del área Y que tengan datos válidos
                for subject, avg in subject_averages.items():
                    if subject in valid_subjects:
                        # CORRECCIÓN: Solo incluir asignaturas con promedios reales
                        # Las asignaturas con 0% real se mostrarán, pero no las que no tienen datos
                        filtered_subjects[subject] = avg
            except Exception as e:
                print(f"Error filtrando asignaturas por área: {e}")
                # En caso de error, filtrar asignaturas sin datos
                filtered_subjects = {s: avg for s, avg in subject_averages.items()}
        else:
            # Si no hay info de área, usar todas las que tengan datos
            filtered_subjects = subject_averages
        
        if not filtered_subjects:
            pdf.set_font("Arial", "I", 9)
            pdf.cell(0, 6, self.pdf_service._encode_text("No hay datos de asignaturas disponibles"), 0, 1, 'C')
            return
        
        # Ordenar asignaturas por promedio
        sorted_subjects = sorted(filtered_subjects.items(), key=lambda x: x[1], reverse=True)
        
        # Calcular cuántas asignaturas podemos mostrar según el espacio disponible
        page_height = 297  # A4 en mm
        current_y = pdf.get_y()
        available_height = page_height - current_y - FOOTER_HEIGHT_MM - 25  # Margen de seguridad
        row_height = 4
        max_subjects_to_show = min(len(sorted_subjects), int(available_height / row_height) - 1)  # -1 para dejar espacio para el total
        
        # Si hay muchas asignaturas, ajustar el tamaño de fuente
        if len(sorted_subjects) > 15:
            pdf.set_font("Arial", "", 7)  # Fuente más pequeña para más asignaturas
        else:
            pdf.set_font("Arial", "", 8)
        
        # Obtener información adicional sobre las asignaturas para contexto
        subject_appearances_info = {}
        student_info = getattr(self, '_current_eta_history', {}).get('student_info', {})
        etas = getattr(self, '_current_eta_history', {}).get('etas', [])
        valid_etas = [eta for eta in etas if eta.get('total_questions', 0) > 0]
        num_etas = len(valid_etas)
        
        # Contar apariciones por asignatura
        if valid_etas:
            for eta in valid_etas:
                consolidated_data = eta.get('consolidated_data', [])
                for row in consolidated_data:
                    if len(row) >= 9:
                        subject, level, peso, correct, wrong, blank, total_q, points, performance = row
                        if total_q > 0:
                            if subject not in subject_appearances_info:
                                subject_appearances_info[subject] = 0
                            subject_appearances_info[subject] += 1
        
        subjects_shown = 0
        subjects_without_data = []  # Asignaturas del área pero sin datos
        
        # Identificar asignaturas del área que no tienen datos
        if academic_area_id and hasattr(self.pdf_service, 'academic_service'):
            try:
                weights_map = self.pdf_service.academic_service.get_weights_by_area(academic_area_id)
                all_area_subjects = set()
                for (start, end), (subject, level, weight) in weights_map.items():
                    all_area_subjects.add(subject)
                
                # Encontrar asignaturas sin datos
                subjects_without_data = list(all_area_subjects - set(filtered_subjects.keys()))
            except Exception as e:
                pass
        
        # Mostrar todas las asignaturas que quepan en la página
        for subject, avg in sorted_subjects[:max_subjects_to_show]:
            # Determinar color según rendimiento
            if avg >= 70:
                color = GREEN_BG
            elif avg >= 50:
                color = YELLOW_BG
            else:
                color = RED_BG
            
            pdf.set_fill_color(*color)
            
            # Nombre de asignatura con indicador de frecuencia
            appearances = subject_appearances_info.get(subject, 0)
            freq_indicator = ""
            if num_etas > 0 and appearances < num_etas * 0.5:
                freq_indicator = f" ({appearances}/{num_etas} ETAs)"
            
            subject_display = subject[:30] + '...' if len(subject) > 30 else subject
            subject_display += freq_indicator
            
            pdf.cell(140, 4, self.pdf_service._encode_text(subject_display), 1, 0, 'L', 1)
            
            # Barra de progreso
            bar_width = 40
            progress = min(100, max(0, avg))
            bar_filled = (progress / 100) * bar_width
            
            # Fondo de la barra
            pdf.set_fill_color(*WHITE_RGB)
            pdf.cell(bar_width, 4, "", 1, 0, 'L', 1)
            
            # Barra de progreso
            bar_x = pdf.get_x() - bar_width
            bar_y = pdf.get_y()
            pdf.set_fill_color(*GREEN_BAR if avg >= 70 else YELLOW_BAR if avg >= 50 else RED_BAR)
            if bar_filled > 0:
                pdf.rect(bar_x, bar_y, bar_filled, 4, 'F')
            
            # Porcentaje
            pdf.cell(10, 4, f"{avg:.1f}%", 1, 1, 'C')
            subjects_shown += 1
        
        # Mostrar mensaje sobre asignaturas mostradas vs total
        pdf.set_font("Arial", "I", 7)
        pdf.set_text_color(*DARK_GREY_RGB)
        
        # Construir mensaje informativo
        if subjects_without_data:
            if subjects_shown < len(sorted_subjects):
                remaining = len(sorted_subjects) - subjects_shown
                message = f"Mostrando {subjects_shown} de {len(sorted_subjects)} asignaturas con datos ({remaining} más no mostradas)"
            else:
                message = f"Total: {len(sorted_subjects)} asignaturas con datos"
            
            pdf.cell(0, 4, self.pdf_service._encode_text(message), 0, 1, 'R')
            
            # Mensaje sobre asignaturas sin datos
            no_data_msg = f"Asignaturas sin datos en las ETAs evaluadas: {', '.join(subjects_without_data[:3])}"
            if len(subjects_without_data) > 3:
                no_data_msg += f" y {len(subjects_without_data) - 3} más"
            
            pdf.set_text_color(*RED_TEXT)
            pdf.cell(0, 4, self.pdf_service._encode_text(no_data_msg), 0, 1, 'R')
        else:
            if subjects_shown < len(sorted_subjects):
                remaining = len(sorted_subjects) - subjects_shown
                message = f"Mostrando {subjects_shown} de {len(sorted_subjects)} asignaturas del área ({remaining} más no mostradas)"
            else:
                message = f"Total: {len(sorted_subjects)} asignaturas del área académica (todas con datos)"
            
            pdf.cell(0, 4, self.pdf_service._encode_text(message), 0, 1, 'R')
        
        # Mensaje adicional sobre promedios calculados
        if num_etas > 0:
            pdf.set_text_color(*DARK_GREY_RGB)
            calc_msg = f"Promedios calculados sobre {num_etas} ETAs totales evaluadas"
            pdf.cell(0, 4, self.pdf_service._encode_text(calc_msg), 0, 1, 'R')
        
        pdf.set_text_color(*BLACK_RGB)
        
        pdf.ln(5)

    def _draw_recommendations(self, pdf: fpdf.FPDF, summary: Dict[str, Any]):
        """Dibuja las recomendaciones."""
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(*PURPLE_RGB)
        pdf.set_text_color(*WHITE_RGB)
        pdf.cell(0, 6, self.pdf_service._encode_text("RECOMENDACIONES"), 1, 1, 'C', 1)
        
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(*BLACK_RGB)
        
        avg_score = summary.get('average_score', 0)
        trend = summary.get('trend', 'estable')
        passing_rate = summary.get('passing_rate', 0)
        
        recommendations = []
        
        if avg_score < 10.5:
            recommendations.append("• Reforzar estudio en áreas débiles identificadas")
            recommendations.append("• Practicar más ejercicios de las asignaturas con menor rendimiento")
        
        if trend == 'declinando':
            recommendations.append("• Revisar métodos de estudio actuales")
            recommendations.append("• Considerar apoyo adicional o tutoría")
        
        if passing_rate < 50:
            recommendations.append("• Establecer un plan de estudio más estructurado")
            recommendations.append("• Aumentar tiempo de preparación para exámenes")
        
        if avg_score >= 14:
            recommendations.append("• Mantener el excelente nivel de preparación")
            recommendations.append("• Enfocarse en perfeccionar áreas específicas")
        
        if not recommendations:
            recommendations.append("• Continuar con la preparación actual")
            recommendations.append("• Mantener constancia en el estudio")
        
        for rec in recommendations:
            pdf.cell(0, 5, self.pdf_service._encode_text(rec), 0, 1, 'L')
        
        pdf.ln(5)

    def _save_eta_pdf(self, pdf: fpdf.FPDF, student_info: Dict[str, Any], output_dir: str) -> str:
        """Guarda el PDF de ETAs."""
        # Crear nombre de archivo
        student_id = student_info.get('student_id', 'unknown')
        safe_student_id = "".join(c if c.isalnum() else "_" for c in str(student_id))
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"Resumen_ETAs_{safe_student_id}_{timestamp}.pdf"
        
        # Crear directorio si no existe
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Guardar archivo
        filepath = os.path.join(output_dir, filename)
        pdf.output(filepath)
        
        print(f"PDF de ETAs generado: {os.path.abspath(filepath)}")
        return os.path.abspath(filepath)

    def generate_consolidated_eta_report(self, student_ids: List[str], output_dir: str = "reports") -> str:
        """
        Genera un PDF consolidado con el análisis de ETAs para múltiples estudiantes.

        Args:
            student_ids: Lista de IDs de estudiantes
            output_dir: Directorio donde guardar el PDF

        Returns:
            str: Ruta al archivo PDF generado

        Raises:
            ValueError: Si no hay estudiantes válidos para analizar
            IOError: Si hay problemas al generar o guardar el PDF
        """
        # Obtener datos consolidados
        analysis_result = self.eta_analysis_service.get_consolidated_eta_analysis(student_ids)
        
        if not analysis_result.get('valid', False):
            raise ValueError(f"Error en análisis consolidado: {analysis_result.get('error', 'Error desconocido')}")

        consolidated_data = analysis_result['data']

        # Crear PDF personalizado
        class ConsolidatedETAReportPDF(fpdf.FPDF):
            img_header_path = self.pdf_service.header_img_path
            img_footer_path = self.pdf_service.footer_img_path

            def header(self):
                if self.img_header_path:
                    try:
                        self.image(self.img_header_path, x=0, y=0, w=self.w, h=HEADER_HEIGHT_MM)
                    except Exception as e:
                        print(f"Error al insertar imagen de encabezado: {e}")
                self.set_y(BASE_MARGIN_TOP_CONTENT)

            def footer(self):
                if self.img_footer_path:
                    try:
                        self.image(self.img_footer_path, x=0, y=self.h - FOOTER_HEIGHT_MM, w=self.w, h=FOOTER_HEIGHT_MM)
                    except Exception as e:
                        print(f"Error al insertar imagen de pie: {e}")

                self.set_y(-15)
                self.set_font('Arial', 'I', 7)
                self.set_text_color(128)
                copyright_text = self.pdf_service._encode_text("© 2025 NK Chambergo")
                self.cell(0, 5, copyright_text, 0, 0, 'C')
                page_num_text = self.pdf_service._encode_text(f'Página {self.page_no()}/{{nb}}')
                self.cell(0, 5, page_num_text, 0, 0, 'R')

        # Crear instancia del PDF
        pdf = ConsolidatedETAReportPDF(orientation='P', unit='mm', format='A4')
        pdf.pdf_service = self.pdf_service
        pdf.alias_nb_pages()
        pdf.set_margins(BASE_MARGIN_LR, BASE_MARGIN_TOP_CONTENT, BASE_MARGIN_LR)
        pdf.set_auto_page_break(auto=True, margin=BASE_MARGIN_BOTTOM_CONTENT)
        pdf.add_page()

        # Generar contenido del PDF
        self._draw_consolidated_report_content(pdf, consolidated_data)

        # Guardar PDF
        pdf_path = self._save_consolidated_pdf(pdf, consolidated_data, output_dir)
        return pdf_path

    def _draw_consolidated_report_content(self, pdf: fpdf.FPDF, consolidated_data: Dict[str, Any]):
        """Dibuja todo el contenido del reporte consolidado."""
        
        # Títulos principales
        self._draw_consolidated_titles(pdf, consolidated_data)
        
        # Información general del reporte
        self._draw_consolidated_info(pdf, consolidated_data)
        
        # Estadísticas grupales
        self._draw_group_statistics(pdf, consolidated_data.get('group_statistics', {}))
        
        # Distribución de rendimiento
        self._draw_performance_distribution(pdf, consolidated_data.get('group_statistics', {}))
        
        # Análisis por ETA
        self._draw_eta_analysis(pdf, consolidated_data.get('eta_comparisons', {}))
        
        # Análisis por asignatura grupal
        self._draw_consolidated_subject_analysis(pdf, consolidated_data.get('subject_analysis', {}))
        
        # Tendencias grupales
        self._draw_group_trends(pdf, consolidated_data.get('trends_analysis', {}))
        
        # Ranking de estudiantes
        self._draw_student_ranking(pdf, consolidated_data.get('students_data', []))
        
        # Recomendaciones grupales
        self._draw_group_recommendations(pdf, consolidated_data)

    def _draw_consolidated_titles(self, pdf: fpdf.FPDF, consolidated_data: Dict[str, Any]):
        """Dibuja los títulos del reporte consolidado."""
        pdf.set_font("Arial", "B", 16)
        pdf.set_text_color(*PURPLE_RGB)
        pdf.cell(0, 8, self.pdf_service._encode_text("REPORTE CONSOLIDADO DE ETAs"), 0, 1, 'C')
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 6, self.pdf_service._encode_text("ANÁLISIS GRUPAL DE RENDIMIENTO ACADÉMICO"), 0, 1, 'C')
        
        # Información de generación
        generation_info = consolidated_data.get('generation_info', {})
        pdf.set_font("Arial", "", 8)
        pdf.set_text_color(*DARK_GREY_RGB)
        date_text = f"Generado: {generation_info.get('generation_date', 'Fecha no disponible')}"
        pdf.cell(0, 4, self.pdf_service._encode_text(date_text), 0, 1, 'C')
        
        pdf.ln(5)
        pdf.set_text_color(*BLACK_RGB)

    def _draw_consolidated_info(self, pdf: fpdf.FPDF, consolidated_data: Dict[str, Any]):
        """Dibuja la información general del reporte."""
        generation_info = consolidated_data.get('generation_info', {})
        
        pdf.set_fill_color(*LIGHT_GREY_RGB)
        pdf.rect(BASE_MARGIN_LR, pdf.get_y(), pdf.w - 2 * BASE_MARGIN_LR, 15, 'F')
        
        pdf.set_font("Arial", "B", 10)
        y_start = pdf.get_y() + 3
        
        # Línea 1
        pdf.set_xy(BASE_MARGIN_LR + 3, y_start)
        pdf.cell(40, 5, self.pdf_service._encode_text("Estudiantes Solicitados:"), 0, 0, 'L')
        pdf.set_font("Arial", "", 10)
        pdf.cell(40, 5, str(generation_info.get('total_students_requested', 0)), 0, 0, 'L')
        
        pdf.set_font("Arial", "B", 10)
        pdf.cell(40, 5, self.pdf_service._encode_text("Estudiantes Analizados:"), 0, 0, 'L')
        pdf.set_font("Arial", "", 10)
        pdf.cell(40, 5, str(generation_info.get('total_students_analyzed', 0)), 0, 1, 'L')
        
        # Línea 2
        pdf.set_xy(BASE_MARGIN_LR + 3, pdf.get_y())
        group_stats = consolidated_data.get('group_statistics', {})
        
        pdf.set_font("Arial", "B", 10)
        pdf.cell(40, 5, self.pdf_service._encode_text("Promedio Grupal:"), 0, 0, 'L')
        pdf.set_font("Arial", "B", 12)
        avg_score = group_stats.get('group_average', 0)
        color = GREEN_TEXT if avg_score >= 10.5 else RED_TEXT
        pdf.set_text_color(*color)
        pdf.cell(40, 5, f"{avg_score:.3f}", 0, 0, 'L')
        pdf.set_text_color(*BLACK_RGB)
        
        pdf.set_font("Arial", "B", 10)
        pdf.cell(40, 5, self.pdf_service._encode_text("Tasa de Éxito:"), 0, 0, 'L')
        pdf.set_font("Arial", "", 10)
        pdf.cell(40, 5, f"{group_stats.get('group_passing_rate', 0):.1f}%", 0, 1, 'L')
        
        pdf.ln(8)

    def _draw_group_statistics(self, pdf: fpdf.FPDF, group_stats: Dict[str, Any]):
        """Dibuja las estadísticas grupales principales."""
        if not group_stats:
            return
            
        pdf.set_font("Arial", "B", 11)
        pdf.set_fill_color(*PURPLE_RGB)
        pdf.set_text_color(*WHITE_RGB)
        pdf.cell(0, 6, self.pdf_service._encode_text("ESTADÍSTICAS GRUPALES"), 1, 1, 'C', 1)
        
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(*BLACK_RGB)
        
        # Tabla de estadísticas
        col_widths = [60, 60, 70]
        
        # Fila 1
        pdf.set_fill_color(*LIGHT_GREY_RGB)
        pdf.cell(col_widths[0], 5, self.pdf_service._encode_text("Total Estudiantes"), 1, 0, 'C', 1)
        pdf.cell(col_widths[1], 5, self.pdf_service._encode_text("ETAs Analizadas"), 1, 0, 'C', 1)
        pdf.cell(col_widths[2], 5, self.pdf_service._encode_text("Mejor Estudiante"), 1, 1, 'C', 1)
        
        # Fila 2 - Datos
        pdf.set_fill_color(*WHITE_RGB)
        total_students = str(group_stats.get('total_students', 0))
        total_etas = str(group_stats.get('total_etas_analyzed', 0))
        
        best_student = group_stats.get('best_student', {})
        if best_student:
            student_info = best_student.get('student', {})
            best_name = f"{student_info.get('first_name', '')} {student_info.get('last_name', '')}"
            best_score = f"({best_student.get('score', 0):.3f})"
            best_text = f"{best_name[:20]}... {best_score}" if len(best_name) > 20 else f"{best_name} {best_score}"
        else:
            best_text = "N/A"
        
        pdf.cell(col_widths[0], 5, total_students, 1, 0, 'C', 1)
        pdf.cell(col_widths[1], 5, total_etas, 1, 0, 'C', 1)
        pdf.cell(col_widths[2], 5, self.pdf_service._encode_text(best_text), 1, 1, 'C', 1)
        
        pdf.ln(5)

    def _draw_performance_distribution(self, pdf: fpdf.FPDF, group_stats: Dict[str, Any]):
        """Dibuja la distribución de rendimiento del grupo."""
        performance_dist = group_stats.get('performance_distribution', {})
        if not performance_dist:
            return
            
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(*LIGHT_GREY_RGB)
        pdf.cell(0, 6, self.pdf_service._encode_text("DISTRIBUCIÓN DE RENDIMIENTO"), 1, 1, 'C', 1)
        
        # Crear barras de distribución
        categories = [
            ('excellent', 'Excelente (16-20)', GREEN_BAR),
            ('good', 'Bueno (13-16)', YELLOW_BAR),
            ('regular', 'Regular (10.5-13)', (100, 149, 237)),  # Azul claro
            ('needs_improvement', 'Necesita Mejora (<10.5)', RED_BAR)
        ]
        
        pdf.set_font("Arial", "", 8)
        for key, label, color in categories:
            data = performance_dist.get(key, {})
            count = data.get('count', 0)
            percentage = data.get('percentage', 0)
            
            # Etiqueta
            pdf.cell(80, 4, self.pdf_service._encode_text(label), 1, 0, 'L')
            
            # Barra de progreso
            bar_width = 60
            bar_filled = (percentage / 100) * bar_width if percentage > 0 else 0
            
            # Fondo de la barra
            pdf.set_fill_color(*WHITE_RGB)
            pdf.cell(bar_width, 4, "", 1, 0, 'L', 1)
            
            # Barra de progreso
            if bar_filled > 0:
                bar_x = pdf.get_x() - bar_width
                bar_y = pdf.get_y()
                pdf.set_fill_color(*color)
                pdf.rect(bar_x, bar_y, bar_filled, 4, 'F')
            
            # Datos
            pdf.cell(50, 4, f"{count} est. ({percentage:.1f}%)", 1, 1, 'C')
        
        pdf.ln(5)

    def _draw_eta_analysis(self, pdf: fpdf.FPDF, eta_comparisons: Dict[str, Any]):
        """Dibuja el análisis comparativo por ETA."""
        eta_stats = eta_comparisons.get('eta_statistics', {})
        if not eta_stats:
            return
            
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(*LIGHT_GREY_RGB)
        pdf.cell(0, 6, self.pdf_service._encode_text("ANÁLISIS POR ETA"), 1, 1, 'C', 1)
        
        # Información general de ETAs
        most_difficult = eta_comparisons.get('most_difficult_eta', {})
        easiest = eta_comparisons.get('easiest_eta', {})
        
        pdf.set_font("Arial", "", 8)
        if most_difficult:
            difficult_text = f"ETA más difícil: ETA {most_difficult.get('eta_number', '?')} (Promedio: {most_difficult.get('average_score', 0):.2f})"
            pdf.cell(0, 4, self.pdf_service._encode_text(difficult_text), 0, 1, 'L')
        
        if easiest:
            easy_text = f"ETA más fácil: ETA {easiest.get('eta_number', '?')} (Promedio: {easiest.get('average_score', 0):.2f})"
            pdf.cell(0, 4, self.pdf_service._encode_text(easy_text), 0, 1, 'L')
        
        pdf.ln(2)
        
        # Tabla de ETAs (hasta 18)
        pdf.set_font("Arial", "B", 7)
        col_widths = [20, 35, 35, 35, 35, 30]
        headers = ["ETA", "ESTUDIANTES", "PROMEDIO", "MÁXIMO", "MÍNIMO", "% ÉXITO"]
        
        pdf.set_fill_color(*MEDIUM_GREY_RGB)
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 4, self.pdf_service._encode_text(header), 1, 0, 'C', 1)
        pdf.ln()
        
        # Ordenar ETAs por número
        sorted_etas = sorted(eta_stats.items(), key=lambda x: x[0])[:18]  # Hasta 18 ETAs
        
        pdf.set_font("Arial", "", 6)
        for eta_num, stats in sorted_etas:
            avg_score = stats.get('average_score', 0)
            
            # Color según promedio
            if avg_score >= 10.5:
                pdf.set_fill_color(*GREEN_BG)
            elif avg_score >= 7:
                pdf.set_fill_color(*YELLOW_BG)
            else:
                pdf.set_fill_color(*RED_BG)
            
            data = [
                str(eta_num),
                str(stats.get('students_count', 0)),
                f"{avg_score:.2f}",
                f"{stats.get('max_score', 0):.2f}",
                f"{stats.get('min_score', 0):.2f}",
                f"{stats.get('passing_rate', 0):.1f}%"
            ]
            
            for i, item in enumerate(data):
                pdf.cell(col_widths[i], 3, item, 1, 0, 'C', 1)
            pdf.ln()
        
        pdf.ln(5)

    def _draw_consolidated_subject_analysis(self, pdf: fpdf.FPDF, subject_analysis: Dict[str, Any]):
        """Dibuja el análisis consolidado por asignatura."""
        subject_stats = subject_analysis.get('subject_statistics', {})
        if not subject_stats:
            return
            
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(*LIGHT_GREY_RGB)
        pdf.cell(0, 6, self.pdf_service._encode_text("RENDIMIENTO POR ASIGNATURA"), 1, 1, 'C', 1)
        
        # Fortalezas y debilidades
        strongest = subject_analysis.get('strongest_subject')
        weakest = subject_analysis.get('weakest_subject')
        
        pdf.set_font("Arial", "", 8)
        if strongest:
            strong_text = f"Fortaleza grupal: {strongest[0]} ({strongest[1]['average_percentage']:.1f}%)"
            pdf.cell(0, 4, self.pdf_service._encode_text(strong_text), 0, 1, 'L')
        
        if weakest:
            weak_text = f"Area de mejora: {weakest[0]} ({weakest[1]['average_percentage']:.1f}%)"
            pdf.cell(0, 4, self.pdf_service._encode_text(weak_text), 0, 1, 'L')
        
        pdf.ln(2)
        
        # Ordenar asignaturas por promedio
        sorted_subjects = sorted(subject_stats.items(), key=lambda x: x[1]['average_percentage'], reverse=True)
        
        pdf.set_font("Arial", "", 7)
        for subject, stats in sorted_subjects[:8]:  # Mostrar solo las primeras 8
            avg_percentage = stats.get('average_percentage', 0)
            
            # Color según rendimiento
            if avg_percentage >= 70:
                color = GREEN_BG
            elif avg_percentage >= 50:
                color = YELLOW_BG
            else:
                color = RED_BG
            
            pdf.set_fill_color(*color)
            
            # Nombre de asignatura
            subject_name = subject[:40] + '...' if len(subject) > 40 else subject
            pdf.cell(100, 3, self.pdf_service._encode_text(subject_name), 1, 0, 'L', 1)
            
            # Estudiantes
            pdf.cell(30, 3, f"{stats.get('students_count', 0)} est.", 1, 0, 'C', 1)
            
            # Barra y porcentaje
            bar_width = 40
            progress = min(100, max(0, avg_percentage))
            bar_filled = (progress / 100) * bar_width
            
            # Fondo de la barra
            pdf.set_fill_color(*WHITE_RGB)
            pdf.cell(bar_width, 3, "", 1, 0, 'L', 1)
            
            # Barra de progreso
            if bar_filled > 0:
                bar_x = pdf.get_x() - bar_width
                bar_y = pdf.get_y()
                pdf.set_fill_color(*GREEN_BAR if avg_percentage >= 70 else YELLOW_BAR if avg_percentage >= 50 else RED_BAR)
                pdf.rect(bar_x, bar_y, bar_filled, 3, 'F')
            
            # Porcentaje
            pdf.cell(20, 3, f"{avg_percentage:.1f}%", 1, 1, 'C')
        
        pdf.ln(5)

    def _draw_group_trends(self, pdf: fpdf.FPDF, trends_analysis: Dict[str, Any]):
        """Dibuja el análisis de tendencias grupales."""
        trend_dist = trends_analysis.get('trend_distribution', {})
        if not trend_dist:
            return
            
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(*LIGHT_GREY_RGB)
        pdf.cell(0, 6, self.pdf_service._encode_text("TENDENCIAS GRUPALES"), 1, 1, 'C', 1)
        
        # Perspectiva general
        outlook = trends_analysis.get('group_outlook', 'estable')
        outlook_text = f"Perspectiva grupal: {outlook.upper()}"
        
        pdf.set_font("Arial", "B", 9)
        color = GREEN_TEXT if outlook == 'positivo' else RED_TEXT if outlook == 'preocupante' else DARK_GREY_RGB
        pdf.set_text_color(*color)
        pdf.cell(0, 5, self.pdf_service._encode_text(outlook_text), 0, 1, 'C')
        pdf.set_text_color(*BLACK_RGB)
        
        # Distribución de tendencias
        pdf.set_font("Arial", "", 8)
        col_widths = [60, 60, 60]
        
        # Cabeceras
        pdf.set_fill_color(*MEDIUM_GREY_RGB)
        pdf.cell(col_widths[0], 4, self.pdf_service._encode_text("MEJORANDO"), 1, 0, 'C', 1)
        pdf.cell(col_widths[1], 4, self.pdf_service._encode_text("ESTABLE"), 1, 0, 'C', 1)
        pdf.cell(col_widths[2], 4, self.pdf_service._encode_text("DECLINANDO"), 1, 1, 'C', 1)
        
        # Datos
        improving = trend_dist.get('improving', {})
        stable = trend_dist.get('stable', {})
        declining = trend_dist.get('declining', {})
        
        # Colores según tendencia
        pdf.set_fill_color(*GREEN_BG)
        pdf.cell(col_widths[0], 4, f"{improving.get('count', 0)} ({improving.get('percentage', 0):.1f}%)", 1, 0, 'C', 1)
        
        pdf.set_fill_color(*YELLOW_BG)
        pdf.cell(col_widths[1], 4, f"{stable.get('count', 0)} ({stable.get('percentage', 0):.1f}%)", 1, 0, 'C', 1)
        
        pdf.set_fill_color(*RED_BG)
        pdf.cell(col_widths[2], 4, f"{declining.get('count', 0)} ({declining.get('percentage', 0):.1f}%)", 1, 1, 'C', 1)
        
        # Estudiantes que necesitan apoyo
        support_needed = trends_analysis.get('students_needing_support', {})
        if support_needed.get('count', 0) > 0:
            pdf.ln(2)
            pdf.set_font("Arial", "B", 8)
            support_text = f"Estudiantes que requieren apoyo adicional: {support_needed.get('count', 0)} ({support_needed.get('percentage', 0):.1f}%)"
            pdf.set_text_color(*RED_TEXT)
            pdf.cell(0, 4, self.pdf_service._encode_text(support_text), 0, 1, 'L')
            pdf.set_text_color(*BLACK_RGB)
        
        pdf.ln(5)

    def _draw_student_ranking(self, pdf: fpdf.FPDF, students_data: List[Dict[str, Any]]):
        """Dibuja el ranking de estudiantes."""
        if not students_data:
            return
            
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(*PURPLE_RGB)
        pdf.set_text_color(*WHITE_RGB)
        pdf.cell(0, 6, self.pdf_service._encode_text("RANKING DE ESTUDIANTES"), 1, 1, 'C', 1)
        
        # Ordenar estudiantes por promedio
        sorted_students = sorted(students_data, key=lambda x: x['summary'].get('average_score', 0), reverse=True)
        
        # Cabeceras
        pdf.set_font("Arial", "B", 7)
        pdf.set_text_color(*BLACK_RGB)
        col_widths = [15, 70, 25, 25, 25, 30]
        headers = ["POS", "ESTUDIANTE", "PROMEDIO", "ETAs", "% ÉXITO", "TENDENCIA"]
        
        pdf.set_fill_color(*MEDIUM_GREY_RGB)
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 4, self.pdf_service._encode_text(header), 1, 0, 'C', 1)
        pdf.ln()
        
        # Estudiantes (solo los primeros 15)
        pdf.set_font("Arial", "", 6)
        for i, student in enumerate(sorted_students[:15]):
            student_info = student['student_info']
            summary = student['summary']
            
            avg_score = summary.get('average_score', 0)
            
            # Color según posición
            if i < 3:  # Top 3
                pdf.set_fill_color(255, 215, 0)  # Dorado
            elif avg_score >= 10.5:
                pdf.set_fill_color(*GREEN_BG)
            else:
                pdf.set_fill_color(*RED_BG)
            
            # Datos
            position = str(i + 1)
            name = f"{student_info.get('first_name', '')} {student_info.get('last_name', '')}"
            name = name[:25] + '...' if len(name) > 25 else name
            average = f"{avg_score:.3f}"
            etas_count = f"{summary.get('valid_etas', 0)}"
            passing_rate = f"{summary.get('passing_rate', 0):.1f}%"
            trend = summary.get('trend', 'estable')[:8].upper()
            
            data = [position, name, average, etas_count, passing_rate, trend]
            aligns = ['C', 'L', 'C', 'C', 'C', 'C']
            
            for j, item in enumerate(data):
                pdf.cell(col_widths[j], 3, self.pdf_service._encode_text(str(item)), 1, 0, aligns[j], 1)
            pdf.ln()
        
        pdf.ln(5)

    def _draw_group_recommendations(self, pdf: fpdf.FPDF, consolidated_data: Dict[str, Any]):
        """Dibuja las recomendaciones grupales."""
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(*PURPLE_RGB)
        pdf.set_text_color(*WHITE_RGB)
        pdf.cell(0, 6, self.pdf_service._encode_text("RECOMENDACIONES GRUPALES"), 1, 1, 'C', 1)
        
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(*BLACK_RGB)
        
        group_stats = consolidated_data.get('group_statistics', {})
        trends_analysis = consolidated_data.get('trends_analysis', {})
        subject_analysis = consolidated_data.get('subject_analysis', {})
        
        recommendations = []
        
        # Análisis del rendimiento grupal
        group_avg = group_stats.get('group_average', 0)
        passing_rate = group_stats.get('group_passing_rate', 0)
        
        if group_avg < 10.5:
            recommendations.append("• PRIORIDAD: Implementar plan de refuerzo académico grupal")
            recommendations.append("• Revisar metodologías de enseñanza y estrategias pedagógicas")
        
        if passing_rate < 50:
            recommendations.append("• Establecer sistema de tutorías y apoyo académico")
            recommendations.append("• Aumentar horas de práctica y ejercitación")
        
        # Análisis de tendencias
        outlook = trends_analysis.get('group_outlook', 'estable')
        if outlook == 'preocupante':
            recommendations.append("• ALERTA: Tendencia negativa detectada - intervención inmediata")
            recommendations.append("• Evaluar factores externos que afectan el rendimiento")
        
        # Análisis por asignatura
        weakest_subject = subject_analysis.get('weakest_subject')
        if weakest_subject and weakest_subject[1]['average_percentage'] < 50:
            subject_name = weakest_subject[0][:30]
            recommendations.append(f"• Reforzar enseñanza en {subject_name}")
            recommendations.append("• Capacitar docentes en áreas de bajo rendimiento")
        
        # Estudiantes que necesitan apoyo
        support_needed = trends_analysis.get('students_needing_support', {})
        if support_needed.get('percentage', 0) > 30:
            recommendations.append("• Implementar programa de apoyo individualizado")
            recommendations.append("• Establecer seguimiento personalizado")
        
        # Recomendaciones positivas
        if group_avg >= 14:
            recommendations.append("• Mantener estándares de excelencia actuales")
            recommendations.append("• Compartir mejores prácticas con otros grupos")
        
        if outlook == 'positivo':
            recommendations.append("• Continuar con las estrategias actuales")
            recommendations.append("• Potenciar fortalezas identificadas")
        
        # Si no hay recomendaciones específicas
        if not recommendations:
            recommendations.append("• Mantener estrategias de enseñanza actuales")
            recommendations.append("• Continuar monitoreo regular del progreso")
            recommendations.append("• Fomentar participación activa de estudiantes")
        
        for rec in recommendations:
            pdf.cell(0, 5, self.pdf_service._encode_text(rec), 0, 1, 'L')
        
        pdf.ln(5)

    def _save_consolidated_pdf(self, pdf: fpdf.FPDF, consolidated_data: Dict[str, Any], output_dir: str) -> str:
        """Guarda el PDF consolidado."""
        # Crear nombre de archivo
        generation_info = consolidated_data.get('generation_info', {})
        student_count = generation_info.get('total_students_analyzed', 0)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"Reporte_Consolidado_ETAs_{student_count}estudiantes_{timestamp}.pdf"
        
        # Crear directorio si no existe
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Guardar archivo
        filepath = os.path.join(output_dir, filename)
        pdf.output(filepath)
        
        print(f"PDF consolidado generado: {os.path.abspath(filepath)}")
        return os.path.abspath(filepath)
