# utils/email_helper.py
"""
Helper functions para envío de notificaciones por email
"""
from config import Config
from extensions import Message, mail
import logging

# Configurar logging
logger = logging.getLogger(__name__)


def enviar_notificacion_asistencia(estudiante, tipo_asistencia, fecha_hora_str):
    """
    Envía notificación de asistencia por email a los padres del estudiante

    Args:
        estudiante: Objeto Estudiante con información del alumno
        tipo_asistencia: String 'ENTRADA' o 'SALIDA'
        fecha_hora_str: String con fecha y hora formateada

    Returns:
        dict: {'success': bool, 'message': str}
    """
    try:
        # Obtener emails de padres
        emails_destinatarios = []

        if estudiante.correo_padre and estudiante.correo_padre.strip():
            emails_destinatarios.append(estudiante.correo_padre.strip())

        if estudiante.correo_madre and estudiante.correo_madre.strip():
            emails_destinatarios.append(estudiante.correo_madre.strip())

        if estudiante.correo_apoderado and estudiante.correo_apoderado.strip():
            emails_destinatarios.append(estudiante.correo_apoderado.strip())

        # Si no hay emails, no se puede enviar
        if not emails_destinatarios:
            logger.warning(f"No hay emails configurados para el estudiante {estudiante.dni_est}")
            return {
                'success': False,
                'message': 'No hay correos electrónicos registrados para los padres'
            }

        # Eliminar duplicados
        emails_destinatarios = list(set(emails_destinatarios))

        # Obtener nombre completo del estudiante
        nombre_estudiante = f"{estudiante.nombres_est} {estudiante.apellido_paterno_est} {estudiante.apellido_materno_est}"

        # Obtener nombre del padre/madre/apoderado para el saludo
        nombre_padre = ""
        if estudiante.nombres_padre and estudiante.nombres_padre.strip():
            nombre_padre = estudiante.nombres_padre.strip()
        elif estudiante.nombres_madre and estudiante.nombres_madre.strip():
            nombre_padre = estudiante.nombres_madre.strip()
        elif estudiante.nombres_apoderado and estudiante.nombres_apoderado.strip():
            nombre_padre = estudiante.nombres_apoderado.strip()
        else:
            nombre_padre = "Estimado padre/madre/apoderado"

        # Determinar tipo de acción
        tipo_texto = "ingresado al" if tipo_asistencia == "ENTRADA" else "salido del"

        # Componer asunto y mensaje
        subject = f"Notificación de {tipo_asistencia.capitalize()} - Intranet Colegio y NK Chambergo"

        body = f"""Hola {nombre_padre},

Su hijo/a {nombre_estudiante} acaba de {tipo_texto.lower()} colegio a las {fecha_hora_str}.

Este es un mensaje automático del sistema de control de asistencia.

Saludos cordiales,
Colegio y NK Chambergo
"""

        # Crear mensaje
        msg = Message(
            subject=subject,
            recipients=emails_destinatarios,
            body=body
        )

        # Intentar enviar con manejo de errores SSL
        try:
            mail.send(msg)
        except Exception as ssl_error:
            # Si falla, intentar con SMTP directo y contexto SSL personalizado
            logger.warning(f"Error al enviar por SMTP principal, intentando método alternativo: {ssl_error}")

            import ssl
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # Crear contexto SSL permisivo
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            try:
                # Crear mensaje MIME
                mime_msg = MIMEText(msg.body, 'plain', 'utf-8')
                mime_msg['Subject'] = msg.subject
                mime_msg['From'] = Config.MAIL_USERNAME
                mime_msg['To'] = ', '.join(msg.recipients)

                # Conectar y enviar con múltiples métodos de fallback
                mail_server = Config.MAIL_SERVER
                mail_username = Config.MAIL_USERNAME
                mail_password = Config.MAIL_PASSWORD

                # Intentar primero con SMTP_SSL (puerto 465)
                try:
                    with smtplib.SMTP_SSL(mail_server, 465, timeout=30, context=ssl_context) as server:
                        server.login(mail_username, mail_password)
                        server.send_message(mime_msg)
                    logger.info("Email enviado con SMTP_SSL (puerto 465)")
                    return
                except Exception as ssl_error:
                    logger.warning(f"Fallo con SMTP_SSL puerto 465: {ssl_error}")

                # Si falla, intentar con SMTP + STARTTLS (puerto 587)
                try:
                    with smtplib.SMTP(mail_server, 587, timeout=30) as server:
                        server.starttls(context=ssl_context)
                        server.login(mail_username, mail_password)
                        server.send_message(mime_msg)
                    logger.info("Email enviado con SMTP + STARTTLS (puerto 587)")
                    return
                except Exception as tls_error:
                    logger.warning(f"Fallo con SMTP puerto 587: {tls_error}")
                    raise  # Re-lanzar el error si ambos métodos fallan

                logger.info("Email enviado exitosamente con método alternativo")
            except Exception as final_error:
                logger.error(f"Error final al enviar email: {final_error}")
                raise

        logger.info(f"Notificación de {tipo_asistencia} enviada exitosamente para estudiante {estudiante.dni_est} a {len(emails_destinatarios)} destinatario(s)")

        return {
            'success': True,
            'message': f'Notificación enviada a {len(emails_destinatarios)} destinatario(s)'
        }

    except Exception as e:
        logger.error(f"Error al enviar notificación de asistencia para estudiante {estudiante.dni_est}: {str(e)}")
        return {
            'success': False,
            'message': f'Error al enviar notificación: {str(e)}'
        }


