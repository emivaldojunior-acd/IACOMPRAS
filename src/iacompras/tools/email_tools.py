import smtplib
import ssl
import configparser
from email.message import EmailMessage


def send_email(
    to_email: str,
    subject: str,
    body: str,
    smtp_section: str,
    config_path: str = "smtp_config.ini",
):

    config = configparser.ConfigParser()
    config.read(config_path)

    if smtp_section not in config:
        raise RuntimeError(f"Seção {smtp_section} não encontrada no smtp_config.ini")

    smtp_host = config[smtp_section]["HOST"]
    smtp_port = int(config[smtp_section]["PORT"])
    smtp_user = config[smtp_section]["USER"]
    smtp_pass = config[smtp_section]["PASS"]

    msg = EmailMessage()
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls(context=context)
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
