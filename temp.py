"""teste_email.py — valida a configuração SMTP enviando um e-mail de teste."""

import os
from envia_email import enviar_email_ativacao

destino = os.environ.get("SMTP_USER", "")
assert destino, "Exporte SMTP_USER antes de rodar."

enviar_email_ativacao(destino)  # envia para você mesmo
print("Enviado para", destino)