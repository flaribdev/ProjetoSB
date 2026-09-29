"""linhas_cuidado/base.py — funções compartilhadas por todas as linhas de cuidado."""
import sqlite3
import unicodedata

import pandas as pd
import streamlit as st

from config import DB

@st.cache_data(ttl=600)
def carregar_dados(indicador_id: int) -> pd.DataFrame:
    with sqlite3.connect(DB) as con:
        return pd.read_sql(
            "SELECT * FROM dados_indicadores WHERE indicador_id = ?",
            con, params=(indicador_id,),
        )

def carregar_cadastro() -> pd.DataFrame:
    """Vínculos unidade → ESB → ESF do cadastro da tela ⚙️."""
    with sqlite3.connect(DB) as con:
        return pd.read_sql(
            """SELECT u.nome AS unidade, e.nome AS esb, g.nome AS esf
               FROM unidades u
               JOIN esb e ON e.unidade_id = u.id
               JOIN esf g ON g.esb_id = e.id""",
            con,
        )

def normalizar_nome(nome) -> str:
    """Maiúsculas sem acento, removendo os tokens SMS e ESB."""
    t = unicodedata.normalize("NFKD", str(nome).strip().upper())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(tk for tk in t.split() if tk not in ("SMS", "ESB"))

def indicador_mensal(df: pd.DataFrame, local_nome: str) -> pd.DataFrame:
    d = df[df["local_nome"] == local_nome].sort_values("mes_ref")
    d = d.groupby("mes_ref", as_index=False)[["numerador", "denominador"]].sum()
    d["percentual"] = (
        d["numerador"] / d["denominador"].replace(0, pd.NA) * 100
    ).astype("Float64").round(1)
    return d

def indicador_esb(df: pd.DataFrame, esb_nome: str) -> pd.DataFrame:
    """Soma as ESFs da ESB e calcula o percentual mensal."""
    with sqlite3.connect(DB) as con:
        esf = pd.read_sql(
            """SELECT g.nome FROM esf g
               JOIN esb e ON e.id = g.esb_id WHERE e.nome = ?""",
            con, params=(esb_nome,),
        )
    d = df[df["local_nome"].isin(esf["nome"])]
    d = d.groupby("mes_ref", as_index=False)[["numerador", "denominador"]].sum()
    d["percentual"] = (
        d["numerador"] / d["denominador"].replace(0, pd.NA) * 100
    ).astype("Float64").round(1)
    return d