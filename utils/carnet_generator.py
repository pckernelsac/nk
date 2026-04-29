"""
Generador de carnets estudiantiles con código QR — versión moderna.

Características principales:
- Frente con header en degradado, logo institucional, foto circular con anillo
  blanco y fallback de iniciales cuando el estudiante no tiene foto.
- Badge tipo pill para grado/nivel y footer inferior con el código.
- Reverso limpio con tarjeta de normas, contacto de emergencia y datos del
  centro educativo.
- Exportación a PDF (A4, 9 por página) y a imagen PNG/JPG individual.
"""
from io import BytesIO
import os

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm as mm_unit
from reportlab.lib.pagesizes import A4
from reportlab.graphics.barcode import qr
from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing
from PIL import Image, ImageDraw, ImageFont

try:
    from pdf2image import convert_from_bytes
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False


# ─────────────────────────── Helpers visuales ────────────────────────────

def _mix(c1, c2, t):
    """Interpolación lineal entre dos colores RGB 0-1."""
    return (
        c1[0] + (c2[0] - c1[0]) * t,
        c1[1] + (c2[1] - c1[1]) * t,
        c1[2] + (c2[2] - c1[2]) * t,
    )


def _draw_vertical_gradient(c, x, y, w, h, color_top, color_bottom, steps=50):
    """Simula un gradiente vertical pintando `steps` franjas."""
    step_h = h / steps
    for i in range(steps):
        t = i / (steps - 1 if steps > 1 else 1)
        r, g, b = _mix(color_top, color_bottom, t)
        c.setFillColorRGB(r, g, b)
        # Pintamos de arriba hacia abajo con un ligero solape para evitar líneas.
        c.rect(x, y + h - (i + 1) * step_h, w, step_h + 0.3, fill=1, stroke=0)


def _iniciales(estudiante):
    """Calcula 1-2 iniciales a partir de nombres y apellidos."""
    n = (getattr(estudiante, 'nombres_est', '') or '').strip()
    ap = (getattr(estudiante, 'apellido_paterno_est', '') or '').strip()
    am = (getattr(estudiante, 'apellido_materno_est', '') or '').strip()
    ini = ''
    if n:
        ini += n[0]
    if ap:
        ini += ap[0]
    elif am:
        ini += am[0]
    return (ini.upper() or '?')[:2]


# ───────────────────────────── PDF A4 (9 x pág) ───────────────────────────

def generar_carnets_a4(estudiantes_list, logo_path=None, insignia_path=None, incluir_reverso=True, root_path=None):
    """Genera PDF A4 con 9 carnets en grid 3x3 (frente y opcionalmente reverso)."""
    PAGE_WIDTH, PAGE_HEIGHT = A4
    mm = mm_unit

    if root_path is None:
        root_path = os.getcwd()

    MARGEN = 10 * mm
    CARNET_W = 50 * mm
    CARNET_H = 80 * mm
    ESPACIADO = 1 * mm
    COLOR_MORADO = (95 / 255, 42 / 255, 93 / 255)
    COLOR_MORADO_CLARO = (140 / 255, 80 / 255, 138 / 255)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    num_paginas = (len(estudiantes_list) + 8) // 9
    indice_estudiante = 0

    for pagina in range(num_paginas):
        # Frente
        for fila in range(3):
            for col in range(3):
                if indice_estudiante >= len(estudiantes_list):
                    break
                x_start = MARGEN + col * (CARNET_W + ESPACIADO)
                y_start = PAGE_HEIGHT - MARGEN - (fila + 1) * CARNET_H - fila * ESPACIADO
                _dibujar_carnet_frente(
                    c,
                    estudiantes_list[indice_estudiante],
                    x_start, y_start,
                    CARNET_W, CARNET_H,
                    logo_path, insignia_path,
                    COLOR_MORADO, COLOR_MORADO_CLARO,
                    root_path,
                )
                indice_estudiante += 1

        # Reverso (orden espejado para impresión duplex)
        if incluir_reverso and indice_estudiante > (pagina * 9):
            c.showPage()
            for fila in range(3):
                for col in range(3):
                    idx_carnet = pagina * 9 + (fila * 3 + col)
                    if idx_carnet >= len(estudiantes_list):
                        break
                    x_start = MARGEN + (2 - col) * (CARNET_W + ESPACIADO)
                    y_start = PAGE_HEIGHT - MARGEN - (fila + 1) * CARNET_H - fila * ESPACIADO
                    _dibujar_carnet_reverso(
                        c,
                        estudiantes_list[idx_carnet],
                        x_start, y_start,
                        CARNET_W, CARNET_H,
                        COLOR_MORADO, COLOR_MORADO_CLARO,
                    )

        if indice_estudiante < len(estudiantes_list):
            c.showPage()

    c.save()
    buffer.seek(0)
    return buffer


