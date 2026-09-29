import sqlite3

DB = "indicadores.db"

def _con():
    return sqlite3.connect(DB)


SCHEMA = """DROP TABLE IF EXISTS listaTabagismo;"""
def criar_schema(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)

if __name__ == '__main__':
    criar_schema(con=_con())