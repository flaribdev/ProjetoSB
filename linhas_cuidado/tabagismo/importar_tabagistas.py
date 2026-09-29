"""importar_tabagistas.py — carga mensal da listagem de pacientes (tabagismo).

Zera a tabela lista_tabagismo e reinsere tudo da planilha. O prontuário é a
chave única; duplicatas dentro da planilha são reportadas e a primeira
ocorrência é mantida.
"""
import re
import sys
import traceback
import unicodedata
from pathlib import Path
import pandas as pd
import sqlite3

# âncora: a pasta onde ESTE script vive (tabagismo/)
BASE = Path(__file__).resolve().parent

# caminhos absolutos construídos a partir da âncora
DB = BASE.parent / "indicadores.db"          # ../indicadores.db — o banco na raiz do projeto
ARQUIVO = BASE.parent / "planilhas" / "Tabagismo.xlsx"   # ../planilhas/Tabagismo.xlsx
ABA = "Página1"
def localizar_cabecalho(xls) -> pd.DataFrame:
    """Lê a planilha sem cabeçalho e encontra a linha dos títulos reais.

    Usa contenção (não igualdade) para tolerar variações como
    'Nº Prontuário', 'No SUS', 'Nome do Paciente' etc.
    """
    bruto = pd.read_excel(xls, sheet_name=0, header=None)

    for i, linha in bruto.iterrows():
        valores = [normalizar_coluna(v) for v in linha if pd.notna(v)]
        tem_equipe = any("equipe" in v for v in valores)
        tem_prontuario = any("prontuario" in v for v in valores)
        if tem_equipe and tem_prontuario:
            print(f"  Cabeçalho encontrado na linha {i}: "
                  f"{[v for v in valores if v]}")
            return pd.read_excel(xls, sheet_name=0, header=i)

    raise ValueError(
        "Cabeçalho não encontrado: nenhuma linha contém 'equipe' e 'prontuario'. "
        f"Primeiras 15 linhas do arquivo:\n{bruto.head(15).to_string()}"
    )
def normalizar_coluna(c) -> str:
    """minúsculas, sem acento, espaços -> underscore."""
    t = unicodedata.normalize("NFKD", str(c).strip().lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"\s+", "_", t)
# nomes possíveis para cada coluna do nosso modelo
CANDIDATOS = {
    "equipe":         ["Equipe","equipe"],
    "microarea":      ["microarea", "micro_area","Microárea"],
    "prontuario":     ["num_prontuario", "prontuario", "n_prontuario",
                       "numero_prontuario", "no_prontuario", "nro_prontuario","Núm. Prontuário"],
    "sus":            ["no_sus", "sus", "cns", "cartao_sus", "numero_sus","Nº SUS"],
    "nome_paciente":  ["nome_do_paciente", "nome_paciente", "nome","Nome do paciente"],
    "idade":          ["idade", "idade_anos","Idade"],
    "atendimento_sb": ["c", "atendimento_sb", "atendimento","C"],
}
def mapear_colunas(colunas_reais: list[str]) -> dict[str, str]:
    """Cada coluna do modelo -> nome real da planilha.

    Estratégia: igualdade exata primeiro; contenção só para candidatos
    com 4+ caracteres (evita 'c' casar dentro de 'microarea').
    """
    norm = {normalizar_coluna(c): c for c in colunas_reais}
    mapa = {}
    faltando = []
    for modelo, candidatos in CANDIDATOS.items():
        achado = None
        # 1ª passada: igualdade exata
        for cand in candidatos:
            if cand in norm:
                achado = norm[cand]
                break
        # 2ª passada: contenção, só para candidatos longos
        if achado is None:
            for cand in candidatos:
                if len(cand) >= 4:
                    real = next((r for chave, r in norm.items() if cand in chave), None)
                    if real:
                        achado = real
                        break
        if achado:
            mapa[modelo] = achado
        else:
            faltando.append(modelo)
    if faltando:
        raise ValueError(
            f"Colunas não encontradas: {faltando}. "
            f"Colunas reais da planilha: {colunas_reais}"
        )
    return mapa
