"""
Importador do indicador de Tabagismo (Saúde Bucal)
Fonte: Tabagismo-2026.xlsx — abas mensais tabagismo_2026_<mes>
Denominador: a_var3_g10_a (tabagistas cadastrados)
Numerador:   c_var3_g10_c (atendidos pela SB nos últimos 12 meses)

Classificação das linhas da coluna 'area':
  - 'AP 2.2'            -> área de planejamento (total)
  - começa com 'SMS'    -> unidade
  - termina com '**'    -> IGNORAR
  - demais              -> equipe de saúde bucal
  - linhas não numéricas (rodapé com definições) -> IGNORAR
Colunas ignoradas: b_var3_g10_b, d_var3_g10_d, total
"""

import re
import sqlite3
from pathlib import Path
import unicodedata
import pandas as pd

# ----------------- CONFIGURAÇÃO -----------------
DB = "indicadores.db"
ARQUIVO = Path("../../planilhas/Tabagismo-2026.xlsx")
INDICADOR_ID = 1
ANO = 2026

MESES = {
    "jan": "01", "fev": "02", "mar": "03", "abr": "04",
    "mai": "05", "jun": "06", "jul": "07", "ago": "08",
    "set": "09", "out": "10", "nov": "11", "dez": "12",
}

COL_AREA = "Area"
PREFIXO_DENOM = "A (VAR3.G10_A"   # denominador (tabagistas cadastrados)
PREFIXO_NUM = "C (VAR3.G10_C"     # numerador (atendidos SB últimos 12 meses)
PADRAO_ABA = re.compile(r"^(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)$")
NOME_AREA = "AP 2.2"          # linha do total da área de planejamento
PREFIXO_UNIDADE = "SMS"       # unidades começam com SMS
SUFIXO_IGNORAR = "**"         # linhas de equipes terminando com ** são descartadas

def normalizar(texto) -> str:
    """Minúsculas, sem espaços, pontos, parênteses ou hífens."""
    t = str(texto).strip().lower()
    for ch in (" ", ".", "(", ")", "-"):
        t = t.replace(ch, "")
    return t

def achar_coluna(colunas, prefixo: str) -> str:
    """Encontra a coluna cujo nome normalizado começa com o prefixo normalizado."""
    alvo = normalizar(prefixo)
    correspondentes = [c for c in colunas if normalizar(c).startswith(alvo)]
    if len(correspondentes) != 1:
        raise ValueError(
            f"Esperava exatamente 1 coluna começando com '{prefixo}', "
            f"encontrei: {correspondentes}"
        )
    return correspondentes[0]
def detectar_linha_cabecalho(xls, aba: str) -> int | None:
    """Localiza a linha do cabeçalho real. Retorna None se a aba estiver vazia."""
    bruto = pd.read_excel(xls, sheet_name=aba, header=None, nrows=20)
    if bruto.empty or bruto.shape[1] == 0:
        return None  # aba sem dados (meses futuros)
    for i, valor in enumerate(bruto.iloc[:, 0]):
        if normalizar(valor) == "area":
            return i
    raise ValueError(f"Aba '{aba}': linha de cabeçalho com 'Area' não encontrada")
