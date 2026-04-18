"""
Generador de carnets estudiantiles con código QR - VERSIÓN MEJORADA (CORREGIDA)
Genera PDFs en formato A4 con 9 carnets por página (grid 3x3)
Incluye frente y reverso del carnet + exportación a imagen
Correcciones: Elementos centrados verticalmente y eliminación de dependencia fuerte de Flask.
              Lógica de Logo/Insignia añadida.
              QR arreglado (vuelve a ser visible y grande).
"""
from io import BytesIO
import os
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm as mm_unit
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.graphics.barcode import qr
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing
from PIL import Image, ImageDraw, ImageFont

# Intentar importar pdf2image, pero no fallar si no existe
try:
    from pdf2image import convert_from_bytes
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False

def generar_carnets_a4(estudiantes_list, logo_path=None, insignia_path=None, incluir_reverso=True, root_path=None):
    """
    Genera PDF A4 con máximo 9 carnets en grid 3x3.
    
    Args:
        estudiantes_list: Lista de objetos.
        logo_path: Ruta al logo por defecto.
        insignia_path: Ruta a la insignia (tiene prioridad sobre logo_path).
        root_path: Ruta base del proyecto.
    """
    PAGE_WIDTH, PAGE_HEIGHT = A4
    mm = mm_unit
    
    # Si no se pasa root_path, intentar adivinar o usar actual
    if root_path is None:
        root_path = os.getcwd()

    # Constantes de Diseño
    MARGEN = 10 * mm
    CARNET_W = 62 * mm
    CARNET_H = 90 * mm
    ESPACIADO = 1 * mm
    COLOR_MORADO = (95/255, 42/255, 93/255)
    COLOR_MORADO_CLARO = (140/255, 80/255, 138/255)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # Calcular número de páginas
    carnets_por_pagina = 9
    num_paginas = (len(estudiantes_list) + 8) // 9

    indice_estudiante = 0

    for pagina in range(num_paginas):
        # --- PÁGINA DE FRENTES ---
        for fila in range(3):
            for col in range(3):
                if indice_estudiante >= len(estudiantes_list):
                    break

                # Calcular posición (desde bottom-left)
                x_start = MARGEN + col * (CARNET_W + ESPACIADO)
                y_start = PAGE_HEIGHT - MARGEN - (fila + 1) * CARNET_H - fila * ESPACIADO

                _dibujar_carnet_frente(
                    c,
                    estudiantes_list[indice_estudiante],
                    x_start,
                    y_start,
                    CARNET_W,
                    CARNET_H,
                    logo_path,
                    insignia_path,  # Pasamos la insignia
                    COLOR_MORADO,
                    COLOR_MORADO_CLARO,
                    root_path
                )

                indice_estudiante += 1

        # --- PÁGINA DE REVERSOS ---
        if incluir_reverso and indice_estudiante > (pagina * 9):
            c.showPage()

            # (en orden inverso para impresión duplex: col 0 -> col 2)
            for fila in range(3):
                for col in range(3):
                    idx_carnet = pagina * 9 + (fila * 3 + col)
                    if idx_carnet >= len(estudiantes_list):
                        break

                    # Posición espejada para reverso
                    x_start = MARGEN + (2 - col) * (CARNET_W + ESPACIADO)
                    y_start = PAGE_HEIGHT - MARGEN - (fila + 1) * CARNET_H - fila * ESPACIADO

                    _dibujar_carnet_reverso(
                        c,
                        estudiantes_list[idx_carnet],
                        x_start,
                        y_start,
                        CARNET_W,
                        CARNET_H,
                        COLOR_MORADO,
                        COLOR_MORADO_CLARO
                    )

        if indice_estudiante < len(estudiantes_list):
            c.showPage()

    c.save()
    buffer.seek(0)
    return buffer