def normalizar_nome(nome) -> str:
    """Maiúsculas sem acento, removendo os tokens SMS e ESB."""
    import unicodedata
    t = unicodedata.normalize("NFKD", str(nome).strip().upper())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(tk for tk in t.split() if tk not in ("SMS", "ESB"))

def converter_atendimento(valor) -> int:
    """SIM/1/TRUE/X -> 1; NAO/0/vazio -> 0."""
    t = str(valor).strip().upper()
    return 1 if t in ("SIM", "1", "TRUE", "X", "S") else 0

def importar_pacientes(xls: str, con: sqlite3.Connection) -> int:
    bruto = localizar_cabecalho(xls)

    # normaliza os nomes das colunas
    bruto.columns = [normalizar_coluna(c) for c in bruto.columns]

    # resolve as colunas do modelo e RENOMEIA para os nomes do modelo
    mapa = mapear_colunas(list(bruto.columns))
    print(f"  Mapeamento: {mapa}")
    bruto = bruto.rename(columns={v: k for k, v in mapa.items()})

    # ---- A PARTIR DAQUI, SÓ NOMES DO MODELO ----
    # descarta linhas de cabeçalho repetidas e linhas sem prontuário
    bruto = bruto[bruto["prontuario"].notna()]
    bruto = bruto[bruto["prontuario"].astype(str).str.strip() != ""]
    bruto = bruto[~bruto["prontuario"].astype(str).str.strip().str.lower()
    .isin(("prontuario", "num_prontuario", "num._prontuario", "nan"))]

    dados = pd.DataFrame({
        "equipe": bruto["equipe"].map(normalizar_nome),
        "microarea": bruto["microarea"].astype(str).str.strip(),
        "prontuario": bruto["prontuario"].astype(str).str.strip(),
        "sus": bruto["sus"].astype(str).str.strip(),
        "nome_paciente": bruto["nome_paciente"].astype(str).str.strip(),
        "idade": pd.to_numeric(bruto["idade"], errors="coerce"),
        "atendimento_sb": bruto["atendimento_sb"].map(converter_atendimento),
    })

    # validações
    sem_nome = dados[dados["nome_paciente"].isin(("", "NAN"))]
    if not sem_nome.empty:
        print(f"  ⚠ {len(sem_nome)} linhas sem nome de paciente (serão mantidas com nome vazio)")

    # duplicatas de prontuário: mantém a primeira, reporta as demais
    duplicadas = dados[dados.duplicated(subset="prontuario", keep="first")]
    if not duplicadas.empty:
        print(f"  ⚠ {len(duplicadas)} prontuários duplicados na planilha "
              f"(mantida a 1ª ocorrência): {duplicadas['prontuario'].head(10).tolist()}")
        dados = dados.drop_duplicates(subset="prontuario", keep="first")

    dados["idade"] = dados["idade"].astype("Int64")

    # carga completa: zera e reinsere
    con.execute("DELETE FROM lista_tabagismo")
    dados[["equipe", "microarea", "prontuario", "sus",
           "nome_paciente", "idade", "atendimento_sb"]].to_sql(
        "lista_tabagismo", con, if_exists="append", index=False)

    com_sb = int(dados["atendimento_sb"].sum())
    print(f"Pacientes importados: {len(dados)} "
          f"(com atendimento SB: {com_sb}, sem: {len(dados) - com_sb})")
    print(f"Equipes presentes: {sorted(dados['equipe'].unique())}")
    return len(dados)

if __name__ == "__main__":
    try:
        print(f"Banco: {DB}")
        print(f"Planilha: {ARQUIVO} (existe? {ARQUIVO.exists()})")
        with sqlite3.connect(DB) as con:
            importar_pacientes(ARQUIVO, con)
    except Exception:
        traceback.print_exc()
        sys.exit(1)