# ----------------- BANCO -----------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS dados_indicadores (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    indicador_id  INTEGER NOT NULL,
    mes_ref       TEXT    NOT NULL,           -- 'AAAA-MM'
    local_nome    TEXT    NOT NULL,           -- nome da área, unidade ou equipe
    local_tipo    TEXT    NOT NULL,           -- 'area' | 'unidade' | 'equipe'
    numerador     INTEGER NOT NULL,
    denominador   INTEGER NOT NULL,
    UNIQUE (indicador_id, mes_ref, local_nome, local_tipo)
);
"""

def normalizar_nome(nome) -> str:
    """Maiúsculas sem acento, removendo os tokens SMS e ESB."""
    t = unicodedata.normalize("NFKD", str(nome).strip().upper())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(tk for tk in t.split() if tk not in ("SMS", "ESB"))
def criar_schema(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA)

# ----------------- CLASSIFICAÇÃO -----------------
def classificar(nome: str) -> str | None:
    """Retorna 'area', 'unidade', 'equipe' ou None (ignorar)."""
    nome = nome.strip()
    if nome.endswith(SUFIXO_IGNORAR):
        return None
    if nome.upper() == NOME_AREA.upper():
        return "area"
    if nome.upper().startswith(PREFIXO_UNIDADE):
        return "unidade"
    return "equipe"

# ----------------- IMPORTAÇÃO -----------------
def importar_aba_equipes(xls, con) -> int:
    """Lê a aba EQUIPES e grava o mapa equipe -> unidade."""
    bruto = pd.read_excel(xls, sheet_name="EQUIPES", header=None)
    pares = []
    for _, linha in bruto.iterrows():
        col_unid, col_eq = linha.iloc[0], linha.iloc[1]
        if pd.isna(col_unid) or pd.isna(col_eq):
            continue
        if pd.notna(pd.to_numeric(col_eq, errors="coerce")):
            continue  # bloco de resumo com percentuais
        nome_unid, nome_eq = str(col_unid).strip().upper(), str(col_eq).strip().upper()
        if nome_unid == "UNIDADE" or nome_eq in ("—", "-"):
            continue  # linhas de rótulo
        pares.append((normalizar_nome(nome_eq), normalizar_nome(nome_unid)))
    df_map = pd.DataFrame(pares, columns=["equipe", "unidade"]).drop_duplicates()
    con.execute("DELETE FROM equipes_unidades")
    df_map.to_sql("equipes_unidades", con, if_exists="append", index=False)
    print(f"Mapa equipes↔unidades: {len(df_map)} pares importados")
    print(df_map.to_string(index=False))  # conferência visual
    return len(df_map)

def importar_aba(df: pd.DataFrame, mes_ref: str, con: sqlite3.Connection) -> int:
    """Valida, limpa, classifica e grava uma aba mensal."""
    try:
        col_denom = achar_coluna(df.columns, PREFIXO_DENOM)
        col_num = achar_coluna(df.columns, PREFIXO_NUM)
        col_area = achar_coluna(df.columns, COL_AREA)
    except ValueError as e:
        raise ValueError(f"Aba de {mes_ref}: {e}") from e

    dados = df[[col_area, col_denom, col_num]].copy()
    dados.columns = ["local_nome", "denominador", "numerador"]

    # remove linhas sem nome e converte números; não numérico -> NaN -> descarta
    dados = dados.dropna(subset=["local_nome"])
    dados["local_nome"] = dados["local_nome"].astype(str).str.strip()
    dados = dados[dados["local_nome"] != ""]
    for col in ("denominador", "numerador"):
        dados[col] = pd.to_numeric(dados[col], errors="coerce")
    dados = dados.dropna(subset=["denominador", "numerador"])
    dados["denominador"] = dados["denominador"].astype(int)
    dados["numerador"] = dados["numerador"].astype(int)

    # consistência: numerador não pode passar do denominador
    invalidas = dados[dados["numerador"] > dados["denominador"]]
    if not invalidas.empty:
        raise ValueError(
            f"Aba de {mes_ref}: numerador > denominador em: "
            f"{invalidas['local_nome'].tolist()}"
        )

    # 1) classifica sobre o nome BRUTO (precisa do SMS e do **)
    dados["local_tipo"] = dados["local_nome"].apply(classificar)
    descartadas = dados[dados["local_tipo"].isna()]["local_nome"].tolist()
    if descartadas:
        print(f"  [{mes_ref}] linhas ignoradas: {descartadas}")
    dados = dados.dropna(subset=["local_tipo"])

    # 2) normaliza o nome (gravação padronizada no banco)
    dados["local_nome"] = dados["local_nome"].map(normalizar_nome)

    # 3) consolida duplicatas DEPOIS de normalizar
    duplicadas = dados[dados.duplicated(subset=["local_nome", "local_tipo"], keep=False)]
    if not duplicadas.empty:
        nomes = duplicadas["local_nome"].unique().tolist()
        print(f"  [{mes_ref}] linhas duplicadas consolidadas (somadas): {nomes}")
        dados = (
            dados.groupby(["local_nome", "local_tipo"], as_index=False)
            [["numerador", "denominador"]]
            .sum()
        )

    dados["indicador_id"] = INDICADOR_ID
    dados["mes_ref"] = mes_ref
    con.execute(
        "DELETE FROM dados_indicadores WHERE indicador_id = ? AND mes_ref = ?",
        (INDICADOR_ID, mes_ref),
    )
    dados[["indicador_id", "mes_ref", "local_nome", "local_tipo",
           "numerador", "denominador"]].to_sql(
        "dados_indicadores", con, if_exists="append", index=False
    )
    return len(dados)

def importar_planilha(caminho: Path) -> dict:
    if not caminho.exists():
        raise FileNotFoundError(f"Planilha não encontrada: {caminho}")

    with sqlite3.connect(DB) as con:
        criar_schema(con)
        xls = pd.ExcelFile(caminho)
        resumo = {}
        for aba in xls.sheet_names:
            # 1º: FILTRA — só processa abas mensais (jan, fev, ...)
            if not PADRAO_ABA.match(aba.strip().lower()):
                continue  # ignora EQUIPES, 2tri e outras
            mes_ref = f"{ANO}-{MESES[aba.strip().lower()]}"

            # 2º: detecta a linha do cabeçalho e lê com ela
            header = detectar_linha_cabecalho(xls, aba)
            if header is None:
                print(f"  [{aba}] aba vazia — nenhum dado ainda, pulando")
                continue
            df = pd.read_excel(xls, sheet_name=aba, header=header)

            # 3º: importa
            resumo[mes_ref] = importar_aba(df, mes_ref, con)
        con.commit()
    return resumo

if __name__ == "__main__":
    import traceback

    print("=" * 50)
    print("DIAGNÓSTICO")
    print("=" * 50)

    # 1. O arquivo está onde o script espera?
    print(f"Caminho procurado : {ARQUIVO}")
    print(f"Arquivo existe?   : {ARQUIVO.exists()}")
    print(f"Pasta atual       : {Path.cwd()}")

    if not ARQUIVO.exists():
        print("\n>>> PROBLEMA: arquivo não encontrado nesse caminho.")
        print(">>> Verifique se a pasta 'planilhas' está ao lado de onde você roda o script.")
    else:
        # 2. Quais abas o pandas enxerga?
        xls = pd.ExcelFile(ARQUIVO)
        print(f"\nAbas encontradas ({len(xls.sheet_names)}):")
        for aba in xls.sheet_names:
            casa = bool(PADRAO_ABA.match(aba))
            print(f"  - '{aba}'  -> casa com o padrão? {casa}")

        # 3. Importação com erro completo visível
        try:
            resultado = importar_planilha(ARQUIVO)
            print("\nRESULTADO:")
            if not resultado:
                print("  Nenhuma aba foi importada!")
            for mes, linhas in sorted(resultado.items()):
                print(f"  {mes}: {linhas} linhas importadas")
        except Exception:
            print("\n>>> ERRO DURANTE A IMPORTAÇÃO:")
            traceback.print_exc()