def _dibujar_carnet_frente(c, estudiante, x, y, ancho, alto, logo_path, insignia_path, color_primario, color_secundario, root_path=None):
    """Dibuja el FRENTE con coordenadas AJUSTADAS para QR GRANDE (35mm)"""
    mm = mm_unit
    if root_path is None: root_path = os.getcwd()

    # 1. Fondo y Marco
    c.setFillColorRGB(1, 1, 1)
    c.rect(x, y, ancho, alto, fill=1, stroke=0)

    # Banda decorativa superior
    franja_alto = 14 * mm
    
    c.setFillColorRGB(*color_secundario)
    c.rect(x, y + alto - franja_alto + 4*mm, ancho, 4*mm, fill=1, stroke=0)

    c.setLineWidth(1)
    c.setStrokeColorRGB(*color_primario)
    c.roundRect(x, y, ancho, alto, 3*mm, fill=0)

    # 2. LOGO O INSIGNIA
    imagen_a_usar = insignia_path if insignia_path else logo_path

    # Antes: alto - 17mm. Ahora: alto - 15mm para ganar espacio abajo
    logo_size = 13*mm
    logo_x = x + (ancho/2) - (logo_size/2)
    logo_y = y + alto - 15*mm 
    
    full_image_path = imagen_a_usar
    if imagen_a_usar and not os.path.isabs(imagen_a_usar):
        full_image_path = os.path.join(root_path, imagen_a_usar)

    if full_image_path and os.path.exists(full_image_path):
        try:
            c.drawImage(full_image_path, logo_x, logo_y, width=logo_size, height=logo_size, mask='auto', preserveAspectRatio=True)
        except Exception:
            pass

    # 3. FOTO (SUBIDA)
    # Antes: alto - 42mm. Ahora: alto - 39mm
    foto_size = 22*mm
    foto_x = x + (ancho/2) - (foto_size/2)
    foto_y = y + alto - 39*mm
    
    _dibujar_foto_circular_mejorada(c, estudiante.foto_perfil, foto_x, foto_y, foto_size, color_primario, root_path)

    # 4. INFORMACIÓN (SUBIDA)
    # Antes: alto - 48mm. Ahora: alto - 45mm
    info_y = y + alto - 45*mm

    nombre_completo = f"{estudiante.nombres_est or ''} {estudiante.apellido_paterno_est or ''} {estudiante.apellido_materno_est or ''}".strip()
    if len(nombre_completo) > 28:
        nombre_completo = nombre_completo[:25] + "..."

    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.drawCentredString(x + ancho/2, info_y, nombre_completo.upper())

    # Grado (debajo del nombre)
    grado_y = info_y - 5*mm 
    c.setFont("Helvetica-Bold", 6)
    c.setFillColorRGB(*color_primario)

    nivel_formateado = (estudiante.nivel or '-').capitalize()
    grado = str(estudiante.grado or '-')
    if grado.isdigit():
        grado_text = f"{grado}°"
    else:
        grado_text = grado[:18] + "..." if len(grado) > 20 else grado

    c.drawCentredString(x + ancho/2, grado_y, f"{nivel_formateado} - {grado_text}")

    if estudiante.seccion:
        c.setFont("Helvetica", 5.5)
        c.setFillColorRGB(0.3, 0.3, 0.3)
        c.drawCentredString(x + ancho/2, grado_y - 4*mm, f"Sección: {estudiante.seccion}")

    # 5. CÓDIGO QR (AGRANDADO)
    # Aumentado a 35mm para asegurar visibilidad
    qr_size = 35*mm 
    qr_x = x + (ancho/2) - (qr_size/2)
    # Ajuste fino: un poquito más arriba del borde (4mm)
    qr_y = y + 4*mm 

    _dibujar_qr_codigo(c, estudiante.codigo_estudiante or 'SIN_CODIGO', qr_x, qr_y, qr_size)