def enviar_notificacion_asistencia_data(estudiante_data, tipo_asistencia, fecha_hora_str):
    """
    Envía notificación usando un diccionario de datos del estudiante (para usar en threads)

    Args:
        estudiante_data: Dict con datos del estudiante
        tipo_asistencia: String 'ENTRADA' o 'SALIDA'
        fecha_hora_str: String con fecha y hora formateada

    Returns:
        dict: {'success': bool, 'message': str}
    """
    try:
        # Obtener emails de padres del diccionario
        emails_destinatarios = []

        if estudiante_data.get('correo_padre') and estudiante_data['correo_padre'].strip():
            emails_destinatarios.append(estudiante_data['correo_padre'].strip())

        if estudiante_data.get('correo_madre') and estudiante_data['correo_madre'].strip():
            emails_destinatarios.append(estudiante_data['correo_madre'].strip())

        if estudiante_data.get('correo_apoderado') and estudiante_data['correo_apoderado'].strip():
            emails_destinatarios.append(estudiante_data['correo_apoderado'].strip())

        # Si no hay emails, no se puede enviar
        if not emails_destinatarios:
            logger.warning(f"No hay emails configurados para el estudiante {estudiante_data['dni_est']}")
            return {
                'success': False,
                'message': 'No hay correos electrónicos registrados para los padres'
            }

        # Eliminar duplicados
        emails_destinatarios = list(set(emails_destinatarios))

        # Obtener nombre completo del estudiante
        nombre_estudiante = f"{estudiante_data['nombres_est']} {estudiante_data['apellido_paterno_est']} {estudiante_data['apellido_materno_est']}"

        # Obtener nombre del padre/madre/apoderado para el saludo
        nombre_padre = ""
        if estudiante_data.get('nombres_padre') and estudiante_data['nombres_padre'].strip():
            nombre_padre = estudiante_data['nombres_padre'].strip()
        elif estudiante_data.get('nombres_madre') and estudiante_data['nombres_madre'].strip():
            nombre_padre = estudiante_data['nombres_madre'].strip()
        elif estudiante_data.get('nombres_apoderado') and estudiante_data['nombres_apoderado'].strip():
            nombre_padre = estudiante_data['nombres_apoderado'].strip()
        else:
            nombre_padre = "Estimado padre/madre/apoderado"

        # Determinar tipo de acción
        tipo_texto = "ingresado al" if tipo_asistencia == "ENTRADA" else "salido del"

        # Componer asunto y mensaje
        subject = f"Notificación de {tipo_asistencia.capitalize()} - Colegio NK Chambergo"

        body = f"""Hola {nombre_padre},

Su hijo/a {nombre_estudiante} ha {tipo_texto} colegio a las {fecha_hora_str}.

Este es un mensaje automático del sistema de control de asistencia.

Saludos cordiales,
Colegio NK Chambergo
"""

        # Crear mensaje
        msg = Message(
            subject=subject,
            recipients=emails_destinatarios,
            body=body
        )

        # Intentar enviar con manejo de errores SSL
        try:
            mail.send(msg)
        except Exception as ssl_error:
            # Si falla, intentar con SMTP directo y contexto SSL personalizado
            logger.warning(f"Error al enviar por SMTP principal, intentando método alternativo: {ssl_error}")

            import ssl
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # Crear contexto SSL permisivo
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            try:
                # Crear mensaje MIME
                mime_msg = MIMEText(msg.body, 'plain', 'utf-8')
                mime_msg['Subject'] = msg.subject
                mime_msg['From'] = Config.MAIL_USERNAME
                mime_msg['To'] = ', '.join(msg.recipients)

                # Conectar y enviar con múltiples métodos de fallback
                mail_server = Config.MAIL_SERVER
                mail_username = Config.MAIL_USERNAME
                mail_password = Config.MAIL_PASSWORD

                # Intentar primero con SMTP_SSL (puerto 465)
                try:
                    with smtplib.SMTP_SSL(mail_server, 465, timeout=30, context=ssl_context) as server:
                        server.login(mail_username, mail_password)
                        server.send_message(mime_msg)
                    logger.info("Email enviado con SMTP_SSL (puerto 465)")
                    return
                except Exception as ssl_error:
                    logger.warning(f"Fallo con SMTP_SSL puerto 465: {ssl_error}")

                # Si falla, intentar con SMTP + STARTTLS (puerto 587)
                try:
                    with smtplib.SMTP(mail_server, 587, timeout=30) as server:
                        server.starttls(context=ssl_context)
                        server.login(mail_username, mail_password)
                        server.send_message(mime_msg)
                    logger.info("Email enviado con SMTP + STARTTLS (puerto 587)")
                    return
                except Exception as tls_error:
                    logger.warning(f"Fallo con SMTP puerto 587: {tls_error}")
                    raise  # Re-lanzar el error si ambos métodos fallan

                logger.info("Email enviado exitosamente con método alternativo")
            except Exception as final_error:
                logger.error(f"Error final al enviar email: {final_error}")
                raise

        logger.info(f"Notificación de {tipo_asistencia} enviada exitosamente para estudiante {estudiante_data['dni_est']} a {len(emails_destinatarios)} destinatario(s)")

        return {
            'success': True,
            'message': f'Notificación enviada a {len(emails_destinatarios)} destinatario(s)'
        }

    except Exception as e:
        logger.error(f"Error al enviar notificación de asistencia para estudiante {estudiante_data['dni_est']}: {str(e)}")
        return {
            'success': False,
            'message': f'Error al enviar notificación: {str(e)}'
        }


