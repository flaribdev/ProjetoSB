"""usuarios.py — hash de senha e validação."""

import hashlib
import re
import secrets

def hash_senha(senha: str) -> str:
    """Gera hash PBKDF2 com salt aleatório (formato: salt$digest)."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt.encode(), 100_000)
    return f"{salt}${digest.hex()}"

def verificar_senha(senha: str, armazenada: str) -> bool:
    salt, digest = armazenada.split("$", 1)
    teste = hashlib.pbkdf2_hmac("sha256", senha.encode(), salt.encode(), 100_000)
    return secrets.compare_digest(teste.hex(), digest)

def senha_valida(senha: str) -> tuple[bool, str]:
    """Exige no mínimo 8 caracteres, com pelo menos uma letra e um número."""
    if len(senha) < 8:
        return False, "A senha deve ter no mínimo 8 caracteres."
    if not re.search(r"[A-Za-z]", senha):
        return False, "A senha deve conter pelo menos uma letra."
    if not re.search(r"\d", senha):
        return False, "A senha deve conter pelo menos um número."
    return True, ""