def _dibujar_carnet_reverso(c, estudiante, x, y, ancho, alto, color_primario, color_secundario):
    """Dibuja el REVERSO"""
    mm = mm_unit

    c.setFillColorRGB(0.98, 0.98, 1)
    c.rect(x, y, ancho, alto, fill=1, stroke=0)

    c.setLineWidth(1.5)
    c.setStrokeColorRGB(*color_primario)
    c.roundRect(x, y, ancho, alto, 3*mm, fill=0)

    c.setFillColorRGB(*color_secundario)
    c.rect(x, y + alto - 10*mm, ancho, 10*mm, fill=1, stroke=0)

    c.setFont("Helvetica-Bold", 7)
    c.setFillColorRGB(1, 1, 1)
    c.drawCentredString(x + ancho/2, y + alto - 6*mm, "REGLAMENTO ESTUDIANTIL")

    # Normas
    c.setFont("Helvetica-Bold", 5)
    c.setFillColorRGB(*color_primario)
    normas_y = y + alto - 15*mm
    c.drawString(x + 3*mm, normas_y, "NORMAS DE CONVIVENCIA:")

    c.setFont("Helvetica", 4.5)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    normas = [
        "1. Portar el carnet en lugar visible",
        "2. Asistir puntualmente a clases",
        "3. Respetar a compañeros y docentes",
        "4. Cuidar las instalaciones",
        "5. Cumplir con tareas y evaluaciones",
        "6. Mantener higiene personal",
    ]

    norma_y = normas_y - 4*mm
    for norma in normas:
        c.drawString(x + 3*mm, norma_y, norma)
        norma_y -= 3.5*mm

    linea_y = norma_y - 2*mm
    c.setStrokeColorRGB(*color_secundario)
    c.setLineWidth(0.5)
    c.line(x + 3*mm, linea_y, x + ancho - 3*mm, linea_y)

    # Contacto
    c.setFont("Helvetica-Bold", 5)
    c.setFillColorRGB(*color_primario)
    contacto_y = linea_y - 5*mm
    c.drawString(x + 3*mm, contacto_y, "CONTACTO DE EMERGENCIA:")

    c.setFont("Helvetica", 4.5)
    c.setFillColorRGB(0.2, 0.2, 0.2)

    apoderado = f"{estudiante.nombres_apoderado or '-'} {estudiante.apellido_paterno_apoderado or ''}".strip()
    if len(apoderado) > 25: apoderado = apoderado[:22] + "..."

    info_y = contacto_y - 4*mm
    c.drawString(x + 3*mm, info_y, f"Apoderado: {apoderado}")

    info_y -= 3.5*mm
    telefono = estudiante.celular_apoderado or estudiante.telefono_fijo_apoderado or 'Sin registro'
    c.drawString(x + 3*mm, info_y, f"Teléfono: {telefono}")

    # Info Institucional
    c.setFont("Helvetica-Bold", 4.5)
    c.setFillColorRGB(*color_primario)
    inst_y = y + 18*mm
    c.drawCentredString(x + ancho/2, inst_y, "INSTITUCIÓN EDUCATIVA")

    c.setFont("Helvetica", 4)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawCentredString(x + ancho/2, inst_y - 3.5*mm, "Formando líderes del mañana")
    
    # Firma
    c.setFont("Helvetica", 3.5)
    c.setFillColorRGB(0.6, 0.6, 0.6)
    c.drawCentredString(x + ancho/2, y + 3*mm, "________________________")
    c.drawCentredString(x + ancho/2, y + 1*mm, "Firma y Sello")


