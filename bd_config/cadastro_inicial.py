"""semeia_cadastro.py — carga inicial do cadastro a partir do mapa conhecido."""
import sqlite3

MAPA = {  # unidade: [grupos]
    "CF ODALEA FIRMO DUTRA": ["ADOLFO CAMINHA", "SANTO ESTEVAO", "ARAXA", "FURNAS"],
    "CF RECANTO DO TROVADOR": ["POPULAR", "MARTINHO DA VILA"],
    "CMS CARLOS FIGUEIREDO FILHO": ["TERREIRAO", "SEMENTE","LADEIRA"],
    "CMS CASA BRANCA": ["CASA BRANCA"],
    "CMS HEITOR BELTRAO": ["SALGUEIRO", "BARAO DE PIRASSINUNGA", "CATRAMBI", "SABOIA LIMA"],
    "CMS HELIO PELLEGRINO": ["VILLA LOBOS", "PRACA DA BANDEIRA 1", "BANDEIRA"],
    "CMS MARIA AUGUSTA ESTRELLA": ["SENADOR", "MIGUEL PEDRO", "CONSELHEIRO"],
    "CMS NICOLA ALBANO": ["BOA VISTA"],
    "CMS NILZA ROSA": ["RAIA"]
}
ESFS = {
    "ADOLFO CAMINHA":"ITORORO",
    "SANTO ESTEVAO":["GASTAO PENALVA I","GASTAO PENALVA II"],
    "ARAXA":"UBERABA",
    "FURNAS":"ESPERANCA",
    "POPULAR":"",
    "MARTINHO DA VILA":"",
    "TERREIRAO":"",
    "SEMENTE":"",
    "LADEIRA":"",
    "CASA BRANCA":"",
    "SALGUEIRO":"",
    "BARAO DE PIRASSINUNGA":"",
    "CATRAMBI":"",
    "SABOIA LIMA":"",
    "VILLA LOBOS":"",
    "PRACA DA BANDEIRA 1":"",
    "BANDEIRA":"",
    "SENADOR":"",
    "MIGUEL PEDRO":"",
    "CONSELHEIRO":"",
    "BOA VISTA":"",
    "RAIA":""
}

with sqlite3.connect("../indicadores.db") as con:
    for unidade, grupos in MAPA.items():
        cur = con.execute("INSERT OR IGNORE INTO unidades (nome) VALUES (?)", (unidade,))
        unid_id = cur.lastrowid or con.execute(
            "SELECT id FROM unidades WHERE nome = ?", (unidade,)).fetchone()[0]
        for grupo in grupos:
            esb_nome = f"{grupo} ESB"
            cur = con.execute("INSERT OR IGNORE INTO esb (nome, unidade_id) VALUES (?, ?)",
                              (esb_nome, unid_id))
            esb_id = cur.lastrowid or con.execute(
                "SELECT id FROM esb WHERE nome = ?", (esb_nome,)).fetchone()[0]
            con.execute("INSERT OR IGNORE INTO esf (nome, esb_id) VALUES (?, ?)",
                        (grupo, esb_id))
    print("Cadastro semeado.")