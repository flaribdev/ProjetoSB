"""cria_admin.py — cria a conta do administrador."""
import sqlite3
from usuarios import hash_senha

with sqlite3.connect("../indicadores.db") as con:
    con.execute(
        "INSERT OR IGNORE INTO usuarios (email, senha_hash, perfil, unidade_id, ativo) "
        "VALUES (?, ?, 'area', NULL, 1)",
        ("flavioribeirocap22@gmail.com", hash_senha("SiteCap22@")),
    )
print("Admin criado")