# ─────────────────────────────── Frente ───────────────────────────────────

def _dibujar_carnet_frente(c, estudiante, x, y, ancho, alto,
                            logo_path, insignia_path,
                            color_primario, color_secundario, root_path=None):
    """Dibuja la cara frontal del carnet con diseño moderno."""
    mm = mm_unit
    if root_path is None:
        root_path = os.getcwd()

    # Variantes de color
    color_oscuro = (max(0, color_primario[0] * 0.65),
                    max(0, color_primario[1] * 0.65),
                    max(0, color_primario[2] * 0.65))

    # 1) Fondo blanco y clip a esquinas redondeadas ──────────────────────
    c.saveState()
    path_clip = c.beginPath()
    path_clip.roundRect(x, y, ancho, alto, 3.2 * mm)
    c.clipPath(path_clip, stroke=0, fill=0)

    c.setFillColorRGB(1, 1, 1)
    c.rect(x, y, ancho, alto, fill=1, stroke=0)

    # 2) Header con gradiente ────────────────────────────────────────────
    header_h = 20 * mm
    _draw_vertical_gradient(
        c,
        x, y + alto - header_h,
        ancho, header_h,
        color_oscuro, color_secundario,
        steps=45,
    )

    # Detalle decorativo: círculo semitransparente en esquina (simulado con color más claro)
    c.setFillColorRGB(*_mix(color_secundario, (1, 1, 1), 0.2))
    c.circle(x + ancho - 3 * mm, y + alto - 3 * mm, 6 * mm, fill=1, stroke=0)
    c.setFillColorRGB(*_mix(color_oscuro, (1, 1, 1), 0.15))
    c.circle(x + 2 * mm, y + alto - header_h + 2 * mm, 4 * mm, fill=1, stroke=0)

    # 3) Logo + título institución en header ──────────────────────────────
    imagen_a_usar = insignia_path if insignia_path else logo_path
    logo_size = 10 * mm
    logo_x = x + 3 * mm
    logo_y = y + alto - 13 * mm

    full_image_path = imagen_a_usar
    if imagen_a_usar and not os.path.isabs(imagen_a_usar):
        full_image_path = os.path.join(root_path, imagen_a_usar)
    if full_image_path and os.path.exists(full_image_path):
        try:
            c.drawImage(
                full_image_path,
                logo_x, logo_y,
                width=logo_size, height=logo_size,
                mask='auto', preserveAspectRatio=True,
            )
        except Exception:
            pass

    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x + 15 * mm, y + alto - 7.5 * mm, "NK CHAMBERGO")
    c.setFont("Helvetica", 5.5)
    c.drawString(x + 15 * mm, y + alto - 10.8 * mm, "CARNET ESTUDIANTIL")

    # Separador delgado al pie del header
    c.setFillColorRGB(*_mix(color_oscuro, (0, 0, 0), 0.3))
    c.rect(x, y + alto - header_h, ancho, 0.6 * mm, fill=1, stroke=0)

    # 4) Foto circular con anillo blanco (overlap con header) ─────────────
    foto_size = 18 * mm
    foto_x = x + (ancho / 2) - (foto_size / 2)
    foto_y = y + alto - header_h - 9 * mm  # overlap ~ mitad/mitad

    # Anillo blanco exterior (efecto tarjeta)
    c.setFillColorRGB(1, 1, 1)
    c.circle(
        foto_x + foto_size / 2,
        foto_y + foto_size / 2,
        foto_size / 2 + 1.2 * mm,
        fill=1, stroke=0,
    )
    _dibujar_foto_circular_mejorada(
        c, estudiante,
        foto_x, foto_y, foto_size,
        color_primario, color_secundario,
        root_path,
    )

    # 5) Nombres (apellidos en negrita + nombres abajo) ──────────────────
    apellidos = (
        f"{estudiante.apellido_paterno_est or ''} {estudiante.apellido_materno_est or ''}".strip()
    )
    nombres = (estudiante.nombres_est or '').strip()
    if len(apellidos) > 30:
        apellidos = apellidos[:27] + '...'
    if len(nombres) > 30:
        nombres = nombres[:27] + '...'

    nombre_y = foto_y - 4 * mm
    c.setFont("Helvetica-Bold", 7)
    c.setFillColorRGB(0.11, 0.11, 0.18)
    c.drawCentredString(x + ancho / 2, nombre_y, apellidos.upper())

    c.setFont("Helvetica", 6.5)
    c.setFillColorRGB(0.32, 0.32, 0.38)
    c.drawCentredString(x + ancho / 2, nombre_y - 3.4 * mm, nombres)

    # 6) Badge grado/nivel (pill) ─────────────────────────────────────────
    nivel = (estudiante.nivel or '').upper() or '-'
    grado_raw = str(estudiante.grado or '').strip() or '-'
    if grado_raw.isdigit():
        badge_text = f"{grado_raw}° {nivel}"
    else:
        # Si "grado" es no numérico (ej: programa de academia) lo mostramos tal cual
        badge_text = grado_raw.upper() if len(grado_raw) <= 18 else grado_raw[:16].upper() + '...'
        if nivel and nivel != '-' and nivel not in badge_text:
            # Intentar agregar nivel si queda compacto
            combo = f"{nivel} · {badge_text}"
            if len(combo) <= 22:
                badge_text = combo

    badge_y_center = nombre_y - 9 * mm
    badge_font_size = 6
    badge_text_w = c.stringWidth(badge_text, "Helvetica-Bold", badge_font_size)
    badge_w = min(ancho - 6 * mm, badge_text_w + 6 * mm)
    badge_h = 4.6 * mm
    badge_x = x + ancho / 2 - badge_w / 2
    badge_y = badge_y_center - badge_h / 2

    c.setFillColorRGB(*color_primario)
    c.roundRect(badge_x, badge_y, badge_w, badge_h, badge_h / 2, fill=1, stroke=0)

    c.setFont("Helvetica-Bold", badge_font_size)
    c.setFillColorRGB(1, 1, 1)
    c.drawCentredString(x + ancho / 2, badge_y + 1.3 * mm, badge_text)

    # 7) Sección ──────────────────────────────────────────────────────────
    if estudiante.seccion:
        c.setFont("Helvetica", 5.5)
        c.setFillColorRGB(0.35, 0.35, 0.4)
        c.drawCentredString(
            x + ancho / 2,
            badge_y - 3.2 * mm,
            f"Sección: {estudiante.seccion}",
        )

    # 8) QR code con fondo suave ──────────────────────────────────────────
    qr_size = 20 * mm
    qr_x = x + ancho / 2 - qr_size / 2
    qr_y = y + 8 * mm  # deja espacio para el footer + aire

    # Tarjeta tenue detrás del QR
    c.setFillColorRGB(0.965, 0.96, 0.97)
    c.roundRect(
        qr_x - 1.5 * mm, qr_y - 1.5 * mm,
        qr_size + 3 * mm, qr_size + 3 * mm,
        1.6 * mm, fill=1, stroke=0,
    )
    _dibujar_qr_codigo(
        c,
        estudiante.codigo_estudiante or 'SIN_CODIGO',
        qr_x, qr_y, qr_size,
    )

    # 9) Footer con código ───────────────────────────────────────────────
    footer_h = 6 * mm
    c.setFillColorRGB(*color_primario)
    c.rect(x, y, ancho, footer_h, fill=1, stroke=0)

    codigo = (estudiante.codigo_estudiante or '').strip() or 'SIN CÓDIGO'
    if len(codigo) > 24:
        codigo = codigo[:22] + '...'
    c.setFont("Helvetica-Bold", 6.5)
    c.setFillColorRGB(1, 1, 1)
    c.drawCentredString(x + ancho / 2, y + 2.6 * mm, f"CÓDIGO: {codigo}")

    c.restoreState()

    # Borde exterior (fuera del clip para que se vea limpio)
    c.setLineWidth(1.2)
    c.setStrokeColorRGB(*color_primario)
    c.roundRect(x, y, ancho, alto, 3.2 * mm, fill=0)


# ───────────────────────────── Reverso ───────────────────────────────────

def _dibujar_carnet_reverso(c, estudiante, x, y, ancho, alto,
                             color_primario, color_secundario):
    """Reverso modernizado con tarjetas internas y normas."""
    mm = mm_unit

    color_oscuro = (max(0, color_primario[0] * 0.65),
                    max(0, color_primario[1] * 0.65),
                    max(0, color_primario[2] * 0.65))

    # Fondo + clip
    c.saveState()
    path_clip = c.beginPath()
    path_clip.roundRect(x, y, ancho, alto, 3.2 * mm)
    c.clipPath(path_clip, stroke=0, fill=0)

    c.setFillColorRGB(0.985, 0.98, 0.99)
    c.rect(x, y, ancho, alto, fill=1, stroke=0)

    # Header con gradiente (más compacto que el frente)
    header_h = 11 * mm
    _draw_vertical_gradient(
        c,
        x, y + alto - header_h,
        ancho, header_h,
        color_oscuro, color_secundario, steps=30,
    )

    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColorRGB(1, 1, 1)
    c.drawCentredString(x + ancho / 2, y + alto - 7.5 * mm, "REGLAMENTO ESTUDIANTIL")

    # Tarjeta "Normas" ────────────────────────────────────────────────────
    card_x = x + 3 * mm
    card_w = ancho - 6 * mm
    card_top = y + alto - header_h - 3 * mm
    normas_card_h = 27 * mm

    c.setFillColorRGB(1, 1, 1)
    c.roundRect(card_x, card_top - normas_card_h, card_w, normas_card_h, 1.8 * mm, fill=1, stroke=0)

    c.setFont("Helvetica-Bold", 5.2)
    c.setFillColorRGB(*color_primario)
    c.drawString(card_x + 2 * mm, card_top - 4 * mm, "NORMAS DE CONVIVENCIA")

    # Línea sutil bajo el título
    c.setStrokeColorRGB(*color_secundario)
    c.setLineWidth(0.4)
    c.line(card_x + 2 * mm, card_top - 5 * mm, card_x + card_w - 2 * mm, card_top - 5 * mm)

    normas = [
        "Portar el carnet en lugar visible",
        "Asistir puntualmente a clases",
        "Respetar a compañeros y docentes",
        "Cuidar las instalaciones",
        "Cumplir con tareas y evaluaciones",
        "Mantener higiene personal",
    ]
    c.setFont("Helvetica", 4.6)
    c.setFillColorRGB(0.22, 0.22, 0.28)
    norma_y = card_top - 8.5 * mm
    for i, norma in enumerate(normas, start=1):
        # Viñeta como círculo pequeño del color primario
        c.setFillColorRGB(*color_primario)
        c.circle(card_x + 3 * mm, norma_y + 0.9 * mm, 0.6 * mm, fill=1, stroke=0)
        c.setFillColorRGB(0.22, 0.22, 0.28)
        c.drawString(card_x + 4.8 * mm, norma_y, norma)
        norma_y -= 3.6 * mm

    # Tarjeta "Contacto de emergencia" ───────────────────────────────────
    contacto_card_h = 14 * mm
    contacto_top = card_top - normas_card_h - 2.5 * mm

    c.setFillColorRGB(*_mix(color_secundario, (1, 1, 1), 0.85))
    c.roundRect(card_x, contacto_top - contacto_card_h, card_w, contacto_card_h, 1.6 * mm, fill=1, stroke=0)

    c.setFont("Helvetica-Bold", 5.2)
    c.setFillColorRGB(*color_primario)
    c.drawString(card_x + 2 * mm, contacto_top - 4 * mm, "CONTACTO DE EMERGENCIA")

    apoderado = f"{estudiante.nombres_apoderado or '-'} {estudiante.apellido_paterno_apoderado or ''}".strip()
    if len(apoderado) > 26:
        apoderado = apoderado[:24] + '...'
    telefono = estudiante.celular_apoderado or estudiante.telefono_fijo_apoderado or 'Sin registro'

    c.setFont("Helvetica", 4.6)
    c.setFillColorRGB(0.22, 0.22, 0.28)
    c.drawString(card_x + 2 * mm, contacto_top - 7.5 * mm, f"Apoderado: {apoderado}")
    c.drawString(card_x + 2 * mm, contacto_top - 10.8 * mm, f"Teléfono: {telefono}")

    # Pie institucional ──────────────────────────────────────────────────
    c.setFont("Helvetica-Bold", 5.2)
    c.setFillColorRGB(*color_primario)
    c.drawCentredString(x + ancho / 2, y + 9 * mm, "NK CHAMBERGO")

    c.setFont("Helvetica-Oblique", 4.2)
    c.setFillColorRGB(0.4, 0.4, 0.45)
    c.drawCentredString(x + ancho / 2, y + 6 * mm, "Formando líderes del mañana")

    # Línea y firma
    c.setStrokeColorRGB(0.65, 0.65, 0.7)
    c.setLineWidth(0.4)
    c.line(x + ancho / 2 - 14 * mm, y + 3.8 * mm, x + ancho / 2 + 14 * mm, y + 3.8 * mm)
    c.setFont("Helvetica", 4)
    c.setFillColorRGB(0.5, 0.5, 0.55)
    c.drawCentredString(x + ancho / 2, y + 2 * mm, "Firma y Sello")

    c.restoreState()

    # Borde exterior
    c.setLineWidth(1.2)
    c.setStrokeColorRGB(*color_primario)
    c.roundRect(x, y, ancho, alto, 3.2 * mm, fill=0)