def enviar_notificacion_asistencia_async(estudiante, tipo_asistencia, fecha_hora_str):
    """
    Versión asíncrona de envío de notificación (para no bloquear la respuesta)
    Usa threading para enviar el email en segundo plano

    Args:
        estudiante: Objeto Estudiante con información del alumno
        tipo_asistencia: String 'ENTRADA' o 'SALIDA'
        fecha_hora_str: String con fecha y hora formateada
    """
    from threading import Thread

    # Extraer todos los datos necesarios del estudiante ANTES de pasar al thread
    # Esto evita el error DetachedInstanceError de SQLAlchemy
    estudiante_data = {
        'dni_est': estudiante.dni_est,
        'nombres_est': estudiante.nombres_est,
        'apellido_paterno_est': estudiante.apellido_paterno_est,
        'apellido_materno_est': estudiante.apellido_materno_est,
        'correo_padre': estudiante.correo_padre,
        'correo_madre': estudiante.correo_madre,
        'correo_apoderado': estudiante.correo_apoderado,
        'nombres_padre': estudiante.nombres_padre if hasattr(estudiante, 'nombres_padre') else None,
        'nombres_madre': estudiante.nombres_madre if hasattr(estudiante, 'nombres_madre') else None,
        'nombres_apoderado': estudiante.nombres_apoderado if hasattr(estudiante, 'nombres_apoderado') else None,
    }

    def send_async_email(estudiante_data, tipo_asistencia, fecha_hora_str):
        """Función interna para enviar email en thread separado"""
        import time
        # Pequeño delay para evitar rate limiting de Gmail
        time.sleep(2)
        enviar_notificacion_asistencia_data(estudiante_data, tipo_asistencia, fecha_hora_str)

    # Crear thread para envío asíncrono
    thread = Thread(
        target=send_async_email,
        args=(estudiante_data, tipo_asistencia, fecha_hora_str)
    )
    thread.start()

    logger.info(f"Email de notificación programado en segundo plano para estudiante {estudiante_data['dni_est']}")


