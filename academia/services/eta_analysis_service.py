# -*- coding: utf-8 -*-
"""
Servicio para análisis consolidado de ETAs por estudiante.
Usa SQLAlchemy ORM (models/academia.py).
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict

from sqlalchemy import or_

from models import db
from models.academia import AcademiaStudent, AcademicArea


class ETAAnalysisService:
    """
    Servicio para análisis de múltiples ETAs de un estudiante.
    """

    def __init__(self, academic_service, pdf_service):
        self.academic_service = academic_service
        self.pdf_service = pdf_service

    def _extract_eta_number(self, quiz_name: str) -> Optional[int]:
        """
        Extrae el número de ETA del nombre del quiz.
        
        Args:
            quiz_name: Nombre del quiz (ej: "ETA 01", "ETA N° 15", etc.)
            
        Returns:
            Número de ETA o None si no se encuentra
        """
        if not quiz_name:
            return None
            
        # Patrones comunes para extraer número de ETA
        patterns = [
            r'ETA(\d+)-\w+-\d{4}-\d+',  # ETA01-INT-2026-1, ETA02-SEM-2026-1, etc.
            r'ETA\s*N?°?\s*(\d+)',  # ETA N° 01, ETA 1, etc.
            r'ETA\s*(\d+)',         # ETA 01
            r'(\d+)',               # Solo número si no hay otro patrón
        ]
        
        quiz_name_upper = quiz_name.upper()
        for pattern in patterns:
            match = re.search(pattern, quiz_name_upper)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
                    
        return None

    def get_student_eta_history(self, student_id: str) -> Dict[str, Any]:
        """
        Obtiene el historial completo de ETAs para un estudiante.

        Args:
            student_id: ID del estudiante (student_id, no el PK de la DB)

        Returns:
            Diccionario con información consolidada del estudiante
        """
        try:
            rows = AcademiaStudent.query.filter_by(
                student_id=student_id
            ).order_by(
                AcademiaStudent.quiz_created.asc(),
                AcademiaStudent.id.asc()
            ).all()

            if not rows:
                return {
                    'student_found': False,
                    'student_info': {},
                    'etas': [],
                    'summary': {}
                }

            first_record = rows[0]
            student_info = {
                'student_id': first_record.student_id,
                'first_name': first_record.first_name,
                'last_name': first_record.last_name,
                'academic_area_id': first_record.academic_area_id,
                'academic_area_name': first_record.academic_area.name if first_record.academic_area else 'Sin área',
                'custom_id': first_record.custom_id,
                'nivel': first_record.nivel or 'ACADEMIA',
                'quiz_class': first_record.quiz_class
            }

            # Procesar cada ETA
            etas = []
            academic_area_id = int(first_record.academic_area_id or 1)

            for row in rows:
                row_dict = row.to_dict(include_area_name=False)
                eta_number = self._extract_eta_number(row.quiz_name or '')

                # Calcular estadísticas de esta ETA
                eta_stats = self._calculate_eta_statistics(row_dict, academic_area_id)

                eta_info = {
                    'id': row.id,
                    'eta_number': eta_number,
                    'quiz_name': row.quiz_name,
                    'quiz_created': row.quiz_created,
                    'percent_correct': row.percent_correct,
                    'earned_points': row.earned_points,
                    'possible_points': row.possible_points,
                    **eta_stats
                }
                
                etas.append(eta_info)

            # Calcular resumen general con academic_area_id y nivel
            nivel = first_record.nivel or 'ACADEMIA'
            quiz_class = first_record.quiz_class or ''
            summary = self._calculate_overall_summary(etas, academic_area_id, nivel=nivel, quiz_class=quiz_class)
            
            return {
                'student_found': True,
                'student_info': student_info,
                'etas': etas,
                'summary': summary
            }
            
        except Exception as e:
            print(f"Error obteniendo historial ETA para estudiante {student_id}: {e}")
            return {
                'student_found': False,
                'student_info': {},
                'etas': [],
                'summary': {},
                'error': str(e)
            }

    def _calculate_eta_statistics(self, student_record: Dict[str, Any], academic_area_id: int) -> Dict[str, Any]:
        """
        Calcula estadísticas detalladas para una ETA específica.
        ACTUALIZADO: Usa la misma lógica que pdf_service.py para total consistencia.
        
        Args:
            student_record: Registro completo del estudiante para esta ETA
            academic_area_id: ID del área académica
            
        Returns:
            Diccionario con estadísticas calculadas
        """
        try:
            # Calcular datos consolidados usando el PDFService existente
            consolidated_data, total_correct, total_wrong, total_blank, total_points = \
                self.pdf_service.calculate_consolidated_data(student_record)
            
            # Número total de preguntas
            num_questions = total_correct + total_wrong + total_blank
            
            # USAR LA MISMA LÓGICA QUE pdf_service.py para total consistencia
            if num_questions > 0:
                # Calcular conocimientos y aptitud sumando por tipo de asignatura (igual que en pdf_service)
                conocimientos_obtained = 0.0
                aptitud_obtained = 0.0
                
                for row in consolidated_data:
                    subject, level, peso, correct, wrong, blank, total_q, points, performance = row
                    if (subject or "").strip().upper().startswith('APTITUD'):
                        aptitud_obtained += points
                    else:
                        conocimientos_obtained += points
                
                # Calcular puntaje total posible (nivel-aware)
                total_possible = self.pdf_service._calculate_total_possible_for_student(student_record, num_questions)
                
                # Calcular vigesimals usando la MISMA base que pdf_service.py
                conocimientos_vigesimal = 0.0
                aptitud_vigesimal = 0.0
                if total_possible > 0:
                    conocimientos_vigesimal = round(max(0, min(20, (conocimientos_obtained / total_possible) * 20)), 3)
                    aptitud_vigesimal = round(max(0, min(20, (aptitud_obtained / total_possible) * 20)), 3)
                
                # La nota final es la suma de ambos vigesimals (igual que en pdf_service)
                nota_vigesimal = conocimientos_vigesimal + aptitud_vigesimal
                
                # Para mostrar en las columnas CONOC. y APTITUD del reporte consolidado
                conocimientos_score = conocimientos_vigesimal
                aptitud_score = aptitud_vigesimal
            else:
                conocimientos_obtained = 0.0
                aptitud_obtained = 0.0
                total_possible = 0.0
                nota_vigesimal = 0.0
                conocimientos_score = 0.0
                aptitud_score = 0.0

            # Rendimiento por asignatura
            subject_performance = {}
            for row in consolidated_data:
                subject, level, peso, correct, wrong, blank, total_q, points, performance = row
                if total_q > 0:
                    subject_percentage = round((correct / total_q) * 100, 2)
                    subject_performance[subject] = {
                        'correct': correct,
                        'total': total_q,
                        'percentage': subject_percentage,
                        'performance': performance,
                        'points': points
                    }

            return {
                'total_correct': total_correct,
                'total_wrong': total_wrong,
                'total_blank': total_blank,
                'total_questions': num_questions,
                'total_points': total_points,
                'total_possible': total_possible,
                'conocimientos_score': conocimientos_score,
                'aptitud_score': aptitud_score,
                'nota_vigesimal': nota_vigesimal,
                'subject_performance': subject_performance,
                'consolidated_data': consolidated_data
            }
            
        except Exception as e:
            print(f"Error calculando estadísticas de ETA: {e}")
            return {
                'total_correct': 0,
                'total_wrong': 0,
                'total_blank': 0,
                'total_questions': 0,
                'total_points': 0.0,
                'total_possible': 0.0,
                'conocimientos_score': 0.0,
                'aptitud_score': 0.0,
                'nota_vigesimal': 0.0,
                'subject_performance': {},
                'consolidated_data': []
            }

    def _calculate_overall_summary(self, etas: List[Dict[str, Any]], academic_area_id: int = None, nivel: str = 'ACADEMIA', quiz_class: str = '') -> Dict[str, Any]:
        """
        Calcula resumen general y tendencias del estudiante.
        
        Args:
            etas: Lista de ETAs procesadas
            academic_area_id: ID del área académica para cálculos correctos
            
        Returns:
            Diccionario con resumen y tendencias
        """
        if not etas:
            return {}

        # Filtrar ETAs válidas (que tengan datos)
        valid_etas = [eta for eta in etas if eta.get('total_questions', 0) > 0]
        
        if not valid_etas:
            return {'total_etas': len(etas), 'valid_etas': 0}

        # Estadísticas básicas
        notas = [eta['nota_vigesimal'] for eta in valid_etas if eta.get('nota_vigesimal') is not None]
        porcentajes = [eta.get('percent_correct', 0) for eta in valid_etas]
        
        # Calcular promedios
        avg_nota = round(sum(notas) / len(notas), 3) if notas else 0
        avg_percentage = round(sum(porcentajes) / len(porcentajes), 2) if porcentajes else 0
        
        # Mejor y peor rendimiento
        best_eta = max(valid_etas, key=lambda x: x.get('nota_vigesimal', 0))
        worst_eta = min(valid_etas, key=lambda x: x.get('nota_vigesimal', 0))
        
        # Calcular tendencia (últimas 3 ETAs vs primeras 3 ETAs)
        trend = 'estable'
        if len(valid_etas) >= 3:
            first_three = valid_etas[:3]
            last_three = valid_etas[-3:]
            
            avg_first = sum(eta['nota_vigesimal'] for eta in first_three) / 3
            avg_last = sum(eta['nota_vigesimal'] for eta in last_three) / 3
            
            if avg_last > avg_first + 0.5:
                trend = 'mejorando'
            elif avg_last < avg_first - 0.5:
                trend = 'declinando'

        # Análisis por asignatura - NUEVA LÓGICA: considerar todas las ETAs
        # El promedio debe reflejar el rendimiento real considerando todas las evaluaciones
        
        # Primero, obtener el peso total de cada asignatura (nivel-aware)
        weights_map = {}
        subject_info = {}  # {subject: {'level': str, 'total_weight': float, 'total_questions': int}}

        if hasattr(self, 'pdf_service') and hasattr(self.pdf_service, 'academic_service'):
            try:
                if nivel != 'ACADEMIA':
                    weights_map = self.pdf_service.academic_service.get_weights_by_nivel_grado(nivel, quiz_class)
                elif academic_area_id:
                    weights_map = self.pdf_service.academic_service.get_weights_by_area(academic_area_id)

                # Calcular información completa por asignatura
                for (q_start, q_end), (subject, level, weight) in weights_map.items():
                    questions_in_range = q_end - q_start + 1
                    
                    if subject not in subject_info:
                        subject_info[subject] = {
                            'level': level,
                            'total_weight': 0.0,
                            'total_questions': 0
                        }
                    
                    subject_info[subject]['total_weight'] += weight * questions_in_range
                    subject_info[subject]['total_questions'] += questions_in_range
                    
            except Exception as e:
                print(f"Error obteniendo ponderaciones para área {academic_area_id}: {e}")
        
        # Recopilar puntos obtenidos por asignatura considerando TODAS las ETAs
        subject_performance_data = {}  # {subject: {'obtained': float, 'appearances': int, 'max_per_eta': float}}
        
        for subject, info in subject_info.items():
            subject_performance_data[subject] = {
                'obtained_points': 0.0,
                'appearances': 0,
                'max_possible_per_eta': info['total_weight'],
                'level': info['level'],
                'total_questions': info['total_questions']
            }
        
        # Recopilar datos de cada ETA
        for eta in valid_etas:
            consolidated_data = eta.get('consolidated_data', [])
            
            # Marcar qué asignaturas aparecieron en esta ETA
            subjects_in_eta = set()
            
            for row in consolidated_data:
                if len(row) >= 9:
                    subject, level, peso, correct, wrong, blank, total_q, points, performance = row
                    
                    if total_q > 0 and subject in subject_performance_data:
                        subject_performance_data[subject]['obtained_points'] += points
                        subject_performance_data[subject]['appearances'] += 1
                        subjects_in_eta.add(subject)
        
        # Calcular promedio por asignatura considerando TODAS las ETAs
        subject_averages = {}
        num_etas = len(valid_etas)
        
        for subject, data in subject_performance_data.items():
            # El máximo posible es el peso de la asignatura multiplicado por el número de ETAs
            max_possible_total = data['max_possible_per_eta'] * num_etas
            
            if max_possible_total > 0:
                # Calcular el porcentaje real considerando todas las ETAs
                # Si la asignatura no apareció en algunas ETAs, cuenta como 0 puntos
                avg_percentage = round((data['obtained_points'] / max_possible_total) * 100, 2)
                
                # Solo incluir asignaturas que aparecieron al menos una vez
                if data['appearances'] > 0:
                    subject_averages[subject] = avg_percentage
                    
                    # Logging para debugging
                    if avg_percentage > 90 and data['appearances'] < num_etas * 0.3:
                        print(f"Advertencia: {subject} tiene {avg_percentage}% pero solo apareció en {data['appearances']}/{num_etas} ETAs")

        # ETAs sobre el promedio (nota >= 10.5)
        passing_etas = [eta for eta in valid_etas if eta.get('nota_vigesimal', 0) >= 10.5]
        passing_rate = round((len(passing_etas) / len(valid_etas)) * 100, 1) if valid_etas else 0

        # Calcular datos por materia y ETA para tabla consolidada
        # Pasar academic_area_id para cálculos correctos
        self._current_student_area_id = academic_area_id  # Guardar para uso en _calculate_eta_data_by_subject
        self._current_student_nivel = nivel
        self._current_student_quiz_class = quiz_class
        eta_data_by_subject = self._calculate_eta_data_by_subject(valid_etas)
        self._current_student_area_id = None  # Limpiar después del uso
        self._current_student_nivel = None
        self._current_student_quiz_class = None
        return {
            'total_etas': len(etas),
            'valid_etas': len(valid_etas),
            'average_score': avg_nota,
            'average_percentage': avg_percentage,
            'best_eta': {
                'eta_number': best_eta.get('eta_number'),
                'score': best_eta.get('nota_vigesimal'),
                'quiz_name': best_eta.get('quiz_name')
            },
            'worst_eta': {
                'eta_number': worst_eta.get('eta_number'),
                'score': worst_eta.get('nota_vigesimal'),
                'quiz_name': worst_eta.get('quiz_name')
            },
            'trend': trend,
            'subject_averages': subject_averages,
            'eta_data_by_subject': eta_data_by_subject,  # NUEVO: Datos para tabla consolidada
            'passing_etas_count': len(passing_etas),
            'passing_rate': passing_rate,
            'improvement_needed': avg_nota < 10.5
        }

    def search_students_for_eta_analysis(self, search_term: str = "") -> List[Dict[str, Any]]:
        """
        Busca estudiantes para análisis de ETA.

        Devuelve una fila por student_id (alumno único). Filtros aplicados
        sobre las filas individuales antes de agregar.
        """
        try:
            term = (search_term or "").strip()
            inner = db.session.query(
                AcademiaStudent.student_id.label('student_id'),
                db.func.max(AcademiaStudent.first_name).label('first_name'),
                db.func.max(AcademiaStudent.last_name).label('last_name'),
                db.func.max(AcademiaStudent.academic_area_id).label('academic_area_id'),
                db.func.count(AcademiaStudent.id).label('total_etas'),
            ).filter(AcademiaStudent.student_id.isnot(None))

            if term:
                pattern = f'%{term}%'
                inner = inner.filter(
                    or_(
                        AcademiaStudent.student_id.ilike(pattern),
                        AcademiaStudent.first_name.ilike(pattern),
                        AcademiaStudent.last_name.ilike(pattern),
                        AcademiaStudent.custom_id.ilike(pattern),
                    )
                )

            sub = inner.group_by(AcademiaStudent.student_id).subquery()

            rows = (
                db.session.query(
                    sub.c.student_id,
                    sub.c.first_name,
                    sub.c.last_name,
                    sub.c.academic_area_id,
                    AcademicArea.name.label('academic_area_name'),
                    sub.c.total_etas,
                )
                .outerjoin(AcademicArea, AcademicArea.id == sub.c.academic_area_id)
                .order_by(sub.c.last_name, sub.c.first_name)
                .limit(50)
                .all()
            )

            return [{
                'student_id': r.student_id,
                'first_name': r.first_name,
                'last_name': r.last_name,
                'academic_area_id': r.academic_area_id,
                'academic_area_name': r.academic_area_name,
                'total_etas': r.total_etas,
            } for r in rows]

        except Exception as e:
            print(f"Error buscando estudiantes para análisis ETA: {e}")
            raise

    def get_consolidated_eta_analysis(self, student_ids: List[str]) -> Dict[str, Any]:
        """
        Genera un análisis consolidado de ETAs para múltiples estudiantes.
        
        Args:
            student_ids: Lista de IDs de estudiantes a analizar
            
        Returns:
            Diccionario con análisis consolidado del grupo
        """
        if not student_ids:
            return {
                'valid': False,
                'error': 'No se proporcionaron estudiantes para analizar'
            }

        try:
            consolidated_data = {
                'students_data': [],
                'group_statistics': {},
                'eta_comparisons': {},
                'subject_analysis': {},
                'trends_analysis': {},
                'generation_info': {
                    'total_students_requested': len(student_ids),
                    'total_students_analyzed': 0,
                    'generation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }

            # Analizar cada estudiante
            students_with_data = []
            all_etas_data = []
            
            for student_id in student_ids:
                student_analysis = self.get_student_eta_history(student_id)
                
                if student_analysis['student_found'] and student_analysis['etas']:
                    students_with_data.append(student_analysis)
                    consolidated_data['students_data'].append({
                        'student_info': student_analysis['student_info'],
                        'summary': student_analysis['summary'],
                        'eta_count': len(student_analysis['etas'])
                    })
                    
                    # Agregar ETAs al análisis general
                    for eta in student_analysis['etas']:
                        if eta.get('total_questions', 0) > 0:  # Solo ETAs válidas
                            all_etas_data.append({
                                'student_id': student_id,
                                'student_name': f"{student_analysis['student_info']['first_name']} {student_analysis['student_info']['last_name']}",
                                **eta
                            })

            consolidated_data['generation_info']['total_students_analyzed'] = len(students_with_data)

            if not students_with_data:
                return {
                    'valid': False,
                    'error': 'No se encontraron datos válidos para ningún estudiante'
                }

            # Calcular estadísticas grupales
            consolidated_data['group_statistics'] = self._calculate_group_statistics(students_with_data)
            
            # Análisis de ETAs
            consolidated_data['eta_comparisons'] = self._calculate_eta_comparisons(all_etas_data)
            
            # Análisis por asignatura
            consolidated_data['subject_analysis'] = self._calculate_subject_analysis(students_with_data)
            
            # Análisis de tendencias
            consolidated_data['trends_analysis'] = self._calculate_trends_analysis(students_with_data)

            return {
                'valid': True,
                'data': consolidated_data
            }
            
        except Exception as e:
            print(f"Error en análisis consolidado: {e}")
            return {
                'valid': False,
                'error': f'Error procesando datos: {str(e)}'
            }

    def _calculate_group_statistics(self, students_data: List[Dict]) -> Dict[str, Any]:
        """
        Calcula estadísticas generales del grupo de estudiantes.
        """
        if not students_data:
            return {}

        # Recopilar todas las notas promedio
        average_scores = []
        total_etas = 0
        passing_rates = []
        
        for student in students_data:
            summary = student['summary']
            if summary.get('valid_etas', 0) > 0:
                average_scores.append(summary.get('average_score', 0))
                total_etas += summary.get('valid_etas', 0)
                passing_rates.append(summary.get('passing_rate', 0))

        if not average_scores:
            return {}

        # Calcular estadísticas
        group_avg = round(sum(average_scores) / len(average_scores), 3)
        group_passing_rate = round(sum(passing_rates) / len(passing_rates), 1)
        
        # Calcular distribución de rendimiento
        excellent = len([score for score in average_scores if score >= 16])
        good = len([score for score in average_scores if 13 <= score < 16])
        regular = len([score for score in average_scores if 10.5 <= score < 13])
        needs_improvement = len([score for score in average_scores if score < 10.5])

        return {
            'total_students': len(students_data),
            'group_average': group_avg,
            'group_passing_rate': group_passing_rate,
            'total_etas_analyzed': total_etas,
            'best_student': {
                'score': max(average_scores),
                'student': next(s['student_info'] for s in students_data 
                              if s['summary'].get('average_score') == max(average_scores))
            },
            'performance_distribution': {
                'excellent': {'count': excellent, 'percentage': round((excellent/len(students_data))*100, 1)},
                'good': {'count': good, 'percentage': round((good/len(students_data))*100, 1)},
                'regular': {'count': regular, 'percentage': round((regular/len(students_data))*100, 1)},
                'needs_improvement': {'count': needs_improvement, 'percentage': round((needs_improvement/len(students_data))*100, 1)}
            }
        }

    def _calculate_eta_comparisons(self, all_etas_data: List[Dict]) -> Dict[str, Any]:
        """
        Analiza el rendimiento comparativo por ETA.
        """
        if not all_etas_data:
            return {}

        # Agrupar por número de ETA
        etas_by_number = defaultdict(list)
        for eta in all_etas_data:
            eta_num = eta.get('eta_number')
            if eta_num is not None:
                etas_by_number[eta_num].append(eta)

        # Calcular estadísticas por ETA
        eta_stats = {}
        for eta_num, etas in etas_by_number.items():
            if etas:
                scores = [eta.get('nota_vigesimal', 0) for eta in etas]
                eta_stats[eta_num] = {
                    'eta_number': eta_num,
                    'students_count': len(etas),
                    'average_score': round(sum(scores) / len(scores), 3),
                    'max_score': max(scores),
                    'min_score': min(scores),
                    'passing_count': len([s for s in scores if s >= 10.5]),
                    'passing_rate': round((len([s for s in scores if s >= 10.5]) / len(scores)) * 100, 1)
                }

        # Identificar ETAs más difíciles y más fáciles
        if eta_stats:
            sorted_by_avg = sorted(eta_stats.values(), key=lambda x: x['average_score'])
            most_difficult = sorted_by_avg[0] if sorted_by_avg else None
            easiest = sorted_by_avg[-1] if sorted_by_avg else None
        else:
            most_difficult = easiest = None

        return {
            'eta_statistics': eta_stats,
            'most_difficult_eta': most_difficult,
            'easiest_eta': easiest,
            'total_unique_etas': len(eta_stats)
        }

    def _calculate_subject_analysis(self, students_data: List[Dict]) -> Dict[str, Any]:
        """
        Analiza el rendimiento por asignatura/materia.
        """
        if not students_data:
            return {}

        # Recopilar rendimiento por asignatura
        subject_data = defaultdict(list)
        
        for student in students_data:
            summary = student.get('summary', {})
            subject_averages = summary.get('subject_averages', {})
            
            for subject, avg_percentage in subject_averages.items():
                subject_data[subject].append(avg_percentage)

        # Calcular estadísticas por asignatura
        subject_stats = {}
        for subject, percentages in subject_data.items():
            if percentages:
                subject_stats[subject] = {
                    'average_percentage': round(sum(percentages) / len(percentages), 2),
                    'students_count': len(percentages),
                    'max_percentage': max(percentages),
                    'min_percentage': min(percentages)
                }

        # Identificar fortalezas y debilidades del grupo
        if subject_stats:
            sorted_subjects = sorted(subject_stats.items(), key=lambda x: x[1]['average_percentage'], reverse=True)
            strongest_subject = sorted_subjects[0] if sorted_subjects else None
            weakest_subject = sorted_subjects[-1] if sorted_subjects else None
        else:
            strongest_subject = weakest_subject = None

        return {
            'subject_statistics': subject_stats,
            'strongest_subject': strongest_subject,
            'weakest_subject': weakest_subject,
            'total_subjects_analyzed': len(subject_stats)
        }

    def _calculate_trends_analysis(self, students_data: List[Dict]) -> Dict[str, Any]:
        """
        Analiza las tendencias de rendimiento del grupo.
        """
        if not students_data:
            return {}

        # Analizar tendencias individuales
        trends = {'mejorando': 0, 'declinando': 0, 'estable': 0}
        improvement_needed = 0
        
        for student in students_data:
            summary = student.get('summary', {})
            trend = summary.get('trend', 'estable')
            trends[trend] += 1
            
            if summary.get('improvement_needed', False):
                improvement_needed += 1

        total_students = len(students_data)
        
        return {
            'trend_distribution': {
                'improving': {
                    'count': trends['mejorando'],
                    'percentage': round((trends['mejorando'] / total_students) * 100, 1)
                },
                'declining': {
                    'count': trends['declinando'],
                    'percentage': round((trends['declinando'] / total_students) * 100, 1)
                },
                'stable': {
                    'count': trends['estable'],
                    'percentage': round((trends['estable'] / total_students) * 100, 1)
                }
            },
            'students_needing_support': {
                'count': improvement_needed,
                'percentage': round((improvement_needed / total_students) * 100, 1)
            },
            'group_outlook': 'positivo' if trends['mejorando'] > trends['declinando'] else 
                           'preocupante' if trends['declinando'] > trends['mejorando'] else 'estable'
        }

    def _calculate_eta_data_by_subject(self, etas: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        """
        Calcula puntajes por materia y ETA para la tabla consolidada.
        CORREGIDO: Usa las ponderaciones reales del academic_service.
        
        Args:
            etas: Lista de ETAs válidas con datos calculados
            
        Returns:
            Dict con formato: {materia: {eta_number: puntaje}}
        """
        if not etas:
            return {}
        
        eta_data_by_subject = {}
        
        # Obtener el área académica para acceder a las ponderaciones reales
        academic_area_id = None
        if etas:
            # Intentar obtener el área desde el primer ETA disponible
            for eta in etas:
                if eta.get('consolidated_data'):
                    # El academic_area_id debería estar disponible desde el contexto
                    break
        
        # Buscar academic_area_id desde el student_info si está disponible
        if hasattr(self, '_current_student_area_id'):
            academic_area_id = self._current_student_area_id
        
        # Obtener ponderaciones reales (nivel-aware)
        weights_map = {}
        current_nivel = getattr(self, '_current_student_nivel', None) or 'ACADEMIA'
        current_quiz_class = getattr(self, '_current_student_quiz_class', None) or ''
        if hasattr(self, 'pdf_service') and hasattr(self.pdf_service, 'academic_service'):
            try:
                if current_nivel != 'ACADEMIA':
                    weights_map = self.pdf_service.academic_service.get_weights_by_nivel_grado(current_nivel, current_quiz_class)
                elif academic_area_id:
                    weights_map = self.pdf_service.academic_service.get_weights_by_area(academic_area_id)
            except Exception as e:
                print(f"Error obteniendo ponderaciones: {e}")
        
        for eta in etas:
            eta_number = eta.get('eta_number', 'N/A')
            if eta_number == 'N/A':
                continue
                
            # NUEVA LÓGICA: Calcular puntajes usando ponderaciones reales
            consolidated_data = eta.get('consolidated_data', [])
            
            if consolidated_data and weights_map:
                # Método 1: Usar consolidated_data que ya tiene los cálculos correctos
                for row in consolidated_data:
                    if len(row) >= 9:  # Asegurar que tiene todos los campos
                        subject, level, peso, correct, wrong, blank, total_q, points, performance = row
                        
                        # Solo incluir si la asignatura tuvo preguntas en esta ETA
                        if total_q > 0:
                            if subject not in eta_data_by_subject:
                                eta_data_by_subject[subject] = {}
                            
                            # Usar el puntaje real calculado por pdf_service
                            eta_data_by_subject[subject][eta_number] = round(points, 2)
                        # Si total_q == 0, no agregar entrada para esta asignatura/ETA
            else:
                # Método 2: Fallback usando subject_performance (menos preciso)
                subject_performance = eta.get('subject_performance', {})
                
                for subject_name, perf_data in subject_performance.items():
                    if perf_data.get('total', 0) > 0:
                        # Buscar la ponderación real para esta asignatura
                        subject_weight = None
                        for (q_start, q_end), (subj, level, weight) in weights_map.items():
                            if subj == subject_name:
                                subject_weight = weight
                                break
                        
                        if subject_weight:
                            # Calcular puntaje usando ponderación real
                            correct_answers = perf_data.get('correct', 0)
                            puntaje = round(correct_answers * subject_weight, 2)
                        else:
                            # Fallback: conversión proporcional si no se encuentra ponderación
                            percentage = perf_data.get('percentage', 0)
                            puntaje = round((percentage / 100) * 2.0, 2)  # Escala más conservadora
                        
                        if subject_name not in eta_data_by_subject:
                            eta_data_by_subject[subject_name] = {}
                        
                        eta_data_by_subject[subject_name][eta_number] = puntaje
        
        return eta_data_by_subject
