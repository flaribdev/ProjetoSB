"""linhas_cuidado/tabagismo/listagem.py — listagem de pacientes tabagistas."""
import io
import sqlite3

import pandas as pd
import streamlit as st

from config import DB
from linhas_cuidado.base import carregar_cadastro

@st.cache_data(ttl=600)
def carregar_pacientes() -> pd.DataFrame:
    with sqlite3.connect(DB) as con:
        return pd.read_sql("SELECT * FROM lista_tabagismo", con)

def tela_listagem(linhas_unid: pd.DataFrame, mes_ref: str):
    """Renderiza a listagem. Recebe o vínculo unidade → ESB → ESF do usuário."""
    st.divider()
    st.subheader("👥 Listagem de pacientes tabagistas")
    pacientes = carregar_pacientes()

    # admin (linhas_unid vazio) enxerga o cadastro inteiro
    vinculos = carregar_cadastro() if linhas_unid.empty else linhas_unid

    if vinculos.empty:
        st.warning("Nenhuma ESB cadastrada para esta unidade. Cadastre em ⚙️ Configuração.")
        return

    # mapa ESB -> ESFs vinculadas
    mapa_esb = (
        vinculos.groupby("esb")["esf"]
        .apply(lambda s: sorted(s.unique()))
        .to_dict()
    )

    c_f0, c_f1, c_f2, c_f3 = st.columns([2, 1.5, 1, 1])
    with c_f0:
        esb_sel = st.selectbox(
            "Equipe de saúde bucal (ESB)",
            ["Todas as ESBs"] + sorted(mapa_esb),
        )
    with c_f1:
        # subfiltro opcional: ESFs da ESB escolhida
        esfs_da_esb = sorted({e for lista in mapa_esb.values() for e in lista}) \
            if esb_sel == "Todas as ESBs" else mapa_esb[esb_sel]
        esf_sel = st.selectbox("ESF", ["Todas as ESFs"] + esfs_da_esb)
    with c_f2:
        atendimento_filtro = st.selectbox(
            "Atendimento SB", ["Todos", "Sem atendimento", "Com atendimento"])
    with c_f3:
        busca = st.text_input("Buscar por nome")

    cobertura = set(pacientes["equipe"].unique()) & set(esfs_da_esb)
    faltantes = set(esfs_da_esb) - cobertura
    if faltantes:
        st.caption(
            f"⚠ ESFs cadastradas sem pacientes na planilha atual: "
            f"{sorted(faltantes)}"
        )

    lista = pacientes[pacientes["equipe"].isin(esfs_da_esb)]
    if esf_sel != "Todas as ESFs":
        lista = lista[lista["equipe"] == esf_sel]

    if atendimento_filtro == "Sem atendimento":
        lista = lista[lista["atendimento_sb"] == 0]
    elif atendimento_filtro == "Com atendimento":
        lista = lista[lista["atendimento_sb"] == 1]
    if busca.strip():
        lista = lista[lista["nome_paciente"].str.upper()
                      .str.contains(busca.strip().upper(), na=False)]

    st.caption(f"{len(lista)} pacientes encontrados")
    st.dataframe(
        lista[["equipe", "microarea", "prontuario", "sus",
               "nome_paciente", "idade", "atendimento_sb"]]
        .rename(columns={"atendimento_sb": "Atendido SB"}),
        use_container_width=True, hide_index=True,
        column_config={"Atendido SB": st.column_config.CheckboxColumn("Atendido SB")},
    )

    if not lista.empty:
        buffer = io.BytesIO()
        lista[["equipe", "microarea", "prontuario", "sus",
               "nome_paciente", "idade", "atendimento_sb"]].to_excel(
            buffer, index=False, sheet_name="pacientes")
        st.download_button(
            "📥 Exportar para Excel",
            data=buffer.getvalue(),
            file_name=f"tabagistas_{mes_ref}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )