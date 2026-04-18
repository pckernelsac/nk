"""
Email SMTP directo: configuración desde config.Config.
Compat: Message + mail.send() con la misma forma de uso que los helpers legacy.
"""
from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Iterable

from config import Config


@dataclass
class Message:
    subject: str
    recipients: list
    body: str | None = None
    html: str | None = None
    sender: tuple[str, str] | None = None


class _Mail:
    def send(self, msg: Message) -> None:
        send_mail(
            msg.subject,
            msg.recipients,
            msg.body or "",
            html=msg.html,
            sender=msg.sender,
        )


mail = _Mail()


def send_mail(
    subject: str,
    recipients: Iterable[str],
    body: str,
    html: str | None = None,
    sender: tuple[str, str] | None = None,
) -> None:
    """Envía correo SMTP síncrono (API esperada por utils/email_helper)."""
    if getattr(Config, "MAIL_SUPPRESS_SEND", False):
        return

    user = Config.MAIL_USERNAME
    password = Config.MAIL_PASSWORD
    if not user or not password:
        raise RuntimeError("MAIL_USERNAME / MAIL_PASSWORD no configurados")

    from_addr, from_name = sender or Config.MAIL_DEFAULT_SENDER
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, from_addr))
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body, "plain", "utf-8"))
    if html:
        msg.attach(MIMEText(html, "html", "utf-8"))

    if Config.MAIL_USE_SSL:
        server = smtplib.SMTP_SSL(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=30)
    else:
        server = smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=30)
    try:
        if Config.MAIL_USE_TLS and not Config.MAIL_USE_SSL:
            server.starttls()
        server.login(user, password)
        server.sendmail(from_addr, list(recipients), msg.as_string())
    finally:
        server.quit()