# ──────────────────────── Foto con fallback de iniciales ─────────────────

def _dibujar_foto_circular_mejorada(c, estudiante, x, y, diametro,
                                    color_borde, color_fallback, root_path):
    """
    Dibuja la foto del estudiante recortada en círculo. Si no hay foto o no
    puede cargarse, pinta un círculo de color con las iniciales en blanco.
    """
    mm = mm_unit
    centro_x = x + diametro / 2
    centro_y = y + diametro / 2
    radio = diametro / 2

    foto_path = getattr(estudiante, 'foto_perfil', None)
    foto_dibujada = False

    if foto_path:
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
                p.circle(centro_x, centro_y, radio - 0.3 * mm)
                c.clipPath(p, stroke=0, fill=0)
                c.drawImage(
                    full_path, x, y,
                    width=diametro, height=diametro,
                    preserveAspectRatio=True, anchor='c',
                    mask='auto',
                )
                c.restoreState()
                foto_dibujada = True
            except Exception as e:
                print(f"Error cargando foto del carnet: {e}")

    if not foto_dibujada:
        # Fallback: círculo con gradiente simulado + iniciales ──────────
        # Capa base (color oscuro)
        color_fondo_oscuro = (color_borde[0] * 0.75, color_borde[1] * 0.75, color_borde[2] * 0.75)
        c.setFillColorRGB(*color_fondo_oscuro)
        c.circle(centro_x, centro_y, radio - 0.3 * mm, fill=1, stroke=0)

        # Capa clara superior (efecto lustre en el tercio superior)
        c.saveState()
        pclip = c.beginPath()
        pclip.circle(centro_x, centro_y, radio - 0.3 * mm)
        c.clipPath(pclip, stroke=0, fill=0)
        c.setFillColorRGB(*color_fallback)
        # Medio círculo superior simulado con rect
        c.rect(
            centro_x - radio,
            centro_y,
            diametro,
            radio,
            fill=1, stroke=0,
        )
        c.restoreState()

        # Iniciales centradas
        iniciales = _iniciales(estudiante)
        # Tamaño de fuente proporcional al diámetro (en puntos, no en mm)
        font_size_pts = diametro * 0.42  # diametro está en puntos (1mm = ~2.83pt)
        c.setFont("Helvetica-Bold", font_size_pts)
        c.setFillColorRGB(1, 1, 1)
        # Ajuste vertical para centrar (Helvetica baseline ≈ 0.3*fontSize por debajo del centro óptico)
        c.drawCentredString(centro_x, centro_y - font_size_pts * 0.33, iniciales)

    # Marco exterior
    c.setStrokeColorRGB(*color_borde)
    c.setLineWidth(1.4)
    c.circle(centro_x, centro_y, radio, fill=0)