def _dibujar_foto_circular_mejorada(c, foto_path, x, y, diametro, color_borde, root_path):
    """
    Dibuja la foto del estudiante.
    """
    centro_x = x + diametro/2
    centro_y = y + diametro/2
    radio = diametro/2

    # Sombra
    c.setFillColorRGB(0.85, 0.85, 0.85)
    c.circle(centro_x + mm_unit*0.5, centro_y - mm_unit*0.5, radio, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.circle(centro_x, centro_y, radio, fill=1, stroke=0)

    if foto_path:
        # Lógica de rutas robusta
        if os.path.isabs(foto_path):
            full_path = foto_path
        else:
            clean_path = foto_path.lstrip('/')
            if 'static' in clean_path:
                full_path = os.path.join(root_path, clean_path)
            else:
                full_path = os.path.join(root_path, 'static', clean_path)

        if os.path.exists(full_path):
            try:
                c.saveState()
                p = c.beginPath()
                p.circle(centro_x, centro_y, radio - mm_unit * 0.5)
                c.clipPath(p, stroke=0)
                c.drawImage(full_path, x, y, width=diametro, height=diametro, preserveAspectRatio=True, anchor='c')
                c.restoreState()
            except Exception as e:
                print(f"Error foto: {e}")
                c.setFillColorRGB(0.9, 0.9, 0.9)
                c.circle(centro_x, centro_y, radio - mm_unit, fill=1, stroke=0)

    # Marco
    c.setStrokeColorRGB(*color_borde)
    c.setLineWidth(2)
    c.circle(centro_x, centro_y, radio, fill=0)


def _dibujar_qr_codigo(c, texto, x, y, tamanio):
    """
    Dibuja QR usando transformación de escala (método seguro y estándar).
    """
    try:
        qr_code = qr.QrCodeWidget(str(texto))
        bounds = qr_code.getBounds()
        
        # Ancho original en puntos (sin escalar)
        orig_width = bounds[2] - bounds[0]
        orig_height = bounds[3] - bounds[1]
        
        if orig_width > 0 and orig_height > 0:
            # Calcular factor de escala
            scale_x = tamanio / orig_width
            scale_y = tamanio / orig_height
            
            # Crear Drawing con transformación aplicada
            d = Drawing(tamanio, tamanio, transform=[scale_x, 0, 0, scale_y, 0, 0])
            d.add(qr_code)
            
            renderPDF.draw(d, c, x, y)
        else:
            raise ValueError("QR width/height 0")
            
    except Exception as e:
        print(f"Error dibujando QR: {e}")
        # Fallback si falla la generación
        c.saveState()
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.rect(x, y, tamanio, tamanio, fill=0)
        c.setFont("Helvetica", 5)
        c.drawCentredString(x + tamanio/2, y + tamanio/2, "Error QR")
        c.restoreState()


# ========== EXPORTACIÓN A IMAGEN ==========

def generar_carnet_imagen(estudiante, logo_path=None, insignia_path=None, formato='PNG', root_path=None):
    if root_path is None: root_path = os.getcwd()
    
    if HAS_PDF2IMAGE:
        try:
            from reportlab.pdfgen import canvas as pdf_canvas
            mm = mm_unit
            carnet_w = 62 * mm
            carnet_h = 90 * mm

            buffer_pdf = BytesIO()
            c = pdf_canvas.Canvas(buffer_pdf, pagesize=(carnet_w, carnet_h))
            
            COLOR_MORADO = (95/255, 42/255, 93/255)
            COLOR_MORADO_CLARO = (140/255, 80/255, 138/255)

            _dibujar_carnet_frente(c, estudiante, 0, 0, carnet_w, carnet_h, logo_path, insignia_path, COLOR_MORADO, COLOR_MORADO_CLARO, root_path)
            c.save()
            buffer_pdf.seek(0)

            images = convert_from_bytes(buffer_pdf.read(), dpi=300)
            buffer_img = BytesIO()
            images[0].save(buffer_img, format=formato, quality=95)
            buffer_img.seek(0)
            return buffer_img
        except Exception as e:
            print(f"Error pdf2image: {e}, usando fallback PIL")

    return _generar_carnet_pil(estudiante, logo_path, formato)

def _generar_carnet_pil(estudiante, logo_path, formato):
    # 300 DPI aprox
    width = 732
    height = 1063
    
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    
    morado = (95, 42, 93)
    morado_claro = (140, 80, 138)
    
    # Fondo simple (sin la primera banda morada)
    draw.rectangle([0, 60, width, 100], fill=morado_claro)
    
    try:
        font = ImageFont.load_default()
    except:
        pass
        
    draw.text((width//2 - 50, 40), "CARNET ESTUDIANTIL", fill='white')
    nombres = f"{estudiante.nombres_est} {estudiante.apellido_paterno_est}"
    draw.text((width//2 - 50, 400), nombres, fill='black')
    draw.text((width//2 - 50, height - 150), f"DNI: {estudiante.dni_est}", fill=morado)
    
    buffer = BytesIO()
    img.save(buffer, format=formato)
    buffer.seek(0)
    return buffer