"""envia_email.py — envio de e-mail via SMTP (credenciais em variáveis de ambiente)."""

import os
import smtplib
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_SENHA = os.environ.get("SMTP_SENHA", "")
URL_SISTEMA = os.environ.get("URL_SISTEMA", "http://localhost:8501")

def enviar_email_ativacao(destinatario: str) -> None:
    corpo = (
        "Olá,\n\n"
        "Seu acesso ao sistema Indicadores de Saúde Bucal foi ativado.\n\n"
        f"Acesse: {URL_SISTEMA}\n\n"
        "Use o e-mail deste endereço e a senha que você cadastrou.\n"
    )
    msg = MIMEText(corpo, "plain", "utf-8")
    msg["Subject"] = "Acesso ativado — Indicadores de Saúde Bucal"
    msg["From"] = SMTP_USER
    msg["To"] = destinatario
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_SENHA)
        smtp.send_message(msg)

def enviar_email_redefinicao(destinatario: str, codigo: str) -> None:
    corpo = (
        "Olá,\n\n"
        "Recebemos um pedido de redefinição de senha para o sistema "
        "Indicadores de Saúde Bucal.\n\n"
        f"Código de redefinição: {codigo}\n"
        "Este código é válido por 30 minutos e pode ser usado uma única vez.\n\n"
        "Se você não pediu a redefinição, ignore este e-mail.\n"
    )
    msg = MIMEText(corpo, "plain", "utf-8")
    msg["Subject"] = "Redefinição de senha — Indicadores de Saúde Bucal"
    msg["From"] = SMTP_USER
    msg["To"] = destinatario
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_SENHA)
        smtp.send_message(msg)