def enviar_notificacion_duplicado_async(estudiante, tipo_asistencia, hora_intento, hora_original):
    """
    Versión asíncrona para envío de notificación de escaneo duplicado

    Args:
        estudiante: Objeto Estudiante con información del alumno
        tipo_asistencia: String 'ENTRADA' o 'SALIDA'
        hora_intento: Hora del intento duplicado
        hora_original: Hora del registro original
    """
    from threading import Thread

    # Extraer datos del estudiante
    estudiante_data = {
        'dni_est': estudiante.dni_est,
        'nombres_est': estudiante.nombres_est,
        'apellido_paterno_est': estudiante.apellido_paterno_est,
        'apellido_materno_est': estudiante.apellido_materno_est,
        'correo_padre': estudiante.correo_padre,
        'correo_madre': estudiante.correo_madre,
        'correo_apoderado': estudiante.correo_apoderado,
        'nombres_padre': estudiante.nombres_padre if hasattr(estudiante, 'nombres_padre') else None,
        'nombres_madre': estudiante.nombres_madre if hasattr(estudiante, 'nombres_madre') else None,
        'nombres_apoderado': estudiante.nombres_apoderado if hasattr(estudiante, 'nombres_apoderado') else None,
    }

    def send_async_duplicado_email(estudiante_data, tipo_asistencia, hora_intento, hora_original):
        """Función interna para enviar email de duplicado en thread separado"""
        import time
        time.sleep(2)
        enviar_email_duplicado(estudiante_data, tipo_asistencia, hora_intento, hora_original)

    # Crear thread para envío asíncrono
    thread = Thread(
        target=send_async_duplicado_email,
        args=(estudiante_data, tipo_asistencia, hora_intento, hora_original)
    )
    thread.start()

    logger.info(f"Email de notificación de duplicado programado para estudiante {estudiante_data['dni_est']}")