# ──────────────────────────────── QR ─────────────────────────────────────

def _dibujar_qr_codigo(c, texto, x, y, tamanio):
    """Dibuja un QR del tamaño indicado usando transformación de escala."""
    try:
        qr_code = qr.QrCodeWidget(str(texto))
        bounds = qr_code.getBounds()
        orig_width = bounds[2] - bounds[0]
        orig_height = bounds[3] - bounds[1]

        if orig_width > 0 and orig_height > 0:
            scale_x = tamanio / orig_width
            scale_y = tamanio / orig_height
            d = Drawing(tamanio, tamanio, transform=[scale_x, 0, 0, scale_y, 0, 0])
            d.add(qr_code)
            renderPDF.draw(d, c, x, y)
        else:
            raise ValueError("QR width/height 0")
    except Exception as e:
        print(f"Error dibujando QR: {e}")
        c.saveState()
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.rect(x, y, tamanio, tamanio, fill=0)
        c.setFont("Helvetica", 5)
        c.drawCentredString(x + tamanio / 2, y + tamanio / 2, "Error QR")
        c.restoreState()


# ───────────────────── Exportación a imagen individual ───────────────────

def generar_carnet_imagen(estudiante, logo_path=None, insignia_path=None, formato='PNG', root_path=None):
    """Genera una imagen PNG/JPG del frente del carnet (usa pdf2image si está)."""
    if root_path is None:
        root_path = os.getcwd()

    if HAS_PDF2IMAGE:
        try:
            from reportlab.pdfgen import canvas as pdf_canvas
            mm = mm_unit
            carnet_w = 50 * mm
            carnet_h = 80 * mm

            buffer_pdf = BytesIO()
            c = pdf_canvas.Canvas(buffer_pdf, pagesize=(carnet_w, carnet_h))

            COLOR_MORADO = (95 / 255, 42 / 255, 93 / 255)
            COLOR_MORADO_CLARO = (140 / 255, 80 / 255, 138 / 255)

            _dibujar_carnet_frente(
                c, estudiante, 0, 0, carnet_w, carnet_h,
                logo_path, insignia_path,
                COLOR_MORADO, COLOR_MORADO_CLARO, root_path,
            )
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
    """Fallback muy básico usando PIL cuando no hay pdf2image."""
    width, height = 732, 1063
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)

    morado = (95, 42, 93)
    morado_claro = (140, 80, 138)

    # Header (aprox 24mm a 300dpi ≈ 283 px)
    draw.rectangle([0, 0, width, 283], fill=morado)

    try:
        font_title = ImageFont.load_default()
    except Exception:
        font_title = None

    if font_title:
        draw.text((30, 60), "NK CHAMBERGO", fill='white', font=font_title)
        draw.text((30, 90), "CARNET ESTUDIANTIL", fill='white', font=font_title)

    # Círculo foto con iniciales
    cx, cy, r = width // 2, 330, 110
    draw.ellipse([cx - r - 12, cy - r - 12, cx + r + 12, cy + r + 12], fill='white')
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=morado_claro)
    iniciales = _iniciales(estudiante)
    draw.text((cx - 25, cy - 25), iniciales, fill='white', font=font_title)

    # Nombre
    apellidos = f"{estudiante.apellido_paterno_est or ''} {estudiante.apellido_materno_est or ''}".strip().upper()
    nombres = (estudiante.nombres_est or '').strip()
    draw.text((width // 2 - 120, cy + r + 30), apellidos, fill='black', font=font_title)
    draw.text((width // 2 - 80, cy + r + 55), nombres, fill='gray', font=font_title)

    # Footer código
    draw.rectangle([0, height - 70, width, height], fill=morado)
    if font_title:
        draw.text((width // 2 - 80, height - 50), f"CÓDIGO: {estudiante.codigo_estudiante or 'S/C'}", fill='white', font=font_title)

    buffer = BytesIO()
    img.save(buffer, format=formato)
    buffer.seek(0)
    return buffer