def enviar_email_duplicado(estudiante_data, tipo_asistencia, hora_intento, hora_original):
    """
    Envía email notificando un intento de registro duplicado

    Args:
        estudiante_data: Dict con datos del estudiante
        tipo_asistencia: String 'ENTRADA' o 'SALIDA'
        hora_intento: Hora del intento duplicado
        hora_original: Hora del registro original

    Returns:
        dict: {'success': bool, 'message': str}
    """
    try:
        # Obtener emails de padres
        emails_destinatarios = []

        if estudiante_data.get('correo_padre') and estudiante_data['correo_padre'].strip():
            emails_destinatarios.append(estudiante_data['correo_padre'].strip())

        if estudiante_data.get('correo_madre') and estudiante_data['correo_madre'].strip():
            emails_destinatarios.append(estudiante_data['correo_madre'].strip())

        if estudiante_data.get('correo_apoderado') and estudiante_data['correo_apoderado'].strip():
            emails_destinatarios.append(estudiante_data['correo_apoderado'].strip())

        # Si no hay emails, no se puede enviar
        if not emails_destinatarios:
            logger.warning(f"No hay emails configurados para el estudiante {estudiante_data['dni_est']}")
            return {
                'success': False,
                'message': 'No hay correos electrónicos registrados'
            }

        # Eliminar duplicados
        emails_destinatarios = list(set(emails_destinatarios))

        # Obtener nombre completo del estudiante
        nombre_estudiante = f"{estudiante_data['nombres_est']} {estudiante_data['apellido_paterno_est']} {estudiante_data['apellido_materno_est']}"

        # Obtener nombre del padre/madre/apoderado
        nombre_padre = ""
        if estudiante_data.get('nombres_padre') and estudiante_data['nombres_padre'].strip():
            nombre_padre = estudiante_data['nombres_padre'].strip()
        elif estudiante_data.get('nombres_madre') and estudiante_data['nombres_madre'].strip():
            nombre_padre = estudiante_data['nombres_madre'].strip()
        elif estudiante_data.get('nombres_apoderado') and estudiante_data['nombres_apoderado'].strip():
            nombre_padre = estudiante_data['nombres_apoderado'].strip()
        else:
            nombre_padre = "Estimado padre/madre/apoderado"

        # Determinar tipo de acción
        tipo_texto = "ENTRADA" if tipo_asistencia == "ENTRADA" else "SALIDA"

        # Componer asunto y mensaje
        subject = f"Notificación: Intento de {tipo_texto} Duplicado - Colegio NK Chambergo"

        body = f"""Hola {nombre_padre},

Le informamos que su hijo/a {nombre_estudiante} intentó registrar su {tipo_texto.lower()} nuevamente a las {hora_intento}.

Sin embargo, ya había registrado su {tipo_texto.lower()} anteriormente hoy a las {hora_original}.

Este es un mensaje automático del sistema de control de asistencia.

Nota: Este mensaje es solo informativo. El registro original a las {hora_original} sigue siendo válido.

Saludos cordiales,
Colegio NK Chambergo
"""

        # Crear mensaje
        msg = Message(
            subject=subject,
            recipients=emails_destinatarios,
            body=body
        )

        # Intentar enviar con manejo de errores SSL
        try:
            mail.send(msg)
        except Exception as ssl_error:
            logger.warning(f"Error al enviar por SMTP principal, intentando método alternativo: {ssl_error}")

            import ssl
            import smtplib
            from email.mime.text import MIMEText

            # Crear contexto SSL permisivo
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            try:
                # Crear mensaje MIME
                mime_msg = MIMEText(msg.body, 'plain', 'utf-8')
                mime_msg['Subject'] = msg.subject
                mime_msg['From'] = Config.MAIL_USERNAME
                mime_msg['To'] = ', '.join(msg.recipients)

                # Conectar y enviar con múltiples métodos de fallback
                mail_server = Config.MAIL_SERVER
                mail_username = Config.MAIL_USERNAME
                mail_password = Config.MAIL_PASSWORD

                # Intentar primero con SMTP_SSL (puerto 465)
                try:
                    with smtplib.SMTP_SSL(mail_server, 465, timeout=30, context=ssl_context) as server:
                        server.login(mail_username, mail_password)
                        server.send_message(mime_msg)
                    logger.info("Email de duplicado enviado con SMTP_SSL (puerto 465)")
                    return
                except Exception as ssl_error:
                    logger.warning(f"Fallo con SMTP_SSL puerto 465: {ssl_error}")

                # Si falla, intentar con SMTP + STARTTLS (puerto 587)
                try:
                    with smtplib.SMTP(mail_server, 587, timeout=30) as server:
                        server.starttls(context=ssl_context)
                        server.login(mail_username, mail_password)
                        server.send_message(mime_msg)
                    logger.info("Email de duplicado enviado con SMTP + STARTTLS (puerto 587)")
                    return
                except Exception as tls_error:
                    logger.warning(f"Fallo con SMTP puerto 587: {tls_error}")
                    raise

                logger.info("Email de duplicado enviado exitosamente con método alternativo")
            except Exception as final_error:
                logger.error(f"Error final al enviar email de duplicado: {final_error}")
                raise

        logger.info(f"Email de duplicado enviado exitosamente para estudiante {estudiante_data['dni_est']} a {len(emails_destinatarios)} destinatario(s)")

        return {
            'success': True,
            'message': f'Notificación de duplicado enviada a {len(emails_destinatarios)} destinatario(s)'
        }

    except Exception as e:
        logger.error(f"Error al enviar notificación de duplicado para estudiante {estudiante_data['dni_est']}: {str(e)}")
        return {
            'success': False,
            'message': f'Error al enviar notificación: {str(e)}'
        }
